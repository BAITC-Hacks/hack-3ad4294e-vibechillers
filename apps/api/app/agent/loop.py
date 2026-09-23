"""The agent loop: prompt in, SSE-shaped events out.

`run_agent` drives `llm.stream` in a bounded tool-calling cycle, executes
registered tools through `tools.call_tool`, and mirrors every event into
`agent_trace` via `TraceWriter` before yielding it. The contract is strict:
events arrive in `seq` order and the stream terminates with exactly one
`final` or one `error` — never a traceback, never stdout, never two
terminals (even when the SDK raises mid-delivery or the consumer abandons
the generator).

Structure: `_drive` is an async generator holding the conversation state
machine; it yields `_Step` requests and receives results through `asend`.
The pump (the `run_agent` loop) performs the awaits `_drive` cannot make
itself — pull one piece from the model stream, run one tool call — and hands
the outcome back as plain data (never an exception). `emit` writes each event
through `TraceWriter` and queues it; the pump drains the queue after every
step, so `token` events reach the consumer live and every event is persisted
before it is yielded.

Nothing here is domain-specific: the system line only tells the model it may
call tools and how to cite what it finds.
"""

from __future__ import annotations

import json
import re
import sqlite3
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from .. import db
from ..config import get_settings
from ..events import Event, SequenceCounter
from . import llm
from .tools import ToolRegistry, call_tool, to_function_schema
from .trace import TraceWriter, install_tracing, set_current_run

MAX_TURNS = 6  # hard cap on model round-trips per run
CITATION_TOOL = "search_documents"
MIN_FRAGMENT_CHARS = 60
SNIPPET_CHARS = 200

SYSTEM_LINE = (
    "You are a helpful assistant. You may call the provided tools to find "
    "information; answer strictly from what the tools return and quote the "
    "exact passages you used. Always reply in the user's language."
)


@dataclass
class _Pending:
    """A tool call the pump must execute before `_drive` continues."""

    name: str
    args: dict[str, Any]
    call_id: str
    decode_error: str | None = None


@dataclass
class _Step:
    """One request from `_drive` to its pump.

    kind "turn": pump opens llm.stream(messages, tools=tools) and asends back
    the first piece. kind "chunk": pump asends the next piece. A piece is the
    stream's own dict, or {"__end__": True} / {"__error__": msg} synthesised
    by the pump — `_drive` sees control flow as data, never as exceptions.
    kind "tool": pump asends the call_tool outcome (+ "ms").
    kind "terminal": pump queues `event` (guarded to exactly one) and stops.
    """

    kind: str
    messages: list[dict[str, Any]] = field(default_factory=list)
    tools: list[dict[str, Any]] | None = None
    call: _Pending | None = None
    event: tuple[str, dict[str, Any]] | None = None


def _norm_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _shares_fragment(a: str, b: str, n: int = MIN_FRAGMENT_CHARS) -> bool:
    """True iff a and b share some verbatim contiguous run of >= n chars.

    Equivalent to longest-common-substring >= n: such a run's first n chars
    are an n-window of the shorter string that occurs in the longer one.
    Windowing lets C-level ``in`` do the work instead of a Python DP table.
    """
    if len(a) < n or len(b) < n:
        return False
    short, long_ = (a, b) if len(a) <= len(b) else (b, a)
    return any(short[i : i + n] in long_ for i in range(len(short) - n + 1))


def _hit_rows(result: Any) -> list[dict[str, Any]]:
    """Coerce a search_documents tool result into a list of hit dicts."""
    payload = result
    if isinstance(payload, dict):
        for key in ("hits", "results", "documents"):
            if isinstance(payload.get(key), list):
                payload = payload[key]
                break
    if not isinstance(payload, list):
        return []
    return [h for h in payload if isinstance(h, dict)]


def _collect_citations(hits: list[dict[str, Any]], final_text: str) -> list[dict[str, Any]]:
    """Data of one citation per distinct hit quoted verbatim (>=60 chars) in the answer."""
    norm_final = _norm_ws(final_text)
    out: list[dict[str, Any]] = []
    if not norm_final:
        return out
    seen: set[str] = set()
    for hit in hits:
        chunk_id = str(hit.get("chunk_id") or "")
        text = str(hit.get("text") or "")
        if not chunk_id or not text or chunk_id in seen:
            continue
        seen.add(chunk_id)
        if not _shares_fragment(_norm_ws(text), norm_final):
            continue
        snippet = text if len(text) <= SNIPPET_CHARS else text[:SNIPPET_CHARS].rstrip() + "…"
        page = hit.get("page")
        out.append(
            {
                "doc_id": chunk_id.split(":", 1)[0],
                "source": str(hit.get("source") or ""),
                "page": page if isinstance(page, int) else None,
                "snippet": snippet,
            }
        )
    return out


def _decode_args(raw: Any) -> tuple[dict[str, Any], str | None]:
    """JSON-decode a tool call's arguments; never raises."""
    if raw is None or raw == "":
        return {}, None
    if isinstance(raw, dict):
        return raw, None
    try:
        decoded = json.loads(str(raw))
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        return {}, f"invalid tool arguments: could not decode JSON ({exc})"
    if isinstance(decoded, dict):
        return decoded, None
    return {}, f"invalid tool arguments: expected a JSON object, got {type(decoded).__name__}"


async def _drive(
    prompt: str,
    *,
    run_id: str,
    registry: ToolRegistry,
    history: list[dict] | None,
    emit,
) -> AsyncIterator[_Step]:
    """The conversation state machine; yields steps, receives results via asend."""
    settings = get_settings()
    try:  # tracing is best-effort; a broken SDK must not kill the run
        install_tracing()
    except Exception:
        pass
    set_current_run(run_id)
    try:
        try:
            db.create_run(run_id, {"prompt": prompt})
        except sqlite3.IntegrityError:
            pass  # run id already exists — replay its trace, don't crash
        except Exception:
            pass  # e.g. concurrent writers; the run row may already be there

        emit("status", {"message": f"Starting run for prompt: {prompt[:120]}"})

        messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_LINE}]
        for row in history or []:
            if isinstance(row, dict) and "role" in row:
                messages.append({"role": str(row["role"]), "content": row.get("content", "")})
        messages.append({"role": "user", "content": prompt})

        tools = [to_function_schema(t) for t in registry.list()] or None
        search_hits: list[dict[str, Any]] = []
        full_text = ""

        for turn in range(MAX_TURNS):
            turn_parts: list[str] = []
            done: dict[str, Any] | None = None
            reply: dict[str, Any] = yield _Step(kind="turn", messages=messages, tools=tools)
            stream_open = True
            while stream_open:
                if "__error__" in reply:
                    yield _Step(
                        kind="terminal",
                        event=("error", {"message": str(reply["__error__"]), "recoverable": False}),
                    )
                    return
                if "__end__" in reply:
                    stream_open = False
                elif "delta" in reply:
                    text = str(reply["delta"])
                    if text:
                        turn_parts.append(text)
                        full_text += text
                        emit("token", {"text": text})
                elif "done" in reply:
                    done = reply["done"] or {}
                reply = yield _Step(kind="chunk")

            turn_text = "".join(turn_parts)
            tool_calls = (done or {}).get("tool_calls") or []
            asst: dict[str, Any] = {"role": "assistant", "content": turn_text or None}
            if tool_calls:
                asst["tool_calls"] = tool_calls
            messages.append(asst)

            if not tool_calls:
                if not full_text.strip():
                    yield _Step(
                        kind="terminal",
                        event=(
                            "error",
                            {"message": "The model returned an empty answer.", "recoverable": True},
                        ),
                    )
                    return
                for data in _collect_citations(search_hits, full_text):
                    emit("citation", data)
                yield _Step(kind="terminal", event=("final", {"text": full_text, "payload": None}))
                return

            for i, call in enumerate(tool_calls):
                fn = call.get("function") or {}
                name = str(fn.get("name") or "")
                call_id = str(call.get("id") or f"call_{turn}_{i}_{name}")
                args, decode_error = _decode_args(fn.get("arguments"))
                emit("tool_call", {"name": name, "args": args, "call_id": call_id})

                pending = _Pending(name=name, args=args, call_id=call_id, decode_error=decode_error)
                outcome: dict[str, Any] = yield _Step(kind="tool", call=pending)
                ok = bool(outcome.get("ok"))
                result_data = outcome.get("result") if ok else outcome.get("error")
                emit(
                    "tool_result",
                    {
                        "name": name,
                        "call_id": call_id,
                        "ok": ok,
                        "result": result_data,
                        "ms": outcome.get("ms", 0.0),
                    },
                )
                if ok and name == CITATION_TOOL:
                    search_hits.extend(_hit_rows(result_data))
                payload = outcome.get("result") if ok else {"error": outcome.get("error")}
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call_id,
                        "content": json.dumps(payload, ensure_ascii=False, default=str),
                    }
                )

        # Turn cap reached without the model settling: answer with what we have.
        emit(
            "status",
            {
                "message": (
                    f"Reached the {MAX_TURNS}-turn model cap; finishing with the text produced so far."
                )
            },
        )
        for data in _collect_citations(search_hits, full_text):
            emit("citation", data)
        yield _Step(kind="terminal", event=("final", {"text": full_text, "payload": None}))
    finally:
        set_current_run(None)


async def run_agent(
    prompt: str,
    *,
    run_id: str,
    registry: ToolRegistry,
    history: list[dict] | None = None,
) -> AsyncIterator[Event]:
    """Stream a run's events; exactly one `final` or `error` terminates the run.

    Every event takes its `seq` from one per-run `SequenceCounter` and is
    written to `agent_trace` through `TraceWriter` before being yielded. The
    run row is closed with `db.finish_run` even if the consumer abandons this
    generator mid-stream.
    """
    counter = SequenceCounter()
    writer = TraceWriter(run_id)
    queue: list[Event] = []
    terminal_sent = False
    run_status = {"status": "error", "output": None, "error": "agent run aborted"}

    def emit(type_: str, data: dict[str, Any]) -> None:
        event = Event(type=type_, run_id=run_id, data=data, seq=counter.next())  # type: ignore[arg-type]
        writer.write(event)  # persisted before the consumer ever sees it
        queue.append(event)

    def terminal(type_: str, data: dict[str, Any]) -> None:
        nonlocal terminal_sent
        if terminal_sent:
            return  # the exactly-one-terminal rule wins over any late claim
        terminal_sent = True
        emit(type_, data)
        if type_ == "final":
            run_status.update(status="ok", output=str(data.get("text") or ""), error=None)
        else:
            run_status.update(
                status="error", output=None, error=str(data.get("message") or "agent run failed")
            )

    async def call_anext(aiter) -> dict[str, Any]:
        """Next stream piece as data, never as an exception."""
        try:
            return await aiter.__anext__()
        except StopAsyncIteration:
            return {"__end__": True}
        except llm.LLMUnavailable as exc:
            return {"__error__": str(exc)}
        except Exception as exc:  # mid-stream SDK/network faults -> readable error
            return {"__error__": f"LLM stream failed: {type(exc).__name__}: {exc}"}

    async def run_tool(step: _Step) -> dict[str, Any]:
        call = step.call
        assert call is not None
        if call.decode_error is not None:
            return {"ok": False, "error": call.decode_error, "ms": 0.0}
        t0 = time.perf_counter()
        outcome = await call_tool(registry, call.name, call.args)
        return {**outcome, "ms": round((time.perf_counter() - t0) * 1000.0, 1)}

    inner = _drive(prompt, run_id=run_id, registry=registry, history=history, emit=emit)
    stream_iter: Any = None
    try:
        try:
            step: _Step = await anext(inner)
            while True:
                if step.kind == "turn":
                    stream_iter = llm.stream(
                        step.messages,
                        tools=step.tools,
                        max_tokens=get_settings().llm_max_tokens,
                    )
                    if not hasattr(stream_iter, "__anext__"):
                        raise TypeError("llm.stream() did not return an async iterator")
                    reply: Any = await call_anext(stream_iter)
                elif step.kind == "chunk":
                    if stream_iter is None:
                        raise RuntimeError("chunk step without an open model stream")
                    reply = await call_anext(stream_iter)
                elif step.kind == "tool":
                    reply = await run_tool(step)
                else:  # terminal
                    assert step.event is not None
                    terminal(*step.event)
                    reply = None
                while queue:
                    event = queue.pop(0)
                    yield event
                    if event.type in ("final", "error"):
                        return
                try:
                    step = await inner.asend(reply)
                except StopAsyncIteration:
                    break  # _drive ended without a terminal; guarded below
        except GeneratorExit:
            if not terminal_sent:
                run_status.update(
                    status="error", output=None, error="client disconnected before completion"
                )
            raise
        except llm.LLMUnavailable as exc:
            terminal("error", {"message": str(exc), "recoverable": False})
        except Exception as exc:  # stray fault anywhere in the pump
            terminal(
                "error",
                {"message": f"Agent run failed: {type(exc).__name__}: {exc}", "recoverable": False},
            )
        if not terminal_sent:  # defensive: _drive must always end on a terminal step
            terminal("error", {"message": "Agent loop ended without a result.", "recoverable": False})
        while queue:
            event = queue.pop(0)
            yield event
            if event.type in ("final", "error"):
                return
    finally:
        if stream_iter is not None:
            try:
                await stream_iter.aclose()
            except Exception:
                pass
        try:
            await inner.aclose()
        except Exception:
            pass
        try:
            db.finish_run(
                run_id, run_status["status"], output=run_status["output"], error=run_status["error"]
            )
        except Exception:
            pass  # persistence trouble must never raise into the caller

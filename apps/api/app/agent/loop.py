"""Bounded model/tool conversation shared by the generic runner and the audit.

``_drive`` is the one conversation state machine. ``_pump`` executes its model
and registry steps; the generic runner persists events, while the audit hands
only nonterminal events to its API-owned event sink. No audit trace writer or
second model conversation is created here.
"""

from __future__ import annotations

import json
import re
import sqlite3
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import anyio

from .. import db
from ..config import get_settings
from ..events import Event, SequenceCounter
from . import llm
from .tools import ToolRegistry, call_tool, to_function_schema
from .trace import TraceWriter, install_tracing, set_current_run

MAX_TURNS = 6  # existing /run cap; the audit has its own bounded policy
CITATION_TOOL = "search_documents"
MIN_FRAGMENT_CHARS = 60
SNIPPET_CHARS = 200
SYSTEM_LINE = (
    "You are a helpful assistant. You may call the provided tools to find "
    "information; answer strictly from what the tools return and quote the "
    "exact passages you used. Always reply in the user's language."
)


@dataclass
class DriveStats:
    turns: int = 0
    tool_calls: int = 0
    invalid_calls: int = 0
    inspected: bool = False
    evidence_turn: int = 0
    finalized: bool = False
    stop_reason: str = ""
    error: str = ""


@dataclass(frozen=True)
class _Policy:
    system: str = SYSTEM_LINE
    max_turns: int = MAX_TURNS
    max_tool_calls: int | None = None
    max_seconds: float | None = None
    audit: bool = False


@dataclass
class _Pending:
    name: str
    args: dict[str, Any]
    call_id: str
    decode_error: str | None = None


@dataclass
class _Step:
    kind: str  # turn, chunk, tool or terminal
    messages: list[dict[str, Any]] = field(default_factory=list)
    tools: list[dict[str, Any]] | None = None
    call: _Pending | None = None
    event: tuple[str, dict[str, Any]] | None = None


def _norm_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _shares_fragment(a: str, b: str, n: int = MIN_FRAGMENT_CHARS) -> bool:
    if len(a) < n or len(b) < n:
        return False
    short, long_ = (a, b) if len(a) <= len(b) else (b, a)
    return any(short[i : i + n] in long_ for i in range(len(short) - n + 1))


def _hit_rows(result: Any) -> list[dict[str, Any]]:
    payload = result
    if isinstance(payload, dict):
        for key in ("hits", "results", "documents"):
            if isinstance(payload.get(key), list):
                payload = payload[key]
                break
    return [h for h in payload if isinstance(h, dict)] if isinstance(payload, list) else []


def _collect_citations(hits: list[dict[str, Any]], final_text: str) -> list[dict[str, Any]]:
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
        out.append({
            "doc_id": chunk_id.split(":", 1)[0],
            "source": str(hit.get("source") or ""),
            "page": page if isinstance(page, int) else None,
            "snippet": snippet,
        })
    return out


def _decode_args(raw: Any) -> tuple[dict[str, Any], str | None]:
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


def _audit_result(name: str, result: Any) -> Any:
    if isinstance(result, dict) and name in ("offer_candidates", "resolve_alignment", "propose_unit_change", "propose_risk", "verify_citations"):
        def bounded(value: Any) -> Any:
            if isinstance(value, str):
                return value[:1600]
            if isinstance(value, list):
                return [bounded(item) for item in value[:16]]
            if isinstance(value, dict):
                clipped = {key: bounded(item) for key, item in value.items()}
                omitted = {key: len(item) - (1600 if isinstance(item, str) else 16)
                           for key, item in value.items()
                           if isinstance(item, (str, list)) and len(item) > (1600 if isinstance(item, str) else 16)}
                if omitted:
                    clipped["omitted_by_field"] = omitted
                return clipped
            return value
        return bounded(result)
    # The complete Report travels in the API's final event, never through the
    # model transcript or its persisted intermediate tool_result.
    if name == "build_report" and isinstance(result, dict):
        warnings = result.get("warnings") or []
        return {
            "mode": result.get("mode"),
            "findings": len(result.get("findings") or []),
            "unit_changes": len(result.get("unit_changes") or []),
            "risks": len(result.get("risks") or []),
            "conclusion": len(result.get("conclusion") or []),
            "coverage": result.get("coverage"),
            "warnings": warnings[:8],
            "omitted_warnings": max(0, len(warnings) - 8),
            "validated": True,
        }
    return result


async def _drive(
    prompt: str,
    *,
    run_id: str,
    registry: ToolRegistry,
    history: list[dict] | None,
    emit,
    policy: _Policy,
    stats: DriveStats,
) -> AsyncIterator[_Step]:
    """Single conversation state machine, returning step outcomes via ``asend``."""
    if not policy.audit:
        try:
            install_tracing()
        except Exception:
            pass
        set_current_run(run_id)
        try:
            db.create_run(run_id, {"prompt": prompt})
        except sqlite3.IntegrityError:
            pass
        except Exception:
            pass
    try:
        if not policy.audit:
            emit("status", {"message": f"Starting run for prompt: {prompt[:120]}"})
        messages: list[dict[str, Any]] = [{"role": "system", "content": policy.system}]
        for row in history or []:
            if isinstance(row, dict) and "role" in row:
                messages.append({"role": str(row["role"]), "content": row.get("content", "")})
        messages.append({"role": "user", "content": prompt})
        tools = [to_function_schema(t) for t in registry.list()] or None
        search_hits: list[dict[str, Any]] = []
        full_text = ""
        deadline = time.monotonic() + policy.max_seconds if policy.max_seconds is not None else None

        for turn in range(policy.max_turns):
            if deadline is not None and time.monotonic() >= deadline:
                stats.stop_reason = "time_limit"
                break
            turn_parts: list[str] = []
            done: dict[str, Any] | None = None
            stats.turns += 1
            turn_messages = messages
            if policy.audit:
                remaining = max(0.0, deadline - time.monotonic()) if deadline is not None else None
                budget_note = (
                    f"\nHost budget: turn {stats.turns}/{policy.max_turns}; "
                    f"tool calls used {stats.tool_calls}/{policy.max_tool_calls}; "
                    f"seconds remaining {remaining:.1f}. "
                    "Reserve a call to build_report before the budget ends. On the last turn, "
                    "finalize the validated state rather than starting another investigation. "
                    "Keep uncertain and uninspected findings unchanged; never invent a resolution to finish."
                )
                turn_messages = [{**messages[0], "content": str(messages[0]["content"]) + budget_note}, *messages[1:]]
            reply: dict[str, Any] = yield _Step(kind="turn", messages=turn_messages, tools=tools)
            while True:
                if "__error__" in reply:
                    stats.stop_reason = str(reply.get("__reason__") or "provider_error")
                    yield _Step(kind="terminal", event=("error", {"message": str(reply["__error__"]), "recoverable": False}))
                    return
                if "__end__" in reply:
                    break
                if "delta" in reply:
                    text = str(reply["delta"])
                    if text:
                        turn_parts.append(text)
                        if not policy.audit:
                            full_text += text
                            emit("token", {"text": text})
                elif "done" in reply:
                    done = reply["done"] or {}
                reply = yield _Step(kind="chunk")
            if deadline is not None and time.monotonic() >= deadline:
                stats.stop_reason = "time_limit"
                break
            turn_text = "".join(turn_parts)
            tool_calls = (done or {}).get("tool_calls") or []
            if not isinstance(tool_calls, list):
                stats.stop_reason = "invalid_model_output"
                yield _Step(kind="terminal", event=("error", {"message": "Model returned invalid tool calls.", "recoverable": False}))
                return
            asst: dict[str, Any] = {"role": "assistant", "content": turn_text or None}
            if tool_calls:
                asst["tool_calls"] = tool_calls
            messages.append(asst)

            if not tool_calls:
                if policy.audit:
                    stats.stop_reason = "finalized" if stats.finalized else "text_only_without_report"
                    yield _Step(kind="terminal", event=("final", {"text": "", "payload": None}))
                    return
                if not full_text.strip():
                    stats.stop_reason = "empty_answer"
                    yield _Step(kind="terminal", event=("error", {"message": "The model returned an empty answer.", "recoverable": True}))
                    return
                for data in _collect_citations(search_hits, full_text):
                    emit("citation", data)
                stats.stop_reason = "finished"
                yield _Step(kind="terminal", event=("final", {"text": full_text, "payload": None}))
                return

            for i, call in enumerate(tool_calls):
                if deadline is not None and time.monotonic() >= deadline:
                    stats.stop_reason = "time_limit"
                    break
                if policy.max_tool_calls is not None and stats.tool_calls >= policy.max_tool_calls:
                    stats.stop_reason = "tool_call_limit"
                    break
                if not isinstance(call, dict):
                    stats.invalid_calls += 1
                    stats.stop_reason = "invalid_model_output"
                    break
                fn = call.get("function") or {}
                if not isinstance(fn, dict):
                    fn = {}
                name = str(fn.get("name") or "")
                call_id = str(call.get("id") or f"call_{turn}_{i}_{name}")
                args, decode_error = _decode_args(fn.get("arguments"))
                stats.tool_calls += 1
                emit("tool_call", {"name": name, "args": args, "call_id": call_id})
                outcome: dict[str, Any] = yield _Step(
                    kind="tool", call=_Pending(name=name, args=args, call_id=call_id, decode_error=decode_error)
                )
                if deadline is not None and time.monotonic() >= deadline:
                    outcome = {"ok": False, "error": "Audit tool exceeded the investigation deadline."}
                    stats.stop_reason = "time_limit"
                ok = bool(outcome.get("ok"))
                result = outcome.get("result")
                rejected = (policy.audit and ok and name in (
                    "offer_candidates", "resolve_alignment", "propose_unit_change", "propose_risk"
                ) and isinstance(result, dict) and result.get("accepted") is False
                    and not str(result.get("reason", "")).startswith("abstained"))
                if not ok or rejected:
                    stats.invalid_calls += 1
                result_data = _audit_result(name, outcome.get("result")) if ok and policy.audit else outcome.get("result") if ok else outcome.get("error")
                emit("tool_result", {
                    "name": name, "call_id": call_id, "ok": ok,
                    "result": result_data, "ms": outcome.get("ms", 0.0),
                })
                if not policy.audit and ok and name == CITATION_TOOL:
                    search_hits.extend(_hit_rows(outcome.get("result")))
                if policy.audit and ok:
                    evidence_keys = {"inspect_findings": "findings", "read_clauses": "clauses", "inspect_units": "units"}
                    evidence_key = evidence_keys.get(name)
                    if evidence_key and isinstance(result, dict) and result.get(evidence_key):
                        stats.inspected = True
                        if not stats.evidence_turn:
                            stats.evidence_turn = stats.turns
                    if name == "build_report" and stats.evidence_turn and stats.evidence_turn < stats.turns:
                        stats.finalized = True
                    elif name in ("offer_candidates", "resolve_alignment", "propose_unit_change", "propose_risk"):
                        if isinstance(outcome.get("result"), dict) and outcome["result"].get("accepted"):
                            stats.finalized = False
                payload = result_data if ok else {"error": outcome.get("error")}
                messages.append({
                    "role": "tool", "tool_call_id": call_id,
                    "content": json.dumps(payload, ensure_ascii=False, default=str),
                })
            if stats.stop_reason:
                break
            if policy.audit and stats.finalized:
                stats.stop_reason = "finalized"
                yield _Step(kind="terminal", event=("final", {"text": "", "payload": None}))
                return

        if not stats.stop_reason:
            stats.stop_reason = "turn_limit"
        if policy.audit:
            emit("status", {"message": f"Audit investigation stopped: {stats.stop_reason}."})
            yield _Step(kind="terminal", event=("final", {"text": "", "payload": None}))
        else:
            emit("status", {"message": f"Reached the {MAX_TURNS}-turn model cap; finishing with the text produced so far."})
            for data in _collect_citations(search_hits, full_text):
                emit("citation", data)
            yield _Step(kind="terminal", event=("final", {"text": full_text, "payload": None}))
    finally:
        if not policy.audit:
            set_current_run(None)


async def _pump(
    prompt: str, *, run_id: str, registry: ToolRegistry,
    history: list[dict] | None, policy: _Policy, stats: DriveStats,
) -> AsyncIterator[tuple[str, dict[str, Any]]]:
    """One step executor for both callers; no event sequencing or persistence."""
    queue: list[tuple[str, dict[str, Any]]] = []
    def emit(type_: str, data: dict[str, Any]) -> None:
        queue.append((type_, data))

    async def next_piece(iterator, turn_deadline: float | None, deadline: float | None) -> dict[str, Any]:
        try:
            if turn_deadline is None:
                return await iterator.__anext__()
            remaining = turn_deadline - time.monotonic()
            if remaining <= 0:
                return {"__error__": "Model call exceeded the audit or per-call time limit.",
                        "__reason__": "time_limit" if deadline is not None and time.monotonic() >= deadline else "provider_error"}
            with anyio.fail_after(remaining):
                return await iterator.__anext__()
        except StopAsyncIteration:
            return {"__end__": True}
        except TimeoutError:
            return {"__error__": "Model call exceeded the audit or per-call time limit.",
                    "__reason__": "time_limit" if deadline is not None and time.monotonic() >= deadline else "provider_error"}
        except llm.LLMUnavailable as exc:
            return {"__error__": str(exc)}
        except Exception as exc:
            return {"__error__": f"LLM stream failed: {type(exc).__name__}: {exc}"}

    async def run_tool(step: _Step, deadline: float | None) -> dict[str, Any]:
        call = step.call
        assert call is not None
        if call.decode_error is not None:
            return {"ok": False, "error": call.decode_error, "ms": 0.0}
        if policy.audit and call.name == "build_report" and (
            not stats.evidence_turn or stats.evidence_turn >= stats.turns
        ):
            return {"ok": False, "error": "Read evidence first, then finalize in a subsequent model turn after consuming its result.", "ms": 0.0}
        t0 = time.perf_counter()
        if deadline is not None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return {"ok": False, "error": "Audit investigation exceeded its time limit.", "ms": 0.0}
            try:
                with anyio.fail_after(remaining):
                    outcome = await call_tool(registry, call.name, call.args)
            except TimeoutError:
                outcome = {"ok": False, "error": "Audit tool exceeded the investigation time limit."}
        else:
            outcome = await call_tool(registry, call.name, call.args)
        return {**outcome, "ms": round((time.perf_counter() - t0) * 1000.0, 1)}

    inner = _drive(prompt, run_id=run_id, registry=registry, history=history, emit=emit, policy=policy, stats=stats)
    stream_iter: Any = None
    terminal = False
    turn_deadline: float | None = None
    deadline = time.monotonic() + policy.max_seconds if policy.max_seconds is not None else None
    try:
        try:
            step = await anext(inner)
            while True:
                if step.kind == "turn":
                    if stream_iter is not None:
                        await stream_iter.aclose()
                    token_budget = get_settings().llm_max_tokens
                    if policy.audit:
                        token_budget = max(token_budget, 2048)  # existing audit reasoning-model floor
                    stream_iter = llm.stream(step.messages, tools=step.tools, max_tokens=token_budget)
                    if not hasattr(stream_iter, "__anext__"):
                        raise TypeError("llm.stream() did not return an async iterator")
                    turn_deadline = min(time.monotonic() + get_settings().llm_timeout_s, deadline) if policy.audit and deadline is not None else None
                    reply: Any = await next_piece(stream_iter, turn_deadline, deadline)
                elif step.kind == "chunk":
                    if stream_iter is None:
                        raise RuntimeError("chunk step without an open model stream")
                    reply = await next_piece(stream_iter, turn_deadline, deadline)
                elif step.kind == "tool":
                    reply = await run_tool(step, deadline)
                else:
                    assert step.event is not None
                    queue.append(step.event)
                    reply = None
                while queue:
                    event = queue.pop(0)
                    if event[0] in ("final", "error"):
                        terminal = True
                    yield event
                    if terminal:
                        return
                try:
                    step = await inner.asend(reply)
                except StopAsyncIteration:
                    break
        except llm.LLMUnavailable as exc:
            stats.stop_reason = "provider_error"
            queue.append(("error", {"message": str(exc), "recoverable": False}))
        except Exception as exc:
            stats.stop_reason = "agent_error"
            queue.append(("error", {"message": f"Agent run failed: {type(exc).__name__}: {exc}", "recoverable": False}))
        if not terminal and not queue:
            stats.stop_reason = stats.stop_reason or "agent_error"
            queue.append(("error", {"message": "Agent loop ended without a result.", "recoverable": False}))
        while queue:
            event = queue.pop(0)
            yield event
            if event[0] in ("final", "error"):
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


async def drive_audit(
    prompt: str, *, run_id: str, registry: ToolRegistry, system: str,
    emit, max_turns: int = 12, max_tool_calls: int = 32,
    max_seconds: float = 180.0,
) -> DriveStats:
    """Use the shared state machine without DB, trace, citations or audit terminal events."""
    stats = DriveStats()
    policy = _Policy(system=system, max_turns=max_turns, max_tool_calls=max_tool_calls,
                     max_seconds=max_seconds, audit=True)
    async for type_, data in _pump(prompt, run_id=run_id, registry=registry,
                                   history=None, policy=policy, stats=stats):
        if type_ in ("final", "error"):
            if type_ == "error":
                stats.stop_reason = stats.stop_reason or "agent_error"
                stats.error = data.get("message", "Agent failed.")
            continue  # the audit API is the sole owner of its terminal event
        if emit is not None:
            await emit(type_, data)
    return stats


async def run_agent(
    prompt: str, *, run_id: str, registry: ToolRegistry,
    history: list[dict] | None = None,
) -> AsyncIterator[Event]:
    """Generic /run SSE stream, persisted before delivery with exactly one terminal."""
    counter = SequenceCounter()
    writer = TraceWriter(run_id)
    stats = DriveStats()
    terminal_sent = False
    run_status = {"status": "error", "output": None, "error": "agent run aborted"}
    try:
        async for type_, data in _pump(prompt, run_id=run_id, registry=registry,
                                       history=history, policy=_Policy(), stats=stats):
            if terminal_sent:
                continue
            event = Event(type=type_, run_id=run_id, data=data, seq=counter.next())  # type: ignore[arg-type]
            writer.write(event)
            if type_ in ("final", "error"):
                terminal_sent = True
                if type_ == "final":
                    run_status.update(status="ok", output=str(data.get("text") or ""), error=None)
                else:
                    run_status.update(status="error", output=None, error=str(data.get("message") or "agent run failed"))
            yield event
            if terminal_sent:
                return
    except GeneratorExit:
        if not terminal_sent:
            run_status.update(status="error", output=None, error="client disconnected before completion")
        raise
    except Exception as exc:
        if not terminal_sent:
            message = f"Agent run failed: {type(exc).__name__}: {exc}"
            run_status.update(status="error", output=None, error=message)
            event = Event(type="error", run_id=run_id,
                          data={"message": message, "recoverable": False}, seq=counter.next())
            try:
                writer.write(event)
            except Exception:
                pass
            yield event
    finally:
        try:
            db.finish_run(run_id, run_status["status"], output=run_status["output"], error=run_status["error"])
        except Exception:
            pass

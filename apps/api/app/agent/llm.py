"""Thin, hardened wrapper around the OpenAI-compatible chat API.

Every call into the model goes through here. The wrapper exists because the
https://xllm.sek.su/v1 gateway (and reasoning models behind it) violate a few
"obvious" assumptions of the OpenAI SDK shapes:

1. ``message.content`` can be ``None`` on reasoning models and on tool-call
   replies. This module normalises content to ``""``; callers never dereference
   ``None``.
2. A reply can finish with ``finish_reason == "length"`` and empty content:
   the whole token budget went to hidden reasoning tokens. ``complete()``
   retries once with the budget doubled (capped at ``RETRY_MAX_TOKENS_CAP``)
   and then raises a ``RuntimeError`` naming the budget it exhausted.

Connection/timeout/API failures are translated into ``LLMUnavailable`` with a
readable message so the agent loop has one exception type to handle for
"the model is not reachable right now".
"""

from __future__ import annotations

import asyncio
import weakref
from collections.abc import AsyncIterator, Iterable, Mapping, Sequence
from typing import Any

from openai import (
    APIConnectionError,
    APITimeoutError,
    AsyncOpenAI,
    OpenAIError,
    RateLimitError,
)

from ..config import get_settings

RETRY_MAX_TOKENS_CAP = 4096

_client: AsyncOpenAI | None = None
_client_key: tuple[str, str, float] | None = None
# The loop the cached client's connection pool was created on. An AsyncOpenAI
# client is bound to that loop; reusing it from a different (or a second
# asyncio.run()) loop raises "Event loop is closed". Keep a weakref so a dead
# loop never stays resurrectable just because we hold the client.
_client_loop: weakref.ReferenceType[asyncio.AbstractEventLoop] | None = None


class LLMUnavailable(RuntimeError):
    """The LLM cannot be reached or is not configured (no API key)."""


def _normalize_messages(messages: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Copy messages, normalising a ``None`` content to "" (guard 1 also on the way in)."""
    out: list[dict[str, Any]] = []
    for msg in messages:
        m = dict(msg)
        if m.get("content") is None:
            m["content"] = ""
        out.append(m)
    return out


def get_client() -> AsyncOpenAI:
    """Return a cached AsyncOpenAI built from settings; raise LLMUnavailable without a key."""
    global _client, _client_key, _client_loop
    settings = get_settings()
    if not settings.llm_configured:
        raise LLMUnavailable(
            "LLM is not configured: LLM_API_KEY is empty. "
            "Set it in .env (or the environment) to enable model calls; "
            "the app otherwise runs in degraded mode."
        )
    key = (settings.llm_base_url, settings.llm_api_key, settings.llm_timeout_s)
    try:
        loop: asyncio.AbstractEventLoop | None = asyncio.get_running_loop()
    except RuntimeError:  # called outside a loop: cache is still fine to reuse later
        loop = None
    live_loop = _client_loop() if _client_loop is not None else None
    if _client is None or _client_key != key or (loop is not None and live_loop is not loop):
        _client = AsyncOpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            timeout=settings.llm_timeout_s,
        )
        _client_key = key
        _client_loop = weakref.ref(loop) if loop is not None else None
    return _client


def _wrap_openai_error(exc: OpenAIError, *, streaming: bool = False) -> LLMUnavailable:
    stage = "streaming call" if streaming else "chat completion"
    if isinstance(exc, APITimeoutError):
        return LLMUnavailable(
            f"LLM {stage} timed out (LLM_TIMEOUT_S={get_settings().llm_timeout_s:g}s): {exc}",
        )
    if isinstance(exc, RateLimitError):
        return LLMUnavailable(f"LLM rate limited on {stage}: {exc}")
    if isinstance(exc, APIConnectionError):
        return LLMUnavailable(
            f"Cannot reach LLM gateway at {get_settings().llm_base_url} on {stage}: {exc}",
        )
    return LLMUnavailable(f"LLM API error on {stage}: {exc}")


def _tool_calls_plain(message: Any) -> list[dict[str, Any]]:
    """Normalise SDK tool_calls into plain JSON-safe dicts (arguments stay a string)."""
    out: list[dict[str, Any]] = []
    for tc in getattr(message, "tool_calls", None) or []:
        fn = getattr(tc, "function", None)
        out.append(
            {
                "id": getattr(tc, "id", None) or "",
                "type": getattr(tc, "type", None) or "function",
                "function": {
                    "name": getattr(fn, "name", None) or "",
                    "arguments": getattr(fn, "arguments", None) or "",
                },
            }
        )
    return out


def _usage_dict(usage: Any) -> dict[str, Any]:
    if usage is None:
        return {}
    try:
        return usage.model_dump()
    except (AttributeError, TypeError):  # pragma: no cover - defensive
        return dict(usage) if isinstance(usage, Mapping) else {}


async def _create(
    messages: list[dict[str, Any]],
    *,
    tools: Iterable[Mapping[str, Any]] | None,
    max_tokens: int,
) -> Any:
    client = get_client()
    settings = get_settings()
    kwargs: dict[str, Any] = {
        "model": settings.llm_model,
        "messages": messages,
        "max_tokens": max_tokens,
    }
    if tools:
        kwargs["tools"] = list(tools)
    try:
        return await client.chat.completions.create(**kwargs)
    except OpenAIError as exc:
        raise _wrap_openai_error(exc) from exc


async def complete(
    messages: Sequence[Mapping[str, Any]],
    *,
    tools: Iterable[Mapping[str, Any]] | None = None,
    max_tokens: int | None = None,
) -> dict[str, Any]:
    """One non-streaming chat completion.

    Returns ``{"content": str, "tool_calls": list, "finish_reason": str, "usage": dict}``;
    ``content`` is never ``None``.
    """
    settings = get_settings()
    msgs = _normalize_messages(messages)
    budget = max_tokens if max_tokens is not None else settings.llm_max_tokens

    resp = await _create(msgs, tools=tools, max_tokens=budget)
    choice = resp.choices[0] if resp.choices else None
    content = (getattr(choice, "message", None) and choice.message.content) or "" if choice else ""
    finish = (getattr(choice, "finish_reason", None) or "") if choice else ""

    # Guard 2: budget swallowed by reasoning tokens -> retry once, doubled, capped.
    if finish == "length" and not content.strip():
        if budget >= RETRY_MAX_TOKENS_CAP:
            raise RuntimeError(
                "LLM returned empty content with finish_reason='length' at max_tokens="
                f"{budget}, already at the {RETRY_MAX_TOKENS_CAP}-token retry cap: the "
                "whole budget went to reasoning tokens and a retry cannot help."
            )
        doubled = min(budget * 2, RETRY_MAX_TOKENS_CAP)
        resp = await _create(msgs, tools=tools, max_tokens=doubled)
        choice = resp.choices[0] if resp.choices else None
        content = (
            (getattr(choice, "message", None) and choice.message.content) or ""
        ) if choice else ""
        finish = (getattr(choice, "finish_reason", None) or "") if choice else ""
        if finish == "length" and not content.strip():
            raise RuntimeError(
                "LLM produced no answerable content within the token budget: the reply "
                f"hit finish_reason='length' with empty content at max_tokens={doubled} "
                f"(doubled once from {budget}, cap {RETRY_MAX_TOKENS_CAP}). Most likely "
                "all tokens went to reasoning. Increase LLM_MAX_TOKENS or the max_tokens "
                "argument."
            )

    return {
        "content": content or "",
        "tool_calls": _tool_calls_plain(choice.message) if choice and choice.message else [],
        "finish_reason": finish,
        "usage": _usage_dict(getattr(resp, "usage", None)),
    }


async def stream(
    messages: Sequence[Mapping[str, Any]],
    *,
    tools: Iterable[Mapping[str, Any]] | None = None,
    max_tokens: int | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Streaming chat completion.

    Yields ``{"delta": str}`` per content piece, ``{"tool_call": {...}}`` per
    tool-call fragment (``{index, id, name, arguments_delta, done}``), then
    exactly one final ``{"done": {"finish_reason", "tool_calls", "usage"}}``.
    """
    settings = get_settings()
    msgs = _normalize_messages(messages)
    budget = max_tokens if max_tokens is not None else settings.llm_max_tokens
    client = get_client()
    kwargs: dict[str, Any] = {
        "model": settings.llm_model,
        "messages": msgs,
        "max_tokens": budget,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    if tools:
        kwargs["tools"] = list(tools)

    try:
        resp_stream = await client.chat.completions.create(**kwargs)
    except OpenAIError as exc:
        raise _wrap_openai_error(exc, streaming=True) from exc

    finish_reason = ""
    usage: dict[str, Any] = {}
    # Accumulate indexed tool-call fragments so the caller gets complete calls in `done`.
    calls: dict[int, dict[str, str]] = {}
    content_seen = False

    try:
        async for chunk in resp_stream:
            if getattr(chunk, "usage", None):
                usage = _usage_dict(chunk.usage)
            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            delta = getattr(choice, "delta", None)
            if delta is not None:
                piece = getattr(delta, "content", None)
                if piece:  # never None-safe-by-accident: guard 1
                    content_seen = True
                    yield {"delta": piece}
                for frag in getattr(delta, "tool_calls", None) or []:
                    idx = getattr(frag, "index", None)
                    if idx is None:
                        idx = len(calls)
                    slot = calls.setdefault(idx, {"id": "", "name": "", "arguments": ""})
                    if getattr(frag, "id", None):
                        slot["id"] = frag.id
                    fn = getattr(frag, "function", None)
                    if fn is not None:
                        if getattr(fn, "name", None):
                            slot["name"] = fn.name
                        arg_delta = getattr(fn, "arguments", None) or ""
                    else:
                        arg_delta = ""
                    slot["arguments"] += arg_delta
                    yield {
                        "tool_call": {
                            "index": idx,
                            "id": slot["id"],
                            "name": slot["name"],
                            "arguments_delta": arg_delta,
                            "done": False,
                        }
                    }
            if getattr(choice, "finish_reason", None):
                finish_reason = choice.finish_reason
    except OpenAIError as exc:
        raise _wrap_openai_error(exc, streaming=True) from exc
    finally:
        try:
            await resp_stream.close()
        except Exception:  # pragma: no cover - best-effort cleanup
            pass

    tool_calls = [
        {
            "id": slot["id"],
            "type": "function",
            "function": {"name": slot["name"], "arguments": slot["arguments"]},
        }
        for slot in (calls[i] for i in sorted(calls))
    ]
    # Guard 2 has no room to retry mid-stream (deltas already delivered): surface it readably.
    if finish_reason == "length" and not content_seen and not tool_calls:
        raise RuntimeError(
            "LLM stream ended with finish_reason='length' and no content: the entire "
            f"max_tokens budget ({budget}) was consumed by reasoning. Increase max_tokens "
            f"or LLM_MAX_TOKENS (complete() auto-doubles up to {RETRY_MAX_TOKENS_CAP}; "
            "stream() cannot retry after deltas were sent)."
        )

    yield {
        "done": {
            "finish_reason": finish_reason,
            "tool_calls": tool_calls,
            "usage": usage,
        }
    }

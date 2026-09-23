"""Optional LLM adjudication of ambiguous findings and conclusion drafting.

A bounded, two-phase pass over a finished deterministic :class:`Report`, not an
agent loop:

1. Unresolved findings are sent to the model in small batches with their
   candidate clause texts. Each proposed decision goes through the run-scoped
   ``resolve_alignment`` tool, which keeps the finding unresolved unless the
   decision stays inside the offered candidates.
2. The model drafts conclusion items over the resulting findings; the
   ``build_report`` tool drops every item that mentions an unverified finding
   ID, clause or citation.

Every model call goes through ``llm.complete`` under the configured
``LLM_TIMEOUT_S``. A missing key, timeout, malformed reply or model error
returns the original deterministic report with one added warning; the
comparison is never gated on the model.
"""

from __future__ import annotations

import inspect
import json
import re
import time
from collections.abc import Awaitable, Callable
from typing import Any

import anyio
from pydantic import ValidationError

from ..audit import ConclusionItem, Finding, Report
from ..config import get_settings
from . import llm
from .audit_tools import STATUSES, AuditContext, create_audit_registry
from .tools import ToolRegistry, call_tool

__all__ = ["adjudicate_report"]

EventSink = Callable[[str, dict[str, Any]], Awaitable[None] | None]

MAX_ADJUDICATED = 24  # ambiguous findings sent to the model per run
BATCH_SIZE = 8
MAX_CONCLUSION_FINDINGS = 60
CLAUSE_CHARS = 700
REASON_CHARS = 240
QUOTE_CHARS = 200
MIN_REPLY_TOKENS = 2048
# Review-worthy findings first when the conclusion prompt must be truncated.
_CONCLUSION_ORDER = {"missing": 0, "duplicate": 1, "unresolved": 2, "added": 3, "moved": 4, "changed": 5, "unchanged": 6}

_STATUS_GUIDE = (
    "unchanged = same text and context; moved = preserved function with changed location or owner unit; "
    "changed = supported match with content changes; added = after clause with no supported predecessor; "
    "missing = before clause with no supported successor in the after set (not proven loss); "
    "duplicate = potentially overlapping responsibilities, not repeated wording alone; "
    "unresolved = the evidence does not decide."
)

ADJUDICATION_SYSTEM = (
    "You review ambiguous alignments between two editions of an organisational regulation. "
    "For each finding choose a status and the subset of its OFFERED candidate refs that support it. "
    "Never name a ref that was not offered for that finding. Statuses: " + _STATUS_GUIDE + " "
    "If the texts do not clearly decide, answer unresolved and keep every offered ref. "
    "Write each reason in the language of the clause texts, citing what in the texts decides it. "
    'Reply with one JSON object only: {"decisions": [{"finding_id": str, "before": [{"doc": str, '
    '"clause_id": str}], "after": [{"doc": str, "clause_id": str}], "status": str, "reason": str}]}'
)

CONCLUSION_SYSTEM = (
    "You write the conclusion of an audit comparing two editions of an organisational regulation, "
    "for an internal auditor. Use only the findings supplied. Each conclusion item states one point "
    "and lists the IDs of the findings it relies on. Mention only finding IDs and clause numbers "
    "that belong to those findings; do not invent sources, units or numbers. 'missing' means no "
    "supported successor was found, not proven loss; 'duplicate' means potential overlap; both need "
    "review. Write in the language of the documents. Citations are optional; if given, copy them "
    "exactly from the listed findings. "
    'Reply with one JSON object only: {"conclusion": [{"text": str, "finding_ids": [str], '
    '"citations": [{"doc": str, "clause_id": str, "quote": str}]}]}'
)


class _MalformedReply(ValueError):
    """The model's reply is not the JSON shape the prompt asked for."""


async def adjudicate_report(report: Report, *, emit: EventSink | None = None) -> Report:
    """Return an LLM-assisted report, or `report` plus one warning when the model cannot help.

    Never raises for model trouble (missing key, timeout, malformed output, API
    error); cancellation still propagates.
    """
    if not get_settings().llm_configured:
        return _with_warning(
            report,
            "LLM adjudication skipped: LLM_API_KEY is not set; the deterministic report is returned.",
        )
    try:
        return await _adjudicate(report, emit)
    except TimeoutError:
        reason = f"the model did not answer within LLM_TIMEOUT_S={get_settings().llm_timeout_s:g}s"
    except _MalformedReply as exc:
        reason = f"malformed model output ({exc})"
    except Exception as exc:  # noqa: BLE001 - model trouble must never fail the audit
        reason = f"{type(exc).__name__}: {exc}"
    return _with_warning(
        report, f"LLM adjudication failed: {reason}; the deterministic report is returned."
    )


def _with_warning(report: Report, warning: str) -> Report:
    return report.model_copy(update={"warnings": [*report.warnings, warning]})


async def _adjudicate(report: Report, emit: EventSink | None) -> Report:
    ctx = AuditContext.from_report(report)
    registry = create_audit_registry(ctx)
    calls = _Calls(registry, emit)

    ambiguous = [f for f in ctx.findings.values() if f.status == "unresolved"]
    selected = ambiguous[:MAX_ADJUDICATED]
    if len(ambiguous) > len(selected):
        ctx.warnings.append(
            f"LLM adjudication covered {len(selected)} of {len(ambiguous)} unresolved findings; "
            "the rest stay unresolved for human review."
        )
    batches = [selected[i : i + BATCH_SIZE] for i in range(0, len(selected), BATCH_SIZE)]
    for n, batch in enumerate(batches, start=1):
        await _emit(emit, "status", {"message": f"LLM adjudicating ambiguous findings, batch {n}/{len(batches)}"})
        reply = await _ask(ADJUDICATION_SYSTEM, _adjudication_prompt(ctx, batch))
        decisions = reply.get("decisions")
        if not isinstance(decisions, list):
            raise _MalformedReply("'decisions' is not a list")
        await _apply_decisions(ctx, calls, batch, decisions)

    await _emit(emit, "status", {"message": "LLM drafting the conclusion"})
    reply = await _ask(CONCLUSION_SYSTEM, _conclusion_prompt(ctx))
    items = reply.get("conclusion")
    if not isinstance(items, list):
        raise _MalformedReply("'conclusion' is not a list")
    proposed: list[dict[str, Any]] = []
    for n, item in enumerate(items, start=1):
        candidate = {
            "text": item.get("text"),
            "finding_ids": item.get("finding_ids") or [],
            "citations": item.get("citations") or [],
        } if isinstance(item, dict) else item
        try:
            ConclusionItem.model_validate(candidate)
        except ValidationError as exc:
            ctx.warnings.append(f"Proposed conclusion item {n} dropped: malformed ({exc.error_count()} errors).")
            continue
        proposed.append(candidate)
    if not proposed:
        ctx.warnings.append("The model proposed no usable conclusion item; the deterministic conclusion is used.")

    outcome = await calls.call(
        "build_report", {"finding_ids": list(ctx.findings), "conclusion": proposed or None}
    )
    if not outcome["ok"] or ctx.last_report is None:
        raise RuntimeError(f"build_report failed: {outcome.get('error')}")
    return ctx.last_report


async def _apply_decisions(
    ctx: AuditContext, calls: _Calls, batch: list[Finding], decisions: list[Any]
) -> None:
    pending = {f.id for f in batch}
    for decision in decisions:
        if not isinstance(decision, dict):
            ctx.warnings.append("LLM decision ignored: not an object.")
            continue
        fid = decision.get("finding_id")
        if fid not in pending:
            ctx.warnings.append(f"LLM decision ignored: finding {fid!r} was not offered in this batch or repeats.")
            continue
        pending.discard(fid)
        args = {k: decision.get(k) for k in ("finding_id", "before", "after", "status", "reason")}
        outcome = await calls.call("resolve_alignment", args)
        if not outcome["ok"]:
            ctx.warnings.append(f"LLM decision for finding {fid} rejected: {outcome['error']}")


class _Calls:
    """Runs registry tools and mirrors them as tool_call/tool_result events."""

    def __init__(self, registry: ToolRegistry, emit: EventSink | None) -> None:
        self._registry = registry
        self._emit = emit
        self._n = 0

    async def call(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        self._n += 1
        call_id = f"audit-{self._n}"
        await _emit(self._emit, "tool_call", {"name": name, "args": args, "call_id": call_id})
        t0 = time.perf_counter()
        outcome = await call_tool(self._registry, name, args)
        ms = round((time.perf_counter() - t0) * 1000.0, 1)
        result = outcome.get("result") if outcome["ok"] else outcome.get("error")
        if name == "build_report" and outcome["ok"]:
            # The whole report travels in the final event; keep the trace row small.
            result = {
                "mode": result["mode"],
                "findings": len(result["findings"]),
                "conclusion": len(result["conclusion"]),
                "warnings": result["warnings"],
            }
        await _emit(
            self._emit,
            "tool_result",
            {"name": name, "call_id": call_id, "ok": outcome["ok"], "result": result, "ms": ms},
        )
        return outcome


async def _emit(sink: EventSink | None, type_: str, data: dict[str, Any]) -> None:
    if sink is None:
        return
    maybe = sink(type_, data)
    if inspect.isawaitable(maybe):
        await maybe


async def _ask(system: str, user: str) -> dict[str, Any]:
    settings = get_settings()
    budget = min(max(settings.llm_max_tokens, MIN_REPLY_TOKENS), llm.RETRY_MAX_TOKENS_CAP)
    with anyio.fail_after(settings.llm_timeout_s):
        reply = await llm.complete(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            max_tokens=budget,
        )
    return _json_object(reply["content"])


def _json_object(text: str) -> dict[str, Any]:
    body = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", body, re.S)
    if fenced:
        body = fenced.group(1).strip()
    try:
        value = json.loads(body)
    except json.JSONDecodeError:
        start, end = body.find("{"), body.rfind("}")
        if start < 0 or end <= start:
            raise _MalformedReply("reply contains no JSON object") from None
        try:
            value = json.loads(body[start : end + 1])
        except json.JSONDecodeError as exc:
            raise _MalformedReply(f"invalid JSON: {exc}") from None
    if not isinstance(value, dict):
        raise _MalformedReply(f"expected a JSON object, got {type(value).__name__}")
    return value


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit].rstrip() + " …"


def _adjudication_prompt(ctx: AuditContext, batch: list[Finding]) -> str:
    clauses = {(c.doc, c.clause_id): c for c in ctx.clauses}
    units = {(u.doc, u.unit_id): u.name for u in ctx.units}

    def candidate(ref) -> dict[str, Any]:
        clause = clauses.get((ref.doc, ref.clause_id))
        if clause is None:
            return {"doc": ref.doc, "clause_id": ref.clause_id, "text": None}
        return {
            "doc": ref.doc,
            "clause_id": ref.clause_id,
            "units": [units.get((ref.doc, uid), uid) for uid in clause.unit_ids],
            "text": _clip(clause.text, CLAUSE_CHARS),
        }

    items = [
        {
            "finding_id": f.id,
            "deterministic_reason": _clip(f.reason, REASON_CHARS),
            "offered_before": [candidate(r) for r in f.before],
            "offered_after": [candidate(r) for r in f.after],
        }
        for f in batch
    ]
    return (
        f"Allowed statuses: {', '.join(STATUSES)}.\n"
        "Decide each finding below; omit none.\n"
        + json.dumps(items, ensure_ascii=False, indent=1)
    )


def _conclusion_prompt(ctx: AuditContext) -> str:
    findings = sorted(ctx.findings.values(), key=lambda f: _CONCLUSION_ORDER.get(f.status, 9))
    shown = findings[:MAX_CONCLUSION_FINDINGS]
    counts: dict[str, int] = {}
    for f in findings:
        counts[f.status] = counts.get(f.status, 0) + 1
    rows = [
        {
            "id": f.id,
            "status": f.status,
            "method": f.method,
            "review_required": f.review_required,
            "before": [f"{r.doc}:{r.clause_id}" for r in f.before],
            "after": [f"{r.doc}:{r.clause_id}" for r in f.after],
            "reason": _clip(f.reason, REASON_CHARS),
            "citations": [
                {"doc": c.doc, "clause_id": c.clause_id, "quote": c.quote[:QUOTE_CHARS]} for c in f.citations
            ],
        }
        for f in shown
    ]
    docs = [{"doc": d.doc, "edition": d.edition, "source": d.source} for d in ctx.documents]
    note = "" if len(shown) == len(findings) else f"(showing {len(shown)} of {len(findings)} findings)\n"
    return (
        f"Documents: {json.dumps(docs, ensure_ascii=False)}\n"
        f"Finding counts by status: {json.dumps(counts, ensure_ascii=False)}\n"
        f"{note}Findings:\n{json.dumps(rows, ensure_ascii=False, indent=1)}"
    )

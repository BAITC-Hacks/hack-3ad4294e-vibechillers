"""Orchestration behind `POST /audits` and `GET /audits/{run_id}` (docs/plan.md §3).

Routes validate the multipart input and own the error envelope; this module
ingests the uploads with the kit pipeline (never RAG indexing), runs the
deterministic audit from `..audit`, optionally lets the agent adjudicate, and
turns every step into `Event` frames that are persisted through `TraceWriter`
before the client sees them. Exactly one terminal `final` or `error` ends a run.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from starlette.concurrency import run_in_threadpool

from .. import db
from ..audit import Document, Report, load_manifest, make_documents, report_summary, run_deterministic_audit
from ..audit.models import AgentExecution
from ..config import get_settings
from ..events import Event, SequenceCounter
from ..ingest import pipeline

logger = logging.getLogger("kit.api.audits")

RUN_KIND = "audit"
# Event types the agent may emit mid-run; the terminal frame is always ours.
_AGENT_EVENT_TYPES = frozenset({"status", "tool_call", "tool_result"})


@dataclass(frozen=True, slots=True)
class AuditUpload:
    edition: Literal["before", "after"]
    filename: str
    data: bytes


@dataclass(slots=True)
class IngestedAudit:
    documents: list[Document]
    pages_by_doc: dict[str, list[dict]]
    warnings: list[str]


class AuditInputError(ValueError):
    """An uploaded file the ingestion pipeline could not parse or store."""


class AuditConflict(ValueError):
    """Uploads that must not be compared as given (e.g. TXT and DOCX exports of one source)."""


class AuditNotFound(LookupError):
    pass


class AuditIncomplete(RuntimeError):
    pass


def _seed_manifest(uploads: list[tuple[AuditUpload, str]]) -> list[dict]:
    """Manifest entries the uploads identify by both file name and full SHA-256.

    A seed edition gets its v8/v9 alias only when the upload is named after it
    (stem, case-insensitive) and its bytes match; a renamed copy stays before-N/after-N.
    Different exports (TXT, DOCX) of one manifest source are rejected: they are one
    input, never two editions or two documents of a side.
    """
    entries = load_manifest()
    by_sha = {str(e.get("sha256", "")).lower(): e for e in entries if e.get("sha256")}
    admitted: list[dict] = []
    origins: dict[str, tuple[AuditUpload, str]] = {}
    for upload, sha256 in uploads:
        entry = by_sha.get(sha256)
        if entry is None:
            continue
        origin = str(entry.get("source") or "")
        prior = origins.get(origin) if origin else None
        if prior is not None and prior[1] != sha256:
            raise AuditConflict(
                f"{prior[0].edition} file {prior[0].filename!r} and {upload.edition} file "
                f"{upload.filename!r} are two exports of the same source document; "
                "upload one canonical export (DOCX) per edition"
            )
        if origin:
            origins.setdefault(origin, (upload, sha256))
        entry_file = str(entry.get("file") or "")
        if entry_file and Path(upload.filename.replace("\\", "/")).stem.lower() == Path(entry_file).stem.lower():
            if entry not in admitted:
                admitted.append(entry)
    return admitted


def ingest_uploads(before: list[AuditUpload], after: list[AuditUpload]) -> IngestedAudit:
    """Ingest both sides with `pipeline.ingest_bytes` and assign report-local aliases.

    Blocking (parsing + SQLite); call it from a worker thread. Raises
    `AuditConflict` before anything is ingested.
    """
    hashed = [(u, hashlib.sha256(u.data).hexdigest()) for u in (*before, *after)]
    manifest = _seed_manifest(hashed)
    sides: dict[str, list[tuple[str, str, str]]] = {"before": [], "after": []}
    pages: dict[str, list[list[dict]]] = {"before": [], "after": []}
    for upload, sha256 in hashed:
        try:
            parsed = pipeline.ingest_bytes(upload.data, upload.filename)
        except Exception as exc:
            raise AuditInputError(
                f"{upload.edition} file {upload.filename!r}: {str(exc) or type(exc).__name__}"
            ) from exc
        sides[upload.edition].append((parsed.doc_id, sha256, parsed.source))
        pages[upload.edition].append(parsed.pages)

    documents, warnings = make_documents(sides["before"], sides["after"], manifest=manifest)

    pages_by_doc: dict[str, list[dict]] = {}
    for edition in ("before", "after"):
        docs = [d for d in documents if d.edition == edition]
        if len(docs) != len(pages[edition]):
            raise RuntimeError(
                f"make_documents returned {len(docs)} {edition} documents for "
                f"{len(pages[edition])} ingested files"
            )
        for document, doc_pages in zip(docs, pages[edition], strict=True):
            pages_by_doc[document.doc] = doc_pages
    return IngestedAudit(documents=documents, pages_by_doc=pages_by_doc, warnings=list(warnings))


def run_input(before: list[AuditUpload], after: list[AuditUpload], use_llm: bool) -> dict[str, Any]:
    """`runs.input` for an audit; `kind` separates audits from `/run` chats on GET."""
    return {
        "kind": RUN_KIND,
        "use_llm": use_llm,
        "before": [u.filename for u in before],
        "after": [u.filename for u in after],
    }


def _with_warning(report: Report, message: str, *, status: str = "failed") -> Report:
    return report.model_copy(update={
        "mode": "deterministic",
        "warnings": [*report.warnings, message],
        "agent": AgentExecution(status=status, model=get_settings().llm_model, stop_reason=message),
    })


def _coverage_line(report: Report) -> str:
    c = report.coverage
    return (
        f"{len(report.findings)} findings; before {c.before_accounted}/{c.before_total} and "
        f"after {c.after_accounted}/{c.after_total} function clauses accounted for; "
        f"{c.unresolved} unresolved"
    )


async def stream_audit(
    run_id: str, ingested: IngestedAudit, *, use_llm: bool
) -> AsyncGenerator[Event, None]:
    """Yield the run's events; each is written to `agent_trace` before it is yielded.

    The `runs` row must already exist (FK). It is closed with `db.finish_run`
    even when the client disconnects mid-stream.
    """
    counter = SequenceCounter()
    outcome: dict[str, str | None] = {"status": "error", "output": None, "error": "audit aborted"}

    def make(type_: str, data: dict[str, Any]) -> Event:
        event = Event(type=type_, run_id=run_id, data=data, seq=counter.next())  # type: ignore[arg-type]
        with db.session() as conn:
            conn.execute(
                "INSERT INTO agent_trace (run_id, seq, ts, type, name, payload) VALUES (?, ?, ?, ?, ?, ?)",
                (run_id, event.seq, event.ts, type_, data.get("name"), json.dumps(data, ensure_ascii=False)),
            )
        return event

    try:
        try:
            for document in ingested.documents:
                blocks = len(ingested.pages_by_doc.get(document.doc, []))
                yield make(
                    "status",
                    {
                        "message": (
                            f"Ingested {document.edition} document {document.doc} from "
                            f"{document.source} (doc_id {document.doc_id}, {blocks} text blocks)"
                        )
                    },
                )
            yield make(
                "status",
                {"message": "Building deterministic report: parsing clauses, aligning functions, verifying citations"},
            )
            report = await run_in_threadpool(
                run_deterministic_audit,
                run_id,
                ingested.documents,
                ingested.pages_by_doc,
                ingested.warnings,
            )
            yield make("status", {"message": f"Deterministic report ready: {_coverage_line(report)}"})

            if use_llm:
                yield make("status", {"message": "Bounded model-driven audit investigation requested"})
                queue: asyncio.Queue[Event] = asyncio.Queue()

                def emit(type_: str, data: dict[str, Any]) -> None:
                    if type_ not in _AGENT_EVENT_TYPES or not isinstance(data, dict):
                        logger.warning("audit %s: dropped agent event of type %r", run_id, type_)
                        return
                    queue.put_nowait(make(type_, data))

                deterministic = report
                try:
                    from ..agent.audit_llm import adjudicate_report
                except Exception as exc:  # agent slice absent or broken: keep deterministic
                    logger.exception("audit %s: agent audit module unavailable", run_id)
                    adjudicate_report = None
                    report = _with_warning(
                        deterministic,
                        f"LLM assistance unavailable ({type(exc).__name__}: {exc}); "
                        "deterministic report returned.", status="unavailable",
                    )

                if adjudicate_report is not None:
                    task = asyncio.ensure_future(adjudicate_report(deterministic, emit=emit))
                    getter: asyncio.Future[Event] | None = None
                    try:
                        while not task.done():
                            getter = asyncio.ensure_future(queue.get())
                            await asyncio.wait({task, getter}, return_when=asyncio.FIRST_COMPLETED)
                            pending, getter = getter, None
                            if pending.done():
                                yield pending.result()
                            else:
                                pending.cancel()
                        while not queue.empty():
                            yield queue.get_nowait()
                    finally:
                        if getter is not None:
                            getter.cancel()
                        if not task.done():
                            task.cancel()
                    try:
                        candidate = Report.model_validate(task.result())
                        if candidate.run_id != run_id:
                            raise ValueError(
                                f"adjudicated report has run_id {candidate.run_id!r}, expected {run_id!r}"
                            )
                        report = candidate
                    except Exception as exc:  # key/model/validation failure never gates the report
                        logger.exception("audit %s: model investigation failed", run_id)
                        report = _with_warning(
                            deterministic,
                            f"Model investigation failed ({type(exc).__name__}: {exc}); "
                            "deterministic report returned.",
                        )
                yield make(
                    "status",
                    {"message": f"Report mode: {report.mode}; {_coverage_line(report)}"},
                )

            text = report_summary(report)
            final = make("final", {"text": text, "payload": report.model_dump(mode="json")})
            outcome.update(status="ok", output=text, error=None)
            yield final
        except GeneratorExit:
            if outcome["status"] != "ok":
                outcome.update(error="client disconnected before completion")
            raise
        except Exception as exc:
            logger.exception("audit %s failed", run_id)
            message = f"Audit failed: {type(exc).__name__}: {exc}"
            outcome.update(status="error", output=None, error=message)
            try:
                failure = make("error", {"message": message, "recoverable": False})
            except Exception:
                # Storage may itself be the failure: never show an unsaved final as success.
                failure = Event(type="error", run_id=run_id, seq=counter.next(), data={
                    "message": message + " Report/trace could not be persisted.", "recoverable": False,
                })
            yield failure
    finally:
        try:
            db.finish_run(run_id, str(outcome["status"]), output=outcome["output"], error=outcome["error"])
        except Exception:
            logger.exception("audit %s: finish_run failed", run_id)


def read_report(run_id: str) -> Report:
    """The persisted final payload of an audit run.

    Raises `AuditNotFound` for unknown ids and non-audit runs, `AuditIncomplete`
    when the run has no `final` frame (still running, failed or abandoned).
    """
    with db.session() as conn:
        run = conn.execute("SELECT status, input FROM runs WHERE id = ?", (run_id,)).fetchone()
        if run is None:
            raise AuditNotFound(f"audit run {run_id!r} not found")
        try:
            kind = json.loads(run["input"]).get("kind")
        except (TypeError, ValueError, AttributeError):
            kind = None
        if kind != RUN_KIND:
            raise AuditNotFound(f"run {run_id!r} is not an audit run")
        row = conn.execute(
            "SELECT payload FROM agent_trace WHERE run_id = ? AND type = 'final' ORDER BY seq DESC LIMIT 1",
            (run_id,),
        ).fetchone()
    payload = json.loads(row["payload"]).get("payload") if row is not None else None
    if not isinstance(payload, dict):
        raise AuditIncomplete(f"audit run {run_id!r} has no final report (run status: {run['status']})")
    return Report.model_validate(payload)

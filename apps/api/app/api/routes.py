"""HTTP surface per CONTRACT.md: /healthz, /run (SSE), /runs/{id}/trace, /upload.

Error shape everywhere is the envelope {"error": {"message", "type"}} — never a
bare stack trace, never FastAPI's default {"detail": ...} on our own paths.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.concurrency import run_in_threadpool

from .. import db
from ..agent.loop import run_agent
from ..agent.tools import ToolRegistry
from ..agent.trace import TraceWriter
from ..config import get_settings
from ..events import Event
from ..ingest import pipeline
from ..rag import search as rag_search
from .schemas import HealthOut, RunRequest, TraceOut, UploadOut

logger = logging.getLogger("kit.api")

router = APIRouter()

_SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


def error_response(status_code: int, message: str, typ: str) -> JSONResponse:
    """The one error envelope from CONTRACT.md."""
    return JSONResponse(status_code=status_code, content={"error": {"message": message, "type": typ}})


def _error_body(exc: BaseException) -> dict[str, Any]:
    return {"error": {"message": str(exc) or type(exc).__name__, "type": type(exc).__name__}}


@router.get("/healthz")
async def healthz(request: Request) -> JSONResponse:
    """200 even with no LLM key. `db` reports a real SELECT 1; on failure the
    endpoint answers 500 with the error envelope and db:"error"."""
    settings = get_settings()
    try:
        with db.session() as conn:
            conn.execute("SELECT 1").fetchone()
    except Exception as exc:
        body: dict[str, Any] = _error_body(exc)
        body["db"] = "error"
        return JSONResponse(status_code=500, content=body)
    payload = HealthOut(
        status="ok",
        llm_configured=bool(settings.llm_configured),
        db="ok",
        version=request.app.version,
    )
    return JSONResponse(status_code=200, content=payload.model_dump())


@router.post("/run")
async def run(body: RunRequest, request: Request) -> StreamingResponse:
    """Stream the agent run as SSE. Every frame carries run_id in its data."""
    run_id = uuid4().hex
    registry: ToolRegistry = request.app.state.tools

    async def stream():
        emitted = False
        last_seq = 0
        try:
            async for event in run_agent(
                body.prompt, run_id=run_id, registry=registry, history=body.history
            ):
                emitted = True
                last_seq = event.seq
                yield event.to_sse()
        except Exception as exc:  # loop died mid-stream: headers are gone, close with a frame
            logger.exception("run %s failed", run_id)
            yield Event(
                "error",
                run_id,
                {"message": str(exc) or type(exc).__name__, "recoverable": False},
                seq=last_seq + 1,
            ).to_sse()
            return
        if not emitted:
            # run_agent must terminate with exactly one final|error; if it
            # yielded nothing, say so and persist the frame to the trace.
            fallback = Event(
                "error",
                run_id,
                {"message": "agent loop produced no events", "recoverable": False},
                seq=1,
            )
            TraceWriter(run_id).write(fallback)
            yield fallback.to_sse()

    return StreamingResponse(stream(), media_type="text/event-stream", headers=_SSE_HEADERS)


@router.get("/runs/{run_id}/trace", response_model=TraceOut)
async def trace(run_id: str) -> TraceOut:
    """Replay from SQLite; an unknown run is 200 with an empty list."""
    return TraceOut(run_id=run_id, events=db.read_trace(run_id))


@router.post("/upload", response_model=UploadOut)
async def upload(file: UploadFile) -> JSONResponse:
    data = await file.read()
    if not data:
        return error_response(400, "uploaded file is empty", "empty_upload")
    filename = file.filename or ""
    suffix = Path(filename).suffix.lower()
    supported = sorted(pipeline.supported_suffixes())
    if suffix not in supported:
        return error_response(
            415,
            f"Unsupported file suffix {suffix!r}; supported: {', '.join(supported)}",
            "unsupported_media_type",
        )
    try:
        doc = await run_in_threadpool(pipeline.ingest_bytes, data, filename)
    except Exception as exc:  # parse/storage failure belongs to the client's document
        logger.exception("upload %s failed to parse", filename)
        return error_response(422, str(exc) or type(exc).__name__, "parse_error")
    try:
        chunks = await run_in_threadpool(rag_search.index_document, doc.doc_id)
    except Exception as exc:
        logger.exception("indexing doc %s failed", doc.doc_id)
        return error_response(500, str(exc) or type(exc).__name__, "index_error")
    out = UploadOut(doc_id=doc.doc_id, chunks=chunks, pages=len(doc.pages))
    return JSONResponse(status_code=200, content=out.model_dump())


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all registered on the app: envelope, no stack trace in the body."""
    return JSONResponse(status_code=500, content=_error_body(exc))


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"error": {"message": str(exc), "type": "validation_error"}},
    )

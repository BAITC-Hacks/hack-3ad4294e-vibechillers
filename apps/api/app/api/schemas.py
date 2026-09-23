"""Request/response models for the HTTP surface. Deliberately thin: the wire
formats that matter (SSE events, error envelope) live in `events.py` and
`routes.py`; these only type the JSON bodies."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RunRequest(BaseModel):
    """Body of `POST /run`. `history` is passed through to the agent loop verbatim."""

    prompt: str = Field(min_length=1)
    history: list[dict[str, Any]] | None = None


class HealthOut(BaseModel):
    status: str
    llm_configured: bool
    db: str
    version: str


class UploadOut(BaseModel):
    doc_id: str
    chunks: int
    pages: int


class TraceOut(BaseModel):
    run_id: str
    events: list[dict[str, Any]]

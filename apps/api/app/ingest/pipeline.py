"""Ingestion pipeline: file bytes -> `documents` + `chunks` rows.

One call, one transaction: ``ingest_path`` hashes the file, parses it with
:mod:`apps.api.app.ingest.parsers`, splits the pages with
:mod:`apps.api.app.rag.chunk`, and writes the ``documents`` row together with
its ``chunks`` rows inside a single :func:`apps.api.app.db.session`.

Identity is content-based: ``doc_id`` is the first 16 hex characters of the
file's SHA-256, so re-ingesting the same bytes replaces the previous record
(``INSERT OR REPLACE`` plus a stale-chunk delete) instead of duplicating it.

Vector/FTS indexing is deliberately *not* done here — the caller invokes
``rag.search.index_document(doc_id)`` afterwards.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from .. import db
from ..config import get_settings
from ..rag.chunk import chunk_id, split_pages
from .parsers import parse_any, supported_suffixes

__all__ = ["ParsedDoc", "ingest_path", "ingest_bytes", "supported_suffixes"]


@dataclass
class ParsedDoc:
    """The ingested document as returned to the caller."""

    doc_id: str
    source: str
    title: str | None
    media_type: str
    pages: list[dict] = field(default_factory=list)  # [{"page": int, "text": str}]


def _doc_id_for(data: bytes) -> str:
    """Content-addressed identifier: first 16 hex chars of sha256(data)."""
    return hashlib.sha256(data).hexdigest()[:16]


def ingest_path(path: str | Path, *, source: str | None = None) -> ParsedDoc:
    """Parse `path`, chunk it, and persist it as one atomic unit.

    `source` defaults to the file name. The ``title`` is the file name without
    its suffix (stem) — parsers do not reliably expose document titles, so the
    name is the best human label available.
    """
    p = Path(path)
    data = p.read_bytes()
    doc_id = _doc_id_for(data)

    pages, media_type = parse_any(p)
    chunks = split_pages(pages)

    title = p.stem or None
    src = source if source is not None else p.name
    meta = json.dumps({"path": str(p), "bytes": len(data), "chunks": len(chunks)})

    with db.session() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO documents
                (id, source, title, media_type, created_at, meta)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (doc_id, src, title, media_type, time.time(), meta),
        )
        # Rebuild the chunk set exactly: drop anything left from a previous
        # ingestion of the same content (the chunking config may have changed).
        conn.execute("DELETE FROM chunks WHERE doc_id = ?", (doc_id,))
        conn.executemany(
            "INSERT INTO chunks (id, doc_id, ordinal, page, text) VALUES (?, ?, ?, ?, ?)",
            [
                (chunk_id(doc_id, c["ordinal"]), doc_id, c["ordinal"], c["page"], c["text"])
                for c in chunks
            ],
        )

    return ParsedDoc(doc_id=doc_id, source=src, title=title, media_type=media_type, pages=pages)


def ingest_bytes(data: bytes, filename: str, *, source: str | None = None) -> ParsedDoc:
    """Persist raw upload bytes under `data_dir/uploads`, then ingest them.

    The filename is sanitised to its basename (suffix kept); an existing target
    is overwritten, which is safe because the doc_id is derived from the
    content, not from the name. `source` defaults to the given filename.
    """
    name = Path(filename.replace("\\", "/")).name
    if not name:
        raise ValueError("ingest_bytes: filename is empty after sanitising")
    uploads = get_settings().data_dir / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    target = uploads / name
    target.write_bytes(data)
    return ingest_path(target, source=source if source is not None else name)

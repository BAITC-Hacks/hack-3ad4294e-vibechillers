"""Hybrid retrieval + index maintenance over the RAG layers.

``search`` runs the query through both index layers owned by
:mod:`apps.api.app.rag.store` — dense ``knn`` and lexical ``bm25`` — and fuses
the two ranked lists with reciprocal rank fusion (RRF):

    score(chunk) = sum over each list of 1 / (RRF_K + rank),  rank 1-based

RRF only uses ranks, so it composes without tuning against the two layers'
incomparable score scales (cosine distance vs SQLite bm25). The fused union is
hydrated from SQLite in ONE query joining ``chunks`` with ``documents`` (text,
page, doc_id, source), sorted by RRF score descending, truncated to ``k``.

Indexing is split out of ingestion (see ``ingest/pipeline.py``): the pipeline
writes ``chunks`` rows, ``index_document`` embeds and upserts them into the
vector + FTS layers. ``index_all`` sweeps anything the index is missing.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, Field

from .. import db
from ..agent.tools import Tool, ToolRegistry
from . import embed, store

__all__ = ["Hit", "search", "index_document", "index_all", "register_tools"]

# RRF smoothing constant: standard value from the original fusion paper.
RRF_K = 60
# Per-list candidate pool; at least 4x the final k, never fewer than 24.
_MIN_POOL = 24
# Rough character budget for one search hit inside tool output.
SNIPPET_CHARS = 600


@dataclass
class Hit:
    """One fused search result (shape fixed by CONTRACT.md)."""

    chunk_id: str
    doc_id: str
    text: str
    score: float
    source: str
    page: int | None


def search(query: str, k: int = 10) -> list[Hit]:
    """Hybrid dense+lexical search over indexed chunks; best (highest RRF) first.

    Embeds the query, asks each layer for a ``max(k*4, 24)``-sized pool, fuses
    the rankings, hydrates the union in a single SQL join, and returns the top
    ``k`` hits. Non-positive ``k`` yields an empty list; a query the lexical
    layer cannot parse (no word tokens) simply contributes no bm25 votes.
    """
    if k <= 0:
        return []

    vector = embed.embed_query(query)
    pool = max(k * 4, _MIN_POOL)
    fused: dict[str, float] = {}
    for ranked in (store.knn(vector, pool), store.bm25(query, pool)):
        for rank, (cid, _score) in enumerate(ranked, start=1):
            fused[cid] = fused.get(cid, 0.0) + 1.0 / (RRF_K + rank)
    if not fused:
        return []

    ordered = sorted(fused, key=fused.get, reverse=True)
    with db.session() as conn:
        placeholders = ",".join("?" * len(ordered))
        rows = {
            r["id"]: r
            for r in conn.execute(
                f"""
                SELECT c.id, c.doc_id, c.text, c.page, d.source
                  FROM chunks c
                  JOIN documents d ON d.id = c.doc_id
                 WHERE c.id IN ({placeholders})
                """,
                ordered,
            )
        }
    hits: list[Hit] = []
    for cid in ordered:
        row = rows.get(cid)
        if row is None:  # raced with a delete between ranking and hydration
            continue
        hits.append(
            Hit(
                chunk_id=cid,
                doc_id=str(row["doc_id"]),
                text=str(row["text"]),
                score=float(fused[cid]),
                source=str(row["source"]),
                page=int(row["page"]) if row["page"] is not None else None,
            )
        )
        if len(hits) >= k:
            break
    return hits


def index_document(doc_id: str) -> int:
    """Embed + upsert every chunk of one document into the vector/FTS layers.

    Assumes the ``chunks`` rows already exist (``ingest/pipeline`` writes them);
    this function only maintains the indexes. Returns the number of chunks
    indexed; an unknown ``doc_id`` (or a document with no chunks) returns 0 and
    does not raise. Re-indexing replaces the previous vectors/FTS entries —
    ``store.upsert_chunks`` is idempotent per chunk id.
    """
    with db.session() as conn:
        rows = conn.execute(
            "SELECT id, ordinal, text FROM chunks WHERE doc_id = ? ORDER BY ordinal",
            (doc_id,),
        ).fetchall()
    if not rows:
        return 0
    texts = [str(r["text"]) for r in rows]
    vectors = embed.embed_texts(texts)
    return store.upsert_chunks([{"id": str(r["id"])} for r in rows], vectors)


def index_all() -> int:
    """Index every chunk that has no ``vec_chunks`` row yet; returns the count.

    Deliberately incremental (documents with *any* unindexed chunk are re-indexed
    whole) instead of re-embedding everything: embedding is the expensive step
    and ``upsert_chunks`` makes re-indexing a document safe. An already fully
    indexed corpus costs one cheap SQL query here. Intended for the API
    lifespan and eval scripts; the DB schema must already exist.
    """
    conn = store._connect()  # vec_chunks is a virtual table: needs the extension loaded
    try:
        doc_ids = [
            str(r["doc_id"])
            for r in conn.execute(
                """
                SELECT c.doc_id
                  FROM chunks c
                  LEFT JOIN vec_chunks v ON v.chunk_id = c.id
                 WHERE v.chunk_id IS NULL
                 GROUP BY c.doc_id
                 ORDER BY c.doc_id
                """
            )
        ]
    finally:
        conn.close()
    return sum(index_document(doc_id) for doc_id in doc_ids)


class SearchParams(BaseModel):
    """Arguments for the search_documents tool."""

    query: str = Field(
        description="Natural-language question or keywords to retrieve against."
    )
    k: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Number of best-matching chunks to return.",
    )


def _search_documents(query: str, k: int) -> list[dict]:
    """Hybrid-search wrapper exposed to the LLM as ``search_documents``.

    Returns the compact per-hit shape
    ``[{"chunk_id", "source", "page", "text"}, ...]``. ``text`` is truncated to
    at most ``SNIPPET_CHARS`` (~600) characters — an ellipsis marks a cut — to
    keep tool results inside the model's context budget; full text stays
    available via ``search()``. Sync on purpose: ``call_tool`` threads it.
    """
    out: list[dict] = []
    for hit in search(query, k):
        text = hit.text
        if len(text) > SNIPPET_CHARS:
            text = text[: SNIPPET_CHARS - 1].rstrip() + "…"
        out.append(
            {
                "chunk_id": hit.chunk_id,
                "source": hit.source,
                "page": hit.page,
                "text": text,
            }
        )
    return out


def register_tools(registry) -> None:
    """Register the RAG slice's tools into a shared :class:`ToolRegistry`."""
    registry.register(
        Tool(
            name="search_documents",
            description=(
                "Semantic + keyword search over the indexed document chunks. "
                "Returns the best-matching passages with their source file and "
                "page number."
            ),
            params=SearchParams,
            fn=_search_documents,
        )
    )

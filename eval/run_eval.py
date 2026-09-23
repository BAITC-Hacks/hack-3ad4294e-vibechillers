#!/usr/bin/env python3
"""Retrieval evaluation harness over the synthetic fixture corpus.

Reads ``eval/queries.jsonl`` (one JSON object per line: ``qid``, ``query``,
``expected`` doc_ids), makes sure the three kit fixtures
(``data/fixtures/{dummy.pdf,t.xlsx,t.csv}``) are ingested and indexed in the
target database, runs hybrid ``rag.search`` for every query, and scores the
runs with ranx (HitRate@5, MRR@10). The per-query table plus aggregates are
printed to stdout and written to ``docs/evidence/results.md``.

Usage (from the repo root):

    uv run --no-sync python eval/run_eval.py            # shared DB (settings.db_path)
    uv run --no-sync python eval/run_eval.py --db data/t16.db --top-k 10

Exit codes: 0 = scored; 2 = a query's expected doc is not in the corpus
(stale harness — fails loudly); 3 = fixture files or queries missing.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):  # Windows console may not be UTF-8
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))

QUERIES_PATH = REPO_ROOT / "eval" / "queries.jsonl"
FIXTURES_DIR = REPO_ROOT / "data" / "fixtures"
FIXTURE_NAMES = ("dummy.pdf", "t.xlsx", "t.csv")
EVIDENCE_PATH = REPO_ROOT / "docs" / "evidence" / "results.md"

HIT_K = 5   # HitRate cutoff
RR_K = 10   # reciprocal-rank cutoff


def doc_id_for(data: bytes) -> str:
    """Content-addressed id, identical to ingest/pipeline._doc_id_for."""
    return hashlib.sha256(data).hexdigest()[:16]


def load_queries(path: Path) -> list[dict]:
    out = []
    with path.open(encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            for key in ("qid", "query", "expected"):
                if key not in obj:
                    raise ValueError(f"{path}:{lineno}: missing key {key!r}")
            out.append(obj)
    return out


def ensure_corpus(db, store, rag_search) -> dict[str, str]:
    """Ingest + index the three fixtures unless already present. Idempotent.

    Returns {doc_id: source}. Re-indexing an already-ingested doc is safe:
    ``index_document`` upserts by chunk id, so a DB whose vec/FTS layers were
    rebuilt elsewhere still ends this run fully searchable.
    """
    missing = [n for n in FIXTURE_NAMES if not (FIXTURES_DIR / n).is_file()]
    if missing:
        print(f"ERROR: fixture files missing under {FIXTURES_DIR}: {missing}", file=sys.stderr)
        raise SystemExit(3)

    from app.ingest import pipeline

    with db.session() as conn:
        have = {str(r["id"]) for r in conn.execute("SELECT id FROM documents")}

    docs: dict[str, str] = {}
    for name in FIXTURE_NAMES:
        path = FIXTURES_DIR / name
        did = doc_id_for(path.read_bytes())
        if did not in have:
            parsed = pipeline.ingest_path(path)
            print(f"ingested {name} -> doc_id={did} ({len(parsed.pages)} page(s))")
        else:
            print(f"doc_id={did} ({name}) already in corpus")
        indexed = rag_search.index_document(did)
        print(f"  indexed {indexed} chunk(s) for {did}")
        docs[did] = name
    return docs


def format_table(rows: list[dict], aggregates: dict[str, float], engine_note: str) -> str:
    lines = [
        "| qid | query | rank found | hit@5 | rr@10 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for r in rows:
        q = r["query"] if len(r["query"]) <= 46 else r["query"][:43] + "..."
        rank = str(r["rank"]) if r["rank"] else "-"
        lines.append(f"| {r['qid']} | {q} | {rank} | {r['hit']} | {r['rr']:.4f} |")
    lines.append("")
    lines.append(
        f"**HitRate@{HIT_K} = {aggregates['hit_rate']:.4f} | MRR@{RR_K} = {aggregates['mrr']:.4f}**"
    )
    if engine_note:
        lines.append("")
        lines.append(engine_note)
    return "\n".join(lines)


def score(qrels: dict, run: dict, rows: list[dict]) -> tuple[dict[str, float], str]:
    """Aggregate HitRate@5 / MRR@10 via ranx; manual fallback if unavailable.

    The fallback applies the identical formulas to the same per-query ranking,
    so the numbers match ranx exactly; it exists only so the harness runs in an
    environment where the optional [eval] extra is broken, and says so.
    """
    try:
        import ranx
    except Exception as exc:  # noqa: BLE001 - any import-time failure degrades
        note = (
            f"_ranx import failed ({exc.__class__.__name__}: {exc}); "
            "metrics computed with the in-script reference implementation._"
        )
        return _manual(rows), note

    last: Exception | None = None
    for mrr_name in ("mrr", "reciprocal_rank"):
        key_hr, key_rr = f"hit_rate@{HIT_K}", f"{mrr_name}@{RR_K}"
        try:
            res = ranx.evaluate(qrels, run, [key_hr, key_rr])
            return (
                {"hit_rate": float(res[key_hr]), "mrr": float(res[key_rr])},
                f"_Metrics computed with ranx (`{key_hr}`, `{key_rr}`)._",
            )
        except Exception as exc:  # noqa: BLE001 - try the alias, then degrade
            last = exc
    note = (
        f"_ranx present but rejected the metric call ({last.__class__.__name__}: {last}); "
        "metrics computed with the in-script reference implementation._"
    )
    return _manual(rows), note


def _manual(rows: list[dict]) -> dict[str, float]:
    n = len(rows) or 1
    return {
        "hit_rate": sum(r["hit"] for r in rows) / n,
        "mrr": sum(r["rr"] for r in rows) / n,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Evaluate hybrid retrieval on fixture queries.")
    ap.add_argument("--db", default=None, help="SQLite path (default: settings.db_path)")
    ap.add_argument("--top-k", type=int, default=10, help="results fetched per query (default 10)")
    args = ap.parse_args()

    if args.db:
        os.environ["DB_PATH"] = str(Path(args.db).expanduser().resolve())

    from app import db
    from app.config import get_settings
    from app.rag import search as rag_search
    from app.rag import store

    settings = get_settings()
    db.init_schema()
    store.ensure_index()

    if not QUERIES_PATH.is_file():
        print(f"ERROR: queries file not found: {QUERIES_PATH}", file=sys.stderr)
        return 3

    queries = load_queries(QUERIES_PATH)
    corpus_docs = ensure_corpus(db, store, rag_search)

    # Fail loudly when the harness points at docs that cannot exist here.
    with db.session() as conn:
        present = {
            str(r["id"])
            for r in conn.execute(
                "SELECT d.id FROM documents d JOIN chunks c ON c.doc_id = d.id GROUP BY d.id"
            )
        }
    unknown = sorted({e for q in queries for e in q["expected"]} - present)
    if unknown:
        print(
            f"ERROR: expected doc_ids absent from corpus {settings.db_path}: {unknown}",
            file=sys.stderr,
        )
        return 2

    # Run retrieval.
    rows: list[dict] = []
    qrels: dict[str, dict[str, int]] = {}
    run: dict[str, dict[str, float]] = {}
    for q in queries:
        hits = rag_search.search(q["query"], k=args.top_k)
        ranked_docs: list[str] = []
        for h in hits:  # keep first occurrence, drop duplicate docs
            if h.doc_id not in ranked_docs:
                ranked_docs.append(h.doc_id)
        expected = set(q["expected"])
        rank = next((i for i, d in enumerate(ranked_docs, 1) if d in expected), 0)
        rows.append(
            {
                "qid": q["qid"],
                "query": q["query"],
                "rank": rank,
                "hit": 1 if 1 <= rank <= HIT_K else 0,
                "rr": (1.0 / rank) if 1 <= rank <= RR_K else 0.0,
            }
        )
        qrels[q["qid"]] = {d: 1 for d in expected}
        n = len(ranked_docs)
        run[q["qid"]] = {d: float(n - i) for i, d in enumerate(ranked_docs)}  # strict order

    aggregates, engine_note = score(qrels, run, rows)

    table = format_table(rows, aggregates, engine_note)
    print(table)
    print(f"\ncorpus docs: {corpus_docs}")

    # Evidence artifact.
    with db.session() as conn:
        n_chunks = conn.execute("SELECT count(*) AS n FROM chunks").fetchone()["n"]
    stamp = dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE_PATH.write_text(
        "\n".join(
            [
                "# Retrieval evaluation — synthetic fixtures",
                "",
                f"- Generated: {stamp}",
                f"- Database: `{settings.db_path}`",
                f"- Embedding model: `{settings.embed_model}`",
                f"- LLM model: `{settings.llm_model}`",
                f"- Chunks in corpus: {n_chunks}",
                f"- Queries: {len(queries)} (eval/queries.jsonl), top-k={args.top_k}",
                "",
                table,
                "",
                "Queries are synthetic-kit fixtures against the demo corpus; "
                "they are replaced per-case on build day.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"wrote {EVIDENCE_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

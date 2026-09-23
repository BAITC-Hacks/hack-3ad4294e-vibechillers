"""Vector + full-text indexes over `chunks`, stored in the SAME SQLite file as
`apps.api.app.db` (settings.db_path, default data/app.db).

db.connect() deliberately does not enable extension loading, so every function
here opens its own connection via db.connect(), enables load_extension, loads
sqlite_vec, and closes the connection when done. No global/shared connection is
kept. Callers must have run db.init_schema() first: this module owns only the
index tables (vec_chunks, chunks_fts) and their sync triggers, never the core
`chunks` / `documents` tables.

FTS5 sync mechanism
-------------------
`chunks_fts` is an external-content table (content='chunks',
content_rowid='rowid'): it stores only the inverted index plus a
`chunks_fts_docsize` shadow table; the text itself lives in `chunks`. Keeping
the two in step uses three layers (in order of cost):

1. Triggers created by ensure_index() handle ordinary DML on chunks:
   AFTER INSERT adds the row, AFTER DELETE removes it via the fts5 'delete'
   command with the old row, AFTER UPDATE deletes-then-reinserts.
2. INSERT OR REPLACE -- the pattern the ingest pipeline uses -- defeats layer 1:
   SQLite's REPLACE conflict resolution removes the conflicting row WITHOUT
   firing DELETE triggers, leaving its FTS entry orphaned under the old rowid.
   So upsert_chunks() re-syncs FTS explicitly for every touched chunk id: a
   guarded 'delete' of the row's current index entry (only when the rowid is
   actually present in chunks_fts_docsize -- deleting a rowid that was never
   indexed corrupts the external-content index) followed by re-inserting the
   row's current text.
3. As a final safety net upsert_chunks() runs a cheap bidirectional drift check
   between `chunks` rowids and `chunks_fts_docsize` ids; if anything is still
   out of step (e.g. orphaned rows from an earlier REPLACE that predated the
   index), it issues an FTS 'rebuild', which reloads the index wholesale from
   `chunks`. The drift check is what guarantees the invariant
   fts rows == chunks rows; the per-id delete+insert is an idempotent fast path
   that avoids rebuilding on every upsert.
"""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

import numpy as np
import sqlite_vec

from .. import db
from ..config import get_settings

# Unicode word characters (Cyrillic included). Everything else is punctuation
# or FTS5 query syntax and is dropped before the query is built.
_TOKEN_RE = re.compile(r"\w+", re.UNICODE)
# Words of this length or more are indexed as prefix phrases: the stem drops
# the last two characters, so "инфляция" matches "инфляцию" / "инфляции" etc.
_STEM_MIN_LEN = 5
_STEM_DROP = 2

_FTS_DELETE_SQL = """
INSERT INTO chunks_fts(chunks_fts, rowid, text)
SELECT 'delete', c.rowid, c.text
  FROM chunks c
 WHERE c.id = ?
   AND EXISTS (SELECT 1 FROM chunks_fts_docsize d WHERE d.id = c.rowid)
"""

_FTS_INSERT_SQL = """
INSERT INTO chunks_fts(rowid, text)
SELECT c.rowid, c.text FROM chunks c WHERE c.id = ?
"""

# True when an FTS docsize entry has no backing chunks row, or a chunks row has
# no FTS entry. Either case means the index needs a full rebuild.
_DRIFT_SQL = """
SELECT EXISTS (
         SELECT 1 FROM chunks_fts_docsize d
          WHERE NOT EXISTS (SELECT 1 FROM chunks c WHERE c.rowid = d.id)
       )
    OR EXISTS (
         SELECT 1 FROM chunks c
          WHERE NOT EXISTS (SELECT 1 FROM chunks_fts_docsize d WHERE d.id = c.rowid)
       )
"""


def _connect() -> sqlite3.Connection:
    """Fresh connection to the shared DB file with the sqlite-vec extension loaded."""
    conn = db.connect()
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    return conn


@contextmanager
def _write_txn() -> Iterator[sqlite3.Connection]:
    """Fresh connection with one IMMEDIATE transaction wrapped around the body."""
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.execute("COMMIT")
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        raise
    finally:
        conn.close()


def _index_dim() -> int:
    dim = get_settings().embed_dim
    if dim <= 0:
        raise ValueError(f"embed_dim must be positive, got {dim}")
    return dim


def _drop_stale_vectors(conn: sqlite3.Connection, dim: int) -> None:
    """Drop vec_chunks when it was built by another EMBED_MODEL or width.

    Vectors from two models are not comparable, and vec0 rejects a width change,
    so a model switch must start the vector index from scratch. `chunks` and the
    FTS index are untouched; search.index_all() re-embeds at the next startup.
    """
    model = get_settings().embed_model
    conn.execute("CREATE TABLE IF NOT EXISTS rag_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    row = conn.execute("SELECT value FROM rag_meta WHERE key = 'embed'").fetchone()
    current = f"{model}|{dim}"
    if row is not None and row[0] == current:
        return
    has_vec = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE name = 'vec_chunks'"
    ).fetchone()
    if has_vec:  # built by another model, or before rag_meta existed
        conn.execute("DROP TABLE vec_chunks")
    conn.execute(
        "INSERT OR REPLACE INTO rag_meta (key, value) VALUES ('embed', ?)", (current,)
    )


def ensure_index() -> None:
    """Create vec_chunks, chunks_fts and the chunks sync triggers. Idempotent."""
    dim = _index_dim()
    statements = [
        f"CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks "
        f"USING vec0(chunk_id TEXT PRIMARY KEY, embedding float[{dim}])",
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
            text,
            content='chunks',
            content_rowid='rowid',
            tokenize="unicode61 remove_diacritics 0"
        )
        """,
        """
        CREATE TRIGGER IF NOT EXISTS chunks_fts_sync_ai AFTER INSERT ON chunks BEGIN
            INSERT INTO chunks_fts(rowid, text) VALUES (new.rowid, new.text);
        END
        """,
        """
        CREATE TRIGGER IF NOT EXISTS chunks_fts_sync_ad AFTER DELETE ON chunks BEGIN
            INSERT INTO chunks_fts(chunks_fts, rowid, text)
            VALUES ('delete', old.rowid, old.text);
        END
        """,
        """
        CREATE TRIGGER IF NOT EXISTS chunks_fts_sync_au AFTER UPDATE ON chunks BEGIN
            INSERT INTO chunks_fts(chunks_fts, rowid, text)
            VALUES ('delete', old.rowid, old.text);
            INSERT INTO chunks_fts(rowid, text) VALUES (new.rowid, new.text);
        END
        """,
    ]
    conn = _connect()
    try:
        _drop_stale_vectors(conn, dim)
        for sql in statements:
            conn.execute(sql)
        conn.commit()
    finally:
        conn.close()


def reset_index() -> None:
    """Drop and recreate both index tables (and their triggers).

    The `chunks` table itself is NOT touched -- only derived index state.
    """
    conn = _connect()
    try:
        for sql in (
            "DROP TRIGGER IF EXISTS chunks_fts_sync_ai",
            "DROP TRIGGER IF EXISTS chunks_fts_sync_ad",
            "DROP TRIGGER IF EXISTS chunks_fts_sync_au",
            "DROP TABLE IF EXISTS vec_chunks",
            "DROP TABLE IF EXISTS chunks_fts",
        ):
            conn.execute(sql)
        conn.commit()
    finally:
        conn.close()
    ensure_index()


def upsert_chunks(rows: list[dict], vectors: np.ndarray) -> int:
    """Index rows[i]['id'] with vectors[i]; returns the number of rows upserted.

    The chunks-table rows themselves are assumed to be already inserted by the
    ingest pipeline (this function never writes to `chunks`). Re-upserting the
    same ids replaces their vector and FTS state instead of duplicating it:
    old vec_chunks rows are deleted by chunk_id first, FTS is re-synced per the
    module docstring, and everything runs inside ONE transaction.
    """
    if not rows:
        return 0
    dim = _index_dim()
    vecs = np.asarray(vectors, dtype=np.float32)
    if vecs.ndim != 2 or vecs.shape != (len(rows), dim):
        raise ValueError(
            f"vectors must have shape ({len(rows)}, {dim}), got {vecs.shape}"
        )
    ids = [str(r["id"]) for r in rows]
    vecs = np.ascontiguousarray(vecs)
    with _write_txn() as conn:
        conn.executemany("DELETE FROM vec_chunks WHERE chunk_id = ?", ((i,) for i in ids))
        conn.executemany(
            "INSERT INTO vec_chunks(chunk_id, embedding) VALUES (?, ?)",
            ((i, sqlite_vec.serialize_float32(vecs[j])) for j, i in enumerate(ids)),
        )
        unique_ids = set(ids)
        conn.executemany(_FTS_DELETE_SQL, ((i,) for i in unique_ids))
        conn.executemany(_FTS_INSERT_SQL, ((i,) for i in unique_ids))
        if conn.execute(_DRIFT_SQL).fetchone()[0]:
            conn.execute("INSERT INTO chunks_fts(chunks_fts) VALUES ('rebuild')")
    return len(ids)


def knn(vector: np.ndarray, k: int) -> list[tuple[str, float]]:
    """Nearest `k` chunk_ids by vec0 distance, ascending (0.0 = exact hit)."""
    if k <= 0:
        return []
    dim = _index_dim()
    v = np.asarray(vector, dtype=np.float32)
    if v.size != dim:
        raise ValueError(f"query vector must hold {dim} components, got shape {v.shape}")
    blob = sqlite_vec.serialize_float32(np.ascontiguousarray(v.reshape(dim)))
    conn = _connect()
    try:
        cur = conn.execute(
            "SELECT chunk_id, distance FROM vec_chunks "
            "WHERE embedding MATCH ? AND k = ? ORDER BY distance",
            (blob, int(k)),
        )
        return [(str(r[0]), float(r[1])) for r in cur.fetchall()]
    finally:
        conn.close()


def _fts_query(query: str) -> str:
    """Turn free text into a safe FTS5 phrase query (implicit AND between terms).

    Every token is quoted so no user input can reach the FTS5 query parser as
    syntax; long tokens additionally become prefix phrases so Russian (and
    other agglutinative) case endings still match.
    """
    parts = []
    for tok in _TOKEN_RE.findall(query.lower()):
        if len(tok) >= _STEM_MIN_LEN:
            parts.append(f'"{tok[:-_STEM_DROP]}"*')
        else:
            parts.append(f'"{tok}"')
    return " ".join(parts)


def bm25(query: str, k: int) -> list[tuple[str, float]]:
    """Top `k` chunk_ids by FTS5 bm25, ascending score (bm25 lower = better).

    The index stores rowids; results join back through chunks.rowid to expose
    the stable textual chunk id.
    """
    if k <= 0:
        return []
    q = _fts_query(query)
    if not q:
        return []
    conn = _connect()
    try:
        cur = conn.execute(
            """
            SELECT c.id, bm25(chunks_fts) AS score
              FROM chunks_fts f
              JOIN chunks c ON c.rowid = f.rowid
             WHERE chunks_fts MATCH ?
             ORDER BY score ASC
             LIMIT ?
            """,
            (q, int(k)),
        )
        return [(str(r[0]), float(r[1])) for r in cur.fetchall()]
    finally:
        conn.close()


def index_stats() -> dict:
    """Row counts for each index layer plus the configured embedding dimension.

    fts_rows counts the FTS index itself (chunks_fts_docsize), not a scan of
    the content table, so it exposes any sync drift against chunk_rows.
    """
    conn = _connect()

    def _count(sql: str) -> int:
        try:
            return int(conn.execute(sql).fetchone()[0])
        except sqlite3.OperationalError:
            return 0  # table not created yet

    try:
        return {
            "vec_rows": _count("SELECT count(*) FROM vec_chunks"),
            "chunk_rows": _count("SELECT count(*) FROM chunks"),
            "fts_rows": _count("SELECT count(*) FROM chunks_fts_docsize"),
            "dim": _index_dim(),
        }
    finally:
        conn.close()

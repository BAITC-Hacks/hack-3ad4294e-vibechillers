"""Durable run trace: our own events and openai-agents SDK spans in one table.

`agent_trace` (owned by app/db.py) is the single audit log for a run. Two writers
land in it:

- `TraceWriter` inserts the `Event` envelopes the agent loop emits (type comes
  from the event: status/token/tool_call/...).
- `SqliteTracingProcessor` implements the SDK's `agents.tracing.TracingProcessor`
  (openai-agents 0.22.3) and inserts completed spans with type='span'.

run_id for SDK spans is resolved in this order (documented per the build plan):

1. the trace's metadata dict under the key ``"run_id"`` — i.e.
   ``trace("wf", metadata={"run_id": run_id})``;
2. the module-level current run set via :func:`set_current_run` — the loop calls
   this once at run start, so spans created anywhere inside the run inherit it;
3. the trace id itself as a last resort. The insert then fails the foreign key
   to ``runs(id)`` (no such run), which is caught and reported to stderr — the
   run never dies because tracing failed.

Seq numbering: events carry their own seq (from `SequenceCounter`). Spans get a
per-run seq from a module-level counter that is seeded from ``MAX(seq)`` already
in the table, so span rows interleave after the events without collisions.

Every write path swallows exceptions and prints one line to stderr — tracing is
best-effort and must never break the run.
"""

from __future__ import annotations

import json
import sys
import threading
import time
from collections.abc import Iterable
from datetime import datetime
from typing import Any

from ..db import session
from ..events import Event

try:  # subclass the real ABC so abstract-method drift is a TypeError at import
    from agents.tracing import TracingProcessor as _TracingProcessor
except ImportError:  # SDK optional at import time; install_tracing() fails loudly
    _TracingProcessor = object

_INSERT_SQL = (
    "INSERT INTO agent_trace (run_id, seq, ts, type, name, payload) VALUES (?, ?, ?, ?, ?, ?)"
)

# Metadata key a trace can set to bind itself to a run: trace(metadata={"run_id": ...}).
RUN_ID_METADATA_KEY = "run_id"

_lock = threading.Lock()
_current_run: str | None = None
_seq_counters: dict[str, int] = {}  # run_id -> highest seq handed out this process
_trace_runs: dict[str, str] = {}  # trace_id -> resolved run_id (filled on trace start)
_installed_processor: Any | None = None


def _warn(context: str, err: BaseException) -> None:
    """One-line stderr note. Tracing failures are never raised into the caller."""
    try:
        print(f"[trace] {context} failed: {type(err).__name__}: {err}", file=sys.stderr)
    except Exception:
        pass


def _json_payload(obj: Any) -> str:
    """json.dumps that never raises: plain first, default=str second, marker last."""
    try:
        return json.dumps(obj, ensure_ascii=False)
    except (TypeError, ValueError):
        pass
    try:
        return json.dumps(obj, ensure_ascii=False, default=str)
    except Exception:
        return json.dumps({"trace_error": "payload not json-serializable"})


def _event_name(data: Any) -> str | None:
    if isinstance(data, dict):
        name = data.get("name")
        return name if isinstance(name, str) else (None if name is None else str(name))
    return None


def _bump_seq(run_id: str, seq: int) -> None:
    """Keep the shared per-run counter ahead of explicitly-sequenced event rows."""
    with _lock:
        if seq > _seq_counters.get(run_id, 0):
            _seq_counters[run_id] = seq


def _next_seq(run_id: str) -> int:
    """Next seq for span rows: seeded once per run from MAX(seq) in the table."""
    with _lock:
        n = _seq_counters.get(run_id)
        if n is None:
            try:
                with session() as conn:
                    row = conn.execute(
                        "SELECT COALESCE(MAX(seq), 0) FROM agent_trace WHERE run_id = ?",
                        (run_id,),
                    ).fetchone()
                n = int(row[0])
            except Exception as err:
                _warn("seq seed", err)
                n = 0
        n += 1
        _seq_counters[run_id] = n
        return n


def set_current_run(run_id: str | None) -> None:
    """Bind subsequently-started SDK traces to `run_id` (None clears the binding).

    The agent loop calls this right after `db.create_run(...)`; spans the SDK
    emits during the run then land under this run without per-trace metadata.
    """
    global _current_run
    with _lock:
        _current_run = run_id


class TraceWriter:
    """Append-only writer for one run's event trace. `write` never raises."""

    __slots__ = ("run_id",)

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id

    def _row(self, event: Event) -> tuple[Any, ...]:
        run_id = event.run_id or self.run_id
        return (
            run_id,
            event.seq,
            event.ts,
            str(event.type),
            _event_name(event.data),
            _json_payload(event.data),
        )

    def write(self, event: Event) -> None:
        try:
            row = self._row(event)
            with session() as conn:
                conn.execute(_INSERT_SQL, row)
            _bump_seq(row[0], event.seq)
        except Exception as err:
            _warn(f"write(run={self.run_id})", err)

    def write_many(self, events: Iterable[Event]) -> None:
        """One transaction for a batch. Partial-failure granularity is the batch."""
        try:
            rows = [self._row(e) for e in events]
            if not rows:
                return
            with session() as conn:
                conn.executemany(_INSERT_SQL, rows)
            for run_id, seq, *_rest in rows:
                _bump_seq(run_id, seq)
        except Exception as err:
            _warn(f"write_many(run={self.run_id})", err)


def _iso_to_epoch(value: Any) -> float | None:
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).timestamp()
        except ValueError:
            return None
    return None


class SqliteTracingProcessor(_TracingProcessor):
    """SDK TracingProcessor that mirrors finished spans into agent_trace.

    Implements every abstract method of `agents.tracing.TracingProcessor` as of
    openai-agents 0.22.3: on_trace_start, on_trace_end, on_span_start,
    on_span_end, shutdown, force_flush. Writes are synchronous per callback, so
    force_flush is a no-op and shutdown just drops bookkeeping maps.
    """

    # --- run_id resolution -------------------------------------------------

    @staticmethod
    def _resolve_run_id(trace: Any) -> str | None:
        meta = getattr(trace, "metadata", None)
        if isinstance(meta, dict):
            bound = meta.get(RUN_ID_METADATA_KEY)
            if isinstance(bound, str) and bound:
                return bound
        with _lock:
            current = _current_run
        if current:
            return current
        trace_id = getattr(trace, "trace_id", None)
        if isinstance(trace_id, str) and trace_id and trace_id != "no-op":
            return trace_id
        return None

    def _run_id_for_span(self, span: Any) -> str | None:
        trace_id = getattr(span, "trace_id", None)
        with _lock:
            if isinstance(trace_id, str) and trace_id in _trace_runs:
                return _trace_runs[trace_id]
            return _current_run

    # --- TracingProcessor interface ----------------------------------------

    def on_trace_start(self, trace: Any) -> None:
        try:
            run_id = self._resolve_run_id(trace)
            trace_id = getattr(trace, "trace_id", None)
            if run_id and isinstance(trace_id, str):
                with _lock:
                    _trace_runs[trace_id] = run_id
        except Exception as err:
            _warn("on_trace_start", err)

    def on_trace_end(self, trace: Any) -> None:
        try:
            trace_id = getattr(trace, "trace_id", None)
            with _lock:
                if isinstance(trace_id, str):
                    _trace_runs.pop(trace_id, None)
        except Exception as err:
            _warn("on_trace_end", err)

    def on_span_start(self, span: Any) -> None:
        # Rows land in the DB on span *end* (started_at/ended_at/error only exist
        # once the span is complete). Nothing to do here.
        return None

    def on_span_end(self, span: Any) -> None:
        try:
            exported = span.export()
            if not isinstance(exported, dict):
                return  # NoOpSpan / tracing disabled
            run_id = self._run_id_for_span(span)
            if not run_id:
                return
            span_data = getattr(span, "span_data", None)
            span_type = getattr(span_data, "type", None) or "span"
            span_name = getattr(span_data, "name", None)
            name = f"{span_type}:{span_name}" if span_name else str(span_type)
            ts = _iso_to_epoch(exported.get("ended_at")) or time.time()
            with session() as conn:
                conn.execute(_INSERT_SQL, (run_id, _next_seq(run_id), ts, "span", name, _json_payload(exported)))
        except Exception as err:
            _warn("on_span_end", err)

    def shutdown(self) -> None:
        try:
            with _lock:
                _trace_runs.clear()
        except Exception as err:
            _warn("shutdown", err)

    def force_flush(self) -> None:
        # Writes are synchronous; there is no buffer to flush.
        return None


def install_tracing() -> SqliteTracingProcessor:
    """Register `SqliteTracingProcessor` as the SDK's only trace processor.

    Idempotent: a second call returns the already-installed processor without
    re-registering (openai-agents' `set_trace_processors` *replaces* the list,
    so passing a fresh instance twice would duplicate span rows). Replacing the
    list also drops the SDK's default OpenAI exporter — this app never uploads
    traces. Returns the installed processor.
    """
    global _installed_processor
    with _lock:
        if _installed_processor is not None:
            return _installed_processor
    try:
        import agents.tracing as at
    except ImportError as err:  # fail loudly: tracing was asked for but SDK missing
        raise RuntimeError("openai-agents SDK not installed; cannot install tracing") from err
    processor = SqliteTracingProcessor()
    with _lock:
        if _installed_processor is not None:  # lost the race; reuse the winner
            return _installed_processor
        at.set_trace_processors([processor])
        _installed_processor = processor
    return processor

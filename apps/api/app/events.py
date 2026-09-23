"""The one event envelope shared by the agent loop, the HTTP layer and the web client.

Everything the user sees during a run arrives as one of these, in `seq` order, over SSE.
Changing this shape breaks three slices at once; add a new `EventType` instead.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Literal

EventType = Literal[
    "status",       # human-readable progress line; data: {"message": str}
    "token",        # incremental assistant text; data: {"text": str}
    "tool_call",    # data: {"name": str, "args": dict, "call_id": str}
    "tool_result",  # data: {"name": str, "call_id": str, "ok": bool, "result": Any, "ms": float}
    "citation",     # data: {"doc_id": str, "source": str, "page": int | None, "snippet": str}
    "final",        # data: {"text": str, "payload": Any | None}
    "error",        # data: {"message": str, "recoverable": bool}
]


@dataclass(slots=True)
class Event:
    type: EventType
    run_id: str
    data: dict[str, Any] = field(default_factory=dict)
    seq: int = 0
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "run_id": self.run_id,
            "seq": self.seq,
            "ts": round(self.ts, 3),
            "data": self.data,
        }

    def to_sse(self) -> str:
        """SSE frame. `event:` carries the type so the client can switch on it without parsing."""
        body = json.dumps(self.to_dict(), ensure_ascii=False)
        return f"event: {self.type}\ndata: {body}\n\n"


class SequenceCounter:
    """Monotonic per-run sequence. The client uses it to detect gaps after a reconnect."""

    __slots__ = ("_n",)

    def __init__(self) -> None:
        self._n = 0

    def next(self) -> int:
        self._n += 1
        return self._n

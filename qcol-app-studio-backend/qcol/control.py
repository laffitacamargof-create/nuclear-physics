"""Cooperative cancellation primitives for long-running QCOL runs.

Cancellation is deliberately checked only at safe boundaries (between model
construction, optimizer evaluations, measurement groups, and reconstruction
steps).  It never mutates scientific artifacts or partially overwrites a
verified result.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Event, Lock
from typing import Any, Dict, Optional


class RunCancelled(RuntimeError):
    """Raised when a cooperative QCOL cancellation request is observed."""

    def __init__(self, message: str, *, location: Optional[str] = None) -> None:
        super().__init__(message)
        self.location = location


@dataclass
class CancellationToken:
    """Thread-safe cancellation token shared by API, optimizer, and runtime."""

    _event: Event = field(default_factory=Event, init=False, repr=False)
    _lock: Lock = field(default_factory=Lock, init=False, repr=False)
    _reason: str = field(default="user_requested", init=False)
    _requested_utc: Optional[str] = field(default=None, init=False)

    def cancel(self, reason: str = "user_requested") -> bool:
        """Request cancellation. Returns True only for the first request."""
        cleaned = str(reason).strip() or "user_requested"
        with self._lock:
            first = not self._event.is_set()
            if first:
                self._reason = cleaned
                self._requested_utc = datetime.now(timezone.utc).isoformat()
                self._event.set()
            return first

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    @property
    def reason(self) -> str:
        with self._lock:
            return self._reason

    @property
    def requested_utc(self) -> Optional[str]:
        with self._lock:
            return self._requested_utc

    def raise_if_cancelled(self, *, location: Optional[str] = None) -> None:
        if self.cancelled:
            suffix = f" at {location}" if location else ""
            raise RunCancelled(
                f"QCOL run cancelled{suffix}: {self.reason}",
                location=location,
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cancelled": self.cancelled,
            "reason": self.reason if self.cancelled else None,
            "requested_utc": self.requested_utc,
        }

from __future__ import annotations
from threading import RLock
from typing import Any

class InMemoryStateRepository:
    def __init__(self) -> None:
        self._runs: dict[str, Any] = {}
        self._comparisons: dict[str, Any] = {}
        self._lock = RLock()
    def put_run(self, run_id: str, value: Any) -> None:
        with self._lock: self._runs[str(run_id)] = value
    def get_run(self, run_id: str) -> Any | None:
        with self._lock: return self._runs.get(str(run_id))
    def list_runs(self) -> tuple[Any, ...]:
        with self._lock: return tuple(self._runs.values())
    def put_comparison(self, comparison_id: str, value: Any) -> None:
        with self._lock: self._comparisons[str(comparison_id)] = value
    def get_comparison(self, comparison_id: str) -> Any | None:
        with self._lock: return self._comparisons.get(str(comparison_id))
    def list_comparisons(self) -> tuple[Any, ...]:
        with self._lock: return tuple(self._comparisons.values())

__all__ = ["InMemoryStateRepository"]

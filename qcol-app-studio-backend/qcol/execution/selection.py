"""Explicit, context-local execution-adapter selection for post-freeze E1.

The frozen runtime continues to request its accepted default adapter.  E1 uses
this execution-seam context to select another registered adapter without
modifying the resolver, canonical IR, optimizer, orchestrator, or shared
scientific pipeline.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

_ACTIVE_EXECUTION_ADAPTER: ContextVar[str | None] = ContextVar(
    "qcol_active_execution_adapter",
    default=None,
)


def active_execution_adapter_id() -> str | None:
    value = _ACTIVE_EXECUTION_ADAPTER.get()
    return None if value is None else str(value)


@contextmanager
def use_execution_adapter(adapter_id: str) -> Iterator[None]:
    value = str(adapter_id).strip()
    if not value:
        raise ValueError("adapter_id must be non-empty.")
    token = _ACTIVE_EXECUTION_ADAPTER.set(value)
    try:
        yield
    finally:
        _ACTIVE_EXECUTION_ADAPTER.reset(token)


__all__ = ["active_execution_adapter_id", "use_execution_adapter"]

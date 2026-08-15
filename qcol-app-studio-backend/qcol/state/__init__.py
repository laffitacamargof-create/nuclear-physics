"""Replaceable state boundary; durable storage is intentionally deferred.

The pre-freeze architecture defines a small port and keeps the current
single-process implementation behind :class:`InMemoryStateRepository`.  A
future SQLite adapter can implement the same port without changing the shared
scientific pipeline.
"""
from __future__ import annotations

from typing import Any

from .ports import StateRepository
from .memory import InMemoryStateRepository


def public_state_boundary_contract() -> dict[str, Any]:
    return {
        "schema_version": "qcol-state-boundary-contract/1.0",
        "port_id": "StateRepository",
        "default_adapter_id": "state.in_memory.v1",
        "default_adapter_class": "InMemoryStateRepository",
        "capabilities": [
            "put_run",
            "get_run",
            "list_runs",
            "put_comparison",
            "get_comparison",
            "list_comparisons",
        ],
        "source_of_truth": "StateRepository port",
        "in_memory_adapter_is_implementation_detail": True,
        "sqlite_adapter_status": "deferred_after_unified_baseline_freeze",
        "pipeline_change_required_for_sqlite": False,
        "durable_state_claimed": False,
    }


__all__ = [
    "StateRepository",
    "InMemoryStateRepository",
    "public_state_boundary_contract",
]

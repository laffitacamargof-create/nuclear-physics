"""Compatibility projection over the single Step-2 plugin registry."""
from __future__ import annotations

from typing import Any

from ..plugin_registry import (
    PluginRegistryError,
    get_execution_plugin,
    list_execution_bindings,
)
from .descriptors import LOCAL_CIRQ_DESCRIPTOR
from .selection import active_execution_adapter_id


class ExecutionAdapterRegistryError(RuntimeError):
    def __init__(self, failure_code: str, message: str) -> None:
        super().__init__(message)
        self.failure_code = failure_code


def get_execution_adapter(adapter_id: str = "execution.local_cirq.v1"):
    selected_id = active_execution_adapter_id() or str(adapter_id)
    try:
        return get_execution_plugin(selected_id)
    except PluginRegistryError as exc:
        raise ExecutionAdapterRegistryError(
            "EXECUTION_ADAPTER_RECOGNIZED_NOT_EXECUTABLE",
            str(exc),
        ) from exc


def public_execution_adapter_catalog() -> dict[str, Any]:
    return {
        "schema_version": "qcol-execution-adapter-registry/1.0",
        "adapters": [row.to_public_dict() for row in list_execution_bindings()],
        "default_adapter_id": LOCAL_CIRQ_DESCRIPTOR.adapter_id,
        "provider_adapters_enabled": False,
        "accepted_local_adapter_ids": [
            row.descriptor.adapter_id
            for row in list_execution_bindings()
            if row.descriptor.execution_mode == "local_simulator"
        ],
        "context_local_selection_enabled": True,
        "silent_fallback_allowed": False,
    }


__all__ = [
    "ExecutionAdapterRegistryError",
    "get_execution_adapter",
    "public_execution_adapter_catalog",
]

"""Compatibility projection over the Step-2 TaskPlugin registry."""
from __future__ import annotations

from typing import Dict, Tuple

from .model_contracts import ModelContractError
from .plugin_registry import (
    canonical_task_plugin_id,
    get_task_plugin,
    list_task_plugins,
    public_plugin_registry,
)
from .task_contracts import TaskContract


def register_task_contract(contract: TaskContract) -> None:
    raise ModelContractError(
        "Register a complete TaskPlugin through qcol.plugin_registry; "
        "a bare TaskContract is not an executable extension seam."
    )


def canonical_task_id(task_id: str | None) -> str:
    try:
        return canonical_task_plugin_id(task_id)
    except Exception as exc:
        raise ModelContractError(str(exc)) from exc


def get_task_contract(task_id: str) -> TaskContract:
    try:
        return get_task_plugin(task_id).contract
    except Exception as exc:
        raise ModelContractError(str(exc)) from exc


def list_task_contracts() -> Tuple[TaskContract, ...]:
    return tuple(plugin.contract for plugin in list_task_plugins())


def public_task_registry() -> Dict[str, object]:
    catalog = public_plugin_registry()
    return {
        "schema_version": "qcol-task-registry/1.1-mapping-analysis",
        "tasks": [contract.to_dict() for contract in list_task_contracts()],
        "aliases": dict(catalog["task_aliases"]),
    }

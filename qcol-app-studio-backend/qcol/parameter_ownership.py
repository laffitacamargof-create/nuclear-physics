"""Parameter namespace ownership and UI projection contract."""
from __future__ import annotations

from typing import Any

from .model_registry import get_model_contract
from .task_registry import get_task_contract
from .execution import public_execution_request_contract


def public_parameter_ownership_catalog(model_id: str | None = None, task_id: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": "qcol-parameter-ownership-catalog/1.0",
        "namespaces": {
            "model_parameters": {
                "owner_id": "owner.model_contract",
                "meaning": "physical model parameters",
            },
            "variational_parameters": {
                "owner_id": "owner.ansatz_policy",
                "meaning": "theta schema, layer and sharing semantics",
            },
            "task_controller_parameters": {
                "owner_id": "owner.task_contract",
                "meaning": "task and controller inputs",
            },
            "execution_parameters": {
                "owner_id": "owner.execution_target",
                "meaning": "shots, seed, backend and execution mode",
                "contract": public_execution_request_contract(),
            },
        },
        "ui_role": "projection_only",
        "ui_may_rederive_parameter_semantics": False,
    }
    if model_id is not None:
        contract = get_model_contract(model_id)
        payload["model"] = {
            "model_id": model_id,
            "physical_parameter_schema": [row.to_dict() for row in contract.parameter_schema],
            "ansatz_policy_id": contract.ansatz_policy_id,
            "variational_parameter_schema_source": "AnsatzPolicy",
        }
    if task_id is not None:
        task = get_task_contract(task_id)
        payload["task"] = {
            "task_id": task_id,
            "task_controller_parameter_schema": [row.to_dict() for row in task.parameter_schema],
        }
    return payload


__all__ = ["public_parameter_ownership_catalog"]

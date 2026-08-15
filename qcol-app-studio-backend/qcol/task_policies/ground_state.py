"""Ground-state task verification and interpretation policies."""
from __future__ import annotations

from typing import Any, Mapping

from ..runtime import verify_reconstructed_result
from .common import runtime_context


def verify_ground_state_task(
    realization_or_artifact,
    outcome,
    request: Mapping[str, Any] | None = None,
    task_plan=None,
) -> Mapping[str, Any]:
    artifact, controls, plan = runtime_context(
        realization_or_artifact, request, task_plan
    )
    result = dict(verify_reconstructed_result(artifact, outcome.final_execution, controls))
    result.update({
        "task_id": plan.task_contract.task_id,
        "verification_metric": plan.task_contract.verification_metric,
        "controller_id": outcome.controller_id,
    })
    return result


def interpret_ground_state_task(
    realization_or_artifact,
    outcome,
    verification,
    request: Mapping[str, Any] | None = None,
    task_plan=None,
) -> Mapping[str, Any]:
    artifact, _controls, plan = runtime_context(
        realization_or_artifact, request, task_plan
    )
    limitations = list(artifact.scientific_context.get("limitations", []))
    return {
        "task_id": plan.task_contract.task_id,
        "scientific_quantity": artifact.scientific_context.get(
            "scientific_quantity", "ground-state energy"
        ),
        "supported_statement": artifact.scientific_context.get(
            "supported_statement",
            "The workflow reconstructs a bounded ground-state/sector-ground-state energy estimate for the declared model.",
        ),
        "unit": artifact.units.get("energy", "unspecified"),
        "result": {
            "energy": float(outcome.final_execution["energy"]),
            "standard_error": float(outcome.final_execution["standard_error"]),
            "sector_diagnostics": dict(
                outcome.final_execution.get("sector_diagnostics", {})
            ),
        },
        "verification_status": verification.get("status"),
        "limitations": limitations,
    }

"""Ground-state optimizer-loop controller over the canonical realization."""
from __future__ import annotations

from .base import ControllerOutcome
from ..optimizer import run_variational_runtime


def run_optimizer_loop_controller(
    realization,
    *,
    run_id: str,
    event_callback=None,
    cancellation_token=None,
) -> ControllerOutcome:
    payload = run_variational_runtime(
        realization,
        run_id=run_id,
        event_callback=event_callback,
        cancellation_token=cancellation_token,
    )
    final_execution = payload["final_execution"]
    return ControllerOutcome(
        controller_id=realization.controller_id,
        task_id=realization.task_id,
        run_mode=payload["run_mode"],
        final_execution=final_execution,
        task_result={
            "result_kind": "ground_state_energy",
            "energy": float(final_execution["energy"]),
            "standard_error": float(final_execution["standard_error"]),
        },
        parameter_source=str(payload["parameter_source"]),
        initial_parameters=[float(v) for v in payload["initial_parameters"]],
        final_parameters=[float(v) for v in payload["final_parameters"]],
        history=list(payload["history"]),
        controller_converged=bool(payload["optimizer_converged"]),
        controller_message=str(payload["optimizer_message"]),
        controller_evaluations=int(payload["optimizer_evaluations"]),
        controller_tolerance=float(payload["optimizer_tolerance"]),
        controller_name=payload["optimizer_name"],
        controller_diagnostics=dict(payload.get("scipy_result", {})),
    )

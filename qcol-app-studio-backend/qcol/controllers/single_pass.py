"""Single-pass controller proving that QCOL tasks are not all optimizer loops."""
from __future__ import annotations

from .base import ControllerOutcome
from ..observable_runtime import (
    execute_pair_occupation_observable,
    select_observable_parameters,
)


def run_single_pass_observable_controller(
    realization,
    *,
    run_id: str,
    event_callback=None,
    cancellation_token=None,
) -> ControllerOutcome:
    artifact = realization.problem_artifact
    task_plan = realization.task_plan
    controls = realization.run_controls
    task_parameters = dict(realization.task_instance.parameters)
    theta, source = select_observable_parameters(artifact, task_parameters)
    shots = int(controls.get("shots", 8192))
    seed = int(controls.get("seed", 42))

    observable = execute_pair_occupation_observable(
        realization,
        theta,
        shots=shots,
        seed=seed,
        run_id=run_id,
        event_callback=event_callback,
        cancellation_token=cancellation_token,
    )
    final_execution = {
        "translation_check": observable["translation_check"],
        "records": observable["records"],
        "term_expectations": {},
        "energy": None,
        "standard_error": None,
        "shots_per_group": int(shots),
    }
    history = [{
        "evaluation": 1,
        "role": "observable_single_pass",
        "theta": [float(v) for v in theta],
        "energy": None,
        "standard_error": None,
        "observable_summary": {
            "occupations": observable["occupations"],
            "sector_leakage": observable["sector_leakage"],
        },
        "seed": seed,
    }]
    return ControllerOutcome(
        controller_id=realization.controller_id,
        task_id=realization.task_id,
        run_mode="observable_single_pass",
        final_execution=final_execution,
        task_result=observable,
        parameter_source=source,
        initial_parameters=[float(v) for v in theta],
        final_parameters=[float(v) for v in theta],
        history=history,
        controller_converged=True,
        controller_message="Single-pass observable task completed.",
        controller_evaluations=1,
        controller_tolerance=0.0,
        controller_name=None,
        controller_diagnostics={
            "optimizer_applicable": False,
            "state_source": source,
            "acceptance_fixture_not_a_vqe_result": (
                source == "acceptance_fixture_exact_derived"
            ),
        },
    )

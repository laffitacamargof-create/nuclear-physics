"""Small inspectable policy declarations used by task resolution."""
from __future__ import annotations

from typing import Any, Mapping


def model_resolved_variational_state(model_plan, task_instance) -> Mapping[str, Any]:
    return {"circuit_family": "model_resolved_variational_state", "model_ansatz_policy": model_plan.policy_bindings.get("ansatz")}


def model_resolved_state_circuit(model_plan, task_instance) -> Mapping[str, Any]:
    return {"circuit_family": "model_resolved_state_circuit", "state_source": task_instance.parameters.get("state_source", "initial_parameters")}


def model_resolved_energy_measurement(model_plan, task_instance) -> Mapping[str, Any]:
    return {"measurement_family": "model_resolved_pauli_energy", "model_measurement_policy": model_plan.policy_bindings.get("measurement")}


def declared_observable_measurement(model_plan, task_instance) -> Mapping[str, Any]:
    return {"measurement_family": "declared_observable", "observables": list(task_instance.requested_observables)}


def energy_expectation_reconstruction(model_plan, task_instance) -> Mapping[str, Any]:
    return {"result_kind": "energy_expectation"}


def observable_expectation_reconstruction(model_plan, task_instance) -> Mapping[str, Any]:
    return {"result_kind": "observable_expectations", "observables": list(task_instance.requested_observables)}


def energy_delta_termination(model_plan, task_instance) -> Mapping[str, Any]:
    return {"termination": "optimizer_or_energy_delta", "tolerance": task_instance.parameters.get("optimizer_tolerance", 1e-3)}


def single_pass_termination(model_plan, task_instance) -> Mapping[str, Any]:
    return {"termination": "single_complete_pass"}


def model_ground_state_reference(model_plan, task_instance) -> Mapping[str, Any]:
    return {"reference_type": "model_ground_state_reference", "model_reference_policy": model_plan.policy_bindings.get("reference")}


def model_observable_reference(model_plan, task_instance) -> Mapping[str, Any]:
    return {"reference_type": "model_observable_reference", "observables": list(task_instance.requested_observables)}


def not_implemented_task_policy(*args, **kwargs):
    raise NotImplementedError("This task policy is registered for roadmap visibility but is not implemented.")


def runtime_context(realization_or_artifact, request=None, task_plan=None):
    """Return ``(ProblemArtifact, run_controls, task_plan)``.

    Canonical runtime calls pass only ``QuantumRealizationArtifact``.  The
    optional arguments preserve direct policy tests written before Step 2.
    """
    if hasattr(realization_or_artifact, "problem_artifact"):
        return (
            realization_or_artifact.problem_artifact,
            dict(realization_or_artifact.run_controls),
            realization_or_artifact.task_plan,
        )
    if task_plan is None:
        raise ValueError("Legacy task-policy invocation requires task_plan.")
    return realization_or_artifact, dict(request or {}), task_plan

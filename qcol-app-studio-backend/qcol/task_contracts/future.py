"""Registered future task contracts.  They are visible but not executable."""
from .base import TaskContract


def _future(task_id: str, label: str, family: str, objective: str, controller: str, reference: str) -> TaskContract:
    return TaskContract(
        task_id=task_id,
        task_version="0.1.0",
        label=label,
        description=f"Registered future QCOL task: {label}.",
        task_family=family,
        objective=objective,
        required_model_capabilities=("task_specific_quantum_realization",),
        required_model_observables=tuple(),
        parameter_schema=tuple(),
        controller_policy_id=controller,
        circuit_policy_id=f"{task_id}.circuit.future",
        measurement_policy_id=f"{task_id}.measurement.future",
        reconstruction_policy_id=f"{task_id}.reconstruction.future",
        termination_policy_id=f"{task_id}.termination.future",
        reference_policy_id=reference,
        verification_policy_id=f"{task_id}.verification.future",
        interpretation_policy_id=f"{task_id}.interpretation.future",
        reference_type="task-specific reference not implemented",
        verification_metric="task-specific metric not implemented",
        support_status="future",
        execution_status="planned",
        limitations=("No executable model × task cell is promoted in this release.",),
    )


EXCITED_STATE_TASK = _future(
    "excited_states",
    "Excited-state estimation",
    "iterative_excited_state",
    "Estimate selected excited-state energies under a declared deflation or orthogonality policy.",
    "excited_state_controller.future",
    "model_excited_state_reference.future",
)
TIME_EVOLUTION_TASK = _future(
    "time_evolution",
    "Time evolution",
    "time_stepper",
    "Propagate a declared initial state and reconstruct observables across time.",
    "time_stepper.future",
    "model_time_evolution_reference.future",
)
EIGENPHASE_TASK = _future(
    "eigenphase",
    "Eigenphase estimation",
    "single_or_staged_phase_estimation",
    "Estimate an eigenphase of a declared unitary with a compatible eigenstate preparation.",
    "eigenphase_controller.future",
    "model_eigenphase_reference.future",
)

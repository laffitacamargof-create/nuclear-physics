"""Ground-state/sector-ground-state energy task contract."""
from .base import TaskContract, TaskParameterSpec

GROUND_STATE_TASK = TaskContract(
    task_id="ground_state_energy",
    task_version="1.0.0",
    aliases=("sector_ground_state_energy",),
    label="Ground-state / sector-ground-state energy",
    description=(
        "Estimate the lowest energy in the declared model sector with an external "
        "variational optimizer and a model-provided state family."
    ),
    task_family="variational_energy",
    objective="Minimize the reconstructed Hamiltonian expectation value in the declared sector.",
    required_model_capabilities=(
        "hamiltonian",
        "target_sector_or_full_space",
        "initial_state",
        "parameterized_state_family",
        "energy_measurement",
        "reference_or_limited_verification",
    ),
    required_model_observables=("energy",),
    parameter_schema=(
        TaskParameterSpec("run_mode", "Run mode", "text", default="vqe", allowed_values=("vqe", "single_evaluation"), order=10),
        TaskParameterSpec("optimizer", "Optimizer", "text", default="COBYLA", allowed_values=("COBYLA",), order=20),
        TaskParameterSpec("max_evaluations", "Maximum evaluations", "integer", default=40, minimum=1, maximum=500, order=30),
        TaskParameterSpec("optimizer_tolerance", "Convergence tolerance", "number", default=1e-3, minimum=0.0, order=40),
    ),
    controller_policy_id="external_variational_energy.v1",
    circuit_policy_id="model_resolved_variational_state.v1",
    measurement_policy_id="model_resolved_energy_measurement.v1",
    reconstruction_policy_id="energy_expectation.v1",
    termination_policy_id="energy_delta_or_controller_stop.v1",
    reference_policy_id="model_ground_state_reference.v1",
    verification_policy_id="energy_error_with_uncertainty.v1",
    interpretation_policy_id="ground_state_bounded_meaning.v1",
    reference_type="model-specific ground-state or sector-ground-state reference",
    verification_metric="absolute energy error with shot uncertainty and structural checks",
    assumptions=("The selected model provides a compatible variational state family.",),
    limitations=("This task contract does not imply that VQE is appropriate for every model or every future QCOL task.",),
    support_status="acceptance_verified",
    execution_status="acceptance_verified",
    acceptance_suite_id="acceptance.task.ground_state_energy.v1",
)

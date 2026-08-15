"""Single-pass observable-estimation task contract."""
from .base import TaskContract, TaskParameterSpec

OBSERVABLE_TASK = TaskContract(
    task_id="observable_estimation",
    task_version="1.0.0",
    aliases=("observable",),
    label="Observable estimation",
    description=(
        "Prepare one declared state, execute a model-compatible measurement plan once, "
        "and reconstruct selected observables without an optimizer loop."
    ),
    task_family="single_pass_observable",
    objective="Estimate declared model observables for a specified prepared state.",
    required_model_capabilities=(
        "initial_state",
        "parameterized_or_fixed_state",
        "declared_observables",
        "observable_measurement",
        "observable_reference_for_acceptance",
    ),
    required_model_observables=tuple(),
    parameter_schema=(
        TaskParameterSpec(
            "state_source",
            "Prepared-state source",
            "text",
            default="acceptance_fixture",
            allowed_values=("acceptance_fixture", "initial_parameters", "explicit_parameters"),
            order=10,
            help_text=(
                "The acceptance fixture is exact-derived and is labelled acceptance-only; "
                "it is never presented as VQE convergence."
            ),
        ),
        TaskParameterSpec("parameter_values", "Explicit parameter values", "vector", default=tuple(), order=20),
        TaskParameterSpec("observable_ids", "Observable IDs", "vector", default=("pair_occupations",), order=30),
        TaskParameterSpec("observable_abs_floor", "Observable acceptance floor", "number", default=0.03, minimum=0.0, order=40),
        TaskParameterSpec("sector_leakage_floor", "Sector-leakage floor", "number", default=0.01, minimum=0.0, order=50),
    ),
    controller_policy_id="single_pass.observable.v1",
    circuit_policy_id="model_resolved_state_circuit.v1",
    measurement_policy_id="declared_observable_measurement.v1",
    reconstruction_policy_id="observable_expectation.v1",
    termination_policy_id="single_pass_complete.v1",
    reference_policy_id="model_observable_reference.v1",
    verification_policy_id="observable_error_with_uncertainty.v1",
    interpretation_policy_id="observable_bounded_meaning.v1",
    reference_type="model-specific observable reference for the declared prepared state",
    verification_metric="maximum observable error, shot uncertainty, and sector leakage",
    assumptions=("Only observables declared by the selected ModelContract may be requested.",),
    limitations=("The verified first cell is one-pair pair-occupation estimation using an acceptance fixture.",),
    support_status="execution_ready",
    execution_status="execution_ready",
    acceptance_suite_id="acceptance.task.observable_estimation.v1",
)

"""Built-in task-policy declarations."""
from __future__ import annotations

from .task_policy_registries import TASK_REGISTRIES

_REGISTERED = False


def _declare(kind: str, policy_id: str, import_path: str, description: str, *, status: str = "implemented") -> None:
    registry = TASK_REGISTRIES[kind]
    if not registry.has(policy_id):
        registry.declare(
            policy_id,
            import_path,
            description,
            implementation_status=status,
            provenance={"source": "QCOL task architecture"},
        )


def register_builtin_task_policies() -> None:
    global _REGISTERED
    if _REGISTERED:
        return

    _declare("controller", "external_variational_energy.v1", "qcol.controllers.optimizer_loop:run_optimizer_loop_controller", "External COBYLA optimizer loop over the shared energy evaluator.")
    _declare("controller", "single_pass.observable.v1", "qcol.controllers.single_pass:run_single_pass_observable_controller", "Single-pass observable controller without an optimizer loop.")
    _declare("controller", "single_pass.mapping_analysis.v1", "qcol.controllers.mapping_analysis:run_mapping_analysis_controller", "Deterministic one-pass JW/BK transformation and resource comparison controller.")

    _declare("circuit", "model_resolved_variational_state.v1", "qcol.task_policies.common:model_resolved_variational_state", "Use the model-resolved initial state and variational circuit family.")
    _declare("circuit", "model_resolved_state_circuit.v1", "qcol.task_policies.common:model_resolved_state_circuit", "Use one model-resolved state circuit for a single-pass task.")
    _declare("circuit", "mapping_analysis.no_circuit.v1", "qcol.task_policies.mapping_analysis:no_circuit_declaration", "Mapping analysis uses operator artifacts and no quantum circuit.")
    _declare("measurement", "model_resolved_energy_measurement.v1", "qcol.task_policies.common:model_resolved_energy_measurement", "Use the model-resolved Pauli energy measurement plan.")
    _declare("measurement", "declared_observable_measurement.v1", "qcol.task_policies.common:declared_observable_measurement", "Build measurements only for observables declared by the model contract.")
    _declare("measurement", "mapping_analysis.no_measurement.v1", "qcol.task_policies.mapping_analysis:no_measurement_declaration", "Mapping analysis requires no measurement circuits or shots.")
    _declare("reconstruction", "energy_expectation.v1", "qcol.task_policies.common:energy_expectation_reconstruction", "Reconstruct the Hamiltonian expectation from measured Pauli terms.")
    _declare("reconstruction", "observable_expectation.v1", "qcol.task_policies.common:observable_expectation_reconstruction", "Reconstruct declared observable expectations and uncertainties.")
    _declare("reconstruction", "mapping_comparison_report.v1", "qcol.task_policies.mapping_analysis:mapping_comparison_reconstruction", "Build a MappingComparisonReport from semantic checks and operator resources.")
    _declare("termination", "energy_delta_or_controller_stop.v1", "qcol.task_policies.common:energy_delta_termination", "Stop under the controller's declared energy/convergence rule.")
    _declare("termination", "single_pass_complete.v1", "qcol.task_policies.common:single_pass_termination", "Stop after one complete prepared-state measurement pass.")
    _declare("termination", "mapping_analysis_complete.v1", "qcol.task_policies.mapping_analysis:mapping_analysis_termination", "Stop after every requested mapping plugin is analyzed exactly once.")
    _declare("reference", "model_ground_state_reference.v1", "qcol.task_policies.common:model_ground_state_reference", "Use the model plugin's ground-state/sector reference within its validity envelope.")
    _declare("reference", "model_observable_reference.v1", "qcol.task_policies.common:model_observable_reference", "Use model-specific observable expectations for the declared prepared state.")
    _declare("reference", "fermionic_fock_space_spectrum.v1", "qcol.task_policies.mapping_analysis:fermionic_fock_space_reference", "Use exact full and fixed-particle Fermionic Fock-space spectra for bounded mapping acceptance.")
    _declare("verification", "energy_error_with_uncertainty.v1", "qcol.task_policies.ground_state:verify_ground_state_task", "Energy/reference comparison with structural checks and shot uncertainty.")
    _declare("verification", "observable_error_with_uncertainty.v1", "qcol.task_policies.observable:verify_observable_task", "Observable/reference comparison with shot uncertainty and sector leakage.")
    _declare("verification", "mapping_equivalence_and_resources.v1", "qcol.task_policies.mapping_analysis:verify_mapping_analysis_task", "Verify JW/BK spectra, fixed-particle sectors, particle-number operators, Hermiticity, and analysis-only support boundaries.")
    _declare("interpretation", "ground_state_bounded_meaning.v1", "qcol.task_policies.ground_state:interpret_ground_state_task", "Return a bounded model-specific ground-state statement.")
    _declare("interpretation", "observable_bounded_meaning.v1", "qcol.task_policies.observable:interpret_observable_task", "Return bounded observable meaning with source labels and limitations.")
    _declare("interpretation", "mapping_analysis_bounded_meaning.v1", "qcol.task_policies.mapping_analysis:interpret_mapping_analysis_task", "Return bounded transformation/resource meaning without a VQE claim.")

    # Future columns are registered honestly but cannot resolve to execution.
    future_ids = {
        "excited_state_controller.future": "controller",
        "time_stepper.future": "controller",
        "eigenphase_controller.future": "controller",
    }
    for policy_id, kind in future_ids.items():
        _declare(kind, policy_id, "qcol.task_policies.common:not_implemented_task_policy", "Registered future task policy.", status="not_implemented")
    for task_id in ("excited_states", "time_evolution", "eigenphase"):
        for suffix, kind in (
            ("circuit.future", "circuit"),
            ("measurement.future", "measurement"),
            ("reconstruction.future", "reconstruction"),
            ("termination.future", "termination"),
            ("verification.future", "verification"),
            ("interpretation.future", "interpretation"),
        ):
            _declare(kind, f"{task_id}.{suffix}", "qcol.task_policies.common:not_implemented_task_policy", "Registered future task policy.", status="not_implemented")
    for policy_id in (
        "model_excited_state_reference.future",
        "model_time_evolution_reference.future",
        "model_eigenphase_reference.future",
    ):
        _declare("reference", policy_id, "qcol.task_policies.common:not_implemented_task_policy", "Registered future reference policy.", status="not_implemented")

    _REGISTERED = True

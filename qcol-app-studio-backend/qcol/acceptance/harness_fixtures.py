"""WP7 tolerance profiles, gate suites, and frozen-baseline classifications."""
from __future__ import annotations

from dataclasses import replace
from typing import Any

from qcol.mapping_policies import CheckStatus, GateApplicability

from .fingerprint import (
    AcceptanceEvidenceFingerprint,
    BindingEvidenceIdentity,
    DeclaredScaleContract,
    DependencyFingerprint,
    component_identity,
)
from .fingerprint_fixtures import WP6_DEPENDENCIES, build_wp6_valid_fingerprint
from .harness import (
    AcceptanceGateContract,
    AcceptanceGateKind,
    AcceptanceHarnessCase,
    AcceptanceObservation,
    GenericThreeGateAcceptanceHarness,
    ObservationComparison,
    ToleranceProfileRegistry,
)
from .mapping_baseline import public_mapping_realization_baseline
from .tolerance_profiles import ToleranceProfile


def build_wp7_tolerance_registry() -> ToleranceProfileRegistry:
    registry = ToleranceProfileRegistry(
        registry_id="qcol.wp7.tolerance-profiles.v1",
        registry_version="1.0.0",
    )
    common = dict(
        algebra_operator_norm=1e-10,
        basis_overlap=1e-12,
        matrix_relative_frobenius=1e-10,
        eigenvalue_absolute=1e-9,
        generator_unitary=1e-9,
        sector_leakage=1e-10,
        qasm_semantic=1e-8,
        statistical_sigma_multiplier=3.0,
        absolute_numerical_floor=2e-2,
        minimum_sampled_seeds=3,
        minimum_random_parameter_points=20,
        units_policy="task_declared_units",
    )
    profiles = (
        ToleranceProfile(
            profile_id="wp7.tolerance.mapper.small.v1",
            profile_version="1.0.0",
            label="WP7 small mapper-conformance profile",
            scope_statement="2–6 modes or a complete declared restricted sector.",
            notes=("Matrix/operator-action checks precede any task-level energy.",),
            **common,
        ),
        ToleranceProfile(
            profile_id="wp7.tolerance.composition.small.v1",
            profile_version="1.0.0",
            label="WP7 small composition-conformance profile",
            scope_statement="At least 20 deterministic nonzero parameter points with explicit nonadjacent parity cases.",
            notes=("No Hamming-weight-only claim is promoted to mapped fermionic semantics.",),
            **common,
        ),
        ToleranceProfile(
            profile_id="wp7.tolerance.cell.sampled-small.v1",
            profile_version="1.0.0",
            label="WP7 sampled small-cell acceptance profile",
            scope_statement="At least three sampled seeds with task-specific numerical floor and statistical consistency.",
            notes=("Controller, reference, uncertainty, evidence, and bounded meaning are separate checks.",),
            **common,
        ),
        ToleranceProfile(
            profile_id="wp7.tolerance.analysis.deterministic.v1",
            profile_version="1.0.0",
            label="WP7 deterministic mapping-analysis cell profile",
            scope_statement="Deterministic mapper comparison; no state, ansatz, shots, QASM, optimizer, simulator, or hardware.",
            notes=("Composition gate is NOT_APPLICABLE, never a synthetic PASS.",),
            **common,
        ),
    )
    for profile in profiles:
        registry.register(profile)
    return registry


def build_wp7_execution_gate_contracts() -> dict[AcceptanceGateKind, AcceptanceGateContract]:
    return {
        AcceptanceGateKind.MAPPER_CONFORMANCE: AcceptanceGateContract(
            gate_id="wp7.gate.mapper-conformance.v1",
            gate_version="1.0.0",
            kind=AcceptanceGateKind.MAPPER_CONFORMANCE,
            label="Mapper conformance",
            tolerance_profile_id="wp7.tolerance.mapper.small.v1",
            required_check_ids=(
                "schema_provenance",
                "declared_algebra_conformance",
                "basis_encoding",
                "hamiltonian_matrix_equivalence",
                "task_observable_matrix_equivalence",
                "sector_semantics",
                "negative_domain_tests",
            ),
            purpose="Establish the encoding and operator transform before any composition or task-level energy claim.",
        ),
        AcceptanceGateKind.COMPOSITION_CONFORMANCE: AcceptanceGateContract(
            gate_id="wp7.gate.composition-conformance.v1",
            gate_version="1.0.0",
            kind=AcceptanceGateKind.COMPOSITION_CONFORMANCE,
            label="Composition conformance",
            tolerance_profile_id="wp7.tolerance.composition.small.v1",
            required_check_ids=(
                "initial_state_encoding",
                "mapped_generator_unitary_equivalence",
                "nonadjacent_sign",
                "random_theta_sector_leakage",
                "random_theta_point_count",
                "mode_ordering_consistency",
                "qasm_semantic_equivalence",
            ),
            purpose="Establish that state, ansatz, ordering, sector, and translated circuit implement the declared mapping semantics.",
        ),
        AcceptanceGateKind.CELL_ACCEPTANCE: AcceptanceGateContract(
            gate_id="wp7.gate.cell-acceptance.v1",
            gate_version="1.0.0",
            kind=AcceptanceGateKind.CELL_ACCEPTANCE,
            label="Model × Task cell acceptance",
            tolerance_profile_id="wp7.tolerance.cell.sampled-small.v1",
            required_check_ids=(
                "deterministic_reachable_fixture",
                "sampled_seed_count",
                "controller_behavior",
                "reference_uncertainty_consistency",
                "evidence_reproducibility",
                "bounded_meaning",
            ),
            purpose="Establish the complete controller, execution, reference, uncertainty, evidence, and bounded-meaning claim at the declared scale.",
        ),
    }


def build_wp7_analysis_gate_contracts() -> dict[AcceptanceGateKind, AcceptanceGateContract]:
    contracts = build_wp7_execution_gate_contracts()
    contracts[AcceptanceGateKind.CELL_ACCEPTANCE] = AcceptanceGateContract(
        gate_id="wp7.gate.analysis-cell-acceptance.v1",
        gate_version="1.0.0",
        kind=AcceptanceGateKind.CELL_ACCEPTANCE,
        label="Mapping-analysis cell acceptance",
        tolerance_profile_id="wp7.tolerance.analysis.deterministic.v1",
        required_check_ids=(
            "mapping_comparison_fixture",
            "full_and_sector_reference_equivalence",
            "resource_report_complete",
            "evidence_reproducibility",
            "bounded_meaning",
        ),
        purpose="Accept deterministic mapping transformation/resource analysis without inventing a circuit-execution claim.",
    )
    return contracts


def _obs(
    check_id: str,
    *,
    observed: Any = True,
    comparison: ObservationComparison = ObservationComparison.BOOLEAN_TRUE,
    tolerance_field: str | None = None,
    expected: Any = None,
    standard_error: float | None = None,
    declared_status: CheckStatus | None = None,
    failure_code: str | None = None,
    evidence: dict[str, Any] | None = None,
) -> AcceptanceObservation:
    code = failure_code or f"{check_id.upper()}.FAILED"
    return AcceptanceObservation(
        check_id=check_id,
        label=check_id.replace("_", " ").title(),
        comparison=comparison,
        observed=observed,
        tolerance_field=tolerance_field,
        expected=expected,
        standard_error=standard_error,
        declared_status=declared_status,
        failure_code=code,
        message_on_pass=f"{check_id} passed under the declared tolerance profile.",
        message_on_failure=f"{check_id} did not satisfy the declared gate requirement.",
        evidence=evidence or {},
    )


def _mapper_pass() -> tuple[AcceptanceObservation, ...]:
    return (
        _obs("schema_provenance"),
        _obs("declared_algebra_conformance"),
        _obs("basis_encoding"),
        _obs("hamiltonian_matrix_equivalence", observed=1e-12, comparison=ObservationComparison.LESS_EQUAL_TOLERANCE, tolerance_field="matrix_relative_frobenius"),
        _obs("task_observable_matrix_equivalence", observed=1e-12, comparison=ObservationComparison.LESS_EQUAL_TOLERANCE, tolerance_field="matrix_relative_frobenius"),
        _obs("sector_semantics"),
        _obs("negative_domain_tests"),
    )


def _composition_pass() -> tuple[AcceptanceObservation, ...]:
    return (
        _obs("initial_state_encoding"),
        _obs("mapped_generator_unitary_equivalence", observed=1e-11, comparison=ObservationComparison.LESS_EQUAL_TOLERANCE, tolerance_field="generator_unitary"),
        _obs("nonadjacent_sign"),
        _obs("random_theta_sector_leakage", observed=0.0, comparison=ObservationComparison.LESS_EQUAL_TOLERANCE, tolerance_field="sector_leakage"),
        _obs("random_theta_point_count", observed=20, comparison=ObservationComparison.GREATER_EQUAL_TOLERANCE, tolerance_field="minimum_random_parameter_points"),
        _obs("mode_ordering_consistency"),
        _obs("qasm_semantic_equivalence", observed=1e-10, comparison=ObservationComparison.LESS_EQUAL_TOLERANCE, tolerance_field="qasm_semantic"),
    )


def _cell_pass() -> tuple[AcceptanceObservation, ...]:
    return (
        _obs("deterministic_reachable_fixture"),
        _obs("sampled_seed_count", observed=3, comparison=ObservationComparison.GREATER_EQUAL_TOLERANCE, tolerance_field="minimum_sampled_seeds"),
        _obs("controller_behavior"),
        _obs("reference_uncertainty_consistency", observed=0.01, comparison=ObservationComparison.STATISTICAL_CONSISTENCY, standard_error=0.004),
        _obs("evidence_reproducibility"),
        _obs("bounded_meaning"),
    )


def _analysis_cell_pass() -> tuple[AcceptanceObservation, ...]:
    return (
        _obs("mapping_comparison_fixture"),
        _obs("full_and_sector_reference_equivalence", observed=1e-12, comparison=ObservationComparison.LESS_EQUAL_TOLERANCE, tolerance_field="eigenvalue_absolute"),
        _obs("resource_report_complete"),
        _obs("evidence_reproducibility"),
        _obs("bounded_meaning"),
    )


def _baseline_component(role: str, component_id: str, payload: dict[str, Any], *, applicability: str = "required"):
    return component_identity(
        role=role,
        component_id=component_id,
        component_version="1.0.0",
        snapshot=payload,
        applicability=applicability,
    )


def build_baseline_variant_fingerprint(row: dict[str, Any]) -> AcceptanceEvidenceFingerprint:
    base = build_wp6_valid_fingerprint()
    variant_id = row["variant_id"]
    mapping_id = row["mapping_id"]
    task_id = row["task_id"]
    analysis = task_id == "mapping_analysis"
    mapping_convention = (
        "qcol.pair.seniority-zero.v1"
        if mapping_id == "pair_mapping"
        else "openfermion.jw.little_endian.v1"
        if mapping_id == "jordan_wigner.v1"
        else "openfermion.bk.fenwick.v1"
    )
    scale = (
        {"n_levels": 4, "n_pairs": 1, "task": task_id, "mapping": mapping_id}
        if "one_pair" in variant_id
        else {"n_levels": 4, "n_pairs": 2, "task": task_id, "mapping": mapping_id}
        if "multi_pair" in variant_id
        else {"n_modes": 4, "n_particles": 2, "task": task_id, "mapping": mapping_id}
    )
    not_applicable = _baseline_component("not_applicable", "not_applicable", {"applicability": "not_applicable"}, applicability="not_applicable")
    state = not_applicable if analysis else _baseline_component("state_preparation_policy", f"{variant_id}.state.v1", {"variant_id": variant_id, "role": "state"})
    ansatz = not_applicable if analysis else _baseline_component("ansatz_policy", f"{variant_id}.ansatz.v1", {"variant_id": variant_id, "role": "ansatz"})
    measurement = not_applicable if analysis else _baseline_component("measurement_policy", f"{variant_id}.measurement.v1", {"variant_id": variant_id, "role": "measurement"})
    binding = BindingEvidenceIdentity(
        role="mapping.operator_transform",
        binding_id=f"{mapping_id}.binding.v1",
        binding_version="1.0.0",
        provider="qcol" if mapping_id == "pair_mapping" else "openfermion",
        implementation_version="baseline-frozen",
        convention_id=mapping_convention,
        source_revision="wp0-baseline-anchor",
    )
    return replace(
        base,
        fingerprint_id=f"wp7.fingerprint.{variant_id}",
        source_problem_fingerprint=f"source-{variant_id}",
        model_contract=_baseline_component("model_contract", row["model_id"], row),
        task_contract=_baseline_component("task_contract", task_id, {"task_id": task_id, "baseline_variant": variant_id}),
        mapping_policy=component_identity(
            role="mapping_policy",
            component_id=row.get("planned_policy_id") or mapping_id,
            component_version="1.0.0",
            snapshot={"mapping_id": mapping_id, "scope": row["mapping_scope"], "baseline_variant": variant_id},
            convention_id=mapping_convention,
        ),
        mode_ordering=_baseline_component("mode_ordering", f"{variant_id}.ordering.v1", {"variant_id": variant_id, "ordering": "frozen"}),
        encoding_context=component_identity(
            role="encoding_context",
            component_id=f"{variant_id}.encoding-context.v1",
            component_version="1.0.0",
            snapshot={"variant_id": variant_id, "mapping_convention": mapping_convention},
            convention_id=mapping_convention,
        ),
        sector_profiles=(
            _baseline_component("sector_profile.primary", f"{variant_id}.sector.v1", {"variant_id": variant_id, "mapping": mapping_id}),
        ),
        state_preparation_policy=state,
        ansatz_policy=ansatz,
        measurement_policy=measurement,
        reference_policy=_baseline_component("reference_policy", f"{variant_id}.reference.v1", {"variant_id": variant_id, "independent": True}),
        verification_policy=_baseline_component("verification_policy", f"{variant_id}.verification.v1", {"variant_id": variant_id, "gates": ["mapper", "composition", "cell"]}),
        tolerance_profile=_baseline_component("tolerance_profile", "wp7.tolerance.analysis.deterministic.v1" if analysis else "wp7.tolerance.cell.sampled-small.v1", {"variant_id": variant_id, "profile": "versioned"}),
        implementation_bindings=(binding,),
        dependencies=DependencyFingerprint(
            dependency_set_id="wp7.baseline-dependencies.v1",
            dependency_set_version="1.0.0",
            versions=WP6_DEPENDENCIES,
        ),
        declared_scale=DeclaredScaleContract(
            scale_id=f"wp7.scale.{variant_id}",
            scale_version="1.0.0",
            dimensions=scale,
            scope_statement="Frozen baseline classification scale; no scientific status is changed by WP7.",
        ),
    )


def build_wp7_cases() -> dict[str, AcceptanceHarnessCase]:
    rows = {row["variant_id"]: row for row in public_mapping_realization_baseline()["variants"]}
    cases: dict[str, AcceptanceHarnessCase] = {}
    for variant_id, row in rows.items():
        fingerprint = build_baseline_variant_fingerprint(row)
        analysis = row["task_id"] == "mapping_analysis"
        applicability = {
            AcceptanceGateKind.MAPPER_CONFORMANCE.value: GateApplicability.REQUIRED.value,
            AcceptanceGateKind.COMPOSITION_CONFORMANCE.value: (
                GateApplicability.NOT_APPLICABLE.value if analysis else GateApplicability.REQUIRED.value
            ),
            AcceptanceGateKind.CELL_ACCEPTANCE.value: GateApplicability.REQUIRED.value,
        }
        observations: dict[str, tuple[AcceptanceObservation, ...]] = {
            AcceptanceGateKind.MAPPER_CONFORMANCE.value: _mapper_pass(),
            AcceptanceGateKind.COMPOSITION_CONFORMANCE.value: _composition_pass(),
            AcceptanceGateKind.CELL_ACCEPTANCE.value: _analysis_cell_pass() if analysis else _cell_pass(),
        }
        observed_fingerprint: AcceptanceEvidenceFingerprint | None = fingerprint

        if variant_id == "baseline.pair.multi_pair.ground_state.v1":
            composition = list(_composition_pass())
            composition[1] = _obs(
                "mapped_generator_unitary_equivalence",
                observed="acceptance_pending",
                comparison=ObservationComparison.DECLARED_STATUS,
                declared_status=CheckStatus.REVIEW,
                failure_code="MULTI_PAIR_COMPOSITION_ACCEPTANCE_PENDING",
            )
            cell = list(_cell_pass())
            cell[2] = _obs(
                "controller_behavior",
                observed="experimental",
                comparison=ObservationComparison.DECLARED_STATUS,
                declared_status=CheckStatus.REVIEW,
                failure_code="MULTI_PAIR_CELL_ACCEPTANCE_PENDING",
            )
            observations[AcceptanceGateKind.COMPOSITION_CONFORMANCE.value] = tuple(composition)
            observations[AcceptanceGateKind.CELL_ACCEPTANCE.value] = tuple(cell)
        elif variant_id == "baseline.jw.general_ground_state.current_composition.v1":
            composition = list(_composition_pass())
            composition[1] = _obs(
                "mapped_generator_unitary_equivalence",
                observed=0.086194444997687,
                comparison=ObservationComparison.LESS_EQUAL_TOLERANCE,
                tolerance_field="generator_unitary",
                failure_code="ANSATZ_GENERATOR_MAPPING_MISMATCH",
                evidence={
                    "particle_number_preserved": True,
                    "sector_leakage": 0.0,
                    "nonadjacent_fermionic_sign_correct": False,
                },
            )
            composition[2] = _obs(
                "nonadjacent_sign",
                observed=False,
                failure_code="ANSATZ_GENERATOR_MAPPING_MISMATCH",
            )
            observations[AcceptanceGateKind.COMPOSITION_CONFORMANCE.value] = tuple(composition)
            observations[AcceptanceGateKind.CELL_ACCEPTANCE.value] = _cell_pass()
        elif variant_id == "baseline.bk.general_ground_state.v1":
            composition = list(_composition_pass())
            composition[0] = _obs(
                "initial_state_encoding",
                observed="unresolved",
                comparison=ObservationComparison.DECLARED_STATUS,
                declared_status=CheckStatus.BLOCKED,
                failure_code="BK_GROUND_STATE_COMPOSITION_UNRESOLVED",
                evidence={"raw_popcount_is_particle_number": False},
            )
            observations[AcceptanceGateKind.COMPOSITION_CONFORMANCE.value] = tuple(composition)
            observed_fingerprint = None

        cases[variant_id] = AcceptanceHarnessCase(
            case_id=f"wp7.case.{variant_id}",
            case_version="1.0.0",
            label=f"WP7 classification for {variant_id}",
            baseline_variant_id=variant_id,
            expected_baseline_status=row["cell_acceptance"],
            gate_applicability=applicability,
            observations=observations,
            expected_fingerprint=fingerprint,
            observed_fingerprint=observed_fingerprint,
            metadata={
                "mapper_baseline": row["mapper_conformance"],
                "composition_baseline": row["composition_conformance"],
                "cell_baseline": row["cell_acceptance"],
                "scientific_behavior_change": False,
            },
        )
    return cases


def run_wp7_baseline_classifications() -> dict[str, Any]:
    tolerance_registry = build_wp7_tolerance_registry()
    cases = build_wp7_cases()
    reports = {}
    for variant_id, case in cases.items():
        gate_contracts = (
            build_wp7_analysis_gate_contracts()
            if case.gate_applicability[AcceptanceGateKind.COMPOSITION_CONFORMANCE.value] == GateApplicability.NOT_APPLICABLE.value
            else build_wp7_execution_gate_contracts()
        )
        harness = GenericThreeGateAcceptanceHarness(
            gate_contracts=gate_contracts,
            tolerance_registry=tolerance_registry,
        )
        reports[variant_id] = harness.run(case)
    return {
        "tolerance_registry": tolerance_registry,
        "cases": cases,
        "reports": reports,
    }


__all__ = [
    "build_wp7_tolerance_registry",
    "build_wp7_execution_gate_contracts",
    "build_wp7_analysis_gate_contracts",
    "build_baseline_variant_fingerprint",
    "build_wp7_cases",
    "run_wp7_baseline_classifications",
]

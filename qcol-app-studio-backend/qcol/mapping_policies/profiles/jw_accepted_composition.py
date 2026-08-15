"""WP11 first accepted Jordan--Wigner ground-state composition.

This module records the deliberate scientific change introduced after the
A.3.2a foundation and A.3.2b migrations: the production endpoint-only qubit
exchange is replaced by a mapping-aware fermionic-swap-network ansatz.  The
WP0/WP9 negative fixture remains archived and executable only as a regression.
"""
from __future__ import annotations

from functools import lru_cache
import hashlib
import json
from typing import Any, Mapping

from qcol.acceptance.fingerprint import (
    AcceptanceEvidenceFingerprint,
    AcceptanceEvidenceRecord,
    BindingEvidenceIdentity,
    DeclaredScaleContract,
    DependencyFingerprint,
    component_identity,
)
from qcol.acceptance.tolerance_profiles import ToleranceProfile
from qcol.implementation_bindings import (
    BindingKind,
    ImplementationBindingContract,
    ImplementationBindingRegistry,
)
from qcol.mapping_policies import AnsatzSemanticClass, PolicyStatus
from qcol.realization_policies import AnsatzPolicyContract, VerificationPolicyContract
from qcol.realization_policies.base import contract_fingerprint
from qcol.models.general_spin_orbital.contract import GENERAL_SPIN_ORBITAL_MODEL_CONTRACT
from qcol.task_registry import get_task_contract

from .spin_orbital_migrations import (
    JW_CONVENTION_ID,
    JW_POLICY_ID,
    build_jw_encoding_context,
    build_jw_mapping_policy,
    jw_policy_contracts,
    public_a3_2b_exit_decision,
    spin_orbital_mapping_migration_catalog_fingerprint,
)
from .pair_mapping import pair_mapping_migration_catalog_fingerprint


WP11_PROJECT_VERSION = "1.19.0"
WP11_COMPOSITION_SCHEMA_VERSION = "qcol-wp11-jw-accepted-composition/1.0"
WP11_CATALOG_SCHEMA_VERSION = "qcol-wp11-jw-accepted-composition-catalog/1.0"
WP11_CATALOG_VERSION = "1.0.0"
WP11_ANSATZ_POLICY_ID = "jw.ansatz.mapped_fermionic_swap_network.v1"
WP11_ANSATZ_BINDING_ID = "jw.binding.ansatz.mapped_fermionic_swap_network.v1"
WP11_TOLERANCE_PROFILE_ID = "wp11.tolerance.jw.accepted_composition.v1"
WP11_VARIANT_ID = "realization.general_spin_orbital.ground_state.jw.wp11.v1"
WP11_ACCEPTANCE_SUITE_ID = "acceptance.cell.general_spin_orbital.jw_ground_state.wp11.v1"
WP11_PROMOTION_RECORD_ID = "promotion.general_spin_orbital.ground_state.jw.wp11.v1"


def build_wp11_ansatz_policy() -> AnsatzPolicyContract:
    return AnsatzPolicyContract(
        policy_id=WP11_ANSATZ_POLICY_ID,
        policy_version="1.0.0",
        display_name="JW mapped-fermionic single-excitation swap-network ansatz",
        implementation_binding_id=WP11_ANSATZ_BINDING_ID,
        semantic_class=AnsatzSemanticClass.MAPPED_FERMIONIC_GENERATOR,
        generator_domain="fermionic_single_excitations_plus_diagonal_number_generators",
        provided_capabilities=(
            "mapped_generator_semantics",
            "particle_number_preserving",
            "mode_order_aware",
            "nonadjacent_fermionic_signs",
            "qasm2_exportable_after_binding",
        ),
        required_mapping_capabilities=(
            "direct_occupation_encoding",
            "mapped_fermionic_operator_semantics",
            "car_preservation",
        ),
        required_sector_capabilities=("particle_number_direct_popcount",),
        preserved_quantities=("particle_number", "fermion_parity"),
        required_equivalence_evidence=(
            "adjacent_generator_unitary_equivalence",
            "nonadjacent_even_parity_unitary_equivalence",
            "nonadjacent_odd_parity_unitary_equivalence",
            "random_nonzero_theta_sector_preservation",
            "qasm_semantic_equivalence",
        ),
        parameterization_policy_id="fermion.binding.identity_parameter_vector.v1",
        support_status=PolicyStatus.ACCEPTANCE_VERIFIED,
        validity_envelope={
            "n_modes": {"minimum": 2, "maximum": 4},
            "particle_number": "1 <= N < n_modes",
            "ansatz_layers": {"minimum": 1, "maximum": 2},
            "particle_species_count": 1,
            "mapping_policy_id": JW_POLICY_ID,
            "mapping_convention_id": JW_CONVENTION_ID,
        },
        limitations=(
            "Acceptance is bounded to the declared 2–4-mode fixed-particle, single-species cell.",
            "This is not a universality claim for arbitrary strongly correlated fermionic systems.",
            "The archived endpoint-only exchange remains rejected and is not silently upgraded.",
        ),
        provenance={
            "phase": "A.3.2c",
            "work_package": "WP11",
            "implementation_strategy": "fermionic_swap_network",
            "replaces_production_policy": "jw.ansatz.current_bare_qubit_exchange.v1",
            "historical_failure_code": "ANSATZ_GENERATOR_MAPPING_MISMATCH",
            "scientific_behavior_change": True,
        },
    )


def build_wp11_tolerance_profile() -> ToleranceProfile:
    return ToleranceProfile(
        profile_id=WP11_TOLERANCE_PROFILE_ID,
        profile_version="1.0.0",
        label="WP11 accepted JW composition",
        scope_statement=(
            "2–4 ordered JW modes, fixed particle number, one or two mapped-fermionic layers; "
            "explicit adjacent/even/odd parity tests, at least 20 nonzero angles, and at least 3 sampled seeds."
        ),
        algebra_operator_norm=1e-10,
        basis_overlap=1e-12,
        matrix_relative_frobenius=1e-10,
        eigenvalue_absolute=1e-9,
        generator_unitary=1e-9,
        sector_leakage=1e-10,
        qasm_semantic=1e-8,
        statistical_sigma_multiplier=3.0,
        absolute_numerical_floor=3e-2,
        minimum_sampled_seeds=3,
        minimum_random_parameter_points=20,
        units_policy="task_declared_units",
        notes=(
            "Mapped-generator and operator-action tests precede task-level energy.",
            "The absolute floor is bounded-cell acceptance, not a general physics tolerance.",
        ),
    )


def build_wp11_verification_policy() -> VerificationPolicyContract:
    return VerificationPolicyContract(
        policy_id="jw.verification.ground_state.wp11.v1",
        policy_version="1.0.0",
        display_name="WP11 JW mapped-generator composition and bounded-cell verification",
        implementation_binding_id="fermion.binding.ground_state_verification.v1",
        required_check_ids=(
            "initial_state_encoding",
            "mapped_generator_unitary_equivalence",
            "nonadjacent_even_odd_sign",
            "random_theta_sector_preservation",
            "qasm_semantic_equivalence",
            "deterministic_reachable_fixture",
            "sampled_seed_count",
            "controller_behavior",
            "reference_uncertainty_consistency",
            "evidence_reproducibility",
            "bounded_meaning",
        ),
        comparison_metric_ids=(
            "generator_unitary",
            "sector_leakage",
            "qasm_semantic",
            "energy_absolute_error",
            "statistical_consistency",
        ),
        required_evidence_capabilities=(
            "independent_reference",
            "composition_gate_report",
            "cell_gate_report",
            "exact_acceptance_fingerprint",
        ),
        tolerance_profile_id=WP11_TOLERANCE_PROFILE_ID,
        requires_independent_reference=True,
        support_status=PolicyStatus.ACCEPTANCE_VERIFIED,
        validity_envelope={
            "n_modes": {"minimum": 2, "maximum": 4},
            "minimum_random_parameter_points": 20,
            "minimum_sampled_seeds": 3,
        },
        limitations=(
            "Acceptance applies only to the exact WP11 fingerprint and declared scale.",
        ),
        provenance={
            "phase": "A.3.2c",
            "work_package": "WP11",
            "three_gate_acceptance": True,
        },
    )


def build_wp11_ansatz_binding() -> ImplementationBindingContract:
    return ImplementationBindingContract(
        binding_id=WP11_ANSATZ_BINDING_ID,
        binding_version="1.0.0",
        display_name="WP11 JW mapped-fermionic swap-network ansatz factory",
        kind=BindingKind.ANSATZ_FACTORY,
        provider="qcol",
        implementation_version="1.0.0",
        convention_id=JW_CONVENTION_ID,
        source_revision="qcol-wp11-jw-fswap-r1",
        import_path="qcol.mapping_policies.profiles.fermion_bindings:jw_mapped_fermionic_ansatz",
        expected_parameters=("context", "mapping", "sector", "initial_state"),
        support_status=PolicyStatus.ACCEPTANCE_VERIFIED,
        description=(
            "Builds exact mapped single-excitation generators by FSWAP conjugation and reuses the shared runtime."
        ),
        limitations=("Bounded by the owning WP11 ansatz policy and exact JW convention.",),
        provenance={
            "phase": "A.3.2c",
            "work_package": "WP11",
            "callable_payload_withheld": True,
        },
    )


def build_wp11_binding_registry() -> ImplementationBindingRegistry:
    from . import fermion_bindings

    registry = ImplementationBindingRegistry(
        registry_id="qcol.mapping-realization.wp11.bindings",
        registry_version="1.0.0",
    )
    binding = build_wp11_ansatz_binding()
    registry.register(
        binding,
        callable_object=fermion_bindings.jw_mapped_fermionic_ansatz,
    )
    return registry


def _source_problem_snapshot() -> dict[str, Any]:
    return {
        "model_id": GENERAL_SPIN_ORBITAL_MODEL_CONTRACT.model_id,
        "model_version": GENERAL_SPIN_ORBITAL_MODEL_CONTRACT.model_version,
        "task_id": "ground_state_energy",
        "mapping_policy_id": JW_POLICY_ID,
        "mapping_convention_id": JW_CONVENTION_ID,
        "declared_presets": [
            "two_modes_one_particle",
            "four_modes_two_particles",
        ],
    }


def build_wp11_acceptance_fingerprint() -> AcceptanceEvidenceFingerprint:
    mapping = build_jw_mapping_policy()
    context = build_jw_encoding_context()
    old_contracts = jw_policy_contracts()
    ansatz = build_wp11_ansatz_policy()
    tolerance = build_wp11_tolerance_profile()
    task = get_task_contract("ground_state_energy")

    state = old_contracts["jw.state.occupation_determinant.v1"]
    measurement = old_contracts["jw.measurement.pauli_energy_qwc.v1"]
    reference = old_contracts["jw.reference.fixed_particle_sector.v1"]
    verification = build_wp11_verification_policy()
    particle_sector = next(
        profile for profile in mapping.sector_profiles
        if profile.quantity_id == "particle_number"
    )

    binding = build_wp11_ansatz_binding()
    binding_identity = BindingEvidenceIdentity(
        role="ansatz_factory",
        binding_id=binding.binding_id,
        binding_version=binding.binding_version,
        provider=binding.provider,
        implementation_version=binding.implementation_version,
        convention_id=binding.convention_id,
        source_revision=binding.source_revision,
    )

    source = _source_problem_snapshot()
    return AcceptanceEvidenceFingerprint(
        fingerprint_id="acceptance-fingerprint.wp11.jw-ground-state.v1",
        fingerprint_version="1.0.0",
        source_problem_fingerprint=contract_fingerprint(source),
        model_contract=component_identity(
            role="model_contract",
            component_id=GENERAL_SPIN_ORBITAL_MODEL_CONTRACT.model_id,
            component_version=GENERAL_SPIN_ORBITAL_MODEL_CONTRACT.model_version,
            snapshot=GENERAL_SPIN_ORBITAL_MODEL_CONTRACT.to_dict(),
        ),
        task_contract=component_identity(
            role="task_contract",
            component_id=task.task_id,
            component_version=task.task_version,
            snapshot=task.to_dict(),
        ),
        mapping_policy=component_identity(
            role="mapping_policy",
            component_id=mapping.policy_id,
            component_version=mapping.policy_version,
            snapshot=mapping.to_dict(),
            convention_id=mapping.convention_id,
        ),
        mode_ordering=component_identity(
            role="mode_ordering",
            component_id=context.mode_ordering.ordering_id,
            component_version=context.mode_ordering.ordering_version,
            snapshot=context.mode_ordering.to_dict(),
        ),
        encoding_context=component_identity(
            role="encoding_context",
            component_id=context.context_id,
            component_version=context.context_version,
            snapshot=context.to_dict(),
            convention_id=context.mapping_convention_id,
        ),
        sector_profiles=(
            component_identity(
                role="sector_profile.particle_number",
                component_id=particle_sector.profile_id,
                component_version=particle_sector.profile_version,
                snapshot=particle_sector.to_dict(),
            ),
        ),
        state_preparation_policy=component_identity(
            role="state_preparation_policy",
            component_id=state.policy_id,
            component_version=state.policy_version,
            snapshot=state.to_dict(),
        ),
        ansatz_policy=component_identity(
            role="ansatz_policy",
            component_id=ansatz.policy_id,
            component_version=ansatz.policy_version,
            snapshot=ansatz.to_dict(),
        ),
        measurement_policy=component_identity(
            role="measurement_policy",
            component_id=measurement.policy_id,
            component_version=measurement.policy_version,
            snapshot=measurement.to_dict(),
        ),
        reference_policy=component_identity(
            role="reference_policy",
            component_id=reference.policy_id,
            component_version=reference.policy_version,
            snapshot=reference.to_dict(),
        ),
        verification_policy=component_identity(
            role="verification_policy",
            component_id=verification.policy_id,
            component_version=verification.policy_version,
            snapshot=verification.to_dict(),
        ),
        tolerance_profile=component_identity(
            role="tolerance_profile",
            component_id=tolerance.profile_id,
            component_version=tolerance.profile_version,
            snapshot=tolerance.to_dict(),
        ),
        implementation_bindings=(binding_identity,),
        dependencies=DependencyFingerprint(
            dependency_set_id="qcol.wp11.quantum-stack",
            dependency_set_version="1.0.0",
            versions={
                "numpy": "1.26.4",
                "scipy": "1.13.1",
                "sympy": "1.13.3",
                "cirq-core": "1.4.1",
                "openfermion": "1.6.1",
                "pyqasm": "1.0.4",
                "ply": "3.11",
            },
        ),
        declared_scale=DeclaredScaleContract(
            scale_id="qcol.wp11.jw-ground-state.bounded-small",
            scale_version="1.0.0",
            dimensions={
                "minimum_modes": 2,
                "maximum_modes": 4,
                "minimum_particles": 1,
                "maximum_ansatz_layers": 2,
                "maximum_parameters": 32,
                "particle_species_count": 1,
                "minimum_random_nonzero_theta_points": 20,
                "minimum_sampled_seeds": 3,
            },
            scope_statement=(
                "First accepted general spin-orbital × ground-state × JW composition; local simulator only."
            ),
        ),
    )


def build_wp11_acceptance_record() -> AcceptanceEvidenceRecord:
    fingerprint = build_wp11_acceptance_fingerprint()
    return AcceptanceEvidenceRecord(
        record_id=WP11_PROMOTION_RECORD_ID,
        record_version="1.0.0",
        acceptance_suite_id=WP11_ACCEPTANCE_SUITE_ID,
        resolved_variant_id=WP11_VARIANT_ID,
        evidence_fingerprint=fingerprint,
        accepted_claim=(
            "The bounded 2–4-mode fixed-particle single-species Jordan–Wigner ground-state composition "
            "uses mapped fermionic single-excitation generators and passes mapper, composition, and cell gates."
        ),
        gate_report_ids=(
            "wp11.mapper-conformance.v1",
            "wp11.composition-conformance.v1",
            "wp11.cell-acceptance.v1",
        ),
        evidence_archive_id="qcol_wp11_jw_accepted_composition_evidence.zip",
        created_by="qcol.wp11.three_gate_acceptance",
        status="accepted",
    )


@lru_cache(maxsize=1)
def public_wp11_jw_accepted_composition_catalog() -> dict[str, Any]:
    ansatz = build_wp11_ansatz_policy()
    binding = build_wp11_ansatz_binding()
    fingerprint = build_wp11_acceptance_fingerprint()
    record = build_wp11_acceptance_record()
    exit_decision = public_a3_2b_exit_decision()
    payload = {
        "schema_version": WP11_CATALOG_SCHEMA_VERSION,
        "catalog_version": WP11_CATALOG_VERSION,
        "project_version": WP11_PROJECT_VERSION,
        "phase": "A.3.2c",
        "work_package": "WP11",
        "variant_id": WP11_VARIANT_ID,
        "mapping_policy_id": JW_POLICY_ID,
        "mapping_convention_id": JW_CONVENTION_ID,
        "ansatz_policy": ansatz.to_dict(),
        "ansatz_binding": binding.to_dict(),
        "tolerance_profile": build_wp11_tolerance_profile().to_dict(),
        "acceptance_fingerprint": fingerprint.to_dict(),
        "promotion_record": record.to_dict(),
        "status_transition": {
            "mapper": {"before": "verified", "after": "verified"},
            "mapping_analysis": {"before": "acceptance_verified", "after": "acceptance_verified"},
            "historical_bare_exchange": {"before": "rejected", "after": "rejected_negative_fixture"},
            "new_composition": {"before": "not_present", "after": "acceptance_verified"},
            "ground_state_cell": {"before": "not_verified", "after": "acceptance_verified"},
        },
        "required_generator_cases": (
            "adjacent_modes",
            "nonadjacent_even_intermediate_parity",
            "nonadjacent_odd_intermediate_parity",
            "random_nonzero_theta",
        ),
        "foundation": {
            "a3_2b_exit_status": exit_decision["status"],
            "a3_2b_catalog_fingerprint": spin_orbital_mapping_migration_catalog_fingerprint(),
            "wp8_pair_catalog_fingerprint": pair_mapping_migration_catalog_fingerprint(),
        },
        "guardrails": {
            "old_negative_fixture_preserved": True,
            "full_bk_execution_enabled": False,
            "second_runtime_created": False,
            "same_shared_execution_pipeline": True,
            "scientific_behavior_change": True,
            "behavior_change_scope": "replace only the production JW ansatz composition",
        },
    }
    return json.loads(json.dumps(payload, sort_keys=True, allow_nan=False))


def wp11_jw_accepted_composition_catalog_fingerprint(
    payload: Mapping[str, Any] | None = None,
) -> str:
    value = dict(payload or public_wp11_jw_accepted_composition_catalog())
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def validate_wp11_jw_accepted_composition(
    payload: Mapping[str, Any] | None = None,
) -> dict[str, bool]:
    catalog = dict(payload or public_wp11_jw_accepted_composition_catalog())
    transition = catalog["status_transition"]
    ansatz = catalog["ansatz_policy"]
    guardrails = catalog["guardrails"]
    return {
        "strict_json_round_trip": json.loads(json.dumps(catalog, sort_keys=True, allow_nan=False)) == catalog,
        "mapped_fermionic_semantics": ansatz["semantic_class"] == "mapped_fermionic_generator",
        "mapped_generator_capability": "mapped_generator_semantics" in ansatz["provided_capabilities"],
        "exact_binding": catalog["ansatz_binding"]["binding_id"] == WP11_ANSATZ_BINDING_ID,
        "historical_negative_preserved": transition["historical_bare_exchange"]["after"] == "rejected_negative_fixture",
        "new_composition_verified": transition["new_composition"]["after"] == "acceptance_verified",
        "cell_promoted": transition["ground_state_cell"]["after"] == "acceptance_verified",
        "fingerprint_current": catalog["promotion_record"]["evidence_fingerprint"]["fingerprint"] == catalog["acceptance_fingerprint"]["fingerprint"],
        "no_second_runtime": guardrails["second_runtime_created"] is False,
        "bk_boundary_preserved": guardrails["full_bk_execution_enabled"] is False,
    }


__all__ = [
    "WP11_PROJECT_VERSION",
    "WP11_COMPOSITION_SCHEMA_VERSION",
    "WP11_CATALOG_SCHEMA_VERSION",
    "WP11_CATALOG_VERSION",
    "WP11_ANSATZ_POLICY_ID",
    "WP11_ANSATZ_BINDING_ID",
    "WP11_TOLERANCE_PROFILE_ID",
    "WP11_VARIANT_ID",
    "WP11_ACCEPTANCE_SUITE_ID",
    "WP11_PROMOTION_RECORD_ID",
    "build_wp11_ansatz_policy",
    "build_wp11_tolerance_profile",
    "build_wp11_verification_policy",
    "build_wp11_ansatz_binding",
    "build_wp11_binding_registry",
    "build_wp11_acceptance_fingerprint",
    "build_wp11_acceptance_record",
    "public_wp11_jw_accepted_composition_catalog",
    "wp11_jw_accepted_composition_catalog_fingerprint",
    "validate_wp11_jw_accepted_composition",
]

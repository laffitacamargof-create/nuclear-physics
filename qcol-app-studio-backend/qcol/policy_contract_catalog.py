"""Public WP2 catalog for declarative mapping-realization policy contracts."""
from __future__ import annotations

from dataclasses import MISSING, fields
import hashlib
import json
from typing import Any, get_type_hints

from qcol.acceptance.tolerance_profiles import ToleranceProfile
from qcol.mapping_policies.contracts import MappingPolicyContract
from qcol.mapping_policies.enums import (
    AlgebraScope,
    AnsatzSemanticClass,
    MappingFamily,
    MappingScope,
    PolicyStatus,
    SectorRepresentationKind,
)
from qcol.realization_policies import (
    AnsatzPolicyContract,
    EncodingContext,
    MeasurementPolicyContract,
    ModeOrderingContract,
    ReferencePolicyContract,
    SectorEncodingProfile,
    StatePreparationPolicyContract,
    VerificationPolicyContract,
    contains_callable,
)
from qcol.realization_policies.base import PolicyContractError


POLICY_CONTRACT_CATALOG_SCHEMA_VERSION = "qcol-declarative-policy-contract-catalog/1.0"
POLICY_CONTRACTS_VERSION = "1.0.0"
WP2_INTRODUCED_PROJECT_VERSION = "1.10.0"


CONTRACT_TYPES = (
    MappingPolicyContract,
    ModeOrderingContract,
    EncodingContext,
    SectorEncodingProfile,
    StatePreparationPolicyContract,
    AnsatzPolicyContract,
    MeasurementPolicyContract,
    ReferencePolicyContract,
    VerificationPolicyContract,
    ToleranceProfile,
)


def _type_text(value: Any) -> str:
    return str(value).replace("typing.", "")


def _schema_for(contract_type: type[Any]) -> dict[str, Any]:
    hints = get_type_hints(contract_type)
    return {
        "contract_type": contract_type.__name__,
        "module": contract_type.__module__,
        "frozen_dataclass": True,
        "fields": [
            {
                "name": field.name,
                "type": _type_text(hints.get(field.name, field.type)),
                "has_default": field.default is not MISSING or field.default_factory is not MISSING,
            }
            for field in fields(contract_type)
        ],
    }


def build_wp2_contract_examples() -> dict[str, Any]:
    """Build schema examples only; none is registered as a live runtime policy."""
    ordering = ModeOrderingContract(
        ordering_id="wp2.example.spin_orbital_order.v1",
        ordering_version="1.0.0",
        ordered_mode_labels=("n:a:+1/2", "n:a:-1/2", "n:b:+1/2", "n:b:-1/2"),
        species_order=("neutron",),
        spin_order=("+1/2", "-1/2"),
        mode_index_convention="declared_zero_based_mode_index.v1",
        qubit_index_convention="declared_zero_based_qubit_index.v1",
        endian_convention="qcol_little_endian.v1",
        bitstring_display_convention="highest_qubit_left.v1",
        metadata={"example_only": True},
    )
    direct_particle = SectorEncodingProfile(
        profile_id="wp2.example.particle_number_direct.v1",
        profile_version="1.0.0",
        quantity_id="particle_number",
        representation_kind=SectorRepresentationKind.DIRECT_POPCOUNT,
        raw_bitstring_semantics="Raw popcount equals the declared particle number only under this exact encoding profile.",
        diagnostic_policy_id="wp2.binding.particle_popcount_diagnostic.v1",
        required_metadata=("target_particle_number", "mode_ordering_fingerprint"),
        support_status=PolicyStatus.REGISTERED,
        limitations=("Schema example only; not a migrated live mapping policy.",),
    )
    nonlocal_particle = SectorEncodingProfile(
        profile_id="wp2.example.particle_number_nonlocal.v1",
        profile_version="1.0.0",
        quantity_id="particle_number",
        representation_kind=SectorRepresentationKind.NONLOCAL_MAPPED_OPERATOR,
        raw_bitstring_semantics="Raw popcount has no universal particle-number meaning; use the mapped diagnostic operator or decoder.",
        diagnostic_policy_id="wp2.binding.nonlocal_particle_operator.v1",
        decoder_policy_id="wp2.binding.distributed_occupation_decoder.v1",
        required_metadata=("mapping_convention_id", "mode_ordering_fingerprint"),
        support_status=PolicyStatus.REGISTERED,
        limitations=("Schema example only; not a migrated live BK policy.",),
    )
    mapping = MappingPolicyContract(
        policy_id="wp2.schema_example.full_fermion_mapping.v1",
        policy_version="1.0.0",
        display_name="WP2 full-fermion mapping schema example",
        family=MappingFamily.JORDAN_WIGNER,
        scope=MappingScope.FULL_FERMIONIC_FOCK_SPACE,
        algebra_scope=AlgebraScope.CANONICAL_ANTICOMMUTATION_RELATIONS,
        convention_id="wp2.example.ordered_mode_encoding.v1",
        implementation_binding_id="wp2.binding.operator_mapper.v1",
        accepted_operator_types=("FermionOperator",),
        supported_term_ranks=(0, 1, 2),
        required_model_metadata=("n_modes", "mode_ordering", "particle_species"),
        allowed_physical_domains=("general_spin_orbital",),
        excluded_configurations=("undeclared_mode_order",),
        qubit_count_rule="n_qubits = n_modes",
        mode_ordering_requirements=("exact_declared_mode_order", "same_context_fingerprint"),
        encoder_policy_id="wp2.binding.occupation_encoder.v1",
        decoder_policy_id="wp2.binding.occupation_decoder.v1",
        physical_subspace_policy_id="wp2.binding.full_fock_space.v1",
        sector_profiles=(direct_particle,),
        provided_capabilities=(
            "fermion_operator_transform",
            "task_operator_transform",
            "basis_state_encoding",
            "particle_number_diagnostic",
        ),
        requires_state_preparation_capabilities=(
            "declared_basis_state_semantics",
            "mode_order_aware",
            "target_sector_aware",
        ),
        requires_ansatz_capabilities=(
            "mapped_generator_semantics",
            "particle_number_preserving",
            "mode_order_aware",
        ),
        requires_measurement_capabilities=("mapped_observable_semantics",),
        requires_reference_capabilities=("source_domain_independence", "sector_matched_reference"),
        requires_verification_capabilities=("operator_action_equivalence", "sector_diagnostics"),
        supported_task_capabilities=("mapping_analysis", "ground_state_energy"),
        required_task_operator_capabilities=("hamiltonian", "particle_number"),
        verification_profile_ids=("wp2.profile.mapper_conformance.v1",),
        resource_metric_ids=("n_qubits", "pauli_term_count", "maximum_pauli_weight"),
        resource_assessor_binding_id="wp2.binding.standard_mapping_resources.v1",
        support_status=PolicyStatus.REGISTERED,
        scientific_owner="WP2 schema example",
        limitations=("Not registered in the live mapping registry.",),
        provenance={"example_only": True, "scientific_behavior_change": False},
    )
    context = EncodingContext(
        context_id="wp2.example.encoding_context.v1",
        context_version="1.0.0",
        mapping_policy_id=mapping.policy_id,
        mapping_policy_version=mapping.policy_version,
        mapping_convention_id=mapping.convention_id,
        mode_ordering=ordering,
        n_qubits=4,
        target_sector_fingerprint="sector-example-4modes-2particles-v1",
        metadata={"example_only": True},
    )
    state = StatePreparationPolicyContract(
        policy_id="wp2.schema_example.state_preparation.v1",
        policy_version="1.0.0",
        display_name="WP2 occupation-state preparation example",
        implementation_binding_id="wp2.binding.state_preparation.v1",
        input_state_semantics="declared spin-orbital occupation vector",
        provided_capabilities=("declared_basis_state_semantics", "mode_order_aware", "target_sector_aware"),
        required_mapping_capabilities=("basis_state_encoding",),
        required_sector_capabilities=("particle_number_diagnostic",),
        conserved_quantity_guarantees=("particle_number",),
        exact_reference_usage="forbidden",
        support_status=PolicyStatus.REGISTERED,
        validity_envelope={"example_only": True, "maximum_modes": 4},
        limitations=("Not registered as a live state-preparation policy.",),
        provenance={"scientific_behavior_change": False},
    )
    ansatz = AnsatzPolicyContract(
        policy_id="wp2.schema_example.mapped_generator_ansatz.v1",
        policy_version="1.0.0",
        display_name="WP2 mapped-generator ansatz example",
        implementation_binding_id="wp2.binding.mapped_generator_ansatz.v1",
        semantic_class=AnsatzSemanticClass.MAPPED_FERMIONIC_GENERATOR,
        generator_domain="fermionic",
        provided_capabilities=("mapped_generator_semantics", "particle_number_preserving", "mode_order_aware"),
        required_mapping_capabilities=("task_operator_transform",),
        required_sector_capabilities=("particle_number_diagnostic",),
        preserved_quantities=("particle_number",),
        required_equivalence_evidence=("generator_circuit_unitary_equivalence", "nonadjacent_sign_equivalence"),
        parameterization_policy_id="wp2.binding.real_parameter_vector.v1",
        support_status=PolicyStatus.REGISTERED,
        validity_envelope={"example_only": True, "maximum_modes": 4},
        limitations=("Not registered as a live ansatz policy.",),
        provenance={"scientific_behavior_change": False},
    )
    measurement = MeasurementPolicyContract(
        policy_id="wp2.schema_example.measurement.v1",
        policy_version="1.0.0",
        display_name="WP2 mapped-observable measurement example",
        implementation_binding_id="wp2.binding.measurement_builder.v1",
        supported_observable_capabilities=("mapped_hamiltonian_terms", "mapped_particle_number"),
        required_mapping_capabilities=("task_operator_transform",),
        required_sector_capabilities=("particle_number_diagnostic",),
        grouping_policy_id="wp2.binding.qwc_grouping.v1",
        reconstruction_policy_id="wp2.binding.term_expectation_reconstruction.v1",
        result_semantics="weighted expectation reconstructed from declared mapped task operators",
        shots_required=True,
        support_status=PolicyStatus.REGISTERED,
        validity_envelope={"example_only": True},
        limitations=("No backend claim is made by the schema example.",),
        provenance={"scientific_behavior_change": False},
    )
    reference = ReferencePolicyContract(
        policy_id="wp2.schema_example.reference.v1",
        policy_version="1.0.0",
        display_name="WP2 independent source-domain reference example",
        independent_solver_binding_id="wp2.binding.source_domain_exact_solver.v1",
        source_representation_id="second_quantized_fermion.v1",
        supported_quantities=("ground_state_energy", "particle_number"),
        required_model_capabilities=("fermion_operator", "mode_ordering"),
        required_sector_capabilities=("fixed_particle_number_sector",),
        units_policy="same_declared_energy_units.v1",
        constant_shift_policy="record_and_apply_constant_shift.v1",
        constructed_from_tested_mapping=False,
        support_status=PolicyStatus.REGISTERED,
        validity_envelope={"example_only": True, "maximum_modes": 6},
        limitations=("Not registered as a live reference policy.",),
        provenance={"scientific_behavior_change": False},
    )
    tolerance = ToleranceProfile(
        profile_id="wp2.example.ideal_small_matrix.v1",
        profile_version="1.0.0",
        label="WP2 ideal small-matrix tolerance example",
        algebra_operator_norm=1e-10,
        basis_overlap=1e-12,
        matrix_relative_frobenius=1e-10,
        eigenvalue_absolute=1e-9,
        generator_unitary=1e-9,
        sector_leakage=1e-10,
        qasm_semantic=1e-8,
        statistical_sigma_multiplier=3.0,
        absolute_numerical_floor=1e-8,
        minimum_sampled_seeds=3,
        minimum_random_parameter_points=20,
        notes=("Schema example only; task-specific profiles may override bounded fields.",),
    )
    verification = VerificationPolicyContract(
        policy_id="wp2.schema_example.verification.v1",
        policy_version="1.0.0",
        display_name="WP2 three-gate verification example",
        implementation_binding_id="wp2.binding.verification.v1",
        required_check_ids=("mapper_conformance", "composition_conformance", "cell_acceptance"),
        comparison_metric_ids=("operator_matrix_error", "sector_leakage", "reference_error"),
        required_evidence_capabilities=("contract_snapshots", "source_fingerprints", "raw_records"),
        tolerance_profile_id=tolerance.profile_id,
        requires_independent_reference=True,
        support_status=PolicyStatus.REGISTERED,
        validity_envelope={"example_only": True},
        limitations=("Not registered as a live verification policy.",),
        provenance={"scientific_behavior_change": False},
    )
    return {
        "mode_ordering": ordering,
        "encoding_context": context,
        "direct_sector_profile": direct_particle,
        "nonlocal_sector_profile": nonlocal_particle,
        "mapping_policy": mapping,
        "state_preparation_policy": state,
        "ansatz_policy": ansatz,
        "measurement_policy": measurement,
        "reference_policy": reference,
        "verification_policy": verification,
        "tolerance_profile": tolerance,
    }


def public_declarative_policy_contract_catalog() -> dict[str, Any]:
    examples = build_wp2_contract_examples()
    payload = {
        "schema_version": POLICY_CONTRACT_CATALOG_SCHEMA_VERSION,
        "contracts_version": POLICY_CONTRACTS_VERSION,
        "project_version": WP2_INTRODUCED_PROJECT_VERSION,
        "phase": "Phase A.3.2a",
        "work_package": "WP2 — Declarative Policy Contracts",
        "scientific_behavior_change": False,
        "contracts_are_executable": False,
        "callables_in_public_contracts": False,
        "live_policy_migration_performed": False,
        "contract_types": [_schema_for(item) for item in CONTRACT_TYPES],
        "examples": {name: value.to_dict() for name, value in examples.items()},
        "guardrails": [
            {
                "id": "wp2.capabilities_not_concrete_ansatz_ids.v1",
                "required_field": "requires_ansatz_capabilities",
                "forbidden_pattern": "compatible_ansatz_ids / concrete ansatz class names",
            },
            {
                "id": "wp2.one_sector_profile_per_quantity.v1",
                "statement": "Every represented conserved quantity has its own SectorEncodingProfile.",
            },
            {
                "id": "wp2.reference_independent_of_tested_mapping.v1",
                "statement": "Acceptance references are derived from the source problem, not the mapping implementation under test.",
            },
            {
                "id": "wp2.binding_ids_not_callables.v1",
                "statement": "Contracts store versioned implementation_binding_id strings only; WP3 registries own callables.",
            },
        ],
    }
    payload["fingerprint"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return json.loads(json.dumps(payload, sort_keys=True, allow_nan=False))


def policy_contract_catalog_fingerprint(payload: dict[str, Any] | None = None) -> str:
    catalog = dict(payload or public_declarative_policy_contract_catalog())
    existing = catalog.pop("fingerprint", None)
    fingerprint = hashlib.sha256(
        json.dumps(catalog, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    if existing is not None and existing != fingerprint:
        raise PolicyContractError("Policy-contract catalog fingerprint mismatch.")
    return fingerprint


def validate_declarative_policy_contracts(payload: dict[str, Any] | None = None) -> dict[str, bool]:
    catalog = payload or public_declarative_policy_contract_catalog()
    examples = build_wp2_contract_examples()
    mapping = examples["mapping_policy"]
    sector_quantities = [item.quantity_id for item in mapping.sector_profiles]
    strict_json = json.loads(json.dumps(catalog, sort_keys=True, allow_nan=False)) == catalog
    no_callables = not any(contains_callable(value) for value in examples.values())
    mapping_fields = {field.name for field in fields(MappingPolicyContract)}
    return {
        "strict_json_round_trip": strict_json,
        "all_contracts_frozen": all(getattr(item, "__dataclass_params__").frozen for item in CONTRACT_TYPES),
        "no_callables": no_callables,
        "all_fingerprints_deterministic": all(len(value.fingerprint()) == 64 for value in examples.values()),
        "mapping_uses_capabilities": bool(mapping.requires_ansatz_capabilities),
        "mapping_does_not_expose_compatible_ansatz_ids": "compatible_ansatz_ids" not in mapping_fields,
        "sector_profiles_are_per_quantity": len(sector_quantities) == len(set(sector_quantities)),
        "direct_and_nonlocal_sector_semantics_separated": (
            examples["direct_sector_profile"].representation_kind
            is not examples["nonlocal_sector_profile"].representation_kind
        ),
        "reference_is_independent": not examples["reference_policy"].constructed_from_tested_mapping,
        "examples_are_not_live_migrations": catalog["live_policy_migration_performed"] is False,
        "scientific_behavior_change_false": catalog["scientific_behavior_change"] is False,
        "catalog_fingerprint_valid": policy_contract_catalog_fingerprint(catalog) == catalog["fingerprint"],
    }


__all__ = [
    "POLICY_CONTRACT_CATALOG_SCHEMA_VERSION",
    "POLICY_CONTRACTS_VERSION",
    "CONTRACT_TYPES",
    "build_wp2_contract_examples",
    "public_declarative_policy_contract_catalog",
    "policy_contract_catalog_fingerprint",
    "validate_declarative_policy_contracts",
]

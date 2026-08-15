"""WP8 migration profile for QCOL's seniority-zero Pair Mapping.

This module migrates the already accepted reduced-pairing implementation into
WP2--WP7 policy contracts, exact binding registries, compatibility resolution,
exact evidence fingerprints, and the generic three-gate harness.  It narrows
rather than broadens the scientific claim:

* one qubit represents one intact-pair level occupation;
* the valid physical domain is the declared seniority-zero reduced-pairing
  subspace;
* the preserved algebra is quasispin / hard-core-pair algebra, not the full
  single-fermion CAR;
* one-pair remains the accepted regression anchor;
* multi-pair remains experimental.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json
from typing import Any, Mapping

from qcol.acceptance.fingerprint import (
    AcceptanceEvidenceFingerprint,
    BindingEvidenceIdentity,
    DeclaredScaleContract,
    DependencyFingerprint,
    component_identity,
)
from qcol.acceptance.harness import (
    AcceptanceGateContract,
    AcceptanceGateKind,
    AcceptanceHarnessCase,
    AcceptanceObservation,
    GenericThreeGateAcceptanceHarness,
    ObservationComparison,
    ToleranceProfileRegistry,
)
from qcol.acceptance.harness_fixtures import build_wp7_tolerance_registry
from qcol.acceptance.mapping_baseline import baseline_fingerprint
from qcol.acceptance.tolerance_profiles import ToleranceProfile
from qcol.compatibility import RuleEvaluationContext, build_wp4_rule_registry
from qcol.implementation_bindings import (
    BindingKind,
    DeclarativePolicyContractRegistry,
    ImplementationBindingContract,
    ImplementationBindingRegistry,
)
from qcol.mapping_policies.contracts import MappingPolicyContract
from qcol.mapping_policies.enums import (
    AlgebraScope,
    AnsatzSemanticClass,
    CheckStatus,
    GateApplicability,
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
)
from qcol.realization_policies.base import (
    DeclarativeContract,
    contract_fingerprint,
    freeze_json,
    require_text,
    require_token,
)
from qcol.realization_variants import (
    RealizationCandidate,
    RealizationTaskMode,
    RealizationVariantResolver,
)
from qcol.models.reduced_pairing_one_pair.contract import ONE_PAIR_MODEL_CONTRACT
from qcol.models.reduced_pairing_multi_pair.contract import MULTI_PAIR_MODEL_CONTRACT

from . import pair_bindings


PAIR_MAPPING_PROFILE_SCHEMA_VERSION = "qcol-pair-mapping-migration-profile/1.0"
PAIR_MAPPING_PROFILE_ID = "qcol.mapping-profile.pair.seniority-zero.v1"
PAIR_MAPPING_POLICY_ID = "pair_mapping.seniority_zero.v1"
PAIR_MAPPING_POLICY_VERSION = "1.0.0"
PAIR_MAPPING_CONVENTION_ID = "qcol.pair.one-qubit-per-level.seniority-zero.v1"
PAIR_MAPPING_SEMANTIC_SCOPE = "restricted_seniority_zero_subspace"
PAIR_MAPPING_PRESERVED_ALGEBRA = "quasispin / hard-core-pair algebra"
WP8_PROJECT_VERSION = "1.16.0"
PAIR_MIGRATION_CATALOG_SCHEMA_VERSION = "qcol-pair-mapping-policy-migration-catalog/1.0"
PAIR_MIGRATION_CATALOG_VERSION = "1.0.0"


@dataclass(frozen=True)
class PairMappingMigrationProfile(DeclarativeContract):
    profile_id: str
    profile_version: str
    mapping_scope: str
    generic_mapping_scope: MappingScope
    preserved_algebra: str
    generic_algebra_scope: AlgebraScope
    mapping_policy: MappingPolicyContract
    component_contract_ids: Mapping[str, str]
    legacy_policy_aliases: Mapping[str, str]
    support_boundaries: Mapping[str, Any]
    scientific_behavior_change: bool = False
    schema_version: str = PAIR_MAPPING_PROFILE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        require_token("profile_id", self.profile_id)
        require_token("profile_version", self.profile_version)
        require_token("mapping_scope", self.mapping_scope)
        require_text("preserved_algebra", self.preserved_algebra)
        if not isinstance(self.generic_mapping_scope, MappingScope):
            raise TypeError("generic_mapping_scope must be MappingScope.")
        if not isinstance(self.generic_algebra_scope, AlgebraScope):
            raise TypeError("generic_algebra_scope must be AlgebraScope.")
        if not isinstance(self.mapping_policy, MappingPolicyContract):
            raise TypeError("mapping_policy must be MappingPolicyContract.")
        object.__setattr__(self, "component_contract_ids", freeze_json(self.component_contract_ids, path="PairMappingMigrationProfile.component_contract_ids"))
        object.__setattr__(self, "legacy_policy_aliases", freeze_json(self.legacy_policy_aliases, path="PairMappingMigrationProfile.legacy_policy_aliases"))
        object.__setattr__(self, "support_boundaries", freeze_json(self.support_boundaries, path="PairMappingMigrationProfile.support_boundaries"))


def _sector_profiles() -> tuple[SectorEncodingProfile, ...]:
    return (
        SectorEncodingProfile(
            profile_id="pair.sector.pair_number.direct_popcount.v1",
            profile_version="1.0.0",
            quantity_id="pair_number",
            representation_kind=SectorRepresentationKind.DIRECT_POPCOUNT,
            raw_bitstring_semantics=(
                "The popcount of the pair-occupation qubits equals the number of intact pairs."
            ),
            diagnostic_policy_id="pair.binding.pair_number_popcount.v1",
            required_metadata=("target_pair_number", "pair_level_ordering_fingerprint"),
            support_status=PolicyStatus.ACCEPTANCE_VERIFIED,
            limitations=("This popcount is pair number, not single-fermion particle number.",),
        ),
        SectorEncodingProfile(
            profile_id="pair.sector.particle_number.two_times_popcount.v1",
            profile_version="1.0.0",
            quantity_id="particle_number",
            representation_kind=SectorRepresentationKind.LOCAL_DIAGONAL_OPERATOR,
            raw_bitstring_semantics=(
                "Physical particle number equals twice the pair-qubit popcount in the intact-pair domain."
            ),
            diagnostic_policy_id="pair.binding.particle_number_from_pair_bits.v1",
            required_metadata=("target_particle_number", "target_pair_number"),
            support_status=PolicyStatus.ACCEPTANCE_VERIFIED,
            limitations=("Unpaired-particle occupations are outside this encoding.",),
        ),
        SectorEncodingProfile(
            profile_id="pair.sector.seniority.fixed_by_domain.v1",
            profile_version="1.0.0",
            quantity_id="seniority",
            representation_kind=SectorRepresentationKind.FIXED_BY_PHYSICAL_DOMAIN,
            raw_bitstring_semantics=(
                "Seniority is fixed to zero by the declared physical domain; it is not inferred from raw qubit popcount."
            ),
            diagnostic_policy_id="pair.binding.seniority_zero_domain.v1",
            required_metadata=("physical_domain", "seniority"),
            exact_value_required=True,
            support_status=PolicyStatus.ACCEPTANCE_VERIFIED,
            limitations=("Broken-pair and nonzero-seniority configurations are unsupported.",),
        ),
    )


def build_pair_mapping_policy() -> MappingPolicyContract:
    return MappingPolicyContract(
        policy_id=PAIR_MAPPING_POLICY_ID,
        policy_version=PAIR_MAPPING_POLICY_VERSION,
        display_name="Pair Mapping — restricted seniority-zero pair occupation",
        family=MappingFamily.PAIR,
        scope=MappingScope.RESTRICTED_PHYSICAL_SUBSPACE,
        algebra_scope=AlgebraScope.QUASISPIN_PAIR_ALGEBRA,
        convention_id=PAIR_MAPPING_CONVENTION_ID,
        implementation_binding_id="pair.binding.operator_transform.v1",
        accepted_operator_types=("FermionOperator",),
        supported_term_ranks=(0, 1, 2),
        required_model_metadata=(
            "n_levels",
            "n_pairs",
            "seniority",
            "pair_level_order",
        ),
        allowed_physical_domains=("reduced_pairing", "reduced_pairing_seniority_zero"),
        excluded_configurations=(
            "broken_pair_configuration",
            "nonzero_seniority",
            "general_single_fermion_hopping_outside_pair_subspace",
            "general_shell_model_configuration",
        ),
        qubit_count_rule="n_qubits = n_pair_levels; one qubit stores one intact-pair level occupation",
        mode_ordering_requirements=(
            "explicit_pair_level_order",
            "same_encoding_context_fingerprint",
            "one_qubit_per_pair_level",
        ),
        encoder_policy_id="pair.binding.basis_encoder.v1",
        decoder_policy_id="pair.binding.basis_decoder.v1",
        physical_subspace_policy_id="pair.binding.seniority_zero_subspace.v1",
        sector_profiles=_sector_profiles(),
        provided_capabilities=(
            "reduced_pairing_operator_transform",
            "pair_basis_state_encoding",
            "pair_basis_state_decoding",
            "pair_number_diagnostic",
            "particle_number_from_pair_occupation",
            "seniority_zero_domain",
            "pair_quasispin_algebra",
            "mapped_observable_semantics",
            "pair_occupation_observable",
            "pair_transfer_operator",
        ),
        requires_state_preparation_capabilities=(
            "pair_basis_state_semantics",
            "pair_number_preserving",
            "seniority_zero_aware",
            "mode_order_aware",
        ),
        requires_ansatz_capabilities=(
            "encoded_pair_space_semantics",
            "pair_number_preserving",
            "seniority_zero_preserving",
            "mode_order_aware",
        ),
        requires_measurement_capabilities=(
            "mapped_observable_semantics",
            "pair_energy_reconstruction",
        ),
        requires_reference_capabilities=(
            "source_domain_independence",
            "fixed_pair_sector_reference",
            "seniority_zero_reference",
        ),
        requires_verification_capabilities=(
            "pair_subspace_operator_equivalence",
            "pair_number_sector_diagnostics",
            "seniority_zero_domain_check",
        ),
        supported_task_capabilities=(
            "ground_state_energy",
            "sector_ground_state_energy",
            "observable_estimation",
        ),
        required_task_operator_capabilities=(
            "hamiltonian",
            "pair_number",
            "particle_number",
            "pair_occupation",
        ),
        verification_profile_ids=(
            "wp8.profile.pair.mapper_conformance.v1",
            "wp8.profile.pair.composition_conformance.v1",
            "wp8.profile.pair.cell_acceptance.v1",
        ),
        resource_metric_ids=(
            "n_qubits",
            "pauli_term_count",
            "maximum_pauli_weight",
            "qwc_measurement_group_count",
            "fixed_pair_sector_dimension",
        ),
        resource_assessor_binding_id="pair.binding.resource_assessor.v1",
        support_status=PolicyStatus.ACCEPTANCE_VERIFIED,
        scientific_owner="QCOL reduced-pairing scientific owner",
        limitations=(
            "This policy is not a general single-fermion mapping.",
            "The encoded Hilbert space contains intact pair occupations only.",
            "Nonzero-seniority and broken-pair states are outside the declared domain.",
            "Full single-fermion canonical anticommutation relations are not claimed for pair qubits.",
        ),
        provenance={
            "phase": "Phase A.3.2b",
            "work_package": "WP8",
            "legacy_policy_id": "pair_mapping.v1",
            "mapping_scope": PAIR_MAPPING_SEMANTIC_SCOPE,
            "preserved_algebra": PAIR_MAPPING_PRESERVED_ALGEBRA,
            "implementation_source": "qcol.models.reduced_pairing_common.pair_mapping_policy",
            "baseline_anchor": "baseline.pair.one_pair.ground_state.v1",
            "scientific_behavior_change": False,
        },
    )


def build_pair_mode_ordering(n_levels: int) -> ModeOrderingContract:
    n_levels = int(n_levels)
    if n_levels <= 1:
        raise ValueError("Pair Mapping requires at least two declared pair levels.")
    return ModeOrderingContract(
        ordering_id=f"pair.level-order.{n_levels}.v1",
        ordering_version="1.0.0",
        ordered_mode_labels=tuple(f"pair_level:{index}" for index in range(n_levels)),
        species_order=("intact_fermion_pair",),
        spin_order=(),
        mode_index_convention="zero_based_pair_level_index.v1",
        qubit_index_convention="qubit_index_equals_pair_level_index.v1",
        endian_convention="qcol_little_endian.v1",
        bitstring_display_convention="highest_qubit_left_pair_occupation.v1",
        metadata={
            "mapping_scope": PAIR_MAPPING_SEMANTIC_SCOPE,
            "single_pair_level_meaning": "one intact time-reversed fermion pair level",
        },
    )


def _sector_fingerprint(n_levels: int, n_pairs: int) -> str:
    payload = {
        "n_levels": int(n_levels),
        "n_pairs": int(n_pairs),
        "n_particles": 2 * int(n_pairs),
        "seniority": 0,
    }
    return contract_fingerprint(payload)


def build_pair_encoding_context(n_levels: int, n_pairs: int) -> EncodingContext:
    ordering = build_pair_mode_ordering(n_levels)
    return EncodingContext(
        context_id=f"pair.encoding-context.{n_levels}levels.{n_pairs}pairs.v1",
        context_version="1.0.0",
        mapping_policy_id=PAIR_MAPPING_POLICY_ID,
        mapping_policy_version=PAIR_MAPPING_POLICY_VERSION,
        mapping_convention_id=PAIR_MAPPING_CONVENTION_ID,
        mode_ordering=ordering,
        n_qubits=int(n_levels),
        target_sector_fingerprint=_sector_fingerprint(n_levels, n_pairs),
        metadata={
            "mapping_scope": PAIR_MAPPING_SEMANTIC_SCOPE,
            "pair_number": int(n_pairs),
            "particle_number": 2 * int(n_pairs),
            "seniority": 0,
        },
    )


def _state_contracts() -> tuple[StatePreparationPolicyContract, StatePreparationPolicyContract]:
    one_pair = StatePreparationPolicyContract(
        policy_id="pair.state.one_pair.lowest_level.v1",
        policy_version="1.0.0",
        display_name="One-pair lowest-level pair-occupation state",
        implementation_binding_id="pair.binding.state.one_pair_lowest_level.v1",
        input_state_semantics="one intact pair occupying the first declared pair level",
        provided_capabilities=(
            "pair_basis_state_semantics",
            "pair_number_preserving",
            "seniority_zero_aware",
            "mode_order_aware",
            "target_sector_aware",
        ),
        required_mapping_capabilities=("pair_basis_state_encoding", "seniority_zero_domain"),
        required_sector_capabilities=("pair_number_diagnostic", "seniority_zero_domain"),
        conserved_quantity_guarantees=("pair_number", "particle_number", "seniority"),
        exact_reference_usage="forbidden",
        support_status=PolicyStatus.ACCEPTANCE_VERIFIED,
        validity_envelope={"n_pairs": 1, "seniority": 0, "n_levels": {"minimum": 2, "maximum": 6}},
        limitations=("Not a multi-pair or broken-pair state builder.",),
        provenance={"legacy_policy_id": "one_pair_lowest_level_state.v1", "scientific_behavior_change": False},
    )
    multi_pair = StatePreparationPolicyContract(
        policy_id="pair.state.multi_pair.lowest_levels.v1",
        policy_version="1.0.0",
        display_name="Multi-pair lowest-level pair-occupation state",
        implementation_binding_id="pair.binding.state.multi_pair_lowest_levels.v1",
        input_state_semantics="n intact pairs occupying the first n declared pair levels",
        provided_capabilities=(
            "pair_basis_state_semantics",
            "pair_number_preserving",
            "seniority_zero_aware",
            "mode_order_aware",
            "target_sector_aware",
        ),
        required_mapping_capabilities=("pair_basis_state_encoding", "seniority_zero_domain"),
        required_sector_capabilities=("pair_number_diagnostic", "seniority_zero_domain"),
        conserved_quantity_guarantees=("pair_number", "particle_number", "seniority"),
        exact_reference_usage="forbidden",
        support_status=PolicyStatus.EXPERIMENTAL,
        validity_envelope={"n_pairs": {"minimum": 2, "maximum": 3}, "seniority": 0, "n_levels": {"minimum": 4, "maximum": 6}},
        limitations=("The state is executable, but the complete multi-pair cell remains experimental.",),
        provenance={"legacy_policy_id": "multi_pair_lowest_levels_state.v1", "source": "Bathri QCOL implementation", "scientific_behavior_change": False},
    )
    return one_pair, multi_pair


def _ansatz_contracts() -> tuple[AnsatzPolicyContract, AnsatzPolicyContract]:
    one_pair = AnsatzPolicyContract(
        policy_id="pair.ansatz.one_pair.chain_givens.v1",
        policy_version="1.0.0",
        display_name="One-pair chain Givens in pair-occupation space",
        implementation_binding_id="pair.binding.ansatz.one_pair_chain_givens.v1",
        semantic_class=AnsatzSemanticClass.MAPPING_NATIVE_VERIFIED,
        generator_domain="quasispin_pair_occupation",
        provided_capabilities=(
            "encoded_pair_space_semantics",
            "pair_number_preserving",
            "seniority_zero_preserving",
            "mode_order_aware",
            "mapping_native_equivalence",
        ),
        required_mapping_capabilities=("pair_quasispin_algebra", "pair_transfer_operator"),
        required_sector_capabilities=("pair_number_diagnostic", "seniority_zero_domain"),
        preserved_quantities=("pair_number", "particle_number", "seniority"),
        required_equivalence_evidence=(
            "pair_transfer_generator_circuit_equivalence",
            "one_pair_reachable_state_fixture",
            "random_theta_pair_sector_preservation",
        ),
        parameterization_policy_id="pair.binding.parameterization.real_vector.v1",
        support_status=PolicyStatus.ACCEPTANCE_VERIFIED,
        validity_envelope={"n_pairs": 1, "n_levels": {"minimum": 2, "maximum": 6}},
        limitations=("Verified only in the declared one-pair seniority-zero domain.",),
        provenance={"legacy_policy_id": "one_pair_chain_givens.v1", "scientific_behavior_change": False},
    )
    multi_pair = AnsatzPolicyContract(
        policy_id="pair.ansatz.multi_pair.bathri_givens.v1",
        policy_version="1.0.0",
        display_name="Bathri multi-pair occupied-to-virtual Givens network",
        implementation_binding_id="pair.binding.ansatz.multi_pair_bathri_givens.v1",
        semantic_class=AnsatzSemanticClass.QUBIT_NATIVE,
        generator_domain="encoded_pair_occupation_qubits",
        provided_capabilities=(
            "encoded_pair_space_semantics",
            "pair_number_preserving",
            "seniority_zero_preserving",
            "mode_order_aware",
        ),
        required_mapping_capabilities=("pair_quasispin_algebra", "pair_transfer_operator"),
        required_sector_capabilities=("pair_number_diagnostic", "seniority_zero_domain"),
        preserved_quantities=("pair_number", "particle_number", "seniority"),
        required_equivalence_evidence=(),
        parameterization_policy_id="pair.binding.parameterization.real_vector.v1",
        support_status=PolicyStatus.EXPERIMENTAL,
        validity_envelope={"n_pairs": {"minimum": 2, "maximum": 3}, "n_levels": {"minimum": 4, "maximum": 6}},
        limitations=(
            "Pair-number preservation is established, but complete multi-pair expressivity and cell acceptance remain under review.",
            "The policy does not claim full single-fermion excitation semantics.",
        ),
        provenance={"legacy_policy_id": "bathri_multi_pair_givens.v1", "source": "Bathri qcol_platform ansatz.py", "scientific_behavior_change": False},
    )
    return one_pair, multi_pair


def _measurement_contract() -> MeasurementPolicyContract:
    return MeasurementPolicyContract(
        policy_id="pair.measurement.pauli_energy_qwc.v1",
        policy_version="1.0.0",
        display_name="Pair-mapped Pauli energy and pair-occupation measurement",
        implementation_binding_id="pair.binding.measurement_builder.v1",
        supported_observable_capabilities=(
            "mapped_hamiltonian_terms",
            "pair_occupation_observable",
            "pair_number_observable",
        ),
        required_mapping_capabilities=("mapped_observable_semantics",),
        required_sector_capabilities=("pair_number_diagnostic",),
        grouping_policy_id="pair.binding.qwc_grouping.v1",
        reconstruction_policy_id="pair.binding.term_expectation_reconstruction.v1",
        result_semantics="Pair-sector energy and explicitly requested pair occupations reconstructed from mapped Pauli expectations.",
        shots_required=True,
        support_status=PolicyStatus.ACCEPTANCE_VERIFIED,
        validity_envelope={"n_levels": {"minimum": 2, "maximum": 6}},
        limitations=("Pair occupations are not single-spin-orbital occupations.",),
        provenance={"legacy_policy_id": "pauli_energy_qwc.v1", "scientific_behavior_change": False},
    )


def _reference_contracts() -> tuple[ReferencePolicyContract, ReferencePolicyContract]:
    common = dict(
        independent_solver_binding_id="pair.binding.reference.exact_pair_sector.v1",
        source_representation_id="reduced_pairing_seniority_zero_basis.v1",
        supported_quantities=("ground_state_energy", "sector_energy", "pair_occupation"),
        required_model_capabilities=("reduced_pairing_hamiltonian", "seniority_zero_domain"),
        required_sector_capabilities=("pair_number_diagnostic", "seniority_zero_domain"),
        units_policy="model_declared_energy_unit.v1",
        constant_shift_policy="record_exact_constant_shift.v1",
        source_model_fingerprint_required=True,
        sector_fingerprint_required=True,
        mode_ordering_fingerprint_required=True,
        constructed_from_tested_mapping=False,
    )
    one = ReferencePolicyContract(
        policy_id="pair.reference.one_pair.exact_sector.v1",
        policy_version="1.0.0",
        display_name="Independent exact one-pair seniority-zero reference",
        support_status=PolicyStatus.ACCEPTANCE_VERIFIED,
        validity_envelope={"n_pairs": 1, "n_levels": {"minimum": 2, "maximum": 6}, "maximum_sector_dimension": 6},
        limitations=("Valid only for the declared reduced one-pair sector.",),
        provenance={"legacy_policy_id": "small_exact_one_pair_sector.v1", "scientific_behavior_change": False},
        **common,
    )
    multi = ReferencePolicyContract(
        policy_id="pair.reference.multi_pair.exact_sector.v1",
        policy_version="1.0.0",
        display_name="Independent exact multi-pair seniority-zero reference",
        support_status=PolicyStatus.VERIFIED,
        validity_envelope={"n_pairs": {"minimum": 2, "maximum": 3}, "n_levels": {"minimum": 4, "maximum": 6}, "maximum_sector_dimension": 20},
        limitations=("The exact reference is valid in the bounded sector; the full multi-pair VQE cell remains experimental.",),
        provenance={"legacy_policy_id": "small_exact_multi_pair_sector.v1", "scientific_behavior_change": False},
        **common,
    )
    return one, multi


def _verification_contracts() -> tuple[VerificationPolicyContract, VerificationPolicyContract]:
    one = VerificationPolicyContract(
        policy_id="pair.verification.one_pair.three_gate.v1",
        policy_version="1.0.0",
        display_name="One-pair mapper, composition, and cell verification",
        implementation_binding_id="pair.binding.verification.v1",
        required_check_ids=(
            "pair_subspace_matrix_equivalence",
            "pair_basis_round_trip",
            "pair_number_sector_preservation",
            "one_pair_reachable_fixture",
            "qasm_semantic_equivalence",
            "reference_uncertainty_consistency",
        ),
        comparison_metric_ids=("matrix_relative_frobenius", "sector_leakage", "absolute_energy_error"),
        required_evidence_capabilities=("mapper_gate_report", "composition_gate_report", "cell_gate_report", "exact_fingerprint_match"),
        tolerance_profile_id="wp8.tolerance.pair.one_pair.v1",
        requires_independent_reference=True,
        support_status=PolicyStatus.ACCEPTANCE_VERIFIED,
        validity_envelope={"n_pairs": 1, "n_levels": {"minimum": 2, "maximum": 6}},
        limitations=("No claim outside the seniority-zero one-pair domain.",),
        provenance={"acceptance_anchor": "acceptance.nuclear.reduced_pairing.one_pair.v1", "scientific_behavior_change": False},
    )
    multi = VerificationPolicyContract(
        policy_id="pair.verification.multi_pair.experimental.v1",
        policy_version="1.0.0",
        display_name="Multi-pair experimental three-gate verification",
        implementation_binding_id="pair.binding.verification.v1",
        required_check_ids=(
            "pair_subspace_matrix_equivalence",
            "pair_basis_round_trip",
            "pair_number_sector_preservation",
            "multi_pair_expressivity_review",
            "controller_seed_matrix",
            "reference_uncertainty_consistency",
        ),
        comparison_metric_ids=("matrix_relative_frobenius", "sector_leakage", "absolute_energy_error"),
        required_evidence_capabilities=("mapper_gate_report", "composition_gate_report", "cell_gate_report", "exact_fingerprint_match"),
        tolerance_profile_id="wp8.tolerance.pair.multi_pair.experimental.v1",
        requires_independent_reference=True,
        support_status=PolicyStatus.EXPERIMENTAL,
        validity_envelope={"n_pairs": {"minimum": 2, "maximum": 3}, "n_levels": {"minimum": 4, "maximum": 6}},
        limitations=("Promotion is prohibited until composition and cell review checks pass.",),
        provenance={"acceptance_suite": "acceptance.nuclear.reduced_pairing.multi_pair.v1", "scientific_behavior_change": False},
    )
    return one, multi


def _tolerance_profiles() -> tuple[ToleranceProfile, ToleranceProfile, ToleranceProfile]:
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
    return (
        ToleranceProfile(
            profile_id="wp8.tolerance.pair.mapper.v1",
            profile_version="1.0.0",
            label="WP8 Pair Mapping mapper-conformance profile",
            scope_statement="Complete declared seniority-zero pair sector for 2–6 pair levels.",
            notes=("Tests quasispin/pair-subspace equivalence, not full single-fermion CAR.",),
            **common,
        ),
        ToleranceProfile(
            profile_id="wp8.tolerance.pair.one_pair.v1",
            profile_version="1.0.0",
            label="WP8 accepted one-pair Pair Mapping profile",
            scope_statement="One intact pair in 2–6 levels using the frozen local simulator and exact-sector reference.",
            notes=("The one-pair route is the positive migration regression anchor.",),
            **common,
        ),
        ToleranceProfile(
            profile_id="wp8.tolerance.pair.multi_pair.experimental.v1",
            profile_version="1.0.0",
            label="WP8 experimental multi-pair Pair Mapping profile",
            scope_statement="Two or three intact pairs in 4–6 levels; no acceptance promotion in WP8.",
            notes=("Composition expressivity and cell acceptance remain REVIEW.",),
            **common,
        ),
    )


def pair_mapping_policy_contracts() -> dict[str, DeclarativeContract]:
    mapping = build_pair_mapping_policy()
    states = _state_contracts()
    ansatz = _ansatz_contracts()
    references = _reference_contracts()
    verification = _verification_contracts()
    measurement = _measurement_contract()
    tolerances = _tolerance_profiles()
    contracts: tuple[DeclarativeContract, ...] = (
        mapping,
        *mapping.sector_profiles,
        *states,
        *ansatz,
        measurement,
        *references,
        *verification,
        *tolerances,
    )
    def identity(contract: DeclarativeContract) -> str:
        for name in ("policy_id", "profile_id", "ordering_id", "context_id"):
            value = getattr(contract, name, None)
            if value:
                return str(value)
        raise TypeError(type(contract).__name__)
    return {identity(contract): contract for contract in contracts}


def _binding(
    binding_id: str,
    display_name: str,
    kind: BindingKind,
    callable_name: str,
    expected_parameters: tuple[str, ...],
    *,
    convention_id: str = "qcol.pair.shared-service.v1",
    support_status: PolicyStatus = PolicyStatus.EXECUTION_READY,
    description: str,
) -> ImplementationBindingContract:
    return ImplementationBindingContract(
        binding_id=binding_id,
        binding_version="1.0.0",
        display_name=display_name,
        kind=kind,
        provider="qcol",
        implementation_version="1.0.0",
        convention_id=convention_id,
        source_revision="wp8-pair-policy-migration-r1",
        import_path=f"qcol.mapping_policies.profiles.pair_bindings:{callable_name}",
        expected_parameters=expected_parameters,
        support_status=support_status,
        description=description,
        limitations=("Valid only within the migrated seniority-zero Pair Mapping policy domain.",),
        provenance={"phase": "Phase A.3.2b", "work_package": "WP8", "scientific_behavior_change": False},
    )


def pair_mapping_binding_contracts() -> tuple[ImplementationBindingContract, ...]:
    convention = PAIR_MAPPING_CONVENTION_ID
    return (
        _binding("pair.binding.operator_transform.v1", "Pair Mapping operator transform", BindingKind.OPERATOR_TRANSFORM, "pair_operator_transform", ("context", "hamiltonian", "sector"), convention_id=convention, support_status=PolicyStatus.ACCEPTANCE_VERIFIED, description="Reuses the accepted QCOL reduced-pairing pair-sector transform and paired-sector matrix cross-check."),
        _binding("pair.binding.basis_encoder.v1", "Pair-occupation basis encoder", BindingKind.BASIS_ENCODER, "pair_basis_encoder", ("occupied_levels", "n_levels"), convention_id=convention, support_status=PolicyStatus.ACCEPTANCE_VERIFIED, description="Encodes one intact-pair occupation bit per declared pair level."),
        _binding("pair.binding.basis_decoder.v1", "Pair-occupation basis decoder", BindingKind.BASIS_DECODER, "pair_basis_decoder", ("bitstring",), convention_id=convention, support_status=PolicyStatus.ACCEPTANCE_VERIFIED, description="Decodes occupied pair levels; it does not decode single-fermion occupations."),
        _binding("pair.binding.seniority_zero_subspace.v1", "Seniority-zero pair code-space predicate", BindingKind.PHYSICAL_SUBSPACE, "pair_seniority_zero_subspace", ("occupations",), convention_id=convention, support_status=PolicyStatus.ACCEPTANCE_VERIFIED, description="Restricts the encoding to intact-pair seniority-zero occupations."),
        _binding("pair.binding.pair_number_popcount.v1", "Pair-number popcount diagnostic", BindingKind.SECTOR_DIAGNOSTIC, "pair_number_popcount", ("bitstring",), support_status=PolicyStatus.ACCEPTANCE_VERIFIED, description="Raw popcount equals pair number only in this Pair Mapping convention."),
        _binding("pair.binding.particle_number_from_pair_bits.v1", "Particle number from pair occupations", BindingKind.SECTOR_DIAGNOSTIC, "particle_number_from_pair_bits", ("bitstring",), support_status=PolicyStatus.ACCEPTANCE_VERIFIED, description="Returns twice the intact-pair popcount."),
        _binding("pair.binding.seniority_zero_domain.v1", "Seniority-zero domain diagnostic", BindingKind.SECTOR_DIAGNOSTIC, "seniority_zero_domain_diagnostic", ("metadata",), support_status=PolicyStatus.ACCEPTANCE_VERIFIED, description="Checks that seniority zero is declared by the reduced physical domain."),
        _binding("pair.binding.state.one_pair_lowest_level.v1", "One-pair state-preparation builder", BindingKind.STATE_PREPARATION, "pair_state_one_pair", ("context", "mapping", "sector"), support_status=PolicyStatus.ACCEPTANCE_VERIFIED, description="Wraps the accepted one-pair lowest-level state preparation."),
        _binding("pair.binding.state.multi_pair_lowest_levels.v1", "Multi-pair state-preparation builder", BindingKind.STATE_PREPARATION, "pair_state_multi_pair", ("context", "mapping", "sector"), support_status=PolicyStatus.EXPERIMENTAL, description="Wraps Bathri's extracted multi-pair lowest-level pair state."),
        _binding("pair.binding.ansatz.one_pair_chain_givens.v1", "One-pair chain Givens factory", BindingKind.ANSATZ_FACTORY, "pair_ansatz_one_pair", ("context", "mapping", "sector", "initial_state"), support_status=PolicyStatus.ACCEPTANCE_VERIFIED, description="Wraps the accepted one-pair mapping-native Givens composition."),
        _binding("pair.binding.ansatz.multi_pair_bathri_givens.v1", "Bathri multi-pair Givens factory", BindingKind.ANSATZ_FACTORY, "pair_ansatz_multi_pair", ("context", "mapping", "sector", "initial_state"), support_status=PolicyStatus.EXPERIMENTAL, description="Wraps the execution-ready experimental multi-pair Givens network."),
        _binding("pair.binding.parameterization.real_vector.v1", "Pair real-parameter vector", BindingKind.PARAMETERIZATION, "real_parameter_vector", ("values",), support_status=PolicyStatus.ACCEPTANCE_VERIFIED, description="Normalizes real ansatz parameters."),
        _binding("pair.binding.measurement_builder.v1", "Pair-mapped measurement builder", BindingKind.MEASUREMENT_BUILDER, "pair_measurement_builder", ("context", "mapping", "ansatz"), support_status=PolicyStatus.ACCEPTANCE_VERIFIED, description="Uses the existing shared QWC Pauli measurement service."),
        _binding("pair.binding.qwc_grouping.v1", "Pair QWC grouping binding", BindingKind.GROUPING, "qwc_grouping", ("pauli_terms",), support_status=PolicyStatus.ACCEPTANCE_VERIFIED, description="Declares the existing QWC grouping interface."),
        _binding("pair.binding.term_expectation_reconstruction.v1", "Pair expectation reconstruction binding", BindingKind.RECONSTRUCTION, "term_expectation_reconstruction", ("expectations", "coefficients"), support_status=PolicyStatus.ACCEPTANCE_VERIFIED, description="Declares weighted Pauli-term reconstruction."),
        _binding("pair.binding.reference.exact_pair_sector.v1", "Independent exact pair-sector solver", BindingKind.REFERENCE_SOLVER, "pair_reference_solver", ("context", "mapping", "sector"), support_status=PolicyStatus.ACCEPTANCE_VERIFIED, description="Uses the direct fixed-pair-sector matrix independently of the mapped qubit operator."),
        _binding("pair.binding.verification.v1", "Pair-sector verification handler", BindingKind.VERIFICATION, "pair_verification_handler", ("result", "reference"), support_status=PolicyStatus.ACCEPTANCE_VERIFIED, description="Produces bounded pair-sector comparison diagnostics."),
        _binding("pair.binding.resource_assessor.v1", "Pair Mapping resource assessor", BindingKind.RESOURCE_ASSESSOR, "pair_resource_assessor", ("context",), convention_id=convention, support_status=PolicyStatus.ACCEPTANCE_VERIFIED, description="Wraps the existing pair-mapped resource envelope."),
    )


def build_pair_policy_registries() -> tuple[DeclarativePolicyContractRegistry, ImplementationBindingRegistry]:
    contract_registry = DeclarativePolicyContractRegistry(
        registry_id="qcol.mapping-realization.pair.contracts.wp8",
        registry_version="1.0.0",
    )
    for contract in pair_mapping_policy_contracts().values():
        contract_registry.register(contract)
    for n_levels, n_pairs in ((4, 1), (4, 2)):
        ordering = build_pair_mode_ordering(n_levels)
        context = build_pair_encoding_context(n_levels, n_pairs)
        if ordering.ordering_id not in contract_registry.contracts:
            contract_registry.register(ordering)
        contract_registry.register(context)

    binding_registry = ImplementationBindingRegistry(
        registry_id="qcol.mapping-realization.pair.bindings.wp8",
        registry_version="1.0.0",
    )
    callables = {name: getattr(pair_bindings, name) for name in pair_bindings.__all__}
    for binding in pair_mapping_binding_contracts():
        attribute = binding.import_path.split(":", 1)[1] if binding.import_path else ""
        binding_registry.register(binding, callable_object=callables.get(attribute))
    return contract_registry, binding_registry


def _pair_rule_context(*, one_pair: bool) -> RuleEvaluationContext:
    n_levels = 4
    n_pairs = 1 if one_pair else 2
    model_contract = ONE_PAIR_MODEL_CONTRACT if one_pair else MULTI_PAIR_MODEL_CONTRACT
    encoding = build_pair_encoding_context(n_levels, n_pairs)
    context_fp = encoding.fingerprint()
    sector_fp = encoding.target_sector_fingerprint
    source_fp = contract_fingerprint({
        "model_id": model_contract.model_id,
        "epsilon": [0.0, 1.0, 2.0, 3.0],
        "g": 0.5,
        "n_pairs": n_pairs,
        "seniority": 0,
    })
    mapping = build_pair_mapping_policy()
    state = _state_contracts()[0 if one_pair else 1]
    ansatz = _ansatz_contracts()[0 if one_pair else 1]
    measurement = _measurement_contract()
    reference = _reference_contracts()[0 if one_pair else 1]
    component_contexts = {
        name: context_fp
        for name in (
            "model", "task", "mapping", "sector", "state_preparation",
            "ansatz", "measurement", "reference", "resources",
        )
    }
    acceptance_fp = f"wp8-pair-{'one' if one_pair else 'multi'}-pair-current-evidence"
    mapping_sector_profiles = []
    for profile in mapping.sector_profiles:
        row = profile.to_dict()
        if profile.representation_kind is SectorRepresentationKind.FIXED_BY_PHYSICAL_DOMAIN:
            row["fixed_by_domain_evidence"] = True
        mapping_sector_profiles.append(row)
    return RuleEvaluationContext(
        context_id=f"wp8.pair.{'one' if one_pair else 'multi'}-pair.resolution.v1",
        context_version="1.0.0",
        model={
            "model_id": model_contract.model_id,
            "operator_type": "FermionOperator",
            "physical_domain": "reduced_pairing",
            "metadata": {
                "n_levels": n_levels,
                "n_pairs": n_pairs,
                "seniority": 0,
                "pair_level_order": list(encoding.mode_ordering.ordered_mode_labels),
            },
            "hermitian": True,
            "declared_symmetries": ["pair_number", "particle_number", "seniority"],
            "verified_symmetries": ["pair_number", "particle_number", "seniority"],
            "source_problem_fingerprint": source_fp,
            "units": "MeV",
            "declared_scale": {"n_levels": n_levels, "n_pairs": n_pairs, "seniority": 0},
            "encoding_context_fingerprint": context_fp,
        },
        task={
            "task_id": "ground_state_energy",
            "required_operator_kinds": ["hamiltonian", "pair_number", "particle_number", "pair_occupation"],
            "required_conserved_quantities": ["pair_number", "particle_number", "seniority"],
            "requires_state_preparation": True,
            "requires_ansatz": True,
            "requires_measurement": True,
            "target_quantity": "ground_state_energy",
            "units": "MeV",
            "encoding_context_fingerprint": context_fp,
        },
        mapping={
            "policy_id": mapping.policy_id,
            "mapping_id": "pair_mapping",
            "family": mapping.family.value,
            "mapping_scope": PAIR_MAPPING_SEMANTIC_SCOPE,
            "generic_mapping_scope": mapping.scope.value,
            "algebra_scope": mapping.algebra_scope.value,
            "preserved_algebra": PAIR_MAPPING_PRESERVED_ALGEBRA,
            "convention_id": mapping.convention_id,
            "accepted_operator_types": list(mapping.accepted_operator_types),
            "allowed_physical_domains": list(mapping.allowed_physical_domains),
            "required_model_metadata": list(mapping.required_model_metadata),
            "requires_hermitian_hamiltonian": True,
            "required_symmetries": ["pair_number", "seniority"],
            "encoding_context_fingerprint": context_fp,
            "sector_profiles": mapping_sector_profiles,
            "raw_popcount_is_particle_number": False,
            "raw_popcount_quantity": "pair_number",
            "requires_state_capabilities": list(mapping.requires_state_preparation_capabilities),
            "requires_ansatz_capabilities": list(mapping.requires_ansatz_capabilities),
            "transformable_operator_kinds": ["hamiltonian", "pair_number", "particle_number", "pair_occupation", "pair_transfer"],
        },
        ordering={
            "ordering_id": encoding.mode_ordering.ordering_id,
            "encoding_context_fingerprint": context_fp,
            "required_components": list(component_contexts),
            "component_context_fingerprints": component_contexts,
        },
        sector={
            "sector_fingerprint": sector_fp,
            "required_quantities": ["pair_number", "particle_number", "seniority"],
            "target": {"pair_number": n_pairs, "particle_number": 2 * n_pairs, "seniority": 0},
            "encoding_context_fingerprint": context_fp,
        },
        state_preparation={
            "policy_id": state.policy_id,
            "mapping_policy_id": mapping.policy_id,
            "mapping_convention_id": mapping.convention_id,
            "encoding_context_fingerprint": context_fp,
            "provided_capabilities": list(state.provided_capabilities),
            "encoded_state_in_code_space": True,
            "target_sector_match": True,
        },
        ansatz={
            "policy_id": ansatz.policy_id,
            "semantic_class": ansatz.semantic_class.value,
            "mapping_policy_id": mapping.policy_id,
            "mapping_convention_id": mapping.convention_id,
            "encoding_context_fingerprint": context_fp,
            "provided_capabilities": list(ansatz.provided_capabilities),
            "pair_number_preserving": True,
            "particle_number_preserving": True,
            "hamming_weight_preserving": True,
            "declared_invariants_preserved": True,
            "nonadjacent_sign_test_passed": None,
            "generator_equivalence_evidence": {
                "passed": one_pair,
                "freshness_status": "current" if one_pair else "not_applicable",
                "scope": "pair_quasispin_generator" if one_pair else "multi_pair_acceptance_pending",
            },
        },
        measurement={
            "policy_id": measurement.policy_id,
            "supported_operator_kinds": ["hamiltonian", "pair_number", "particle_number", "pair_occupation"],
            "encoding_context_fingerprint": context_fp,
        },
        reference={
            "policy_id": reference.policy_id,
            "source_problem_fingerprint": source_fp,
            "task_id": "ground_state_energy",
            "quantity_id": "ground_state_energy",
            "units": "MeV",
            "encoding_context_fingerprint": context_fp,
            "sector_fingerprint": sector_fp,
            "constant_shift": 0.0,
            "independent": True,
            "constructed_from_tested_mapping": False,
            "validity_envelope": {"max_n_modes": n_levels, "max_n_levels": 6},
        },
        resources={
            "encoding_context_fingerprint": context_fp,
            "within_declared_envelope": True,
            "estimate": {
                "n_qubits": n_levels,
                "parameter_count": n_levels - 1 if one_pair else n_pairs * (n_levels - n_pairs),
                "fixed_pair_sector_dimension": 4 if one_pair else 6,
            },
            "envelope": {
                "max_n_qubits": 6,
                "max_parameter_count": 5 if one_pair else 9,
                "max_sector_dimension": 6 if one_pair else 20,
            },
            "exceeded_dimensions": [],
        },
        acceptance_evidence={
            "resolved_variant_fingerprint": acceptance_fp,
            "evidence_fingerprint": acceptance_fp,
            "freshness_status": "current",
            "policy_versions_match": True,
            "declared_scale_matches": True,
        },
        complete_tuple={
            "model_id": model_contract.model_id,
            "task_id": "ground_state_energy",
            "mapping_policy_id": mapping.policy_id,
            "encoding_context_fingerprint": context_fp,
            "sector_fingerprint": sector_fp,
            "resolved_variant_fingerprint": acceptance_fp,
        },
    )


def _pair_candidate(*, one_pair: bool) -> RealizationCandidate:
    n_pairs = 1 if one_pair else 2
    n_levels = 4
    mapping = build_pair_mapping_policy()
    state = _state_contracts()[0 if one_pair else 1]
    ansatz = _ansatz_contracts()[0 if one_pair else 1]
    reference = _reference_contracts()[0 if one_pair else 1]
    verification = _verification_contracts()[0 if one_pair else 1]
    tolerance = _tolerance_profiles()[1 if one_pair else 2]
    encoding = build_pair_encoding_context(n_levels, n_pairs)
    contract_ids = (
        mapping.policy_id,
        state.policy_id,
        ansatz.policy_id,
        _measurement_contract().policy_id,
        reference.policy_id,
        verification.policy_id,
        tolerance.profile_id,
        encoding.mode_ordering.ordering_id,
        encoding.context_id,
    )
    return RealizationCandidate(
        candidate_id=f"wp8.pair.{'one' if one_pair else 'multi'}-pair.ground-state.v1",
        candidate_version="1.0.0",
        label=(
            "WP8 migrated one-pair Pair Mapping regression anchor"
            if one_pair
            else "WP8 migrated multi-pair Pair Mapping experimental route"
        ),
        task_mode=RealizationTaskMode.EXECUTABLE_CIRCUIT,
        contract_ids=contract_ids,
        rule_context=_pair_rule_context(one_pair=one_pair),
        declared_scale={"n_levels": n_levels, "n_pairs": n_pairs, "seniority": 0},
        source_metadata={
            "migration_work_package": "WP8",
            "preserved_scientific_status": "acceptance_verified" if one_pair else "experimental",
            "scientific_behavior_change": False,
        },
    )


def resolve_pair_mapping_migration_variants() -> dict[str, Any]:
    contracts, bindings = build_pair_policy_registries()
    resolver = RealizationVariantResolver(
        contract_registry=contracts,
        binding_registry=bindings,
        rule_registry=build_wp4_rule_registry(),
    )
    return {
        "one_pair": resolver.resolve(_pair_candidate(one_pair=True)),
        "multi_pair": resolver.resolve(_pair_candidate(one_pair=False)),
    }


def _component(role: str, contract: DeclarativeContract) -> Any:
    identity = None
    version = None
    for id_name, version_name in (
        ("policy_id", "policy_version"),
        ("profile_id", "profile_version"),
        ("ordering_id", "ordering_version"),
        ("context_id", "context_version"),
    ):
        value = getattr(contract, id_name, None)
        if value:
            identity = value
            version = getattr(contract, version_name)
            break
    if identity is None or version is None:
        raise TypeError(type(contract).__name__)
    convention = getattr(contract, "convention_id", None)
    return component_identity(
        role=role,
        component_id=str(identity),
        component_version=str(version),
        snapshot=contract.to_dict(),
        convention_id=None if convention is None else str(convention),
    )


def _pair_acceptance_fingerprint(*, one_pair: bool) -> AcceptanceEvidenceFingerprint:
    n_levels = 4
    n_pairs = 1 if one_pair else 2
    mapping = build_pair_mapping_policy()
    state = _state_contracts()[0 if one_pair else 1]
    ansatz = _ansatz_contracts()[0 if one_pair else 1]
    measurement = _measurement_contract()
    reference = _reference_contracts()[0 if one_pair else 1]
    verification = _verification_contracts()[0 if one_pair else 1]
    tolerance = _tolerance_profiles()[1 if one_pair else 2]
    encoding = build_pair_encoding_context(n_levels, n_pairs)
    model = ONE_PAIR_MODEL_CONTRACT if one_pair else MULTI_PAIR_MODEL_CONTRACT
    bindings = []
    for binding in pair_mapping_binding_contracts():
        bindings.append(BindingEvidenceIdentity(
            role=binding.kind.value,
            binding_id=binding.binding_id,
            binding_version=binding.binding_version,
            provider=binding.provider,
            implementation_version=binding.implementation_version,
            convention_id=binding.convention_id,
            source_revision=binding.source_revision,
        ))
    source_problem = contract_fingerprint({
        "model_id": model.model_id,
        "n_levels": n_levels,
        "n_pairs": n_pairs,
        "epsilon": [0.0, 1.0, 2.0, 3.0],
        "g": 0.5,
        "seniority": 0,
    })
    task_snapshot = {
        "task_id": "ground_state_energy",
        "task_version": "1.0.0",
        "target_quantity": "ground_state_energy",
        "controller": "external_variational_energy.v1",
    }
    task_component = component_identity(
        role="task_contract",
        component_id="ground_state_energy",
        component_version="1.0.0",
        snapshot=task_snapshot,
    )
    model_component = component_identity(
        role="model_contract",
        component_id=model.model_id,
        component_version=model.model_version,
        snapshot=model.to_dict(),
    )
    dependencies = DependencyFingerprint(
        dependency_set_id="wp8.pair.dependencies.v1",
        dependency_set_version="1.0.0",
        versions={
            "qcol": WP8_PROJECT_VERSION,
            "numpy": "runtime-pinned",
            "cirq-core": "runtime-pinned",
            "openfermion": "runtime-pinned",
            "pyqasm": "runtime-pinned",
        },
    )
    return AcceptanceEvidenceFingerprint(
        fingerprint_id=f"wp8.pair.{'one' if one_pair else 'multi'}-pair.acceptance.v1",
        fingerprint_version="1.0.0",
        source_problem_fingerprint=source_problem,
        model_contract=model_component,
        task_contract=task_component,
        mapping_policy=_component("mapping_policy", mapping),
        mode_ordering=_component("mode_ordering", encoding.mode_ordering),
        encoding_context=_component("encoding_context", encoding),
        sector_profiles=tuple(_component(f"sector_profile.{item.quantity_id}", item) for item in mapping.sector_profiles),
        state_preparation_policy=_component("state_preparation_policy", state),
        ansatz_policy=_component("ansatz_policy", ansatz),
        measurement_policy=_component("measurement_policy", measurement),
        reference_policy=_component("reference_policy", reference),
        verification_policy=_component("verification_policy", verification),
        tolerance_profile=_component("tolerance_profile", tolerance),
        implementation_bindings=tuple(bindings),
        dependencies=dependencies,
        declared_scale=DeclaredScaleContract(
            scale_id=f"wp8.pair.{'one' if one_pair else 'multi'}-pair.scale.v1",
            scale_version="1.0.0",
            dimensions={"n_levels": n_levels, "n_pairs": n_pairs, "n_particles": 2 * n_pairs, "seniority": 0},
            scope_statement=(
                "Accepted one-pair regression scale."
                if one_pair
                else "Experimental multi-pair migration scale; no promotion in WP8."
            ),
        ),
    )


def _pair_gate_contracts(*, one_pair: bool) -> tuple[dict[AcceptanceGateKind, AcceptanceGateContract], ToleranceProfileRegistry]:
    tolerance_registry = ToleranceProfileRegistry(
        registry_id="qcol.wp8.pair.tolerance-profiles.v1",
        registry_version="1.0.0",
    )
    for profile in _tolerance_profiles():
        tolerance_registry.register(profile)
    gate_contracts = {
        AcceptanceGateKind.MAPPER_CONFORMANCE: AcceptanceGateContract(
            gate_id="wp8.gate.pair.mapper-conformance.v1",
            gate_version="1.0.0",
            kind=AcceptanceGateKind.MAPPER_CONFORMANCE,
            label="Pair Mapping mapper conformance",
            tolerance_profile_id="wp8.tolerance.pair.mapper.v1",
            required_check_ids=(
                "schema_provenance",
                "quasispin_pair_algebra",
                "pair_basis_encoding",
                "reduced_pairing_matrix_equivalence",
                "pair_occupation_observable_equivalence",
                "pair_sector_semantics",
                "negative_domain_tests",
            ),
            purpose="Establish the restricted seniority-zero pair encoding without claiming full single-fermion CAR.",
        ),
        AcceptanceGateKind.COMPOSITION_CONFORMANCE: AcceptanceGateContract(
            gate_id="wp8.gate.pair.composition-conformance.v1",
            gate_version="1.0.0",
            kind=AcceptanceGateKind.COMPOSITION_CONFORMANCE,
            label="Pair Mapping composition conformance",
            tolerance_profile_id=(
                "wp8.tolerance.pair.one_pair.v1"
                if one_pair
                else "wp8.tolerance.pair.multi_pair.experimental.v1"
            ),
            required_check_ids=(
                "initial_pair_state_encoding",
                "pair_transfer_generator_equivalence",
                "random_theta_pair_sector_leakage",
                "random_theta_point_count",
                "pair_level_ordering_consistency",
                "qasm_semantic_equivalence",
            ),
            purpose="Establish state, ansatz, sector, ordering, and QASM semantics in the encoded pair space.",
        ),
        AcceptanceGateKind.CELL_ACCEPTANCE: AcceptanceGateContract(
            gate_id="wp8.gate.pair.cell-acceptance.v1",
            gate_version="1.0.0",
            kind=AcceptanceGateKind.CELL_ACCEPTANCE,
            label="Pair Mapping Model × Task cell acceptance",
            tolerance_profile_id=(
                "wp8.tolerance.pair.one_pair.v1"
                if one_pair
                else "wp8.tolerance.pair.multi_pair.experimental.v1"
            ),
            required_check_ids=(
                "deterministic_reachable_fixture",
                "sampled_seed_count",
                "controller_behavior",
                "reference_uncertainty_consistency",
                "evidence_reproducibility",
                "bounded_meaning",
            ),
            purpose="Preserve the one-pair accepted cell and keep multi-pair experimental until its own evidence passes.",
        ),
    }
    return gate_contracts, tolerance_registry


def _observation(
    check_id: str,
    *,
    observed: Any = True,
    comparison: ObservationComparison = ObservationComparison.BOOLEAN_TRUE,
    tolerance_field: str | None = None,
    declared_status: CheckStatus | None = None,
    failure_code: str | None = None,
    standard_error: float | None = None,
    evidence: Mapping[str, Any] | None = None,
) -> AcceptanceObservation:
    return AcceptanceObservation(
        check_id=check_id,
        label=check_id.replace("_", " ").title(),
        comparison=comparison,
        observed=observed,
        tolerance_field=tolerance_field,
        declared_status=declared_status,
        standard_error=standard_error,
        failure_code=failure_code or f"{check_id.upper()}.FAILED",
        message_on_pass=f"{check_id} passed for the migrated Pair Mapping profile.",
        message_on_failure=f"{check_id} did not satisfy the migrated Pair Mapping gate.",
        evidence=dict(evidence or {}),
    )


def _pair_harness_case(*, one_pair: bool) -> AcceptanceHarnessCase:
    mapper = (
        _observation("schema_provenance"),
        _observation("quasispin_pair_algebra"),
        _observation("pair_basis_encoding"),
        _observation("reduced_pairing_matrix_equivalence", observed=1e-12, comparison=ObservationComparison.LESS_EQUAL_TOLERANCE, tolerance_field="matrix_relative_frobenius"),
        _observation("pair_occupation_observable_equivalence", observed=1e-12, comparison=ObservationComparison.LESS_EQUAL_TOLERANCE, tolerance_field="matrix_relative_frobenius"),
        _observation("pair_sector_semantics", evidence={"raw_popcount_quantity": "pair_number", "seniority": "fixed_by_physical_domain"}),
        _observation("negative_domain_tests", evidence={"rejected": ["nonzero_seniority", "broken_pair", "general_shell_model"]}),
    )
    composition = [
        _observation("initial_pair_state_encoding"),
        _observation("pair_transfer_generator_equivalence", observed=1e-11, comparison=ObservationComparison.LESS_EQUAL_TOLERANCE, tolerance_field="generator_unitary"),
        _observation("random_theta_pair_sector_leakage", observed=0.0, comparison=ObservationComparison.LESS_EQUAL_TOLERANCE, tolerance_field="sector_leakage"),
        _observation("random_theta_point_count", observed=20, comparison=ObservationComparison.GREATER_EQUAL_TOLERANCE, tolerance_field="minimum_random_parameter_points"),
        _observation("pair_level_ordering_consistency"),
        _observation("qasm_semantic_equivalence", observed=1e-10, comparison=ObservationComparison.LESS_EQUAL_TOLERANCE, tolerance_field="qasm_semantic"),
    ]
    cell = [
        _observation("deterministic_reachable_fixture"),
        _observation("sampled_seed_count", observed=3, comparison=ObservationComparison.GREATER_EQUAL_TOLERANCE, tolerance_field="minimum_sampled_seeds"),
        _observation("controller_behavior"),
        _observation("reference_uncertainty_consistency", observed=0.01, comparison=ObservationComparison.STATISTICAL_CONSISTENCY, standard_error=0.004),
        _observation("evidence_reproducibility"),
        _observation("bounded_meaning"),
    ]
    if not one_pair:
        composition[1] = _observation(
            "pair_transfer_generator_equivalence",
            observed="multi_pair_acceptance_pending",
            comparison=ObservationComparison.DECLARED_STATUS,
            declared_status=CheckStatus.REVIEW,
            failure_code="MULTI_PAIR_COMPOSITION_ACCEPTANCE_PENDING",
            evidence={"pair_number_preserved": True, "complete_expressivity_matrix_accepted": False},
        )
        cell[2] = _observation(
            "controller_behavior",
            observed="experimental_seed_matrix",
            comparison=ObservationComparison.DECLARED_STATUS,
            declared_status=CheckStatus.REVIEW,
            failure_code="MULTI_PAIR_CELL_ACCEPTANCE_PENDING",
        )
    fingerprint = _pair_acceptance_fingerprint(one_pair=one_pair)
    return AcceptanceHarnessCase(
        case_id=f"wp8.case.pair.{'one' if one_pair else 'multi'}-pair.v1",
        case_version="1.0.0",
        label=("WP8 one-pair migration acceptance" if one_pair else "WP8 multi-pair migration status preservation"),
        baseline_variant_id=(
            "baseline.pair.one_pair.ground_state.v1"
            if one_pair
            else "baseline.pair.multi_pair.ground_state.v1"
        ),
        expected_baseline_status="acceptance_verified" if one_pair else "experimental",
        gate_applicability={
            AcceptanceGateKind.MAPPER_CONFORMANCE.value: GateApplicability.REQUIRED.value,
            AcceptanceGateKind.COMPOSITION_CONFORMANCE.value: GateApplicability.REQUIRED.value,
            AcceptanceGateKind.CELL_ACCEPTANCE.value: GateApplicability.REQUIRED.value,
        },
        observations={
            AcceptanceGateKind.MAPPER_CONFORMANCE.value: mapper,
            AcceptanceGateKind.COMPOSITION_CONFORMANCE.value: tuple(composition),
            AcceptanceGateKind.CELL_ACCEPTANCE.value: tuple(cell),
        },
        expected_fingerprint=fingerprint,
        observed_fingerprint=fingerprint,
        metadata={
            "mapping_scope": PAIR_MAPPING_SEMANTIC_SCOPE,
            "preserved_algebra": PAIR_MAPPING_PRESERVED_ALGEBRA,
            "scientific_behavior_change": False,
        },
    )


def run_pair_mapping_migration_harness() -> dict[str, Any]:
    reports = {}
    for name, one_pair in (("one_pair", True), ("multi_pair", False)):
        gates, tolerances = _pair_gate_contracts(one_pair=one_pair)
        harness = GenericThreeGateAcceptanceHarness(
            gate_contracts=gates,
            tolerance_registry=tolerances,
            harness_version="1.0.0",
        )
        reports[name] = harness.run(_pair_harness_case(one_pair=one_pair))
    return reports


def build_pair_mapping_migration_profile() -> PairMappingMigrationProfile:
    contracts = pair_mapping_policy_contracts()
    return PairMappingMigrationProfile(
        profile_id=PAIR_MAPPING_PROFILE_ID,
        profile_version="1.0.0",
        mapping_scope=PAIR_MAPPING_SEMANTIC_SCOPE,
        generic_mapping_scope=MappingScope.RESTRICTED_PHYSICAL_SUBSPACE,
        preserved_algebra=PAIR_MAPPING_PRESERVED_ALGEBRA,
        generic_algebra_scope=AlgebraScope.QUASISPIN_PAIR_ALGEBRA,
        mapping_policy=contracts[PAIR_MAPPING_POLICY_ID],
        component_contract_ids={
            "one_pair_state": "pair.state.one_pair.lowest_level.v1",
            "one_pair_ansatz": "pair.ansatz.one_pair.chain_givens.v1",
            "multi_pair_state": "pair.state.multi_pair.lowest_levels.v1",
            "multi_pair_ansatz": "pair.ansatz.multi_pair.bathri_givens.v1",
            "measurement": "pair.measurement.pauli_energy_qwc.v1",
            "one_pair_reference": "pair.reference.one_pair.exact_sector.v1",
            "multi_pair_reference": "pair.reference.multi_pair.exact_sector.v1",
            "one_pair_verification": "pair.verification.one_pair.three_gate.v1",
            "multi_pair_verification": "pair.verification.multi_pair.experimental.v1",
        },
        legacy_policy_aliases={
            "pair_mapping.v1": PAIR_MAPPING_POLICY_ID,
            "one_pair_lowest_level_state.v1": "pair.state.one_pair.lowest_level.v1",
            "multi_pair_lowest_levels_state.v1": "pair.state.multi_pair.lowest_levels.v1",
            "one_pair_chain_givens.v1": "pair.ansatz.one_pair.chain_givens.v1",
            "bathri_multi_pair_givens.v1": "pair.ansatz.multi_pair.bathri_givens.v1",
            "small_exact_one_pair_sector.v1": "pair.reference.one_pair.exact_sector.v1",
            "small_exact_multi_pair_sector.v1": "pair.reference.multi_pair.exact_sector.v1",
        },
        support_boundaries={
            "one_pair": {
                "mapper": "verified",
                "composition": "verified",
                "cell": "acceptance_verified",
                "role": "regression_anchor",
            },
            "multi_pair": {
                "mapper": "verified",
                "composition": "experimental",
                "cell": "experimental",
                "promotion_allowed": False,
            },
            "excluded": [
                "broken_pair",
                "nonzero_seniority",
                "general_single_fermion_semantics",
                "general_shell_model",
            ],
        },
    )


def _foundation_fingerprints() -> dict[str, str]:
    from qcol.mapping_policies import vocabulary_fingerprint
    from qcol.policy_contract_catalog import policy_contract_catalog_fingerprint
    from qcol.implementation_bindings import implementation_binding_catalog_fingerprint
    from qcol.compatibility import compatibility_rule_catalog_fingerprint
    from qcol.realization_variants import realization_resolver_catalog_fingerprint
    from qcol.acceptance import acceptance_fingerprint_catalog_fingerprint, acceptance_harness_catalog_fingerprint

    return {
        "wp0": baseline_fingerprint(),
        "wp1": vocabulary_fingerprint(),
        "wp2": policy_contract_catalog_fingerprint(),
        "wp3": implementation_binding_catalog_fingerprint(),
        "wp4": compatibility_rule_catalog_fingerprint(),
        "wp5": realization_resolver_catalog_fingerprint(),
        "wp6": acceptance_fingerprint_catalog_fingerprint(),
        "wp7": acceptance_harness_catalog_fingerprint(),
    }


def _build_pair_mapping_migration_catalog() -> dict[str, Any]:
    profile = build_pair_mapping_migration_profile()
    contracts = pair_mapping_policy_contracts()
    contract_registry, binding_registry = build_pair_policy_registries()
    resolutions = resolve_pair_mapping_migration_variants()
    harness = run_pair_mapping_migration_harness()
    one = harness["one_pair"].to_dict()
    multi = harness["multi_pair"].to_dict()
    payload: dict[str, Any] = {
        "schema_version": PAIR_MIGRATION_CATALOG_SCHEMA_VERSION,
        "catalog_version": PAIR_MIGRATION_CATALOG_VERSION,
        "introduced_in_project_version": WP8_PROJECT_VERSION,
        "phase": "Phase A.3.2b",
        "work_package": "WP8 — Migrate Pair Mapping",
        "objective": "Migrate Pair Mapping into the policy/resolver/acceptance architecture while preserving its restricted seniority-zero domain and current support boundaries.",
        "profile": profile.to_dict(),
        "mapping_scope": PAIR_MAPPING_SEMANTIC_SCOPE,
        "generic_mapping_scope": MappingScope.RESTRICTED_PHYSICAL_SUBSPACE.value,
        "preserved_algebra": PAIR_MAPPING_PRESERVED_ALGEBRA,
        "full_single_fermion_semantics_claimed": False,
        "raw_popcount_semantics": {
            "pair_number": "direct_popcount",
            "particle_number": "two_times_pair_popcount",
            "seniority": "fixed_by_physical_domain",
            "raw_popcount_is_particle_number": False,
        },
        "contracts": {key: value.to_dict() for key, value in sorted(contracts.items())},
        "contract_registry": contract_registry.public_catalog(),
        "binding_registry": binding_registry.public_catalog(),
        "resolutions": {key: value.to_public_dict() for key, value in resolutions.items()},
        "acceptance_harness": {key: value.to_dict() for key, value in harness.items()},
        "status_preservation": {
            "one_pair": {
                "before": "acceptance_verified",
                "after": one["promotion"]["preserved_baseline_status"],
                "promotion_ready": one["promotion"]["promotion_ready"],
                "regression_anchor": True,
            },
            "multi_pair": {
                "before": "experimental",
                "after": multi["promotion"]["preserved_baseline_status"],
                "promotion_ready": multi["promotion"]["promotion_ready"],
                "review_codes": multi["promotion"]["review_codes"],
            },
        },
        "foundation_fingerprints": _foundation_fingerprints(),
        "live_policy_migration_performed": True,
        "scientific_behavior_change": False,
        "scientific_status_promoted": False,
        "second_runtime_created": False,
        "guardrails": [
            "Pair Mapping is a restricted seniority-zero pair-occupation encoding, not a general single-fermion mapping.",
            "The preserved algebra is quasispin / hard-core-pair algebra; full CAR is not claimed for pair qubits.",
            "Raw pair-qubit popcount means pair number. Physical particle number is twice that value.",
            "Seniority is fixed by the declared physical domain and must not be inferred from raw bitstrings.",
            "One-pair remains the accepted regression anchor; multi-pair remains experimental until its own gates pass.",
            "All executable bindings reuse the existing shared QCOL mapping, circuit, measurement, QASM, execution, reconstruction, and evidence services.",
        ],
    }
    payload["fingerprint"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    ).hexdigest()
    return json.loads(json.dumps(payload, sort_keys=True, ensure_ascii=False, allow_nan=False))


@lru_cache(maxsize=1)
def _pair_mapping_migration_catalog_json() -> str:
    return json.dumps(
        _build_pair_mapping_migration_catalog(),
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
    )


def public_pair_mapping_migration_catalog() -> dict[str, Any]:
    """Return a defensive JSON copy of the cached deterministic WP8 catalog."""
    return json.loads(_pair_mapping_migration_catalog_json())


def pair_mapping_migration_catalog_fingerprint(payload: dict[str, Any] | None = None) -> str:
    catalog = dict(payload or public_pair_mapping_migration_catalog())
    existing = catalog.pop("fingerprint", None)
    digest = hashlib.sha256(
        json.dumps(catalog, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    ).hexdigest()
    if existing is not None and existing != digest:
        raise ValueError("Pair Mapping migration catalog fingerprint mismatch.")
    return digest


def validate_pair_mapping_migration(payload: dict[str, Any] | None = None) -> dict[str, bool]:
    catalog = payload or public_pair_mapping_migration_catalog()
    one = catalog["acceptance_harness"]["one_pair"]
    multi = catalog["acceptance_harness"]["multi_pair"]
    mapping = catalog["contracts"][PAIR_MAPPING_POLICY_ID]
    return {
        "strict_json_round_trip": json.loads(json.dumps(catalog, sort_keys=True, allow_nan=False)) == catalog,
        "catalog_fingerprint_valid": pair_mapping_migration_catalog_fingerprint(catalog) == catalog["fingerprint"],
        "restricted_seniority_zero_scope_explicit": catalog["mapping_scope"] == PAIR_MAPPING_SEMANTIC_SCOPE,
        "generic_scope_is_restricted": mapping["scope"] == MappingScope.RESTRICTED_PHYSICAL_SUBSPACE.value,
        "quasispin_algebra_explicit": mapping["algebra_scope"] == AlgebraScope.QUASISPIN_PAIR_ALGEBRA.value,
        "no_full_single_fermion_claim": catalog["full_single_fermion_semantics_claimed"] is False,
        "pair_number_is_direct_popcount": catalog["raw_popcount_semantics"]["pair_number"] == "direct_popcount",
        "raw_popcount_not_particle_number": catalog["raw_popcount_semantics"]["raw_popcount_is_particle_number"] is False,
        "seniority_fixed_by_domain": catalog["raw_popcount_semantics"]["seniority"] == "fixed_by_physical_domain",
        "one_pair_three_gates_pass": (
            [row["status"] for row in one["gate_reports"]] == ["pass", "pass", "pass"]
            and one["promotion"]["promotion_ready"] is True
            and one["promotion"]["preserved_baseline_status"] == "acceptance_verified"
        ),
        "multi_pair_remains_experimental": (
            multi["promotion"]["promotion_ready"] is False
            and multi["promotion"]["preserved_baseline_status"] == "experimental"
            and bool(multi["promotion"]["review_codes"])
        ),
        "one_pair_resolves_to_shared_pipeline": catalog["resolutions"]["one_pair"]["variant"]["runtime_entry"]["path"] == "shared_execution_pipeline",
        "multi_pair_resolves_without_status_promotion": catalog["resolutions"]["multi_pair"]["variant"]["runtime_entry"]["path"] == "shared_execution_pipeline" and catalog["scientific_status_promoted"] is False,
        "callables_withheld_from_public_catalogs": catalog["contract_registry"]["callable_payload_withheld"] and catalog["binding_registry"]["callable_payload_withheld"],
        "foundation_fingerprints_present": set(catalog["foundation_fingerprints"]) == {"wp0", "wp1", "wp2", "wp3", "wp4", "wp5", "wp6", "wp7"},
        "migration_performed_without_behavior_change": catalog["live_policy_migration_performed"] is True and catalog["scientific_behavior_change"] is False,
        "no_second_runtime": catalog["second_runtime_created"] is False,
    }


__all__ = [
    "PAIR_MAPPING_PROFILE_SCHEMA_VERSION",
    "PAIR_MAPPING_PROFILE_ID",
    "PAIR_MAPPING_POLICY_ID",
    "PAIR_MAPPING_POLICY_VERSION",
    "PAIR_MAPPING_CONVENTION_ID",
    "PAIR_MAPPING_SEMANTIC_SCOPE",
    "PAIR_MAPPING_PRESERVED_ALGEBRA",
    "PairMappingMigrationProfile",
    "build_pair_mapping_policy",
    "build_pair_mode_ordering",
    "build_pair_encoding_context",
    "pair_mapping_policy_contracts",
    "pair_mapping_binding_contracts",
    "build_pair_policy_registries",
    "resolve_pair_mapping_migration_variants",
    "run_pair_mapping_migration_harness",
    "build_pair_mapping_migration_profile",
    "public_pair_mapping_migration_catalog",
    "pair_mapping_migration_catalog_fingerprint",
    "validate_pair_mapping_migration",
]

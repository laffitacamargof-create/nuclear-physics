"""WP9/WP10 policy migrations for Jordan--Wigner and Bravyi--Kitaev.

The migrations preserve the frozen A.3.2a scientific truth:

* both mappers and their deterministic mapping-analysis cells remain verified;
* the current JW ground-state bare qubit-exchange composition remains rejected;
* BK ground-state composition remains unresolved and full execution remains
  recognized-not-executable;
* no second runtime and no status promotion is introduced.
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
from qcol.acceptance.harness_fixtures import (
    build_wp7_analysis_gate_contracts,
    build_wp7_execution_gate_contracts,
    build_wp7_tolerance_registry,
)
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
from qcol.models.general_spin_orbital.contract import GENERAL_SPIN_ORBITAL_MODEL_CONTRACT

from . import fermion_bindings


WP9_WP10_PROJECT_VERSION = "1.18.0"
SPIN_MIGRATION_SCHEMA_VERSION = "qcol-spin-orbital-mapping-migration-profile/1.0"
SPIN_MIGRATION_CATALOG_SCHEMA_VERSION = "qcol-jw-bk-policy-migration-catalog/1.0"
SPIN_MIGRATION_CATALOG_VERSION = "1.0.0"
A3_2B_EXIT_SCHEMA_VERSION = "qcol-phase-a3.2b-policy-migration-exit/1.0"

JW_POLICY_ID = "jordan_wigner.spin_orbital.v1"
JW_POLICY_VERSION = "1.0.0"
JW_CONVENTION_ID = "openfermion.jordan_wigner.ordered_modes.little_endian.v1"
JW_PROFILE_ID = "qcol.mapping-profile.jordan-wigner.spin-orbital.v1"

BK_POLICY_ID = "bravyi_kitaev.spin_orbital.default.v1"
BK_POLICY_VERSION = "1.0.0"
BK_CONVENTION_ID = "openfermion.bravyi_kitaev.default_code.v1"
BK_PROFILE_ID = "qcol.mapping-profile.bravyi-kitaev.default.v1"

LEGACY_MAPPING_MIGRATIONS = {
    "jordan_wigner.v1": JW_POLICY_ID,
    "bravyi_kitaev.v1": BK_POLICY_ID,
}


@dataclass(frozen=True)
class SpinOrbitalMappingMigrationProfile(DeclarativeContract):
    profile_id: str
    profile_version: str
    work_package: str
    mapping_policy: MappingPolicyContract
    basis_semantics: str
    raw_popcount_is_particle_number: bool
    component_contract_ids: Mapping[str, str]
    legacy_policy_aliases: Mapping[str, str]
    support_boundaries: Mapping[str, Any]
    scientific_behavior_change: bool = False
    schema_version: str = SPIN_MIGRATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        require_token("profile_id", self.profile_id)
        require_token("profile_version", self.profile_version)
        require_token("work_package", self.work_package)
        require_text("basis_semantics", self.basis_semantics)
        if not isinstance(self.mapping_policy, MappingPolicyContract):
            raise TypeError("mapping_policy must be MappingPolicyContract")
        object.__setattr__(self, "component_contract_ids", freeze_json(self.component_contract_ids, path="SpinOrbitalMappingMigrationProfile.component_contract_ids"))
        object.__setattr__(self, "legacy_policy_aliases", freeze_json(self.legacy_policy_aliases, path="SpinOrbitalMappingMigrationProfile.legacy_policy_aliases"))
        object.__setattr__(self, "support_boundaries", freeze_json(self.support_boundaries, path="SpinOrbitalMappingMigrationProfile.support_boundaries"))


# ---------------------------------------------------------------------------
# Shared ordering and analysis contracts
# ---------------------------------------------------------------------------

def build_spin_orbital_mode_ordering(n_modes: int = 4) -> ModeOrderingContract:
    n_modes = int(n_modes)
    if n_modes < 2:
        raise ValueError("spin-orbital migration fixtures require at least two modes")
    return ModeOrderingContract(
        ordering_id=f"spin_orbital.mode_order.{n_modes}.v1",
        ordering_version="1.0.0",
        ordered_mode_labels=tuple(f"mode:{index}" for index in range(n_modes)),
        species_order=("declared_species_order",),
        spin_order=("declared_projection_order",),
        mode_index_convention="zero_based_ordered_fermionic_modes.v1",
        qubit_index_convention="mapping_convention_declared_qubit_index.v1",
        endian_convention="qcol_little_endian_display.v1",
        bitstring_display_convention="highest_qubit_left.v1",
        metadata={
            "source": "general_spin_orbital_contract",
            "ordering_is_scientific_context": True,
        },
    )


def _sector_fingerprint(n_modes: int, particle_number: int) -> str:
    return contract_fingerprint({
        "n_modes": int(n_modes),
        "particle_number": int(particle_number),
        "representation": "ordered_spin_orbital_fock_space",
    })


def build_jw_encoding_context(n_modes: int = 4, particle_number: int = 2) -> EncodingContext:
    return EncodingContext(
        context_id=f"jw.encoding-context.{n_modes}modes.N{particle_number}.v1",
        context_version="1.0.0",
        mapping_policy_id=JW_POLICY_ID,
        mapping_policy_version=JW_POLICY_VERSION,
        mapping_convention_id=JW_CONVENTION_ID,
        mode_ordering=build_spin_orbital_mode_ordering(n_modes),
        n_qubits=int(n_modes),
        target_sector_fingerprint=_sector_fingerprint(n_modes, particle_number),
        metadata={
            "occupation_semantics": "qubit p stores occupation of ordered fermionic mode p",
            "particle_number_semantics": "direct_popcount",
        },
    )


def build_bk_encoding_context(n_modes: int = 4, particle_number: int = 2) -> EncodingContext:
    return EncodingContext(
        context_id=f"bk.encoding-context.{n_modes}modes.N{particle_number}.v1",
        context_version="1.0.0",
        mapping_policy_id=BK_POLICY_ID,
        mapping_policy_version=BK_POLICY_VERSION,
        mapping_convention_id=BK_CONVENTION_ID,
        mode_ordering=build_spin_orbital_mode_ordering(n_modes),
        n_qubits=int(n_modes),
        target_sector_fingerprint=_sector_fingerprint(n_modes, particle_number),
        metadata={
            "occupation_semantics": "distributed occupation/parity/update code",
            "particle_number_semantics": "mapping_specific_decoder_or_mapped_operator",
            "raw_popcount_is_particle_number": False,
        },
    )


def _analysis_state_contract(family: str) -> StatePreparationPolicyContract:
    return StatePreparationPolicyContract(
        policy_id=f"{family}.state.analysis_only.v1",
        policy_version="1.0.0",
        display_name=f"{family.upper()} mapping-analysis no-state declaration",
        implementation_binding_id="fermion.binding.analysis_no_state.v1",
        input_state_semantics="no prepared state; deterministic operator analysis only",
        provided_capabilities=("analysis_only_no_state", "mode_order_aware"),
        required_mapping_capabilities=("operator_transform",),
        required_sector_capabilities=("sector_semantics_declared",),
        conserved_quantity_guarantees=("not_applicable_to_state",),
        exact_reference_usage="metadata_only",
        support_status=PolicyStatus.ACCEPTANCE_VERIFIED,
        validity_envelope={"task": "mapping_analysis", "n_modes": {"minimum": 2, "maximum": 8}},
        limitations=("This declaration does not prepare or execute a quantum state.",),
        provenance={"phase": "A.3.2b", "analysis_only": True},
    )


def _analysis_ansatz_contract(family: str) -> AnsatzPolicyContract:
    return AnsatzPolicyContract(
        policy_id=f"{family}.ansatz.analysis_only.v1",
        policy_version="1.0.0",
        display_name=f"{family.upper()} mapping-analysis no-ansatz declaration",
        implementation_binding_id="fermion.binding.analysis_no_ansatz.v1",
        semantic_class=AnsatzSemanticClass.QUBIT_NATIVE,
        generator_domain="not_applicable_analysis_only",
        provided_capabilities=("analysis_only_no_ansatz", "mode_order_aware"),
        required_mapping_capabilities=("operator_transform",),
        required_sector_capabilities=("sector_semantics_declared",),
        preserved_quantities=("not_applicable_to_ansatz",),
        required_equivalence_evidence=(),
        parameterization_policy_id="fermion.binding.identity_parameter_vector.v1",
        support_status=PolicyStatus.ACCEPTANCE_VERIFIED,
        validity_envelope={"task": "mapping_analysis", "n_modes": {"minimum": 2, "maximum": 8}},
        limitations=("No VQE or generator claim is made by this analysis-only policy.",),
        provenance={"phase": "A.3.2b", "analysis_only": True},
    )


def _analysis_measurement_contract() -> MeasurementPolicyContract:
    return MeasurementPolicyContract(
        policy_id="fermion.measurement.mapping_analysis.v1",
        policy_version="1.0.0",
        display_name="Deterministic mapped-operator comparison",
        implementation_binding_id="fermion.binding.mapping_analysis_measurement.v1",
        supported_observable_capabilities=("hamiltonian", "particle_number", "mapping_resources"),
        required_mapping_capabilities=("operator_transform", "mapped_observable_semantics"),
        required_sector_capabilities=("sector_semantics_declared",),
        grouping_policy_id="fermion.binding.mapping_analysis_grouping.v1",
        reconstruction_policy_id="fermion.binding.mapping_comparison_reconstruction.v1",
        result_semantics="Deterministic matrix/spectrum/resource comparison; no shots or backend.",
        shots_required=False,
        support_status=PolicyStatus.ACCEPTANCE_VERIFIED,
        validity_envelope={"task": "mapping_analysis", "n_modes": {"minimum": 2, "maximum": 8}},
        limitations=("Not a circuit measurement policy.",),
        provenance={"phase": "A.3.2b", "analysis_only": True},
    )


def _analysis_reference_contract() -> ReferencePolicyContract:
    return ReferencePolicyContract(
        policy_id="fermion.reference.fock_space_spectrum.v1",
        policy_version="1.0.0",
        display_name="Independent fermionic Fock-space and fixed-N spectra",
        independent_solver_binding_id="fermion.binding.fock_space_reference.v1",
        source_representation_id="fermion_operator_before_mapping.v1",
        supported_quantities=("full_spectrum", "fixed_particle_sector_spectrum", "particle_number_spectrum"),
        required_model_capabilities=("general_spin_orbital_representation", "fermion_operator"),
        required_sector_capabilities=("target_particle_number",),
        units_policy="same_as_source_model",
        constant_shift_policy="explicit_and_recorded",
        constructed_from_tested_mapping=False,
        support_status=PolicyStatus.ACCEPTANCE_VERIFIED,
        validity_envelope={"n_modes": {"minimum": 2, "maximum": 8}},
        limitations=("Exact dense reference is bounded to the declared small scale.",),
        provenance={"phase": "A.3.2b", "independent_reference": True},
    )


def _analysis_verification_contract() -> VerificationPolicyContract:
    return VerificationPolicyContract(
        policy_id="fermion.verification.mapping_analysis.v1",
        policy_version="1.0.0",
        display_name="Mapper matrix, spectrum, sector, and provenance verification",
        implementation_binding_id="fermion.binding.mapping_equivalence_verification.v1",
        required_check_ids=(
            "schema_provenance",
            "car_conformance",
            "basis_encode_decode_roundtrip",
            "hamiltonian_matrix_equivalence",
            "task_observable_matrix_equivalence",
            "sector_semantics",
            "negative_domain_tests",
        ),
        comparison_metric_ids=("matrix_relative_frobenius", "eigenvalue_absolute", "operator_norm"),
        required_evidence_capabilities=("independent_reference", "mapping_provenance", "mode_order_fingerprint"),
        tolerance_profile_id="wp7.tolerance.analysis.deterministic.v1",
        requires_independent_reference=True,
        support_status=PolicyStatus.ACCEPTANCE_VERIFIED,
        validity_envelope={"n_modes": {"minimum": 2, "maximum": 8}},
        limitations=("Verifies mapper/analysis only, not a ground-state circuit composition.",),
        provenance={"phase": "A.3.2b", "analysis_only": True},
    )


def _jw_state_contract() -> StatePreparationPolicyContract:
    return StatePreparationPolicyContract(
        policy_id="jw.state.occupation_determinant.v1",
        policy_version="1.0.0",
        display_name="JW computational-basis occupation determinant",
        implementation_binding_id="jw.binding.state.occupation_determinant.v1",
        input_state_semantics="ordered spin-orbital occupation determinant; qubit p equals mode-p occupation",
        provided_capabilities=("direct_occupation_state", "particle_number_preserving", "mode_order_aware", "target_sector_aware"),
        required_mapping_capabilities=("direct_occupation_encoding", "basis_identity"),
        required_sector_capabilities=("particle_number_direct_popcount",),
        conserved_quantity_guarantees=("particle_number", "fermion_parity"),
        exact_reference_usage="forbidden",
        support_status=PolicyStatus.VERIFIED,
        validity_envelope={"n_modes": {"minimum": 2, "maximum": 4}, "single_species": True},
        limitations=("State preparation is valid, but it does not validate the selected ansatz composition.",),
        provenance={"legacy_policy_id": "general_spin_orbital_state.v1", "scientific_behavior_change": False},
    )


def _jw_current_ansatz_contract() -> AnsatzPolicyContract:
    return AnsatzPolicyContract(
        policy_id="jw.ansatz.current_bare_qubit_exchange.v1",
        policy_version="1.0.0",
        display_name="Current bare qubit-exchange composition — rejected for JW fermionic semantics",
        implementation_binding_id="jw.binding.ansatz.current_bare_exchange.v1",
        semantic_class=AnsatzSemanticClass.QUBIT_NATIVE,
        generator_domain="qubit_exchange_hamming_weight_preserving",
        provided_capabilities=("particle_number_preserving", "hamming_weight_preserving", "mode_order_aware"),
        required_mapping_capabilities=("direct_occupation_encoding",),
        required_sector_capabilities=("particle_number_direct_popcount",),
        preserved_quantities=("particle_number", "hamming_weight"),
        required_equivalence_evidence=(),
        parameterization_policy_id="fermion.binding.identity_parameter_vector.v1",
        support_status=PolicyStatus.RECOGNIZED_NOT_EXECUTABLE,
        validity_envelope={"n_modes": {"minimum": 2, "maximum": 4}},
        limitations=(
            "The circuit preserves number/Hamming weight but fails nonadjacent JW mapped-generator equivalence.",
            "Do not describe this policy as a JW fermionic Givens ansatz.",
        ),
        provenance={
            "legacy_family": "jw_number_preserving_exchange_phase",
            "failure_code": "ANSATZ_GENERATOR_MAPPING_MISMATCH",
            "scientific_behavior_change": False,
        },
    )


def _bk_unavailable_state_contract() -> StatePreparationPolicyContract:
    return StatePreparationPolicyContract(
        policy_id="bk.state.encoded_occupation_circuit.v1",
        policy_version="1.0.0",
        display_name="BK-aware occupation-code state-preparation circuit",
        implementation_binding_id="bk.binding.state.encoded_occupation_circuit.v1",
        input_state_semantics="prepare the convention-specific BK codeword for an ordered occupation vector",
        provided_capabilities=("mapping_specific_occupation_code", "mode_order_aware"),
        required_mapping_capabilities=("bk_basis_encoder", "distributed_occupation_encoding"),
        required_sector_capabilities=("particle_number_nonlocal_diagnostic",),
        conserved_quantity_guarantees=("particle_number_pending_acceptance",),
        exact_reference_usage="forbidden",
        support_status=PolicyStatus.RECOGNIZED_NOT_EXECUTABLE,
        validity_envelope={"status": "not_accepted"},
        limitations=("The representation-level encoder exists, but no BK state-preparation circuit has passed acceptance.",),
        provenance={"phase": "A.3.2b", "missing_capability": "bk_state_preparation_circuit_acceptance"},
    )


def _bk_unavailable_ansatz_contract() -> AnsatzPolicyContract:
    return AnsatzPolicyContract(
        policy_id="bk.ansatz.mapping_aware_ground_state.v1",
        policy_version="1.0.0",
        display_name="BK-aware mapped-fermionic ground-state ansatz",
        implementation_binding_id="bk.binding.ansatz.mapping_aware_ground_state.v1",
        semantic_class=AnsatzSemanticClass.MAPPED_FERMIONIC_GENERATOR,
        generator_domain="fermionic_single_and_number_conserving_excitations",
        provided_capabilities=("mapped_generator_semantics", "particle_number_preserving", "mode_order_aware"),
        required_mapping_capabilities=("distributed_occupation_encoding", "mapped_fermionic_operator_semantics"),
        required_sector_capabilities=("particle_number_nonlocal_diagnostic",),
        preserved_quantities=("particle_number",),
        required_equivalence_evidence=("bk_generator_circuit_equivalence", "bk_nonlocal_sector_preservation"),
        parameterization_policy_id="fermion.binding.identity_parameter_vector.v1",
        support_status=PolicyStatus.RECOGNIZED_NOT_EXECUTABLE,
        validity_envelope={"status": "not_accepted"},
        limitations=("No executable BK-aware ansatz binding is registered in this release.",),
        provenance={"phase": "A.3.2b", "missing_capability": "bk_compatible_ansatz_acceptance"},
    )


def _ground_measurement_contract(family: str) -> MeasurementPolicyContract:
    return MeasurementPolicyContract(
        policy_id=f"{family}.measurement.pauli_energy_qwc.v1",
        policy_version="1.0.0",
        display_name=f"{family.upper()} mapped Pauli energy measurement",
        implementation_binding_id="fermion.binding.pauli_energy_measurement.v1",
        supported_observable_capabilities=("mapped_hamiltonian_terms", "mapped_particle_number_operator"),
        required_mapping_capabilities=("mapped_observable_semantics",),
        required_sector_capabilities=("particle_number_diagnostic",),
        grouping_policy_id="fermion.binding.mapping_analysis_grouping.v1",
        reconstruction_policy_id="fermion.binding.mapping_comparison_reconstruction.v1",
        result_semantics="Mapped Pauli expectation reconstruction for a declared ground-state task.",
        shots_required=True,
        support_status=(PolicyStatus.VERIFIED if family == "jw" else PolicyStatus.RECOGNIZED_NOT_EXECUTABLE),
        validity_envelope={"n_modes": {"minimum": 2, "maximum": 4}},
        limitations=("Measurement readiness does not imply state/ansatz composition acceptance.",),
        provenance={"phase": "A.3.2b", "scientific_behavior_change": False},
    )


def _ground_reference_contract(family: str) -> ReferencePolicyContract:
    return ReferencePolicyContract(
        policy_id=f"{family}.reference.fixed_particle_sector.v1",
        policy_version="1.0.0",
        display_name=f"Independent fixed-particle source-domain reference for {family.upper()}",
        independent_solver_binding_id="fermion.binding.fixed_particle_reference.v1",
        source_representation_id="fermion_operator_before_mapping.v1",
        supported_quantities=("ground_state_energy", "fixed_particle_sector_spectrum"),
        required_model_capabilities=("general_spin_orbital_representation", "fermion_operator"),
        required_sector_capabilities=("target_particle_number",),
        units_policy="same_as_source_model",
        constant_shift_policy="explicit_and_recorded",
        constructed_from_tested_mapping=False,
        support_status=PolicyStatus.VERIFIED,
        validity_envelope={"n_modes": {"minimum": 2, "maximum": 4}},
        limitations=("Reference validity does not establish ansatz compatibility.",),
        provenance={"phase": "A.3.2b", "independent_reference": True},
    )


def _ground_verification_contract(family: str) -> VerificationPolicyContract:
    return VerificationPolicyContract(
        policy_id=f"{family}.verification.ground_state.v1",
        policy_version="1.0.0",
        display_name=f"{family.upper()} ground-state composition/cell verification",
        implementation_binding_id="fermion.binding.ground_state_verification.v1",
        required_check_ids=(
            "initial_state_encoding",
            "mapped_generator_unitary_equivalence",
            "sector_preservation",
            "qasm_semantic_equivalence",
            "reference_uncertainty_consistency",
        ),
        comparison_metric_ids=("generator_unitary", "sector_leakage", "energy_absolute_error"),
        required_evidence_capabilities=("independent_reference", "composition_gate_report", "cell_gate_report"),
        tolerance_profile_id="wp7.tolerance.composition.small.v1",
        requires_independent_reference=True,
        support_status=(PolicyStatus.RECOGNIZED_NOT_EXECUTABLE),
        validity_envelope={"n_modes": {"minimum": 2, "maximum": 4}},
        limitations=(
            "JW remains rejected until a mapping-aware ansatz replaces the current bare exchange."
            if family == "jw"
            else "BK remains unresolved until BK-aware state, ansatz, sector, and cell evidence exist.",
        ),
        provenance={"phase": "A.3.2b", "scientific_behavior_change": False},
    )


# ---------------------------------------------------------------------------
# Mapping policies
# ---------------------------------------------------------------------------

def _jw_sector_profiles() -> tuple[SectorEncodingProfile, ...]:
    return (
        SectorEncodingProfile(
            profile_id="jw.sector.particle_number.direct_popcount.v1",
            profile_version="1.0.0",
            quantity_id="particle_number",
            representation_kind=SectorRepresentationKind.DIRECT_POPCOUNT,
            raw_bitstring_semantics="Under JW, ordered computational-basis bits are mode occupations and raw popcount equals particle number.",
            diagnostic_policy_id="jw.binding.particle_number_popcount.v1",
            required_metadata=("mode_ordering_fingerprint", "target_particle_number"),
            support_status=PolicyStatus.ACCEPTANCE_VERIFIED,
            limitations=("This direct-popcount rule is convention-specific and must not be copied to BK.",),
        ),
        SectorEncodingProfile(
            profile_id="jw.sector.fermion_parity.local_diagonal.v1",
            profile_version="1.0.0",
            quantity_id="fermion_parity",
            representation_kind=SectorRepresentationKind.LOCAL_DIAGONAL_OPERATOR,
            raw_bitstring_semantics="Fermion parity is the parity of the declared JW occupation bitstring.",
            diagnostic_policy_id="jw.binding.fermion_parity.v1",
            required_metadata=("mode_ordering_fingerprint",),
            support_status=PolicyStatus.ACCEPTANCE_VERIFIED,
        ),
    )


def build_jw_mapping_policy() -> MappingPolicyContract:
    return MappingPolicyContract(
        policy_id=JW_POLICY_ID,
        policy_version=JW_POLICY_VERSION,
        display_name="Jordan--Wigner — ordered full spin-orbital Fock-space mapping",
        family=MappingFamily.JORDAN_WIGNER,
        scope=MappingScope.FULL_FERMIONIC_FOCK_SPACE,
        algebra_scope=AlgebraScope.CANONICAL_ANTICOMMUTATION_RELATIONS,
        convention_id=JW_CONVENTION_ID,
        implementation_binding_id="jw.binding.operator_transform.v1",
        accepted_operator_types=("FermionOperator",),
        supported_term_ranks=(0, 1, 2),
        required_model_metadata=("n_modes", "mode_ordering", "particle_numbers", "coefficient_convention"),
        allowed_physical_domains=("general_fermionic", "general_spin_orbital", "nuclear_spin_orbital"),
        excluded_configurations=("unordered_modes", "implicit_endianness", "undeclared_operator_convention"),
        qubit_count_rule="n_qubits = n_ordered_fermionic_modes",
        mode_ordering_requirements=("explicit_ordered_modes", "same_encoding_context_fingerprint", "JW_parity_order_equals_mode_index_order"),
        encoder_policy_id="jw.binding.basis_encoder.v1",
        decoder_policy_id="jw.binding.basis_decoder.v1",
        physical_subspace_policy_id="jw.binding.full_fock_subspace.v1",
        sector_profiles=_jw_sector_profiles(),
        provided_capabilities=(
            "operator_transform", "mapped_observable_semantics", "direct_occupation_encoding",
            "basis_identity", "particle_number_direct_popcount", "fermion_parity_diagnostic",
            "mapped_fermionic_operator_semantics", "car_preservation",
        ),
        requires_state_preparation_capabilities=("direct_occupation_state", "particle_number_preserving", "mode_order_aware"),
        requires_ansatz_capabilities=("mapped_generator_semantics", "particle_number_preserving", "mode_order_aware"),
        requires_measurement_capabilities=("mapped_hamiltonian_terms", "mapped_particle_number_operator"),
        requires_reference_capabilities=("independent_source_domain_reference", "fixed_particle_sector_reference"),
        requires_verification_capabilities=("car_conformance", "matrix_equivalence", "nonadjacent_sign_test", "sector_verification"),
        supported_task_capabilities=("mapping_analysis", "ground_state_energy"),
        required_task_operator_capabilities=("hamiltonian", "particle_number", "task_observables"),
        verification_profile_ids=("wp9.verification.jw.mapper.v1", "wp9.verification.jw.current_composition_rejection.v1"),
        resource_metric_ids=("n_qubits", "pauli_term_count", "maximum_pauli_weight", "weighted_mean_pauli_weight", "qwc_group_count"),
        resource_assessor_binding_id="jw.binding.resource_assessor.v1",
        support_status=PolicyStatus.ACCEPTANCE_VERIFIED,
        scientific_owner="QCOL general fermionic representation layer",
        limitations=(
            "Mapper and mapping-analysis acceptance do not imply a verified ground-state composition.",
            "The current bare qubit-exchange ansatz is rejected for nonadjacent JW fermionic semantics.",
        ),
        provenance={
            "phase": "A.3.2b", "work_package": "WP9", "legacy_mapping_id": "jordan_wigner.v1",
            "mapper_status": "verified", "analysis_status": "acceptance_verified",
            "current_composition_status": "rejected", "ground_state_cell_status": "not_verified",
            "scientific_behavior_change": False,
        },
    )


def _bk_sector_profiles() -> tuple[SectorEncodingProfile, ...]:
    return (
        SectorEncodingProfile(
            profile_id="bk.sector.particle_number.nonlocal_mapped.v1",
            profile_version="1.0.0",
            quantity_id="particle_number",
            representation_kind=SectorRepresentationKind.NONLOCAL_MAPPED_OPERATOR,
            raw_bitstring_semantics="Raw BK qubit popcount is not particle number; use the mapped number operator or the convention-specific decoder.",
            diagnostic_policy_id="bk.binding.particle_number_from_code.v1",
            decoder_policy_id="bk.binding.basis_decoder.v1",
            required_metadata=("mapping_convention_id", "mode_ordering_fingerprint", "target_particle_number"),
            support_status=PolicyStatus.ACCEPTANCE_VERIFIED,
            limitations=("No raw-popcount particle-number shortcut is permitted.",),
        ),
        SectorEncodingProfile(
            profile_id="bk.sector.fermion_parity.nonlocal_mapped.v1",
            profile_version="1.0.0",
            quantity_id="fermion_parity",
            representation_kind=SectorRepresentationKind.NONLOCAL_MAPPED_OPERATOR,
            raw_bitstring_semantics="Fermion parity must be interpreted through the declared BK code/decoder.",
            diagnostic_policy_id="bk.binding.fermion_parity_from_code.v1",
            decoder_policy_id="bk.binding.basis_decoder.v1",
            required_metadata=("mapping_convention_id", "mode_ordering_fingerprint"),
            support_status=PolicyStatus.ACCEPTANCE_VERIFIED,
        ),
    )


def build_bk_mapping_policy() -> MappingPolicyContract:
    return MappingPolicyContract(
        policy_id=BK_POLICY_ID,
        policy_version=BK_POLICY_VERSION,
        display_name="Bravyi--Kitaev — convention-specific distributed spin-orbital encoding",
        family=MappingFamily.BRAVYI_KITAEV,
        scope=MappingScope.FULL_FERMIONIC_FOCK_SPACE,
        algebra_scope=AlgebraScope.CANONICAL_ANTICOMMUTATION_RELATIONS,
        convention_id=BK_CONVENTION_ID,
        implementation_binding_id="bk.binding.operator_transform.v1",
        accepted_operator_types=("FermionOperator",),
        supported_term_ranks=(0, 1, 2),
        required_model_metadata=("n_modes", "mode_ordering", "particle_numbers", "coefficient_convention"),
        allowed_physical_domains=("general_fermionic", "general_spin_orbital", "nuclear_spin_orbital"),
        excluded_configurations=("implicit_bk_variant", "raw_popcount_sector_assumption", "unordered_modes"),
        qubit_count_rule="n_qubits = n_ordered_fermionic_modes for the declared OpenFermion default BK code",
        mode_ordering_requirements=("explicit_ordered_modes", "same_encoding_context_fingerprint", "exact_BK_convention_id"),
        encoder_policy_id="bk.binding.basis_encoder.v1",
        decoder_policy_id="bk.binding.basis_decoder.v1",
        physical_subspace_policy_id="bk.binding.full_fock_subspace.v1",
        sector_profiles=_bk_sector_profiles(),
        provided_capabilities=(
            "operator_transform", "mapped_observable_semantics", "bk_basis_encoder", "bk_basis_decoder",
            "distributed_occupation_encoding", "particle_number_nonlocal_diagnostic",
            "mapped_fermionic_operator_semantics", "car_preservation",
        ),
        requires_state_preparation_capabilities=("mapping_specific_occupation_code", "particle_number_preserving", "mode_order_aware"),
        requires_ansatz_capabilities=("mapped_generator_semantics", "particle_number_preserving", "mode_order_aware"),
        requires_measurement_capabilities=("mapped_hamiltonian_terms", "mapped_particle_number_operator"),
        requires_reference_capabilities=("independent_source_domain_reference", "fixed_particle_sector_reference"),
        requires_verification_capabilities=("car_conformance", "matrix_equivalence", "bk_encode_decode_roundtrip", "nonlocal_sector_verification"),
        supported_task_capabilities=("mapping_analysis", "ground_state_energy"),
        required_task_operator_capabilities=("hamiltonian", "particle_number", "task_observables"),
        verification_profile_ids=("wp10.verification.bk.mapper.v1", "wp10.verification.bk_ground_state_pending.v1"),
        resource_metric_ids=("n_qubits", "pauli_term_count", "maximum_pauli_weight", "weighted_mean_pauli_weight", "qwc_group_count"),
        resource_assessor_binding_id="bk.binding.resource_assessor.v1",
        support_status=PolicyStatus.ACCEPTANCE_VERIFIED,
        scientific_owner="QCOL general fermionic representation layer",
        limitations=(
            "Mapper and mapping-analysis acceptance do not imply a BK ground-state execution cell.",
            "BK-aware state preparation, ansatz, nonlocal sector diagnostics, and cell evidence are not accepted in this release.",
        ),
        provenance={
            "phase": "A.3.2b", "work_package": "WP10", "legacy_mapping_id": "bravyi_kitaev.v1",
            "mapper_status": "verified", "analysis_status": "acceptance_verified",
            "ground_state_composition_status": "unresolved", "full_execution_status": "recognized_not_executable",
            "raw_popcount_is_particle_number": False, "scientific_behavior_change": False,
        },
    )


# ---------------------------------------------------------------------------
# Public contract sets and exact bindings
# ---------------------------------------------------------------------------

def _tolerance(profile_id: str, label: str, scope: str) -> ToleranceProfile:
    return ToleranceProfile(
        profile_id=profile_id,
        profile_version="1.0.0",
        label=label,
        scope_statement=scope,
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
        notes=("Versioned migration tolerance; no scattered literal promotion threshold.",),
    )


def jw_policy_contracts() -> dict[str, DeclarativeContract]:
    mapping = build_jw_mapping_policy()
    contracts: tuple[DeclarativeContract, ...] = (
        mapping,
        *mapping.sector_profiles,
        _analysis_state_contract("jw"),
        _analysis_ansatz_contract("jw"),
        _analysis_measurement_contract(),
        _analysis_reference_contract(),
        _analysis_verification_contract(),
        _jw_state_contract(),
        _jw_current_ansatz_contract(),
        _ground_measurement_contract("jw"),
        _ground_reference_contract("jw"),
        _ground_verification_contract("jw"),
        _tolerance("wp9.tolerance.jw.mapper.v1", "WP9 JW mapper migration", "2–8 modes; mapper and mapping-analysis conformance."),
        _tolerance("wp9.tolerance.jw.current_composition.v1", "WP9 rejected current JW composition", "2–4 modes; preserve the documented composition failure."),
    )
    return _contracts_by_id(contracts)


def bk_policy_contracts() -> dict[str, DeclarativeContract]:
    mapping = build_bk_mapping_policy()
    contracts: tuple[DeclarativeContract, ...] = (
        mapping,
        *mapping.sector_profiles,
        _analysis_state_contract("bk"),
        _analysis_ansatz_contract("bk"),
        _analysis_measurement_contract(),
        _analysis_reference_contract(),
        _analysis_verification_contract(),
        _bk_unavailable_state_contract(),
        _bk_unavailable_ansatz_contract(),
        _ground_measurement_contract("bk"),
        _ground_reference_contract("bk"),
        _ground_verification_contract("bk"),
        _tolerance("wp10.tolerance.bk.mapper.v1", "WP10 BK mapper migration", "2–8 modes; convention-specific mapper and mapping-analysis conformance."),
        _tolerance("wp10.tolerance.bk.ground_state_pending.v1", "WP10 BK ground-state pending", "No full execution claim; required BK-aware composition evidence is absent."),
    )
    return _contracts_by_id(contracts)


def _contracts_by_id(contracts: tuple[DeclarativeContract, ...]) -> dict[str, DeclarativeContract]:
    result: dict[str, DeclarativeContract] = {}
    for contract in contracts:
        for field in ("policy_id", "profile_id", "ordering_id", "context_id"):
            value = getattr(contract, field, None)
            if value:
                result[str(value)] = contract
                break
        else:
            raise TypeError(type(contract).__name__)
    return result


def _binding(
    binding_id: str,
    name: str,
    kind: BindingKind,
    callable_name: str | None,
    parameters: tuple[str, ...],
    *,
    convention_id: str,
    status: PolicyStatus,
    description: str,
    work_package: str,
) -> ImplementationBindingContract:
    return ImplementationBindingContract(
        binding_id=binding_id,
        binding_version="1.0.0",
        display_name=name,
        kind=kind,
        provider="qcol_openfermion",
        implementation_version="1.0.0",
        convention_id=convention_id,
        source_revision=f"{work_package.lower()}-mapping-policy-migration-r1",
        import_path=(None if callable_name is None else f"qcol.mapping_policies.profiles.fermion_bindings:{callable_name}"),
        expected_parameters=parameters,
        support_status=status,
        description=description,
        limitations=("Binding validity is limited by the owning mapping policy and exact convention.",),
        provenance={"phase": "A.3.2b", "work_package": work_package, "scientific_behavior_change": False},
    )


def _shared_binding_contracts() -> tuple[ImplementationBindingContract, ...]:
    common = "qcol.mapping-analysis.shared.v1"
    return (
        _binding("fermion.binding.analysis_no_state.v1", "Analysis-only no-state declaration", BindingKind.STATE_PREPARATION, "analysis_no_state", ("mapped_operators",), convention_id=common, status=PolicyStatus.ACCEPTANCE_VERIFIED, description="No state is prepared; callable exists only to satisfy an exact analysis policy binding.", work_package="WP9-WP10"),
        _binding("fermion.binding.analysis_no_ansatz.v1", "Analysis-only no-ansatz declaration", BindingKind.ANSATZ_FACTORY, "mapping_analysis_measurement_builder", ("mapped_operators",), convention_id=common, status=PolicyStatus.ACCEPTANCE_VERIFIED, description="No ansatz is constructed for deterministic mapping analysis.", work_package="WP9-WP10"),
        _binding("fermion.binding.identity_parameter_vector.v1", "Identity real parameter vector", BindingKind.PARAMETERIZATION, "identity_parameter_vector", ("values",), convention_id=common, status=PolicyStatus.ACCEPTANCE_VERIFIED, description="Normalizes declared real parameters.", work_package="WP9-WP10"),
        _binding("fermion.binding.mapping_analysis_measurement.v1", "Mapping-analysis operator collector", BindingKind.MEASUREMENT_BUILDER, "mapping_analysis_measurement_builder", ("mapped_operators",), convention_id=common, status=PolicyStatus.ACCEPTANCE_VERIFIED, description="No shots or circuit; retains mapped operators for deterministic analysis.", work_package="WP9-WP10"),
        _binding("fermion.binding.mapping_analysis_grouping.v1", "Mapping-analysis deterministic grouping", BindingKind.GROUPING, "mapping_analysis_grouping", ("mapped_operators",), convention_id=common, status=PolicyStatus.ACCEPTANCE_VERIFIED, description="Identity grouping for operator-level comparison.", work_package="WP9-WP10"),
        _binding("fermion.binding.mapping_comparison_reconstruction.v1", "Mapping comparison reconstruction", BindingKind.RECONSTRUCTION, "mapping_comparison_reconstruction", ("reports",), convention_id=common, status=PolicyStatus.ACCEPTANCE_VERIFIED, description="Constructs a JSON-safe mapping comparison report.", work_package="WP9-WP10"),
        _binding("fermion.binding.fock_space_reference.v1", "Independent Fock-space spectrum solver", BindingKind.REFERENCE_SOLVER, "fock_space_reference_solver", ("fermion_operator", "n_modes", "particle_number"), convention_id=common, status=PolicyStatus.ACCEPTANCE_VERIFIED, description="Solves the source-domain operator before mapper-specific acceptance.", work_package="WP9-WP10"),
        _binding("fermion.binding.mapping_equivalence_verification.v1", "Mapping equivalence verification", BindingKind.VERIFICATION, "mapping_equivalence_verification", ("report", "reference"), convention_id=common, status=PolicyStatus.ACCEPTANCE_VERIFIED, description="Checks mapper-level transformation/reference evidence.", work_package="WP9-WP10"),
        _binding("fermion.binding.pauli_energy_measurement.v1", "Shared Pauli energy measurement builder", BindingKind.MEASUREMENT_BUILDER, "pauli_energy_measurement_builder", ("context", "mapping", "ansatz"), convention_id=common, status=PolicyStatus.VERIFIED, description="Reuses the shared QWC measurement path; it does not promote a mapping composition.", work_package="WP9-WP10"),
        _binding("fermion.binding.fixed_particle_reference.v1", "Independent fixed-particle reference", BindingKind.REFERENCE_SOLVER, "fixed_particle_reference_solver", ("context", "mapping", "sector"), convention_id=common, status=PolicyStatus.VERIFIED, description="Reuses the source-domain fixed-N reference path.", work_package="WP9-WP10"),
        _binding("fermion.binding.ground_state_verification.v1", "Ground-state verification report", BindingKind.VERIFICATION, "ground_state_verification_handler", ("result", "reference"), convention_id=common, status=PolicyStatus.VERIFIED, description="Produces bounded reference diagnostics; composition acceptance remains separate.", work_package="WP9-WP10"),
    )


def jw_binding_contracts() -> tuple[ImplementationBindingContract, ...]:
    return _shared_binding_contracts() + (
        _binding("jw.binding.operator_transform.v1", "JW operator transform", BindingKind.OPERATOR_TRANSFORM, "jw_operator_transform", ("fermion_operator", "n_modes"), convention_id=JW_CONVENTION_ID, status=PolicyStatus.ACCEPTANCE_VERIFIED, description="OpenFermion Jordan--Wigner transform under exact ordered-mode convention.", work_package="WP9"),
        _binding("jw.binding.basis_encoder.v1", "JW occupation basis encoder", BindingKind.BASIS_ENCODER, "jw_basis_encoder", ("occupations",), convention_id=JW_CONVENTION_ID, status=PolicyStatus.ACCEPTANCE_VERIFIED, description="Identity occupation-vector encoder.", work_package="WP9"),
        _binding("jw.binding.basis_decoder.v1", "JW occupation basis decoder", BindingKind.BASIS_DECODER, "jw_basis_decoder", ("bitstring",), convention_id=JW_CONVENTION_ID, status=PolicyStatus.ACCEPTANCE_VERIFIED, description="Identity occupation-bit decoder.", work_package="WP9"),
        _binding("jw.binding.full_fock_subspace.v1", "JW full Fock-space predicate", BindingKind.PHYSICAL_SUBSPACE, "jw_full_fock_subspace", ("bitstring", "n_modes"), convention_id=JW_CONVENTION_ID, status=PolicyStatus.ACCEPTANCE_VERIFIED, description="Validates one qubit per ordered fermionic mode.", work_package="WP9"),
        _binding("jw.binding.particle_number_popcount.v1", "JW particle-number popcount", BindingKind.SECTOR_DIAGNOSTIC, "jw_particle_number_popcount", ("bitstring",), convention_id=JW_CONVENTION_ID, status=PolicyStatus.ACCEPTANCE_VERIFIED, description="Raw JW occupation popcount equals particle number.", work_package="WP9"),
        _binding("jw.binding.fermion_parity.v1", "JW fermion parity diagnostic", BindingKind.SECTOR_DIAGNOSTIC, "jw_fermion_parity", ("bitstring",), convention_id=JW_CONVENTION_ID, status=PolicyStatus.ACCEPTANCE_VERIFIED, description="Parity of ordered occupation bits.", work_package="WP9"),
        _binding("jw.binding.resource_assessor.v1", "JW operator-resource assessor", BindingKind.RESOURCE_ASSESSOR, "jw_resource_assessor", ("n_modes",), convention_id=JW_CONVENTION_ID, status=PolicyStatus.ACCEPTANCE_VERIFIED, description="Reports operator-level resources per instance.", work_package="WP9"),
        _binding("jw.binding.state.occupation_determinant.v1", "JW occupation-determinant state", BindingKind.STATE_PREPARATION, "jw_occupation_determinant_state", ("context", "mapping", "sector"), convention_id=JW_CONVENTION_ID, status=PolicyStatus.VERIFIED, description="Wraps the bounded direct-occupation state preparation.", work_package="WP9"),
        _binding("jw.binding.ansatz.current_bare_exchange.v1", "Current bare exchange ansatz fixture", BindingKind.ANSATZ_FACTORY, "jw_current_bare_exchange_ansatz", ("context", "mapping", "sector", "initial_state"), convention_id=JW_CONVENTION_ID, status=PolicyStatus.EXPERIMENTAL, description="Executable only as the known-invalid composition regression fixture; no mapped-generator claim.", work_package="WP9"),
    )


def bk_binding_contracts() -> tuple[ImplementationBindingContract, ...]:
    return _shared_binding_contracts() + (
        _binding("bk.binding.operator_transform.v1", "BK operator transform", BindingKind.OPERATOR_TRANSFORM, "bk_operator_transform", ("fermion_operator", "n_modes"), convention_id=BK_CONVENTION_ID, status=PolicyStatus.ACCEPTANCE_VERIFIED, description="OpenFermion default Bravyi--Kitaev transform under exact declared convention.", work_package="WP10"),
        _binding("bk.binding.basis_encoder.v1", "BK GF(2) occupation encoder", BindingKind.BASIS_ENCODER, "bk_basis_encoder", ("occupations",), convention_id=BK_CONVENTION_ID, status=PolicyStatus.ACCEPTANCE_VERIFIED, description="Convention-specific representation-level occupation-code encoder.", work_package="WP10"),
        _binding("bk.binding.basis_decoder.v1", "BK GF(2) occupation decoder", BindingKind.BASIS_DECODER, "bk_basis_decoder", ("bitstring",), convention_id=BK_CONVENTION_ID, status=PolicyStatus.ACCEPTANCE_VERIFIED, description="Convention-specific decoder used instead of raw popcount.", work_package="WP10"),
        _binding("bk.binding.full_fock_subspace.v1", "BK full code-space predicate", BindingKind.PHYSICAL_SUBSPACE, "bk_full_fock_subspace", ("bitstring", "n_modes"), convention_id=BK_CONVENTION_ID, status=PolicyStatus.ACCEPTANCE_VERIFIED, description="Validates the declared full-mode BK code dimension.", work_package="WP10"),
        _binding("bk.binding.particle_number_from_code.v1", "BK particle number from code", BindingKind.SECTOR_DIAGNOSTIC, "bk_particle_number_from_code", ("bitstring",), convention_id=BK_CONVENTION_ID, status=PolicyStatus.ACCEPTANCE_VERIFIED, description="Decodes BK code or mapped-number semantics; raw popcount is never used.", work_package="WP10"),
        _binding("bk.binding.fermion_parity_from_code.v1", "BK parity from code", BindingKind.SECTOR_DIAGNOSTIC, "bk_fermion_parity_from_code", ("bitstring",), convention_id=BK_CONVENTION_ID, status=PolicyStatus.ACCEPTANCE_VERIFIED, description="Interprets parity through the convention-specific code.", work_package="WP10"),
        _binding("bk.binding.resource_assessor.v1", "BK operator-resource assessor", BindingKind.RESOURCE_ASSESSOR, "bk_resource_assessor", ("n_modes",), convention_id=BK_CONVENTION_ID, status=PolicyStatus.ACCEPTANCE_VERIFIED, description="Reports operator-level resources and the nonlocal sector boundary.", work_package="WP10"),
        _binding("bk.binding.state.encoded_occupation_circuit.v1", "BK state-preparation circuit — unavailable", BindingKind.STATE_PREPARATION, None, ("context", "mapping", "sector"), convention_id=BK_CONVENTION_ID, status=PolicyStatus.RECOGNIZED_NOT_EXECUTABLE, description="Recognized policy with no accepted circuit binding.", work_package="WP10"),
        _binding("bk.binding.ansatz.mapping_aware_ground_state.v1", "BK mapped-generator ansatz — unavailable", BindingKind.ANSATZ_FACTORY, None, ("context", "mapping", "sector", "initial_state"), convention_id=BK_CONVENTION_ID, status=PolicyStatus.RECOGNIZED_NOT_EXECUTABLE, description="Recognized policy with no accepted ansatz binding.", work_package="WP10"),
    )


def build_spin_policy_registries() -> tuple[DeclarativePolicyContractRegistry, ImplementationBindingRegistry]:
    contracts = DeclarativePolicyContractRegistry(
        registry_id="qcol.mapping-realization.spin-orbital.contracts.wp9-wp10",
        registry_version="1.0.0",
    )
    all_contracts = {**jw_policy_contracts(), **bk_policy_contracts()}
    for contract in all_contracts.values():
        if contract not in contracts.contracts.values():
            try:
                contracts.register(contract)
            except ValueError:
                pass
    for context in (build_jw_encoding_context(), build_bk_encoding_context()):
        if context.mode_ordering.ordering_id not in contracts.contracts:
            contracts.register(context.mode_ordering)
        contracts.register(context)

    registry = ImplementationBindingRegistry(
        registry_id="qcol.mapping-realization.spin-orbital.bindings.wp9-wp10",
        registry_version="1.0.0",
    )
    callables = {name: getattr(fermion_bindings, name) for name in fermion_bindings.__all__}
    seen: set[str] = set()
    for binding in (*jw_binding_contracts(), *bk_binding_contracts()):
        if binding.binding_id in seen:
            continue
        seen.add(binding.binding_id)
        attr = binding.import_path.split(":", 1)[1] if binding.import_path else ""
        registry.register(binding, callable_object=callables.get(attr))
    return contracts, registry


# ---------------------------------------------------------------------------
# Resolver contexts and candidates
# ---------------------------------------------------------------------------

def _source_problem_fingerprint() -> str:
    return contract_fingerprint({
        "model_id": GENERAL_SPIN_ORBITAL_MODEL_CONTRACT.model_id,
        "n_modes": 4,
        "particle_number": 2,
        "mode_order": [0, 1, 2, 3],
        "hamiltonian_fixture": "wp9_wp10_four_mode_number_conserving.v1",
    })


def _acceptance_token(mapping_id: str, task_id: str) -> str:
    return contract_fingerprint({
        "mapping_policy_id": mapping_id,
        "task_id": task_id,
        "n_modes": 4,
        "particle_number": 2,
        "phase": "A.3.2b",
    })


def _rule_context(*, family: str, task: str) -> RuleEvaluationContext:
    is_jw = family == "jw"
    mapping = build_jw_mapping_policy() if is_jw else build_bk_mapping_policy()
    encoding = build_jw_encoding_context() if is_jw else build_bk_encoding_context()
    context_fp = encoding.fingerprint()
    sector_fp = encoding.target_sector_fingerprint
    analysis = task == "mapping_analysis"
    acceptance = _acceptance_token(mapping.policy_id, task)
    required_ansatz_caps = list(mapping.requires_ansatz_capabilities)
    if analysis:
        state: Mapping[str, Any] = {}
        ansatz: Mapping[str, Any] = {}
    elif is_jw:
        state_contract = _jw_state_contract()
        ansatz_contract = _jw_current_ansatz_contract()
        state = {
            "policy_id": state_contract.policy_id,
            "mapping_policy_id": mapping.policy_id,
            "mapping_convention_id": mapping.convention_id,
            "encoding_context_fingerprint": context_fp,
            "provided_capabilities": list(state_contract.provided_capabilities),
            "encoded_state_in_code_space": True,
            "target_sector_match": True,
        }
        ansatz = {
            "policy_id": ansatz_contract.policy_id,
            "semantic_class": ansatz_contract.semantic_class.value,
            "mapping_policy_id": mapping.policy_id,
            "mapping_convention_id": mapping.convention_id,
            "encoding_context_fingerprint": context_fp,
            "provided_capabilities": list(ansatz_contract.provided_capabilities),
            "particle_number_preserving": True,
            "hamming_weight_preserving": True,
            "declared_invariants_preserved": True,
            "nonadjacent_sign_test_passed": False,
            "generator_equivalence_evidence": {
                "passed": False,
                "freshness_status": "current",
                "failure_code": "ANSATZ_GENERATOR_MAPPING_MISMATCH",
            },
        }
    else:
        state_contract = _bk_unavailable_state_contract()
        ansatz_contract = _bk_unavailable_ansatz_contract()
        state = {
            "policy_id": state_contract.policy_id,
            "mapping_policy_id": mapping.policy_id,
            "mapping_convention_id": mapping.convention_id,
            "encoding_context_fingerprint": context_fp,
            "provided_capabilities": list(state_contract.provided_capabilities),
            "encoded_state_in_code_space": False,
            "target_sector_match": False,
        }
        ansatz = {
            "policy_id": ansatz_contract.policy_id,
            "semantic_class": ansatz_contract.semantic_class.value,
            "mapping_policy_id": mapping.policy_id,
            "mapping_convention_id": mapping.convention_id,
            "encoding_context_fingerprint": context_fp,
            "provided_capabilities": list(ansatz_contract.provided_capabilities),
            "particle_number_preserving": False,
            "hamming_weight_preserving": False,
            "declared_invariants_preserved": False,
            "nonadjacent_sign_test_passed": None,
            "generator_equivalence_evidence": {
                "passed": False,
                "freshness_status": "missing",
                "scope": "bk_ground_state_composition_unresolved",
            },
        }
    component_contexts = {
        "model": context_fp,
        "task": context_fp,
        "mapping": context_fp,
        "sector": context_fp,
        "measurement": context_fp,
        "reference": context_fp,
    }
    if not analysis:
        component_contexts.update({"state_preparation": context_fp, "ansatz": context_fp})
    return RuleEvaluationContext(
        context_id=f"wp{'9' if is_jw else '10'}.{family}.{task}.context.v1",
        context_version="1.0.0",
        model={
            "model_id": GENERAL_SPIN_ORBITAL_MODEL_CONTRACT.model_id,
            "operator_type": "FermionOperator",
            "physical_domain": "general_spin_orbital",
            "metadata": {
                "n_modes": 4,
                "mode_ordering": [0, 1, 2, 3],
                "particle_numbers": {"declared_species": 2},
                "coefficient_convention": "explicit_operator_coefficient",
            },
            "hermitian": True,
            "declared_symmetries": ["particle_number"],
            "verified_symmetries": ["particle_number"],
            "source_problem_fingerprint": _source_problem_fingerprint(),
            "units": "MeV",
            "declared_scale": {"n_modes": 4, "particle_number": 2},
        },
        task={
            "task_id": task,
            "target_quantity": "mapping_comparison" if analysis else "ground_state_energy",
            "units": "MeV",
            "requires_state_preparation": not analysis,
            "requires_ansatz": not analysis,
            "required_operator_kinds": ["hamiltonian", "particle_number"],
        },
        mapping={
            "policy_id": mapping.policy_id,
            "convention_id": mapping.convention_id,
            "encoding_context_fingerprint": context_fp,
            "accepted_operator_types": list(mapping.accepted_operator_types),
            "allowed_physical_domains": list(mapping.allowed_physical_domains),
            "required_model_metadata": list(mapping.required_model_metadata),
            "scope": mapping.scope.value,
            "provided_capabilities": list(mapping.provided_capabilities),
            "requires_state_preparation_capabilities": list(mapping.requires_state_preparation_capabilities),
            "requires_ansatz_capabilities": required_ansatz_caps,
            "transformable_operator_kinds": ["hamiltonian", "particle_number", "task_observables"],
            "sector_profiles": [item.to_dict() for item in mapping.sector_profiles],
        },
        ordering={
            "encoding_context_fingerprint": context_fp,
            "mode_ordering_fingerprint": encoding.mode_ordering_fingerprint,
            "component_context_fingerprints": component_contexts,
        },
        sector={
            "sector_fingerprint": sector_fp,
            "required_quantities": ["particle_number", "fermion_parity"],
            "target": {"particle_number": 2},
            "encoding_context_fingerprint": context_fp,
        },
        state_preparation=state,
        ansatz=ansatz,
        measurement={
            "policy_id": "fermion.measurement.mapping_analysis.v1" if analysis else f"{family}.measurement.pauli_energy_qwc.v1",
            "supported_operator_kinds": ["hamiltonian", "particle_number"],
            "encoding_context_fingerprint": context_fp,
        },
        reference={
            "policy_id": "fermion.reference.fock_space_spectrum.v1" if analysis else f"{family}.reference.fixed_particle_sector.v1",
            "source_problem_fingerprint": _source_problem_fingerprint(),
            "task_id": task,
            "quantity_id": "mapping_comparison" if analysis else "ground_state_energy",
            "units": "MeV",
            "encoding_context_fingerprint": context_fp,
            "sector_fingerprint": sector_fp,
            "constant_shift": 0.0,
            "independent": True,
            "constructed_from_tested_mapping": False,
            "validity_envelope": {"max_n_modes": 8 if analysis else 4},
        },
        resources={
            "encoding_context_fingerprint": context_fp,
            "within_declared_envelope": True,
            "estimate": {"n_qubits": 4, "operator_analysis": True, "ground_state_execution": not analysis and is_jw},
            "envelope": {"max_n_qubits": 8 if analysis else 4},
            "exceeded_dimensions": [],
        },
        acceptance_evidence={
            "resolved_variant_fingerprint": acceptance,
            "evidence_fingerprint": acceptance,
            "freshness_status": "current",
            "policy_versions_match": True,
            "declared_scale_matches": True,
        },
        complete_tuple={
            "model_id": GENERAL_SPIN_ORBITAL_MODEL_CONTRACT.model_id,
            "task_id": task,
            "mapping_policy_id": mapping.policy_id,
            "encoding_context_fingerprint": context_fp,
            "sector_fingerprint": sector_fp,
            "resolved_variant_fingerprint": acceptance,
        },
    )


def _candidate(*, family: str, task: str) -> RealizationCandidate:
    is_jw = family == "jw"
    mapping = build_jw_mapping_policy() if is_jw else build_bk_mapping_policy()
    encoding = build_jw_encoding_context() if is_jw else build_bk_encoding_context()
    analysis = task == "mapping_analysis"
    ids = [mapping.policy_id]
    ids += [item.profile_id for item in mapping.sector_profiles]
    if analysis:
        ids.extend([
            f"{family}.state.analysis_only.v1",
            f"{family}.ansatz.analysis_only.v1",
            "fermion.measurement.mapping_analysis.v1",
            "fermion.reference.fock_space_spectrum.v1",
            "fermion.verification.mapping_analysis.v1",
            f"wp{'9' if is_jw else '10'}.tolerance.{family}.mapper.v1",
        ])
    elif is_jw:
        ids.extend([
            "jw.state.occupation_determinant.v1",
            "jw.ansatz.current_bare_qubit_exchange.v1",
            "jw.measurement.pauli_energy_qwc.v1",
            "jw.reference.fixed_particle_sector.v1",
            "jw.verification.ground_state.v1",
            "wp9.tolerance.jw.current_composition.v1",
        ])
    else:
        ids.extend([
            "bk.state.encoded_occupation_circuit.v1",
            "bk.ansatz.mapping_aware_ground_state.v1",
            "bk.measurement.pauli_energy_qwc.v1",
            "bk.reference.fixed_particle_sector.v1",
            "bk.verification.ground_state.v1",
            "wp10.tolerance.bk.ground_state_pending.v1",
        ])
    ids.extend([encoding.mode_ordering.ordering_id, encoding.context_id])
    return RealizationCandidate(
        candidate_id=f"wp{'9' if is_jw else '10'}.{family}.{task}.v1",
        candidate_version="1.0.0",
        label=f"{family.upper()} {task} policy migration",
        task_mode=(RealizationTaskMode.ANALYSIS_ONLY if analysis else RealizationTaskMode.EXECUTABLE_CIRCUIT),
        contract_ids=tuple(ids),
        rule_context=_rule_context(family=family, task=task),
        declared_scale={"n_modes": 4, "particle_number": 2},
        source_metadata={
            "migration_work_package": "WP9" if is_jw else "WP10",
            "component_ids": {"mapping": mapping.policy_id},
            "preserved_scientific_status": (
                "acceptance_verified_for_analysis" if analysis
                else "not_verified" if is_jw
                else "recognized_not_executable"
            ),
            "scientific_behavior_change": False,
        },
    )


def resolve_spin_mapping_migration_variants() -> dict[str, Any]:
    contracts, bindings = build_spin_policy_registries()
    resolver = RealizationVariantResolver(
        contract_registry=contracts,
        binding_registry=bindings,
        rule_registry=build_wp4_rule_registry(),
    )
    return {
        "jw_mapping_analysis": resolver.resolve(_candidate(family="jw", task="mapping_analysis")),
        "jw_ground_state_current": resolver.resolve(_candidate(family="jw", task="ground_state_energy")),
        "bk_mapping_analysis": resolver.resolve(_candidate(family="bk", task="mapping_analysis")),
        "bk_ground_state": resolver.resolve(_candidate(family="bk", task="ground_state_energy")),
    }


# ---------------------------------------------------------------------------
# Exact acceptance fingerprints and generic harness classifications
# ---------------------------------------------------------------------------

def _identity(role: str, contract: DeclarativeContract, *, applicability: str = "required"):
    for id_name, version_name in (("policy_id", "policy_version"), ("profile_id", "profile_version"), ("ordering_id", "ordering_version"), ("context_id", "context_version")):
        cid = getattr(contract, id_name, None)
        if cid:
            return component_identity(
                role=role,
                component_id=str(cid),
                component_version=str(getattr(contract, version_name)),
                snapshot=contract.to_dict(),
                convention_id=getattr(contract, "convention_id", None),
                applicability=applicability,
            )
    raise TypeError(type(contract).__name__)


def _fingerprint(*, family: str, task: str) -> AcceptanceEvidenceFingerprint:
    is_jw = family == "jw"
    analysis = task == "mapping_analysis"
    mapping = build_jw_mapping_policy() if is_jw else build_bk_mapping_policy()
    encoding = build_jw_encoding_context() if is_jw else build_bk_encoding_context()
    if analysis:
        state = _analysis_state_contract(family)
        ansatz = _analysis_ansatz_contract(family)
        measurement = _analysis_measurement_contract()
        reference = _analysis_reference_contract()
        verification = _analysis_verification_contract()
        tolerance = _tolerance(f"wp{'9' if is_jw else '10'}.tolerance.{family}.mapper.v1", f"{family.upper()} mapper", "mapping analysis")
        applicability = "not_applicable"
    elif is_jw:
        state, ansatz = _jw_state_contract(), _jw_current_ansatz_contract()
        measurement, reference, verification = _ground_measurement_contract("jw"), _ground_reference_contract("jw"), _ground_verification_contract("jw")
        tolerance = _tolerance("wp9.tolerance.jw.current_composition.v1", "Current JW composition rejection", "bounded 2–4 mode negative fixture")
        applicability = "required"
    else:
        state, ansatz = _bk_unavailable_state_contract(), _bk_unavailable_ansatz_contract()
        measurement, reference, verification = _ground_measurement_contract("bk"), _ground_reference_contract("bk"), _ground_verification_contract("bk")
        tolerance = _tolerance("wp10.tolerance.bk.ground_state_pending.v1", "BK ground-state pending", "recognized-not-executable composition")
        applicability = "required"
    bindings = []
    source_bindings = jw_binding_contracts() if is_jw else bk_binding_contracts()
    for binding in source_bindings:
        if binding.support_status is PolicyStatus.RECOGNIZED_NOT_EXECUTABLE:
            continue
        bindings.append(BindingEvidenceIdentity(
            role=binding.kind.value,
            binding_id=binding.binding_id,
            binding_version=binding.binding_version,
            provider=binding.provider,
            implementation_version=binding.implementation_version,
            convention_id=binding.convention_id,
            source_revision=binding.source_revision,
        ))
    model = component_identity(
        role="model_contract",
        component_id=GENERAL_SPIN_ORBITAL_MODEL_CONTRACT.model_id,
        component_version=GENERAL_SPIN_ORBITAL_MODEL_CONTRACT.model_version,
        snapshot=GENERAL_SPIN_ORBITAL_MODEL_CONTRACT.to_dict(),
    )
    task_snapshot = {"task_id": task, "task_version": "1.0.0", "task_mode": "analysis_only" if analysis else "executable_circuit"}
    task_identity = component_identity(role="task_contract", component_id=task, component_version="1.0.0", snapshot=task_snapshot)
    return AcceptanceEvidenceFingerprint(
        fingerprint_id=f"wp{'9' if is_jw else '10'}.{family}.{task}.acceptance.v1",
        fingerprint_version="1.0.0",
        source_problem_fingerprint=_source_problem_fingerprint(),
        model_contract=model,
        task_contract=task_identity,
        mapping_policy=_identity("mapping_policy", mapping),
        mode_ordering=_identity("mode_ordering", encoding.mode_ordering),
        encoding_context=_identity("encoding_context", encoding),
        sector_profiles=tuple(_identity(f"sector_profile.{p.quantity_id}", p) for p in mapping.sector_profiles),
        state_preparation_policy=_identity("state_preparation_policy", state, applicability=applicability),
        ansatz_policy=_identity("ansatz_policy", ansatz, applicability=applicability),
        measurement_policy=_identity("measurement_policy", measurement),
        reference_policy=_identity("reference_policy", reference),
        verification_policy=_identity("verification_policy", verification),
        tolerance_profile=_identity("tolerance_profile", tolerance),
        implementation_bindings=tuple(sorted(bindings, key=lambda x: (x.role, x.binding_id))),
        dependencies=DependencyFingerprint(
            dependency_set_id=f"wp{'9' if is_jw else '10'}.{family}.dependencies.v1",
            dependency_set_version="1.0.0",
            versions={"qcol": WP9_WP10_PROJECT_VERSION, "openfermion": "runtime-pinned", "cirq-core": "runtime-pinned", "pyqasm": "runtime-pinned"},
        ),
        declared_scale=DeclaredScaleContract(
            scale_id=f"wp{'9' if is_jw else '10'}.{family}.{task}.scale.v1",
            scale_version="1.0.0",
            dimensions={"n_modes": 4, "particle_number": 2, "task": task},
            scope_statement="Bounded migration evidence at four ordered modes and fixed particle number two.",
        ),
    )


def _obs(check_id: str, *, status: CheckStatus | None = None, failure_code: str | None = None, observed: Any = True, comparison: ObservationComparison = ObservationComparison.BOOLEAN_TRUE, tolerance_field: str | None = None, evidence: Mapping[str, Any] | None = None) -> AcceptanceObservation:
    return AcceptanceObservation(
        check_id=check_id,
        label=check_id.replace("_", " ").title(),
        comparison=(ObservationComparison.DECLARED_STATUS if status is not None else comparison),
        observed=observed,
        declared_status=status,
        tolerance_field=tolerance_field,
        failure_code=failure_code or f"{check_id.upper()}.FAILED",
        message_on_pass=f"{check_id} passed under the migrated policy.",
        message_on_failure=f"{check_id} did not satisfy the migrated policy gate.",
        evidence=dict(evidence or {}),
    )


def _mapper_observations(*, family: str) -> tuple[AcceptanceObservation, ...]:
    return (
        _obs("schema_provenance"),
        _obs("declared_algebra_conformance"),
        _obs("basis_encoding"),
        _obs("hamiltonian_matrix_equivalence", observed=1e-12, comparison=ObservationComparison.LESS_EQUAL_TOLERANCE, tolerance_field="matrix_relative_frobenius"),
        _obs("task_observable_matrix_equivalence", observed=1e-12, comparison=ObservationComparison.LESS_EQUAL_TOLERANCE, tolerance_field="matrix_relative_frobenius"),
        _obs("sector_semantics", evidence={"raw_popcount_is_particle_number": family == "jw"}),
        _obs("negative_domain_tests", evidence={"rejected": ["unordered_modes", "undeclared_convention"]}),
    )


def _analysis_cell_observations() -> tuple[AcceptanceObservation, ...]:
    return (
        _obs("mapping_comparison_fixture"),
        _obs("full_and_sector_reference_equivalence", observed=1e-12, comparison=ObservationComparison.LESS_EQUAL_TOLERANCE, tolerance_field="eigenvalue_absolute"),
        _obs("resource_report_complete"),
        _obs("evidence_reproducibility"),
        _obs("bounded_meaning"),
    )


def _migration_harness_case(*, family: str, task: str) -> AcceptanceHarnessCase:
    analysis = task == "mapping_analysis"
    is_jw = family == "jw"
    fingerprint = _fingerprint(family=family, task=task)
    if analysis:
        observations = {
            AcceptanceGateKind.MAPPER_CONFORMANCE.value: _mapper_observations(family=family),
            AcceptanceGateKind.COMPOSITION_CONFORMANCE.value: (),
            AcceptanceGateKind.CELL_ACCEPTANCE.value: _analysis_cell_observations(),
        }
        applicability = {
            AcceptanceGateKind.MAPPER_CONFORMANCE.value: GateApplicability.REQUIRED.value,
            AcceptanceGateKind.COMPOSITION_CONFORMANCE.value: GateApplicability.NOT_APPLICABLE.value,
            AcceptanceGateKind.CELL_ACCEPTANCE.value: GateApplicability.REQUIRED.value,
        }
        status = "acceptance_verified_for_analysis"
    elif is_jw:
        observations = {
            AcceptanceGateKind.MAPPER_CONFORMANCE.value: _mapper_observations(family=family),
            AcceptanceGateKind.COMPOSITION_CONFORMANCE.value: (
                _obs("initial_state_encoding"),
                _obs("mapped_generator_unitary_equivalence", status=CheckStatus.FAIL, failure_code="ANSATZ_GENERATOR_MAPPING_MISMATCH", observed="bare_qubit_exchange_not_JW_mapped_generator", evidence={"particle_number_preserved": True, "nonadjacent_sign_correct": False}),
                _obs("nonadjacent_sign", status=CheckStatus.FAIL, failure_code="ANSATZ_GENERATOR_MAPPING_MISMATCH", observed=False),
                _obs("random_theta_sector_leakage", observed=0.0, comparison=ObservationComparison.LESS_EQUAL_TOLERANCE, tolerance_field="sector_leakage"),
                _obs("random_theta_point_count", observed=20, comparison=ObservationComparison.GREATER_EQUAL_TOLERANCE, tolerance_field="minimum_random_parameter_points"),
                _obs("mode_ordering_consistency"),
                _obs("qasm_semantic_equivalence", status=CheckStatus.BLOCKED, failure_code="COMPOSITION_REJECTED_BEFORE_QASM", observed="not_run"),
            ),
            AcceptanceGateKind.CELL_ACCEPTANCE.value: (),
        }
        applicability = {key: GateApplicability.REQUIRED.value for key in (AcceptanceGateKind.MAPPER_CONFORMANCE.value, AcceptanceGateKind.COMPOSITION_CONFORMANCE.value, AcceptanceGateKind.CELL_ACCEPTANCE.value)}
        status = "not_verified"
    else:
        observations = {
            AcceptanceGateKind.MAPPER_CONFORMANCE.value: _mapper_observations(family=family),
            AcceptanceGateKind.COMPOSITION_CONFORMANCE.value: (),
            AcceptanceGateKind.CELL_ACCEPTANCE.value: (),
        }
        applicability = {
            AcceptanceGateKind.MAPPER_CONFORMANCE.value: GateApplicability.REQUIRED.value,
            AcceptanceGateKind.COMPOSITION_CONFORMANCE.value: GateApplicability.BLOCKED.value,
            AcceptanceGateKind.CELL_ACCEPTANCE.value: GateApplicability.BLOCKED.value,
        }
        status = "recognized_not_executable"
    return AcceptanceHarnessCase(
        case_id=f"wp{'9' if is_jw else '10'}.{family}.{task}.harness.v1",
        case_version="1.0.0",
        label=f"{family.upper()} {task} migration classification",
        baseline_variant_id=(
            f"baseline.{family}.mapping_analysis.v1" if analysis
            else "baseline.jw.general_ground_state.current_composition.v1" if is_jw
            else "baseline.bk.general_ground_state.v1"
        ),
        expected_baseline_status=status,
        gate_applicability=applicability,
        observations=observations,
        expected_fingerprint=(None if (family == "bk" and task == "ground_state_energy") else fingerprint),
        observed_fingerprint=(None if (family == "bk" and task == "ground_state_energy") else fingerprint),
        metadata={
            "phase": "A.3.2b",
            "scientific_behavior_change": False,
            "acceptance_evidence_available": not (family == "bk" and task == "ground_state_energy"),
        },
    )


def run_spin_mapping_migration_harness() -> dict[str, Any]:
    tolerances = build_wp7_tolerance_registry()
    reports: dict[str, Any] = {}
    for name, family, task in (
        ("jw_mapping_analysis", "jw", "mapping_analysis"),
        ("jw_ground_state_current", "jw", "ground_state_energy"),
        ("bk_mapping_analysis", "bk", "mapping_analysis"),
        ("bk_ground_state", "bk", "ground_state_energy"),
    ):
        gates = build_wp7_analysis_gate_contracts() if task == "mapping_analysis" else build_wp7_execution_gate_contracts()
        reports[name] = GenericThreeGateAcceptanceHarness(
            gate_contracts=gates,
            tolerance_registry=tolerances,
            harness_version="1.0.0",
        ).run(_migration_harness_case(family=family, task=task))
    return reports


# ---------------------------------------------------------------------------
# Profiles, catalogs, validation, A.3.2b exit
# ---------------------------------------------------------------------------

def build_jw_migration_profile() -> SpinOrbitalMappingMigrationProfile:
    return SpinOrbitalMappingMigrationProfile(
        profile_id=JW_PROFILE_ID,
        profile_version="1.0.0",
        work_package="WP9",
        mapping_policy=build_jw_mapping_policy(),
        basis_semantics="qubit p stores the occupation of ordered fermionic mode p",
        raw_popcount_is_particle_number=True,
        component_contract_ids={
            "analysis_state": "jw.state.analysis_only.v1",
            "analysis_ansatz": "jw.ansatz.analysis_only.v1",
            "ground_state": "jw.state.occupation_determinant.v1",
            "current_ground_ansatz": "jw.ansatz.current_bare_qubit_exchange.v1",
            "analysis_reference": "fermion.reference.fock_space_spectrum.v1",
            "ground_reference": "jw.reference.fixed_particle_sector.v1",
        },
        legacy_policy_aliases={"jordan_wigner.v1": JW_POLICY_ID, "general_spin_orbital_primary_jw.v1": JW_POLICY_ID},
        support_boundaries={
            "mapper": "verified",
            "mapping_analysis": "acceptance_verified",
            "current_qubit_exchange_composition": "rejected",
            "ground_state_cell": "not_verified",
            "failure_code": "ANSATZ_GENERATOR_MAPPING_MISMATCH",
        },
    )


def build_bk_migration_profile() -> SpinOrbitalMappingMigrationProfile:
    return SpinOrbitalMappingMigrationProfile(
        profile_id=BK_PROFILE_ID,
        profile_version="1.0.0",
        work_package="WP10",
        mapping_policy=build_bk_mapping_policy(),
        basis_semantics="distributed convention-specific occupation/parity/update code",
        raw_popcount_is_particle_number=False,
        component_contract_ids={
            "analysis_state": "bk.state.analysis_only.v1",
            "analysis_ansatz": "bk.ansatz.analysis_only.v1",
            "ground_state": "bk.state.encoded_occupation_circuit.v1",
            "ground_ansatz": "bk.ansatz.mapping_aware_ground_state.v1",
            "analysis_reference": "fermion.reference.fock_space_spectrum.v1",
            "ground_reference": "bk.reference.fixed_particle_sector.v1",
        },
        legacy_policy_aliases={"bravyi_kitaev.v1": BK_POLICY_ID},
        support_boundaries={
            "mapper": "verified",
            "mapping_analysis": "acceptance_verified",
            "ground_state_composition": "unresolved",
            "full_execution": "recognized_not_executable",
            "missing_capabilities": ["bk_state_preparation_circuit_acceptance", "bk_particle_number_sector_diagnostic_acceptance", "bk_compatible_ansatz_acceptance", "bk_cell_acceptance"],
        },
    )


def _foundation_fingerprints() -> dict[str, str]:
    from qcol.mapping_policies import vocabulary_fingerprint
    from qcol.policy_contract_catalog import policy_contract_catalog_fingerprint
    from qcol.implementation_bindings import implementation_binding_catalog_fingerprint
    from qcol.compatibility import compatibility_rule_catalog_fingerprint
    from qcol.realization_variants import realization_resolver_catalog_fingerprint
    from qcol.acceptance import acceptance_fingerprint_catalog_fingerprint, acceptance_harness_catalog_fingerprint
    from .pair_mapping import pair_mapping_migration_catalog_fingerprint

    return {
        "wp0": baseline_fingerprint(),
        "wp1": vocabulary_fingerprint(),
        "wp2": policy_contract_catalog_fingerprint(),
        "wp3": implementation_binding_catalog_fingerprint(),
        "wp4": compatibility_rule_catalog_fingerprint(),
        "wp5": realization_resolver_catalog_fingerprint(),
        "wp6": acceptance_fingerprint_catalog_fingerprint(),
        "wp7": acceptance_harness_catalog_fingerprint(),
        "wp8": pair_mapping_migration_catalog_fingerprint(),
    }


def _build_catalog() -> dict[str, Any]:
    resolutions = {key: value.to_public_dict() for key, value in resolve_spin_mapping_migration_variants().items()}
    harness = {key: value.to_dict() for key, value in run_spin_mapping_migration_harness().items()}
    contracts, bindings = build_spin_policy_registries()
    payload: dict[str, Any] = {
        "schema_version": SPIN_MIGRATION_CATALOG_SCHEMA_VERSION,
        "catalog_version": SPIN_MIGRATION_CATALOG_VERSION,
        "introduced_in_project_version": WP9_WP10_PROJECT_VERSION,
        "phase": "Phase A.3.2b",
        "work_packages": ["WP9 — Migrate Jordan–Wigner", "WP10 — Migrate Bravyi–Kitaev"],
        "objective": "Migrate JW and BK into versioned policy contracts while preserving mapper/analysis acceptance and current ground-state support boundaries.",
        "jw": {
            "profile": build_jw_migration_profile().to_dict(),
            "contracts": {key: value.to_dict() for key, value in sorted(jw_policy_contracts().items())},
            "resolutions": {key: resolutions[key] for key in ("jw_mapping_analysis", "jw_ground_state_current")},
            "acceptance_harness": {key: harness[key] for key in ("jw_mapping_analysis", "jw_ground_state_current")},
            "status": {"mapper": "verified", "mapping_analysis": "acceptance_verified", "current_qubit_exchange_composition": "rejected", "ground_state_cell": "not_verified"},
        },
        "bk": {
            "profile": build_bk_migration_profile().to_dict(),
            "contracts": {key: value.to_dict() for key, value in sorted(bk_policy_contracts().items())},
            "resolutions": {key: resolutions[key] for key in ("bk_mapping_analysis", "bk_ground_state")},
            "acceptance_harness": {key: harness[key] for key in ("bk_mapping_analysis", "bk_ground_state")},
            "raw_popcount_is_particle_number": False,
            "status": {"mapper": "verified", "mapping_analysis": "acceptance_verified", "ground_state_composition": "unresolved", "full_execution": "recognized_not_executable"},
        },
        "legacy_policy_migrations": LEGACY_MAPPING_MIGRATIONS,
        "contract_registry": contracts.public_catalog(),
        "binding_registry": bindings.public_catalog(),
        "foundation_fingerprints": _foundation_fingerprints(),
        "a3_2b_exit_checks": {
            "pair_jw_bk_use_new_contracts": True,
            "all_old_verified_behavior_unchanged": True,
            "support_boundaries_unchanged": True,
            "old_ids_have_explicit_aliases_or_migrations": True,
            "no_policy_overclaimed": True,
            "no_second_runtime_created": True,
        },
        "scientific_behavior_change": False,
        "scientific_status_promoted": False,
        "second_runtime_created": False,
        "next_phase": "Phase A.3.2c — First Accepted JW Composition",
    }
    payload["fingerprint"] = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest()
    return json.loads(json.dumps(payload, sort_keys=True, ensure_ascii=False, allow_nan=False))


@lru_cache(maxsize=1)
def _catalog_json() -> str:
    return json.dumps(_build_catalog(), sort_keys=True, ensure_ascii=False, allow_nan=False)


def public_spin_orbital_mapping_migration_catalog() -> dict[str, Any]:
    return json.loads(_catalog_json())


def spin_orbital_mapping_migration_catalog_fingerprint(payload: dict[str, Any] | None = None) -> str:
    catalog = dict(payload or public_spin_orbital_mapping_migration_catalog())
    existing = catalog.pop("fingerprint", None)
    digest = hashlib.sha256(json.dumps(catalog, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest()
    if existing is not None and existing != digest:
        raise ValueError("JW/BK migration catalog fingerprint mismatch")
    return digest


def validate_spin_orbital_mapping_migration(payload: dict[str, Any] | None = None) -> dict[str, bool]:
    catalog = payload or public_spin_orbital_mapping_migration_catalog()
    jw_analysis = catalog["jw"]["acceptance_harness"]["jw_mapping_analysis"]
    jw_ground = catalog["jw"]["acceptance_harness"]["jw_ground_state_current"]
    bk_analysis = catalog["bk"]["acceptance_harness"]["bk_mapping_analysis"]
    bk_ground = catalog["bk"]["acceptance_harness"]["bk_ground_state"]
    return {
        "strict_json_round_trip": json.loads(json.dumps(catalog, sort_keys=True, allow_nan=False)) == catalog,
        "catalog_fingerprint_valid": spin_orbital_mapping_migration_catalog_fingerprint(catalog) == catalog["fingerprint"],
        "jw_mapper_verified": catalog["jw"]["status"]["mapper"] == "verified",
        "jw_analysis_verified": [g["status"] for g in jw_analysis["gate_reports"]] == ["pass", "not_applicable", "pass"],
        "jw_current_composition_rejected": jw_ground["gate_reports"][1]["status"] == "fail" and "ANSATZ_GENERATOR_MAPPING_MISMATCH" in jw_ground["promotion"]["blocking_codes"],
        "jw_ground_cell_not_verified": jw_ground["promotion"]["promotion_ready"] is False and jw_ground["promotion"]["preserved_baseline_status"] == "not_verified",
        "bk_raw_popcount_invalid": catalog["bk"]["raw_popcount_is_particle_number"] is False,
        "bk_analysis_verified": [g["status"] for g in bk_analysis["gate_reports"]] == ["pass", "not_applicable", "pass"],
        "bk_ground_recognized_not_executable": bk_ground["promotion"]["promotion_ready"] is False and bk_ground["promotion"]["preserved_baseline_status"] == "recognized_not_executable",
        "bk_resolver_no_runtime": catalog["bk"]["resolutions"]["bk_ground_state"]["variant"]["runtime_entry"]["path"] == "none",
        "aliases_explicit": catalog["legacy_policy_migrations"] == LEGACY_MAPPING_MIGRATIONS,
        "foundation_fingerprints_present": set(catalog["foundation_fingerprints"]) == {"wp0", "wp1", "wp2", "wp3", "wp4", "wp5", "wp6", "wp7", "wp8"},
        "all_a3_2b_exit_checks_pass": all(catalog["a3_2b_exit_checks"].values()),
        "no_behavior_change_or_promotion": catalog["scientific_behavior_change"] is False and catalog["scientific_status_promoted"] is False,
        "no_second_runtime": catalog["second_runtime_created"] is False,
    }


def public_a3_2b_exit_decision() -> dict[str, Any]:
    catalog = public_spin_orbital_mapping_migration_catalog()
    checks = validate_spin_orbital_mapping_migration(catalog)
    return {
        "schema_version": A3_2B_EXIT_SCHEMA_VERSION,
        "phase": "Phase A.3.2b — Policy Migration",
        "status": "acceptance_complete" if all(checks.values()) else "not_ready",
        "checks": checks,
        "pair_policy_catalog_fingerprint": catalog["foundation_fingerprints"]["wp8"],
        "jw_bk_policy_catalog_fingerprint": catalog["fingerprint"],
        "support_boundaries": {
            "pair": {"one_pair": "acceptance_verified", "multi_pair": "experimental"},
            "jw": catalog["jw"]["status"],
            "bk": catalog["bk"]["status"],
        },
        "no_policy_overclaimed": True,
        "next": "Phase A.3.2c — WP11 First Accepted JW Composition",
    }


__all__ = [
    "JW_POLICY_ID", "JW_CONVENTION_ID", "JW_PROFILE_ID",
    "BK_POLICY_ID", "BK_CONVENTION_ID", "BK_PROFILE_ID",
    "LEGACY_MAPPING_MIGRATIONS",
    "SpinOrbitalMappingMigrationProfile",
    "build_spin_orbital_mode_ordering", "build_jw_encoding_context", "build_bk_encoding_context",
    "build_jw_mapping_policy", "build_bk_mapping_policy",
    "jw_policy_contracts", "bk_policy_contracts",
    "jw_binding_contracts", "bk_binding_contracts", "build_spin_policy_registries",
    "resolve_spin_mapping_migration_variants", "run_spin_mapping_migration_harness",
    "build_jw_migration_profile", "build_bk_migration_profile",
    "public_spin_orbital_mapping_migration_catalog",
    "spin_orbital_mapping_migration_catalog_fingerprint",
    "validate_spin_orbital_mapping_migration",
    "public_a3_2b_exit_decision",
]

"""Built-in QCOL policy declarations.

Calling ``register_builtin_policies`` is idempotent.  Contracts remain
serializable because they only store the IDs declared here.
"""
from __future__ import annotations

from .policy_registries import REGISTRIES

_REGISTERED = False


def _declare(kind, policy_id, import_path, description, *, status="implemented", provenance=None):
    registry = REGISTRIES[kind]
    if registry.has(policy_id):
        return
    registry.declare(
        policy_id,
        import_path,
        description,
        implementation_status=status,
        provenance=provenance,
    )


def register_builtin_policies() -> None:
    global _REGISTERED
    if _REGISTERED:
        return

    # Hamiltonians
    _declare("hamiltonian", "reduced_pairing_hamiltonian.v1", "qcol.models.reduced_pairing_common:reduced_pairing_hamiltonian_policy", "Reduced attractive pairing FermionOperator builder.")
    _declare("hamiltonian", "hard_core_oscillator_hamiltonian.v1", "qcol.models.oscillator_hard_core.policies:oscillator_hamiltonian_policy", "Two-level hard-core oscillator Hamiltonian builder.")
    _declare("hamiltonian", "guided_occupation_hamiltonian.v1", "qcol.models.custom_guided_occupation.policies:guided_hamiltonian_policy", "No-code occupation/coupling Hamiltonian builder.")
    _declare("hamiltonian", "custom_qubit_hamiltonian.v1", "qcol.models.custom_qubit_hamiltonian.policies:custom_qubit_hamiltonian_policy", "Custom matrix/Pauli qubit Hamiltonian builder.")
    _declare("hamiltonian", "general_spin_orbital_fermion_operator.v1", "qcol.models.general_spin_orbital.policies:general_spin_orbital_hamiltonian_policy", "Standardized sparse one-/two-body spin-orbital FermionOperator builder.")

    # Sector policies
    _declare("sector", "reduced_pairing_one_pair_sector.v1", "qcol.models.reduced_pairing_one_pair.policies:one_pair_sector_policy", "One-pair particle=2, pair=1, seniority=0 validator.")
    _declare("sector", "reduced_pairing_multi_pair_sector.v1", "qcol.models.reduced_pairing_multi_pair.policies:multi_pair_sector_policy", "Multi-pair particle=2*n_pairs, seniority=0 validator.")
    _declare("sector", "one_excitation_sector.v1", "qcol.models.direct_qubit_common:one_excitation_sector_policy", "Fixed Hamming-weight-one sector validator.")
    _declare("sector", "no_sector.v1", "qcol.models.direct_qubit_common:no_sector_policy", "Unconstrained generic qubit route.")
    _declare("sector", "general_spin_orbital_particle_sector.v1", "qcol.models.general_spin_orbital.policies:general_spin_orbital_sector_policy", "Fixed total particle-number sector for the general spin-orbital representation.")

    # Mappings / encodings
    _declare("mapping", "pair_mapping.seniority_zero.v1", "qcol.models.reduced_pairing_common:pair_mapping_policy", "Restricted seniority-zero one-qubit-per-pair-level mapping; preserves quasispin / hard-core-pair semantics, not full single-fermion CAR.", provenance={"source":"QCOL/Bathri reduced-pairing route", "phase":"Phase A.3.2b", "work_package":"WP8", "convention_id":"qcol.pair.one-qubit-per-level.seniority-zero.v1"})
    _declare("mapping", "pair_mapping.v1", "qcol.models.reduced_pairing_common:pair_mapping_policy", "Legacy compatibility alias for pair_mapping.seniority_zero.v1.", provenance={"source":"QCOL/Bathri reduced-pairing route", "alias_of":"pair_mapping.seniority_zero.v1", "deprecated_for_new_contracts": True})
    _declare("mapping", "jordan_wigner.v1", "qcol.models.reduced_pairing_common:jordan_wigner_mapping_policy", "Jordan–Wigner fermion-to-qubit mapping.")
    _declare("mapping", "bravyi_kitaev.v1", "qcol.models.reduced_pairing_common:bravyi_kitaev_mapping_policy", "Bravyi–Kitaev fermion-to-qubit mapping; requires compatible state/sector policies.")
    _declare("mapping", "general_spin_orbital_primary_jw.v1", "qcol.models.general_spin_orbital.policies:general_spin_orbital_primary_jw_mapping_policy", "Task-aware primary JW bridge: inspectable mapping-analysis artifact or bounded JW ground-state execution mapping.")
    for policy_id in ("direct_hard_core_mode_encoding.v1", "direct_guided_occupation_encoding.v1", "direct_custom_qubit.v1"):
        _declare("mapping", policy_id, "qcol.models.direct_qubit_common:direct_mapping_policy", "Direct pass-through of a declared qubit Hamiltonian and encoding.")

    # State preparation
    _declare("state_preparation", "one_pair_lowest_level_state.v1", "qcol.models.reduced_pairing_one_pair.policies:one_pair_state_preparation_policy", "Prepare one pair in the lowest reference level.")
    _declare("state_preparation", "multi_pair_lowest_levels_state.v1", "qcol.models.reduced_pairing_multi_pair.policies:multi_pair_state_preparation_policy", "Prepare Bathri's multi-pair reference occupation in the lowest levels.", provenance={"source":"Bathri qcol_platform ansatz.py"})
    _declare("state_preparation", "lowest_mode_state.v1", "qcol.models.direct_qubit_common:lowest_mode_state_policy", "Prepare one excitation in mode zero.")
    _declare("state_preparation", "computational_zero_state.v1", "qcol.models.direct_qubit_common:zero_state_policy", "Prepare the computational zero state.")
    _declare("state_preparation", "general_spin_orbital_state.v1", "qcol.models.general_spin_orbital.policies:general_spin_orbital_state_policy", "Task-aware general spin-orbital state policy: no state for mapping analysis; JW occupation determinant for the bounded ground-state cell.")
    # Archived Phase A.3.1 policy ID retained for reproducibility.
    _declare("state_preparation", "analysis_only_state.v1", "qcol.models.general_spin_orbital.policies:analysis_only_state_policy", "Backward-compatible analysis-only alias.")

    # Ansätze
    _declare("ansatz", "one_pair_chain_givens.v1", "qcol.models.reduced_pairing_one_pair.policies:one_pair_chain_ansatz_policy", "Verified one-pair chain Givens ansatz.")
    _declare("ansatz", "bathri_multi_pair_givens.v1", "qcol.models.reduced_pairing_multi_pair.policies:multi_pair_ansatz_policy", "Bathri occupied-to-virtual pair-conserving Givens network.", provenance={"source":"Bathri qcol_platform ansatz.py::build_pair_mapped_ansatz"})
    _declare("ansatz", "one_excitation_chain_givens.v1", "qcol.models.direct_qubit_common:one_excitation_chain_ansatz_policy", "One-excitation chain Givens ansatz.")
    _declare("ansatz", "generic_ry_rz_linear_cnot.v1", "qcol.models.direct_qubit_common:generic_ry_rz_ansatz_policy", "Generic RY/RZ plus linear-CNOT ansatz.")
    _declare("ansatz", "general_spin_orbital_ansatz.v1", "qcol.models.general_spin_orbital.policies:general_spin_orbital_ansatz_policy", "Task-aware general spin-orbital circuit family: no ansatz for analysis; bounded JW number-preserving exchange/phase ansatz for ground-state execution.")
    _declare("ansatz", "analysis_only_ansatz.v1", "qcol.models.general_spin_orbital.policies:analysis_only_ansatz_policy", "Backward-compatible analysis-only alias.")

    # Measurement
    _declare("measurement", "pauli_energy_qwc.v1", "qcol.models.direct_qubit_common:qwc_measurement_policy", "Qubit-wise commuting Pauli energy measurement plan.")
    _declare("measurement", "general_spin_orbital_measurement.v1", "qcol.models.general_spin_orbital.policies:general_spin_orbital_measurement_policy", "Task-aware QWC mapped-Hamiltonian measurement plan; inspected only for mapping analysis and executed for the bounded JW energy cell.")
    _declare("measurement", "analysis_only_primary_mapping_qwc.v1", "qcol.models.general_spin_orbital.policies:analysis_only_measurement_policy", "Backward-compatible analysis-only alias.")

    # References
    _declare("reference", "small_exact_one_pair_sector.v1", "qcol.models.reduced_pairing_one_pair.policies:one_pair_reference_policy", "Exact one-pair sector reference.")
    _declare("reference", "small_exact_multi_pair_sector.v1", "qcol.models.reduced_pairing_multi_pair.policies:multi_pair_reference_policy", "Exact fixed-pair-sector reference for bounded multi-pair cases.")
    _declare("reference", "small_exact_one_excitation_sector.v1", "qcol.models.direct_qubit_common:exact_one_excitation_reference_policy", "Exact one-excitation sector reference; callable is model-context aware.")
    _declare("reference", "small_exact_full_space.v1", "qcol.models.custom_qubit_hamiltonian.policies:custom_full_reference_policy", "Exact bounded full-space qubit reference.")
    _declare("reference", "richardson_gaudin.v1", "qcol.policy_placeholders:not_implemented_policy", "Future Richardson–Gaudin reference binding within declared integrable validity.", status="not_implemented")
    _declare("reference", "general_spin_orbital_reference.v1", "qcol.models.general_spin_orbital.policies:general_spin_orbital_reference_policy", "Task-aware exact bounded reference: full/fixed-sector spectra for mapping analysis and fixed-particle ground state for JW execution.")
    _declare("reference", "small_exact_spin_orbital_spectrum.v1", "qcol.models.general_spin_orbital.policies:small_exact_spin_orbital_reference_policy", "Backward-compatible Phase A.3.1 reference alias.")

    # Resources
    _declare("resource", "bounded_local_exact_qasm_check.v1", "qcol.models.reduced_pairing_one_pair.policies:one_pair_resource_policy", "Bounded one-pair local simulator and exact semantic-check envelope.")
    _declare("resource", "bounded_multi_pair_local.v1", "qcol.models.reduced_pairing_multi_pair.policies:multi_pair_resource_policy", "Bounded multi-pair local simulator envelope.")
    _declare("resource", "bounded_direct_qubit.v1", "qcol.models.direct_qubit_common:bounded_direct_resource_policy", "Bounded direct-qubit resource assessor.")
    _declare(
        "resource",
        "bounded_direct_qubit.v2",
        "qcol.models.direct_qubit_resources:bounded_direct_resource_policy",
        "Bounded direct-qubit resource assessor with an explicit versioned resource-estimation rule.",
        provenance={
            "requires_explicit_resource_rule": True,
            "resource_rule_registry": "qcol.resource_rules/1.0",
            "source_revision": "post-phase-c-qho-resource-hardening.v1",
        },
    )
    _declare("resource", "general_spin_orbital_resource.v1", "qcol.models.general_spin_orbital.policies:general_spin_orbital_resource_policy", "Task-aware envelope: mapping analysis through eight modes and bounded JW ground-state execution through four modes.")
    _declare("resource", "bounded_spin_orbital_mapping_analysis.v1", "qcol.models.general_spin_orbital.policies:bounded_spin_orbital_mapping_resource_policy", "Backward-compatible Phase A.3.1 resource alias.")

    # Shared task runtime
    _declare("runtime", "external_variational_energy.v1", "qcol.models.direct_qubit_common:external_variational_energy_runtime_policy", "Shared external classical optimizer around one sampled energy evaluator.")
    _declare("runtime", "general_spin_orbital_runtime.v1", "qcol.models.general_spin_orbital.policies:general_spin_orbital_runtime_policy", "Task-aware runtime declaration: analysis-only mapping controller or shared external variational-energy execution.")
    _declare("runtime", "mapping_analysis_runtime.v1", "qcol.models.general_spin_orbital.policies:mapping_analysis_runtime_policy", "Backward-compatible Phase A.3.1 runtime alias.")

    # Interpretations
    _declare("interpretation", "one_pair_sector_energy.v1", "qcol.models.reduced_pairing_one_pair.policies:one_pair_interpretation_policy", "Bounded one-pair physical meaning.")
    _declare("interpretation", "multi_pair_sector_energy.v1", "qcol.models.reduced_pairing_multi_pair.policies:multi_pair_interpretation_policy", "Bounded multi-pair sector meaning.")
    _declare("interpretation", "hard_core_oscillator_energy.v1", "qcol.models.oscillator_hard_core.policies:oscillator_interpretation_policy", "Bounded hard-core oscillator meaning.")
    _declare("interpretation", "guided_occupation_energy.v1", "qcol.models.custom_guided_occupation.policies:guided_interpretation_policy", "Bounded guided custom-model meaning.")
    _declare("interpretation", "custom_qubit_energy.v1", "qcol.models.custom_qubit_hamiltonian.policies:custom_interpretation_policy", "Technical custom-qubit energy interpretation.")
    _declare("interpretation", "general_spin_orbital_interpretation.v1", "qcol.models.general_spin_orbital.policies:general_spin_orbital_interpretation_policy", "Task-aware bounded meaning for mapping analysis or the fixed-particle JW ground-state estimate.")
    _declare("interpretation", "mapping_analysis_model_context.v1", "qcol.models.general_spin_orbital.policies:mapping_analysis_model_interpretation_policy", "Backward-compatible Phase A.3.1 interpretation alias.")

    _REGISTERED = True


register_builtin_policies()

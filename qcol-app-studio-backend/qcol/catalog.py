"""Pure-JSON QCOL model-registry UI catalog.

The catalog describes supported no-code entrances and honest support states. It
contains no scientific execution logic and is safe to import when Cirq is not
loaded yet.
"""
from __future__ import annotations

from typing import Any, Dict

from .config import REFERENCE_POLICY
from .model_registry import public_model_registry
from .model_ui_schema import public_qho_ui_catalog
from .state import public_state_boundary_contract
from .task_registry import public_task_registry
from .model_task_matrix import public_model_task_matrix
from .mappings import public_mapping_registry
from .mapping_policies import (
    public_mapping_realization_vocabulary,
    vocabulary_fingerprint,
    public_pair_mapping_migration_catalog,
    pair_mapping_migration_catalog_fingerprint,
    public_spin_orbital_mapping_migration_catalog,
    spin_orbital_mapping_migration_catalog_fingerprint,
    public_a3_2b_exit_decision,
)
from .mapping_policies.profiles import (
    public_wp11_jw_accepted_composition_catalog,
    wp11_jw_accepted_composition_catalog_fingerprint,
)
from .policy_contract_catalog import public_declarative_policy_contract_catalog, policy_contract_catalog_fingerprint
from .implementation_bindings import (
    public_implementation_binding_catalog,
    implementation_binding_catalog_fingerprint,
)
from .compatibility import (
    compatibility_rule_catalog_fingerprint,
    public_compatibility_rule_catalog,
)
from .realization_variants import (
    public_realization_resolver_catalog,
    realization_resolver_catalog_fingerprint,
    public_model_task_realization_catalog,
    model_task_realization_catalog_fingerprint,
)
from .acceptance import (
    public_acceptance_fingerprint_catalog,
    acceptance_fingerprint_catalog_fingerprint,
    public_acceptance_harness_catalog,
    acceptance_harness_catalog_fingerprint,
)
from .governance import (
    public_governance_catalog,
    governance_catalog_fingerprint,
    public_allowed_request_patch_registry,
    allowed_request_patch_registry_fingerprint,
    build_a3_2c_release_decision,
    build_phase_b_handoff_contract,
)
from .advisor import (
    public_deterministic_advisor_catalog,
    deterministic_advisor_catalog_fingerprint,
)
from .comparison import public_phase_c_catalog, phase_c_catalog_fingerprint
from .semantic_authority import (
    public_semantic_authority_catalog,
    semantic_authority_catalog_fingerprint,
)
from .execution import public_execution_adapter_catalog
from .scientific_core import public_scientific_core_catalog, public_user_navigation_catalog
from .parameter_ownership import public_parameter_ownership_catalog
from .failure_model import public_failure_model_contract
from .composition_root import public_composition_root_contract
from .versioning import public_version_compatibility_policy
from .observability import public_observability_contract
from .fermion_registry import (
    FERMION_REGISTRY_VERSION,
    get_fermion_problem_spec,
    public_fermion_problem_catalog,
)


def get_catalog() -> Dict[str, Any]:
    fermion_all = public_fermion_problem_catalog(include_unavailable=True)
    fermion_selectable = [
        item for item in fermion_all
        if item.get("selectable") and item.get("executable")
    ]
    fermion_future = [item for item in fermion_all if not item.get("executable")]
    default_fermion = get_fermion_problem_spec("four_level_one_pair").to_public_dict()
    default_fields = {
        item["key"]: item
        for item in default_fermion["parameter_schema"]["fields"]
    }
    mapping_plugins = public_mapping_registry()["plugins"]
    qho_catalog = public_qho_ui_catalog()

    return {
        "product": {
            "name": "QCOL Model × Task Modelling Journey",
            "phase": "Pre-Unified-Baseline hardening — semantic authority, taxonomy, resource and execution boundaries",
            "default_execution": "local_simulator",
            "reference_policy": REFERENCE_POLICY,
            "feedback_enabled": True,
            "phase_b_handoff_ready": True,
            "phase_b_advisor_runtime_implemented": True,
            "phase_b_advisor_type": "deterministic_rules_only",
            "phase_c_try_compare_implemented": True,
            "phase_c_outcomes": ["ADOPT", "REJECT", "INCONCLUSIVE"],
            "provider_adapters_enabled": False,
            "qho_structural_integration_complete": True,
            "qho_schema_driven_ui_complete": True,
            "semantic_authority_invariant_enabled": True,
            "model_family_authority": "navigation_and_grouping_only",
            "resource_authority": "owner.resource_assessor",
            "semantic_authority_rule": "one semantic fact -> one authoritative owner -> explicit inputs -> read-only consumers",
            "integrity_i1_merged": False,
            "fermion_registry_version": FERMION_REGISTRY_VERSION,
        },
        "semantic_authority": {
            "catalog": public_semantic_authority_catalog(),
            "fingerprint": semantic_authority_catalog_fingerprint(),
        },
        "user_navigation": public_user_navigation_catalog(),
        "scientific_core": public_scientific_core_catalog(),
        "parameter_ownership": public_parameter_ownership_catalog(),
        "composition_root": public_composition_root_contract(),
        "failure_model": public_failure_model_contract(),
        "version_compatibility": public_version_compatibility_policy(),
        "observability": public_observability_contract(),
        "state_boundary": public_state_boundary_contract(),
        "model_classifications": [
            {
                "model_id": row["model_id"],
                "model_version": row["model_version"],
                "family": row.get("family"),
                "family_authority": row.get("family_authority"),
                "classification": row.get("classification"),
            }
            for row in public_model_registry()["contracts"]
        ],
        "execution_adapters": public_execution_adapter_catalog(),
        "backends": [
            {"id": "ibm", "label": "IBM", "status": "target_only"},
            {"id": "google", "label": "Google", "status": "target_only"},
            {"id": "aws", "label": "AWS", "status": "target_only"},
        ],
        "run_modes": [
            {
                "id": "vqe",
                "label": "External VQE loop (COBYLA)",
                "description": "Optimizer proposes θ and repeatedly calls the same verified energy evaluator.",
            },
            {
                "id": "single_evaluation",
                "label": "Single validated θ evaluation",
                "description": "One energy evaluation; no optimizer-convergence claim.",
            },
        ],
        "model_families": [
            {
                "id": "oscillator",
                "label": "Oscillators",
                "support_status": "four_independent_experimental_model_contracts",
                "description": (
                    "Choose one bounded nuclear QHO interaction profile. The interface "
                    "renders parameters from the selected ModelContract; fixed interactions "
                    "are not shown as editable controls."
                ),
                **qho_catalog,
                # Backward-compatible library shape for older Browser clients.
                "problems": [
                    {
                        "id": item["model_id"],
                        "model_id": item["model_id"],
                        "label": item["label"],
                        "status": item["execution_status"],
                        "parameter_schema": item["parameter_fields"],
                    }
                    for item in qho_catalog["models"]
                ],
                "legacy_model_contract": {
                    "model_id": "nuclear.oscillator.hard_core.one_quantum",
                    "status": "retained_for_phase_c_regression_not_shown_as_primary_qho_choice",
                },
                "review": {
                    "scientific_owner": "Q-Lab / QHO integration",
                    "source_credit": "Interaction menu adapted from D. Chauhan's QHO module",
                    "scientific_review_status": (
                        "structural and UI integration complete; each new cell remains "
                        "experimental pending its own acceptance promotion"
                    ),
                },
            },
            {
                "id": "fermion_pairing",
                "label": "Fermions",
                "support_status": "execution_ready_problem_specific_contracts",
                "description": (
                    "Choose a physical fermion problem first.  Each problem declares its "
                    "own sector, mapping, initial-state, ansatz, constraints, and reference policy."
                ),
                "default_problem": "four_level_one_pair",
                "problems": fermion_selectable,
                "registered_future_problems": fermion_future,
                "schema_endpoint": "/catalog/fermion-problems/{problem_id}",
                "defaults": {
                    "problem": "four_level_one_pair",
                    "n_levels": default_fields["n_levels"]["fixed_value"],
                    "epsilon": default_fields["epsilon"]["default"],
                    "g": default_fields["g"]["default"],
                    "n_particles": default_fields["n_particles"]["fixed_value"],
                    "n_pairs": default_fields["n_pairs"]["fixed_value"],
                    "seniority": default_fields["seniority"]["fixed_value"],
                    "energy_unit": default_fields["energy_unit"]["default"],
                },
                "mapping": {
                    "id": "pair_mapping",
                    "label": "Pair mapping",
                    "selection": "problem_contract",
                    "status": "execution_ready_for_registered_reduced_pairing_routes",
                },
                "nested_routes": [
                    {
                        "id": "reduced_pairing",
                        "label": "Reduced-pairing model contracts",
                        "description": "One-pair and multi-pair seniority-zero routes with automatic pair mapping.",
                        "internal_model_family": "fermion_pairing",
                    },
                    {
                        "id": "general_spin_orbital",
                        "label": "General spin-orbital — Mapping Explorer / JW ground state",
                        "description": (
                            "Declare a general spin-orbital FermionOperator. Compare JW and BK "
                            "without a VQE claim, or run the bounded JW-only fixed-particle "
                            "ground-state cell."
                        ),
                        "internal_model_family": "general_spin_orbital",
                        "status": "mapping_analysis_verified_jw_ground_state_acceptance_verified",
                    },
                ],
            },
            {
                "id": "general_spin_orbital",
                "top_level": False,
                "parent_family_id": "fermion_pairing",
                "label": "General spin-orbital representation",
                "support_status": "mapping_analysis_verified_jw_ground_state_acceptance_verified",
                "description": (
                    "Declare a finite sparse one-/two-body FermionOperator input. The "
                    "mapping-analysis task compares Jordan–Wigner and Bravyi–Kitaev on "
                    "the same mode ordering and particle sector. The first execution task "
                    "uses Jordan–Wigner, an occupation determinant, a mapping-aware fermionic "
                    "swap-network ansatz, and an exact bounded fixed-particle reference."
                ),
                "default_problem": "mapping_explorer",
                "problems": [
                    {
                        "id": "mapping_explorer",
                        "label": "JW / BK Mapping Explorer",
                        "task_id": "mapping_analysis",
                        "status": "acceptance_verified_analysis_only",
                    },
                    {
                        "id": "jw_ground_state",
                        "label": "JW fixed-particle ground-state energy",
                        "task_id": "ground_state_energy",
                        "status": "acceptance_verified_execution_cell",
                    },
                ],
                "defaults": {
                    "problem": "mapping_explorer",
                    "n_modes": 4,
                    "particle_species": "neutron",
                    "mode_labels": "neutron|a|m=+1/2\nneutron|a|m=-1/2\nneutron|b|m=+1/2\nneutron|b|m=-1/2",
                    "one_body_terms": "0,0,0.0\n1,1,0.0\n2,2,1.0\n3,3,1.0\n0,2,0.2\n2,0,0.2\n1,3,0.2\n3,1,0.2",
                    "two_body_terms": "0,1,0,1,0.08\n0,2,0,2,0.08\n0,3,0,3,0.08\n1,2,1,2,0.08\n1,3,1,3,0.08\n2,3,2,3,0.08",
                    "target_particle_number": 2,
                    "initial_occupied_modes": "0,1",
                    "ansatz_layers": 1,
                    "declared_symmetries": "particle_number",
                    "coefficient_convention": "explicit_operator_coefficient",
                    "energy_unit": "MeV",
                },
                "mapping_plugins": [
                    {
                        "id": item["mapping_id"],
                        "label": item["label"],
                        "analysis_status": item["support_by_task"]["mapping_analysis"],
                        "ground_state_status": item["support_by_task"]["ground_state_energy"],
                        "execution_boundary": item["execution_boundary"],
                    }
                    for item in mapping_plugins
                ],
                # Backward-compatible default-task alias retained for A.3.1 clients.
                "task": {
                    "id": "mapping_analysis",
                    "label": "JW / BK mapping analysis",
                    "status": "acceptance_verified",
                    "backend_required": False,
                    "shots_required": False,
                },
                "tasks": [
                    {
                        "id": "mapping_analysis",
                        "label": "JW / BK mapping analysis",
                        "status": "acceptance_verified",
                        "backend_required": False,
                        "shots_required": False,
                    },
                    {
                        "id": "ground_state_energy",
                        "label": "JW fixed-particle ground-state energy",
                        "status": "acceptance_verified",
                        "backend_required": True,
                        "shots_required": True,
                        "mapping_id": "jordan_wigner.v1",
                    },
                ],
                "execution_boundary": {
                    "jordan_wigner": (
                        "Mapping analysis is verified. A bounded 2–4-mode fixed-particle "
                        "ground-state cell is acceptance-verified at the declared WP11 2–4-mode "
                        "fixed-particle scale with mapped fermionic generators."
                    ),
                    "bravyi_kitaev": (
                        "Transformation and analysis are verified. Ground-state state "
                        "preparation, sector diagnostics, and ansatz acceptance are not executable."
                    ),
                },
            },
            {
                "id": "custom",
                "label": "Custom",
                "support_status": "execution_ready_bounded_inputs",
                "description": "A guided no-code occupation/coupling model, or advanced matrix/Pauli input.",
                "routes": [
                    {"id": "guided", "label": "Guided occupation-coupling model (no-code)"},
                    {"id": "matrix", "label": "Dense Hermitian matrix (advanced)"},
                    {"id": "pauli", "label": "Pauli terms (advanced)"},
                ],
                "defaults": {
                    "route": "guided",
                    "model_name": "custom occupation-coupling model",
                    "n_modes": 2,
                    "onsite_energies": "0.0, 1.0",
                    "couplings": "0, 1, 0.2",
                    "energy_offset": 0.0,
                    "matrix": "[[0, 1], [1, 0]]",
                    "pauli_terms": "X0: 1.0",
                    "n_qubits": 1,
                    "ansatz_layers": 1,
                    "energy_unit": "MeV",
                },
            },
        ],
        "model_contract_registry": public_model_registry(),
        "task_contract_registry": public_task_registry(),
        "model_task_matrix": public_model_task_matrix(),
        "model_task_realization_surface": {
            "schema_version": public_model_task_realization_catalog()["schema_version"],
            "surface_version": public_model_task_realization_catalog()["surface_version"],
            "fingerprint": model_task_realization_catalog_fingerprint(),
            "endpoint": "/catalog/model-task-realizations",
            "matrix_dimensions": ["model", "task"],
            "internal_variant_records": True,
            "unsupported_variants_runnable": False,
            "historical_jw_failure_code": "ANSATZ_GENERATOR_MAPPING_MISMATCH",
            "bk_ground_state_selectable": False,
            "evidence_pickle_free": True,
            "second_runtime_created": False,
            "scientific_behavior_change": False,
        },
        "mapping_plugin_registry": public_mapping_registry(),
        "mapping_realization_vocabulary": {
            "schema_version": public_mapping_realization_vocabulary()["schema_version"],
            "vocabulary_version": public_mapping_realization_vocabulary()["vocabulary_version"],
            "fingerprint": vocabulary_fingerprint(),
            "endpoint": "/catalog/mapping-realization-vocabulary",
            "scientific_behavior_change": False,
        },
        "mapping_realization_policy_contracts": {
            "schema_version": public_declarative_policy_contract_catalog()["schema_version"],
            "contracts_version": public_declarative_policy_contract_catalog()["contracts_version"],
            "fingerprint": policy_contract_catalog_fingerprint(),
            "endpoint": "/catalog/mapping-realization-policy-contracts",
            "contracts_are_executable": False,
            "live_policy_migration_performed": False,
            "scientific_behavior_change": False,
        },
        "mapping_realization_implementation_bindings": {
            "schema_version": public_implementation_binding_catalog()["schema_version"],
            "catalog_version": public_implementation_binding_catalog()["catalog_version"],
            "fingerprint": implementation_binding_catalog_fingerprint(),
            "endpoint": "/catalog/mapping-realization-implementation-bindings",
            "callable_payload_withheld": True,
            "missing_binding_status": "recognized_not_executable",
            "live_policy_migration_performed": False,
            "scientific_behavior_change": False,
        },
        "mapping_realization_compatibility_rules": {
            "schema_version": public_compatibility_rule_catalog()["schema_version"],
            "catalog_version": public_compatibility_rule_catalog()["catalog_version"],
            "fingerprint": compatibility_rule_catalog_fingerprint(),
            "endpoint": "/catalog/compatibility-rules",
            "rule_count": public_compatibility_rule_catalog()["rule_registry"]["rule_count"],
            "pairwise_and_global_phases_separate": True,
            "live_rule_gate_enforced": False,
            "live_policy_migration_performed": False,
            "scientific_behavior_change": False,
        },
        "mapping_realization_resolver": {
            "schema_version": public_realization_resolver_catalog()["schema_version"],
            "catalog_version": public_realization_resolver_catalog()["catalog_version"],
            "fingerprint": realization_resolver_catalog_fingerprint(),
            "endpoint": "/catalog/realization-resolver",
            "resolve_endpoint": "/catalog/realization-variants/resolve",
            "returns_named_reports": True,
            "live_resolver_gate_enforced": True,
            "fatal_fail_blocks_runtime": True,
            "legacy_run_pipeline_rewired": False,
            "live_policy_migration_performed": False,
            "scientific_behavior_change": False,
        },
        "acceptance_evidence_fingerprints": {
            "schema_version": public_acceptance_fingerprint_catalog()["schema_version"],
            "catalog_version": public_acceptance_fingerprint_catalog()["catalog_version"],
            "fingerprint": acceptance_fingerprint_catalog_fingerprint(),
            "endpoint": "/catalog/acceptance-evidence-fingerprints",
            "stable_stale_code": "ACCEPTANCE_EVIDENCE_STALE",
            "exact_scale_bound": True,
            "live_policy_migration_performed": False,
            "scientific_behavior_change": False,
        },
        "generic_three_gate_acceptance_harness": {
            "schema_version": public_acceptance_harness_catalog()["schema_version"],
            "catalog_version": public_acceptance_harness_catalog()["catalog_version"],
            "fingerprint": acceptance_harness_catalog_fingerprint(),
            "endpoint": "/catalog/acceptance-harness",
            "gate_order": ["mapper_conformance", "composition_conformance", "cell_acceptance"],
            "a3_2a_exit_ready": public_acceptance_harness_catalog()["a3_2a_exit_ready"],
            "live_policy_migration_performed": False,
            "scientific_behavior_change": False,
        },
        "pair_mapping_policy_migration": {
            "schema_version": public_pair_mapping_migration_catalog()["schema_version"],
            "catalog_version": public_pair_mapping_migration_catalog()["catalog_version"],
            "fingerprint": pair_mapping_migration_catalog_fingerprint(),
            "endpoint": "/catalog/mapping-policies/pair-mapping",
            "mapping_scope": "restricted_seniority_zero_subspace",
            "preserved_algebra": "quasispin / hard-core-pair algebra",
            "one_pair_status": "acceptance_verified",
            "multi_pair_status": "experimental",
            "live_policy_migration_performed": True,
            "scientific_behavior_change": False,
        },
        "spin_orbital_mapping_policy_migration": {
            "schema_version": public_spin_orbital_mapping_migration_catalog()["schema_version"],
            "catalog_version": public_spin_orbital_mapping_migration_catalog()["catalog_version"],
            "fingerprint": spin_orbital_mapping_migration_catalog_fingerprint(),
            "jw_endpoint": "/catalog/mapping-policies/jordan-wigner",
            "bk_endpoint": "/catalog/mapping-policies/bravyi-kitaev",
            "exit_endpoint": "/catalog/mapping-policies/a3-2b-exit",
            "jw_mapper_status": "verified",
            "jw_mapping_analysis_status": "acceptance_verified",
            "jw_current_composition_status": "rejected",
            "jw_ground_state_cell_status": "not_verified",
            "bk_mapper_status": "verified",
            "bk_mapping_analysis_status": "acceptance_verified",
            "bk_raw_popcount_is_particle_number": False,
            "bk_ground_state_composition_status": "unresolved",
            "bk_full_execution_status": "recognized_not_executable",
            "a3_2b_exit_status": public_a3_2b_exit_decision()["status"],
            "scientific_status_promoted": False,
            "scientific_behavior_change": False,
        },
        "jw_accepted_composition": {
            "schema_version": public_wp11_jw_accepted_composition_catalog()["schema_version"],
            "catalog_version": public_wp11_jw_accepted_composition_catalog()["catalog_version"],
            "fingerprint": wp11_jw_accepted_composition_catalog_fingerprint(),
            "endpoint": "/catalog/jw-accepted-composition",
            "promotion_endpoint": "/catalog/jw-accepted-composition/promotion",
            "mapper_status": "verified",
            "composition_status": "acceptance_verified",
            "cell_status": "acceptance_verified",
            "historical_negative_fixture_preserved": True,
            "bk_full_execution_enabled": False,
            "second_runtime_created": False,
            "scientific_behavior_change": True,
        },
        "governance_and_phase_b_handoff": {
            "schema_version": public_governance_catalog()["schema_version"],
            "catalog_version": public_governance_catalog()["catalog_version"],
            "fingerprint": governance_catalog_fingerprint(),
            "endpoint": "/catalog/governance",
            "published_statuses_endpoint": "/catalog/governance/statuses",
            "allowed_patches_endpoint": "/catalog/advisor-handoff/allowed-patches",
            "release_endpoint": "/catalog/a3-2c-release",
            "schema_versions_separate_from_implementation_versions": True,
            "scientific_owner_required_per_policy": True,
            "unqualified_mapping_verified_badge_allowed": False,
            "phase_b_handoff_ready": build_phase_b_handoff_contract().phase_b_may_start,
            "phase_b_advisor_runtime_implemented": True,
            "second_runtime_created": False,
        },
        "a3_2c_governed_release": {
            "release_id": build_a3_2c_release_decision().release_id,
            "release_version": build_a3_2c_release_decision().release_version,
            "mapper_gate": build_a3_2c_release_decision().gate_attestations[0].status.value,
            "composition_gate": build_a3_2c_release_decision().gate_attestations[1].status.value,
            "cell_gate": build_a3_2c_release_decision().gate_attestations[2].status.value,
            "fingerprint_match": build_a3_2c_release_decision().fingerprint_match,
            "evidence_reproducible": build_a3_2c_release_decision().evidence_reproducible,
            "published_cell_status": build_a3_2c_release_decision().published_cell_status,
            "phase_a3_2c_exit_ready": build_a3_2c_release_decision().phase_a3_2c_exit_ready,
        },
        "deterministic_advisor": {
            "schema_version": public_deterministic_advisor_catalog()["schema_version"],
            "catalog_version": public_deterministic_advisor_catalog()["catalog_version"],
            "fingerprint": deterministic_advisor_catalog_fingerprint(),
            "endpoint": "/catalog/deterministic-advisor",
            "rules_endpoint": "/catalog/deterministic-advisor/rules",
            "run_endpoint": "/runs/{run_id}/advisor",
            "deterministic": True,
            "llm_used": False,
            "reads_sanitized_compatibility_evidence_resource_context": True,
            "allowlisted_patch_hypotheses_only": True,
            "automatic_execution_performed": False,
            "user_approval_required": True,
            "same_pipeline_entrypoint": "qcol.orchestrator.run_pipeline",
            "verification_retains_final_authority": True,
            "system_functional_when_disabled": True,
            "second_runtime_created": False,
        },
        "phase_c_try_compare": {
            "schema_version": public_phase_c_catalog()["schema_version"],
            "phase_version": public_phase_c_catalog()["phase_version"],
            "fingerprint": phase_c_catalog_fingerprint(),
            "endpoint": "/catalog/phase-c-try-compare",
            "runtime_endpoint": "/runs/{baseline_run_id}/try-compare",
            "comparison_endpoint": "/comparisons/{session_id}",
            "outcomes": ["ADOPT", "REJECT", "INCONCLUSIVE"],
            "explicit_user_approval_required": True,
            "same_pipeline_entrypoint": "qcol.orchestrator.run_pipeline",
            "automatic_replacement_performed": False,
            "verification_retains_final_authority": True,
            "second_runtime_created": False,
        },
        "phase_b_allowed_request_patches": {
            "registry_id": public_allowed_request_patch_registry()["registry_id"],
            "registry_version": public_allowed_request_patch_registry()["registry_version"],
            "fingerprint": allowed_request_patch_registry_fingerprint(),
            "rule_count": len(public_allowed_request_patch_registry()["contracts"]),
            "hypothesis_only": True,
            "user_approval_required": True,
            "same_pipeline_required": True,
            "verification_retains_final_authority": True,
        },
        "fermion_problem_registry": {
            "version": FERMION_REGISTRY_VERSION,
            "problems": fermion_all,
        },
        "epistemic_badges": [
            "MEASURED",
            "DERIVED",
            "REFERENCE — CLASSICAL",
            "VERIFIED",
            "DECLARED",
            "ILLUSTRATIVE / TARGET",
            "UNVERIFIED SUGGESTION",
            "INCONCLUSIVE",
        ],
    }


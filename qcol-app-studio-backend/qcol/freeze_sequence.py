"""Governed sequence from the hardened candidate to the Unified Baseline."""
from __future__ import annotations

from typing import Any


def public_unified_freeze_sequence_contract() -> dict[str, Any]:
    return {
        "schema_version": "qcol-unified-freeze-sequence/1.1",
        "current_package_role": "pre_merge_unified_baseline_candidate",
        "invariants": {
            "integrity_i1_donor_gate_is_not_a_merge": True,
            "bundled_donor_is_test_input_not_merged_source": True,
            "integrity_i1_merge_precedes_unified_baseline_freeze": True,
            "post_merge_fingerprint_regression_precedes_freeze": True,
            "full_unified_regression_precedes_manifest_issue": True,
            "unified_baseline_manifest_precedes_freeze_decision": True,
            "execution_realization_proof_follows_architecture_freeze": True,
            "no_second_runtime": True,
        },
        "ordered_steps": [
            {
                "step_id": "candidate.clean_environment",
                "label": "Clean accepted environment",
                "required_evidence": [
                    "qcol_scoped_environment_consistency",
                    "clean_isolated_environment_proof",
                ],
            },
            {
                "step_id": "candidate.scientific_regression",
                "label": "Complete scientific regression",
                "required_evidence": ["phase_a_b_c_qho_regressions"],
            },
            {
                "step_id": "integrity_i1.donor_gate",
                "label": "Integrity I1 donor gate",
                "required_evidence": ["exact_i1_archive_sha256", "i1_gate_pass"],
            },
            {
                "step_id": "integrity_i1.controlled_merge",
                "label": "Controlled Integrity I1 merge",
                "required_evidence": ["merge_manifest", "source_diff", "no_runtime_duplication"],
            },
            {
                "step_id": "integrity_i1.fingerprint_regression",
                "label": "Fingerprint regression",
                "required_evidence": [
                    "accepted_scientific_fingerprints_unchanged",
                    "explicit_new_integrity_fingerprints",
                ],
            },
            {
                "step_id": "unified.full_pre_freeze_regression",
                "label": "Full unified pre-freeze regression",
                "required_evidence": ["all_must_gates_pass", "critical_risks_zero"],
            },
            {
                "step_id": "unified.manifest",
                "label": "Issue UnifiedBaselineManifest",
                "required_evidence": ["merged_source_identity", "test_manifest", "environment_manifest"],
            },
            {
                "step_id": "unified.freeze",
                "label": "GO → Unified Baseline Freeze",
                "required_evidence": ["signed_freeze_decision"],
            },
        ],
        "post_freeze_execution_proof": [
            "minimal_execution_adapter_and_semantic_guards",
            "local_simulator_transport_conformance",
            "golden_vertical_slice_one_pair_ground_state",
            "golden_vertical_slice_qho_free",
            "quantum_app_studio_html_api_facade",
            "mentor_end_to_end_simulator_demo",
        ],
        "deferred_after_mentor_demo": [
            "i2_live_comparison_admission",
            "atomic_phase_c_orchestration",
            "sqlite_durable_state",
            "stronger_provider_integrity",
            "real_provider_adapter",
            "hardware_demo",
        ],
    }


__all__ = ["public_unified_freeze_sequence_contract"]

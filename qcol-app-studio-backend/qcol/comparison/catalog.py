"""Public Phase C catalog and release validation."""
from __future__ import annotations
from qcol.realization_policies.base import contract_fingerprint
from .fixtures import SCENARIO_IDS, build_phase_c_scenario
from .policies import public_comparison_policy_catalog

PHASE_C_VERSION = "1.0.0"


def public_phase_c_catalog() -> dict:
    scenarios = {name: build_phase_c_scenario(name) for name in SCENARIO_IDS}
    return {
        "schema_version": "qcol-phase-c-try-compare-catalog/1.0",
        "phase": "Phase C — User-approved Try / Compare",
        "phase_version": PHASE_C_VERSION,
        "objective": "Approve one safe patch, rerun the same QCOL pipeline, compare evidence under a declared uncertainty policy, and record ADOPT, REJECT, or INCONCLUSIVE without silent replacement.",
        "decision_loop": [
            "load baseline terminal run",
            "validate Phase B patch against the governed allowlist",
            "require explicit user approval",
            "prepare a new candidate request without mutating the baseline",
            "execute candidate through qcol.orchestrator.run_pipeline",
            "compare baseline and candidate evidence",
            "record ADOPT / REJECT / INCONCLUSIVE with both run IDs",
        ],
        "comparison_policies": public_comparison_policy_catalog(),
        "scenario_examples": scenarios,
        "definition_of_done": {
            "explicit_approval_required": True,
            "same_run_pipeline_required": True,
            "same_evidence_schema_required": True,
            "uncertainty_and_missing_metrics_explicit": True,
            "outcomes": ["ADOPT", "REJECT", "INCONCLUSIVE"],
            "silent_replacement_allowed": False,
            "decision_record_contains_both_run_ids": True,
            "verification_retains_final_authority": True,
        },
        "runtime_contract": {
            "canonical_pipeline_entrypoint": "qcol.orchestrator.run_pipeline",
            "second_runtime_created": False,
            "baseline_mutated": False,
            "automatic_replacement_performed": False,
        },
    }


def phase_c_catalog_fingerprint() -> str:
    return contract_fingerprint(public_phase_c_catalog())


def validate_phase_c_catalog() -> dict[str, bool]:
    catalog = public_phase_c_catalog()
    scenarios = catalog["scenario_examples"]
    return {
        "catalog_is_strict_json": isinstance(catalog, dict),
        "adopt_scenario_present": scenarios["adopt"]["comparison"]["outcome"] == "ADOPT",
        "reject_scenario_present": scenarios["reject"]["comparison"]["outcome"] == "REJECT",
        "inconclusive_scenario_present": scenarios["inconclusive"]["comparison"]["outcome"] == "INCONCLUSIVE",
        "mapping_resource_comparison_does_not_rank_physical_accuracy": not scenarios["mapping_adopt"]["comparison"]["physical_accuracy_ranking_claimed"],
        "explicit_approval_required": catalog["definition_of_done"]["explicit_approval_required"],
        "same_pipeline_required": catalog["definition_of_done"]["same_run_pipeline_required"],
        "no_silent_replacement": not catalog["definition_of_done"]["silent_replacement_allowed"],
        "both_run_ids_recorded": catalog["definition_of_done"]["decision_record_contains_both_run_ids"],
        "verification_final_authority": catalog["definition_of_done"]["verification_retains_final_authority"],
        "no_second_runtime": not catalog["runtime_contract"]["second_runtime_created"],
    }


__all__ = ["PHASE_C_VERSION", "public_phase_c_catalog", "phase_c_catalog_fingerprint", "validate_phase_c_catalog"]

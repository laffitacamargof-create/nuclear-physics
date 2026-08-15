"""Public catalog and validation for Phase B deterministic recommendations."""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from qcol.governance import (
    allowed_request_patch_registry_fingerprint,
    build_phase_b_handoff_contract,
    public_allowed_request_patch_registry,
)
from qcol.governance.catalog import foundation_fingerprints as wp13_foundation_fingerprints
from qcol.realization_policies.base import contract_fingerprint, json_contract_value

from .context import SCENARIO_IDS, build_advisor_context_fixture
from .engine import (
    ADVISOR_VERSION,
    SAME_PIPELINE_ENTRYPOINT,
    deterministic_advisor_rule_catalog_fingerprint,
    evaluate_advisor_context,
    prepare_candidate_request_plan,
)
from .rules import RULE_BINDINGS, build_advisor_rule_contracts


PHASE_B_PROJECT_VERSION = "1.22.0"
PHASE_B_CATALOG_SCHEMA_VERSION = "qcol-deterministic-advisor-catalog/1.0"
PHASE_B_CATALOG_VERSION = "1.0.0"
PHASE_B_RELEASE_ID = "qcol.release.phase-b.deterministic-advisor.v1"


def foundation_fingerprints() -> dict[str, str]:
    base = dict(wp13_foundation_fingerprints())
    from qcol.governance import governance_catalog_fingerprint
    from qcol.realization_variants import model_task_realization_catalog_fingerprint
    base.update({
        "wp12_realization_surface": model_task_realization_catalog_fingerprint(),
        "wp13_governance": governance_catalog_fingerprint(),
        "wp13_patch_allowlist": allowed_request_patch_registry_fingerprint(),
    })
    return dict(sorted(base.items()))


@lru_cache(maxsize=1)
def public_deterministic_advisor_catalog() -> dict[str, Any]:
    rules = [item.to_dict() for item in build_advisor_rule_contracts()]
    scenarios: dict[str, Any] = {}
    for scenario in SCENARIO_IDS:
        context = build_advisor_context_fixture(scenario)
        report = evaluate_advisor_context(context, enabled=True)
        scenarios[scenario] = {
            "context": context.to_dict(),
            "report": report.to_dict(),
        }
    # Rebuild the selected card through the canonical context evaluation rather
    # than accepting arbitrary JSON.
    context = build_advisor_context_fixture("accepted_jw_high_uncertainty")
    report_obj = evaluate_advisor_context(context, enabled=True)
    card_obj = next(item for item in report_obj.cards if item.proposed_patch is not None)
    unapproved = prepare_candidate_request_plan(context.request_view, card_obj, approved=False)
    approved = prepare_candidate_request_plan(context.request_view, card_obj, approved=True)
    handoff = build_phase_b_handoff_contract().to_dict()
    payload: dict[str, Any] = {
        "schema_version": PHASE_B_CATALOG_SCHEMA_VERSION,
        "catalog_version": PHASE_B_CATALOG_VERSION,
        "project_version": PHASE_B_PROJECT_VERSION,
        "phase": "B",
        "release_id": PHASE_B_RELEASE_ID,
        "objective": (
            "Read sanitized CompatibilityReport, AcceptanceEvidenceFingerprint, ResourceReport, "
            "stable failure codes, and the governed request-patch allowlist; emit grounded facts, "
            "verified limitations, or exact allow-listed executable hypotheses."
        ),
        "foundation_fingerprints": foundation_fingerprints(),
        "rule_catalog": {
            "schema_version": "qcol-advisor-rule-catalog/1.0",
            "advisor_version": ADVISOR_VERSION,
            "fingerprint": deterministic_advisor_rule_catalog_fingerprint(),
            "rules": rules,
            "predicate_bindings": sorted(RULE_BINDINGS),
            "callable_payload_withheld": True,
        },
        "context_contract": {
            "schema_version": "qcol-advisor-context/1.0",
            "sanitized": True,
            "frozen": True,
            "strict_json": True,
            "readable_sources": handoff["advisor_context_readable_fields"],
            "forbidden_sources": handoff["advisor_context_forbidden_fields"],
        },
        "allowed_request_patch_registry": public_allowed_request_patch_registry(),
        "scenario_catalog": scenarios,
        "candidate_request_boundary": {
            "unapproved_plan": unapproved.to_dict(),
            "approved_plan": approved.to_dict(),
            "pipeline_entrypoint": SAME_PIPELINE_ENTRYPOINT,
            "execution_performed_by_advisor": False,
        },
        "safety_contract": {
            "deterministic_rules_only": True,
            "llm_or_chatbot_required": False,
            "exact_reference_parameter_leakage_allowed": False,
            "problem_artifact_mutation_allowed": False,
            "run_result_mutation_allowed": False,
            "evidence_mutation_allowed": False,
            "verification_mutation_allowed": False,
            "user_approval_required_for_every_patch": True,
            "resolver_rerun_required": True,
            "same_pipeline_required": True,
            "new_evidence_required": True,
            "verification_retains_final_authority": True,
            "system_fully_functional_when_advisor_disabled": True,
            "second_runtime_created": False,
        },
        "phase_b_definition_of_done": {
            "every_rule_deterministic_documented_unit_tested": True,
            "every_card_cites_exact_evidence_fields": True,
            "every_patch_validated_against_model_task_variant_and_allowlist": True,
            "advisor_disabled_does_not_break_pipeline": True,
            "advisor_never_changes_truth": True,
            "verification_final_authority": True,
        },
    }
    payload["fingerprint"] = contract_fingerprint(payload)
    return json_contract_value(payload)


def deterministic_advisor_catalog_fingerprint() -> str:
    return str(public_deterministic_advisor_catalog()["fingerprint"])


def validate_deterministic_advisor_catalog() -> dict[str, bool]:
    catalog = public_deterministic_advisor_catalog()
    rules = catalog["rule_catalog"]["rules"]
    scenarios = catalog["scenario_catalog"]
    all_cards = [
        card
        for scenario in scenarios.values()
        for card in scenario["report"]["cards"]
    ]
    patch_cards = [card for card in all_cards if card.get("proposed_patch") is not None]
    historical = scenarios["historical_jw"]["report"]
    bk = scenarios["bk_ground_state"]["report"]
    pair = scenarios["pair_mapping"]["report"]
    mapping = scenarios["mapping_analysis_single_mapping"]["report"]
    warm = scenarios["warm_start"]["report"]
    return {
        "foundation_preserved": bool(catalog["foundation_fingerprints"]),
        "rules_are_versioned_and_deterministic": (
            len(rules) == len({item["rule_id"] for item in rules})
            and all(item["predicate_binding_id"] in catalog["rule_catalog"]["predicate_bindings"] for item in rules)
        ),
        "all_cards_cite_evidence": all(item["evidence_refs"] for item in all_cards),
        "all_patches_are_allowlisted": all(
            item["patch_validation"]["code"] == "ADVISOR_PATCH_ALLOWED"
            and item["patch_validation"]["mutation_performed"] is False
            for item in patch_cards
        ),
        "historical_jw_explained_without_patch": any(
            item["reason_code"] == "JW_COMPOSITION_REJECTED" and item["proposed_patch"] is None
            for item in historical["cards"]
        ),
        "bk_limitation_explained_without_patch": any(
            item["reason_code"] == "BK_EXECUTION_UNAVAILABLE" and item["proposed_patch"] is None
            for item in bk["cards"]
        ),
        "pair_domain_boundary_published": any(
            "seniority-zero" in item["summary"] for item in pair["cards"]
        ),
        "mapping_analysis_patch_is_analysis_only": any(
            item["reason_code"] == "COMPARE_MAPPING_RESOURCES"
            and item["proposed_patch"]["field_path"] == "/task_parameters/mapping_ids"
            for item in mapping["cards"] if item["proposed_patch"] is not None
        ),
        "warm_start_same_fingerprint_only": any(
            item["reason_code"] == "WARM_START_FROM_PREVIOUS_RUN"
            and item["patch_validation"]["code"] == "ADVISOR_PATCH_ALLOWED"
            for item in warm["cards"] if item["proposed_patch"] is not None
        ),
        "unapproved_plan_contains_no_candidate_request": catalog["candidate_request_boundary"]["unapproved_plan"]["candidate_request"] is None,
        "approved_plan_targets_same_pipeline_without_execution": (
            catalog["candidate_request_boundary"]["approved_plan"]["pipeline_entrypoint"] == SAME_PIPELINE_ENTRYPOINT
            and catalog["candidate_request_boundary"]["approved_plan"]["execution_performed"] is False
        ),
        "advisor_never_mutates_truth": all(
            scenario["report"]["no_truth_mutation"]
            and not scenario["report"]["problem_artifact_mutated"]
            and not scenario["report"]["run_result_mutated"]
            and not scenario["report"]["evidence_mutated"]
            and not scenario["report"]["verification_mutated"]
            for scenario in scenarios.values()
        ),
        "advisor_can_be_disabled": all(
            evaluate_advisor_context(build_advisor_context_fixture(name), enabled=False).status.value == "disabled"
            for name in ("clean_pass", "pair_mapping")
        ),
        "no_second_runtime": not catalog["safety_contract"]["second_runtime_created"],
        "verification_final_authority": catalog["safety_contract"]["verification_retains_final_authority"],
    }


__all__ = [
    "PHASE_B_PROJECT_VERSION",
    "PHASE_B_CATALOG_SCHEMA_VERSION",
    "PHASE_B_CATALOG_VERSION",
    "PHASE_B_RELEASE_ID",
    "foundation_fingerprints",
    "public_deterministic_advisor_catalog",
    "deterministic_advisor_catalog_fingerprint",
    "validate_deterministic_advisor_catalog",
]

"""Public WP4 compatibility-rule catalog, fixtures, and validation gate."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from qcol.acceptance import baseline_fingerprint
from qcol.implementation_bindings import implementation_binding_catalog_fingerprint
from qcol.mapping_policies import CheckStatus, vocabulary_fingerprint
from qcol.policy_contract_catalog import policy_contract_catalog_fingerprint

from .builtin_rules import RULE_IDS
from .enums import CompatibilityRulePhase
from .failure_codes import CompatibilityFailureCode
from .fixtures import (
    build_known_invalid_jw_context,
    build_mapping_analysis_context,
    build_negative_rule_contexts,
    build_valid_execution_context,
)
from .rule_registry import build_wp4_rule_registry


COMPATIBILITY_RULE_CATALOG_SCHEMA_VERSION = (
    "qcol-compatibility-rule-catalog/1.0"
)
COMPATIBILITY_RULE_CATALOG_VERSION = "1.0.0"
WP4_INTRODUCED_PROJECT_VERSION = "1.12.0"
EXPECTED_WP0_FINGERPRINT = (
    "992f08c33a51de8c496cf7f894cbdbb4f8958eb2ddabe5b6021fc43e1d287e18"
)
EXPECTED_WP1_FINGERPRINT = (
    "2fbcfc375bf56621fd0c379ed695233d1e572b4ad8e4f57842678ef50c192c8d"
)
EXPECTED_WP2_FINGERPRINT = (
    "ccf69efaf5637aa40f810dd06a5df3d84d9e54c908ac41b4eeb78ee04eb54888"
)
EXPECTED_WP3_FINGERPRINT = (
    "218cf2a640c81af2b2f9e75dd7fb446354ec06b608816fd12e21911b09829ab3"
)


EXPECTED_FAILURE_CODES = {
    "model_mapping.domain.v1": CompatibilityFailureCode.MAPPING_DOMAIN_MISMATCH.value,
    "ordering.same_context.v1": CompatibilityFailureCode.MODE_ORDER_CONTEXT_MISMATCH.value,
    "mapping_sector.representation.v1": CompatibilityFailureCode.SECTOR_REPRESENTATION_UNAVAILABLE.value,
    "mapping_state.encoder_match.v1": CompatibilityFailureCode.INITIAL_STATE_ENCODING_MISMATCH.value,
    "mapping_ansatz.generator_semantics.v1": CompatibilityFailureCode.ANSATZ_GENERATOR_MAPPING_MISMATCH.value,
    "mapping_task.all_operators_mapped.v1": CompatibilityFailureCode.TASK_OPERATOR_NOT_MAPPABLE.value,
    "model_task_reference.same_problem.v1": CompatibilityFailureCode.REFERENCE_SECTOR_MISMATCH.value,
    "composition.resource_envelope.v1": CompatibilityFailureCode.RESOURCE_ENVELOPE_EXCEEDED.value,
    "composition.acceptance_fingerprint.v1": CompatibilityFailureCode.ACCEPTANCE_EVIDENCE_STALE.value,
}


def build_wp4_evaluation_bundle() -> dict[str, Any]:
    registry = build_wp4_rule_registry()
    valid_context = build_valid_execution_context()
    analysis_context = build_mapping_analysis_context()
    invalid_jw_context = build_known_invalid_jw_context()
    negative_contexts = build_negative_rule_contexts()
    return {
        "registry": registry,
        "valid_execution_context": valid_context,
        "valid_execution_report": registry.evaluate(valid_context),
        "mapping_analysis_context": analysis_context,
        "mapping_analysis_report": registry.evaluate(analysis_context),
        "invalid_jw_context": invalid_jw_context,
        "invalid_jw_report": registry.evaluate(invalid_jw_context),
        "negative_contexts": negative_contexts,
        "negative_results": {
            rule_id: registry.evaluate_rule(context, rule_id)
            for rule_id, context in negative_contexts.items()
        },
    }


def public_compatibility_rule_catalog() -> dict[str, Any]:
    bundle = build_wp4_evaluation_bundle()
    registry = bundle["registry"]
    negative_results = bundle["negative_results"]
    payload = {
        "schema_version": COMPATIBILITY_RULE_CATALOG_SCHEMA_VERSION,
        "catalog_version": COMPATIBILITY_RULE_CATALOG_VERSION,
        "introduced_in_project_version": WP4_INTRODUCED_PROJECT_VERSION,
        "phase": "Phase A.3.2a",
        "work_package": "WP4 — Compatibility Rule Registry",
        "objective": (
            "Move scientific compatibility judgment into exact versioned, "
            "testable relation rules owned by the resolver rather than any "
            "single mapping, state, ansatz, task, or reference policy."
        ),
        "scientific_behavior_change": False,
        "live_rule_gate_enforced": False,
        "live_policy_migration_performed": False,
        "silent_fallback_allowed": False,
        "pairwise_and_global_phases_separate": True,
        "rule_registry": registry.public_catalog(),
        "rule_to_failure_code": dict(EXPECTED_FAILURE_CODES),
        "valid_execution_example": bundle["valid_execution_report"].to_dict(),
        "mapping_analysis_example": bundle["mapping_analysis_report"].to_dict(),
        "known_invalid_jw_composition": bundle["invalid_jw_report"].to_dict(),
        "negative_rule_fixtures": {
            rule_id: result.to_dict()
            for rule_id, result in negative_results.items()
        },
        "preserved_foundation_fingerprints": {
            "wp0_baseline": baseline_fingerprint(),
            "wp1_vocabulary": vocabulary_fingerprint(),
            "wp2_declarative_contract_catalog": policy_contract_catalog_fingerprint(),
            "wp3_implementation_binding_catalog": implementation_binding_catalog_fingerprint(),
        },
        "guardrails": [
            {
                "id": "wp4.relations_owned_by_resolver.v1",
                "statement": (
                    "Policies declare facts and abstract obligations; the resolver-owned rule registry judges relations."
                ),
            },
            {
                "id": "wp4.all_task_operators_mapped.v1",
                "statement": (
                    "Mapping the Hamiltonian alone is insufficient; every operator required by the task must be covered."
                ),
            },
            {
                "id": "wp4.pairwise_plus_global.v1",
                "statement": (
                    "Pairwise relation checks and complete-tuple invariants are evaluated in separate phases."
                ),
            },
            {
                "id": "wp4.known_invalid_jw_rejected.v1",
                "statement": (
                    "The legacy nonadjacent bare qubit exchange fails ANSATZ_GENERATOR_MAPPING_MISMATCH even though it preserves particle number."
                ),
            },
            {
                "id": "wp4.no_live_gate_yet.v1",
                "statement": (
                    "WP4 evaluates fixtures and publishes reports; WP5 will connect the rules to live realization resolution."
                ),
            },
        ],
    }
    payload["fingerprint"] = hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    return json.loads(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, allow_nan=False)
    )


def compatibility_rule_catalog_fingerprint(
    payload: dict[str, Any] | None = None,
) -> str:
    catalog = dict(payload or public_compatibility_rule_catalog())
    existing = catalog.pop("fingerprint", None)
    fingerprint = hashlib.sha256(
        json.dumps(
            catalog,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    if existing is not None and existing != fingerprint:
        raise ValueError("Compatibility-rule catalog fingerprint mismatch.")
    return fingerprint


def validate_compatibility_rule_registry(
    payload: dict[str, Any] | None = None,
) -> dict[str, bool]:
    catalog = payload or public_compatibility_rule_catalog()
    bundle = build_wp4_evaluation_bundle()
    registry = bundle["registry"]
    rules = registry.list_rules()
    valid_report = bundle["valid_execution_report"]
    analysis_report = bundle["mapping_analysis_report"]
    invalid_jw_report = bundle["invalid_jw_report"]
    negative_results = bundle["negative_results"]

    invalid_jw_failures = [
        item
        for item in invalid_jw_report.results
        if item.status in {CheckStatus.FAIL, CheckStatus.BLOCKED}
    ]
    analysis_by_id = {item.rule_id: item for item in analysis_report.results}
    negative_exact = all(
        result.failure_code == EXPECTED_FAILURE_CODES[rule_id]
        and result.status
        is (
            CheckStatus.REVIEW
            if rule_id == "composition.resource_envelope.v1"
            else CheckStatus.FAIL
        )
        for rule_id, result in negative_results.items()
    )
    no_callable_text = "callable_object" not in json.dumps(catalog, sort_keys=True)
    rule_ids = tuple(rule.rule_id for rule in rules)
    binding_ids = [rule.predicate_binding_id for rule in rules]

    return {
        "strict_json_round_trip": (
            json.loads(json.dumps(catalog, allow_nan=False, sort_keys=True))
            == catalog
        ),
        "catalog_fingerprint_valid": (
            compatibility_rule_catalog_fingerprint(catalog)
            == catalog["fingerprint"]
        ),
        "exact_nine_rules_registered": rule_ids == RULE_IDS and len(rules) == 9,
        "six_pairwise_three_global": (
            sum(rule.phase is CompatibilityRulePhase.PAIRWISE for rule in rules) == 6
            and sum(rule.phase is CompatibilityRulePhase.GLOBAL_INVARIANT for rule in rules) == 3
        ),
        "rule_ids_unique": len(rule_ids) == len(set(rule_ids)),
        "predicate_binding_ids_unique": len(binding_ids) == len(set(binding_ids)),
        "all_predicate_bindings_resolve_exactly": all(
            registry.predicate_bindings.resolve(
                registry._binding_requirement(rule)  # internal gate by design
            ).executable
            for rule in rules
        ),
        "rule_failure_code_map_exact": {
            rule.rule_id: rule.failure_code.value for rule in rules
        }
        == EXPECTED_FAILURE_CODES,
        "valid_execution_tuple_passes": (
            valid_report.overall_status is CheckStatus.PASS
            and valid_report.may_enter_runtime_if_enforced
        ),
        "analysis_only_state_rule_not_applicable": (
            analysis_by_id["mapping_state.encoder_match.v1"].status
            is CheckStatus.NOT_APPLICABLE
        ),
        "analysis_only_ansatz_rule_not_applicable": (
            analysis_by_id["mapping_ansatz.generator_semantics.v1"].status
            is CheckStatus.NOT_APPLICABLE
        ),
        "analysis_only_tuple_passes": analysis_report.overall_status is CheckStatus.PASS,
        "known_invalid_jw_fails_only_ansatz_rule": (
            len(invalid_jw_failures) == 1
            and invalid_jw_failures[0].rule_id
            == "mapping_ansatz.generator_semantics.v1"
            and invalid_jw_failures[0].failure_code
            == CompatibilityFailureCode.ANSATZ_GENERATOR_MAPPING_MISMATCH.value
        ),
        "all_negative_fixtures_emit_exact_codes": negative_exact,
        "resource_excess_is_review_not_fatal_fail": (
            negative_results["composition.resource_envelope.v1"].status
            is CheckStatus.REVIEW
            and not negative_results[
                "composition.resource_envelope.v1"
            ].blocks_runtime
        ),
        "public_catalog_contains_no_callable_objects": no_callable_text,
        "callable_payload_withheld": catalog["rule_registry"][
            "callable_payload_withheld"
        ]
        is True,
        "no_silent_fallback": catalog["silent_fallback_allowed"] is False,
        "pairwise_and_global_phases_separate": catalog[
            "pairwise_and_global_phases_separate"
        ]
        is True,
        "wp0_fingerprint_preserved": baseline_fingerprint()
        == EXPECTED_WP0_FINGERPRINT,
        "wp1_fingerprint_preserved": vocabulary_fingerprint()
        == EXPECTED_WP1_FINGERPRINT,
        "wp2_fingerprint_preserved": policy_contract_catalog_fingerprint()
        == EXPECTED_WP2_FINGERPRINT,
        "wp3_fingerprint_preserved": implementation_binding_catalog_fingerprint()
        == EXPECTED_WP3_FINGERPRINT,
        "live_rule_gate_not_enforced": catalog["live_rule_gate_enforced"] is False,
        "live_policy_migration_not_performed": catalog[
            "live_policy_migration_performed"
        ]
        is False,
        "scientific_behavior_change_false": catalog["scientific_behavior_change"]
        is False,
    }


__all__ = [
    "COMPATIBILITY_RULE_CATALOG_SCHEMA_VERSION",
    "COMPATIBILITY_RULE_CATALOG_VERSION",
    "WP4_INTRODUCED_PROJECT_VERSION",
    "EXPECTED_WP0_FINGERPRINT",
    "EXPECTED_WP1_FINGERPRINT",
    "EXPECTED_WP2_FINGERPRINT",
    "EXPECTED_WP3_FINGERPRINT",
    "EXPECTED_FAILURE_CODES",
    "build_wp4_evaluation_bundle",
    "public_compatibility_rule_catalog",
    "compatibility_rule_catalog_fingerprint",
    "validate_compatibility_rule_registry",
]

"""Public WP5 realization-resolver catalog and validation gate."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from qcol.acceptance import baseline_fingerprint
from qcol.compatibility import compatibility_rule_catalog_fingerprint
from qcol.implementation_bindings import implementation_binding_catalog_fingerprint
from qcol.mapping_policies import CheckStatus, vocabulary_fingerprint
from qcol.policy_contract_catalog import policy_contract_catalog_fingerprint

from .enums import RuntimeEntryStatus, RuntimePath
from .fixtures import build_wp5_candidates, build_wp5_fixture_registries
from .resolver import RealizationVariantResolver
from .runtime_gate import dispatch_resolved_variant


REALIZATION_RESOLVER_CATALOG_SCHEMA_VERSION = "qcol-realization-resolver-catalog/1.0"
REALIZATION_RESOLVER_CATALOG_VERSION = "1.0.0"
WP5_INTRODUCED_PROJECT_VERSION = "1.13.0"
EXPECTED_WP0_FINGERPRINT = "992f08c33a51de8c496cf7f894cbdbb4f8958eb2ddabe5b6021fc43e1d287e18"
EXPECTED_WP1_FINGERPRINT = "2fbcfc375bf56621fd0c379ed695233d1e572b4ad8e4f57842678ef50c192c8d"
EXPECTED_WP2_FINGERPRINT = "ccf69efaf5637aa40f810dd06a5df3d84d9e54c908ac41b4eeb78ee04eb54888"
EXPECTED_WP3_FINGERPRINT = "218cf2a640c81af2b2f9e75dd7fb446354ec06b608816fd12e21911b09829ab3"
EXPECTED_WP4_FINGERPRINT = "93913be83395de47ce03325b9aad448af77b5c54df1c05a5894d2c8d75c8027a"


def build_wp5_resolution_bundle() -> dict[str, Any]:
    contract_registry, binding_registry, rule_registry = build_wp5_fixture_registries()
    resolver = RealizationVariantResolver(
        contract_registry=contract_registry,
        binding_registry=binding_registry,
        rule_registry=rule_registry,
    )
    candidates = build_wp5_candidates()
    resolutions = {name: resolver.resolve(candidate) for name, candidate in candidates.items()}

    invocation_log: list[str] = []

    def analysis_runner(payload: dict[str, Any]) -> dict[str, Any]:
        invocation_log.append("analysis")
        return {
            "path": "analysis_controller",
            "task_id": payload["variant"]["task_id"],
            "measurement_called": False,
            "qasm_called": False,
        }

    def execution_runner(payload: dict[str, Any]) -> dict[str, Any]:
        invocation_log.append("execution")
        return {
            "path": "shared_execution_pipeline",
            "task_id": payload["variant"]["task_id"],
            "second_runtime_created": False,
        }

    dispatches = {
        "valid_execution": dispatch_resolved_variant(
            resolutions["valid_execution"],
            analysis_runner=analysis_runner,
            execution_runner=execution_runner,
        ),
        "mapping_analysis": dispatch_resolved_variant(
            resolutions["mapping_analysis"],
            analysis_runner=analysis_runner,
            execution_runner=execution_runner,
        ),
        "known_invalid_jw": dispatch_resolved_variant(
            resolutions["known_invalid_jw"],
            analysis_runner=analysis_runner,
            execution_runner=execution_runner,
        ),
        "missing_binding": dispatch_resolved_variant(
            resolutions["missing_binding"],
            analysis_runner=analysis_runner,
            execution_runner=execution_runner,
        ),
    }
    return {
        "resolver": resolver,
        "candidates": candidates,
        "resolutions": resolutions,
        "dispatches": dispatches,
        "invocation_log": tuple(invocation_log),
    }


def public_realization_resolver_catalog() -> dict[str, Any]:
    bundle = build_wp5_resolution_bundle()
    resolutions = bundle["resolutions"]
    dispatches = bundle["dispatches"]
    payload = {
        "schema_version": REALIZATION_RESOLVER_CATALOG_SCHEMA_VERSION,
        "catalog_version": REALIZATION_RESOLVER_CATALOG_VERSION,
        "introduced_in_project_version": WP5_INTRODUCED_PROJECT_VERSION,
        "phase": "Phase A.3.2a",
        "work_package": "WP5 — Resolver and Compatibility Reports",
        "objective": (
            "Resolve one exact mapping-realization variant, expose every binding and scientific judgment, and enforce an explicit runtime-entry decision rather than returning a hidden Boolean."
        ),
        "resolver_function": "resolve_realization_variant",
        "outputs": [
            "ResolvedRealizationVariant",
            "CompatibilityReport",
            "ResourceReport",
            "AcceptanceEvidenceStatus",
        ],
        "live_resolver_gate_enforced": True,
        "legacy_runtime_rewired": False,
        "live_policy_migration_performed": False,
        "scientific_status_promoted": False,
        "second_runtime_created": False,
        "silent_fallback_allowed": False,
        "resolution_examples": {
            name: resolution.to_public_dict()
            for name, resolution in resolutions.items()
        },
        "runtime_gate_examples": {
            name: report.to_dict() for name, report in dispatches.items()
        },
        "runtime_invocation_log": list(bundle["invocation_log"]),
        "preserved_foundation_fingerprints": {
            "wp0_baseline": baseline_fingerprint(),
            "wp1_vocabulary": vocabulary_fingerprint(),
            "wp2_declarative_contract_catalog": policy_contract_catalog_fingerprint(),
            "wp3_implementation_binding_catalog": implementation_binding_catalog_fingerprint(),
            "wp4_compatibility_rule_catalog": compatibility_rule_catalog_fingerprint(),
        },
        "guardrails": [
            {
                "id": "wp5.no_hidden_boolean.v1",
                "statement": "Every resolution exposes binding reports, rule checks, diagnostics, resource status, evidence freshness, and one explicit runtime-entry disposition.",
            },
            {
                "id": "wp5.fatal_fail_blocks_runtime.v1",
                "statement": "A fatal scientific FAIL invokes neither measurement, QASM, simulator, hardware, nor the shared execution pipeline.",
            },
            {
                "id": "wp5.analysis_stays_analysis.v1",
                "statement": "Analysis-only tasks may enter only their deterministic analysis controller and cannot enter circuit execution.",
            },
            {
                "id": "wp5.missing_binding_is_inspectable.v1",
                "statement": "A known contract with a missing exact binding resolves as recognized_not_executable rather than raising ImportError.",
            },
            {
                "id": "wp5.no_second_runtime.v1",
                "statement": "The gate routes accepted variants to existing handlers; it implements no optimizer, measurement, QASM, execution, reconstruction, or evidence service.",
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
    return json.loads(json.dumps(payload, sort_keys=True, allow_nan=False))


def realization_resolver_catalog_fingerprint(payload: dict[str, Any] | None = None) -> str:
    catalog = dict(payload or public_realization_resolver_catalog())
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
        raise ValueError("Realization-resolver catalog fingerprint mismatch.")
    return fingerprint


def validate_realization_resolver(payload: dict[str, Any] | None = None) -> dict[str, bool]:
    catalog = payload or public_realization_resolver_catalog()
    examples = catalog["resolution_examples"]
    valid = examples["valid_execution"]
    analysis = examples["mapping_analysis"]
    invalid = examples["known_invalid_jw"]
    resource_review = examples["resource_review"]
    stale = examples["stale_evidence"]
    missing = examples["missing_binding"]
    invalid_diagnostics = {
        item["diagnostic_id"]: item
        for item in invalid["compatibility_report"]["diagnostics"]
    }
    analysis_rules = {
        item["rule_id"]: item
        for item in analysis["compatibility_report"]["pairwise_results"]
    }
    invalid_dispatch = catalog["runtime_gate_examples"]["known_invalid_jw"]
    analysis_dispatch = catalog["runtime_gate_examples"]["mapping_analysis"]
    valid_dispatch = catalog["runtime_gate_examples"]["valid_execution"]
    missing_dispatch = catalog["runtime_gate_examples"]["missing_binding"]
    public_text = json.dumps(catalog, sort_keys=True)

    return {
        "strict_json_round_trip": json.loads(json.dumps(catalog, sort_keys=True, allow_nan=False)) == catalog,
        "catalog_fingerprint_valid": realization_resolver_catalog_fingerprint(catalog) == catalog["fingerprint"],
        "wp0_preserved": baseline_fingerprint() == EXPECTED_WP0_FINGERPRINT,
        "wp1_preserved": vocabulary_fingerprint() == EXPECTED_WP1_FINGERPRINT,
        "wp2_preserved": policy_contract_catalog_fingerprint() == EXPECTED_WP2_FINGERPRINT,
        "wp3_preserved": implementation_binding_catalog_fingerprint() == EXPECTED_WP3_FINGERPRINT,
        "wp4_preserved": compatibility_rule_catalog_fingerprint() == EXPECTED_WP4_FINGERPRINT,
        "one_explicit_variant_per_candidate": all(
            row["variant"]["candidate_id"] == row["candidate"]["candidate_id"]
            for row in examples.values()
        ),
        "valid_execution_allowed": valid["variant"]["runtime_entry"]["status"] == RuntimeEntryStatus.EXECUTION_ALLOWED.value,
        "analysis_only_stays_analysis_only": (
            analysis["variant"]["runtime_entry"]["status"] == RuntimeEntryStatus.ANALYSIS_ONLY_ALLOWED.value
            and analysis["variant"]["runtime_entry"]["path"] == RuntimePath.ANALYSIS_CONTROLLER.value
            and analysis_rules["mapping_state.encoder_match.v1"]["status"] == CheckStatus.NOT_APPLICABLE.value
            and analysis_rules["mapping_ansatz.generator_semantics.v1"]["status"] == CheckStatus.NOT_APPLICABLE.value
        ),
        "invalid_jw_blocked_before_runtime": (
            invalid["variant"]["runtime_entry"]["status"] == RuntimeEntryStatus.BLOCKED_SCIENTIFIC.value
            and invalid_dispatch["dispatched"] is False
            and "measurement_not_called" in invalid_dispatch["trace"]
            and "qasm_not_called" in invalid_dispatch["trace"]
        ),
        "invalid_jw_particle_number_and_semantics_separated": (
            invalid_diagnostics["particle_number_preservation"]["status"] == CheckStatus.PASS.value
            and invalid_diagnostics["fermionic_generator_semantics"]["status"] == CheckStatus.FAIL.value
            and invalid_diagnostics["fermionic_generator_semantics"]["failure_code"] == "ANSATZ_GENERATOR_MAPPING_MISMATCH"
        ),
        "resource_review_visible_not_hidden": (
            resource_review["resource_report"]["status"] == CheckStatus.REVIEW.value
            and resource_review["variant"]["runtime_entry"]["status"] == RuntimeEntryStatus.EXECUTION_ALLOWED_WITH_REVIEW.value
        ),
        "stale_evidence_blocks_with_stable_code": (
            stale["acceptance_evidence"]["freshness_status"] == "stale"
            and "ACCEPTANCE_EVIDENCE_STALE" in stale["compatibility_report"]["failure_codes"]
        ),
        "missing_binding_recognized_not_executable": (
            missing["variant"]["runtime_entry"]["status"] == RuntimeEntryStatus.RECOGNIZED_NOT_EXECUTABLE.value
            and missing_dispatch["dispatched"] is False
            and "BINDING_NOT_REGISTERED" in missing["variant"]["runtime_entry"]["blocking_codes"]
        ),
        "valid_and_analysis_dispatched_to_distinct_existing_paths": (
            valid_dispatch["requested_path"] == RuntimePath.SHARED_EXECUTION_PIPELINE.value
            and analysis_dispatch["requested_path"] == RuntimePath.ANALYSIS_CONTROLLER.value
            and catalog["runtime_invocation_log"] == ["execution", "analysis"]
        ),
        "no_callable_in_public_catalog": (
            "callable_object" not in public_text
            and '"runtime_callable_loaded": true' in public_text
            and catalog["second_runtime_created"] is False
        ),
        "live_policy_migration_not_performed": catalog["live_policy_migration_performed"] is False,
        "scientific_status_not_promoted": catalog["scientific_status_promoted"] is False,
    }


__all__ = [
    "REALIZATION_RESOLVER_CATALOG_SCHEMA_VERSION",
    "REALIZATION_RESOLVER_CATALOG_VERSION",
    "WP5_INTRODUCED_PROJECT_VERSION",
    "build_wp5_resolution_bundle",
    "public_realization_resolver_catalog",
    "realization_resolver_catalog_fingerprint",
    "validate_realization_resolver",
]

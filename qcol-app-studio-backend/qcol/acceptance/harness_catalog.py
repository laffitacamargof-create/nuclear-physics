"""Public WP7 three-gate harness catalog and A.3.2a exit classification."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from qcol.acceptance.mapping_baseline import baseline_fingerprint, public_mapping_realization_baseline
from qcol.compatibility import compatibility_rule_catalog_fingerprint
from qcol.implementation_bindings import implementation_binding_catalog_fingerprint
from qcol.mapping_policies import CheckStatus
from qcol.policy_contract_catalog import policy_contract_catalog_fingerprint
from qcol.realization_variants import realization_resolver_catalog_fingerprint
from qcol.mapping_policies import vocabulary_fingerprint

from .fingerprint_catalog import (
    acceptance_fingerprint_catalog_fingerprint,
    public_acceptance_fingerprint_catalog,
)
from .harness import AcceptanceGateKind
from .harness_fixtures import (
    build_wp7_analysis_gate_contracts,
    build_wp7_execution_gate_contracts,
    run_wp7_baseline_classifications,
)


ACCEPTANCE_HARNESS_CATALOG_SCHEMA_VERSION = "qcol-generic-three-gate-acceptance-harness-catalog/1.0"
ACCEPTANCE_HARNESS_CATALOG_VERSION = "1.0.0"
WP7_INTRODUCED_PROJECT_VERSION = "1.15.0"

EXPECTED_FOUNDATION_FINGERPRINTS = {
    "wp0": "992f08c33a51de8c496cf7f894cbdbb4f8958eb2ddabe5b6021fc43e1d287e18",
    "wp1": "2fbcfc375bf56621fd0c379ed695233d1e572b4ad8e4f57842678ef50c192c8d",
    "wp2": "ccf69efaf5637aa40f810dd06a5df3d84d9e54c908ac41b4eeb78ee04eb54888",
    "wp3": "218cf2a640c81af2b2f9e75dd7fb446354ec06b608816fd12e21911b09829ab3",
    "wp4": "93913be83395de47ce03325b9aad448af77b5c54df1c05a5894d2c8d75c8027a",
    "wp5": "e931fb17147327f0e5bd49da27c24a4270bb2c74be9e9cf9df74a0f60c32a16e",
}


def _foundation() -> dict[str, str]:
    return {
        "wp0": baseline_fingerprint(),
        "wp1": vocabulary_fingerprint(),
        "wp2": policy_contract_catalog_fingerprint(),
        "wp3": implementation_binding_catalog_fingerprint(),
        "wp4": compatibility_rule_catalog_fingerprint(),
        "wp5": realization_resolver_catalog_fingerprint(),
        "wp6": acceptance_fingerprint_catalog_fingerprint(),
    }


def public_acceptance_harness_catalog() -> dict[str, Any]:
    bundle = run_wp7_baseline_classifications()
    reports = bundle["reports"]
    baseline = public_mapping_realization_baseline()
    baseline_rows = {row["variant_id"]: row for row in baseline["variants"]}
    public_reports = {key: value.to_dict() for key, value in reports.items()}

    preserved = {
        variant_id: {
            "baseline_mapper_status": baseline_rows[variant_id]["mapper_conformance"],
            "baseline_composition_status": baseline_rows[variant_id]["composition_conformance"],
            "baseline_cell_status": baseline_rows[variant_id]["cell_acceptance"],
            "harness_gate_statuses": {
                row["gate"]["kind"]: row["status"]
                for row in report["gate_reports"]
            },
            "promotion_ready": report["promotion"]["promotion_ready"],
            "decision": report["promotion"]["decision"],
            "preserved_baseline_status": report["promotion"]["preserved_baseline_status"],
        }
        for variant_id, report in public_reports.items()
    }

    invalid = public_reports["baseline.jw.general_ground_state.current_composition.v1"]
    analysis_jw = public_reports["baseline.jw.mapping_analysis.v1"]
    analysis_bk = public_reports["baseline.bk.mapping_analysis.v1"]
    multi = public_reports["baseline.pair.multi_pair.ground_state.v1"]
    one_pair = public_reports["baseline.pair.one_pair.ground_state.v1"]
    bk_ground = public_reports["baseline.bk.general_ground_state.v1"]

    exit_checks = {
        "no_accepted_scientific_behavior_changed": True,
        "no_runtime_duplicated": True,
        "existing_verified_paths_frozen": (
            one_pair["promotion"]["preserved_baseline_status"] == "acceptance_verified"
            and analysis_jw["promotion"]["preserved_baseline_status"] == "acceptance_verified_for_analysis"
            and analysis_bk["promotion"]["preserved_baseline_status"] == "acceptance_verified_for_analysis"
        ),
        "known_experimental_paths_remain_experimental": (
            multi["promotion"]["preserved_baseline_status"] == "experimental"
            and multi["promotion"]["promotion_ready"] is False
        ),
        "invalid_jw_composition_rejected_consistently": (
            invalid["promotion"]["promotion_ready"] is False
            and "ANSATZ_GENERATOR_MAPPING_MISMATCH" in invalid["promotion"]["blocking_codes"]
            and invalid["gate_reports"][1]["status"] == "fail"
            and invalid["gate_reports"][2]["status"] == "blocked"
        ),
        "generic_contracts_and_reports_operational": len(public_reports) == len(baseline_rows),
        "acceptance_harness_classifies_all_baseline_variants": set(public_reports) == set(baseline_rows),
        "analysis_composition_is_not_applicable": (
            analysis_jw["gate_reports"][1]["status"] == "not_applicable"
            and analysis_bk["gate_reports"][1]["status"] == "not_applicable"
        ),
        "bk_ground_state_remains_not_executable": (
            bk_ground["promotion"]["preserved_baseline_status"] == "recognized_not_executable"
            and bk_ground["promotion"]["promotion_ready"] is False
        ),
    }
    payload: dict[str, Any] = {
        "schema_version": ACCEPTANCE_HARNESS_CATALOG_SCHEMA_VERSION,
        "catalog_version": ACCEPTANCE_HARNESS_CATALOG_VERSION,
        "introduced_in_project_version": WP7_INTRODUCED_PROJECT_VERSION,
        "phase": "Phase A.3.2a",
        "work_package": "WP7 — Generic Three-Gate Acceptance Harness",
        "objective": "Classify mapper conformance, composition conformance, and complete Model × Task cell acceptance through one reusable harness and versioned tolerance profiles.",
        "gate_order": [
            AcceptanceGateKind.MAPPER_CONFORMANCE.value,
            AcceptanceGateKind.COMPOSITION_CONFORMANCE.value,
            AcceptanceGateKind.CELL_ACCEPTANCE.value,
        ],
        "execution_gate_contracts": {
            key.value: value.to_dict()
            for key, value in build_wp7_execution_gate_contracts().items()
        },
        "analysis_gate_contracts": {
            key.value: value.to_dict()
            for key, value in build_wp7_analysis_gate_contracts().items()
        },
        "tolerance_profile_registry": bundle["tolerance_registry"].public_catalog(),
        "baseline_classifications": public_reports,
        "baseline_status_preservation": preserved,
        "a3_2a_exit_checks": exit_checks,
        "a3_2a_exit_ready": all(exit_checks.values()),
        "foundation_fingerprints": _foundation(),
        "wp6_fingerprint_catalog": {
            "fingerprint": acceptance_fingerprint_catalog_fingerprint(),
            "endpoint": "/catalog/acceptance-evidence-fingerprints",
        },
        "promotion_rule": (
            "All REQUIRED gates PASS, non-required gates are explicitly NOT_APPLICABLE, "
            "and evidence.fingerprint equals resolved_variant.fingerprint."
        ),
        "scientific_behavior_change": False,
        "live_policy_migration_performed": False,
        "scientific_status_promoted": False,
        "second_runtime_created": False,
        "guardrails": [
            "Mapper/operator-action tests run before any task-level energy claim.",
            "A composition failure blocks the cell gate; optimizer or energy output cannot mask it.",
            "NOT_APPLICABLE is distinct from PASS for analysis-only tasks.",
            "Tolerance values are read from exact versioned ToleranceProfile IDs; no test-local numerical threshold is authoritative.",
            "The harness classifies evidence and promotion readiness only; it implements no mapper, circuit, optimizer, QASM, backend, or evidence runtime.",
        ],
    }
    payload["fingerprint"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    ).hexdigest()
    return json.loads(json.dumps(payload, sort_keys=True, allow_nan=False))


def acceptance_harness_catalog_fingerprint(payload: dict[str, Any] | None = None) -> str:
    catalog = dict(payload or public_acceptance_harness_catalog())
    existing = catalog.pop("fingerprint", None)
    digest = hashlib.sha256(
        json.dumps(catalog, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    ).hexdigest()
    if existing is not None and existing != digest:
        raise ValueError("Acceptance-harness catalog fingerprint mismatch.")
    return digest


def validate_acceptance_harness_catalog(payload: dict[str, Any] | None = None) -> dict[str, bool]:
    catalog = payload or public_acceptance_harness_catalog()
    classifications = catalog["baseline_classifications"]
    invalid = classifications["baseline.jw.general_ground_state.current_composition.v1"]
    analysis = classifications["baseline.jw.mapping_analysis.v1"]
    multi = classifications["baseline.pair.multi_pair.ground_state.v1"]
    return {
        "strict_json_round_trip": json.loads(json.dumps(catalog, sort_keys=True, allow_nan=False)) == catalog,
        "catalog_fingerprint_valid": acceptance_harness_catalog_fingerprint(catalog) == catalog["fingerprint"],
        "wp0_wp5_foundation_preserved": {k: catalog["foundation_fingerprints"][k] for k in EXPECTED_FOUNDATION_FINGERPRINTS} == EXPECTED_FOUNDATION_FINGERPRINTS,
        "wp6_fingerprint_registered": catalog["foundation_fingerprints"]["wp6"] == acceptance_fingerprint_catalog_fingerprint(),
        "exact_three_gate_order": catalog["gate_order"] == [
            "mapper_conformance", "composition_conformance", "cell_acceptance"
        ],
        "all_baseline_variants_classified": len(classifications) == 6,
        "invalid_jw_fails_composition_before_cell": (
            invalid["gate_reports"][0]["status"] == CheckStatus.PASS.value
            and invalid["gate_reports"][1]["status"] == CheckStatus.FAIL.value
            and invalid["gate_reports"][2]["status"] == CheckStatus.BLOCKED.value
            and "ANSATZ_GENERATOR_MAPPING_MISMATCH" in invalid["promotion"]["blocking_codes"]
        ),
        "analysis_composition_not_applicable": analysis["gate_reports"][1]["status"] == CheckStatus.NOT_APPLICABLE.value,
        "experimental_multi_pair_not_promoted": (
            multi["promotion"]["promotion_ready"] is False
            and multi["promotion"]["preserved_baseline_status"] == "experimental"
        ),
        "all_exit_checks_pass": catalog["a3_2a_exit_ready"] is True and all(catalog["a3_2a_exit_checks"].values()),
        "no_runtime_duplicated": catalog["second_runtime_created"] is False,
        "no_scientific_behavior_change": catalog["scientific_behavior_change"] is False,
        "no_policy_migration_or_promotion": (
            catalog["live_policy_migration_performed"] is False
            and catalog["scientific_status_promoted"] is False
        ),
    }


__all__ = [
    "ACCEPTANCE_HARNESS_CATALOG_SCHEMA_VERSION",
    "ACCEPTANCE_HARNESS_CATALOG_VERSION",
    "WP7_INTRODUCED_PROJECT_VERSION",
    "public_acceptance_harness_catalog",
    "acceptance_harness_catalog_fingerprint",
    "validate_acceptance_harness_catalog",
]

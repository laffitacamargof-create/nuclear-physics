"""Public WP6 acceptance-evidence fingerprint catalog and validation fixtures."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from qcol.acceptance.mapping_baseline import baseline_fingerprint
from qcol.compatibility import compatibility_rule_catalog_fingerprint
from qcol.implementation_bindings import implementation_binding_catalog_fingerprint
from qcol.mapping_policies import vocabulary_fingerprint
from qcol.policy_contract_catalog import policy_contract_catalog_fingerprint
from qcol.realization_variants import realization_resolver_catalog_fingerprint

from .fingerprint import ACCEPTANCE_EVIDENCE_STALE, compare_acceptance_fingerprints
from .fingerprint_fixtures import (
    build_wp6_acceptance_record,
    build_wp6_mutated_fingerprints,
    build_wp6_valid_fingerprint,
)


ACCEPTANCE_FINGERPRINT_CATALOG_SCHEMA_VERSION = "qcol-acceptance-evidence-fingerprint-catalog/1.0"
ACCEPTANCE_FINGERPRINT_CATALOG_VERSION = "1.0.0"
WP6_INTRODUCED_PROJECT_VERSION = "1.14.0"

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
    }


def public_acceptance_fingerprint_catalog() -> dict[str, Any]:
    current = build_wp6_valid_fingerprint()
    record = build_wp6_acceptance_record()
    exact_report = compare_acceptance_fingerprints(current, record.evidence_fingerprint)
    mutations = build_wp6_mutated_fingerprints()
    mismatch_reports = {
        name: compare_acceptance_fingerprints(current, mutated).to_dict()
        for name, mutated in mutations.items()
    }
    payload: dict[str, Any] = {
        "schema_version": ACCEPTANCE_FINGERPRINT_CATALOG_SCHEMA_VERSION,
        "catalog_version": ACCEPTANCE_FINGERPRINT_CATALOG_VERSION,
        "introduced_in_project_version": WP6_INTRODUCED_PROJECT_VERSION,
        "phase": "Phase A.3.2a",
        "work_package": "WP6 — Acceptance Evidence Fingerprint",
        "objective": "Tie every acceptance claim to one exact resolved composition, dependency set, and declared problem scale.",
        "fingerprinted_dimensions": [
            "ModelContract ID/version",
            "TaskContract ID/version",
            "MappingPolicy ID/version/convention",
            "ModeOrdering ID",
            "EncodingContext",
            "SectorEncodingProfile values",
            "StatePreparationPolicy ID/version",
            "AnsatzPolicy ID/version",
            "MeasurementPolicy ID/version",
            "ReferencePolicy ID/version",
            "VerificationPolicy ID/version",
            "ToleranceProfile ID/version",
            "Implementation binding provider/version/convention/source revision",
            "Dependency versions",
            "Declared problem scale",
        ],
        "current_fingerprint": current.to_dict(),
        "acceptance_record": record.to_dict(),
        "exact_match_report": exact_report.to_dict(),
        "staleness_scenarios": mismatch_reports,
        "four_mode_cannot_promote_twenty_mode": mismatch_reports["declared_scale_20_modes"],
        "stable_failure_code": ACCEPTANCE_EVIDENCE_STALE,
        "foundation_fingerprints": _foundation(),
        "live_policy_migration_performed": False,
        "scientific_behavior_change": False,
        "second_runtime_created": False,
        "guardrails": [
            "Fingerprint equality is exact; no field-level substitution or scale extrapolation is allowed.",
            "Any convention, ordering, sector, state, ansatz, measurement, reference, verification, tolerance, dependency, or scale change makes the record stale.",
            "A stale record cannot promote a realization and cannot authorize runtime entry when current acceptance evidence is required.",
            "The fingerprint stores public identities and hashes only; no Python callable or scientific runtime object is serialized.",
        ],
    }
    payload["fingerprint"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    ).hexdigest()
    return json.loads(json.dumps(payload, sort_keys=True, allow_nan=False))


def acceptance_fingerprint_catalog_fingerprint(payload: dict[str, Any] | None = None) -> str:
    catalog = dict(payload or public_acceptance_fingerprint_catalog())
    existing = catalog.pop("fingerprint", None)
    digest = hashlib.sha256(
        json.dumps(catalog, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    ).hexdigest()
    if existing is not None and existing != digest:
        raise ValueError("Acceptance-fingerprint catalog fingerprint mismatch.")
    return digest


def validate_acceptance_fingerprint_catalog(payload: dict[str, Any] | None = None) -> dict[str, bool]:
    catalog = payload or public_acceptance_fingerprint_catalog()
    stale = catalog["staleness_scenarios"]
    required_scenarios = {
        "model_contract_changed",
        "task_contract_changed",
        "mapping_convention_changed",
        "ordering_changed",
        "encoding_context_changed",
        "sector_changed",
        "state_preparation_changed",
        "ansatz_changed",
        "measurement_changed",
        "reference_changed",
        "verification_changed",
        "tolerance_changed",
        "dependency_changed",
        "declared_scale_20_modes",
    }
    return {
        "strict_json_round_trip": json.loads(json.dumps(catalog, sort_keys=True, allow_nan=False)) == catalog,
        "catalog_fingerprint_valid": acceptance_fingerprint_catalog_fingerprint(catalog) == catalog["fingerprint"],
        "foundation_fingerprints_preserved": catalog["foundation_fingerprints"] == EXPECTED_FOUNDATION_FINGERPRINTS,
        "exact_record_is_current": (
            catalog["exact_match_report"]["exact_match"] is True
            and catalog["exact_match_report"]["decision"]["freshness_status"] == "current"
            and catalog["exact_match_report"]["decision"]["promotion_allowed"] is True
        ),
        "all_required_mutations_covered": required_scenarios == set(stale),
        "all_mutations_are_stale": all(
            report["decision"]["freshness_status"] == "stale"
            and report["decision"]["failure_code"] == ACCEPTANCE_EVIDENCE_STALE
            and report["decision"]["promotion_allowed"] is False
            for report in stale.values()
        ),
        "four_mode_cannot_promote_twenty_mode": (
            catalog["four_mode_cannot_promote_twenty_mode"]["exact_match"] is False
            and "declared_scale" in catalog["four_mode_cannot_promote_twenty_mode"]["changed_categories"]
        ),
        "no_scientific_behavior_change": catalog["scientific_behavior_change"] is False,
        "no_policy_migration": catalog["live_policy_migration_performed"] is False,
        "no_second_runtime": catalog["second_runtime_created"] is False,
        "no_callable_payload": "callable_object" not in json.dumps(catalog, sort_keys=True),
    }


__all__ = [
    "ACCEPTANCE_FINGERPRINT_CATALOG_SCHEMA_VERSION",
    "ACCEPTANCE_FINGERPRINT_CATALOG_VERSION",
    "WP6_INTRODUCED_PROJECT_VERSION",
    "EXPECTED_FOUNDATION_FINGERPRINTS",
    "public_acceptance_fingerprint_catalog",
    "acceptance_fingerprint_catalog_fingerprint",
    "validate_acceptance_fingerprint_catalog",
]

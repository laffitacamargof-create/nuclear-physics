"""WP0 mapping-realization baseline declaration and validation.

The baseline is deliberately dependency-light.  It records the current truth
before policy refactoring without importing Cirq, OpenFermion, or PyQASM.
Scientific regression checks are implemented separately in
``baseline_evidence`` and are run only in the pinned acceptance environment.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
from importlib.resources import files
import json
from typing import Any, Dict, Iterable, Mapping

from ..compatibility import CompatibilityFailureCode

BASELINE_SCHEMA_VERSION = "qcol-mapping-realization-baseline/1.0"
BASELINE_RESOURCE_NAME = "mapping_realization_baseline.v1.json"

_MAPPER_STATUSES = {
    "verified", "verified_for_transform", "unresolved", "failed", "not_applicable"
}
_COMPOSITION_STATUSES = {
    "verified", "experimental", "failed", "unresolved", "not_applicable"
}
_CELL_STATUSES = {
    "acceptance_verified",
    "acceptance_verified_for_analysis",
    "experimental",
    "not_verified",
    "recognized_not_executable",
}


def _resource_text() -> str:
    resource = files("qcol.acceptance").joinpath("baselines", BASELINE_RESOURCE_NAME)
    return resource.read_text(encoding="utf-8")


def load_mapping_realization_baseline() -> Dict[str, Any]:
    data = json.loads(_resource_text())
    validate_mapping_realization_baseline(data, raise_on_error=True)
    return data


def public_mapping_realization_baseline() -> Dict[str, Any]:
    """Return a mutable JSON-safe copy for API, UI, and Evidence boundaries."""
    return deepcopy(load_mapping_realization_baseline())


def baseline_fingerprint(data: Mapping[str, Any] | None = None) -> str:
    payload = data if data is not None else load_mapping_realization_baseline()
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _index(data: Mapping[str, Any]) -> Dict[str, Mapping[str, Any]]:
    return {str(item["variant_id"]): item for item in data.get("variants", [])}


def get_baseline_variant(variant_id: str) -> Dict[str, Any]:
    data = load_mapping_realization_baseline()
    try:
        return deepcopy(_index(data)[str(variant_id)])
    except KeyError as exc:
        raise KeyError(f"Unknown mapping-realization baseline variant: {variant_id}") from exc


def find_baseline_variants(
    *,
    model_id: str | None = None,
    task_id: str | None = None,
    mapping_id: str | None = None,
) -> list[Dict[str, Any]]:
    items: Iterable[Mapping[str, Any]] = load_mapping_realization_baseline()["variants"]
    result = []
    for item in items:
        if model_id is not None and item.get("model_id") != model_id:
            continue
        if task_id is not None and item.get("task_id") != task_id:
            continue
        if mapping_id is not None and item.get("mapping_id") != mapping_id:
            continue
        result.append(deepcopy(dict(item)))
    return result


def validate_mapping_realization_baseline(
    data: Mapping[str, Any] | None = None,
    *,
    raise_on_error: bool = False,
) -> Dict[str, bool]:
    baseline = dict(data or json.loads(_resource_text()))
    variants = list(baseline.get("variants", []))
    variant_ids = [str(item.get("variant_id", "")) for item in variants]

    checks = {
        "schema_version": baseline.get("schema_version") == BASELINE_SCHEMA_VERSION,
        "scientific_behavior_unchanged": baseline.get("scientific_behavior_change") is False,
        "six_frozen_variants": len(variants) == 6,
        "variant_ids_unique": len(variant_ids) == len(set(variant_ids)) and all(variant_ids),
        "mapper_statuses_valid": all(item.get("mapper_conformance") in _MAPPER_STATUSES for item in variants),
        "composition_statuses_valid": all(item.get("composition_conformance") in _COMPOSITION_STATUSES for item in variants),
        "cell_statuses_valid": all(item.get("cell_acceptance") in _CELL_STATUSES for item in variants),
        "one_pair_anchor_verified": False,
        "multi_pair_stays_experimental": False,
        "jw_analysis_stays_verified": False,
        "bk_analysis_stays_verified": False,
        "jw_ground_composition_frozen_failed": False,
        "bk_ground_stays_not_executable": False,
        "no_status_promoted": "No scientific status is promoted by this baseline freeze." in baseline.get("frozen_invariants", []),
    }

    indexed = _index(baseline)
    one_pair = indexed.get("baseline.pair.one_pair.ground_state.v1", {})
    multi_pair = indexed.get("baseline.pair.multi_pair.ground_state.v1", {})
    jw_analysis = indexed.get("baseline.jw.mapping_analysis.v1", {})
    bk_analysis = indexed.get("baseline.bk.mapping_analysis.v1", {})
    jw_ground = indexed.get("baseline.jw.general_ground_state.current_composition.v1", {})
    bk_ground = indexed.get("baseline.bk.general_ground_state.v1", {})

    checks["one_pair_anchor_verified"] = (
        one_pair.get("mapper_conformance") == "verified"
        and one_pair.get("composition_conformance") == "verified"
        and one_pair.get("cell_acceptance") == "acceptance_verified"
    )
    checks["multi_pair_stays_experimental"] = (
        multi_pair.get("composition_conformance") == "experimental"
        and multi_pair.get("cell_acceptance") == "experimental"
    )
    checks["jw_analysis_stays_verified"] = (
        jw_analysis.get("mapper_conformance") == "verified"
        and jw_analysis.get("composition_conformance") == "not_applicable"
        and jw_analysis.get("cell_acceptance") == "acceptance_verified_for_analysis"
    )
    checks["bk_analysis_stays_verified"] = (
        bk_analysis.get("mapper_conformance") == "verified"
        and bk_analysis.get("composition_conformance") == "not_applicable"
        and bk_analysis.get("cell_acceptance") == "acceptance_verified_for_analysis"
    )
    checks["jw_ground_composition_frozen_failed"] = (
        jw_ground.get("mapper_conformance") == "verified"
        and jw_ground.get("composition_conformance") == "failed"
        and jw_ground.get("cell_acceptance") == "not_verified"
        and jw_ground.get("failure_code")
        == CompatibilityFailureCode.ANSATZ_GENERATOR_MAPPING_MISMATCH.value
    )
    checks["bk_ground_stays_not_executable"] = (
        bk_ground.get("mapper_conformance") == "verified_for_transform"
        and bk_ground.get("composition_conformance") == "unresolved"
        and bk_ground.get("cell_acceptance") == "recognized_not_executable"
        and bk_ground.get("current_runtime_runnable") is False
    )

    if raise_on_error and not all(checks.values()):
        failed = [name for name, passed in checks.items() if not passed]
        raise AssertionError("Mapping-realization baseline validation failed: " + ", ".join(failed))
    return checks


def assert_wp0_baseline() -> Dict[str, bool]:
    checks = validate_mapping_realization_baseline(raise_on_error=True)
    return checks

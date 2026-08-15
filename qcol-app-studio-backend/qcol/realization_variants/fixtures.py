"""Deterministic WP5 candidates and registries.

These fixtures prove the resolver/report/runtime-gate architecture without
migrating live Pair/JW/BK policies.  Production policy migration remains WP8–10.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any

from qcol.compatibility import (
    RuleEvaluationContext,
    build_known_invalid_jw_context,
    build_mapping_analysis_context,
    build_negative_rule_contexts,
    build_valid_execution_context,
    build_wp4_rule_registry,
)
from qcol.implementation_bindings import build_wp3_example_registries
from qcol.mapping_policies import PolicyStatus
from qcol.policy_contract_catalog import build_wp2_contract_examples

from .contracts import RealizationCandidate
from .enums import RealizationTaskMode


FUTURE_MAPPING_CONTRACT_ID = "wp5.fixture.known_future_mapping.v1"
ABSENT_MAPPING_BINDING_ID = "wp5.binding.absent_mapper.v1"


def build_wp5_fixture_registries():
    """Return WP2 contract, WP3 binding, and WP4 rule registries for WP5."""
    contract_registry, binding_registry = build_wp3_example_registries()
    examples = build_wp2_contract_examples()
    mapping = examples["mapping_policy"]
    future_mapping = replace(
        mapping,
        policy_id=FUTURE_MAPPING_CONTRACT_ID,
        display_name="WP5 recognized future mapping without executable mapper",
        implementation_binding_id=ABSENT_MAPPING_BINDING_ID,
        support_status=PolicyStatus.RECOGNIZED_NOT_EXECUTABLE,
        limitations=(
            "WP5 fixture proving known-contract/missing-binding resolution.",
        ),
        provenance={
            "phase": "Phase A.3.2a",
            "work_package": "WP5",
            "fixture_only": True,
            "scientific_behavior_change": False,
            "live_policy_migration_performed": False,
        },
    )
    contract_registry.register(future_mapping)
    return contract_registry, binding_registry, build_wp4_rule_registry()


def _base_contract_ids() -> dict[str, str]:
    examples = build_wp2_contract_examples()
    return {
        "mapping": examples["mapping_policy"].policy_id,
        "ordering": examples["mode_ordering"].ordering_id,
        "encoding_context": examples["encoding_context"].context_id,
        "sector": examples["direct_sector_profile"].profile_id,
        "state_preparation": examples["state_preparation_policy"].policy_id,
        "ansatz": examples["ansatz_policy"].policy_id,
        "measurement": examples["measurement_policy"].policy_id,
        "reference": examples["reference_policy"].policy_id,
        "verification": examples["verification_policy"].policy_id,
        "tolerance": examples["tolerance_profile"].profile_id,
    }


def _component_ids(context: RuleEvaluationContext) -> dict[str, str]:
    payload = context.to_dict()
    return {
        "model": str(payload["model"].get("model_id", "unknown-model")),
        "task": str(payload["task"].get("task_id", "unknown-task")),
        "mapping": str(payload["mapping"].get("policy_id", "unknown-mapping")),
        "ordering": str(payload["ordering"].get("ordering_id", "unknown-ordering")),
        "sector": str(payload["sector"].get("sector_fingerprint", "unknown-sector")),
        "state_preparation": str(
            payload["state_preparation"].get("policy_id", "not_applicable")
        ),
        "ansatz": str(payload["ansatz"].get("policy_id", "not_applicable")),
        "measurement": str(
            payload["measurement"].get("policy_id", "not_applicable")
        ),
        "reference": str(payload["reference"].get("policy_id", "unknown-reference")),
    }


def _candidate(
    candidate_id: str,
    label: str,
    task_mode: RealizationTaskMode,
    context: RuleEvaluationContext,
    contract_ids: tuple[str, ...],
) -> RealizationCandidate:
    context_payload = context.to_dict()
    declared_scale = context_payload["model"].get("declared_scale", {})
    return RealizationCandidate(
        candidate_id=candidate_id,
        candidate_version="1.0.0",
        label=label,
        task_mode=task_mode,
        contract_ids=contract_ids,
        rule_context=context,
        declared_scale=declared_scale,
        source_metadata={
            "phase": "Phase A.3.2a",
            "work_package": "WP5",
            "fixture_only": True,
            "component_ids": _component_ids(context),
            "live_policy_migration_performed": False,
        },
    )


def _execution_contract_ids(*, mapping_id: str | None = None) -> tuple[str, ...]:
    ids = _base_contract_ids()
    if mapping_id is not None:
        ids["mapping"] = mapping_id
    return tuple(ids.values())


def _analysis_contract_ids() -> tuple[str, ...]:
    ids = _base_contract_ids()
    return (
        ids["mapping"],
        ids["ordering"],
        ids["encoding_context"],
        ids["sector"],
        ids["reference"],
        ids["verification"],
        ids["tolerance"],
    )


def _context_from_payload(payload: dict[str, Any]) -> RuleEvaluationContext:
    return RuleEvaluationContext(**payload)


def build_future_mapping_context() -> RuleEvaluationContext:
    payload = build_valid_execution_context().to_dict()
    payload["context_id"] = "wp5.known-contract-missing-binding.v1"
    payload["mapping"]["policy_id"] = FUTURE_MAPPING_CONTRACT_ID
    payload["state_preparation"]["mapping_policy_id"] = FUTURE_MAPPING_CONTRACT_ID
    payload["ansatz"]["mapping_policy_id"] = FUTURE_MAPPING_CONTRACT_ID
    payload["complete_tuple"]["mapping_policy_id"] = FUTURE_MAPPING_CONTRACT_ID
    return _context_from_payload(payload)


def build_wp5_candidates() -> dict[str, RealizationCandidate]:
    negative = build_negative_rule_contexts()
    return {
        "valid_execution": _candidate(
            "wp5.valid-execution.v1",
            "Valid executable-circuit realization fixture",
            RealizationTaskMode.EXECUTABLE_CIRCUIT,
            build_valid_execution_context(),
            _execution_contract_ids(),
        ),
        "mapping_analysis": _candidate(
            "wp5.mapping-analysis.v1",
            "Analysis-only mapping comparison fixture",
            RealizationTaskMode.ANALYSIS_ONLY,
            build_mapping_analysis_context(),
            _analysis_contract_ids(),
        ),
        "known_invalid_jw": _candidate(
            "wp5.known-invalid-jw.v1",
            "Known invalid JW bare-exchange composition",
            RealizationTaskMode.EXECUTABLE_CIRCUIT,
            build_known_invalid_jw_context(),
            _execution_contract_ids(),
        ),
        "resource_review": _candidate(
            "wp5.resource-review.v1",
            "Scientifically compatible tuple outside declared resource envelope",
            RealizationTaskMode.EXECUTABLE_CIRCUIT,
            negative["composition.resource_envelope.v1"],
            _execution_contract_ids(),
        ),
        "stale_evidence": _candidate(
            "wp5.stale-evidence.v1",
            "Tuple with stale acceptance evidence",
            RealizationTaskMode.EXECUTABLE_CIRCUIT,
            negative["composition.acceptance_fingerprint.v1"],
            _execution_contract_ids(),
        ),
        "missing_binding": _candidate(
            "wp5.missing-binding.v1",
            "Known policy whose exact implementation binding is absent",
            RealizationTaskMode.EXECUTABLE_CIRCUIT,
            build_future_mapping_context(),
            _execution_contract_ids(mapping_id=FUTURE_MAPPING_CONTRACT_ID),
        ),
    }


__all__ = [
    "FUTURE_MAPPING_CONTRACT_ID",
    "ABSENT_MAPPING_BINDING_ID",
    "build_wp5_fixture_registries",
    "build_future_mapping_context",
    "build_wp5_candidates",
]

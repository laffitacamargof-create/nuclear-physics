"""WP5 mapping-realization resolver and explicit report construction.

The resolver joins WP2 contracts, WP3 exact implementation bindings, and WP4
scientific relation rules.  It returns one inspectable realization variant and
never enters measurement/QASM/backend services itself.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from qcol.compatibility import CompatibilityRuleRegistry
from qcol.implementation_bindings import (
    DeclarativePolicyContractRegistry,
    ImplementationBindingRegistry,
    ResolvedBindingPlan,
)
from qcol.implementation_bindings.contract_index import resolve_contracts
from qcol.mapping_policies import (
    CheckStatus,
    DecisionStatus,
    EvidenceFreshnessStatus,
    PolicyStatus,
    Severity,
)

from .contracts import (
    AcceptanceEvidenceStatus,
    CompatibilityDiagnostic,
    CompatibilityReport,
    RealizationCandidate,
    RealizationResolution,
    ResolvedRealizationVariant,
    ResourceReport,
    RuntimeEntryDecision,
)
from .enums import (
    RealizationTaskMode,
    ResolutionStatus,
    RuntimeEntryStatus,
    RuntimePath,
)


class RealizationResolverError(ValueError):
    """Raised for invalid resolver construction, never for a scientific rejection."""


_DIAGNOSTIC_LABELS = {
    "model_mapping.domain.v1": ("model_domain", "Model domain"),
    "ordering.same_context.v1": ("mode_ordering", "Mode ordering"),
    "mapping_state.encoder_match.v1": (
        "initial_state_encoding",
        "Initial-state encoding",
    ),
    "mapping_sector.representation.v1": (
        "sector_representation",
        "Sector representation",
    ),
    "mapping_ansatz.generator_semantics.v1": (
        "fermionic_generator_semantics",
        "Fermionic-generator semantics",
    ),
    "mapping_task.all_operators_mapped.v1": (
        "task_operators_mapped",
        "Task operators mapped",
    ),
    "model_task_reference.same_problem.v1": (
        "reference_independence",
        "Reference independence",
    ),
    "composition.resource_envelope.v1": (
        "resource_envelope",
        "Resource envelope",
    ),
    "composition.acceptance_fingerprint.v1": (
        "acceptance_evidence",
        "Acceptance evidence",
    ),
}


def _deterministic_id(prefix: str, payload: Any, width: int = 16) -> str:
    digest = hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()[:width]
    return f"{prefix}-{digest}"


def _status_decision(status: CheckStatus) -> DecisionStatus:
    if status in {CheckStatus.FAIL, CheckStatus.BLOCKED}:
        return DecisionStatus.REJECT
    if status is CheckStatus.REVIEW:
        return DecisionStatus.REVIEW
    if status is CheckStatus.NOT_RUN:
        return DecisionStatus.DEFER
    return DecisionStatus.ACCEPT


def _freshness(value: Any) -> EvidenceFreshnessStatus:
    try:
        return EvidenceFreshnessStatus(str(value))
    except ValueError:
        return EvidenceFreshnessStatus.UNKNOWN


def _binding_codes(plan: ResolvedBindingPlan) -> tuple[str, ...]:
    return tuple(
        item.report.code.value
        for item in plan.required_resolutions
        if not item.executable
    )


def _rule_diagnostics(candidate: RealizationCandidate, rule_report) -> tuple[CompatibilityDiagnostic, ...]:
    context = candidate.rule_context
    by_id = {item.rule_id: item for item in rule_report.results}
    diagnostics: list[CompatibilityDiagnostic] = []

    for rule_id in (
        "model_mapping.domain.v1",
        "ordering.same_context.v1",
        "mapping_state.encoder_match.v1",
        "mapping_sector.representation.v1",
    ):
        result = by_id[rule_id]
        diagnostic_id, label = _DIAGNOSTIC_LABELS[rule_id]
        diagnostics.append(
            CompatibilityDiagnostic(
                diagnostic_id=diagnostic_id,
                label=label,
                status=result.status,
                severity=result.severity,
                source_rule_id=rule_id,
                message=result.message,
                failure_code=result.failure_code or result.binding_code,
                evidence=result.evidence,
                suggested_action=result.suggested_action,
            )
        )

    requires_ansatz = bool(context.task.get("requires_ansatz", True))
    if not requires_ansatz:
        particle_status = CheckStatus.NOT_APPLICABLE
        particle_message = "The analysis-only task has no ansatz invariant to evaluate."
        particle_severity = Severity.INFO
        particle_code = None
    else:
        particle_preserving = bool(
            context.ansatz.get("particle_number_preserving", False)
        )
        particle_status = CheckStatus.PASS if particle_preserving else CheckStatus.FAIL
        particle_message = (
            "The selected ansatz preserves the declared particle-number sector."
            if particle_preserving
            else "The selected ansatz does not preserve the required particle-number sector."
        )
        particle_severity = Severity.INFO if particle_preserving else Severity.FATAL
        particle_code = None if particle_preserving else "SECTOR_LEAKAGE_EXCEEDS_LIMIT"
    diagnostics.append(
        CompatibilityDiagnostic(
            diagnostic_id="particle_number_preservation",
            label="Particle-number preservation",
            status=particle_status,
            severity=particle_severity,
            source_rule_id="mapping_ansatz.generator_semantics.v1",
            message=particle_message,
            failure_code=particle_code,
            evidence={
                "particle_number_preserving": bool(
                    context.ansatz.get("particle_number_preserving", False)
                ),
                "hamming_weight_preserving": bool(
                    context.ansatz.get("hamming_weight_preserving", False)
                ),
                "semantic_class": context.ansatz.get("semantic_class"),
            },
            suggested_action=(
                None
                if particle_status in {CheckStatus.PASS, CheckStatus.NOT_APPLICABLE}
                else "Choose a sector-preserving ansatz and rerun composition conformance."
            ),
        )
    )

    for rule_id in (
        "mapping_ansatz.generator_semantics.v1",
        "mapping_task.all_operators_mapped.v1",
        "model_task_reference.same_problem.v1",
        "composition.resource_envelope.v1",
        "composition.acceptance_fingerprint.v1",
    ):
        result = by_id[rule_id]
        diagnostic_id, label = _DIAGNOSTIC_LABELS[rule_id]
        diagnostics.append(
            CompatibilityDiagnostic(
                diagnostic_id=diagnostic_id,
                label=label,
                status=result.status,
                severity=result.severity,
                source_rule_id=rule_id,
                message=result.message,
                failure_code=result.failure_code or result.binding_code,
                evidence=result.evidence,
                suggested_action=result.suggested_action,
            )
        )
    return tuple(diagnostics)


def _overall_status(binding_plan: ResolvedBindingPlan, rule_report, diagnostics) -> CheckStatus:
    if not binding_plan.all_required_resolved:
        return CheckStatus.BLOCKED
    statuses = {item.status for item in rule_report.results}
    statuses.update(item.status for item in diagnostics)
    if CheckStatus.BLOCKED in statuses:
        return CheckStatus.BLOCKED
    if CheckStatus.FAIL in statuses:
        return CheckStatus.FAIL
    if CheckStatus.REVIEW in statuses:
        return CheckStatus.REVIEW
    if CheckStatus.NOT_RUN in statuses:
        return CheckStatus.NOT_RUN
    return CheckStatus.PASS


def _runtime_decision(candidate: RealizationCandidate, binding_plan, rule_report, diagnostics) -> RuntimeEntryDecision:
    unresolved_codes = _binding_codes(binding_plan)
    if unresolved_codes:
        return RuntimeEntryDecision(
            status=RuntimeEntryStatus.RECOGNIZED_NOT_EXECUTABLE,
            path=RuntimePath.NONE,
            decision=DecisionStatus.DEFER,
            message=(
                "The candidate is understood, but at least one exact required implementation binding is unavailable."
            ),
            blocking_codes=unresolved_codes,
            suggested_actions=(
                "Install or register the exact versioned binding; no silent substitution is permitted.",
            ),
        )

    fatal_results = [item for item in rule_report.results if item.blocks_runtime]
    fatal_diagnostics = [
        item
        for item in diagnostics
        if item.status in {CheckStatus.FAIL, CheckStatus.BLOCKED}
        and item.severity in {Severity.ERROR, Severity.FATAL}
    ]
    if fatal_results or fatal_diagnostics:
        codes: list[str] = []
        actions: list[str] = []
        for item in fatal_results:
            code = item.failure_code or item.binding_code or item.rule_id
            if code not in codes:
                codes.append(code)
            if item.suggested_action and item.suggested_action not in actions:
                actions.append(item.suggested_action)
        for item in fatal_diagnostics:
            code = item.failure_code or item.diagnostic_id
            if code not in codes:
                codes.append(code)
            if item.suggested_action and item.suggested_action not in actions:
                actions.append(item.suggested_action)
        return RuntimeEntryDecision(
            status=RuntimeEntryStatus.BLOCKED_SCIENTIFIC,
            path=RuntimePath.NONE,
            decision=DecisionStatus.REJECT,
            message=(
                "A fatal scientific compatibility rule failed. The candidate is rejected before measurement, QASM, simulator, or hardware entry."
            ),
            blocking_codes=tuple(codes),
            suggested_actions=tuple(actions),
        )

    review_codes = tuple(
        item.failure_code
        for item in rule_report.results
        if item.status is CheckStatus.REVIEW and item.failure_code is not None
    )
    if candidate.task_mode is RealizationTaskMode.ANALYSIS_ONLY:
        return RuntimeEntryDecision(
            status=(
                RuntimeEntryStatus.ANALYSIS_ONLY_ALLOWED_WITH_REVIEW
                if review_codes
                else RuntimeEntryStatus.ANALYSIS_ONLY_ALLOWED
            ),
            path=RuntimePath.ANALYSIS_CONTROLLER,
            decision=DecisionStatus.REVIEW if review_codes else DecisionStatus.ACCEPT,
            message=(
                "The candidate may enter only the deterministic analysis controller; circuit execution remains not applicable."
            ),
            review_codes=review_codes,
            suggested_actions=tuple(
                item.suggested_action
                for item in rule_report.results
                if item.status is CheckStatus.REVIEW and item.suggested_action
            ),
        )
    return RuntimeEntryDecision(
        status=(
            RuntimeEntryStatus.EXECUTION_ALLOWED_WITH_REVIEW
            if review_codes
            else RuntimeEntryStatus.EXECUTION_ALLOWED
        ),
        path=RuntimePath.SHARED_EXECUTION_PIPELINE,
        decision=DecisionStatus.REVIEW if review_codes else DecisionStatus.ACCEPT,
        message=(
            "The candidate may enter the existing shared execution pipeline."
            if not review_codes
            else "The candidate is scientifically non-fatal but carries review conditions that remain visible at runtime entry."
        ),
        review_codes=review_codes,
        suggested_actions=tuple(
            item.suggested_action
            for item in rule_report.results
            if item.status is CheckStatus.REVIEW and item.suggested_action
        ),
    )


def _resolution_status(entry: RuntimeEntryDecision) -> ResolutionStatus:
    if entry.status is RuntimeEntryStatus.RECOGNIZED_NOT_EXECUTABLE:
        return ResolutionStatus.RECOGNIZED_NOT_EXECUTABLE
    if entry.status is RuntimeEntryStatus.BLOCKED_SCIENTIFIC:
        return ResolutionStatus.REJECTED
    if entry.status in {
        RuntimeEntryStatus.EXECUTION_ALLOWED_WITH_REVIEW,
        RuntimeEntryStatus.ANALYSIS_ONLY_ALLOWED_WITH_REVIEW,
    }:
        return ResolutionStatus.RESOLVED_WITH_REVIEW
    if entry.status is RuntimeEntryStatus.DEFERRED:
        return ResolutionStatus.DEFERRED
    return ResolutionStatus.RESOLVED


def _policy_status(entry: RuntimeEntryDecision, candidate: RealizationCandidate) -> PolicyStatus:
    if entry.status in {
        RuntimeEntryStatus.RECOGNIZED_NOT_EXECUTABLE,
        RuntimeEntryStatus.BLOCKED_SCIENTIFIC,
        RuntimeEntryStatus.DEFERRED,
    }:
        return PolicyStatus.RECOGNIZED_NOT_EXECUTABLE
    if candidate.task_mode is RealizationTaskMode.ANALYSIS_ONLY:
        return PolicyStatus.ACCEPTANCE_VERIFIED
    if entry.status is RuntimeEntryStatus.EXECUTION_ALLOWED_WITH_REVIEW:
        return PolicyStatus.EXPERIMENTAL
    return PolicyStatus.EXECUTION_READY


class RealizationVariantResolver:
    """Resolve one exact candidate through bindings, rules, and reports."""

    def __init__(
        self,
        *,
        contract_registry: DeclarativePolicyContractRegistry,
        binding_registry: ImplementationBindingRegistry,
        rule_registry: CompatibilityRuleRegistry,
    ) -> None:
        if not isinstance(contract_registry, DeclarativePolicyContractRegistry):
            raise RealizationResolverError("contract_registry has the wrong type.")
        if not isinstance(binding_registry, ImplementationBindingRegistry):
            raise RealizationResolverError("binding_registry has the wrong type.")
        if not isinstance(rule_registry, CompatibilityRuleRegistry):
            raise RealizationResolverError("rule_registry has the wrong type.")
        self.contract_registry = contract_registry
        self.binding_registry = binding_registry
        self.rule_registry = rule_registry

    def resolve(self, candidate: RealizationCandidate) -> RealizationResolution:
        if not isinstance(candidate, RealizationCandidate):
            raise TypeError("candidate must be RealizationCandidate.")

        binding_plan = resolve_contracts(
            self.contract_registry,
            self.binding_registry,
            candidate.contract_ids,
            plan_label=candidate.candidate_id,
        )
        rule_report = self.rule_registry.evaluate(candidate.rule_context)
        variant_seed = {
            "candidate": candidate.to_dict(),
            "binding_plan": binding_plan.to_public_dict(),
            "rule_report": rule_report.to_dict(),
        }
        variant_id = _deterministic_id("realization-variant", variant_seed)
        diagnostics = _rule_diagnostics(candidate, rule_report)
        overall = _overall_status(binding_plan, rule_report, diagnostics)
        entry = _runtime_decision(candidate, binding_plan, rule_report, diagnostics)

        resource_result = next(
            item
            for item in rule_report.results
            if item.rule_id == "composition.resource_envelope.v1"
        )
        resources = candidate.rule_context.resources
        resource_report = ResourceReport(
            report_id=_deterministic_id(
                "resource-report",
                {
                    "variant_id": variant_id,
                    "resources": candidate.rule_context.to_dict()["resources"],
                    "rule": resource_result.to_dict(),
                },
            ),
            variant_id=variant_id,
            status=resource_result.status,
            source_rule_id=resource_result.rule_id,
            within_declared_envelope=bool(
                resources.get("within_declared_envelope", False)
            ),
            estimate=dict(resources.get("estimate", {})),
            envelope=dict(resources.get("envelope", {})),
            exceeded_dimensions=tuple(
                str(item) for item in resources.get("exceeded_dimensions", ())
            ),
            runtime_blocking=resource_result.blocks_runtime,
            message=resource_result.message,
            suggested_action=resource_result.suggested_action,
        )

        acceptance_result = next(
            item
            for item in rule_report.results
            if item.rule_id == "composition.acceptance_fingerprint.v1"
        )
        acceptance_payload = candidate.rule_context.acceptance_evidence
        freshness = _freshness(acceptance_payload.get("freshness_status", "unknown"))
        acceptance_status = AcceptanceEvidenceStatus(
            variant_id=variant_id,
            check_status=acceptance_result.status,
            freshness_status=freshness,
            expected_fingerprint=acceptance_payload.get(
                "resolved_variant_fingerprint"
            ),
            observed_fingerprint=acceptance_payload.get("evidence_fingerprint"),
            policy_versions_match=bool(
                acceptance_payload.get("policy_versions_match", False)
            ),
            declared_scale_matches=bool(
                acceptance_payload.get("declared_scale_matches", False)
            ),
            required_for_runtime=True,
            required_for_promotion=True,
            promotable_under_wp5=False,
        )

        component_ids = dict(candidate.source_metadata.get("component_ids", {}))
        context_payload = candidate.rule_context.to_dict()
        provisional_fingerprint = str(
            context_payload["complete_tuple"].get(
                "resolved_variant_fingerprint",
                _deterministic_id("pre-wp6-fingerprint", variant_seed, width=32),
            )
        )
        compatibility_report_id = _deterministic_id(
            "compatibility-report",
            {
                "variant_id": variant_id,
                "bindings": [
                    item.report.to_dict() for item in binding_plan.implementations
                ],
                "rules": rule_report.to_dict(),
                "diagnostics": [item.to_dict() for item in diagnostics],
            },
        )
        summary = (
            "All required bindings and scientific rules passed."
            if overall is CheckStatus.PASS
            else "The candidate resolved with review conditions."
            if overall is CheckStatus.REVIEW
            else "The candidate is recognized but not executable; inspect missing exact bindings."
            if entry.status is RuntimeEntryStatus.RECOGNIZED_NOT_EXECUTABLE
            else "The candidate is blocked or rejected; inspect explicit diagnostics."
        )
        compatibility_report = CompatibilityReport(
            report_id=compatibility_report_id,
            variant_id=variant_id,
            binding_results=tuple(
                item.report for item in binding_plan.implementations
            ),
            pairwise_results=rule_report.pairwise_results,
            global_results=rule_report.global_results,
            diagnostics=diagnostics,
            overall_status=overall,
            decision=entry.decision,
            runtime_entry=entry,
            summary=summary,
            runtime_gate_enforced=True,
        )
        variant = ResolvedRealizationVariant(
            variant_id=variant_id,
            variant_version="1.0.0",
            candidate_id=candidate.candidate_id,
            model_id=str(context_payload["model"].get("model_id", "unknown-model")),
            task_id=str(context_payload["task"].get("task_id", "unknown-task")),
            task_mode=candidate.task_mode,
            component_ids=component_ids,
            contract_ids=candidate.contract_ids,
            binding_plan_public=binding_plan.to_public_dict(),
            encoding_context_fingerprint=str(
                context_payload["ordering"].get(
                    "encoding_context_fingerprint", "not-declared"
                )
            ),
            sector_fingerprint=str(
                context_payload["sector"].get(
                    "sector_fingerprint", "not-declared"
                )
            ),
            declared_scale=candidate.declared_scale,
            resolution_status=_resolution_status(entry),
            policy_status=_policy_status(entry, candidate),
            runtime_entry=entry,
            compatibility_report_id=compatibility_report.report_id,
            resource_report_id=resource_report.report_id,
            acceptance_evidence_freshness=freshness,
            provisional_variant_fingerprint=provisional_fingerprint,
            live_policy_migration_performed=False,
            scientific_status_promoted=False,
        )
        return RealizationResolution(
            candidate=candidate,
            variant=variant,
            compatibility_report=compatibility_report,
            resource_report=resource_report,
            acceptance_evidence=acceptance_status,
            binding_plan=binding_plan,
        )


def resolve_realization_variant(
    candidate: RealizationCandidate,
    *,
    contract_registry: DeclarativePolicyContractRegistry,
    binding_registry: ImplementationBindingRegistry,
    rule_registry: CompatibilityRuleRegistry,
) -> RealizationResolution:
    """Functional WP5 entry point returning all named resolver outputs."""

    return RealizationVariantResolver(
        contract_registry=contract_registry,
        binding_registry=binding_registry,
        rule_registry=rule_registry,
    ).resolve(candidate)


__all__ = [
    "RealizationResolverError",
    "RealizationVariantResolver",
    "resolve_realization_variant",
]

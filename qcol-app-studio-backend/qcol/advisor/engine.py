"""Deterministic, evidence-grounded Phase B Advisor engine.

The Advisor is a bounded proposer.  It evaluates versioned pure rules against a
frozen :class:`AdvisorContext`, emits grounded cards, and validates every
request patch against the WP13 governance allowlist.  It never mutates a
ProblemArtifact, RunResult, Evidence, verification policy, or the baseline
request.  An approved candidate request is returned to the canonical
``qcol.orchestrator.run_pipeline`` entrypoint; Phase B itself does not execute
it.
"""
from __future__ import annotations

from typing import Any, Mapping

from qcol.governance import validate_advisor_request_patch
from qcol.realization_policies.base import contract_fingerprint, json_contract_value
from qcol.request_boundaries import copy_plain_data

from .contracts import (
    AdvisorContext,
    AdvisorReport,
    CandidateRequestPlan,
    RecommendationCard,
)
from .enums import (
    AdvisorStatus,
    RecommendationEpistemicStatus,
    RecommendationKind,
)
from .rules import (
    RULE_BINDINGS,
    build_advisor_rule_contracts,
    evaluate_rule,
)

ADVISOR_VERSION = "1.0.0"
SAME_PIPELINE_ENTRYPOINT = "qcol.orchestrator.run_pipeline"


def _card_from_outcome(context: AdvisorContext, rule: Any, outcome: Any) -> RecommendationCard:
    patch_validation = None
    if outcome.patch is not None:
        patch_validation = validate_advisor_request_patch(outcome.patch)
        # A deterministic rule is never allowed to emit an invalid executable
        # hypothesis.  Convert it into a grounded limitation instead of
        # leaking an unsafe patch.
        if patch_validation.code != "ADVISOR_PATCH_ALLOWED":
            return RecommendationCard(
                card_id=f"advisor-card-{contract_fingerprint({'context': context.context_id, 'rule': rule.rule_id, 'invalid_patch': patch_validation.code})[:16]}",
                run_id=context.run_id,
                rule_id=rule.rule_id,
                reason_code=f"{rule.reason_code}_PATCH_BLOCKED",
                kind=rule.output_kind if rule.output_kind is not RecommendationKind.PATCH_HYPOTHESIS else RecommendationKind.LIMITATION,
                epistemic_status=RecommendationEpistemicStatus.VERIFIED_LIMITATION,
                title=outcome.title,
                summary=outcome.summary,
                explanation=(
                    f"{outcome.explanation} The proposed change was blocked by governance: "
                    f"{patch_validation.message}"
                ),
                evidence_refs=outcome.evidence_refs,
                proposed_patch=None,
                patch_validation=None,
                expected_effect="Report the governed limitation without changing the request.",
                limitations=tuple(outcome.limitations) + (
                    "No candidate request was prepared because the patch did not pass the exact WP13 allowlist.",
                ),
                requires_user_approval=False,
                requires_resolver_rerun=False,
                requires_pipeline_rerun=False,
                requires_new_evidence=False,
            )

    seed = {
        "context": context.context_id,
        "rule": rule.rule_id,
        "reason": rule.reason_code,
        "patch": None if outcome.patch is None else outcome.patch.to_dict(),
        "evidence": [item.to_dict() for item in outcome.evidence_refs],
    }
    has_patch = outcome.patch is not None
    return RecommendationCard(
        card_id=f"advisor-card-{contract_fingerprint(seed)[:16]}",
        run_id=context.run_id,
        rule_id=rule.rule_id,
        reason_code=rule.reason_code,
        kind=outcome.kind,
        epistemic_status=outcome.epistemic_status,
        title=outcome.title,
        summary=outcome.summary,
        explanation=outcome.explanation,
        evidence_refs=outcome.evidence_refs,
        proposed_patch=outcome.patch,
        patch_validation=patch_validation,
        expected_effect=outcome.expected_effect,
        limitations=outcome.limitations,
        requires_user_approval=has_patch,
        requires_resolver_rerun=has_patch,
        requires_pipeline_rerun=has_patch,
        requires_new_evidence=has_patch,
    )


def deterministic_advisor_rule_catalog_fingerprint() -> str:
    payload = {
        "schema_version": "qcol-advisor-rule-catalog/1.0",
        "advisor_version": ADVISOR_VERSION,
        "rules": [item.to_dict() for item in build_advisor_rule_contracts()],
        "predicate_bindings": sorted(RULE_BINDINGS),
        "callable_payload_withheld": True,
    }
    return contract_fingerprint(payload)


def evaluate_advisor_context(
    context: AdvisorContext,
    *,
    enabled: bool = True,
) -> AdvisorReport:
    """Evaluate all deterministic rules and return one immutable report."""
    rules = tuple(sorted(build_advisor_rule_contracts(), key=lambda item: (item.priority, item.rule_id)))
    evaluated_rule_ids = tuple(item.rule_id for item in rules)

    if not enabled:
        seed = {"context": context.context_id, "enabled": False, "version": ADVISOR_VERSION}
        return AdvisorReport(
            report_id=f"advisor-report-{contract_fingerprint(seed)[:16]}",
            context_id=context.context_id,
            context_fingerprint=context.fingerprint(),
            status=AdvisorStatus.DISABLED,
            cards=(),
            rule_catalog_fingerprint=deterministic_advisor_rule_catalog_fingerprint(),
            patch_registry_fingerprint=context.allowed_patch_registry_fingerprint,
            evaluated_rule_ids=evaluated_rule_ids,
            emitted_rule_ids=(),
            no_truth_mutation=True,
            problem_artifact_mutated=False,
            run_result_mutated=False,
            evidence_mutated=False,
            verification_mutated=False,
            same_pipeline_entrypoint=SAME_PIPELINE_ENTRYPOINT,
            verification_retains_final_authority=True,
            deterministic=True,
            advisor_runtime_enabled=False,
        )

    cards: list[RecommendationCard] = []
    emitted: list[str] = []
    patched_fields: set[str] = set()
    for rule in rules:
        outcome = evaluate_rule(rule, context)
        if outcome is None:
            continue
        card = _card_from_outcome(context, rule, outcome)
        # Avoid multiple competing hypotheses for the same field in one report.
        if card.proposed_patch is not None:
            field = card.proposed_patch.field_path
            if field in patched_fields:
                continue
            patched_fields.add(field)
        cards.append(card)
        emitted.append(rule.rule_id)

    if not cards:
        from .contracts import EvidenceReference
        ref = EvidenceReference(
            source="context",
            path="/status_triplet",
            label="Published mapper/composition/cell statuses",
            observed_value=context.status_triplet,
        )
        cards.append(RecommendationCard(
            card_id=f"advisor-card-{contract_fingerprint({'context': context.context_id, 'no_action': True})[:16]}",
            run_id=context.run_id,
            rule_id="advisor.rule.no_action.v1",
            reason_code="NO_GROUNDED_PATCH_REQUIRED",
            kind=RecommendationKind.NO_ACTION,
            epistemic_status=RecommendationEpistemicStatus.NO_ACTION,
            title="No bounded change recommended",
            summary="The current governed diagnostics do not trigger an allow-listed request patch.",
            explanation=(
                "QCOL remains usable without the Advisor.  The current run should be interpreted through its "
                "published compatibility, evidence, resource, and verification records."
            ),
            evidence_refs=(ref,),
            proposed_patch=None,
            patch_validation=None,
            expected_effect="Preserve the current verified request and evidence without unnecessary changes.",
            limitations=("This is not a claim that the run is globally optimal; it is only a bounded no-action decision.",),
            requires_user_approval=False,
            requires_resolver_rerun=False,
            requires_pipeline_rerun=False,
            requires_new_evidence=False,
        ))
        emitted.append("advisor.rule.no_action.v1")

    seed = {
        "context": context.context_id,
        "cards": [item.to_dict() for item in cards],
        "rule_catalog": deterministic_advisor_rule_catalog_fingerprint(),
    }
    return AdvisorReport(
        report_id=f"advisor-report-{contract_fingerprint(seed)[:16]}",
        context_id=context.context_id,
        context_fingerprint=context.fingerprint(),
        status=AdvisorStatus.READY,
        cards=tuple(cards),
        rule_catalog_fingerprint=deterministic_advisor_rule_catalog_fingerprint(),
        patch_registry_fingerprint=context.allowed_patch_registry_fingerprint,
        evaluated_rule_ids=evaluated_rule_ids,
        emitted_rule_ids=tuple(emitted),
        no_truth_mutation=True,
        problem_artifact_mutated=False,
        run_result_mutated=False,
        evidence_mutated=False,
        verification_mutated=False,
        same_pipeline_entrypoint=SAME_PIPELINE_ENTRYPOINT,
        verification_retains_final_authority=True,
        deterministic=True,
        advisor_runtime_enabled=True,
    )


def _decode_pointer(path: str) -> list[str]:
    if not path.startswith("/"):
        raise ValueError("Patch path must be absolute.")
    return [token.replace("~1", "/").replace("~0", "~") for token in path[1:].split("/") if token]


def _apply_patch_copy(request: Mapping[str, Any], card: RecommendationCard) -> dict[str, Any]:
    if card.proposed_patch is None:
        raise ValueError("Recommendation card has no request patch.")
    patch = card.proposed_patch
    if patch.operation.value != "replace":
        raise ValueError("Phase B supports replace operations only.")
    payload = copy_plain_data(request)
    if not isinstance(payload, dict):
        raise TypeError("Baseline request must be a mapping.")
    tokens = _decode_pointer(patch.field_path)
    if not tokens:
        raise ValueError("The root request cannot be replaced.")
    cursor: dict[str, Any] = payload
    for token in tokens[:-1]:
        child = cursor.get(token)
        if child is None:
            child = {}
            cursor[token] = child
        if not isinstance(child, dict):
            raise ValueError(f"Patch path crosses a non-mapping value at {token!r}.")
        cursor = child
    cursor[tokens[-1]] = copy_plain_data(patch.proposed_value)
    return json_contract_value(payload)


def prepare_candidate_request_plan(
    baseline_request: Mapping[str, Any],
    card: RecommendationCard,
    *,
    approved: bool,
) -> CandidateRequestPlan:
    """Prepare, but never execute, one user-approved candidate request."""
    baseline = json_contract_value(copy_plain_data(baseline_request))
    baseline_fp = contract_fingerprint(baseline)
    if card.proposed_patch is None or card.patch_validation is None:
        raise ValueError("Only a validated patch-hypothesis card can prepare a candidate request.")
    if card.patch_validation.code != "ADVISOR_PATCH_ALLOWED":
        raise ValueError("The card patch did not pass the exact governed allowlist.")

    if not approved:
        seed = {"card": card.card_id, "approved": False, "baseline": baseline_fp}
        return CandidateRequestPlan(
            plan_id=f"advisor-candidate-plan-{contract_fingerprint(seed)[:16]}",
            card_id=card.card_id,
            patch_id=card.proposed_patch.patch_id,
            approved=False,
            validation_report=card.patch_validation,
            baseline_request_fingerprint=baseline_fp,
            candidate_request_fingerprint=None,
            candidate_request=None,
            pipeline_entrypoint=SAME_PIPELINE_ENTRYPOINT,
            execution_performed=False,
            baseline_request_mutated=False,
        )

    candidate = _apply_patch_copy(baseline, card)
    candidate_fp = contract_fingerprint(candidate)
    # Verify the baseline mapping remained byte-for-byte equivalent as strict JSON.
    if contract_fingerprint(json_contract_value(copy_plain_data(baseline_request))) != baseline_fp:
        raise RuntimeError("Baseline request changed while preparing the candidate request.")
    seed = {
        "card": card.card_id,
        "approved": True,
        "baseline": baseline_fp,
        "candidate": candidate_fp,
    }
    return CandidateRequestPlan(
        plan_id=f"advisor-candidate-plan-{contract_fingerprint(seed)[:16]}",
        card_id=card.card_id,
        patch_id=card.proposed_patch.patch_id,
        approved=True,
        validation_report=card.patch_validation,
        baseline_request_fingerprint=baseline_fp,
        candidate_request_fingerprint=candidate_fp,
        candidate_request=candidate,
        pipeline_entrypoint=SAME_PIPELINE_ENTRYPOINT,
        execution_performed=False,
        baseline_request_mutated=False,
    )


def advise_run_payload(
    snapshot: Mapping[str, Any],
    *,
    previous_snapshot: Mapping[str, Any] | None = None,
    enabled: bool = True,
) -> tuple[AdvisorContext, AdvisorReport]:
    from .context import build_advisor_context_from_run_payload
    context = build_advisor_context_from_run_payload(snapshot, previous_snapshot=previous_snapshot)
    return context, evaluate_advisor_context(context, enabled=enabled)


__all__ = [
    "ADVISOR_VERSION",
    "SAME_PIPELINE_ENTRYPOINT",
    "deterministic_advisor_rule_catalog_fingerprint",
    "evaluate_advisor_context",
    "prepare_candidate_request_plan",
    "advise_run_payload",
]

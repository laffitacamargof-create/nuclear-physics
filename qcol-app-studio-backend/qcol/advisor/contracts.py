"""Strict-JSON contracts for the deterministic Advisor."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Tuple

from qcol.governance.contracts import RequestPatchCandidate, RequestPatchValidationReport
from qcol.realization_policies.base import (
    DeclarativeContract,
    PolicyContractError,
    freeze_json,
    require_text,
    require_token,
)

from .enums import (
    AdvisorRulePhase,
    AdvisorStatus,
    RecommendationEpistemicStatus,
    RecommendationKind,
)

ADVISOR_CONTEXT_SCHEMA_VERSION = "qcol-advisor-context/1.0"
ADVISOR_RULE_SCHEMA_VERSION = "qcol-advisor-rule/1.0"
EVIDENCE_REFERENCE_SCHEMA_VERSION = "qcol-advisor-evidence-reference/1.0"
RECOMMENDATION_CARD_SCHEMA_VERSION = "qcol-recommendation-card/1.0"
ADVISOR_REPORT_SCHEMA_VERSION = "qcol-deterministic-advisor-report/1.0"
CANDIDATE_REQUEST_PLAN_SCHEMA_VERSION = "qcol-advisor-candidate-request-plan/1.0"


@dataclass(frozen=True)
class EvidenceReference(DeclarativeContract):
    source: str
    path: str
    label: str
    observed_value: Any
    schema_version: str = EVIDENCE_REFERENCE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        require_token("source", self.source)
        if not isinstance(self.path, str) or not self.path.startswith("/"):
            raise PolicyContractError("EvidenceReference.path must be an absolute JSON-pointer-like path.")
        require_text("label", self.label)
        object.__setattr__(
            self,
            "observed_value",
            freeze_json(self.observed_value, path="EvidenceReference.observed_value"),
        )


@dataclass(frozen=True)
class PreviousRunSummary(DeclarativeContract):
    run_id: str
    variant_id: str
    variant_fingerprint: str
    final_parameters: Tuple[float, ...]
    status: str
    parameter_source: str
    schema_version: str = "qcol-advisor-previous-run-summary/1.0"

    def __post_init__(self) -> None:
        for label in ("run_id", "variant_id", "variant_fingerprint", "status"):
            require_token(label, getattr(self, label))
        require_text("parameter_source", self.parameter_source)
        values = tuple(float(item) for item in self.final_parameters)
        if not values:
            raise PolicyContractError("PreviousRunSummary.final_parameters must not be empty.")
        object.__setattr__(self, "final_parameters", values)


@dataclass(frozen=True)
class AdvisorContext(DeclarativeContract):
    context_id: str
    run_id: str
    model_id: str
    task_id: str
    variant_id: str
    variant_fingerprint: str
    status_triplet: Mapping[str, Any]
    compatibility_report: Mapping[str, Any]
    acceptance_evidence: Mapping[str, Any]
    resource_report: Mapping[str, Any]
    telemetry: Mapping[str, Any]
    request_view: Mapping[str, Any]
    stable_failure_codes: Tuple[str, ...]
    allowed_patch_registry_id: str
    allowed_patch_registry_fingerprint: str
    source_snapshot_fingerprint: str
    previous_run: Optional[PreviousRunSummary] = None
    schema_version: str = ADVISOR_CONTEXT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for label in (
            "context_id",
            "run_id",
            "model_id",
            "task_id",
            "variant_id",
            "variant_fingerprint",
            "allowed_patch_registry_id",
            "allowed_patch_registry_fingerprint",
            "source_snapshot_fingerprint",
        ):
            require_token(label, getattr(self, label))
        for name in (
            "status_triplet",
            "compatibility_report",
            "acceptance_evidence",
            "resource_report",
            "telemetry",
            "request_view",
        ):
            object.__setattr__(
                self,
                name,
                freeze_json(getattr(self, name), path=f"AdvisorContext.{name}"),
            )
        codes = tuple(sorted({require_token("stable_failure_codes", str(item)) for item in self.stable_failure_codes}))
        object.__setattr__(self, "stable_failure_codes", codes)


@dataclass(frozen=True)
class AdvisorRuleContract(DeclarativeContract):
    rule_id: str
    rule_version: str
    priority: int
    phase: AdvisorRulePhase
    reason_code: str
    predicate_binding_id: str
    output_kind: RecommendationKind
    title: str
    description: str
    applies_to_task_ids: Tuple[str, ...] = field(default_factory=tuple)
    applies_to_variant_ids: Tuple[str, ...] = field(default_factory=tuple)
    schema_version: str = ADVISOR_RULE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for label in ("rule_id", "rule_version", "reason_code", "predicate_binding_id"):
            require_token(label, getattr(self, label))
        if self.priority < 0:
            raise PolicyContractError("Advisor rule priority must be non-negative.")
        if not isinstance(self.phase, AdvisorRulePhase):
            raise PolicyContractError("phase must be AdvisorRulePhase.")
        if not isinstance(self.output_kind, RecommendationKind):
            raise PolicyContractError("output_kind must be RecommendationKind.")
        require_text("title", self.title)
        require_text("description", self.description)
        object.__setattr__(self, "applies_to_task_ids", tuple(require_token("applies_to_task_ids", str(x)) for x in self.applies_to_task_ids))
        object.__setattr__(self, "applies_to_variant_ids", tuple(require_token("applies_to_variant_ids", str(x)) for x in self.applies_to_variant_ids))


@dataclass(frozen=True)
class RecommendationCard(DeclarativeContract):
    card_id: str
    run_id: str
    rule_id: str
    reason_code: str
    kind: RecommendationKind
    epistemic_status: RecommendationEpistemicStatus
    title: str
    summary: str
    explanation: str
    evidence_refs: Tuple[EvidenceReference, ...]
    proposed_patch: Optional[RequestPatchCandidate]
    patch_validation: Optional[RequestPatchValidationReport]
    expected_effect: str
    limitations: Tuple[str, ...]
    requires_user_approval: bool
    requires_resolver_rerun: bool
    requires_pipeline_rerun: bool
    requires_new_evidence: bool
    verification_retains_final_authority: bool = True
    schema_version: str = RECOMMENDATION_CARD_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for label in ("card_id", "run_id", "rule_id", "reason_code"):
            require_token(label, getattr(self, label))
        if not isinstance(self.kind, RecommendationKind):
            raise PolicyContractError("kind must be RecommendationKind.")
        if not isinstance(self.epistemic_status, RecommendationEpistemicStatus):
            raise PolicyContractError("epistemic_status must be RecommendationEpistemicStatus.")
        for label in ("title", "summary", "explanation", "expected_effect"):
            require_text(label, getattr(self, label))
        refs = tuple(self.evidence_refs)
        if not refs or not all(isinstance(item, EvidenceReference) for item in refs):
            raise PolicyContractError("Every RecommendationCard must cite at least one EvidenceReference.")
        object.__setattr__(self, "evidence_refs", refs)
        limits = tuple(require_text("limitations", str(item)) for item in self.limitations)
        if not limits:
            raise PolicyContractError("RecommendationCard.limitations must not be empty.")
        object.__setattr__(self, "limitations", limits)
        if self.proposed_patch is None:
            if self.patch_validation is not None:
                raise PolicyContractError("A card without a patch cannot carry patch_validation.")
            if any((self.requires_user_approval, self.requires_resolver_rerun, self.requires_pipeline_rerun, self.requires_new_evidence)):
                raise PolicyContractError("A no-patch card cannot claim rerun requirements.")
        else:
            if self.patch_validation is None:
                raise PolicyContractError("A patch hypothesis requires a validation report.")
            if self.epistemic_status is not RecommendationEpistemicStatus.HYPOTHESIS:
                raise PolicyContractError("A proposed patch must remain a hypothesis.")
            if not all((self.requires_user_approval, self.requires_resolver_rerun, self.requires_pipeline_rerun, self.requires_new_evidence)):
                raise PolicyContractError("Every patch hypothesis must require approval, resolution, rerun, and new Evidence.")


@dataclass(frozen=True)
class AdvisorReport(DeclarativeContract):
    report_id: str
    context_id: str
    context_fingerprint: str
    status: AdvisorStatus
    cards: Tuple[RecommendationCard, ...]
    rule_catalog_fingerprint: str
    patch_registry_fingerprint: str
    evaluated_rule_ids: Tuple[str, ...]
    emitted_rule_ids: Tuple[str, ...]
    no_truth_mutation: bool
    problem_artifact_mutated: bool
    run_result_mutated: bool
    evidence_mutated: bool
    verification_mutated: bool
    same_pipeline_entrypoint: str
    verification_retains_final_authority: bool
    deterministic: bool
    advisor_runtime_enabled: bool
    schema_version: str = ADVISOR_REPORT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for label in (
            "report_id",
            "context_id",
            "context_fingerprint",
            "rule_catalog_fingerprint",
            "patch_registry_fingerprint",
            "same_pipeline_entrypoint",
        ):
            require_token(label, getattr(self, label))
        if not isinstance(self.status, AdvisorStatus):
            raise PolicyContractError("status must be AdvisorStatus.")
        cards = tuple(self.cards)
        if not all(isinstance(item, RecommendationCard) for item in cards):
            raise PolicyContractError("cards must contain RecommendationCard objects.")
        object.__setattr__(self, "cards", cards)
        object.__setattr__(self, "evaluated_rule_ids", tuple(require_token("evaluated_rule_ids", str(x)) for x in self.evaluated_rule_ids))
        object.__setattr__(self, "emitted_rule_ids", tuple(require_token("emitted_rule_ids", str(x)) for x in self.emitted_rule_ids))
        if not self.no_truth_mutation or any((self.problem_artifact_mutated, self.run_result_mutated, self.evidence_mutated, self.verification_mutated)):
            raise PolicyContractError("The deterministic Advisor may not mutate scientific truth.")
        if self.same_pipeline_entrypoint != "qcol.orchestrator.run_pipeline":
            raise PolicyContractError("Advisor patches must return to qcol.orchestrator.run_pipeline.")


@dataclass(frozen=True)
class CandidateRequestPlan(DeclarativeContract):
    plan_id: str
    card_id: str
    patch_id: str
    approved: bool
    validation_report: RequestPatchValidationReport
    baseline_request_fingerprint: str
    candidate_request_fingerprint: Optional[str]
    candidate_request: Optional[Mapping[str, Any]]
    pipeline_entrypoint: str
    execution_performed: bool
    baseline_request_mutated: bool
    user_approval_required: bool = True
    resolver_rerun_required: bool = True
    new_evidence_required: bool = True
    schema_version: str = CANDIDATE_REQUEST_PLAN_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for label in ("plan_id", "card_id", "patch_id", "baseline_request_fingerprint", "pipeline_entrypoint"):
            require_token(label, getattr(self, label))
        if self.pipeline_entrypoint != "qcol.orchestrator.run_pipeline":
            raise PolicyContractError("Candidate requests must target the canonical run_pipeline entrypoint.")
        if self.execution_performed:
            raise PolicyContractError("Phase B may prepare a candidate request but may not execute it.")
        if self.baseline_request_mutated:
            raise PolicyContractError("Phase B must not mutate the baseline request.")
        if self.approved:
            if self.candidate_request is None or self.candidate_request_fingerprint is None:
                raise PolicyContractError("An approved plan must contain a candidate request and fingerprint.")
            object.__setattr__(self, "candidate_request", freeze_json(self.candidate_request, path="CandidateRequestPlan.candidate_request"))
        else:
            if self.candidate_request is not None or self.candidate_request_fingerprint is not None:
                raise PolicyContractError("An unapproved plan must not reveal an executable candidate request.")


__all__ = [
    "ADVISOR_CONTEXT_SCHEMA_VERSION",
    "ADVISOR_RULE_SCHEMA_VERSION",
    "RECOMMENDATION_CARD_SCHEMA_VERSION",
    "ADVISOR_REPORT_SCHEMA_VERSION",
    "EvidenceReference",
    "PreviousRunSummary",
    "AdvisorContext",
    "AdvisorRuleContract",
    "RecommendationCard",
    "AdvisorReport",
    "CandidateRequestPlan",
]

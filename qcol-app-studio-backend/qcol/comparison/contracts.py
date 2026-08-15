"""Strict-JSON Phase C comparison contracts.

Phase C never silently replaces the baseline.  It records two independent run
identities, their evidence, a declared comparison policy, and one bounded
ADOPT/REJECT/INCONCLUSIVE outcome.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Tuple

from qcol.realization_policies.base import (
    DeclarativeContract, PolicyContractError, freeze_json, require_text, require_token,
)
from .enums import (
    ComparisonKind, ComparisonOutcome, ComparisonStatus,
    MetricDirection, MetricJudgment,
)


@dataclass(frozen=True)
class ComparisonPolicyContract(DeclarativeContract):
    policy_id: str
    policy_version: str
    comparison_kind: ComparisonKind
    required_identity_fields: Tuple[str, ...]
    required_metrics: Tuple[str, ...]
    optional_metrics: Tuple[str, ...]
    uncertainty_rule: str
    missing_metric_rule: str
    acceptance_rule: str
    physical_accuracy_ranking_allowed: bool
    description: str
    schema_version: str = "qcol-comparison-policy/1.0"

    def __post_init__(self) -> None:
        require_token("policy_id", self.policy_id)
        require_token("policy_version", self.policy_version)
        if not isinstance(self.comparison_kind, ComparisonKind):
            raise PolicyContractError("comparison_kind must be ComparisonKind.")
        for name in ("required_identity_fields", "required_metrics", "optional_metrics"):
            values = tuple(require_token(name, str(x)) for x in getattr(self, name))
            object.__setattr__(self, name, values)
        require_text("uncertainty_rule", self.uncertainty_rule)
        require_text("missing_metric_rule", self.missing_metric_rule)
        require_text("acceptance_rule", self.acceptance_rule)
        require_text("description", self.description)


@dataclass(frozen=True)
class MetricComparison(DeclarativeContract):
    metric_id: str
    label: str
    baseline_value: Any
    candidate_value: Any
    delta: Any
    direction: MetricDirection
    judgment: MetricJudgment
    uncertainty_threshold: Optional[float]
    rationale: str
    evidence_refs: Tuple[str, ...]
    schema_version: str = "qcol-metric-comparison/1.0"

    def __post_init__(self) -> None:
        require_token("metric_id", self.metric_id)
        require_text("label", self.label)
        if not isinstance(self.direction, MetricDirection):
            raise PolicyContractError("direction must be MetricDirection.")
        if not isinstance(self.judgment, MetricJudgment):
            raise PolicyContractError("judgment must be MetricJudgment.")
        object.__setattr__(self, "baseline_value", freeze_json(self.baseline_value, path="MetricComparison.baseline_value"))
        object.__setattr__(self, "candidate_value", freeze_json(self.candidate_value, path="MetricComparison.candidate_value"))
        object.__setattr__(self, "delta", freeze_json(self.delta, path="MetricComparison.delta"))
        if self.uncertainty_threshold is not None and self.uncertainty_threshold < 0:
            raise PolicyContractError("uncertainty_threshold must be non-negative.")
        require_text("rationale", self.rationale)
        refs = tuple(require_text("evidence_refs", str(x)) for x in self.evidence_refs)
        if not refs:
            raise PolicyContractError("Every metric comparison must cite evidence fields.")
        object.__setattr__(self, "evidence_refs", refs)


@dataclass(frozen=True)
class RunComparison(DeclarativeContract):
    comparison_id: str
    comparison_kind: ComparisonKind
    policy_id: str
    policy_version: str
    baseline_run_id: str
    candidate_run_id: str
    baseline_request_fingerprint: str
    candidate_request_fingerprint: str
    baseline_evidence_schema: str
    candidate_evidence_schema: str
    same_pipeline_entrypoint: str
    same_model_task_cell: bool
    explicit_user_approval: bool
    metrics: Tuple[MetricComparison, ...]
    outcome: ComparisonOutcome
    rationale: str
    warnings: Tuple[str, ...]
    missing_metrics: Tuple[str, ...]
    baseline_verification_status: str
    candidate_verification_status: str
    physical_accuracy_ranking_claimed: bool
    automatic_replacement_performed: bool
    evidence_refs: Tuple[str, ...]
    schema_version: str = "qcol-run-comparison/1.0"

    def __post_init__(self) -> None:
        for label in (
            "comparison_id", "policy_id", "policy_version", "baseline_run_id", "candidate_run_id",
            "baseline_request_fingerprint", "candidate_request_fingerprint", "same_pipeline_entrypoint",
        ):
            require_token(label, getattr(self, label))
        require_text("baseline_evidence_schema", self.baseline_evidence_schema)
        require_text("candidate_evidence_schema", self.candidate_evidence_schema)
        if not isinstance(self.comparison_kind, ComparisonKind):
            raise PolicyContractError("comparison_kind must be ComparisonKind.")
        if not isinstance(self.outcome, ComparisonOutcome):
            raise PolicyContractError("outcome must be ComparisonOutcome.")
        if self.same_pipeline_entrypoint != "qcol.orchestrator.run_pipeline":
            raise PolicyContractError("Phase C candidates must use qcol.orchestrator.run_pipeline.")
        if not self.explicit_user_approval:
            raise PolicyContractError("Phase C comparisons require explicit user approval.")
        if not self.same_model_task_cell:
            raise PolicyContractError("Baseline and candidate must belong to the same Model × Task cell.")
        if self.automatic_replacement_performed:
            raise PolicyContractError("Phase C may not silently replace the baseline.")
        if self.comparison_kind is ComparisonKind.MAPPING_ANALYSIS and self.physical_accuracy_ranking_claimed:
            raise PolicyContractError("Mapping-resource comparison may not claim physical-accuracy ranking.")
        items = tuple(self.metrics)
        if not all(isinstance(item, MetricComparison) for item in items):
            raise PolicyContractError("metrics must contain MetricComparison values.")
        object.__setattr__(self, "metrics", items)
        object.__setattr__(self, "warnings", tuple(require_text("warnings", str(x)) for x in self.warnings))
        object.__setattr__(self, "missing_metrics", tuple(require_token("missing_metrics", str(x)) for x in self.missing_metrics))
        object.__setattr__(self, "evidence_refs", tuple(require_text("evidence_refs", str(x)) for x in self.evidence_refs))
        require_text("rationale", self.rationale)


@dataclass(frozen=True)
class ComparisonDecisionRecord(DeclarativeContract):
    decision_id: str
    comparison_id: str
    baseline_run_id: str
    candidate_run_id: str
    outcome: ComparisonOutcome
    rationale: str
    policy_id: str
    user_approved_candidate: bool
    automatic_replacement_performed: bool
    recorded_with_both_run_ids: bool
    verification_retains_final_authority: bool
    evidence_refs: Tuple[str, ...]
    schema_version: str = "qcol-comparison-decision-record/1.0"

    def __post_init__(self) -> None:
        for label in ("decision_id", "comparison_id", "baseline_run_id", "candidate_run_id", "policy_id"):
            require_token(label, getattr(self, label))
        if not isinstance(self.outcome, ComparisonOutcome):
            raise PolicyContractError("outcome must be ComparisonOutcome.")
        require_text("rationale", self.rationale)
        if not self.user_approved_candidate:
            raise PolicyContractError("Decision record requires a user-approved candidate.")
        if self.automatic_replacement_performed:
            raise PolicyContractError("Decision records cannot represent silent replacement.")
        if not self.recorded_with_both_run_ids or not self.verification_retains_final_authority:
            raise PolicyContractError("Decision must retain both run IDs and verification authority.")
        object.__setattr__(self, "evidence_refs", tuple(require_text("evidence_refs", str(x)) for x in self.evidence_refs))


@dataclass(frozen=True)
class TryCompareSession(DeclarativeContract):
    session_id: str
    baseline_run_id: str
    candidate_run_id: str
    advisor_card_id: str
    candidate_plan_id: str
    policy_id: str
    status: ComparisonStatus
    approved: bool
    same_pipeline_entrypoint: str
    candidate_execution_started: bool
    comparison: Optional[RunComparison] = None
    decision_record: Optional[ComparisonDecisionRecord] = None
    error: Optional[str] = None
    evidence_available: bool = False
    created_utc: Optional[str] = None
    completed_utc: Optional[str] = None
    schema_version: str = "qcol-try-compare-session/1.0"

    def __post_init__(self) -> None:
        for label in ("session_id", "baseline_run_id", "candidate_run_id", "advisor_card_id", "candidate_plan_id", "policy_id", "same_pipeline_entrypoint"):
            require_token(label, getattr(self, label))
        if not isinstance(self.status, ComparisonStatus):
            raise PolicyContractError("status must be ComparisonStatus.")
        if not self.approved or not self.candidate_execution_started:
            raise PolicyContractError("A Phase C session exists only after approval and candidate execution start.")
        if self.same_pipeline_entrypoint != "qcol.orchestrator.run_pipeline":
            raise PolicyContractError("Phase C must reuse the canonical pipeline.")


__all__ = [
    "ComparisonPolicyContract", "MetricComparison", "RunComparison",
    "ComparisonDecisionRecord", "TryCompareSession",
]

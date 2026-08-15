"""Declarative WP4 compatibility-rule contracts and public reports.

Scientific judgment is represented as versioned rules.  Public contracts and
reports are strict JSON and never contain executable predicates.  Predicate
callables are resolved through the WP3 implementation-binding registry.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from qcol.compatibility.failure_codes import CompatibilityFailureCode
from qcol.mapping_policies import CheckStatus, DecisionStatus, Severity
from qcol.realization_policies.base import (
    DeclarativeContract,
    PolicyContractError,
    freeze_json,
    require_text,
    require_token,
)

from .enums import CompatibilityParticipant, CompatibilityRulePhase


COMPATIBILITY_RULE_CONTRACT_SCHEMA_VERSION = (
    "qcol-compatibility-rule-contract/1.0"
)
RULE_EVALUATION_CONTEXT_SCHEMA_VERSION = (
    "qcol-compatibility-rule-evaluation-context/1.0"
)
PREDICATE_RESULT_SCHEMA_VERSION = "qcol-compatibility-predicate-result/1.0"
COMPATIBILITY_CHECK_RESULT_SCHEMA_VERSION = (
    "qcol-compatibility-check-result/1.0"
)
COMPATIBILITY_EVALUATION_REPORT_SCHEMA_VERSION = (
    "qcol-compatibility-rule-evaluation-report/1.0"
)


@dataclass(frozen=True)
class CompatibilityRuleContract(DeclarativeContract):
    """One versioned, testable scientific relation rule."""

    rule_id: str
    rule_version: str
    display_name: str
    phase: CompatibilityRulePhase
    participants: tuple[CompatibilityParticipant, ...]
    predicate_binding_id: str
    predicate_binding_version: str
    predicate_convention_id: str
    failure_code: CompatibilityFailureCode
    severity: Severity
    pass_condition: str
    required_evidence: tuple[str, ...]
    suggested_action: str
    description: str = ""
    schema_version: str = COMPATIBILITY_RULE_CONTRACT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in (
            "rule_id",
            "rule_version",
            "predicate_binding_id",
            "predicate_binding_version",
            "predicate_convention_id",
        ):
            require_token(name, getattr(self, name))
        require_text("display_name", self.display_name)
        require_text("pass_condition", self.pass_condition)
        require_text("suggested_action", self.suggested_action)
        if self.description:
            require_text("description", self.description)
        if not isinstance(self.phase, CompatibilityRulePhase):
            raise PolicyContractError("phase must be CompatibilityRulePhase.")
        if not self.participants:
            raise PolicyContractError("participants must not be empty.")
        if not all(isinstance(item, CompatibilityParticipant) for item in self.participants):
            raise PolicyContractError(
                "participants entries must be CompatibilityParticipant values."
            )
        if len(set(self.participants)) != len(self.participants):
            raise PolicyContractError("participants must not contain duplicates.")
        if not isinstance(self.failure_code, CompatibilityFailureCode):
            raise PolicyContractError(
                "failure_code must be CompatibilityFailureCode."
            )
        if not isinstance(self.severity, Severity):
            raise PolicyContractError("severity must be Severity.")
        evidence = tuple(
            require_token("required_evidence", str(item))
            for item in self.required_evidence
        )
        if len(set(evidence)) != len(evidence):
            raise PolicyContractError(
                "required_evidence must not contain duplicates."
            )
        object.__setattr__(self, "required_evidence", evidence)


@dataclass(frozen=True)
class RuleEvaluationContext(DeclarativeContract):
    """Strict-JSON facts consumed by compatibility predicates.

    WP4 deliberately evaluates facts rather than scientific runtime objects.
    WP5 will build this context from the selected model/task/policy contracts.
    """

    context_id: str
    context_version: str
    model: Mapping[str, Any]
    task: Mapping[str, Any]
    mapping: Mapping[str, Any]
    ordering: Mapping[str, Any]
    sector: Mapping[str, Any]
    state_preparation: Mapping[str, Any] = field(default_factory=dict)
    ansatz: Mapping[str, Any] = field(default_factory=dict)
    measurement: Mapping[str, Any] = field(default_factory=dict)
    reference: Mapping[str, Any] = field(default_factory=dict)
    resources: Mapping[str, Any] = field(default_factory=dict)
    acceptance_evidence: Mapping[str, Any] = field(default_factory=dict)
    complete_tuple: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = RULE_EVALUATION_CONTEXT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        require_token("context_id", self.context_id)
        require_token("context_version", self.context_version)
        for name in (
            "model",
            "task",
            "mapping",
            "ordering",
            "sector",
            "state_preparation",
            "ansatz",
            "measurement",
            "reference",
            "resources",
            "acceptance_evidence",
            "complete_tuple",
        ):
            value = getattr(self, name)
            if not isinstance(value, Mapping):
                raise PolicyContractError(f"{name} must be a mapping.")
            object.__setattr__(
                self,
                name,
                freeze_json(value, path=f"RuleEvaluationContext.{name}"),
            )

    def component(self, name: str) -> Mapping[str, Any]:
        value = getattr(self, name)
        if not isinstance(value, Mapping):  # pragma: no cover - constructor guard
            return {}
        return value


@dataclass(frozen=True)
class PredicateResult(DeclarativeContract):
    """Result returned by one internal predicate callable."""

    status: CheckStatus
    message: str
    evidence: Mapping[str, Any] = field(default_factory=dict)
    details: Mapping[str, Any] = field(default_factory=dict)
    suggested_action: str | None = None
    schema_version: str = PREDICATE_RESULT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.status, CheckStatus):
            raise PolicyContractError("status must be CheckStatus.")
        require_text("message", self.message)
        if self.suggested_action is not None:
            require_text("suggested_action", self.suggested_action)
        object.__setattr__(
            self,
            "evidence",
            freeze_json(self.evidence, path="PredicateResult.evidence"),
        )
        object.__setattr__(
            self,
            "details",
            freeze_json(self.details, path="PredicateResult.details"),
        )


@dataclass(frozen=True)
class CompatibilityCheckResult(DeclarativeContract):
    """Public result of evaluating one rule."""

    rule_id: str
    rule_version: str
    phase: CompatibilityRulePhase
    participants: tuple[CompatibilityParticipant, ...]
    status: CheckStatus
    severity: Severity
    message: str
    failure_code: str | None = None
    binding_code: str | None = None
    evidence: Mapping[str, Any] = field(default_factory=dict)
    details: Mapping[str, Any] = field(default_factory=dict)
    suggested_action: str | None = None
    schema_version: str = COMPATIBILITY_CHECK_RESULT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        require_token("rule_id", self.rule_id)
        require_token("rule_version", self.rule_version)
        if not isinstance(self.phase, CompatibilityRulePhase):
            raise PolicyContractError("phase must be CompatibilityRulePhase.")
        if not all(isinstance(item, CompatibilityParticipant) for item in self.participants):
            raise PolicyContractError(
                "participants entries must be CompatibilityParticipant values."
            )
        if not isinstance(self.status, CheckStatus):
            raise PolicyContractError("status must be CheckStatus.")
        if not isinstance(self.severity, Severity):
            raise PolicyContractError("severity must be Severity.")
        require_text("message", self.message)
        for name in ("failure_code", "binding_code"):
            value = getattr(self, name)
            if value is not None:
                require_token(name, value)
        if self.suggested_action is not None:
            require_text("suggested_action", self.suggested_action)
        object.__setattr__(
            self,
            "evidence",
            freeze_json(self.evidence, path="CompatibilityCheckResult.evidence"),
        )
        object.__setattr__(
            self,
            "details",
            freeze_json(self.details, path="CompatibilityCheckResult.details"),
        )

    @property
    def applicable(self) -> bool:
        return self.status is not CheckStatus.NOT_APPLICABLE

    @property
    def passed(self) -> bool:
        return self.status in {CheckStatus.PASS, CheckStatus.NOT_APPLICABLE}

    @property
    def blocks_runtime(self) -> bool:
        return self.status in {CheckStatus.FAIL, CheckStatus.BLOCKED} and self.severity in {
            Severity.ERROR,
            Severity.FATAL,
        }

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "applicable": self.applicable,
                "passed": self.passed,
                "blocks_runtime": self.blocks_runtime,
            }
        )
        return payload


@dataclass(frozen=True)
class CompatibilityRuleEvaluationReport(DeclarativeContract):
    """Separated pairwise and global results for one candidate tuple."""

    report_id: str
    context_id: str
    pairwise_results: tuple[CompatibilityCheckResult, ...]
    global_results: tuple[CompatibilityCheckResult, ...]
    runtime_gate_enforced: bool = False
    scientific_behavior_change: bool = False
    schema_version: str = COMPATIBILITY_EVALUATION_REPORT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        require_token("report_id", self.report_id)
        require_token("context_id", self.context_id)
        for name, phase in (
            ("pairwise_results", CompatibilityRulePhase.PAIRWISE),
            ("global_results", CompatibilityRulePhase.GLOBAL_INVARIANT),
        ):
            values = tuple(getattr(self, name))
            if not all(isinstance(item, CompatibilityCheckResult) for item in values):
                raise PolicyContractError(
                    f"{name} entries must be CompatibilityCheckResult."
                )
            if not all(item.phase is phase for item in values):
                raise PolicyContractError(
                    f"{name} contains a result from the wrong phase."
                )
            object.__setattr__(self, name, values)

    @property
    def results(self) -> tuple[CompatibilityCheckResult, ...]:
        return self.pairwise_results + self.global_results

    @property
    def overall_status(self) -> CheckStatus:
        statuses = {item.status for item in self.results}
        if CheckStatus.BLOCKED in statuses:
            return CheckStatus.BLOCKED
        if CheckStatus.FAIL in statuses:
            return CheckStatus.FAIL
        if CheckStatus.REVIEW in statuses:
            return CheckStatus.REVIEW
        if CheckStatus.NOT_RUN in statuses:
            return CheckStatus.NOT_RUN
        return CheckStatus.PASS

    @property
    def decision(self) -> DecisionStatus:
        status = self.overall_status
        if status in {CheckStatus.FAIL, CheckStatus.BLOCKED}:
            return DecisionStatus.REJECT
        if status is CheckStatus.REVIEW:
            return DecisionStatus.REVIEW
        if status is CheckStatus.NOT_RUN:
            return DecisionStatus.DEFER
        return DecisionStatus.ACCEPT

    @property
    def may_enter_runtime_if_enforced(self) -> bool:
        return not any(item.blocks_runtime for item in self.results)

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "overall_status": self.overall_status.value,
                "decision": self.decision.value,
                "may_enter_runtime_if_enforced": self.may_enter_runtime_if_enforced,
                "check_count": len(self.results),
                "pairwise_check_count": len(self.pairwise_results),
                "global_check_count": len(self.global_results),
            }
        )
        return payload


__all__ = [
    "COMPATIBILITY_RULE_CONTRACT_SCHEMA_VERSION",
    "RULE_EVALUATION_CONTEXT_SCHEMA_VERSION",
    "PREDICATE_RESULT_SCHEMA_VERSION",
    "COMPATIBILITY_CHECK_RESULT_SCHEMA_VERSION",
    "COMPATIBILITY_EVALUATION_REPORT_SCHEMA_VERSION",
    "CompatibilityRuleContract",
    "RuleEvaluationContext",
    "PredicateResult",
    "CompatibilityCheckResult",
    "CompatibilityRuleEvaluationReport",
]

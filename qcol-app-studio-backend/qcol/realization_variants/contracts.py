"""WP5 public resolver contracts and explicit reports.

The resolver returns inspectable objects rather than a hidden ``True``/``False``.
Runtime callables remain internal to the WP3 binding plan and are never stored in
these strict-JSON public contracts.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from qcol.compatibility import (
    CompatibilityCheckResult,
    RuleEvaluationContext,
)
from qcol.implementation_bindings import BindingResolutionReport, ResolvedBindingPlan
from qcol.mapping_policies import (
    CheckStatus,
    DecisionStatus,
    EvidenceFreshnessStatus,
    PolicyStatus,
    Severity,
)
from qcol.realization_policies.base import (
    DeclarativeContract,
    PolicyContractError,
    freeze_json,
    require_text,
    require_token,
)

from .enums import (
    RealizationTaskMode,
    ResolutionStatus,
    RuntimeEntryStatus,
    RuntimePath,
)


REALIZATION_CANDIDATE_SCHEMA_VERSION = "qcol-realization-candidate/1.0"
COMPATIBILITY_DIAGNOSTIC_SCHEMA_VERSION = "qcol-compatibility-diagnostic/1.0"
RESOURCE_REPORT_SCHEMA_VERSION = "qcol-realization-resource-report/1.0"
ACCEPTANCE_EVIDENCE_STATUS_SCHEMA_VERSION = "qcol-acceptance-evidence-status/1.0"
RUNTIME_ENTRY_DECISION_SCHEMA_VERSION = "qcol-runtime-entry-decision/1.0"
COMPATIBILITY_REPORT_SCHEMA_VERSION = "qcol-compatibility-report/1.0"
RESOLVED_REALIZATION_VARIANT_SCHEMA_VERSION = "qcol-resolved-realization-variant/1.0"
RUNTIME_DISPATCH_REPORT_SCHEMA_VERSION = "qcol-runtime-dispatch-report/1.0"


@dataclass(frozen=True)
class RealizationCandidate(DeclarativeContract):
    """One exact candidate tuple to be judged by the WP5 resolver."""

    candidate_id: str
    candidate_version: str
    label: str
    task_mode: RealizationTaskMode
    contract_ids: tuple[str, ...]
    rule_context: RuleEvaluationContext
    declared_scale: Mapping[str, Any]
    source_metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = REALIZATION_CANDIDATE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        require_token("candidate_id", self.candidate_id)
        require_token("candidate_version", self.candidate_version)
        require_text("label", self.label)
        if not isinstance(self.task_mode, RealizationTaskMode):
            raise PolicyContractError("task_mode must be RealizationTaskMode.")
        contract_ids = tuple(require_token("contract_ids", str(item)) for item in self.contract_ids)
        if not contract_ids:
            raise PolicyContractError("contract_ids must not be empty.")
        if len(set(contract_ids)) != len(contract_ids):
            raise PolicyContractError("contract_ids must not contain duplicates.")
        object.__setattr__(self, "contract_ids", contract_ids)
        if not isinstance(self.rule_context, RuleEvaluationContext):
            raise PolicyContractError("rule_context must be RuleEvaluationContext.")
        object.__setattr__(
            self,
            "declared_scale",
            freeze_json(self.declared_scale, path="RealizationCandidate.declared_scale"),
        )
        object.__setattr__(
            self,
            "source_metadata",
            freeze_json(self.source_metadata, path="RealizationCandidate.source_metadata"),
        )


@dataclass(frozen=True)
class CompatibilityDiagnostic(DeclarativeContract):
    """Readable scientific diagnostic derived from one rule or sub-check."""

    diagnostic_id: str
    label: str
    status: CheckStatus
    severity: Severity
    source_rule_id: str
    message: str
    failure_code: str | None = None
    evidence: Mapping[str, Any] = field(default_factory=dict)
    suggested_action: str | None = None
    schema_version: str = COMPATIBILITY_DIAGNOSTIC_SCHEMA_VERSION

    def __post_init__(self) -> None:
        require_token("diagnostic_id", self.diagnostic_id)
        require_text("label", self.label)
        require_token("source_rule_id", self.source_rule_id)
        require_text("message", self.message)
        if not isinstance(self.status, CheckStatus):
            raise PolicyContractError("status must be CheckStatus.")
        if not isinstance(self.severity, Severity):
            raise PolicyContractError("severity must be Severity.")
        if self.failure_code is not None:
            require_token("failure_code", self.failure_code)
        if self.suggested_action is not None:
            require_text("suggested_action", self.suggested_action)
        object.__setattr__(
            self,
            "evidence",
            freeze_json(self.evidence, path="CompatibilityDiagnostic.evidence"),
        )


@dataclass(frozen=True)
class ResourceReport(DeclarativeContract):
    report_id: str
    variant_id: str
    status: CheckStatus
    source_rule_id: str
    within_declared_envelope: bool
    estimate: Mapping[str, Any]
    envelope: Mapping[str, Any]
    exceeded_dimensions: tuple[str, ...] = field(default_factory=tuple)
    runtime_blocking: bool = False
    message: str = ""
    suggested_action: str | None = None
    schema_version: str = RESOURCE_REPORT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        require_token("report_id", self.report_id)
        require_token("variant_id", self.variant_id)
        require_token("source_rule_id", self.source_rule_id)
        if not isinstance(self.status, CheckStatus):
            raise PolicyContractError("status must be CheckStatus.")
        if self.message:
            require_text("message", self.message)
        if self.suggested_action is not None:
            require_text("suggested_action", self.suggested_action)
        object.__setattr__(
            self,
            "estimate",
            freeze_json(self.estimate, path="ResourceReport.estimate"),
        )
        object.__setattr__(
            self,
            "envelope",
            freeze_json(self.envelope, path="ResourceReport.envelope"),
        )
        object.__setattr__(
            self,
            "exceeded_dimensions",
            tuple(require_token("exceeded_dimensions", str(item)) for item in self.exceeded_dimensions),
        )


@dataclass(frozen=True)
class AcceptanceEvidenceStatus(DeclarativeContract):
    variant_id: str
    check_status: CheckStatus
    freshness_status: EvidenceFreshnessStatus
    expected_fingerprint: str | None
    observed_fingerprint: str | None
    policy_versions_match: bool
    declared_scale_matches: bool
    required_for_runtime: bool
    required_for_promotion: bool
    promotable_under_wp5: bool
    source_rule_id: str = "composition.acceptance_fingerprint.v1"
    note: str = "WP6 will replace this provisional fixture-level fingerprint handling."
    schema_version: str = ACCEPTANCE_EVIDENCE_STATUS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        require_token("variant_id", self.variant_id)
        require_token("source_rule_id", self.source_rule_id)
        if not isinstance(self.check_status, CheckStatus):
            raise PolicyContractError("check_status must be CheckStatus.")
        if not isinstance(self.freshness_status, EvidenceFreshnessStatus):
            raise PolicyContractError("freshness_status must be EvidenceFreshnessStatus.")
        for name in ("expected_fingerprint", "observed_fingerprint"):
            value = getattr(self, name)
            if value is not None:
                require_token(name, value)
        require_text("note", self.note)

    @property
    def matches_variant(self) -> bool:
        return (
            bool(self.expected_fingerprint)
            and self.expected_fingerprint == self.observed_fingerprint
            and self.policy_versions_match
            and self.declared_scale_matches
        )

    @property
    def current(self) -> bool:
        return self.freshness_status is EvidenceFreshnessStatus.CURRENT

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "matches_variant": self.matches_variant,
                "current": self.current,
            }
        )
        return payload


@dataclass(frozen=True)
class RuntimeEntryDecision(DeclarativeContract):
    status: RuntimeEntryStatus
    path: RuntimePath
    decision: DecisionStatus
    message: str
    blocking_codes: tuple[str, ...] = field(default_factory=tuple)
    review_codes: tuple[str, ...] = field(default_factory=tuple)
    suggested_actions: tuple[str, ...] = field(default_factory=tuple)
    gate_enforced: bool = True
    schema_version: str = RUNTIME_ENTRY_DECISION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.status, RuntimeEntryStatus):
            raise PolicyContractError("status must be RuntimeEntryStatus.")
        if not isinstance(self.path, RuntimePath):
            raise PolicyContractError("path must be RuntimePath.")
        if not isinstance(self.decision, DecisionStatus):
            raise PolicyContractError("decision must be DecisionStatus.")
        require_text("message", self.message)
        for name in ("blocking_codes", "review_codes"):
            values = tuple(require_token(name, str(item)) for item in getattr(self, name))
            object.__setattr__(self, name, values)
        actions = tuple(require_text("suggested_actions", str(item)) for item in self.suggested_actions)
        object.__setattr__(self, "suggested_actions", actions)

    @property
    def permitted(self) -> bool:
        return self.status in {
            RuntimeEntryStatus.EXECUTION_ALLOWED,
            RuntimeEntryStatus.EXECUTION_ALLOWED_WITH_REVIEW,
            RuntimeEntryStatus.ANALYSIS_ONLY_ALLOWED,
            RuntimeEntryStatus.ANALYSIS_ONLY_ALLOWED_WITH_REVIEW,
        }

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload["permitted"] = self.permitted
        return payload


@dataclass(frozen=True)
class CompatibilityReport(DeclarativeContract):
    report_id: str
    variant_id: str
    binding_results: tuple[BindingResolutionReport, ...]
    pairwise_results: tuple[CompatibilityCheckResult, ...]
    global_results: tuple[CompatibilityCheckResult, ...]
    diagnostics: tuple[CompatibilityDiagnostic, ...]
    overall_status: CheckStatus
    decision: DecisionStatus
    runtime_entry: RuntimeEntryDecision
    summary: str
    runtime_gate_enforced: bool = True
    schema_version: str = COMPATIBILITY_REPORT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        require_token("report_id", self.report_id)
        require_token("variant_id", self.variant_id)
        require_text("summary", self.summary)
        for name, expected in (
            ("binding_results", BindingResolutionReport),
            ("pairwise_results", CompatibilityCheckResult),
            ("global_results", CompatibilityCheckResult),
            ("diagnostics", CompatibilityDiagnostic),
        ):
            values = tuple(getattr(self, name))
            if not all(isinstance(item, expected) for item in values):
                raise PolicyContractError(f"{name} entries must be {expected.__name__}.")
            object.__setattr__(self, name, values)
        if not isinstance(self.overall_status, CheckStatus):
            raise PolicyContractError("overall_status must be CheckStatus.")
        if not isinstance(self.decision, DecisionStatus):
            raise PolicyContractError("decision must be DecisionStatus.")
        if not isinstance(self.runtime_entry, RuntimeEntryDecision):
            raise PolicyContractError("runtime_entry must be RuntimeEntryDecision.")

    @property
    def results(self) -> tuple[CompatibilityCheckResult, ...]:
        return self.pairwise_results + self.global_results

    @property
    def failure_codes(self) -> tuple[str, ...]:
        return tuple(
            item.failure_code
            for item in self.results
            if item.failure_code is not None and item.status in {CheckStatus.FAIL, CheckStatus.BLOCKED}
        )

    @property
    def review_codes(self) -> tuple[str, ...]:
        return tuple(
            item.failure_code
            for item in self.results
            if item.failure_code is not None and item.status is CheckStatus.REVIEW
        )

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "failure_codes": list(self.failure_codes),
                "review_codes": list(self.review_codes),
                "check_count": len(self.results),
                "binding_check_count": len(self.binding_results),
                "diagnostic_count": len(self.diagnostics),
            }
        )
        return payload


@dataclass(frozen=True)
class ResolvedRealizationVariant(DeclarativeContract):
    variant_id: str
    variant_version: str
    candidate_id: str
    model_id: str
    task_id: str
    task_mode: RealizationTaskMode
    component_ids: Mapping[str, str]
    contract_ids: tuple[str, ...]
    binding_plan_public: Mapping[str, Any]
    encoding_context_fingerprint: str
    sector_fingerprint: str
    declared_scale: Mapping[str, Any]
    resolution_status: ResolutionStatus
    policy_status: PolicyStatus
    runtime_entry: RuntimeEntryDecision
    compatibility_report_id: str
    resource_report_id: str
    acceptance_evidence_freshness: EvidenceFreshnessStatus
    provisional_variant_fingerprint: str
    fingerprint_authority: str = "pre_wp6_fixture_declaration"
    live_policy_migration_performed: bool = False
    scientific_status_promoted: bool = False
    schema_version: str = RESOLVED_REALIZATION_VARIANT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in (
            "variant_id",
            "variant_version",
            "candidate_id",
            "model_id",
            "task_id",
            "encoding_context_fingerprint",
            "sector_fingerprint",
            "compatibility_report_id",
            "resource_report_id",
            "provisional_variant_fingerprint",
            "fingerprint_authority",
        ):
            require_token(name, getattr(self, name))
        if not isinstance(self.task_mode, RealizationTaskMode):
            raise PolicyContractError("task_mode must be RealizationTaskMode.")
        if not isinstance(self.resolution_status, ResolutionStatus):
            raise PolicyContractError("resolution_status must be ResolutionStatus.")
        if not isinstance(self.policy_status, PolicyStatus):
            raise PolicyContractError("policy_status must be PolicyStatus.")
        if not isinstance(self.runtime_entry, RuntimeEntryDecision):
            raise PolicyContractError("runtime_entry must be RuntimeEntryDecision.")
        if not isinstance(self.acceptance_evidence_freshness, EvidenceFreshnessStatus):
            raise PolicyContractError("acceptance_evidence_freshness must be EvidenceFreshnessStatus.")
        object.__setattr__(
            self,
            "component_ids",
            freeze_json(self.component_ids, path="ResolvedRealizationVariant.component_ids"),
        )
        object.__setattr__(
            self,
            "binding_plan_public",
            freeze_json(self.binding_plan_public, path="ResolvedRealizationVariant.binding_plan_public"),
        )
        object.__setattr__(
            self,
            "declared_scale",
            freeze_json(self.declared_scale, path="ResolvedRealizationVariant.declared_scale"),
        )
        ids = tuple(require_token("contract_ids", str(item)) for item in self.contract_ids)
        object.__setattr__(self, "contract_ids", ids)


@dataclass(frozen=True)
class RuntimeDispatchReport(DeclarativeContract):
    variant_id: str
    entry_status: RuntimeEntryStatus
    requested_path: RuntimePath
    dispatched: bool
    invoked_handler: str | None
    blocked_codes: tuple[str, ...]
    trace: tuple[str, ...]
    result_summary: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = RUNTIME_DISPATCH_REPORT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        require_token("variant_id", self.variant_id)
        if not isinstance(self.entry_status, RuntimeEntryStatus):
            raise PolicyContractError("entry_status must be RuntimeEntryStatus.")
        if not isinstance(self.requested_path, RuntimePath):
            raise PolicyContractError("requested_path must be RuntimePath.")
        if self.invoked_handler is not None:
            require_token("invoked_handler", self.invoked_handler)
        object.__setattr__(
            self,
            "blocked_codes",
            tuple(require_token("blocked_codes", str(item)) for item in self.blocked_codes),
        )
        object.__setattr__(
            self,
            "trace",
            tuple(require_text("trace", str(item)) for item in self.trace),
        )
        object.__setattr__(
            self,
            "result_summary",
            freeze_json(self.result_summary, path="RuntimeDispatchReport.result_summary"),
        )


@dataclass(frozen=True)
class RealizationResolution:
    """Internal WP5 resolution object; callables stay inside ``binding_plan``."""

    candidate: RealizationCandidate
    variant: ResolvedRealizationVariant
    compatibility_report: CompatibilityReport
    resource_report: ResourceReport
    acceptance_evidence: AcceptanceEvidenceStatus
    binding_plan: ResolvedBindingPlan

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "qcol-realization-resolution/1.0",
            "candidate": self.candidate.to_dict(),
            "variant": self.variant.to_dict(),
            "compatibility_report": self.compatibility_report.to_dict(),
            "resource_report": self.resource_report.to_dict(),
            "acceptance_evidence": self.acceptance_evidence.to_dict(),
            "binding_plan": self.binding_plan.to_public_dict(),
            "runtime_callable_payload_withheld": True,
        }


__all__ = [
    "REALIZATION_CANDIDATE_SCHEMA_VERSION",
    "COMPATIBILITY_DIAGNOSTIC_SCHEMA_VERSION",
    "RESOURCE_REPORT_SCHEMA_VERSION",
    "ACCEPTANCE_EVIDENCE_STATUS_SCHEMA_VERSION",
    "RUNTIME_ENTRY_DECISION_SCHEMA_VERSION",
    "COMPATIBILITY_REPORT_SCHEMA_VERSION",
    "RESOLVED_REALIZATION_VARIANT_SCHEMA_VERSION",
    "RUNTIME_DISPATCH_REPORT_SCHEMA_VERSION",
    "RealizationCandidate",
    "CompatibilityDiagnostic",
    "ResourceReport",
    "AcceptanceEvidenceStatus",
    "RuntimeEntryDecision",
    "CompatibilityReport",
    "ResolvedRealizationVariant",
    "RuntimeDispatchReport",
    "RealizationResolution",
]

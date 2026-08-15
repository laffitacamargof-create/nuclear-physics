"""Generic three-gate acceptance harness for QCOL WP7.

The harness classifies evidence produced by mapper, composition, and complete
Model × Task cell tests.  It does not implement scientific algorithms, circuits,
optimizers, or backends.  Numerical thresholds come only from versioned
ToleranceProfile contracts.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import hashlib
import json
from typing import Any, Mapping
from types import MappingProxyType

from qcol.mapping_policies import (
    CheckStatus,
    DecisionStatus,
    GateApplicability,
    Severity,
)
from qcol.realization_policies.base import (
    DeclarativeContract,
    PolicyContractError,
    freeze_json,
    require_text,
    require_token,
)

from .fingerprint import (
    AcceptanceEvidenceFingerprint,
    FingerprintComparisonReport,
    compare_acceptance_fingerprints,
)
from .tolerance_profiles import ToleranceProfile


class AcceptanceGateKind(StrEnum):
    MAPPER_CONFORMANCE = "mapper_conformance"
    COMPOSITION_CONFORMANCE = "composition_conformance"
    CELL_ACCEPTANCE = "cell_acceptance"


class ObservationComparison(StrEnum):
    BOOLEAN_TRUE = "boolean_true"
    LESS_EQUAL_TOLERANCE = "less_equal_tolerance"
    GREATER_EQUAL_TOLERANCE = "greater_equal_tolerance"
    EXACT_EQUAL = "exact_equal"
    STATISTICAL_CONSISTENCY = "statistical_consistency"
    DECLARED_STATUS = "declared_status"


ACCEPTANCE_OBSERVATION_SCHEMA_VERSION = "qcol-acceptance-observation/1.0"
ACCEPTANCE_GATE_CONTRACT_SCHEMA_VERSION = "qcol-acceptance-gate-contract/1.0"
ACCEPTANCE_GATE_REPORT_SCHEMA_VERSION = "qcol-acceptance-gate-report/1.0"
ACCEPTANCE_HARNESS_CASE_SCHEMA_VERSION = "qcol-acceptance-harness-case/1.0"
PROMOTION_DECISION_SCHEMA_VERSION = "qcol-promotion-decision/1.0"
ACCEPTANCE_HARNESS_REPORT_SCHEMA_VERSION = "qcol-acceptance-harness-report/1.0"


@dataclass(frozen=True)
class AcceptanceObservation(DeclarativeContract):
    check_id: str
    label: str
    comparison: ObservationComparison
    observed: Any
    failure_code: str
    message_on_pass: str
    message_on_failure: str
    tolerance_field: str | None = None
    expected: Any = None
    standard_error: float | None = None
    declared_status: CheckStatus | None = None
    evidence: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = ACCEPTANCE_OBSERVATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        require_token("check_id", self.check_id)
        require_text("label", self.label)
        require_token("failure_code", self.failure_code)
        require_text("message_on_pass", self.message_on_pass)
        require_text("message_on_failure", self.message_on_failure)
        if not isinstance(self.comparison, ObservationComparison):
            raise PolicyContractError("comparison must be ObservationComparison.")
        if self.tolerance_field is not None:
            require_token("tolerance_field", self.tolerance_field)
        if self.standard_error is not None and float(self.standard_error) < 0:
            raise PolicyContractError("standard_error must be non-negative.")
        if self.declared_status is not None and not isinstance(self.declared_status, CheckStatus):
            raise PolicyContractError("declared_status must be CheckStatus.")
        if self.comparison is ObservationComparison.DECLARED_STATUS and self.declared_status is None:
            raise PolicyContractError("DECLARED_STATUS observations require declared_status.")
        object.__setattr__(self, "observed", freeze_json(self.observed, path="AcceptanceObservation.observed"))
        object.__setattr__(self, "expected", freeze_json(self.expected, path="AcceptanceObservation.expected"))
        object.__setattr__(self, "evidence", freeze_json(self.evidence, path="AcceptanceObservation.evidence"))


@dataclass(frozen=True)
class AcceptanceGateContract(DeclarativeContract):
    gate_id: str
    gate_version: str
    kind: AcceptanceGateKind
    label: str
    tolerance_profile_id: str
    required_check_ids: tuple[str, ...]
    purpose: str
    schema_version: str = ACCEPTANCE_GATE_CONTRACT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        require_token("gate_id", self.gate_id)
        require_token("gate_version", self.gate_version)
        require_token("tolerance_profile_id", self.tolerance_profile_id)
        require_text("label", self.label)
        require_text("purpose", self.purpose)
        if not isinstance(self.kind, AcceptanceGateKind):
            raise PolicyContractError("kind must be AcceptanceGateKind.")
        checks = tuple(require_token("required_check_ids", str(item)) for item in self.required_check_ids)
        if not checks or len(set(checks)) != len(checks):
            raise PolicyContractError("required_check_ids must be non-empty and unique.")
        object.__setattr__(self, "required_check_ids", checks)


@dataclass(frozen=True)
class ObservationResult(DeclarativeContract):
    check_id: str
    label: str
    status: CheckStatus
    severity: Severity
    failure_code: str | None
    observed: Any
    threshold: Any
    message: str
    evidence: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = "qcol-acceptance-observation-result/1.0"

    def __post_init__(self) -> None:
        require_token("check_id", self.check_id)
        require_text("label", self.label)
        require_text("message", self.message)
        if not isinstance(self.status, CheckStatus):
            raise PolicyContractError("status must be CheckStatus.")
        if not isinstance(self.severity, Severity):
            raise PolicyContractError("severity must be Severity.")
        if self.failure_code is not None:
            require_token("failure_code", self.failure_code)
        object.__setattr__(self, "observed", freeze_json(self.observed, path="ObservationResult.observed"))
        object.__setattr__(self, "threshold", freeze_json(self.threshold, path="ObservationResult.threshold"))
        object.__setattr__(self, "evidence", freeze_json(self.evidence, path="ObservationResult.evidence"))


@dataclass(frozen=True)
class AcceptanceGateReport(DeclarativeContract):
    report_id: str
    gate: AcceptanceGateContract
    applicability: GateApplicability
    status: CheckStatus
    tolerance_profile_id: str
    observation_results: tuple[ObservationResult, ...]
    failure_codes: tuple[str, ...]
    review_codes: tuple[str, ...]
    summary: str
    schema_version: str = ACCEPTANCE_GATE_REPORT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        require_token("report_id", self.report_id)
        require_token("tolerance_profile_id", self.tolerance_profile_id)
        require_text("summary", self.summary)
        if not isinstance(self.gate, AcceptanceGateContract):
            raise PolicyContractError("gate must be AcceptanceGateContract.")
        if not isinstance(self.applicability, GateApplicability):
            raise PolicyContractError("applicability must be GateApplicability.")
        if not isinstance(self.status, CheckStatus):
            raise PolicyContractError("status must be CheckStatus.")
        results = tuple(self.observation_results)
        if not all(isinstance(item, ObservationResult) for item in results):
            raise PolicyContractError("observation_results must contain ObservationResult values.")
        object.__setattr__(self, "observation_results", results)
        object.__setattr__(self, "failure_codes", tuple(require_token("failure_codes", str(item)) for item in self.failure_codes))
        object.__setattr__(self, "review_codes", tuple(require_token("review_codes", str(item)) for item in self.review_codes))


@dataclass(frozen=True)
class AcceptanceHarnessCase(DeclarativeContract):
    case_id: str
    case_version: str
    label: str
    baseline_variant_id: str
    expected_baseline_status: str
    gate_applicability: Mapping[str, str]
    observations: Mapping[str, tuple[AcceptanceObservation, ...]]
    expected_fingerprint: AcceptanceEvidenceFingerprint | None
    observed_fingerprint: AcceptanceEvidenceFingerprint | None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = ACCEPTANCE_HARNESS_CASE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in ("case_id", "case_version", "baseline_variant_id", "expected_baseline_status"):
            require_token(name, getattr(self, name))
        require_text("label", self.label)
        applicability = {require_token("gate_kind", str(k)): require_token("gate_applicability", str(v)) for k, v in self.gate_applicability.items()}
        object.__setattr__(self, "gate_applicability", freeze_json(applicability, path="AcceptanceHarnessCase.gate_applicability"))
        rows: dict[str, tuple[AcceptanceObservation, ...]] = {}
        for key, values in self.observations.items():
            token = require_token("observation_gate", str(key))
            values_tuple = tuple(values)
            if not all(isinstance(item, AcceptanceObservation) for item in values_tuple):
                raise PolicyContractError("observations must contain AcceptanceObservation values.")
            rows[token] = values_tuple
        object.__setattr__(self, "observations", MappingProxyType(rows))
        if self.expected_fingerprint is not None and not isinstance(self.expected_fingerprint, AcceptanceEvidenceFingerprint):
            raise PolicyContractError("expected_fingerprint has the wrong type.")
        if self.observed_fingerprint is not None and not isinstance(self.observed_fingerprint, AcceptanceEvidenceFingerprint):
            raise PolicyContractError("observed_fingerprint has the wrong type.")
        object.__setattr__(self, "metadata", freeze_json(self.metadata, path="AcceptanceHarnessCase.metadata"))


@dataclass(frozen=True)
class PromotionDecision(DeclarativeContract):
    decision: DecisionStatus
    promotion_ready: bool
    required_gate_ids: tuple[str, ...]
    passed_gate_ids: tuple[str, ...]
    non_applicable_gate_ids: tuple[str, ...]
    blocking_codes: tuple[str, ...]
    review_codes: tuple[str, ...]
    fingerprint_match: bool
    preserved_baseline_status: str
    message: str
    schema_version: str = PROMOTION_DECISION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.decision, DecisionStatus):
            raise PolicyContractError("decision must be DecisionStatus.")
        require_token("preserved_baseline_status", self.preserved_baseline_status)
        require_text("message", self.message)
        for name in (
            "required_gate_ids", "passed_gate_ids", "non_applicable_gate_ids",
            "blocking_codes", "review_codes",
        ):
            object.__setattr__(self, name, tuple(require_token(name, str(item)) for item in getattr(self, name)))


@dataclass(frozen=True)
class AcceptanceHarnessReport(DeclarativeContract):
    report_id: str
    case_id: str
    gate_reports: tuple[AcceptanceGateReport, ...]
    fingerprint_comparison: FingerprintComparisonReport | None
    promotion: PromotionDecision
    tolerance_profile_fingerprints: Mapping[str, str]
    harness_version: str = "1.0.0"
    schema_version: str = ACCEPTANCE_HARNESS_REPORT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        require_token("report_id", self.report_id)
        require_token("case_id", self.case_id)
        require_token("harness_version", self.harness_version)
        reports = tuple(self.gate_reports)
        if len(reports) != 3 or not all(isinstance(item, AcceptanceGateReport) for item in reports):
            raise PolicyContractError("gate_reports must contain exactly three AcceptanceGateReport values.")
        object.__setattr__(self, "gate_reports", reports)
        if self.fingerprint_comparison is not None and not isinstance(self.fingerprint_comparison, FingerprintComparisonReport):
            raise PolicyContractError("fingerprint_comparison has the wrong type.")
        if not isinstance(self.promotion, PromotionDecision):
            raise PolicyContractError("promotion must be PromotionDecision.")
        object.__setattr__(self, "tolerance_profile_fingerprints", freeze_json(self.tolerance_profile_fingerprints, path="AcceptanceHarnessReport.tolerance_profile_fingerprints"))


class ToleranceProfileRegistry:
    """Exact versioned profile lookup; no similar-ID fallback is permitted."""

    def __init__(self, *, registry_id: str, registry_version: str) -> None:
        self.registry_id = require_token("registry_id", registry_id)
        self.registry_version = require_token("registry_version", registry_version)
        self._profiles: dict[str, ToleranceProfile] = {}

    def register(self, profile: ToleranceProfile, *, replace: bool = False) -> None:
        if not isinstance(profile, ToleranceProfile):
            raise TypeError("profile must be ToleranceProfile.")
        if profile.profile_id in self._profiles and not replace:
            raise ValueError(f"Tolerance profile {profile.profile_id!r} is already registered.")
        self._profiles[profile.profile_id] = profile

    def get(self, profile_id: str) -> ToleranceProfile:
        try:
            return self._profiles[str(profile_id)]
        except KeyError as exc:
            raise KeyError(f"Unknown exact tolerance profile {profile_id!r}; no fallback is allowed.") from exc

    def public_catalog(self) -> dict[str, Any]:
        return {
            "schema_version": "qcol-tolerance-profile-registry/1.0",
            "registry_id": self.registry_id,
            "registry_version": self.registry_version,
            "profiles": [self._profiles[key].to_dict() for key in sorted(self._profiles)],
            "fingerprints": {key: self._profiles[key].fingerprint() for key in sorted(self._profiles)},
            "silent_fallback_allowed": False,
        }


class GenericThreeGateAcceptanceHarness:
    def __init__(
        self,
        *,
        gate_contracts: Mapping[AcceptanceGateKind, AcceptanceGateContract],
        tolerance_registry: ToleranceProfileRegistry,
        harness_version: str = "1.0.0",
    ) -> None:
        required = set(AcceptanceGateKind)
        if set(gate_contracts) != required:
            raise ValueError("gate_contracts must contain exactly mapper, composition, and cell gates.")
        self.gate_contracts = dict(gate_contracts)
        self.tolerance_registry = tolerance_registry
        self.harness_version = require_token("harness_version", harness_version)

    @staticmethod
    def _severity(status: CheckStatus) -> Severity:
        if status in {CheckStatus.FAIL, CheckStatus.BLOCKED}:
            return Severity.ERROR
        if status is CheckStatus.REVIEW:
            return Severity.REVIEW
        return Severity.INFO

    def _evaluate_observation(self, observation: AcceptanceObservation, profile: ToleranceProfile) -> ObservationResult:
        threshold: Any = None
        status = CheckStatus.FAIL
        comparison = observation.comparison
        observed = observation.observed
        if comparison is ObservationComparison.DECLARED_STATUS:
            status = observation.declared_status or CheckStatus.FAIL
        elif comparison is ObservationComparison.BOOLEAN_TRUE:
            threshold = True
            status = CheckStatus.PASS if observed is True else CheckStatus.FAIL
        elif comparison is ObservationComparison.EXACT_EQUAL:
            threshold = observation.expected
            status = CheckStatus.PASS if observed == observation.expected else CheckStatus.FAIL
        elif comparison is ObservationComparison.LESS_EQUAL_TOLERANCE:
            if observation.tolerance_field is None:
                raise PolicyContractError("LESS_EQUAL_TOLERANCE requires tolerance_field.")
            threshold = getattr(profile, observation.tolerance_field)
            status = CheckStatus.PASS if float(observed) <= float(threshold) else CheckStatus.FAIL
        elif comparison is ObservationComparison.GREATER_EQUAL_TOLERANCE:
            if observation.tolerance_field is None:
                raise PolicyContractError("GREATER_EQUAL_TOLERANCE requires tolerance_field.")
            threshold = getattr(profile, observation.tolerance_field)
            status = CheckStatus.PASS if float(observed) >= float(threshold) else CheckStatus.FAIL
        elif comparison is ObservationComparison.STATISTICAL_CONSISTENCY:
            standard_error = float(observation.standard_error or 0.0)
            threshold = max(
                profile.statistical_sigma_multiplier * standard_error,
                profile.absolute_numerical_floor,
            )
            status = CheckStatus.PASS if float(observed) <= float(threshold) else CheckStatus.FAIL
        message = observation.message_on_pass if status is CheckStatus.PASS else observation.message_on_failure
        failure_code = None if status in {CheckStatus.PASS, CheckStatus.NOT_APPLICABLE} else observation.failure_code
        return ObservationResult(
            check_id=observation.check_id,
            label=observation.label,
            status=status,
            severity=self._severity(status),
            failure_code=failure_code,
            observed=observed,
            threshold=threshold,
            message=message,
            evidence=observation.evidence,
        )

    def _gate_report(
        self,
        *,
        gate: AcceptanceGateContract,
        applicability: GateApplicability,
        observations: tuple[AcceptanceObservation, ...],
    ) -> AcceptanceGateReport:
        profile = self.tolerance_registry.get(gate.tolerance_profile_id)
        if applicability is GateApplicability.NOT_APPLICABLE:
            status = CheckStatus.NOT_APPLICABLE
            results: tuple[ObservationResult, ...] = ()
            summary = f"{gate.label} is not applicable to this task mode."
        elif applicability is GateApplicability.BLOCKED:
            status = CheckStatus.BLOCKED
            results = ()
            summary = f"{gate.label} is blocked because an upstream required gate did not pass."
        else:
            observed_ids = {item.check_id for item in observations}
            missing = [item for item in gate.required_check_ids if item not in observed_ids]
            evaluated = [self._evaluate_observation(item, profile) for item in observations]
            for check_id in missing:
                evaluated.append(
                    ObservationResult(
                        check_id=check_id,
                        label=check_id.replace("_", " ").title(),
                        status=CheckStatus.BLOCKED,
                        severity=Severity.ERROR,
                        failure_code="GATE_EVIDENCE_INCOMPLETE",
                        observed=None,
                        threshold=None,
                        message="Required gate evidence was not supplied.",
                    )
                )
            results = tuple(evaluated)
            statuses = {item.status for item in results}
            if CheckStatus.FAIL in statuses or CheckStatus.BLOCKED in statuses:
                status = CheckStatus.FAIL
            elif CheckStatus.REVIEW in statuses:
                status = CheckStatus.REVIEW
            elif results and all(item.status is CheckStatus.PASS for item in results):
                status = CheckStatus.PASS
            else:
                status = CheckStatus.NOT_RUN
            summary = (
                f"{gate.label} passed all required checks."
                if status is CheckStatus.PASS
                else f"{gate.label} requires review."
                if status is CheckStatus.REVIEW
                else f"{gate.label} did not pass."
            )
        failures = tuple(item.failure_code for item in results if item.failure_code and item.status in {CheckStatus.FAIL, CheckStatus.BLOCKED})
        reviews = tuple(item.failure_code for item in results if item.failure_code and item.status is CheckStatus.REVIEW)
        seed = {
            "gate": gate.to_dict(),
            "applicability": applicability.value,
            "results": [item.to_dict() for item in results],
        }
        report_id = f"gate-report-{hashlib.sha256(json.dumps(seed, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()[:16]}"
        return AcceptanceGateReport(
            report_id=report_id,
            gate=gate,
            applicability=applicability,
            status=status,
            tolerance_profile_id=profile.profile_id,
            observation_results=results,
            failure_codes=failures,
            review_codes=reviews,
            summary=summary,
        )

    def run(self, case: AcceptanceHarnessCase) -> AcceptanceHarnessReport:
        if not isinstance(case, AcceptanceHarnessCase):
            raise TypeError("case must be AcceptanceHarnessCase.")
        reports: list[AcceptanceGateReport] = []
        upstream_failed = False
        for kind in (
            AcceptanceGateKind.MAPPER_CONFORMANCE,
            AcceptanceGateKind.COMPOSITION_CONFORMANCE,
            AcceptanceGateKind.CELL_ACCEPTANCE,
        ):
            gate = self.gate_contracts[kind]
            applicability = GateApplicability(case.gate_applicability.get(kind.value, GateApplicability.REQUIRED.value))
            if upstream_failed and applicability is GateApplicability.REQUIRED:
                applicability = GateApplicability.BLOCKED
            report = self._gate_report(
                gate=gate,
                applicability=applicability,
                observations=tuple(case.observations.get(kind.value, ())),
            )
            reports.append(report)
            if applicability is GateApplicability.REQUIRED and report.status in {CheckStatus.FAIL, CheckStatus.BLOCKED}:
                upstream_failed = True

        comparison = None
        if case.expected_fingerprint is not None and case.observed_fingerprint is not None:
            comparison = compare_acceptance_fingerprints(case.expected_fingerprint, case.observed_fingerprint)
        fingerprint_match = bool(comparison and comparison.exact_match)
        required_reports = [item for item in reports if item.applicability is GateApplicability.REQUIRED]
        required_pass = all(item.status is CheckStatus.PASS for item in required_reports)
        reviews = tuple(code for item in reports for code in item.review_codes)
        blocks = tuple(code for item in reports for code in item.failure_codes)
        if comparison is not None and not comparison.exact_match:
            blocks = (*blocks, "ACCEPTANCE_EVIDENCE_STALE")
        promotion_ready = required_pass and fingerprint_match and not blocks and not reviews
        if promotion_ready:
            decision = DecisionStatus.ACCEPT
            message = "All required gates passed and the acceptance evidence fingerprint exactly matches the resolved realization."
        elif blocks:
            decision = DecisionStatus.REJECT
            message = "Promotion is rejected because a required gate or exact evidence-fingerprint check failed."
        elif reviews:
            decision = DecisionStatus.REVIEW
            message = "Promotion remains under review; no scientific status is changed."
        else:
            decision = DecisionStatus.DEFER
            message = "Promotion is deferred because complete current acceptance evidence is unavailable."
        promotion = PromotionDecision(
            decision=decision,
            promotion_ready=promotion_ready,
            required_gate_ids=tuple(item.gate.gate_id for item in required_reports),
            passed_gate_ids=tuple(item.gate.gate_id for item in reports if item.status is CheckStatus.PASS),
            non_applicable_gate_ids=tuple(item.gate.gate_id for item in reports if item.applicability is GateApplicability.NOT_APPLICABLE),
            blocking_codes=tuple(dict.fromkeys(blocks)),
            review_codes=tuple(dict.fromkeys(reviews)),
            fingerprint_match=fingerprint_match,
            preserved_baseline_status=case.expected_baseline_status,
            message=message,
        )
        seed = {
            "case": case.to_dict(),
            "gates": [item.to_dict() for item in reports],
            "fingerprint": None if comparison is None else comparison.to_dict(),
            "promotion": promotion.to_dict(),
        }
        report_id = f"acceptance-report-{hashlib.sha256(json.dumps(seed, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()[:16]}"
        profile_fingerprints = {
            item.gate.tolerance_profile_id: self.tolerance_registry.get(item.gate.tolerance_profile_id).fingerprint()
            for item in reports
        }
        return AcceptanceHarnessReport(
            report_id=report_id,
            case_id=case.case_id,
            gate_reports=tuple(reports),
            fingerprint_comparison=comparison,
            promotion=promotion,
            tolerance_profile_fingerprints=profile_fingerprints,
            harness_version=self.harness_version,
        )


__all__ = [
    "AcceptanceGateKind",
    "ObservationComparison",
    "AcceptanceObservation",
    "AcceptanceGateContract",
    "ObservationResult",
    "AcceptanceGateReport",
    "AcceptanceHarnessCase",
    "PromotionDecision",
    "AcceptanceHarnessReport",
    "ToleranceProfileRegistry",
    "GenericThreeGateAcceptanceHarness",
]

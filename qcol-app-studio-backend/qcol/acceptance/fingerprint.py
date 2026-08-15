"""Exact acceptance-evidence fingerprints for QCOL WP6.

An acceptance claim belongs to one exact resolved realization, one exact set of
versions/conventions, and one declared problem scale.  This module is
intentionally dependency-light and stores only strict-JSON declarations.  It
never stores runtime callables or scientific objects.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from typing import Any, Iterable, Mapping

from qcol.mapping_policies import CheckStatus, DecisionStatus, EvidenceFreshnessStatus
from qcol.realization_policies.base import (
    DeclarativeContract,
    PolicyContractError,
    contract_fingerprint,
    freeze_json,
    json_contract_value,
    require_text,
    require_token,
)


COMPONENT_EVIDENCE_IDENTITY_SCHEMA_VERSION = "qcol-component-evidence-identity/1.0"
BINDING_EVIDENCE_IDENTITY_SCHEMA_VERSION = "qcol-binding-evidence-identity/1.0"
DEPENDENCY_FINGERPRINT_SCHEMA_VERSION = "qcol-dependency-fingerprint/1.0"
DECLARED_SCALE_CONTRACT_SCHEMA_VERSION = "qcol-declared-scale-contract/1.0"
ACCEPTANCE_EVIDENCE_FINGERPRINT_SCHEMA_VERSION = "qcol-acceptance-evidence-fingerprint/1.0"
ACCEPTANCE_EVIDENCE_RECORD_SCHEMA_VERSION = "qcol-acceptance-evidence-record/1.0"
FINGERPRINT_DIFFERENCE_SCHEMA_VERSION = "qcol-fingerprint-difference/1.0"
FINGERPRINT_COMPARISON_REPORT_SCHEMA_VERSION = "qcol-fingerprint-comparison-report/1.0"
EVIDENCE_FRESHNESS_DECISION_SCHEMA_VERSION = "qcol-evidence-freshness-decision/1.0"

ACCEPTANCE_EVIDENCE_STALE = "ACCEPTANCE_EVIDENCE_STALE"


def _sha256(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            json_contract_value(payload),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True)
class ComponentEvidenceIdentity(DeclarativeContract):
    """Exact identity of one contract/policy component in an acceptance claim."""

    role: str
    component_id: str
    component_version: str
    snapshot_fingerprint: str
    convention_id: str | None = None
    applicability: str = "required"
    schema_version: str = COMPONENT_EVIDENCE_IDENTITY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in ("role", "component_id", "component_version", "snapshot_fingerprint", "applicability"):
            require_token(name, getattr(self, name))
        if len(self.snapshot_fingerprint) != 64:
            raise PolicyContractError("snapshot_fingerprint must be a SHA-256 hex digest.")
        if self.convention_id is not None:
            require_token("convention_id", self.convention_id)


@dataclass(frozen=True)
class BindingEvidenceIdentity(DeclarativeContract):
    """Public reproducibility identity of one resolved implementation binding."""

    role: str
    binding_id: str
    binding_version: str
    provider: str
    implementation_version: str
    convention_id: str
    source_revision: str
    schema_version: str = BINDING_EVIDENCE_IDENTITY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in (
            "role", "binding_id", "binding_version", "provider",
            "implementation_version", "convention_id", "source_revision",
        ):
            require_token(name, getattr(self, name))


@dataclass(frozen=True)
class DependencyFingerprint(DeclarativeContract):
    """Exact dependency versions included in an acceptance record."""

    dependency_set_id: str
    dependency_set_version: str
    versions: Mapping[str, str]
    schema_version: str = DEPENDENCY_FINGERPRINT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        require_token("dependency_set_id", self.dependency_set_id)
        require_token("dependency_set_version", self.dependency_set_version)
        versions = {require_token("dependency_name", str(k)): require_token("dependency_version", str(v)) for k, v in self.versions.items()}
        if not versions:
            raise PolicyContractError("DependencyFingerprint.versions must not be empty.")
        object.__setattr__(self, "versions", freeze_json(versions, path="DependencyFingerprint.versions"))

    @property
    def digest(self) -> str:
        return _sha256(super().to_dict())

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload["fingerprint"] = self.digest
        return payload


@dataclass(frozen=True)
class DeclaredScaleContract(DeclarativeContract):
    """Exact scale at which evidence was generated and may be claimed."""

    scale_id: str
    scale_version: str
    dimensions: Mapping[str, Any]
    scope_statement: str
    schema_version: str = DECLARED_SCALE_CONTRACT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        require_token("scale_id", self.scale_id)
        require_token("scale_version", self.scale_version)
        require_text("scope_statement", self.scope_statement)
        if not self.dimensions:
            raise PolicyContractError("DeclaredScaleContract.dimensions must not be empty.")
        object.__setattr__(self, "dimensions", freeze_json(self.dimensions, path="DeclaredScaleContract.dimensions"))

    @property
    def digest(self) -> str:
        return _sha256(super().to_dict())

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload["fingerprint"] = self.digest
        return payload


@dataclass(frozen=True)
class AcceptanceEvidenceFingerprint(DeclarativeContract):
    """Exact scientific identity to which one acceptance claim is bound."""

    fingerprint_id: str
    fingerprint_version: str
    source_problem_fingerprint: str

    model_contract: ComponentEvidenceIdentity
    task_contract: ComponentEvidenceIdentity
    mapping_policy: ComponentEvidenceIdentity
    mode_ordering: ComponentEvidenceIdentity
    encoding_context: ComponentEvidenceIdentity
    sector_profiles: tuple[ComponentEvidenceIdentity, ...]
    state_preparation_policy: ComponentEvidenceIdentity
    ansatz_policy: ComponentEvidenceIdentity
    measurement_policy: ComponentEvidenceIdentity
    reference_policy: ComponentEvidenceIdentity
    verification_policy: ComponentEvidenceIdentity
    tolerance_profile: ComponentEvidenceIdentity

    implementation_bindings: tuple[BindingEvidenceIdentity, ...]
    dependencies: DependencyFingerprint
    declared_scale: DeclaredScaleContract
    schema_version: str = ACCEPTANCE_EVIDENCE_FINGERPRINT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        require_token("fingerprint_id", self.fingerprint_id)
        require_token("fingerprint_version", self.fingerprint_version)
        require_token("source_problem_fingerprint", self.source_problem_fingerprint)
        for name in (
            "model_contract", "task_contract", "mapping_policy", "mode_ordering",
            "encoding_context", "state_preparation_policy", "ansatz_policy",
            "measurement_policy", "reference_policy", "verification_policy",
            "tolerance_profile",
        ):
            if not isinstance(getattr(self, name), ComponentEvidenceIdentity):
                raise PolicyContractError(f"{name} must be ComponentEvidenceIdentity.")
        sectors = tuple(self.sector_profiles)
        if not sectors or not all(isinstance(item, ComponentEvidenceIdentity) for item in sectors):
            raise PolicyContractError("sector_profiles must contain at least one ComponentEvidenceIdentity.")
        roles = [item.role for item in sectors]
        if len(set(roles)) != len(roles):
            raise PolicyContractError("sector_profiles must use unique role tokens.")
        object.__setattr__(self, "sector_profiles", sectors)
        bindings = tuple(self.implementation_bindings)
        if not all(isinstance(item, BindingEvidenceIdentity) for item in bindings):
            raise PolicyContractError("implementation_bindings must contain BindingEvidenceIdentity values.")
        binding_keys = [(item.role, item.binding_id) for item in bindings]
        if len(set(binding_keys)) != len(binding_keys):
            raise PolicyContractError("implementation_bindings must not contain duplicate role/binding pairs.")
        object.__setattr__(self, "implementation_bindings", bindings)
        if not isinstance(self.dependencies, DependencyFingerprint):
            raise PolicyContractError("dependencies must be DependencyFingerprint.")
        if not isinstance(self.declared_scale, DeclaredScaleContract):
            raise PolicyContractError("declared_scale must be DeclaredScaleContract.")

    def canonical_payload(self) -> dict[str, Any]:
        return super().to_dict()

    @property
    def digest(self) -> str:
        return _sha256(self.canonical_payload())

    def to_dict(self) -> dict[str, Any]:
        payload = self.canonical_payload()
        payload["fingerprint"] = self.digest
        payload["fingerprint_authority"] = "wp6.exact_resolved_composition_and_scale.v1"
        return payload


@dataclass(frozen=True)
class AcceptanceEvidenceRecord(DeclarativeContract):
    record_id: str
    record_version: str
    acceptance_suite_id: str
    resolved_variant_id: str
    evidence_fingerprint: AcceptanceEvidenceFingerprint
    accepted_claim: str
    gate_report_ids: tuple[str, ...]
    evidence_archive_id: str
    created_by: str
    status: str = "accepted"
    schema_version: str = ACCEPTANCE_EVIDENCE_RECORD_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in (
            "record_id", "record_version", "acceptance_suite_id", "resolved_variant_id",
            "evidence_archive_id", "created_by", "status",
        ):
            require_token(name, getattr(self, name))
        require_text("accepted_claim", self.accepted_claim)
        if not isinstance(self.evidence_fingerprint, AcceptanceEvidenceFingerprint):
            raise PolicyContractError("evidence_fingerprint must be AcceptanceEvidenceFingerprint.")
        gate_ids = tuple(require_token("gate_report_ids", str(item)) for item in self.gate_report_ids)
        object.__setattr__(self, "gate_report_ids", gate_ids)


@dataclass(frozen=True)
class FingerprintDifference(DeclarativeContract):
    path: str
    expected: Any
    observed: Any
    category: str
    schema_version: str = FINGERPRINT_DIFFERENCE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        require_text("path", self.path)
        require_token("category", self.category)
        object.__setattr__(self, "expected", freeze_json(self.expected, path="FingerprintDifference.expected"))
        object.__setattr__(self, "observed", freeze_json(self.observed, path="FingerprintDifference.observed"))


@dataclass(frozen=True)
class EvidenceFreshnessDecision(DeclarativeContract):
    freshness_status: EvidenceFreshnessStatus
    check_status: CheckStatus
    decision: DecisionStatus
    failure_code: str | None
    promotion_allowed: bool
    runtime_entry_allowed_when_current_evidence_required: bool
    message: str
    suggested_action: str | None = None
    schema_version: str = EVIDENCE_FRESHNESS_DECISION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.freshness_status, EvidenceFreshnessStatus):
            raise PolicyContractError("freshness_status must be EvidenceFreshnessStatus.")
        if not isinstance(self.check_status, CheckStatus):
            raise PolicyContractError("check_status must be CheckStatus.")
        if not isinstance(self.decision, DecisionStatus):
            raise PolicyContractError("decision must be DecisionStatus.")
        if self.failure_code is not None:
            require_token("failure_code", self.failure_code)
        require_text("message", self.message)
        if self.suggested_action is not None:
            require_text("suggested_action", self.suggested_action)


@dataclass(frozen=True)
class FingerprintComparisonReport(DeclarativeContract):
    report_id: str
    expected_fingerprint: str
    observed_fingerprint: str
    exact_match: bool
    differences: tuple[FingerprintDifference, ...]
    changed_categories: tuple[str, ...]
    decision: EvidenceFreshnessDecision
    schema_version: str = FINGERPRINT_COMPARISON_REPORT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in ("report_id", "expected_fingerprint", "observed_fingerprint"):
            require_token(name, getattr(self, name))
        differences = tuple(self.differences)
        if not all(isinstance(item, FingerprintDifference) for item in differences):
            raise PolicyContractError("differences must contain FingerprintDifference values.")
        object.__setattr__(self, "differences", differences)
        categories = tuple(require_token("changed_categories", str(item)) for item in self.changed_categories)
        object.__setattr__(self, "changed_categories", categories)
        if not isinstance(self.decision, EvidenceFreshnessDecision):
            raise PolicyContractError("decision must be EvidenceFreshnessDecision.")
        if self.exact_match != (not differences and self.expected_fingerprint == self.observed_fingerprint):
            raise PolicyContractError("exact_match is inconsistent with differences/fingerprints.")


def _strip_generated(payload: Mapping[str, Any]) -> dict[str, Any]:
    result = json.loads(json.dumps(json_contract_value(payload), sort_keys=True, allow_nan=False))
    result.pop("fingerprint", None)
    result.pop("fingerprint_authority", None)
    return result


def _diff_values(expected: Any, observed: Any, *, path: str = "root") -> list[FingerprintDifference]:
    out: list[FingerprintDifference] = []
    if isinstance(expected, Mapping) and isinstance(observed, Mapping):
        keys = sorted(set(expected) | set(observed))
        for key in keys:
            child = f"{path}.{key}"
            if key not in expected:
                out.append(FingerprintDifference(child, None, observed[key], _category(child)))
            elif key not in observed:
                out.append(FingerprintDifference(child, expected[key], None, _category(child)))
            else:
                out.extend(_diff_values(expected[key], observed[key], path=child))
        return out
    if isinstance(expected, list) and isinstance(observed, list):
        max_len = max(len(expected), len(observed))
        for index in range(max_len):
            child = f"{path}[{index}]"
            if index >= len(expected):
                out.append(FingerprintDifference(child, None, observed[index], _category(child)))
            elif index >= len(observed):
                out.append(FingerprintDifference(child, expected[index], None, _category(child)))
            else:
                out.extend(_diff_values(expected[index], observed[index], path=child))
        return out
    if expected != observed:
        out.append(FingerprintDifference(path, expected, observed, _category(path)))
    return out


def _category(path: str) -> str:
    for token, category in (
        ("model_contract", "model"),
        ("task_contract", "task"),
        ("mapping_policy", "mapping"),
        ("mode_ordering", "ordering"),
        ("encoding_context", "encoding_context"),
        ("sector_profiles", "sector"),
        ("state_preparation_policy", "state_preparation"),
        ("ansatz_policy", "ansatz"),
        ("measurement_policy", "measurement"),
        ("reference_policy", "reference"),
        ("verification_policy", "verification"),
        ("tolerance_profile", "tolerance"),
        ("implementation_bindings", "implementation_binding"),
        ("dependencies", "dependency"),
        ("declared_scale", "declared_scale"),
        ("source_problem_fingerprint", "source_problem"),
    ):
        if token in path:
            return category
    return "other"


def compare_acceptance_fingerprints(
    expected: AcceptanceEvidenceFingerprint,
    observed: AcceptanceEvidenceFingerprint,
) -> FingerprintComparisonReport:
    if not isinstance(expected, AcceptanceEvidenceFingerprint) or not isinstance(observed, AcceptanceEvidenceFingerprint):
        raise TypeError("expected and observed must be AcceptanceEvidenceFingerprint.")
    differences = tuple(
        _diff_values(
            _strip_generated(expected.to_dict()),
            _strip_generated(observed.to_dict()),
        )
    )
    exact = expected.digest == observed.digest and not differences
    categories = tuple(sorted({item.category for item in differences}))
    if exact:
        decision = EvidenceFreshnessDecision(
            freshness_status=EvidenceFreshnessStatus.CURRENT,
            check_status=CheckStatus.PASS,
            decision=DecisionStatus.ACCEPT,
            failure_code=None,
            promotion_allowed=True,
            runtime_entry_allowed_when_current_evidence_required=True,
            message="The acceptance evidence matches the exact resolved composition, dependencies, and declared scale.",
        )
    else:
        decision = EvidenceFreshnessDecision(
            freshness_status=EvidenceFreshnessStatus.STALE,
            check_status=CheckStatus.FAIL,
            decision=DecisionStatus.REJECT,
            failure_code=ACCEPTANCE_EVIDENCE_STALE,
            promotion_allowed=False,
            runtime_entry_allowed_when_current_evidence_required=False,
            message=(
                "The acceptance evidence belongs to a different resolved composition, dependency set, or declared scale."
            ),
            suggested_action="Re-run the required acceptance gates for the exact current realization and archive a new evidence record.",
        )
    report_seed = {
        "expected": expected.digest,
        "observed": observed.digest,
        "differences": [item.to_dict() for item in differences],
    }
    return FingerprintComparisonReport(
        report_id="fingerprint-comparison-" + _sha256(report_seed)[:16],
        expected_fingerprint=expected.digest,
        observed_fingerprint=observed.digest,
        exact_match=exact,
        differences=differences,
        changed_categories=categories,
        decision=decision,
    )


def component_identity(
    *,
    role: str,
    component_id: str,
    component_version: str,
    snapshot: Mapping[str, Any],
    convention_id: str | None = None,
    applicability: str = "required",
) -> ComponentEvidenceIdentity:
    return ComponentEvidenceIdentity(
        role=role,
        component_id=component_id,
        component_version=component_version,
        snapshot_fingerprint=contract_fingerprint(snapshot),
        convention_id=convention_id,
        applicability=applicability,
    )


def binding_identities_from_public_plan(plan: Mapping[str, Any]) -> tuple[BindingEvidenceIdentity, ...]:
    rows = []
    for implementation in plan.get("implementations", ()):  # type: ignore[union-attr]
        requirement = implementation.get("requirement", {})
        metadata = implementation.get("binding_metadata", {})
        if not metadata or not implementation.get("resolved", False):
            continue
        rows.append(
            BindingEvidenceIdentity(
                role=str(requirement.get("role", "unknown.role")),
                binding_id=str(metadata["binding_id"]),
                binding_version=str(metadata["binding_version"]),
                provider=str(metadata["provider"]),
                implementation_version=str(metadata["implementation_version"]),
                convention_id=str(metadata["convention_id"]),
                source_revision=str(metadata["source_revision"]),
            )
        )
    return tuple(sorted(rows, key=lambda item: (item.role, item.binding_id)))


__all__ = [
    "ACCEPTANCE_EVIDENCE_STALE",
    "ComponentEvidenceIdentity",
    "BindingEvidenceIdentity",
    "DependencyFingerprint",
    "DeclaredScaleContract",
    "AcceptanceEvidenceFingerprint",
    "AcceptanceEvidenceRecord",
    "FingerprintDifference",
    "EvidenceFreshnessDecision",
    "FingerprintComparisonReport",
    "component_identity",
    "binding_identities_from_public_plan",
    "compare_acceptance_fingerprints",
]

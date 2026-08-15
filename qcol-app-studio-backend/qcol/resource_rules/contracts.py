"""Declarative, JSON-safe resource-estimation rule contracts.

Resource rules describe *how* a resolved ansatz is costed during model
preflight.  They are separate from model families and from executable
callables.  A ModelContract carries an exact versioned rule ID; the registry
binds that ID to one estimator implementation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Tuple

RESOURCE_RULE_SCHEMA_VERSION = "qcol-resource-estimation-rule/1.0"
RESOURCE_POLICY_RULE_PROFILE_SCHEMA_VERSION = "qcol-resource-policy-rule-profile/1.0"
RESOURCE_RULE_BINDING_SCHEMA_VERSION = "qcol-resource-rule-binding/1.0"


class ResourceRuleContractError(ValueError):
    """Raised when a declarative resource-rule contract is invalid."""


def _require_nonempty(label: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ResourceRuleContractError(f"{label} must be a non-empty string.")


@dataclass(frozen=True)
class ResourceEstimationRuleContract:
    rule_id: str
    rule_version: str
    label: str
    description: str
    metric_id: str
    output_key: str
    supported_ansatz_policy_ids: Tuple[str, ...]
    required_inputs: Tuple[str, ...]
    formula_label: str
    semantic_fact_id: str
    authoritative_owner_id: str
    source_semantic_fact_ids: Tuple[str, ...]
    limitations: Tuple[str, ...] = field(default_factory=tuple)
    schema_version: str = RESOURCE_RULE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for label, value in (
            ("rule_id", self.rule_id),
            ("rule_version", self.rule_version),
            ("label", self.label),
            ("description", self.description),
            ("metric_id", self.metric_id),
            ("output_key", self.output_key),
            ("formula_label", self.formula_label),
            ("semantic_fact_id", self.semantic_fact_id),
            ("authoritative_owner_id", self.authoritative_owner_id),
        ):
            _require_nonempty(label, value)
        if not self.supported_ansatz_policy_ids:
            raise ResourceRuleContractError(
                "Resource rule must declare at least one supported ansatz policy."
            )
        if not self.required_inputs:
            raise ResourceRuleContractError(
                "Resource rule must declare at least one required input."
            )
        object.__setattr__(
            self,
            "supported_ansatz_policy_ids",
            tuple(str(v) for v in self.supported_ansatz_policy_ids),
        )
        object.__setattr__(
            self, "required_inputs", tuple(str(v) for v in self.required_inputs)
        )
        object.__setattr__(
            self,
            "source_semantic_fact_ids",
            tuple(str(v) for v in self.source_semantic_fact_ids),
        )
        object.__setattr__(
            self, "limitations", tuple(str(v) for v in self.limitations)
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "rule_id": self.rule_id,
            "rule_version": self.rule_version,
            "label": self.label,
            "description": self.description,
            "metric_id": self.metric_id,
            "output_key": self.output_key,
            "supported_ansatz_policy_ids": list(self.supported_ansatz_policy_ids),
            "required_inputs": list(self.required_inputs),
            "formula_label": self.formula_label,
            "semantic_fact_id": self.semantic_fact_id,
            "authoritative_owner_id": self.authoritative_owner_id,
            "source_semantic_fact_ids": list(self.source_semantic_fact_ids),
            "limitations": list(self.limitations),
        }


@dataclass(frozen=True)
class ResourcePolicyRuleProfile:
    resource_policy_id: str
    profile_version: str
    allowed_rule_ids: Tuple[str, ...]
    requires_explicit_rule: bool
    description: str
    aggregate_fact_id: str = "fact.resource.aggregate_report"
    authoritative_owner_id: str = "owner.resource_assessor"
    schema_version: str = RESOURCE_POLICY_RULE_PROFILE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for label, value in (
            ("resource_policy_id", self.resource_policy_id),
            ("profile_version", self.profile_version),
            ("description", self.description),
            ("aggregate_fact_id", self.aggregate_fact_id),
            ("authoritative_owner_id", self.authoritative_owner_id),
        ):
            _require_nonempty(label, value)
        if not self.allowed_rule_ids:
            raise ResourceRuleContractError(
                "Resource policy profile must declare at least one allowed rule."
            )
        object.__setattr__(
            self, "allowed_rule_ids", tuple(str(v) for v in self.allowed_rule_ids)
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "resource_policy_id": self.resource_policy_id,
            "profile_version": self.profile_version,
            "allowed_rule_ids": list(self.allowed_rule_ids),
            "requires_explicit_rule": bool(self.requires_explicit_rule),
            "description": self.description,
            "aggregate_fact_id": self.aggregate_fact_id,
            "authoritative_owner_id": self.authoritative_owner_id,
        }


@dataclass(frozen=True)
class ResourceRuleBinding:
    binding_id: str
    binding_version: str
    rule_id: str
    import_path: str
    implementation_status: str
    provider: str
    source_revision: str
    provenance: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = RESOURCE_RULE_BINDING_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for label, value in (
            ("binding_id", self.binding_id),
            ("binding_version", self.binding_version),
            ("rule_id", self.rule_id),
            ("import_path", self.import_path),
            ("provider", self.provider),
            ("source_revision", self.source_revision),
        ):
            _require_nonempty(label, value)
        if ":" not in self.import_path:
            raise ResourceRuleContractError(
                "Resource rule import_path must use module:function syntax."
            )
        if self.implementation_status not in {"implemented", "not_implemented"}:
            raise ResourceRuleContractError(
                f"Unsupported implementation status {self.implementation_status!r}."
            )
        object.__setattr__(self, "provenance", dict(self.provenance))

    @property
    def executable(self) -> bool:
        return self.implementation_status == "implemented"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "binding_id": self.binding_id,
            "binding_version": self.binding_version,
            "rule_id": self.rule_id,
            "import_path": self.import_path,
            "implementation_status": self.implementation_status,
            "executable": self.executable,
            "provider": self.provider,
            "source_revision": self.source_revision,
            "provenance": dict(self.provenance),
        }


@dataclass(frozen=True)
class ResourceRuleEvaluation:
    resource_policy_id: str
    rule_id: str
    rule_version: str
    binding_id: str
    binding_version: str
    ansatz_policy_id: str
    estimated_parameter_count: int
    input_snapshot: Mapping[str, int]
    explicit_rule_selection: bool
    semantic_derivation: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "resource_policy_id": self.resource_policy_id,
            "resource_rule_id": self.rule_id,
            "resource_rule_version": self.rule_version,
            "resource_rule_binding_id": self.binding_id,
            "resource_rule_binding_version": self.binding_version,
            "ansatz_policy_id": self.ansatz_policy_id,
            "estimated_parameter_count": int(self.estimated_parameter_count),
            "input_snapshot": {
                str(k): int(v) for k, v in self.input_snapshot.items()
            },
            "explicit_rule_selection": bool(self.explicit_rule_selection),
            "semantic_derivation": dict(self.semantic_derivation),
        }

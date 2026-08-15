"""Declarative verification policy contract."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from qcol.mapping_policies.enums import PolicyStatus

from .base import DeclarativeContract, PolicyContractError, freeze_json, normalize_capabilities, require_text, require_token


VERIFICATION_POLICY_SCHEMA_VERSION = "qcol-verification-policy-contract/1.0"


@dataclass(frozen=True)
class VerificationPolicyContract(DeclarativeContract):
    policy_id: str
    policy_version: str
    display_name: str
    implementation_binding_id: str
    required_check_ids: tuple[str, ...]
    comparison_metric_ids: tuple[str, ...]
    required_evidence_capabilities: tuple[str, ...]
    tolerance_profile_id: str
    requires_independent_reference: bool
    support_status: PolicyStatus = PolicyStatus.REGISTERED
    validity_envelope: Mapping[str, Any] = field(default_factory=dict)
    limitations: tuple[str, ...] = field(default_factory=tuple)
    provenance: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = VERIFICATION_POLICY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in (
            "policy_id", "policy_version", "implementation_binding_id", "tolerance_profile_id",
        ):
            require_token(name, getattr(self, name))
        require_text("display_name", self.display_name)
        for name in (
            "required_check_ids", "comparison_metric_ids", "required_evidence_capabilities",
        ):
            object.__setattr__(self, name, normalize_capabilities(getattr(self, name), label=name))
        if not self.required_check_ids:
            raise PolicyContractError("required_check_ids must not be empty.")
        if not isinstance(self.support_status, PolicyStatus):
            raise PolicyContractError("support_status must be PolicyStatus.")
        object.__setattr__(self, "validity_envelope", freeze_json(self.validity_envelope, path="VerificationPolicyContract.validity_envelope"))
        object.__setattr__(self, "provenance", freeze_json(self.provenance, path="VerificationPolicyContract.provenance"))
        object.__setattr__(self, "limitations", tuple(require_text("limitations", str(v)) for v in self.limitations))


__all__ = ["VERIFICATION_POLICY_SCHEMA_VERSION", "VerificationPolicyContract"]

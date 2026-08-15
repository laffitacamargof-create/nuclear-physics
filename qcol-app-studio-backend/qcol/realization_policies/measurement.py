"""Declarative measurement policy contract."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from qcol.mapping_policies.enums import PolicyStatus

from .base import DeclarativeContract, PolicyContractError, freeze_json, normalize_capabilities, require_text, require_token


MEASUREMENT_POLICY_SCHEMA_VERSION = "qcol-measurement-policy-contract/1.0"


@dataclass(frozen=True)
class MeasurementPolicyContract(DeclarativeContract):
    policy_id: str
    policy_version: str
    display_name: str
    implementation_binding_id: str
    supported_observable_capabilities: tuple[str, ...]
    required_mapping_capabilities: tuple[str, ...]
    required_sector_capabilities: tuple[str, ...]
    grouping_policy_id: str
    reconstruction_policy_id: str
    result_semantics: str
    shots_required: bool
    support_status: PolicyStatus = PolicyStatus.REGISTERED
    validity_envelope: Mapping[str, Any] = field(default_factory=dict)
    limitations: tuple[str, ...] = field(default_factory=tuple)
    provenance: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = MEASUREMENT_POLICY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in (
            "policy_id", "policy_version", "implementation_binding_id",
            "grouping_policy_id", "reconstruction_policy_id",
        ):
            require_token(name, getattr(self, name))
        require_text("display_name", self.display_name)
        require_text("result_semantics", self.result_semantics)
        for name in (
            "supported_observable_capabilities",
            "required_mapping_capabilities",
            "required_sector_capabilities",
        ):
            object.__setattr__(self, name, normalize_capabilities(getattr(self, name), label=name))
        if not isinstance(self.support_status, PolicyStatus):
            raise PolicyContractError("support_status must be PolicyStatus.")
        object.__setattr__(self, "validity_envelope", freeze_json(self.validity_envelope, path="MeasurementPolicyContract.validity_envelope"))
        object.__setattr__(self, "provenance", freeze_json(self.provenance, path="MeasurementPolicyContract.provenance"))
        object.__setattr__(self, "limitations", tuple(require_text("limitations", str(v)) for v in self.limitations))


__all__ = ["MEASUREMENT_POLICY_SCHEMA_VERSION", "MeasurementPolicyContract"]

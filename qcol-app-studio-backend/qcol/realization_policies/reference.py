"""Declarative independent-reference policy contract."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from qcol.mapping_policies.enums import PolicyStatus

from .base import DeclarativeContract, PolicyContractError, freeze_json, normalize_capabilities, require_text, require_token


REFERENCE_POLICY_SCHEMA_VERSION = "qcol-reference-policy-contract/1.0"


@dataclass(frozen=True)
class ReferencePolicyContract(DeclarativeContract):
    policy_id: str
    policy_version: str
    display_name: str
    independent_solver_binding_id: str
    source_representation_id: str
    supported_quantities: tuple[str, ...]
    required_model_capabilities: tuple[str, ...]
    required_sector_capabilities: tuple[str, ...]
    units_policy: str
    constant_shift_policy: str
    source_model_fingerprint_required: bool = True
    sector_fingerprint_required: bool = True
    mode_ordering_fingerprint_required: bool = True
    constructed_from_tested_mapping: bool = False
    support_status: PolicyStatus = PolicyStatus.REGISTERED
    validity_envelope: Mapping[str, Any] = field(default_factory=dict)
    limitations: tuple[str, ...] = field(default_factory=tuple)
    provenance: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = REFERENCE_POLICY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in (
            "policy_id", "policy_version", "independent_solver_binding_id",
            "source_representation_id", "units_policy", "constant_shift_policy",
        ):
            require_token(name, getattr(self, name))
        require_text("display_name", self.display_name)
        for name in (
            "supported_quantities",
            "required_model_capabilities",
            "required_sector_capabilities",
        ):
            object.__setattr__(self, name, normalize_capabilities(getattr(self, name), label=name))
        if self.constructed_from_tested_mapping:
            raise PolicyContractError(
                "An acceptance reference must be independent of the mapping implementation under test."
            )
        if not isinstance(self.support_status, PolicyStatus):
            raise PolicyContractError("support_status must be PolicyStatus.")
        object.__setattr__(self, "validity_envelope", freeze_json(self.validity_envelope, path="ReferencePolicyContract.validity_envelope"))
        object.__setattr__(self, "provenance", freeze_json(self.provenance, path="ReferencePolicyContract.provenance"))
        object.__setattr__(self, "limitations", tuple(require_text("limitations", str(v)) for v in self.limitations))


__all__ = ["REFERENCE_POLICY_SCHEMA_VERSION", "ReferencePolicyContract"]

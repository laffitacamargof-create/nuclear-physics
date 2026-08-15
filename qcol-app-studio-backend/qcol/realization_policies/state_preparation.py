"""Declarative state-preparation policy contract."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from qcol.mapping_policies.enums import PolicyStatus

from .base import (
    DeclarativeContract,
    PolicyContractError,
    freeze_json,
    normalize_capabilities,
    require_text,
    require_token,
)


STATE_PREPARATION_SCHEMA_VERSION = "qcol-state-preparation-policy-contract/1.0"
_EXACT_REFERENCE_USAGE = {"forbidden", "test_fixture_only", "metadata_only"}


@dataclass(frozen=True)
class StatePreparationPolicyContract(DeclarativeContract):
    policy_id: str
    policy_version: str
    display_name: str
    implementation_binding_id: str
    input_state_semantics: str
    provided_capabilities: tuple[str, ...]
    required_mapping_capabilities: tuple[str, ...]
    required_sector_capabilities: tuple[str, ...]
    conserved_quantity_guarantees: tuple[str, ...]
    exact_reference_usage: str = "forbidden"
    mapping_context_required: bool = True
    mode_order_aware: bool = True
    support_status: PolicyStatus = PolicyStatus.REGISTERED
    validity_envelope: Mapping[str, Any] = field(default_factory=dict)
    limitations: tuple[str, ...] = field(default_factory=tuple)
    provenance: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = STATE_PREPARATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in ("policy_id", "policy_version", "implementation_binding_id"):
            require_token(name, getattr(self, name))
        require_text("display_name", self.display_name)
        require_text("input_state_semantics", self.input_state_semantics)
        for name in (
            "provided_capabilities",
            "required_mapping_capabilities",
            "required_sector_capabilities",
            "conserved_quantity_guarantees",
        ):
            object.__setattr__(self, name, normalize_capabilities(getattr(self, name), label=name))
        if self.exact_reference_usage not in _EXACT_REFERENCE_USAGE:
            raise PolicyContractError(
                f"exact_reference_usage must be one of {sorted(_EXACT_REFERENCE_USAGE)}."
            )
        if not isinstance(self.support_status, PolicyStatus):
            raise PolicyContractError("support_status must be PolicyStatus.")
        object.__setattr__(self, "validity_envelope", freeze_json(self.validity_envelope, path="StatePreparationPolicyContract.validity_envelope"))
        object.__setattr__(self, "provenance", freeze_json(self.provenance, path="StatePreparationPolicyContract.provenance"))
        object.__setattr__(self, "limitations", tuple(require_text("limitations", str(v)) for v in self.limitations))


__all__ = ["STATE_PREPARATION_SCHEMA_VERSION", "StatePreparationPolicyContract"]

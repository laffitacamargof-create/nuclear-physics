"""Declarative ansatz policy contract with explicit semantic class."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from qcol.mapping_policies.enums import AnsatzSemanticClass, PolicyStatus

from .base import (
    DeclarativeContract,
    PolicyContractError,
    freeze_json,
    normalize_capabilities,
    require_text,
    require_token,
)


ANSATZ_POLICY_SCHEMA_VERSION = "qcol-ansatz-policy-contract/1.0"


@dataclass(frozen=True)
class AnsatzPolicyContract(DeclarativeContract):
    policy_id: str
    policy_version: str
    display_name: str
    implementation_binding_id: str
    semantic_class: AnsatzSemanticClass
    generator_domain: str
    provided_capabilities: tuple[str, ...]
    required_mapping_capabilities: tuple[str, ...]
    required_sector_capabilities: tuple[str, ...]
    preserved_quantities: tuple[str, ...]
    required_equivalence_evidence: tuple[str, ...]
    parameterization_policy_id: str
    mapping_context_required: bool = True
    support_status: PolicyStatus = PolicyStatus.REGISTERED
    validity_envelope: Mapping[str, Any] = field(default_factory=dict)
    limitations: tuple[str, ...] = field(default_factory=tuple)
    provenance: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = ANSATZ_POLICY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in (
            "policy_id",
            "policy_version",
            "implementation_binding_id",
            "parameterization_policy_id",
        ):
            require_token(name, getattr(self, name))
        require_text("display_name", self.display_name)
        require_token("generator_domain", self.generator_domain)
        if not isinstance(self.semantic_class, AnsatzSemanticClass):
            raise PolicyContractError("semantic_class must be AnsatzSemanticClass.")
        for name in (
            "provided_capabilities",
            "required_mapping_capabilities",
            "required_sector_capabilities",
            "preserved_quantities",
            "required_equivalence_evidence",
        ):
            object.__setattr__(self, name, normalize_capabilities(getattr(self, name), label=name))
        if self.semantic_class is AnsatzSemanticClass.MAPPED_FERMIONIC_GENERATOR:
            if "mapped_generator_semantics" not in self.provided_capabilities:
                raise PolicyContractError(
                    "mapped_fermionic_generator ansätze must provide mapped_generator_semantics."
                )
            if not self.required_equivalence_evidence:
                raise PolicyContractError(
                    "mapped_fermionic_generator ansätze require generator/circuit equivalence evidence."
                )
        if self.semantic_class is AnsatzSemanticClass.MAPPING_NATIVE_VERIFIED and not self.required_equivalence_evidence:
            raise PolicyContractError(
                "mapping_native_verified ansätze require named equivalence evidence."
            )
        if self.semantic_class is AnsatzSemanticClass.QUBIT_NATIVE and "mapped_generator_semantics" in self.provided_capabilities:
            raise PolicyContractError(
                "qubit_native ansätze cannot claim mapped_generator_semantics."
            )
        if not isinstance(self.support_status, PolicyStatus):
            raise PolicyContractError("support_status must be PolicyStatus.")
        object.__setattr__(self, "validity_envelope", freeze_json(self.validity_envelope, path="AnsatzPolicyContract.validity_envelope"))
        object.__setattr__(self, "provenance", freeze_json(self.provenance, path="AnsatzPolicyContract.provenance"))
        object.__setattr__(self, "limitations", tuple(require_text("limitations", str(v)) for v in self.limitations))


__all__ = ["ANSATZ_POLICY_SCHEMA_VERSION", "AnsatzPolicyContract"]

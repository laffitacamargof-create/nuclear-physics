"""Declarative MappingPolicyContract for QCOL WP2.

The mapping policy declares scientific semantics and abstract composition
obligations.  It never stores Python callables and never hard-codes concrete
ansatz class names.  Executable binding IDs are resolved in WP3.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Mapping

from qcol.realization_policies.base import (
    DeclarativeContract,
    PolicyContractError,
    freeze_json,
    normalize_capabilities,
    require_text,
    require_token,
)
from qcol.realization_policies.sector import SectorEncodingProfile

from .enums import AlgebraScope, MappingFamily, MappingScope, PolicyStatus


MAPPING_POLICY_SCHEMA_VERSION = "qcol-mapping-policy-contract/1.0"


@dataclass(frozen=True)
class MappingPolicyContract(DeclarativeContract):
    policy_id: str
    policy_version: str
    display_name: str
    family: MappingFamily
    scope: MappingScope
    algebra_scope: AlgebraScope
    convention_id: str
    implementation_binding_id: str

    accepted_operator_types: tuple[str, ...]
    supported_term_ranks: tuple[int, ...]
    required_model_metadata: tuple[str, ...]
    allowed_physical_domains: tuple[str, ...]
    excluded_configurations: tuple[str, ...]

    qubit_count_rule: str
    mode_ordering_requirements: tuple[str, ...]
    encoder_policy_id: str
    decoder_policy_id: str | None
    physical_subspace_policy_id: str
    sector_profiles: tuple[SectorEncodingProfile, ...]

    provided_capabilities: tuple[str, ...]
    requires_state_preparation_capabilities: tuple[str, ...]
    requires_ansatz_capabilities: tuple[str, ...]
    requires_measurement_capabilities: tuple[str, ...]
    requires_reference_capabilities: tuple[str, ...]
    requires_verification_capabilities: tuple[str, ...]
    supported_task_capabilities: tuple[str, ...]
    required_task_operator_capabilities: tuple[str, ...]

    verification_profile_ids: tuple[str, ...]
    resource_metric_ids: tuple[str, ...]
    resource_assessor_binding_id: str
    support_status: PolicyStatus = PolicyStatus.REGISTERED
    scientific_owner: str = "unassigned"
    limitations: tuple[str, ...] = field(default_factory=tuple)
    provenance: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = MAPPING_POLICY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in (
            "policy_id", "policy_version", "convention_id",
            "implementation_binding_id", "encoder_policy_id",
            "physical_subspace_policy_id", "resource_assessor_binding_id",
        ):
            require_token(name, getattr(self, name))
        if self.decoder_policy_id is not None:
            require_token("decoder_policy_id", self.decoder_policy_id)
        require_text("display_name", self.display_name)
        require_text("qubit_count_rule", self.qubit_count_rule)
        require_text("scientific_owner", self.scientific_owner)
        if not isinstance(self.family, MappingFamily):
            raise PolicyContractError("family must be MappingFamily.")
        if not isinstance(self.scope, MappingScope):
            raise PolicyContractError("scope must be MappingScope.")
        if not isinstance(self.algebra_scope, AlgebraScope):
            raise PolicyContractError("algebra_scope must be AlgebraScope.")
        if not isinstance(self.support_status, PolicyStatus):
            raise PolicyContractError("support_status must be PolicyStatus.")

        operator_types = tuple(require_token("accepted_operator_types", str(v)) for v in self.accepted_operator_types)
        if not operator_types:
            raise PolicyContractError("accepted_operator_types must not be empty.")
        object.__setattr__(self, "accepted_operator_types", operator_types)
        ranks = tuple(int(v) for v in self.supported_term_ranks)
        if not ranks or any(rank < 0 for rank in ranks) or len(set(ranks)) != len(ranks):
            raise PolicyContractError("supported_term_ranks must be unique non-negative integers.")
        object.__setattr__(self, "supported_term_ranks", ranks)
        for name in (
            "required_model_metadata", "allowed_physical_domains",
            "excluded_configurations", "mode_ordering_requirements",
            "verification_profile_ids", "resource_metric_ids",
        ):
            values = tuple(require_token(name, str(v)) for v in getattr(self, name))
            if len(set(values)) != len(values):
                raise PolicyContractError(f"{name} must not contain duplicates.")
            object.__setattr__(self, name, values)

        sector_profiles = tuple(self.sector_profiles)
        if not sector_profiles or not all(isinstance(v, SectorEncodingProfile) for v in sector_profiles):
            raise PolicyContractError("sector_profiles must contain SectorEncodingProfile values.")
        quantities = [profile.quantity_id for profile in sector_profiles]
        if len(set(quantities)) != len(quantities):
            raise PolicyContractError(
                "Each conserved quantity must have exactly one SectorEncodingProfile per mapping policy."
            )
        object.__setattr__(self, "sector_profiles", sector_profiles)

        for name in (
            "provided_capabilities",
            "requires_state_preparation_capabilities",
            "requires_ansatz_capabilities",
            "requires_measurement_capabilities",
            "requires_reference_capabilities",
            "requires_verification_capabilities",
            "supported_task_capabilities",
            "required_task_operator_capabilities",
        ):
            object.__setattr__(self, name, normalize_capabilities(getattr(self, name), label=name))

        object.__setattr__(self, "limitations", tuple(require_text("limitations", str(v)) for v in self.limitations))
        object.__setattr__(self, "provenance", freeze_json(self.provenance, path="MappingPolicyContract.provenance"))

        # Scientific architecture guardrail: concrete ansatz names are not a
        # compatibility mechanism.  Only abstract capabilities are accepted.
        if any(re.search(r"\.v[0-9]+$", value) or value.endswith("_ansatz") for value in self.requires_ansatz_capabilities):
            raise PolicyContractError(
                "requires_ansatz_capabilities must contain abstract capabilities, not versioned concrete ansatz IDs."
            )


__all__ = ["MAPPING_POLICY_SCHEMA_VERSION", "MappingPolicyContract"]

"""Per-conserved-quantity sector representation contracts."""
from __future__ import annotations

from dataclasses import dataclass, field

from qcol.mapping_policies.enums import PolicyStatus, SectorRepresentationKind

from .base import DeclarativeContract, PolicyContractError, require_text, require_token


SECTOR_ENCODING_SCHEMA_VERSION = "qcol-sector-encoding-profile/1.0"


@dataclass(frozen=True)
class SectorEncodingProfile(DeclarativeContract):
    profile_id: str
    profile_version: str
    quantity_id: str
    representation_kind: SectorRepresentationKind
    raw_bitstring_semantics: str
    diagnostic_policy_id: str
    required_metadata: tuple[str, ...]
    projector_policy_id: str | None = None
    decoder_policy_id: str | None = None
    exact_value_required: bool = True
    support_status: PolicyStatus = PolicyStatus.REGISTERED
    limitations: tuple[str, ...] = field(default_factory=tuple)
    schema_version: str = SECTOR_ENCODING_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in ("profile_id", "profile_version", "quantity_id", "diagnostic_policy_id"):
            require_token(name, getattr(self, name))
        if not isinstance(self.representation_kind, SectorRepresentationKind):
            raise PolicyContractError("representation_kind must be SectorRepresentationKind.")
        require_text("raw_bitstring_semantics", self.raw_bitstring_semantics)
        for name in ("projector_policy_id", "decoder_policy_id"):
            value = getattr(self, name)
            if value is not None:
                require_token(name, value)
        metadata = tuple(require_token("required_metadata", str(value)) for value in self.required_metadata)
        if len(set(metadata)) != len(metadata):
            raise PolicyContractError("required_metadata must not contain duplicates.")
        object.__setattr__(self, "required_metadata", metadata)
        if not isinstance(self.support_status, PolicyStatus):
            raise PolicyContractError("support_status must be PolicyStatus.")
        object.__setattr__(self, "limitations", tuple(require_text("limitations", str(v)) for v in self.limitations))
        if self.representation_kind is SectorRepresentationKind.UNSUPPORTED and self.support_status in {
            PolicyStatus.VERIFIED,
            PolicyStatus.ACCEPTANCE_VERIFIED,
            PolicyStatus.EXECUTION_READY,
        }:
            raise PolicyContractError("An unsupported sector representation cannot be declared verified or ready.")


__all__ = ["SECTOR_ENCODING_SCHEMA_VERSION", "SectorEncodingProfile"]

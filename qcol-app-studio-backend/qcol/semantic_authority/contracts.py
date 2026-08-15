"""Declarative semantic-authority and derivation contracts for QCOL."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Tuple

from ..runtime_integrity import (
    SemanticDerivationRecord,
    canonical_json_bytes,
    stable_sha256,
)

SEMANTIC_OWNER_SCHEMA_VERSION = "qcol-semantic-owner/1.0"
SEMANTIC_FACT_SCHEMA_VERSION = "qcol-semantic-fact/1.0"
SEMANTIC_DERIVATION_SCHEMA_VERSION = "qcol-semantic-derivation/1.0"


class SemanticAuthorityError(ValueError):
    def __init__(self, failure_code: str, message: str) -> None:
        super().__init__(message)
        self.failure_code = str(failure_code)


def _token(label: str, value: str) -> str:
    value = str(value).strip()
    if not value:
        raise SemanticAuthorityError(
            "SEMANTIC_AUTHORITY_INVALID_CONTRACT",
            f"{label} must be a non-empty string.",
        )
    return value



@dataclass(frozen=True)
class SemanticOwnerContract:
    owner_id: str
    owner_version: str
    owner_kind: str
    label: str
    authoritative_responsibilities: Tuple[str, ...]
    allowed_read_only_consumers: Tuple[str, ...]
    forbidden_responsibilities: Tuple[str, ...] = field(default_factory=tuple)
    schema_version: str = SEMANTIC_OWNER_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in ("owner_id", "owner_version", "owner_kind", "label"):
            object.__setattr__(self, name, _token(name, getattr(self, name)))
        for name in (
            "authoritative_responsibilities",
            "allowed_read_only_consumers",
            "forbidden_responsibilities",
        ):
            values = tuple(_token(name, value) for value in getattr(self, name))
            object.__setattr__(self, name, values)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "owner_id": self.owner_id,
            "owner_version": self.owner_version,
            "owner_kind": self.owner_kind,
            "label": self.label,
            "authoritative_responsibilities": list(self.authoritative_responsibilities),
            "allowed_read_only_consumers": list(self.allowed_read_only_consumers),
            "forbidden_responsibilities": list(self.forbidden_responsibilities),
        }


@dataclass(frozen=True)
class SemanticFactContract:
    fact_id: str
    fact_version: str
    label: str
    authoritative_owner_id: str
    declaration_or_derivation: str
    required_input_fact_ids: Tuple[str, ...]
    read_only_consumers: Tuple[str, ...]
    forbidden_owner_ids: Tuple[str, ...]
    description: str
    schema_version: str = SEMANTIC_FACT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in (
            "fact_id",
            "fact_version",
            "label",
            "authoritative_owner_id",
            "description",
        ):
            object.__setattr__(self, name, _token(name, getattr(self, name)))
        if self.declaration_or_derivation not in {"declared", "derived"}:
            raise SemanticAuthorityError(
                "SEMANTIC_AUTHORITY_INVALID_CONTRACT",
                "declaration_or_derivation must be 'declared' or 'derived'.",
            )
        for name in (
            "required_input_fact_ids",
            "read_only_consumers",
            "forbidden_owner_ids",
        ):
            values = tuple(_token(name, value) for value in getattr(self, name))
            object.__setattr__(self, name, values)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "fact_id": self.fact_id,
            "fact_version": self.fact_version,
            "label": self.label,
            "authoritative_owner_id": self.authoritative_owner_id,
            "declaration_or_derivation": self.declaration_or_derivation,
            "required_input_fact_ids": list(self.required_input_fact_ids),
            "read_only_consumers": list(self.read_only_consumers),
            "forbidden_owner_ids": list(self.forbidden_owner_ids),
            "description": self.description,
        }


__all__ = [
    "SemanticAuthorityError",
    "SemanticOwnerContract",
    "SemanticFactContract",
    "SemanticDerivationRecord",
    "canonical_json_bytes",
    "stable_sha256",
]

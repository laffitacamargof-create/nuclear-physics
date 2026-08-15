"""Versioned, JSON-safe primitives shared by mapping-realization policies.

These value objects carry identifiers and public vocabulary entries only.
Executable functions remain in registries and are deliberately outside WP1.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any, Mapping, TypeAlias



JSONScalar: TypeAlias = None | bool | int | float | str
JSONValue: TypeAlias = JSONScalar | list["JSONValue"] | dict[str, "JSONValue"]

_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")
_VERSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.+-]*$")


@dataclass(frozen=True)
class VersionedIdentifier:
    """A dependency-light identifier for a versioned scientific asset.

    The object does not impose a new naming convention on existing QCOL IDs.
    It records the identifier and version separately so future contracts can
    fingerprint them without storing Python callables.
    """

    identifier: str
    version: str
    kind: str = "policy"
    convention_id: str | None = None
    schema_version: str = "qcol-versioned-identifier/1.0"

    def __post_init__(self) -> None:
        for label, value, pattern in (
            ("identifier", self.identifier, _IDENTIFIER_PATTERN),
            ("version", self.version, _VERSION_PATTERN),
            ("kind", self.kind, _IDENTIFIER_PATTERN),
        ):
            if not isinstance(value, str) or not value.strip() or not pattern.match(value):
                raise ValueError(f"{label} must be a non-empty transport-safe token.")
        if self.convention_id is not None:
            if (
                not isinstance(self.convention_id, str)
                or not self.convention_id.strip()
                or not _IDENTIFIER_PATTERN.match(self.convention_id)
            ):
                raise ValueError(
                    "convention_id must be None or a non-empty transport-safe token."
                )

    @property
    def canonical_token(self) -> str:
        base = f"{self.kind}:{self.identifier}@{self.version}"
        return (
            f"{base}#{self.convention_id}"
            if self.convention_id is not None
            else base
        )

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "schema_version": self.schema_version,
            "kind": self.kind,
            "identifier": self.identifier,
            "version": self.version,
            "convention_id": self.convention_id,
            "canonical_token": self.canonical_token,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "VersionedIdentifier":
        return cls(
            identifier=str(payload["identifier"]),
            version=str(payload["version"]),
            kind=str(payload.get("kind", "policy")),
            convention_id=(
                None
                if payload.get("convention_id") is None
                else str(payload["convention_id"])
            ),
        )

    def fingerprint(self) -> str:
        canonical = json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class VocabularyEntry:
    """Public description of one enum member."""

    enum_name: str
    member_name: str
    value: str
    label: str
    description: str
    schema_version: str = "qcol-vocabulary-entry/1.0"

    def __post_init__(self) -> None:
        for label, value in (
            ("enum_name", self.enum_name),
            ("member_name", self.member_name),
            ("value", self.value),
            ("label", self.label),
            ("description", self.description),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{label} must be a non-empty string.")

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "schema_version": self.schema_version,
            "enum_name": self.enum_name,
            "member_name": self.member_name,
            "value": self.value,
            "label": self.label,
            "description": self.description,
        }


@dataclass(frozen=True)
class LegacyVocabularyTranslation:
    """Explicit bridge from a pre-WP1 raw status to canonical vocabulary.

    WP1 does not rewrite existing scientific records.  A translation record
    makes the intended future migration explicit without silently blessing a
    scoped phrase such as ``verified_for_transform`` as a universal status.
    """

    raw_value: str
    target_enum: str
    target_value: str
    qualifier: str | None
    rationale: str
    schema_version: str = "qcol-legacy-vocabulary-translation/1.0"

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "schema_version": self.schema_version,
            "raw_value": self.raw_value,
            "target_enum": self.target_enum,
            "target_value": self.target_value,
            "qualifier": self.qualifier,
            "rationale": self.rationale,
        }


__all__ = [
    "JSONScalar",
    "JSONValue",
    "VersionedIdentifier",
    "VocabularyEntry",
    "LegacyVocabularyTranslation",
]

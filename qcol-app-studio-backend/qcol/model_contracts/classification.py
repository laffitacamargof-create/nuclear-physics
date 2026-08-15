"""Descriptive, non-authoritative model taxonomy for QCOL.

This contract exists only for discovery, navigation, and documentation.  It
must never own mapping, sector, encoding, ansatz, measurement, task, resource,
or execution semantics.  Those facts remain with the resolved contracts and
policies that own them.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
import hashlib
import json
from typing import Any, Dict, Tuple

MODEL_CLASSIFICATION_SCHEMA_VERSION = "qcol-model-classification/1.1"


class ModelClassificationError(ValueError):
    pass


def _token(label: str, value: str) -> str:
    value = str(value).strip()
    if not value:
        raise ModelClassificationError(f"{label} must be a non-empty string.")
    return value


def _tokens(label: str, values: Tuple[str, ...]) -> Tuple[str, ...]:
    result = tuple(_token(label, value) for value in values)
    if len(result) != len(set(result)):
        raise ModelClassificationError(f"{label} contains duplicates.")
    return result


def _canonical_json(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


@dataclass(frozen=True)
class ModelClassificationContract:
    """Navigation/discovery metadata only.

    Scientific facts are deliberately absent.  ``discovery_tags`` may help a
    person browse the catalog, but it cannot drive resolver, resource, mapping,
    sector, task, or execution decisions.
    """

    classification_id: str
    classification_version: str
    ui_group_id: str
    ui_group_label: str
    discovery_tags: Tuple[str, ...] = field(default_factory=tuple)
    notes: Tuple[str, ...] = field(default_factory=tuple)
    schema_version: str = MODEL_CLASSIFICATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in ("classification_id", "classification_version", "ui_group_id", "ui_group_label"):
            object.__setattr__(self, name, _token(name, getattr(self, name)))
        object.__setattr__(self, "discovery_tags", _tokens("discovery_tags", self.discovery_tags))
        object.__setattr__(self, "notes", tuple(str(v) for v in self.notes))

    @property
    def ui_group_is_navigation_only(self) -> bool:
        return True

    def descriptive_taxonomy_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "classification_id": self.classification_id,
            "classification_version": self.classification_version,
            "discovery_tags": list(self.discovery_tags),
            "notes": list(self.notes),
        }

    # Backward-compatible name retained for callers that only need a stable
    # descriptive fingerprint.  It is not a scientific-realization identity.
    def scientific_axes_dict(self) -> Dict[str, Any]:
        return self.descriptive_taxonomy_dict()

    @property
    def descriptive_taxonomy_fingerprint(self) -> str:
        return hashlib.sha256(_canonical_json(self.descriptive_taxonomy_dict())).hexdigest()

    @property
    def scientific_axes_fingerprint(self) -> str:
        return self.descriptive_taxonomy_fingerprint

    def with_ui_group(self, ui_group_id: str, ui_group_label: str):
        return replace(self, ui_group_id=_token("ui_group_id", ui_group_id), ui_group_label=_token("ui_group_label", ui_group_label))

    def to_dict(self) -> Dict[str, Any]:
        return {
            **self.descriptive_taxonomy_dict(),
            "ui_group_id": self.ui_group_id,
            "ui_group_label": self.ui_group_label,
            "authority": "descriptive_taxonomy_and_navigation_only",
            "scientific_authority": False,
            "runtime_dispatch_allowed": False,
            "descriptive_taxonomy_fingerprint": self.descriptive_taxonomy_fingerprint,
        }


__all__ = ["MODEL_CLASSIFICATION_SCHEMA_VERSION", "ModelClassificationContract", "ModelClassificationError"]

"""One authoritative entry-normalization boundary for QCOL.

This module converts UI/API/legacy entry labels to canonical model/task IDs by
reusing the existing exact alias tables.  It owns no physics and performs no
capability resolution.  Legacy values are retained only as provenance.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping

from .model_instance_adapters import infer_model_id
from .request_boundaries import copy_plain_data
from .task_registry import canonical_task_id

ENTRY_NORMALIZATION_SCHEMA = "qcol-entry-normalization/1.0"
ENTRY_NORMALIZATION_BOUNDARY_ID = "qcol.entry.normalize_once.v1"
LEGACY_ENTRY_KEYS = (
    "method",
    "problem",
    "model_family_label",
    "ui_group_label",
)


def normalize_once(entry: Mapping[str, Any], *, source: str = "unspecified") -> Dict[str, Any]:
    """Return one canonical entry while preserving legacy identity as provenance.

    The exact model alias table in ``infer_model_id`` and the task registry are
    reused; this function does not introduce a second alias registry or infer a
    model from parameters/family labels.  Calling it repeatedly is idempotent.
    """
    payload = copy_plain_data(entry)
    canonical_model_id = infer_model_id(payload)
    canonical_task = canonical_task_id(payload.get("task_id"))

    previous = payload.get("entry_provenance")
    previous = dict(previous) if isinstance(previous, Mapping) else {}
    legacy = previous.get("legacy_entry")
    legacy = dict(legacy) if isinstance(legacy, Mapping) else {}
    for key in LEGACY_ENTRY_KEYS:
        if key in payload and payload.get(key) not in (None, ""):
            legacy.setdefault(key, copy_plain_data(payload[key]))

    payload["model_id"] = canonical_model_id
    payload["task_id"] = canonical_task
    payload["entry_provenance"] = {
        "schema_version": ENTRY_NORMALIZATION_SCHEMA,
        "normalization_boundary_id": ENTRY_NORMALIZATION_BOUNDARY_ID,
        "source": str(previous.get("source") or source),
        "legacy_entry": legacy,
        "canonical_identity": {
            "model_id": canonical_model_id,
            "task_id": canonical_task,
        },
        "legacy_identity_role": "provenance_only",
        "canonical_identity_authoritative": True,
    }
    return payload


__all__ = [
    "ENTRY_NORMALIZATION_SCHEMA",
    "ENTRY_NORMALIZATION_BOUNDARY_ID",
    "LEGACY_ENTRY_KEYS",
    "normalize_once",
]

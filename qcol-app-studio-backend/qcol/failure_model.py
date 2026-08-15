"""Unified architectural failure-record contract and namespaces."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

FAILURE_NAMESPACES = ("RESOLUTION", "RESOURCE", "TRANSLATION", "EXECUTION", "EVIDENCE", "COMPARISON", "STATE")
FAILURE_CATEGORIES = tuple(value.lower() for value in FAILURE_NAMESPACES)
FAILURE_SEVERITIES = ("info", "warning", "error", "fatal")


@dataclass(frozen=True)
class FailureRecord:
    code: str
    station: str
    category: str
    severity: str
    message: str
    evidence_context: Mapping[str, Any] = field(default_factory=dict)
    suggested_action: str | None = None
    recoverable: bool = False

    def __post_init__(self) -> None:
        if self.category not in FAILURE_CATEGORIES:
            raise ValueError(f"Unsupported failure category {self.category!r}.")
        if self.severity not in FAILURE_SEVERITIES:
            raise ValueError(f"Unsupported failure severity {self.severity!r}.")
        prefix = self.code.split("_", 1)[0].upper()
        if prefix not in FAILURE_NAMESPACES:
            raise ValueError(f"Failure code {self.code!r} must use a registered namespace.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "qcol-failure-record/1.0",
            "code": self.code,
            "station": self.station,
            "category": self.category,
            "severity": self.severity,
            "message": self.message,
            "evidence_context": dict(self.evidence_context),
            "suggested_action": self.suggested_action,
            "recoverable": bool(self.recoverable),
        }


def public_failure_model_contract() -> dict[str, Any]:
    return {
        "schema_version": "qcol-failure-model-contract/1.0",
        "record_schema": ["code", "station", "category", "severity", "message", "evidence_context", "suggested_action", "recoverable"],
        "namespaces": list(FAILURE_NAMESPACES),
        "severities": list(FAILURE_SEVERITIES),
        "critical_layers_may_return_unstructured_boolean": False,
        "critical_layers_may_return_generic_value_error_for_expected_failure": False,
    }


__all__ = ["FailureRecord", "FAILURE_NAMESPACES", "public_failure_model_contract"]

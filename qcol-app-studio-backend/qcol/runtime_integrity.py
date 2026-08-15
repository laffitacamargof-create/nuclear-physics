"""Minimal runtime integrity primitives.

This module contains only deterministic hashing and derivation records required
by live scientific/resource decisions. Governance catalogs and ownership audits
remain in CI/release tooling and may re-export these primitives for compatibility.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Dict, Mapping, Tuple

RUNTIME_DERIVATION_SCHEMA_VERSION = "qcol-runtime-derivation/1.0"


def canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def stable_sha256(payload: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def scientific_identity_fingerprint(
    *,
    model_id: str,
    task_id: str,
    target_sector: Mapping[str, Any],
    encoding_context_id: str,
    mapping_policy_id: str,
    state_preparation_policy_id: str | None,
    ansatz_policy_id: str | None,
    measurement_policy_id: str | None,
    reference_policy_id: str | None,
) -> str:
    """Fingerprint the frozen Gate-0 scientific identity vocabulary."""
    def required(label: str, value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError(f"{label} must be a non-empty scientific identifier.")
        return text

    def optional(value: Any) -> str | None:
        return None if value in (None, "") else str(value)

    return stable_sha256({
        "model_id": required("model_id", model_id),
        "task_id": required("task_id", task_id),
        "target_sector": dict(target_sector),
        "encoding_context_id": required("encoding_context_id", encoding_context_id),
        "mapping_policy_id": required("mapping_policy_id", mapping_policy_id),
        "state_preparation_policy_id": optional(state_preparation_policy_id),
        "ansatz_policy_id": optional(ansatz_policy_id),
        "measurement_policy_id": optional(measurement_policy_id),
        "reference_policy_id": optional(reference_policy_id),
    })


@dataclass(frozen=True)
class SemanticDerivationRecord:
    """A live, JSON-safe derivation record without a governance dependency."""

    derivation_id: str
    derivation_version: str
    fact_id: str
    authoritative_owner_id: str
    derivation_rule_id: str
    explicit_inputs: Mapping[str, Any]
    output: Mapping[str, Any]
    source_fact_ids: Tuple[str, ...]
    schema_version: str = RUNTIME_DERIVATION_SCHEMA_VERSION

    @property
    def input_fingerprint(self) -> str:
        return stable_sha256(dict(self.explicit_inputs))

    @property
    def output_fingerprint(self) -> str:
        return stable_sha256(dict(self.output))

    @property
    def derivation_fingerprint(self) -> str:
        return stable_sha256({
            "fact_id": self.fact_id,
            "owner": self.authoritative_owner_id,
            "rule": self.derivation_rule_id,
            "inputs": dict(self.explicit_inputs),
            "output": dict(self.output),
            "source_fact_ids": list(self.source_fact_ids),
        })

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "derivation_id": self.derivation_id,
            "derivation_version": self.derivation_version,
            "fact_id": self.fact_id,
            "authoritative_owner_id": self.authoritative_owner_id,
            "derivation_rule_id": self.derivation_rule_id,
            "explicit_inputs": dict(self.explicit_inputs),
            "input_fingerprint": self.input_fingerprint,
            "output": dict(self.output),
            "output_fingerprint": self.output_fingerprint,
            "source_fact_ids": list(self.source_fact_ids),
            "derivation_fingerprint": self.derivation_fingerprint,
        }


__all__ = [
    "RUNTIME_DERIVATION_SCHEMA_VERSION",
    "SemanticDerivationRecord",
    "canonical_json_bytes",
    "stable_sha256",
    "scientific_identity_fingerprint",
]

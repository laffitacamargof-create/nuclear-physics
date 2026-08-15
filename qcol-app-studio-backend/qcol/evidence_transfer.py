"""Execution-evidence transferability under hierarchical QCOL identity.

Scientific freshness and execution-evidence transferability are intentionally
separate questions.  A shots or adapter mutation leaves the scientific
realization unchanged, but evidence produced for the old execution identity
cannot be reused as evidence for the new execution identity.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ExecutionEvidenceIdentity:
    evidence_id: str
    scientific_fingerprint: str
    execution_fingerprint: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "qcol-execution-evidence-identity/1.0",
            "evidence_id": self.evidence_id,
            "scientific_fingerprint": self.scientific_fingerprint,
            "execution_fingerprint": self.execution_fingerprint,
        }


@dataclass(frozen=True)
class ExecutionEvidenceTransferabilityReport:
    evidence_id: str
    scientific_identity_current: bool
    execution_identity_matches: bool
    transferable: bool
    failure_code: str | None
    message: str
    suggested_action: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "qcol-execution-evidence-transferability-report/1.0",
            "evidence_id": self.evidence_id,
            "scientific_identity_current": self.scientific_identity_current,
            "execution_identity_matches": self.execution_identity_matches,
            "transferable": self.transferable,
            "failure_code": self.failure_code,
            "message": self.message,
            "suggested_action": self.suggested_action,
        }


def assess_execution_evidence_transferability(
    *,
    evidence: ExecutionEvidenceIdentity,
    target_scientific_fingerprint: str,
    target_execution_fingerprint: str,
) -> ExecutionEvidenceTransferabilityReport:
    scientific_current = evidence.scientific_fingerprint == target_scientific_fingerprint
    execution_matches = evidence.execution_fingerprint == target_execution_fingerprint
    if not scientific_current:
        return ExecutionEvidenceTransferabilityReport(
            evidence_id=evidence.evidence_id,
            scientific_identity_current=False,
            execution_identity_matches=execution_matches,
            transferable=False,
            failure_code="EVIDENCE_SCIENTIFIC_IDENTITY_MISMATCH",
            message=(
                "The Evidence was produced for a different scientific realization and "
                "cannot support the target claim."
            ),
            suggested_action=(
                "Resolve the target realization and produce fresh Evidence under its exact "
                "scientific and execution fingerprints."
            ),
        )
    if not execution_matches:
        return ExecutionEvidenceTransferabilityReport(
            evidence_id=evidence.evidence_id,
            scientific_identity_current=True,
            execution_identity_matches=False,
            transferable=False,
            failure_code="EVIDENCE_EXECUTION_IDENTITY_MISMATCH",
            message=(
                "The scientific realization is unchanged, but the Evidence belongs to a "
                "different execution identity."
            ),
            suggested_action=(
                "Execute the target settings and retain a new Evidence record bound to the "
                "new execution fingerprint."
            ),
        )
    return ExecutionEvidenceTransferabilityReport(
        evidence_id=evidence.evidence_id,
        scientific_identity_current=True,
        execution_identity_matches=True,
        transferable=True,
        failure_code=None,
        message="The Evidence matches both the scientific and execution identities.",
        suggested_action=None,
    )


def public_execution_evidence_transferability_contract() -> dict[str, Any]:
    return {
        "schema_version": "qcol-execution-evidence-transferability-contract/1.0",
        "invariants": {
            "scientific_freshness_is_not_execution_evidence_transferability": True,
            "execution_setting_mutation_preserves_scientific_identity_when_science_is_unchanged": True,
            "execution_setting_mutation_requires_new_execution_evidence": True,
            "old_evidence_remains_valid_for_its_original_execution": True,
            "evidence_reuse_requires_exact_execution_fingerprint_match": True,
        },
        "failure_codes": [
            "EVIDENCE_SCIENTIFIC_IDENTITY_MISMATCH",
            "EVIDENCE_EXECUTION_IDENTITY_MISMATCH",
        ],
    }


__all__ = [
    "ExecutionEvidenceIdentity",
    "ExecutionEvidenceTransferabilityReport",
    "assess_execution_evidence_transferability",
    "public_execution_evidence_transferability_contract",
]

"""Governance vocabulary for WP13 and the Phase B handoff.

These enums describe governed scientific assets and request-patch safety.  They
carry no executable advisor logic and remain strict-JSON friendly.
"""
from __future__ import annotations

from enum import StrEnum


class GovernedAssetKind(StrEnum):
    MAPPING_POLICY = "mapping_policy"
    STATE_PREPARATION_POLICY = "state_preparation_policy"
    ANSATZ_POLICY = "ansatz_policy"
    MEASUREMENT_POLICY = "measurement_policy"
    REFERENCE_POLICY = "reference_policy"
    VERIFICATION_POLICY = "verification_policy"
    COMPATIBILITY_RULE = "compatibility_rule"
    ACCEPTANCE_EVIDENCE = "acceptance_evidence"
    REALIZATION_VARIANT = "realization_variant"
    REQUEST_PATCH_POLICY = "request_patch_policy"
    RELEASE = "release"


class OwnerType(StrEnum):
    ROLE = "role"
    TEAM = "team"


class DeprecationStatus(StrEnum):
    ACTIVE = "active"
    DEPRECATED_ALIAS = "deprecated_alias"
    SUPERSEDED = "superseded"
    REJECTED_REGRESSION_FIXTURE = "rejected_regression_fixture"
    RETIRED = "retired"


class MigrationKind(StrEnum):
    EXPLICIT_ALIAS = "explicit_alias"
    IDENTIFIER_MIGRATION = "identifier_migration"
    SCIENTIFIC_REPLACEMENT = "scientific_replacement"
    MANUAL_REVIEW = "manual_review"


class EvidenceTreatment(StrEnum):
    PRESERVE = "preserve"
    RECOMPUTE = "recompute"
    STALE = "stale"
    NOT_APPLICABLE = "not_applicable"


class PatchOperation(StrEnum):
    REPLACE = "replace"


class PatchValueType(StrEnum):
    INTEGER = "integer"
    NUMBER = "number"
    VECTOR_NUMBER = "vector_number"
    VECTOR_TOKEN = "vector_token"


class HandoffStatus(StrEnum):
    READY = "ready"
    BLOCKED = "blocked"


__all__ = [
    "GovernedAssetKind",
    "OwnerType",
    "DeprecationStatus",
    "MigrationKind",
    "EvidenceTreatment",
    "PatchOperation",
    "PatchValueType",
    "HandoffStatus",
]

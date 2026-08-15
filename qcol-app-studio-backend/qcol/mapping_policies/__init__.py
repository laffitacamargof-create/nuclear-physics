"""Public mapping-realization vocabulary and declarative mapping contracts.

The mapping contract imports the realization-sector contract, so it is exposed
lazily to keep both package namespaces import-order independent.
"""
from __future__ import annotations

from importlib import import_module
from typing import Any

from .enums import (
    AlgebraScope,
    AnsatzSemanticClass,
    CheckStatus,
    DecisionStatus,
    EvidenceFreshnessStatus,
    GateApplicability,
    MappingFamily,
    MappingScope,
    PolicyStatus,
    SectorRepresentationKind,
    Severity,
)
from .primitives import (
    JSONScalar,
    JSONValue,
    LegacyVocabularyTranslation,
    VersionedIdentifier,
    VocabularyEntry,
)
from .vocabulary import (
    VOCABULARY_SCHEMA_VERSION,
    VOCABULARY_VERSION,
    coerce_enum,
    enum_entries,
    public_mapping_realization_vocabulary,
    validate_mapping_realization_vocabulary,
    vocabulary_fingerprint,
)

_LAZY = {
    "JW_POLICY_ID": ("qcol.mapping_policies.profiles", "JW_POLICY_ID"),
    "JW_CONVENTION_ID": ("qcol.mapping_policies.profiles", "JW_CONVENTION_ID"),
    "JW_PROFILE_ID": ("qcol.mapping_policies.profiles", "JW_PROFILE_ID"),
    "BK_POLICY_ID": ("qcol.mapping_policies.profiles", "BK_POLICY_ID"),
    "BK_CONVENTION_ID": ("qcol.mapping_policies.profiles", "BK_CONVENTION_ID"),
    "BK_PROFILE_ID": ("qcol.mapping_policies.profiles", "BK_PROFILE_ID"),
    "build_jw_mapping_policy": ("qcol.mapping_policies.profiles", "build_jw_mapping_policy"),
    "build_bk_mapping_policy": ("qcol.mapping_policies.profiles", "build_bk_mapping_policy"),
    "public_spin_orbital_mapping_migration_catalog": ("qcol.mapping_policies.profiles", "public_spin_orbital_mapping_migration_catalog"),
    "spin_orbital_mapping_migration_catalog_fingerprint": ("qcol.mapping_policies.profiles", "spin_orbital_mapping_migration_catalog_fingerprint"),
    "validate_spin_orbital_mapping_migration": ("qcol.mapping_policies.profiles", "validate_spin_orbital_mapping_migration"),
    "public_a3_2b_exit_decision": ("qcol.mapping_policies.profiles", "public_a3_2b_exit_decision"),
    "PAIR_MAPPING_PROFILE_ID": ("qcol.mapping_policies.profiles", "PAIR_MAPPING_PROFILE_ID"),
    "PAIR_MAPPING_POLICY_ID": ("qcol.mapping_policies.profiles", "PAIR_MAPPING_POLICY_ID"),
    "PAIR_MAPPING_CONVENTION_ID": ("qcol.mapping_policies.profiles", "PAIR_MAPPING_CONVENTION_ID"),
    "PairMappingMigrationProfile": ("qcol.mapping_policies.profiles", "PairMappingMigrationProfile"),
    "build_pair_mapping_policy": ("qcol.mapping_policies.profiles", "build_pair_mapping_policy"),
    "public_pair_mapping_migration_catalog": ("qcol.mapping_policies.profiles", "public_pair_mapping_migration_catalog"),
    "pair_mapping_migration_catalog_fingerprint": ("qcol.mapping_policies.profiles", "pair_mapping_migration_catalog_fingerprint"),
    "validate_pair_mapping_migration": ("qcol.mapping_policies.profiles", "validate_pair_mapping_migration"),
    "MAPPING_POLICY_SCHEMA_VERSION": (
        "qcol.mapping_policies.contracts",
        "MAPPING_POLICY_SCHEMA_VERSION",
    ),
    "MappingPolicyContract": (
        "qcol.mapping_policies.contracts",
        "MappingPolicyContract",
    ),
}


def __getattr__(name: str) -> Any:
    target = _LAZY.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, attribute_name = target
    value = getattr(import_module(module_name), attribute_name)
    globals()[name] = value
    return value


__all__ = [
    "MappingFamily",
    "MappingScope",
    "AlgebraScope",
    "PolicyStatus",
    "CheckStatus",
    "Severity",
    "GateApplicability",
    "AnsatzSemanticClass",
    "SectorRepresentationKind",
    "EvidenceFreshnessStatus",
    "DecisionStatus",
    "MAPPING_POLICY_SCHEMA_VERSION",
    "MappingPolicyContract",
    "JSONScalar",
    "JSONValue",
    "VersionedIdentifier",
    "VocabularyEntry",
    "LegacyVocabularyTranslation",
    "VOCABULARY_SCHEMA_VERSION",
    "VOCABULARY_VERSION",
    "coerce_enum",
    "enum_entries",
    "public_mapping_realization_vocabulary",
    "vocabulary_fingerprint",
    "validate_mapping_realization_vocabulary",
    "PAIR_MAPPING_PROFILE_ID",
    "PAIR_MAPPING_POLICY_ID",
    "PAIR_MAPPING_CONVENTION_ID",
    "PairMappingMigrationProfile",
    "build_pair_mapping_policy",
    "public_pair_mapping_migration_catalog",
    "pair_mapping_migration_catalog_fingerprint",
    "validate_pair_mapping_migration",
    "JW_POLICY_ID",
    "JW_CONVENTION_ID",
    "JW_PROFILE_ID",
    "BK_POLICY_ID",
    "BK_CONVENTION_ID",
    "BK_PROFILE_ID",
    "build_jw_mapping_policy",
    "build_bk_mapping_policy",
    "public_spin_orbital_mapping_migration_catalog",
    "spin_orbital_mapping_migration_catalog_fingerprint",
    "validate_spin_orbital_mapping_migration",
    "public_a3_2b_exit_decision",
]

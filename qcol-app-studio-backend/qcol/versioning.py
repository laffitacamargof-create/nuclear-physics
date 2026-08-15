"""Contract and registry version compatibility policy."""
from __future__ import annotations

def public_version_compatibility_policy() -> dict:
    return {
        "schema_version": "qcol-version-compatibility-policy/1.0",
        "rules": {
            "immutable_ids": True,
            "semantic_change_requires_new_version": True,
            "additive_schema_change_requires_declared_compatibility": True,
            "implementation_change_requires_binding_version_bump": True,
            "deprecated_ids_require_explicit_migration": True,
            "silent_alias_or_fallback_allowed": False,
        },
        "legacy_family_field": {
            "status": "deprecated_navigation_alias",
            "removal_policy": "retain through at least two compatible releases",
            "scientific_authority": False,
        },
    }

__all__ = ["public_version_compatibility_policy"]

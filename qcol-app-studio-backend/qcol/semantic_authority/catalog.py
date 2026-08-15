"""Public semantic-authority catalog."""
from __future__ import annotations

from typing import Any, Dict

from .builtin import register_builtin_semantic_authority
from .registry import SEMANTIC_AUTHORITY_REGISTRY


def public_semantic_authority_catalog() -> Dict[str, Any]:
    register_builtin_semantic_authority()
    return SEMANTIC_AUTHORITY_REGISTRY.to_dict()


def semantic_authority_catalog_fingerprint() -> str:
    return str(public_semantic_authority_catalog()["catalog_fingerprint"])


def validate_semantic_authority_catalog() -> Dict[str, bool]:
    return dict(public_semantic_authority_catalog()["validation"])

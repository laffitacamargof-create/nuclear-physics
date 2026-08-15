"""Compatibility-layer import surface for the canonical WP5 resolver.

The implementation lives in :mod:`qcol.realization_variants`; this module
preserves the target package structure without creating a second resolver or
runtime implementation.
"""
from qcol.realization_variants.resolver import (
    RealizationResolverError,
    RealizationVariantResolver,
    resolve_realization_variant,
)
from qcol.realization_variants.runtime_gate import dispatch_resolved_variant

__all__ = [
    "RealizationResolverError",
    "RealizationVariantResolver",
    "resolve_realization_variant",
    "dispatch_resolved_variant",
]

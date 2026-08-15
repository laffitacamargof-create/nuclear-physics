"""Public WP5 realization resolver, reports, fixtures, and runtime gate."""
from .enums import (
    RealizationTaskMode,
    ResolutionStatus,
    RuntimeEntryStatus,
    RuntimePath,
)
from .contracts import (
    RealizationCandidate,
    CompatibilityDiagnostic,
    ResourceReport,
    AcceptanceEvidenceStatus,
    RuntimeEntryDecision,
    CompatibilityReport,
    ResolvedRealizationVariant,
    RuntimeDispatchReport,
    RealizationResolution,
)
from .resolver import (
    RealizationResolverError,
    RealizationVariantResolver,
    resolve_realization_variant,
)
from .runtime_gate import dispatch_resolved_variant

_LAZY_NAMES = {
    "build_wp5_fixture_registries": ("qcol.realization_variants.fixtures", "build_wp5_fixture_registries"),
    "build_wp5_candidates": ("qcol.realization_variants.fixtures", "build_wp5_candidates"),
    "public_realization_resolver_catalog": ("qcol.realization_variants.catalog", "public_realization_resolver_catalog"),
    "realization_resolver_catalog_fingerprint": ("qcol.realization_variants.catalog", "realization_resolver_catalog_fingerprint"),
    "validate_realization_resolver": ("qcol.realization_variants.catalog", "validate_realization_resolver"),
    "build_wp5_resolution_bundle": ("qcol.realization_variants.catalog", "build_wp5_resolution_bundle"),
    "PublicRealizationVariant": ("qcol.realization_variants.public_surface", "PublicRealizationVariant"),
    "ModelTaskCellRealizationView": ("qcol.realization_variants.public_surface", "ModelTaskCellRealizationView"),
    "build_model_task_realization_registry": ("qcol.realization_variants.public_surface", "build_model_task_realization_registry"),
    "get_model_task_realization_view": ("qcol.realization_variants.public_surface", "get_model_task_realization_view"),
    "get_public_realization_variant": ("qcol.realization_variants.public_surface", "get_public_realization_variant"),
    "public_model_task_realization_catalog": ("qcol.realization_variants.public_surface", "public_model_task_realization_catalog"),
    "model_task_realization_catalog_fingerprint": ("qcol.realization_variants.public_surface", "model_task_realization_catalog_fingerprint"),
    "validate_model_task_realization_catalog": ("qcol.realization_variants.public_surface", "validate_model_task_realization_catalog"),
}


def __getattr__(name):
    target = _LAZY_NAMES.get(name)
    if target is None:
        raise AttributeError(name)
    from importlib import import_module
    value = getattr(import_module(target[0]), target[1])
    globals()[name] = value
    return value


__all__ = [
    "RealizationTaskMode",
    "ResolutionStatus",
    "RuntimeEntryStatus",
    "RuntimePath",
    "RealizationCandidate",
    "CompatibilityDiagnostic",
    "ResourceReport",
    "AcceptanceEvidenceStatus",
    "RuntimeEntryDecision",
    "CompatibilityReport",
    "ResolvedRealizationVariant",
    "RuntimeDispatchReport",
    "RealizationResolution",
    "RealizationResolverError",
    "RealizationVariantResolver",
    "resolve_realization_variant",
    "dispatch_resolved_variant",
    *_LAZY_NAMES,
]

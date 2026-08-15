"""Acceptance declarations, fixtures, catalogs, and evidence exporters.

Heavy cross-layer catalogs are loaded lazily so low-level policy modules can
import :mod:`qcol.acceptance` without creating circular imports.
"""
from __future__ import annotations

from importlib import import_module
from typing import Any

from .baseline_evidence import (
    BaselineEvidenceExport,
    collect_scientific_baseline_checks,
    export_mapping_baseline_evidence,
)
from .jw_negative_fixture import (
    JWNegativeFixtureReport,
    evaluate_frozen_jw_negative_fixture,
    evaluate_runtime_jw_negative_fixture,
)
from .mapping_baseline import (
    BASELINE_SCHEMA_VERSION,
    assert_wp0_baseline,
    baseline_fingerprint,
    find_baseline_variants,
    get_baseline_variant,
    load_mapping_realization_baseline,
    public_mapping_realization_baseline,
    validate_mapping_realization_baseline,
)
from .tolerance_profiles import ToleranceProfile
from .vocabulary_evidence import (
    VocabularyEvidenceExport,
    export_mapping_vocabulary_evidence,
)


_LAZY_EXPORTS: dict[str, tuple[str, str]] = {
    # Earlier work-package evidence exporters.
    "PolicyContractEvidenceExport": (
        "qcol.acceptance.policy_contract_evidence",
        "PolicyContractEvidenceExport",
    ),
    "ImplementationBindingEvidenceExport": (
        "qcol.acceptance.implementation_binding_evidence",
        "ImplementationBindingEvidenceExport",
    ),
    "CompatibilityRuleEvidenceExport": (
        "qcol.acceptance.compatibility_rule_evidence",
        "CompatibilityRuleEvidenceExport",
    ),
    "RealizationResolverEvidenceExport": (
        "qcol.acceptance.resolver_evidence",
        "RealizationResolverEvidenceExport",
    ),
    # WP6 fingerprint contracts.
    "ACCEPTANCE_EVIDENCE_STALE": (
        "qcol.acceptance.fingerprint",
        "ACCEPTANCE_EVIDENCE_STALE",
    ),
    "ComponentEvidenceIdentity": (
        "qcol.acceptance.fingerprint",
        "ComponentEvidenceIdentity",
    ),
    "BindingEvidenceIdentity": (
        "qcol.acceptance.fingerprint",
        "BindingEvidenceIdentity",
    ),
    "DependencyFingerprint": (
        "qcol.acceptance.fingerprint",
        "DependencyFingerprint",
    ),
    "DeclaredScaleContract": (
        "qcol.acceptance.fingerprint",
        "DeclaredScaleContract",
    ),
    "AcceptanceEvidenceFingerprint": (
        "qcol.acceptance.fingerprint",
        "AcceptanceEvidenceFingerprint",
    ),
    "AcceptanceEvidenceRecord": (
        "qcol.acceptance.fingerprint",
        "AcceptanceEvidenceRecord",
    ),
    "FingerprintDifference": (
        "qcol.acceptance.fingerprint",
        "FingerprintDifference",
    ),
    "EvidenceFreshnessDecision": (
        "qcol.acceptance.fingerprint",
        "EvidenceFreshnessDecision",
    ),
    "FingerprintComparisonReport": (
        "qcol.acceptance.fingerprint",
        "FingerprintComparisonReport",
    ),
    "component_identity": (
        "qcol.acceptance.fingerprint",
        "component_identity",
    ),
    "binding_identities_from_public_plan": (
        "qcol.acceptance.fingerprint",
        "binding_identities_from_public_plan",
    ),
    "compare_acceptance_fingerprints": (
        "qcol.acceptance.fingerprint",
        "compare_acceptance_fingerprints",
    ),
    "public_acceptance_fingerprint_catalog": (
        "qcol.acceptance.fingerprint_catalog",
        "public_acceptance_fingerprint_catalog",
    ),
    "acceptance_fingerprint_catalog_fingerprint": (
        "qcol.acceptance.fingerprint_catalog",
        "acceptance_fingerprint_catalog_fingerprint",
    ),
    "validate_acceptance_fingerprint_catalog": (
        "qcol.acceptance.fingerprint_catalog",
        "validate_acceptance_fingerprint_catalog",
    ),
    # WP7 generic acceptance harness.
    "AcceptanceGateKind": (
        "qcol.acceptance.harness",
        "AcceptanceGateKind",
    ),
    "ObservationComparison": (
        "qcol.acceptance.harness",
        "ObservationComparison",
    ),
    "AcceptanceObservation": (
        "qcol.acceptance.harness",
        "AcceptanceObservation",
    ),
    "AcceptanceGateContract": (
        "qcol.acceptance.harness",
        "AcceptanceGateContract",
    ),
    "ObservationResult": (
        "qcol.acceptance.harness",
        "ObservationResult",
    ),
    "AcceptanceGateReport": (
        "qcol.acceptance.harness",
        "AcceptanceGateReport",
    ),
    "AcceptanceHarnessCase": (
        "qcol.acceptance.harness",
        "AcceptanceHarnessCase",
    ),
    "PromotionDecision": (
        "qcol.acceptance.harness",
        "PromotionDecision",
    ),
    "AcceptanceHarnessReport": (
        "qcol.acceptance.harness",
        "AcceptanceHarnessReport",
    ),
    "ToleranceProfileRegistry": (
        "qcol.acceptance.harness",
        "ToleranceProfileRegistry",
    ),
    "GenericThreeGateAcceptanceHarness": (
        "qcol.acceptance.harness",
        "GenericThreeGateAcceptanceHarness",
    ),
    "public_acceptance_harness_catalog": (
        "qcol.acceptance.harness_catalog",
        "public_acceptance_harness_catalog",
    ),
    "acceptance_harness_catalog_fingerprint": (
        "qcol.acceptance.harness_catalog",
        "acceptance_harness_catalog_fingerprint",
    ),
    "validate_acceptance_harness_catalog": (
        "qcol.acceptance.harness_catalog",
        "validate_acceptance_harness_catalog",
    ),
    # WP6/WP7 evidence bundles.
    "AcceptanceFingerprintEvidenceExport": (
        "qcol.acceptance.policy_foundation_evidence",
        "AcceptanceFingerprintEvidenceExport",
    ),
    "AcceptanceHarnessEvidenceExport": (
        "qcol.acceptance.policy_foundation_evidence",
        "AcceptanceHarnessEvidenceExport",
    ),
    "PolicyFoundationEvidenceExport": (
        "qcol.acceptance.policy_foundation_evidence",
        "PolicyFoundationEvidenceExport",
    ),
    "SpinOrbitalMappingMigrationEvidenceExport": (
        "qcol.acceptance.spin_orbital_mapping_migration_evidence",
        "SpinOrbitalMappingMigrationEvidenceExport",
    ),
    "collect_spin_orbital_mapping_scientific_regressions": (
        "qcol.acceptance.spin_orbital_mapping_migration_evidence",
        "collect_spin_orbital_mapping_scientific_regressions",
    ),
    "PairMappingMigrationEvidenceExport": (
        "qcol.acceptance.pair_mapping_migration_evidence",
        "PairMappingMigrationEvidenceExport",
    ),
    "collect_pair_mapping_scientific_regressions": (
        "qcol.acceptance.pair_mapping_migration_evidence",
        "collect_pair_mapping_scientific_regressions",
    ),
    "ExportedWP11Evidence": (
        "qcol.acceptance.jw_accepted_composition",
        "ExportedWP11Evidence",
    ),
    "evaluate_jw_generator_conformance": (
        "qcol.acceptance.jw_accepted_composition",
        "evaluate_jw_generator_conformance",
    ),
    "evaluate_wp11_cell_acceptance": (
        "qcol.acceptance.jw_accepted_composition",
        "evaluate_wp11_cell_acceptance",
    ),
    "evaluate_wp11_acceptance": (
        "qcol.acceptance.jw_accepted_composition",
        "evaluate_wp11_acceptance",
    ),
    "ExportedWP12Evidence": (
        "qcol.acceptance.wp12_surface_evidence",
        "ExportedWP12Evidence",
    ),
    "build_wp12_station_error_examples": (
        "qcol.acceptance.wp12_surface_evidence",
        "build_wp12_station_error_examples",
    ),
    "public_wp12_surface_catalog": (
        "qcol.acceptance.wp12_surface_evidence",
        "public_wp12_surface_catalog",
    ),
    "wp12_surface_catalog_fingerprint": (
        "qcol.acceptance.wp12_surface_evidence",
        "wp12_surface_catalog_fingerprint",
    ),
    "validate_wp12_surface_catalog": (
        "qcol.acceptance.wp12_surface_evidence",
        "validate_wp12_surface_catalog",
    ),
}


def __getattr__(name: str) -> Any:
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, attribute_name = target
    value = getattr(import_module(module_name), attribute_name)
    globals()[name] = value
    return value


def export_policy_contract_evidence(*args: Any, **kwargs: Any):
    from .policy_contract_evidence import export_policy_contract_evidence as _export
    return _export(*args, **kwargs)


def export_implementation_binding_evidence(*args: Any, **kwargs: Any):
    from .implementation_binding_evidence import export_implementation_binding_evidence as _export
    return _export(*args, **kwargs)


def export_compatibility_rule_evidence(*args: Any, **kwargs: Any):
    from .compatibility_rule_evidence import export_compatibility_rule_evidence as _export
    return _export(*args, **kwargs)


def export_realization_resolver_evidence(*args: Any, **kwargs: Any):
    from .resolver_evidence import export_realization_resolver_evidence as _export
    return _export(*args, **kwargs)


def export_acceptance_fingerprint_evidence(*args: Any, **kwargs: Any):
    from .policy_foundation_evidence import export_acceptance_fingerprint_evidence as _export
    return _export(*args, **kwargs)


def export_acceptance_harness_evidence(*args: Any, **kwargs: Any):
    from .policy_foundation_evidence import export_acceptance_harness_evidence as _export
    return _export(*args, **kwargs)



def export_pair_mapping_migration_evidence(*args: Any, **kwargs: Any):
    from .pair_mapping_migration_evidence import export_pair_mapping_migration_evidence as _export
    return _export(*args, **kwargs)



def export_spin_orbital_mapping_migration_evidence(*args: Any, **kwargs: Any):
    from .spin_orbital_mapping_migration_evidence import export_spin_orbital_mapping_migration_evidence as _export
    return _export(*args, **kwargs)


def export_wp11_acceptance_evidence(*args: Any, **kwargs: Any):
    from .jw_accepted_composition import export_wp11_acceptance_evidence as _export
    return _export(*args, **kwargs)


def export_wp12_surface_evidence(*args: Any, **kwargs: Any):
    from .wp12_surface_evidence import export_wp12_surface_evidence as _export
    return _export(*args, **kwargs)


def export_policy_foundation_evidence(*args: Any, **kwargs: Any):
    from .policy_foundation_evidence import export_policy_foundation_evidence as _export
    return _export(*args, **kwargs)


__all__ = [
    "BaselineEvidenceExport",
    "collect_scientific_baseline_checks",
    "export_mapping_baseline_evidence",
    "JWNegativeFixtureReport",
    "evaluate_frozen_jw_negative_fixture",
    "evaluate_runtime_jw_negative_fixture",
    "BASELINE_SCHEMA_VERSION",
    "assert_wp0_baseline",
    "baseline_fingerprint",
    "find_baseline_variants",
    "get_baseline_variant",
    "load_mapping_realization_baseline",
    "public_mapping_realization_baseline",
    "validate_mapping_realization_baseline",
    "VocabularyEvidenceExport",
    "export_mapping_vocabulary_evidence",
    "ToleranceProfile",
    "PolicyContractEvidenceExport",
    "export_policy_contract_evidence",
    "ImplementationBindingEvidenceExport",
    "export_implementation_binding_evidence",
    "CompatibilityRuleEvidenceExport",
    "export_compatibility_rule_evidence",
    "RealizationResolverEvidenceExport",
    "export_realization_resolver_evidence",
    *_LAZY_EXPORTS.keys(),
    "export_acceptance_fingerprint_evidence",
    "export_acceptance_harness_evidence",
    "export_policy_foundation_evidence",
    "export_pair_mapping_migration_evidence",
    "export_spin_orbital_mapping_migration_evidence",
    "export_wp11_acceptance_evidence",
    "export_wp12_surface_evidence",
]

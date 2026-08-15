"""Public mapping-realization compatibility foundation with lazy WP4 imports.

WP0 failure codes remain dependency-light and eager.  WP4 rule-registry assets
are imported lazily so the acceptance package can use the stable failure-code
vocabulary without creating a circular import through implementation bindings.
"""
from __future__ import annotations

from importlib import import_module
from typing import Any

from .failure_codes import (
    CompatibilityFailureCode,
    CompatibilityFailureSpec,
    get_failure_spec,
    public_failure_code_registry,
    validate_failure_code_registry,
)

_LAZY_EXPORTS = {
    "CompatibilityParticipant": ("qcol.compatibility.enums", "CompatibilityParticipant"),
    "CompatibilityRulePhase": ("qcol.compatibility.enums", "CompatibilityRulePhase"),
    "CompatibilityRuleContract": ("qcol.compatibility.rule_contracts", "CompatibilityRuleContract"),
    "RuleEvaluationContext": ("qcol.compatibility.rule_contracts", "RuleEvaluationContext"),
    "PredicateResult": ("qcol.compatibility.rule_contracts", "PredicateResult"),
    "CompatibilityCheckResult": ("qcol.compatibility.rule_contracts", "CompatibilityCheckResult"),
    "CompatibilityRuleEvaluationReport": ("qcol.compatibility.rule_contracts", "CompatibilityRuleEvaluationReport"),
    "CompatibilityRuleRegistry": ("qcol.compatibility.rule_registry", "CompatibilityRuleRegistry"),
    "CompatibilityRuleRegistryError": ("qcol.compatibility.rule_registry", "CompatibilityRuleRegistryError"),
    "build_wp4_rule_registry": ("qcol.compatibility.rule_registry", "build_wp4_rule_registry"),
    "build_valid_execution_context": ("qcol.compatibility.fixtures", "build_valid_execution_context"),
    "build_mapping_analysis_context": ("qcol.compatibility.fixtures", "build_mapping_analysis_context"),
    "build_known_invalid_jw_context": ("qcol.compatibility.fixtures", "build_known_invalid_jw_context"),
    "build_negative_rule_contexts": ("qcol.compatibility.fixtures", "build_negative_rule_contexts"),
    "EXPECTED_FAILURE_CODES": ("qcol.compatibility.catalog", "EXPECTED_FAILURE_CODES"),
    "build_wp4_evaluation_bundle": ("qcol.compatibility.catalog", "build_wp4_evaluation_bundle"),
    "public_compatibility_rule_catalog": ("qcol.compatibility.catalog", "public_compatibility_rule_catalog"),
    "compatibility_rule_catalog_fingerprint": ("qcol.compatibility.catalog", "compatibility_rule_catalog_fingerprint"),
    "validate_compatibility_rule_registry": ("qcol.compatibility.catalog", "validate_compatibility_rule_registry"),
    "RealizationResolverError": ("qcol.compatibility.resolver", "RealizationResolverError"),
    "RealizationVariantResolver": ("qcol.compatibility.resolver", "RealizationVariantResolver"),
    "resolve_realization_variant": ("qcol.compatibility.resolver", "resolve_realization_variant"),
    "dispatch_resolved_variant": ("qcol.compatibility.resolver", "dispatch_resolved_variant"),
}

__all__ = [
    "CompatibilityFailureCode",
    "CompatibilityFailureSpec",
    "get_failure_spec",
    "public_failure_code_registry",
    "validate_failure_code_registry",
    *_LAZY_EXPORTS,
]


def __getattr__(name: str) -> Any:
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, attribute_name = target
    value = getattr(import_module(module_name), attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))

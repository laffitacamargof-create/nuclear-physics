"""Public resource-rule contract and registry API."""
from .builtin import (
    GENERIC_RY_RZ_RULE_ID,
    ONE_EXCITATION_RULE_ID,
    register_builtin_resource_rules,
)
from .contracts import (
    ResourceEstimationRuleContract,
    ResourcePolicyRuleProfile,
    ResourceRuleBinding,
    ResourceRuleEvaluation,
)
from .registry import (
    RESOURCE_RULE_REGISTRY,
    ResourceRuleRegistryError,
    public_resource_rule_catalog,
    resource_rule_catalog_fingerprint,
    validate_resource_rule_registry,
)

__all__ = [
    "GENERIC_RY_RZ_RULE_ID",
    "ONE_EXCITATION_RULE_ID",
    "RESOURCE_RULE_REGISTRY",
    "ResourceEstimationRuleContract",
    "ResourcePolicyRuleProfile",
    "ResourceRuleBinding",
    "ResourceRuleEvaluation",
    "ResourceRuleRegistryError",
    "public_resource_rule_catalog",
    "register_builtin_resource_rules",
    "resource_rule_catalog_fingerprint",
    "validate_resource_rule_registry",
]

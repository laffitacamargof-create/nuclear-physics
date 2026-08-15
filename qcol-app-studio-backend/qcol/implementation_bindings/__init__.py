"""QCOL WP3 versioned implementation binding layer."""
from .enums import BindingFailureCode, BindingKind
from .contracts import (
    IMPLEMENTATION_BINDING_SCHEMA_VERSION,
    BINDING_REQUIREMENT_SCHEMA_VERSION,
    BINDING_RESOLUTION_SCHEMA_VERSION,
    RESOLVED_BINDING_PLAN_SCHEMA_VERSION,
    ImplementationBindingContract,
    BindingRequirement,
    BindingResolutionReport,
    ResolvedImplementation,
    ResolvedBindingPlan,
)
from .registry import BindingRegistryDefinitionError, ImplementationBindingRegistry
from .contract_index import (
    DeclarativePolicyContractRegistry,
    binding_requirements_for_contract,
    contract_identity,
    resolve_contracts,
)
from .builtin import (
    WP3_BINDING_REGISTRY_ID,
    WP3_BINDING_REGISTRY_VERSION,
    WP3_CONTRACT_REGISTRY_ID,
    WP3_CONTRACT_REGISTRY_VERSION,
    build_wp3_example_registries,
    known_contract_missing_binding_requirement,
    recognized_not_executable_requirement,
    wp3_binding_contracts,
)
from .catalog import (
    IMPLEMENTATION_BINDING_CATALOG_SCHEMA_VERSION,
    IMPLEMENTATION_BINDING_CATALOG_VERSION,
    build_wp3_example_resolution_bundle,
    public_implementation_binding_catalog,
    implementation_binding_catalog_fingerprint,
    validate_implementation_binding_registry,
)

__all__ = [
    "BindingFailureCode",
    "BindingKind",
    "IMPLEMENTATION_BINDING_SCHEMA_VERSION",
    "BINDING_REQUIREMENT_SCHEMA_VERSION",
    "BINDING_RESOLUTION_SCHEMA_VERSION",
    "RESOLVED_BINDING_PLAN_SCHEMA_VERSION",
    "ImplementationBindingContract",
    "BindingRequirement",
    "BindingResolutionReport",
    "ResolvedImplementation",
    "ResolvedBindingPlan",
    "BindingRegistryDefinitionError",
    "ImplementationBindingRegistry",
    "DeclarativePolicyContractRegistry",
    "binding_requirements_for_contract",
    "contract_identity",
    "resolve_contracts",
    "WP3_BINDING_REGISTRY_ID",
    "WP3_BINDING_REGISTRY_VERSION",
    "WP3_CONTRACT_REGISTRY_ID",
    "WP3_CONTRACT_REGISTRY_VERSION",
    "build_wp3_example_registries",
    "known_contract_missing_binding_requirement",
    "recognized_not_executable_requirement",
    "wp3_binding_contracts",
    "IMPLEMENTATION_BINDING_CATALOG_SCHEMA_VERSION",
    "IMPLEMENTATION_BINDING_CATALOG_VERSION",
    "build_wp3_example_resolution_bundle",
    "public_implementation_binding_catalog",
    "implementation_binding_catalog_fingerprint",
    "validate_implementation_binding_registry",
]

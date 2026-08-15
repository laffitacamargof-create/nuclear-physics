"""Exact versioned predicate bindings for the WP4 compatibility rules."""
from __future__ import annotations

from qcol.implementation_bindings import (
    BindingKind,
    ImplementationBindingContract,
    ImplementationBindingRegistry,
)


PREDICATE_BINDING_VERSION = "1.0.0"
PREDICATE_CONVENTION_ID = "qcol.compatibility.predicate.v1"
PREDICATE_SOURCE_REVISION = "qcol-wp4-rules-r1"


_PREDICATE_BINDINGS = (
    (
        "compatibility.predicate.model_mapping_domain.v1",
        "Model-to-mapping domain predicate",
        "qcol.compatibility.predicates:evaluate_model_mapping_domain",
    ),
    (
        "compatibility.predicate.ordering_same_context.v1",
        "Shared EncodingContext predicate",
        "qcol.compatibility.predicates:evaluate_ordering_same_context",
    ),
    (
        "compatibility.predicate.mapping_sector_representation.v1",
        "Mapping-to-sector representation predicate",
        "qcol.compatibility.predicates:evaluate_mapping_sector_representation",
    ),
    (
        "compatibility.predicate.mapping_state_encoder_match.v1",
        "Mapping-to-state encoder predicate",
        "qcol.compatibility.predicates:evaluate_mapping_state_encoder_match",
    ),
    (
        "compatibility.predicate.mapping_ansatz_generator_semantics.v1",
        "Mapping-to-ansatz generator-semantics predicate",
        "qcol.compatibility.predicates:evaluate_mapping_ansatz_generator_semantics",
    ),
    (
        "compatibility.predicate.mapping_task_all_operators_mapped.v1",
        "Mapping-to-task operator coverage predicate",
        "qcol.compatibility.predicates:evaluate_mapping_task_all_operators_mapped",
    ),
    (
        "compatibility.predicate.model_task_reference_same_problem.v1",
        "Model/task-to-reference identity predicate",
        "qcol.compatibility.predicates:evaluate_model_task_reference_same_problem",
    ),
    (
        "compatibility.predicate.composition_resource_envelope.v1",
        "Complete-composition resource-envelope predicate",
        "qcol.compatibility.predicates:evaluate_composition_resource_envelope",
    ),
    (
        "compatibility.predicate.composition_acceptance_fingerprint.v1",
        "Complete-composition acceptance-fingerprint predicate",
        "qcol.compatibility.predicates:evaluate_composition_acceptance_fingerprint",
    ),
)


def build_wp4_predicate_binding_registry() -> ImplementationBindingRegistry:
    registry = ImplementationBindingRegistry(
        registry_id="qcol.compatibility.predicate-bindings.v1",
        registry_version="1.0.0",
    )
    for binding_id, display_name, import_path in _PREDICATE_BINDINGS:
        registry.register(
            ImplementationBindingContract(
                binding_id=binding_id,
                binding_version=PREDICATE_BINDING_VERSION,
                display_name=display_name,
                kind=BindingKind.COMPATIBILITY_PREDICATE,
                provider="qcol",
                implementation_version="1.0.0",
                convention_id=PREDICATE_CONVENTION_ID,
                source_revision=PREDICATE_SOURCE_REVISION,
                import_path=import_path,
                expected_parameters=("context",),
                description=(
                    "Dependency-light predicate used by the WP4 scientific "
                    "compatibility-rule registry."
                ),
                provenance={
                    "phase": "Phase A.3.2a",
                    "work_package": "WP4",
                    "callable_payload_withheld": True,
                },
            )
        )
    return registry


__all__ = [
    "PREDICATE_BINDING_VERSION",
    "PREDICATE_CONVENTION_ID",
    "PREDICATE_SOURCE_REVISION",
    "build_wp4_predicate_binding_registry",
]

"""WP3 vocabulary for executable implementation bindings.

These enums describe technical binding roles and structured resolution outcomes.
They do not add scientific compatibility judgments; those remain the work of
WP4/WP5.  A binding can be technically resolvable while the scientific
composition is still rejected.
"""
from __future__ import annotations

from enum import StrEnum


class BindingKind(StrEnum):
    OPERATOR_TRANSFORM = "operator_transform"
    BASIS_ENCODER = "basis_encoder"
    BASIS_DECODER = "basis_decoder"
    PHYSICAL_SUBSPACE = "physical_subspace"
    SECTOR_DIAGNOSTIC = "sector_diagnostic"
    SECTOR_PROJECTOR = "sector_projector"
    STATE_PREPARATION = "state_preparation"
    ANSATZ_FACTORY = "ansatz_factory"
    PARAMETERIZATION = "parameterization"
    MEASUREMENT_BUILDER = "measurement_builder"
    GROUPING = "grouping"
    RECONSTRUCTION = "reconstruction"
    REFERENCE_SOLVER = "reference_solver"
    VERIFICATION = "verification"
    RESOURCE_ASSESSOR = "resource_assessor"
    COMPATIBILITY_PREDICATE = "compatibility_predicate"


class BindingFailureCode(StrEnum):
    RESOLVED = "BINDING_RESOLVED"
    NOT_REGISTERED = "BINDING_NOT_REGISTERED"
    DECLARED_NOT_EXECUTABLE = "BINDING_DECLARED_NOT_EXECUTABLE"
    IMPORT_FAILED = "BINDING_IMPORT_FAILED"
    ATTRIBUTE_MISSING = "BINDING_ATTRIBUTE_MISSING"
    NOT_CALLABLE = "BINDING_NOT_CALLABLE"
    SIGNATURE_MISMATCH = "BINDING_SIGNATURE_MISMATCH"
    KIND_MISMATCH = "BINDING_KIND_MISMATCH"
    VERSION_MISMATCH = "BINDING_VERSION_MISMATCH"
    CONVENTION_MISMATCH = "BINDING_CONVENTION_MISMATCH"


__all__ = ["BindingKind", "BindingFailureCode"]

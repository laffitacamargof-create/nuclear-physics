"""Domain-neutral model contracts for the QCOL model-plugin architecture.

This module is deliberately dependency-light.  It contains no Cirq,
OpenFermion, NumPy, Gradio, or FastAPI imports, so the same scientific
contract can be inspected by notebooks, APIs, user interfaces, acceptance
tests, and future resolvers without importing the quantum runtime.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import math
from types import MappingProxyType
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple

from .classification import ModelClassificationContract
from ..runtime_integrity import scientific_identity_fingerprint


MODEL_CONTRACT_SCHEMA_VERSION = "qcol-model-contract/1.0"
MODEL_CONTRACT_SCHEMA_VERSION_1_1 = "qcol-model-contract/1.1"
MODEL_CONTRACT_SCHEMA_VERSION_1_2 = "qcol-model-contract/1.2"
MODEL_CONTRACT_SCHEMA_VERSION_1_3 = "qcol-model-contract/1.3"
MODEL_INSTANCE_SCHEMA_VERSION = "qcol-model-instance/1.0"
CAPABILITY_REPORT_SCHEMA_VERSION = "qcol-capability-report/1.0"
RESOLVED_PLAN_SCHEMA_VERSION = "qcol-resolved-model-plan/1.0"
QUANTUM_REALIZATION_SCHEMA_VERSION = "qcol-quantum-realization/1.1"

SUPPORT_STATUSES = {
    "registered",
    "recognized",
    "execution_ready",
    "acceptance_verified",
    "future",
}
EXECUTION_STATUSES = {
    "not_implemented",
    "recognized_not_executable",
    "experimental",
    "execution_ready",
    "acceptance_verified",
}
CAPABILITY_STATUSES = {
    "verified",
    "executable",
    "experimental",
    "recognized_not_executable",
    "unsupported",
    "unresolved",
}
CHECK_STATUSES = {"pass", "review", "fail", "not_run"}


class ModelContractError(ValueError):
    """Raised when a domain-neutral QCOL contract is structurally invalid."""


def _freeze(value: Any) -> Any:
    """Recursively copy mappings into read-only views and sequences into tuples."""
    if isinstance(value, Mapping):
        return MappingProxyType({str(k): _freeze(v) for k, v in value.items()})
    if isinstance(value, (list, tuple, set, frozenset)):
        return tuple(_freeze(v) for v in value)
    return deepcopy(value)


def _thaw(value: Any) -> Any:
    """Convert frozen contract values back to ordinary JSON-friendly objects."""
    if isinstance(value, Mapping):
        return {str(k): _thaw(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [_thaw(v) for v in value]
    return deepcopy(value)


def _require_nonempty(label: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ModelContractError(f"{label} must be a non-empty string.")


@dataclass(frozen=True)
class ParameterSpec:
    """One field in a model-neutral, UI-generatable parameter schema."""

    key: str
    label: str
    kind: str
    role: str = "editable"  # editable | fixed | derived
    default: Any = None
    fixed_value: Any = None
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    step: Optional[float] = None
    exact_length: Optional[int] = None
    length_from: Optional[str] = None
    item_kind: Optional[str] = None
    unit_key: Optional[str] = None
    help_text: str = ""
    visible: bool = True
    order: int = 0

    def __post_init__(self) -> None:
        _require_nonempty("parameter key", self.key)
        _require_nonempty("parameter label", self.label)
        _require_nonempty("parameter kind", self.kind)
        if self.role not in {"editable", "fixed", "derived"}:
            raise ModelContractError(
                f"Parameter {self.key!r} has unsupported role {self.role!r}."
            )
        if self.role == "fixed" and self.fixed_value is None:
            raise ModelContractError(
                f"Fixed parameter {self.key!r} must declare fixed_value."
            )
        if self.minimum is not None and self.maximum is not None:
            if float(self.minimum) > float(self.maximum):
                raise ModelContractError(
                    f"Parameter {self.key!r} has minimum > maximum."
                )
        if self.exact_length is not None and int(self.exact_length) <= 0:
            raise ModelContractError(
                f"Parameter {self.key!r} exact_length must be positive."
            )
        object.__setattr__(self, "default", _freeze(self.default))
        object.__setattr__(self, "fixed_value", _freeze(self.fixed_value))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "kind": self.kind,
            "role": self.role,
            "default": _thaw(self.default),
            "fixed_value": _thaw(self.fixed_value),
            "minimum": self.minimum,
            "maximum": self.maximum,
            "step": self.step,
            "exact_length": self.exact_length,
            "length_from": self.length_from,
            "item_kind": self.item_kind,
            "unit_key": self.unit_key,
            "help_text": self.help_text,
            "visible": bool(self.visible),
            "order": int(self.order),
        }


@dataclass(frozen=True)
class ReferenceValidity:
    """Declares where a model-specific reference is scientifically trustworthy."""

    reference_kind: str
    validity_statement: str
    exact_within_declared_model: bool
    maximum_dimension: Optional[int] = None
    maximum_qubits: Optional[int] = None
    parameter_conditions: Mapping[str, Any] = field(default_factory=dict)
    fallback_policy: str = "limited_verification"

    def __post_init__(self) -> None:
        _require_nonempty("reference_kind", self.reference_kind)
        _require_nonempty("validity_statement", self.validity_statement)
        _require_nonempty("fallback_policy", self.fallback_policy)
        if self.maximum_dimension is not None and self.maximum_dimension <= 0:
            raise ModelContractError("maximum_dimension must be positive when set.")
        if self.maximum_qubits is not None and self.maximum_qubits <= 0:
            raise ModelContractError("maximum_qubits must be positive when set.")
        object.__setattr__(
            self, "parameter_conditions", _freeze(self.parameter_conditions)
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reference_kind": self.reference_kind,
            "validity_statement": self.validity_statement,
            "exact_within_declared_model": bool(self.exact_within_declared_model),
            "maximum_dimension": self.maximum_dimension,
            "maximum_qubits": self.maximum_qubits,
            "parameter_conditions": _thaw(self.parameter_conditions),
            "fallback_policy": self.fallback_policy,
        }


@dataclass(frozen=True)
class ResourceValidityEnvelope:
    """Honest execution envelope declared by a model plugin."""

    simulator_max_qubits: Optional[int] = None
    exact_semantic_check_max_qubits: Optional[int] = None
    maximum_parameter_count: Optional[int] = None
    notes: Tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        for label, value in (
            ("simulator_max_qubits", self.simulator_max_qubits),
            ("exact_semantic_check_max_qubits", self.exact_semantic_check_max_qubits),
            ("maximum_parameter_count", self.maximum_parameter_count),
        ):
            if value is not None and int(value) <= 0:
                raise ModelContractError(f"{label} must be positive when set.")
        object.__setattr__(self, "notes", tuple(str(v) for v in self.notes))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "simulator_max_qubits": self.simulator_max_qubits,
            "exact_semantic_check_max_qubits": self.exact_semantic_check_max_qubits,
            "maximum_parameter_count": self.maximum_parameter_count,
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class ModelContract:
    """Scientific promise and implementation requirements for one model plugin.

    The contract is declarative.  It contains policy IDs, not executable
    callables.  A later Capability Resolver binds those IDs to certified
    implementations.
    """

    model_id: str
    model_version: str
    label: str
    description: str
    domain: str
    family: str
    problem_type: str
    supported_tasks: Tuple[str, ...]
    parameter_schema: Tuple[ParameterSpec, ...]
    units: Mapping[str, str]
    conserved_quantities: Tuple[str, ...]
    sector_schema: Mapping[str, Any]
    supported_observables: Tuple[str, ...]

    hamiltonian_policy_id: str
    sector_policy_id: str
    mapping_policy_id: str
    state_preparation_policy_id: str
    ansatz_policy_id: str
    measurement_policy_id: str
    reference_policy_id: str
    resource_policy_id: str
    runtime_policy_id: str
    interpretation_policy_id: str

    reference_validity: ReferenceValidity
    resource_validity: ResourceValidityEnvelope
    # Optional in legacy 1.0 contracts; required by resource policies that
    # declare exact rule selection (for example bounded_direct_qubit.v2).
    resource_estimation_rule_id: Optional[str] = None
    # Optional representation-specific contract carried by model plugins.
    # This keeps the neutral ModelContract extensible without making every
    # domain-specific field a top-level requirement.
    representation_contract: Mapping[str, Any] = field(default_factory=dict)
    # Independent taxonomy axes.  ``family`` is retained for backward
    # compatibility and navigation only; it is never an execution authority.
    classification: Optional[ModelClassificationContract] = None
    # Authoritative model-science axes.  These belong to ModelContract, not to
    # the descriptive ModelClassificationContract.
    physical_phenomena: Tuple[str, ...] = field(default_factory=tuple)
    degrees_of_freedom: Tuple[str, ...] = field(default_factory=tuple)
    hamiltonian_components: Tuple[str, ...] = field(default_factory=tuple)
    compatible_mapping_ids: Tuple[str, ...] = field(default_factory=tuple)
    assumptions: Tuple[str, ...] = field(default_factory=tuple)
    limitations: Tuple[str, ...] = field(default_factory=tuple)
    support_status: str = "registered"
    execution_status: str = "not_implemented"
    scientific_owner: str = "unassigned"
    scientific_review_status: str = "pending"
    acceptance_suite_id: Optional[str] = None
    schema_version: str = MODEL_CONTRACT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for label, value in (
            ("model_id", self.model_id),
            ("model_version", self.model_version),
            ("label", self.label),
            ("description", self.description),
            ("domain", self.domain),
            ("family", self.family),
            ("problem_type", self.problem_type),
            ("scientific_owner", self.scientific_owner),
            ("scientific_review_status", self.scientific_review_status),
        ):
            _require_nonempty(label, value)
        if self.support_status not in SUPPORT_STATUSES:
            raise ModelContractError(
                f"Unsupported support_status {self.support_status!r}."
            )
        if self.execution_status not in EXECUTION_STATUSES:
            raise ModelContractError(
                f"Unsupported execution_status {self.execution_status!r}."
            )
        if not self.supported_tasks:
            raise ModelContractError("A ModelContract must declare supported_tasks.")
        if len(set(self.supported_tasks)) != len(self.supported_tasks):
            raise ModelContractError("supported_tasks contains duplicates.")
        keys = [item.key for item in self.parameter_schema]
        if len(keys) != len(set(keys)):
            raise ModelContractError("parameter_schema contains duplicate keys.")
        declared_keys = set(keys)
        for item in self.parameter_schema:
            if item.length_from and item.length_from not in declared_keys:
                raise ModelContractError(
                    f"Parameter {item.key!r} references unknown length_from "
                    f"{item.length_from!r}."
                )
        required_policy_ids = (
            self.hamiltonian_policy_id,
            self.sector_policy_id,
            self.mapping_policy_id,
            self.state_preparation_policy_id,
            self.ansatz_policy_id,
            self.measurement_policy_id,
            self.reference_policy_id,
            self.resource_policy_id,
            self.runtime_policy_id,
            self.interpretation_policy_id,
        )
        if self.resource_estimation_rule_id is not None:
            _require_nonempty(
                "resource_estimation_rule_id", self.resource_estimation_rule_id
            )
        if self.resource_policy_id == "bounded_direct_qubit.v2":
            _require_nonempty(
                "resource_estimation_rule_id",
                self.resource_estimation_rule_id or "",
            )
        if self.execution_status in {"execution_ready", "acceptance_verified"}:
            for policy_id in required_policy_ids:
                _require_nonempty("policy ID", policy_id)
            if not self.acceptance_suite_id:
                raise ModelContractError(
                    "Execution-ready contracts must declare acceptance_suite_id."
                )
        object.__setattr__(self, "units", _freeze(self.units))
        object.__setattr__(self, "sector_schema", _freeze(self.sector_schema))
        object.__setattr__(self, "representation_contract", _freeze(self.representation_contract))
        if self.classification is not None and not isinstance(
            self.classification, ModelClassificationContract
        ):
            raise ModelContractError(
                "classification must be a ModelClassificationContract when set."
            )
        for semantic_name in ("physical_phenomena", "degrees_of_freedom", "hamiltonian_components"):
            values = tuple(str(v).strip() for v in getattr(self, semantic_name))
            if not values or any(not value for value in values):
                raise ModelContractError(f"{semantic_name} must declare at least one non-empty value.")
            if len(values) != len(set(values)):
                raise ModelContractError(f"{semantic_name} contains duplicates.")
            object.__setattr__(self, semantic_name, values)
        object.__setattr__(
            self, "compatible_mapping_ids", tuple(str(v) for v in self.compatible_mapping_ids)
        )
        object.__setattr__(
            self, "supported_tasks", tuple(str(v) for v in self.supported_tasks)
        )
        object.__setattr__(
            self,
            "conserved_quantities",
            tuple(str(v) for v in self.conserved_quantities),
        )
        object.__setattr__(
            self,
            "supported_observables",
            tuple(str(v) for v in self.supported_observables),
        )
        object.__setattr__(self, "assumptions", tuple(str(v) for v in self.assumptions))
        object.__setattr__(self, "limitations", tuple(str(v) for v in self.limitations))

    @property
    def executable(self) -> bool:
        return self.execution_status in {"execution_ready", "acceptance_verified"}

    def parameter(self, key: str) -> ParameterSpec:
        for item in self.parameter_schema:
            if item.key == key:
                return item
        raise KeyError(key)

    def to_dict(self) -> Dict[str, Any]:
        fields = sorted(self.parameter_schema, key=lambda item: item.order)
        return {
            "schema_version": self.schema_version,
            "model_id": self.model_id,
            "model_version": self.model_version,
            "label": self.label,
            "description": self.description,
            "domain": self.domain,
            "family": self.family,
            "family_authority": "navigation_and_grouping_only",
            "family_status": "deprecated_navigation_alias",
            "family_removal_policy": "retain_for_two_compatible_releases",
            "problem_type": self.problem_type,
            "supported_tasks": list(self.supported_tasks),
            "parameter_schema": [item.to_dict() for item in fields],
            "units": _thaw(self.units),
            "conserved_quantities": list(self.conserved_quantities),
            "sector_schema": _thaw(self.sector_schema),
            "supported_observables": list(self.supported_observables),
            "representation_contract": _thaw(self.representation_contract),
            "classification": (
                {
                    **self.classification.to_dict(),
                    "read_only_projection": {
                        "physical_domain": self.domain,
                        "phenomena": list(self.physical_phenomena),
                        "degrees_of_freedom": list(self.degrees_of_freedom),
                        "descriptive_representation_tags": list(_thaw(self.representation_contract).keys()),
                        "descriptive_interaction_tags": list(self.hamiltonian_components),
                    },
                    "projection_source": "ModelContract",
                }
                if self.classification is not None
                else None
            ),
            "scientific_model": {
                "physical_domain": self.domain,
                "physical_phenomena": list(self.physical_phenomena),
                "degrees_of_freedom": list(self.degrees_of_freedom),
                "representation": _thaw(self.representation_contract),
                "hamiltonian_components": list(self.hamiltonian_components),
                "sector_symmetries": {
                    "conserved_quantities": list(self.conserved_quantities),
                    "sector_schema": _thaw(self.sector_schema),
                    "sector_policy_id": self.sector_policy_id,
                },
                "encoding_mapping": {
                    "mapping_policy_id": self.mapping_policy_id,
                    "compatible_mapping_ids": list(self.compatible_mapping_ids),
                },
            },
            "compatible_mapping_ids": list(self.compatible_mapping_ids),
            "policies": {
                **{
                    "hamiltonian": self.hamiltonian_policy_id,
                    "sector": self.sector_policy_id,
                    "mapping": self.mapping_policy_id,
                    "state_preparation": self.state_preparation_policy_id,
                    "ansatz": self.ansatz_policy_id,
                    "measurement": self.measurement_policy_id,
                    "reference": self.reference_policy_id,
                    "resource": self.resource_policy_id,
                    "runtime": self.runtime_policy_id,
                    "interpretation": self.interpretation_policy_id,
                },
                **(
                    {"resource_estimation_rule": self.resource_estimation_rule_id}
                    if self.resource_estimation_rule_id is not None
                    else {}
                ),
            },
            "reference_validity": self.reference_validity.to_dict(),
            "resource_validity": self.resource_validity.to_dict(),
            "assumptions": list(self.assumptions),
            "limitations": list(self.limitations),
            "support_status": self.support_status,
            "execution_status": self.execution_status,
            "executable": self.executable,
            "scientific_owner": self.scientific_owner,
            "scientific_review_status": self.scientific_review_status,
            "acceptance_suite_id": self.acceptance_suite_id,
        }


@dataclass(frozen=True)
class ModelInstance:
    """One user-specified physical case under a declared ModelContract."""

    model_id: str
    model_version: str
    task_id: str
    parameters: Mapping[str, Any]
    target_sector: Mapping[str, Any]
    requested_observables: Tuple[str, ...]
    units: Mapping[str, str]
    source_metadata: Mapping[str, Any] = field(default_factory=dict)
    instance_id: Optional[str] = None
    schema_version: str = MODEL_INSTANCE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for label, value in (
            ("model_id", self.model_id),
            ("model_version", self.model_version),
            ("task_id", self.task_id),
        ):
            _require_nonempty(label, value)
        object.__setattr__(self, "parameters", _freeze(self.parameters))
        object.__setattr__(self, "target_sector", _freeze(self.target_sector))
        object.__setattr__(self, "units", _freeze(self.units))
        object.__setattr__(self, "source_metadata", _freeze(self.source_metadata))
        object.__setattr__(
            self,
            "requested_observables",
            tuple(str(v) for v in self.requested_observables),
        )

    def validate_against(self, contract: ModelContract) -> None:
        if self.model_id != contract.model_id:
            raise ModelContractError(
                f"ModelInstance model_id {self.model_id!r} does not match "
                f"contract {contract.model_id!r}."
            )
        if self.model_version != contract.model_version:
            raise ModelContractError(
                f"ModelInstance version {self.model_version!r} does not match "
                f"contract {contract.model_version!r}."
            )
        if self.task_id not in contract.supported_tasks:
            raise ModelContractError(
                f"Task {self.task_id!r} is not supported by {contract.model_id}."
            )
        unknown_observables = set(self.requested_observables) - set(
            contract.supported_observables
        )
        if unknown_observables:
            raise ModelContractError(
                f"Unsupported observables: {sorted(unknown_observables)}"
            )
        supplied = set(self.parameters)
        declared = {field.key for field in contract.parameter_schema}
        unknown = supplied - declared
        if unknown:
            raise ModelContractError(
                f"ModelInstance contains undeclared parameters: {sorted(unknown)}"
            )
        for field_spec in contract.parameter_schema:
            if field_spec.role == "fixed":
                observed = self.parameters.get(field_spec.key, field_spec.fixed_value)
                if observed != field_spec.fixed_value:
                    raise ModelContractError(
                        f"Fixed parameter {field_spec.key!r} must equal "
                        f"{field_spec.fixed_value!r}, received {observed!r}."
                    )
            if field_spec.role == "editable" and field_spec.key not in self.parameters:
                raise ModelContractError(
                    f"Editable parameter {field_spec.key!r} is missing."
                )
            if field_spec.key in self.parameters:
                value = self.parameters[field_spec.key]
                if field_spec.kind in {"number", "integer"}:
                    numeric = float(value)
                    if not math.isfinite(numeric):
                        raise ModelContractError(
                            f"Parameter {field_spec.key!r} must be finite."
                        )
                    if field_spec.minimum is not None and numeric < field_spec.minimum:
                        raise ModelContractError(
                            f"Parameter {field_spec.key!r} is below its minimum."
                        )
                    if field_spec.maximum is not None and numeric > field_spec.maximum:
                        raise ModelContractError(
                            f"Parameter {field_spec.key!r} is above its maximum."
                        )
                if field_spec.kind == "vector":
                    try:
                        values = tuple(value)
                    except TypeError as exc:
                        raise ModelContractError(
                            f"Parameter {field_spec.key!r} must be a sequence."
                        ) from exc
                    if field_spec.exact_length is not None:
                        expected_length = int(field_spec.exact_length)
                    elif field_spec.length_from:
                        expected_length = int(self.parameters[field_spec.length_from])
                    else:
                        expected_length = None
                    if expected_length is not None and len(values) != expected_length:
                        raise ModelContractError(
                            f"Parameter {field_spec.key!r} requires {expected_length} "
                            f"values, received {len(values)}."
                        )
                    for item in values:
                        if isinstance(item, (int, float)) and not math.isfinite(float(item)):
                            raise ModelContractError(
                                f"Parameter {field_spec.key!r} contains a non-finite value."
                            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "instance_id": self.instance_id,
            "model_id": self.model_id,
            "model_version": self.model_version,
            "task_id": self.task_id,
            "parameters": _thaw(self.parameters),
            "target_sector": _thaw(self.target_sector),
            "requested_observables": list(self.requested_observables),
            "units": _thaw(self.units),
            "source_metadata": _thaw(self.source_metadata),
        }


@dataclass(frozen=True)
class CapabilityCheck:
    key: str
    status: str
    message: str
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_nonempty("capability check key", self.key)
        if self.status not in CHECK_STATUSES:
            raise ModelContractError(
                f"Capability check {self.key!r} has invalid status {self.status!r}."
            )
        _require_nonempty("capability check message", self.message)
        object.__setattr__(self, "details", _freeze(self.details))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "status": self.status,
            "message": self.message,
            "details": _thaw(self.details),
        }


@dataclass(frozen=True)
class CapabilityReport:
    """Resolver-facing decision record for one model instance and supported task."""

    model_id: str
    model_version: str
    task_id: str
    overall_status: str
    checks: Tuple[CapabilityCheck, ...]
    reasons: Tuple[str, ...] = field(default_factory=tuple)
    schema_version: str = CAPABILITY_REPORT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.overall_status not in CAPABILITY_STATUSES:
            raise ModelContractError(
                f"Invalid capability status {self.overall_status!r}."
            )
        object.__setattr__(self, "reasons", tuple(str(v) for v in self.reasons))

    @property
    def may_enter_runtime(self) -> bool:
        return self.overall_status in {"verified", "executable", "experimental"}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "model_id": self.model_id,
            "model_version": self.model_version,
            "task_id": self.task_id,
            "overall_status": self.overall_status,
            "may_enter_runtime": self.may_enter_runtime,
            "checks": [item.to_dict() for item in self.checks],
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class ResolvedModelPlan:
    """An actual capability resolution for one model instance.

    Policy identifiers remain serializable.  The certified callables are kept in
    ``resolved_bindings`` and are intentionally omitted from ``to_dict`` so the
    scientific contract can be logged without serializing executable code.
    """

    plan_id: str
    model_contract_id: str
    model_version: str
    model_instance_id: Optional[str]
    task_id: str
    policy_bindings: Mapping[str, str]
    capability_report: CapabilityReport
    resolution_status: str = "resolved"
    contract: Optional[ModelContract] = field(default=None, repr=False, compare=False)
    instance: Optional[ModelInstance] = field(default=None, repr=False, compare=False)
    resolved_bindings: Mapping[str, Any] = field(
        default_factory=dict, repr=False, compare=False
    )
    preflight_resources: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = RESOLVED_PLAN_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require_nonempty("plan_id", self.plan_id)
        object.__setattr__(self, "policy_bindings", _freeze(self.policy_bindings))
        object.__setattr__(self, "preflight_resources", _freeze(self.preflight_resources))
        if self.resolution_status == "resolved":
            if self.contract is None or self.instance is None:
                raise ModelContractError(
                    "A resolved plan must retain its ModelContract and ModelInstance."
                )
            missing = set(self.policy_bindings) - set(self.resolved_bindings)
            if missing:
                raise ModelContractError(
                    f"ResolvedModelPlan is missing callable bindings: {sorted(missing)}"
                )
            bad = [key for key, value in self.resolved_bindings.items() if not callable(value)]
            if bad:
                raise ModelContractError(
                    f"Resolved bindings are not callable: {sorted(bad)}"
                )
            object.__setattr__(
                self,
                "resolved_bindings",
                MappingProxyType(dict(self.resolved_bindings)),
            )

    @property
    def actual_resolved(self) -> bool:
        return self.resolution_status == "resolved" and bool(self.resolved_bindings)

    def binding(self, kind: str) -> Any:
        try:
            return self.resolved_bindings[str(kind)]
        except KeyError as exc:
            raise ModelContractError(
                f"Resolved plan has no callable binding for {kind!r}."
            ) from exc

    @property
    def hamiltonian_builder(self) -> Any:
        return self.binding("hamiltonian")

    @property
    def sector_checker(self) -> Any:
        return self.binding("sector")

    @property
    def mapping_handler(self) -> Any:
        return self.binding("mapping")

    @property
    def state_preparation_handler(self) -> Any:
        return self.binding("state_preparation")

    @property
    def ansatz_factory(self) -> Any:
        return self.binding("ansatz")

    @property
    def measurement_builder(self) -> Any:
        return self.binding("measurement")

    @property
    def reference_solver(self) -> Any:
        return self.binding("reference")

    @property
    def resource_assessor(self) -> Any:
        return self.binding("resource")

    @property
    def runtime_handler(self) -> Any:
        return self.binding("runtime")

    @property
    def interpretation_handler(self) -> Any:
        return self.binding("interpretation")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "plan_id": self.plan_id,
            "model_contract_id": self.model_contract_id,
            "model_version": self.model_version,
            "model_instance_id": self.model_instance_id,
            "task_id": self.task_id,
            "policy_bindings": _thaw(self.policy_bindings),
            "capability_report": self.capability_report.to_dict(),
            "resolution_status": self.resolution_status,
            "actual_resolved": self.actual_resolved,
            "preflight_resources": _thaw(self.preflight_resources),
            "callable_payload_withheld": True,
        }


@dataclass(frozen=True)
class QuantumRealizationArtifact:
    """Resolved, model-aware quantum realization consumed by the shared runtime.

    The executable ``ProblemArtifact`` remains the runtime payload for backward
    compatibility, while this object makes the mapping, ordering, sector,
    initial-state, ansatz, measurement, resource, and reference contracts
    explicit and inspectable.
    """

    realization_id: str
    model_id: str
    model_version: str
    task_id: str
    runtime_policy_id: str
    problem_artifact_id: str
    contract_snapshot: Mapping[str, Any]
    instance_snapshot: Mapping[str, Any]
    capability_report: CapabilityReport
    runtime_artifact: Any = field(repr=False, compare=False)
    qubit_hamiltonian_payload: Any = field(default=None, repr=False, compare=False)
    initial_state_circuit: Any = field(default=None, repr=False, compare=False)
    parameterized_ansatz_circuit: Any = field(default=None, repr=False, compare=False)
    measurement_plan_payload: Any = field(default=None, repr=False, compare=False)
    resolved_plan_snapshot: Mapping[str, Any] = field(default_factory=dict)
    mapping_metadata: Mapping[str, Any] = field(default_factory=dict)
    orbital_to_qubit_order: Mapping[str, Any] = field(default_factory=dict)
    preserved_symmetries: Tuple[str, ...] = field(default_factory=tuple)
    initial_state: Mapping[str, Any] = field(default_factory=dict)
    parameter_schema: Mapping[str, Any] = field(default_factory=dict)
    resource_report: Mapping[str, Any] = field(default_factory=dict)
    reference_declaration: Mapping[str, Any] = field(default_factory=dict)
    task_contract_snapshot: Mapping[str, Any] = field(default_factory=dict)
    task_instance_snapshot: Mapping[str, Any] = field(default_factory=dict)
    model_task_plan_snapshot: Mapping[str, Any] = field(default_factory=dict)
    task_execution_plan: Mapping[str, Any] = field(default_factory=dict)
    model_task_plan: Any = field(default=None, repr=False, compare=False)

    # Step-2 canonical-IR identities.  These are carried directly so no
    # downstream consumer has to re-derive scientific choices from registries,
    # request fields, or UI metadata.
    encoding_context_id: str = ""
    mapping_policy_id: str = ""
    state_preparation_policy_id: Optional[str] = None
    ansatz_policy_id: Optional[str] = None
    measurement_policy_id: Optional[str] = None
    reference_policy_id: Optional[str] = None
    controller_id: str = ""
    scientific_fingerprint: str = ""
    acceptance_certificate: Mapping[str, Any] = field(default_factory=dict)
    run_controls: Mapping[str, Any] = field(default_factory=dict)
    request_summary: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = QUANTUM_REALIZATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require_nonempty("realization_id", self.realization_id)
        _require_nonempty("problem_artifact_id", self.problem_artifact_id)
        for name in (
            "contract_snapshot",
            "instance_snapshot",
            "resolved_plan_snapshot",
            "mapping_metadata",
            "orbital_to_qubit_order",
            "initial_state",
            "parameter_schema",
            "resource_report",
            "reference_declaration",
            "task_contract_snapshot",
            "task_instance_snapshot",
            "model_task_plan_snapshot",
            "task_execution_plan",
            "acceptance_certificate",
            "run_controls",
            "request_summary",
        ):
            object.__setattr__(self, name, _freeze(getattr(self, name)))
        object.__setattr__(
            self, "preserved_symmetries", tuple(str(v) for v in self.preserved_symmetries)
        )

    @property
    def qubit_hamiltonian(self) -> Any:
        return (
            self.qubit_hamiltonian_payload
            if self.qubit_hamiltonian_payload is not None
            else self.runtime_artifact.hamiltonian_payload
        )

    @property
    def n_qubits(self) -> int:
        return int(self.runtime_artifact.n_qubits)

    @property
    def target_sector(self) -> Any:
        return self.runtime_artifact.target_sector

    @property
    def initial_state_executable(self) -> Any:
        return self.initial_state_circuit

    @property
    def parameterized_ansatz(self) -> Any:
        return (
            self.parameterized_ansatz_circuit
            if self.parameterized_ansatz_circuit is not None
            else self.runtime_artifact.ansatz_template
        )

    @property
    def measurement_plan(self) -> Any:
        return (
            self.measurement_plan_payload
            if self.measurement_plan_payload is not None
            else self.runtime_artifact.measurement_plan
        )

    @property
    def problem_artifact(self) -> Any:
        """Compatibility runtime projection carried by the canonical IR."""
        return self.runtime_artifact

    @property
    def task_plan(self) -> Any:
        if self.model_task_plan is None:
            raise ModelContractError(
                "Canonical realization does not carry a ResolvedModelTaskPlan."
            )
        return self.model_task_plan

    @property
    def task_contract(self) -> Any:
        return self.task_plan.task_contract

    @property
    def task_instance(self) -> Any:
        return self.task_plan.task_instance

    @property
    def task_execution(self) -> Any:
        return self.task_plan.task_execution_plan

    @property
    def controller(self) -> Any:
        return self.task_plan.controller

    @property
    def verification_handler(self) -> Any:
        return self.task_plan.verification_handler

    @property
    def interpretation_handler(self) -> Any:
        return self.task_plan.interpretation_handler

    @property
    def cell_snapshot(self) -> Mapping[str, Any]:
        return self.task_plan.cell_snapshot

    @property
    def backend_execution_required(self) -> bool:
        declaration = self.cell_snapshot.get("resolved_declarations", {}).get(
            "circuit", {}
        )
        return bool(declaration.get("backend_execution_required", True))

    def validate_bridge(self) -> None:
        artifact = self.runtime_artifact
        for attribute in (
            "artifact_id",
            "hamiltonian_payload",
            "ansatz_template",
            "measurement_plan",
            "target_sector",
            "mapping",
            "n_qubits",
        ):
            if not hasattr(artifact, attribute):
                raise ModelContractError(
                    f"Runtime artifact is missing required attribute {attribute!r}."
                )
        if str(artifact.artifact_id) != self.problem_artifact_id:
            raise ModelContractError(
                "QuantumRealizationArtifact problem_artifact_id does not match "
                "the wrapped runtime artifact."
            )
        if not self.capability_report.may_enter_runtime:
            raise ModelContractError(
                "A non-executable CapabilityReport cannot enter the runtime."
            )
        if self.n_qubits <= 0:
            raise ModelContractError("Quantum realization must contain qubits.")
        if not self.mapping_metadata:
            raise ModelContractError("Mapping metadata must be explicit.")
        if not self.initial_state:
            raise ModelContractError("Initial-state metadata must be explicit.")
        if not self.parameter_schema:
            raise ModelContractError("Parameter schema must be explicit.")
        if not self.resource_report:
            raise ModelContractError("Resource assessment must be explicit.")
        if self.qubit_hamiltonian is not artifact.hamiltonian_payload:
            raise ModelContractError("Explicit qubit Hamiltonian does not match runtime artifact.")
        if self.measurement_plan is not artifact.measurement_plan:
            raise ModelContractError("Explicit measurement plan does not match runtime artifact.")
        if self.parameterized_ansatz is not artifact.ansatz_template:
            raise ModelContractError("Explicit parameterized ansatz does not match runtime artifact.")
        if self.model_task_plan is not None:
            if not self.model_task_plan.actual_resolved:
                raise ModelContractError(
                    "Canonical realization must carry one actual resolved model-task plan."
                )
            for name in (
                "encoding_context_id",
                "mapping_policy_id",
                "controller_id",
                "scientific_fingerprint",
            ):
                if not str(getattr(self, name) or "").strip():
                    raise ModelContractError(
                        f"Canonical realization is missing direct identity {name!r}."
                    )
            if not self.acceptance_certificate:
                raise ModelContractError(
                    "Canonical realization must carry its acceptance certificate."
                )
            if str(self.model_task_plan.model_plan.model_contract_id) != self.model_id:
                raise ModelContractError(
                    "Canonical realization model identity differs from the resolved plan."
                )
            if str(self.model_task_plan.task_contract.task_id) != self.task_id:
                raise ModelContractError(
                    "Canonical realization task identity differs from the resolved plan."
                )
            expected_fingerprint = scientific_identity_fingerprint(
                model_id=self.model_id,
                task_id=self.task_id,
                target_sector=self.target_sector,
                encoding_context_id=self.encoding_context_id,
                mapping_policy_id=self.mapping_policy_id,
                state_preparation_policy_id=self.state_preparation_policy_id,
                ansatz_policy_id=self.ansatz_policy_id,
                measurement_policy_id=self.measurement_policy_id,
                reference_policy_id=self.reference_policy_id,
            )
            if expected_fingerprint != self.scientific_fingerprint:
                raise ModelContractError(
                    "Canonical realization scientific fingerprint does not match its direct identities."
                )
            certificate_contexts = self.acceptance_certificate.get(
                "policy_encoding_contexts", {}
            )
            if certificate_contexts and set(certificate_contexts.values()) != {
                self.encoding_context_id
            }:
                raise ModelContractError(
                    "Mapping, state, ansatz, measurement, reference, and task operators "
                    "must share one encoding context."
                )

    def to_public_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "realization_id": self.realization_id,
            "model_id": self.model_id,
            "model_version": self.model_version,
            "task_id": self.task_id,
            "runtime_policy_id": self.runtime_policy_id,
            "problem_artifact_id": self.problem_artifact_id,
            "n_qubits": self.n_qubits,
            "target_sector": _thaw(self.target_sector),
            "contract_snapshot": _thaw(self.contract_snapshot),
            "instance_snapshot": _thaw(self.instance_snapshot),
            "resolved_plan_snapshot": _thaw(self.resolved_plan_snapshot),
            "capability_report": self.capability_report.to_dict(),
            "mapping_metadata": _thaw(self.mapping_metadata),
            "orbital_to_qubit_order": _thaw(self.orbital_to_qubit_order),
            "preserved_symmetries": list(self.preserved_symmetries),
            "initial_state": _thaw(self.initial_state),
            "parameter_schema": _thaw(self.parameter_schema),
            "measurement_plan_summary": {
                "identity_coefficient": float(
                    self.runtime_artifact.measurement_plan.get("identity_coefficient", 0.0)
                ),
                "group_count": len(
                    self.runtime_artifact.measurement_plan.get("groups", [])
                ),
            },
            "resource_report": _thaw(self.resource_report),
            "reference_declaration": _thaw(self.reference_declaration),
            "task_contract_snapshot": _thaw(self.task_contract_snapshot),
            "task_instance_snapshot": _thaw(self.task_instance_snapshot),
            "model_task_plan_snapshot": _thaw(self.model_task_plan_snapshot),
            "task_execution_plan": _thaw(self.task_execution_plan),
            "encoding_context_id": self.encoding_context_id,
            "mapping_policy_id": self.mapping_policy_id,
            "state_preparation_policy_id": self.state_preparation_policy_id,
            "ansatz_policy_id": self.ansatz_policy_id,
            "measurement_policy_id": self.measurement_policy_id,
            "reference_policy_id": self.reference_policy_id,
            "controller_id": self.controller_id,
            "scientific_fingerprint": self.scientific_fingerprint,
            "acceptance_certificate": _thaw(self.acceptance_certificate),
            "run_controls": _thaw(self.run_controls),
            "request_summary": _thaw(self.request_summary),
            "runtime_payload_withheld": True,
        }


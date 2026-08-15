"""Domain-neutral task contracts for the QCOL model × task architecture.

Task contracts describe *what a scientific task requires*.  They contain stable
policy identifiers, not executable callables.  A model-task resolver later
checks those requirements against a ModelContract and binds certified task
implementations.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Dict, Mapping, Optional, Tuple

from ..model_contracts import CapabilityCheck, ModelContractError, ResolvedModelPlan

TASK_CONTRACT_SCHEMA_VERSION = "qcol-task-contract/1.0"
TASK_INSTANCE_SCHEMA_VERSION = "qcol-task-instance/1.0"
TASK_EXECUTION_PLAN_SCHEMA_VERSION = "qcol-task-execution-plan/1.0"
MODEL_TASK_PLAN_SCHEMA_VERSION = "qcol-resolved-model-task-plan/1.0"
MODEL_TASK_CAPABILITY_SCHEMA_VERSION = "qcol-model-task-capability/1.0"

TASK_SUPPORT_STATUSES = {"registered", "execution_ready", "acceptance_verified", "future"}
TASK_EXECUTION_STATUSES = {"not_implemented", "planned", "experimental", "execution_ready", "acceptance_verified"}
MODEL_TASK_CELL_STATUSES = {
    "acceptance_verified",
    "execution_ready",
    "experimental",
    "planned",
    "registered",
    "not_applicable",
    "unsupported",
}


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(k): _freeze(v) for k, v in value.items()})
    if isinstance(value, (list, tuple, set, frozenset)):
        return tuple(_freeze(v) for v in value)
    return deepcopy(value)


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _thaw(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [_thaw(v) for v in value]
    return deepcopy(value)


def _require_text(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ModelContractError(f"{name} must be a non-empty string.")


@dataclass(frozen=True)
class TaskParameterSpec:
    key: str
    label: str
    kind: str
    default: Any = None
    required: bool = False
    allowed_values: Tuple[Any, ...] = field(default_factory=tuple)
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    help_text: str = ""
    order: int = 0

    def __post_init__(self) -> None:
        _require_text("task parameter key", self.key)
        _require_text("task parameter label", self.label)
        _require_text("task parameter kind", self.kind)
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ModelContractError(f"Task parameter {self.key!r} has minimum > maximum.")
        object.__setattr__(self, "default", _freeze(self.default))
        object.__setattr__(self, "allowed_values", tuple(_freeze(v) for v in self.allowed_values))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "kind": self.kind,
            "default": _thaw(self.default),
            "required": bool(self.required),
            "allowed_values": _thaw(self.allowed_values),
            "minimum": self.minimum,
            "maximum": self.maximum,
            "help_text": self.help_text,
            "order": int(self.order),
        }


@dataclass(frozen=True)
class TaskContract:
    """Declarative contract for one task/algorithm column."""

    task_id: str
    task_version: str
    label: str
    description: str
    task_family: str
    objective: str
    required_model_capabilities: Tuple[str, ...]
    required_model_observables: Tuple[str, ...]
    parameter_schema: Tuple[TaskParameterSpec, ...]

    controller_policy_id: str
    circuit_policy_id: str
    measurement_policy_id: str
    reconstruction_policy_id: str
    termination_policy_id: str
    reference_policy_id: str
    verification_policy_id: str
    interpretation_policy_id: str

    reference_type: str
    verification_metric: str
    aliases: Tuple[str, ...] = field(default_factory=tuple)
    assumptions: Tuple[str, ...] = field(default_factory=tuple)
    limitations: Tuple[str, ...] = field(default_factory=tuple)
    support_status: str = "registered"
    execution_status: str = "not_implemented"
    acceptance_suite_id: Optional[str] = None
    schema_version: str = TASK_CONTRACT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name, value in (
            ("task_id", self.task_id),
            ("task_version", self.task_version),
            ("label", self.label),
            ("description", self.description),
            ("task_family", self.task_family),
            ("objective", self.objective),
            ("reference_type", self.reference_type),
            ("verification_metric", self.verification_metric),
        ):
            _require_text(name, value)
        if self.support_status not in TASK_SUPPORT_STATUSES:
            raise ModelContractError(f"Unsupported task support status {self.support_status!r}.")
        if self.execution_status not in TASK_EXECUTION_STATUSES:
            raise ModelContractError(f"Unsupported task execution status {self.execution_status!r}.")
        keys = [item.key for item in self.parameter_schema]
        if len(keys) != len(set(keys)):
            raise ModelContractError("Task parameter schema contains duplicate keys.")
        policy_ids = (
            self.controller_policy_id,
            self.circuit_policy_id,
            self.measurement_policy_id,
            self.reconstruction_policy_id,
            self.termination_policy_id,
            self.reference_policy_id,
            self.verification_policy_id,
            self.interpretation_policy_id,
        )
        if self.execution_status in {"execution_ready", "acceptance_verified"}:
            for policy_id in policy_ids:
                _require_text("task policy ID", policy_id)
            if not self.acceptance_suite_id:
                raise ModelContractError("Executable tasks must declare acceptance_suite_id.")
        object.__setattr__(self, "required_model_capabilities", tuple(str(v) for v in self.required_model_capabilities))
        object.__setattr__(self, "required_model_observables", tuple(str(v) for v in self.required_model_observables))
        object.__setattr__(self, "aliases", tuple(str(v) for v in self.aliases))
        object.__setattr__(self, "assumptions", tuple(str(v) for v in self.assumptions))
        object.__setattr__(self, "limitations", tuple(str(v) for v in self.limitations))

    @property
    def executable(self) -> bool:
        return self.execution_status in {"execution_ready", "acceptance_verified", "experimental"}

    @property
    def all_ids(self) -> Tuple[str, ...]:
        return (self.task_id, *self.aliases)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "task_id": self.task_id,
            "task_version": self.task_version,
            "label": self.label,
            "description": self.description,
            "task_family": self.task_family,
            "objective": self.objective,
            "required_model_capabilities": list(self.required_model_capabilities),
            "required_model_observables": list(self.required_model_observables),
            "parameter_schema": [item.to_dict() for item in sorted(self.parameter_schema, key=lambda x: x.order)],
            "policies": {
                "controller": self.controller_policy_id,
                "circuit": self.circuit_policy_id,
                "measurement": self.measurement_policy_id,
                "reconstruction": self.reconstruction_policy_id,
                "termination": self.termination_policy_id,
                "reference": self.reference_policy_id,
                "verification": self.verification_policy_id,
                "interpretation": self.interpretation_policy_id,
            },
            "reference_type": self.reference_type,
            "verification_metric": self.verification_metric,
            "aliases": list(self.aliases),
            "assumptions": list(self.assumptions),
            "limitations": list(self.limitations),
            "support_status": self.support_status,
            "execution_status": self.execution_status,
            "executable": self.executable,
            "acceptance_suite_id": self.acceptance_suite_id,
        }


@dataclass(frozen=True)
class TaskInstance:
    task_id: str
    task_version: str
    parameters: Mapping[str, Any] = field(default_factory=dict)
    requested_observables: Tuple[str, ...] = field(default_factory=tuple)
    source_metadata: Mapping[str, Any] = field(default_factory=dict)
    instance_id: Optional[str] = None
    schema_version: str = TASK_INSTANCE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require_text("task_id", self.task_id)
        _require_text("task_version", self.task_version)
        object.__setattr__(self, "parameters", _freeze(self.parameters))
        object.__setattr__(self, "requested_observables", tuple(str(v) for v in self.requested_observables))
        object.__setattr__(self, "source_metadata", _freeze(self.source_metadata))

    def validate_against(self, contract: TaskContract) -> None:
        if self.task_id != contract.task_id:
            raise ModelContractError(
                f"TaskInstance {self.task_id!r} does not match TaskContract {contract.task_id!r}."
            )
        if self.task_version != contract.task_version:
            raise ModelContractError("TaskInstance version does not match TaskContract version.")
        declared = {item.key for item in contract.parameter_schema}
        unknown = set(self.parameters) - declared
        if unknown:
            raise ModelContractError(f"TaskInstance contains undeclared parameters: {sorted(unknown)}")
        for spec in contract.parameter_schema:
            if spec.required and spec.key not in self.parameters:
                raise ModelContractError(f"Required task parameter {spec.key!r} is missing.")
            value = self.parameters.get(spec.key, spec.default)
            if spec.allowed_values:
                if spec.kind in {"vector", "list", "sequence"}:
                    try:
                        invalid = [item for item in value if item not in spec.allowed_values]
                    except TypeError as exc:
                        raise ModelContractError(
                            f"Task parameter {spec.key!r} must be a sequence."
                        ) from exc
                    if invalid:
                        raise ModelContractError(
                            f"Task parameter {spec.key!r} contains unsupported values {invalid!r}; "
                            f"allowed={list(spec.allowed_values)!r}."
                        )
                elif value not in spec.allowed_values:
                    raise ModelContractError(
                        f"Task parameter {spec.key!r} must be one of {list(spec.allowed_values)!r}."
                    )
            if value is not None and spec.kind in {"integer", "number"}:
                number = float(value)
                if spec.minimum is not None and number < spec.minimum:
                    raise ModelContractError(f"Task parameter {spec.key!r} is below its minimum.")
                if spec.maximum is not None and number > spec.maximum:
                    raise ModelContractError(f"Task parameter {spec.key!r} is above its maximum.")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "instance_id": self.instance_id,
            "task_id": self.task_id,
            "task_version": self.task_version,
            "parameters": _thaw(self.parameters),
            "requested_observables": list(self.requested_observables),
            "source_metadata": _thaw(self.source_metadata),
        }


@dataclass(frozen=True)
class TaskExecutionPlan:
    controller_policy_id: str
    circuit_policy_id: str
    measurement_policy_id: str
    reconstruction_policy_id: str
    termination_policy_id: str
    reference_policy_id: str
    verification_policy_id: str
    interpretation_policy_id: str
    controller_structure: str
    controller_stage: str
    controller_message: str
    result_kind: str
    schema_version: str = TASK_EXECUTION_PLAN_SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "controller_policy_id": self.controller_policy_id,
            "circuit_policy_id": self.circuit_policy_id,
            "measurement_policy_id": self.measurement_policy_id,
            "reconstruction_policy_id": self.reconstruction_policy_id,
            "termination_policy_id": self.termination_policy_id,
            "reference_policy_id": self.reference_policy_id,
            "verification_policy_id": self.verification_policy_id,
            "interpretation_policy_id": self.interpretation_policy_id,
            "controller_structure": self.controller_structure,
            "controller_stage": self.controller_stage,
            "controller_message": self.controller_message,
            "result_kind": self.result_kind,
        }


@dataclass(frozen=True)
class ModelTaskCapabilityReport:
    model_id: str
    task_id: str
    cell_status: str
    overall_status: str
    checks: Tuple[CapabilityCheck, ...]
    reasons: Tuple[str, ...] = field(default_factory=tuple)
    schema_version: str = MODEL_TASK_CAPABILITY_SCHEMA_VERSION

    @property
    def may_enter_runtime(self) -> bool:
        return self.overall_status in {"verified", "executable", "experimental"}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "model_id": self.model_id,
            "task_id": self.task_id,
            "cell_status": self.cell_status,
            "overall_status": self.overall_status,
            "may_enter_runtime": self.may_enter_runtime,
            "checks": [item.to_dict() for item in self.checks],
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class ResolvedModelTaskPlan:
    plan_id: str
    model_plan: ResolvedModelPlan
    task_contract: TaskContract
    task_instance: TaskInstance
    cell_snapshot: Mapping[str, Any]
    task_policy_bindings: Mapping[str, str]
    task_execution_plan: TaskExecutionPlan
    capability_report: ModelTaskCapabilityReport
    resolved_task_bindings: Mapping[str, Any] = field(default_factory=dict, repr=False, compare=False)
    resolution_status: str = "resolved"
    schema_version: str = MODEL_TASK_PLAN_SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "cell_snapshot", _freeze(self.cell_snapshot))
        object.__setattr__(self, "task_policy_bindings", _freeze(self.task_policy_bindings))
        if self.resolution_status == "resolved":
            missing = set(self.task_policy_bindings) - set(self.resolved_task_bindings)
            if missing:
                raise ModelContractError(f"ResolvedModelTaskPlan is missing task callables: {sorted(missing)}")
            bad = [key for key, value in self.resolved_task_bindings.items() if not callable(value)]
            if bad:
                raise ModelContractError(f"Task bindings are not callable: {sorted(bad)}")
            object.__setattr__(self, "resolved_task_bindings", MappingProxyType(dict(self.resolved_task_bindings)))

    @property
    def actual_resolved(self) -> bool:
        return self.resolution_status == "resolved" and bool(self.resolved_task_bindings)

    def task_binding(self, kind: str) -> Any:
        try:
            return self.resolved_task_bindings[str(kind)]
        except KeyError as exc:
            raise ModelContractError(f"No resolved task binding for {kind!r}.") from exc

    @property
    def controller(self) -> Any:
        return self.task_binding("controller")

    @property
    def verification_handler(self) -> Any:
        return self.task_binding("verification")

    @property
    def interpretation_handler(self) -> Any:
        return self.task_binding("interpretation")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "plan_id": self.plan_id,
            "model_plan": self.model_plan.to_dict(),
            "task_contract": self.task_contract.to_dict(),
            "task_instance": self.task_instance.to_dict(),
            "cell_snapshot": _thaw(self.cell_snapshot),
            "task_policy_bindings": _thaw(self.task_policy_bindings),
            "task_execution_plan": self.task_execution_plan.to_dict(),
            "capability_report": self.capability_report.to_dict(),
            "resolution_status": self.resolution_status,
            "actual_resolved": self.actual_resolved,
            "callable_payload_withheld": True,
        }

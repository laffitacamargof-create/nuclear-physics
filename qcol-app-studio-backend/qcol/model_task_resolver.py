"""Resolve one ModelInstance × TaskInstance cell into an executable plan."""
from __future__ import annotations

from typing import Any, Dict, Mapping, Optional
from uuid import uuid4

from .builtin_task_policies import register_builtin_task_policies
from .model_contracts import CapabilityCheck, ModelContractError, ModelInstance
from .model_task_matrix import get_model_task_cell
from .resolver import resolve_model
from .task_contracts import (
    ModelTaskCapabilityReport,
    ResolvedModelTaskPlan,
    TaskExecutionPlan,
    TaskInstance,
)
from .task_policy_registries import TASK_REGISTRIES
from .plugin_registry import get_model_plugin, get_task_plugin

TASK_POLICY_FIELD_MAP = {
    "controller": "controller_policy_id",
    "circuit": "circuit_policy_id",
    "measurement": "measurement_policy_id",
    "reconstruction": "reconstruction_policy_id",
    "termination": "termination_policy_id",
    "reference": "reference_policy_id",
    "verification": "verification_policy_id",
    "interpretation": "interpretation_policy_id",
}


def _cell_to_overall(status: str) -> str:
    return {
        "acceptance_verified": "verified",
        "execution_ready": "executable",
        "experimental": "experimental",
        "planned": "recognized_not_executable",
        "registered": "recognized_not_executable",
        "not_applicable": "unsupported",
        "unsupported": "unsupported",
    }[status]



def resolve_model_task(
    model_instance: ModelInstance,
    task_instance: TaskInstance,
    *,
    request_metadata: Optional[Mapping[str, Any]] = None,
) -> ResolvedModelTaskPlan:
    register_builtin_task_policies()
    model_plugin = get_model_plugin(model_instance.model_id)
    task_plugin = get_task_plugin(task_instance.task_id)
    task_contract = task_plugin.contract
    task_instance.validate_against(task_contract)
    cell = get_model_task_cell(model_instance.model_id, task_contract.task_id)
    checks = []
    reasons = []

    # The model contract is resolved first.  It remains the owner of model-specific
    # Hamiltonian, mapping, sector, state, ansatz, and reference capabilities.
    model_plan = resolve_model(model_instance, request_metadata=request_metadata)
    checks.append(CapabilityCheck(
        key="model_plan",
        status="pass" if model_plan.capability_report.may_enter_runtime else "fail",
        message=(
            "Model capabilities resolved successfully."
            if model_plan.capability_report.may_enter_runtime
            else "Model capabilities did not authorize runtime entry."
        ),
        details={
            "model_status": model_plan.capability_report.overall_status,
            "model_reasons": list(model_plan.capability_report.reasons),
        },
    ))
    if not model_plan.capability_report.may_enter_runtime:
        if model_plan.capability_report.reasons:
            reasons.extend(
                f"model_plan:{reason}"
                for reason in model_plan.capability_report.reasons
            )
        else:
            failed_model_checks = [
                check.key
                for check in model_plan.capability_report.checks
                if check.status == "fail"
            ]
            reasons.append(
                "model_plan_not_runtime_eligible"
                + (":" + ",".join(failed_model_checks) if failed_model_checks else "")
            )

    if model_plugin.contract is not model_plan.contract:
        raise ModelContractError("Resolver model plan does not match the selected ModelPlugin contract.")
    available = set(model_plugin.capabilities)
    missing_capabilities = sorted(set(task_contract.required_model_capabilities) - available)
    if missing_capabilities:
        checks.append(CapabilityCheck(
            key="task_requires_model_capabilities",
            status="fail",
            message=f"Model does not provide required task capabilities: {missing_capabilities}",
        ))
        reasons.append("missing_model_capabilities")
    else:
        checks.append(CapabilityCheck(
            key="task_requires_model_capabilities",
            status="pass",
            message="Task requirements are a subset of the model's declared capabilities.",
            details={"required": list(task_contract.required_model_capabilities)},
        ))

    requested = set(task_instance.requested_observables)
    supported = set(model_plan.contract.supported_observables)
    observable_ok = task_plugin.observables_compatible(
        requested=requested,
        supported=supported,
    )
    checks.append(CapabilityCheck(
        key="observable_compatibility",
        status="pass" if observable_ok else "fail",
        message=(
            "Requested task observables are declared by the model contract."
            if observable_ok else
            "Requested task observables are not declared by the model contract."
        ),
        details={"requested": sorted(requested), "supported": sorted(supported)},
    ))
    if not observable_ok:
        reasons.append("unsupported_observable")

    task_policy_ids: Dict[str, str] = {
        kind: getattr(task_contract, field)
        for kind, field in TASK_POLICY_FIELD_MAP.items()
    }
    resolved: Dict[str, Any] = {}
    for kind, policy_id in task_policy_ids.items():
        registry = TASK_REGISTRIES[kind]
        if not registry.has(policy_id):
            checks.append(CapabilityCheck(
                key=f"task_policy.{kind}",
                status="fail",
                message=f"Task policy {policy_id!r} is not registered.",
            ))
            reasons.append(f"missing_task_policy:{kind}")
            continue
        binding = registry.binding(policy_id)
        if not binding.executable:
            checks.append(CapabilityCheck(
                key=f"task_policy.{kind}",
                status="review",
                message=f"Task policy {policy_id!r} is registered but not implemented.",
                details=binding.to_dict(),
            ))
            reasons.append(f"task_policy_not_implemented:{kind}")
            continue
        try:
            resolved[kind] = registry.resolve(policy_id)
            checks.append(CapabilityCheck(
                key=f"task_policy.{kind}",
                status="pass",
                message=f"Resolved task {kind} policy {policy_id!r}.",
                details={"import_path": binding.import_path},
            ))
        except Exception as exc:
            checks.append(CapabilityCheck(
                key=f"task_policy.{kind}",
                status="fail",
                message=f"Could not import task policy {policy_id!r}: {type(exc).__name__}: {exc}",
            ))
            reasons.append(f"task_policy_import_failed:{kind}")

    cell_overall = _cell_to_overall(cell.status)
    checks.append(CapabilityCheck(
        key="cell_acceptance_gate",
        status="pass" if cell.status == "acceptance_verified" else ("review" if cell.runnable else "fail"),
        message=(
            "This model × task cell passed its own acceptance suite."
            if cell.status == "acceptance_verified"
            else (
                "This cell is runnable but has not passed full cell-specific acceptance."
                if cell.runnable else
                "This model × task cell is registered but not executable."
            )
        ),
        details=cell.to_dict(),
    ))

    fatal = (
        not model_plan.capability_report.may_enter_runtime
        or missing_capabilities
        or not observable_ok
        or len(resolved) != len(task_policy_ids)
        or not cell.runnable
    )
    overall = "recognized_not_executable" if fatal and cell_overall != "unsupported" else cell_overall
    resolution_status = "unresolved" if fatal else "resolved"

    report = ModelTaskCapabilityReport(
        model_id=model_instance.model_id,
        task_id=task_contract.task_id,
        cell_status=cell.status,
        overall_status=overall,
        checks=tuple(checks),
        reasons=tuple(reasons),
    )

    # Inspectable task execution declarations.  These do not execute the task.
    if resolution_status == "resolved":
        circuit_decl = resolved["circuit"](model_plan, task_instance)
        measurement_decl = resolved["measurement"](model_plan, task_instance)
        reconstruction_decl = resolved["reconstruction"](model_plan, task_instance)
        termination_decl = resolved["termination"](model_plan, task_instance)
        reference_decl = resolved["reference"](model_plan, task_instance)
        controller_structure = task_plugin.controller_structure
        result_kind = str(reconstruction_decl.get("result_kind", task_contract.task_family))
        # Declarations are retained in the cell snapshot to keep the plan compact.
        cell_snapshot = {
            **cell.to_dict(),
            "resolved_declarations": {
                "circuit": circuit_decl,
                "measurement": measurement_decl,
                "reconstruction": reconstruction_decl,
                "termination": termination_decl,
                "reference": reference_decl,
            },
        }
    else:
        controller_structure = "unresolved"
        result_kind = "unresolved"
        cell_snapshot = cell.to_dict()

    execution_plan = TaskExecutionPlan(
        controller_policy_id=task_contract.controller_policy_id,
        circuit_policy_id=task_contract.circuit_policy_id,
        measurement_policy_id=task_contract.measurement_policy_id,
        reconstruction_policy_id=task_contract.reconstruction_policy_id,
        termination_policy_id=task_contract.termination_policy_id,
        reference_policy_id=task_contract.reference_policy_id,
        verification_policy_id=task_contract.verification_policy_id,
        interpretation_policy_id=task_contract.interpretation_policy_id,
        controller_structure=controller_structure,
        controller_stage=(task_plugin.controller_stage if resolution_status == "resolved" else "task"),
        controller_message=(task_plugin.controller_message if resolution_status == "resolved" else "Task is unresolved."),
        result_kind=result_kind,
    )

    return ResolvedModelTaskPlan(
        plan_id=f"model-task-plan-{uuid4().hex[:12]}",
        model_plan=model_plan,
        task_contract=task_contract,
        task_instance=task_instance,
        cell_snapshot=cell_snapshot,
        task_policy_bindings=task_policy_ids,
        task_execution_plan=execution_plan,
        capability_report=report,
        resolved_task_bindings=resolved if resolution_status == "resolved" else {},
        resolution_status=resolution_status,
    )


def resolve_model_task_request(request: Mapping[str, Any]) -> ResolvedModelTaskPlan:
    """Resolve a raw request after enforcing model/task/run parameter scopes."""
    from .model_instance_adapters import instance_from_request
    from .request_boundaries import normalize_request_boundaries
    from .task_instance_adapters import task_instance_from_request

    bounded_request = normalize_request_boundaries(request)
    model_instance = instance_from_request(bounded_request)
    task_instance = task_instance_from_request(bounded_request)
    return resolve_model_task(
        model_instance,
        task_instance,
        request_metadata=bounded_request,
    )

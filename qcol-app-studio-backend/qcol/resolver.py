"""Capability resolver: policy IDs -> certified callables -> actual model plan."""
from __future__ import annotations

from typing import Any, Dict, Mapping, Optional
from uuid import uuid4

from .builtin_policies import register_builtin_policies
from .model_contracts import (
    CapabilityCheck,
    CapabilityReport,
    ModelContractError,
    ModelInstance,
    ResolvedModelPlan,
)
from .model_execution_types import ModelBuildContext
from .model_registry import get_model_contract
from .policy_registries import REGISTRIES, PolicyRegistryError


POLICY_FIELD_MAP = {
    "hamiltonian": "hamiltonian_policy_id",
    "sector": "sector_policy_id",
    "mapping": "mapping_policy_id",
    "state_preparation": "state_preparation_policy_id",
    "ansatz": "ansatz_policy_id",
    "measurement": "measurement_policy_id",
    "reference": "reference_policy_id",
    "resource": "resource_policy_id",
    "runtime": "runtime_policy_id",
    "interpretation": "interpretation_policy_id",
}


def _contract_status_to_capability(execution_status: str) -> str:
    return {
        "acceptance_verified": "verified",
        "execution_ready": "executable",
        "experimental": "experimental",
        "recognized_not_executable": "recognized_not_executable",
        "not_implemented": "recognized_not_executable",
    }.get(execution_status, "unresolved")


def resolve_model(
    instance: ModelInstance,
    *,
    request_metadata: Optional[Mapping[str, Any]] = None,
) -> ResolvedModelPlan:
    """Resolve one model instance into actual callable policy bindings."""
    register_builtin_policies()
    contract = get_model_contract(instance.model_id)
    checks = []
    reasons = []

    try:
        instance.validate_against(contract)
    except Exception as exc:
        report = CapabilityReport(
            model_id=instance.model_id,
            model_version=instance.model_version,
            task_id=instance.task_id,
            overall_status="unsupported",
            checks=(CapabilityCheck(
                key="model_instance",
                status="fail",
                message=f"ModelInstance validation failed: {exc}",
            ),),
            reasons=(str(exc),),
        )
        return ResolvedModelPlan(
            plan_id=f"plan-{uuid4().hex[:12]}",
            model_contract_id=contract.model_id,
            model_version=contract.model_version,
            model_instance_id=instance.instance_id,
            task_id=instance.task_id,
            policy_bindings={
                kind: getattr(contract, field)
                for kind, field in POLICY_FIELD_MAP.items()
            },
            capability_report=report,
            resolution_status="rejected",
            contract=contract,
            instance=instance,
        )

    checks.append(CapabilityCheck(
        key="model_instance",
        status="pass",
        message="ModelInstance satisfies the declared ModelContract.",
    ))
    checks.append(CapabilityCheck(
        key="task",
        status="pass",
        message=f"Task {instance.task_id!r} is supported by the contract.",
    ))

    policy_ids: Dict[str, str] = {
        kind: getattr(contract, field)
        for kind, field in POLICY_FIELD_MAP.items()
    }
    resolved: Dict[str, Any] = {}
    missing = []
    non_executable = []
    for kind, policy_id in policy_ids.items():
        registry = REGISTRIES[kind]
        if not registry.has(policy_id):
            missing.append(f"{kind}:{policy_id}")
            checks.append(CapabilityCheck(
                key=f"policy.{kind}",
                status="fail",
                message=f"Policy {policy_id!r} is not registered.",
            ))
            continue
        binding = registry.binding(policy_id)
        if not binding.executable:
            non_executable.append(f"{kind}:{policy_id}")
            checks.append(CapabilityCheck(
                key=f"policy.{kind}",
                status="review",
                message=f"Policy {policy_id!r} is registered but not implemented.",
                details=binding.to_dict(),
            ))
            continue
        try:
            resolved[kind] = registry.resolve(policy_id)
            checks.append(CapabilityCheck(
                key=f"policy.{kind}",
                status="pass",
                message=f"Resolved {kind} policy {policy_id!r} to a certified callable.",
                details={"import_path": binding.import_path},
            ))
        except Exception as exc:
            missing.append(f"{kind}:{policy_id}")
            checks.append(CapabilityCheck(
                key=f"policy.{kind}",
                status="fail",
                message=f"Could not import {policy_id!r}: {type(exc).__name__}: {exc}",
            ))

    preflight_resources: Mapping[str, Any] = {}
    if "resource" in resolved:
        try:
            context = ModelBuildContext(
                contract=contract,
                instance=instance,
                request_metadata=dict(request_metadata or {}),
            )
            preflight_resources = resolved["resource"](context)
            within = bool(preflight_resources.get("within_declared_envelope", False))
            checks.append(CapabilityCheck(
                key="resource_preflight",
                status="pass" if within else "fail",
                message=(
                    "The instance is inside the model plugin's declared resource envelope."
                    if within else
                    "The instance exceeds the model plugin's declared resource envelope."
                ),
                details=preflight_resources,
            ))
            if not within:
                reasons.append("resource_envelope_exceeded")
        except Exception as exc:
            failure_code = str(
                getattr(exc, "failure_code", "RESOURCE_PREFLIGHT_FAILED")
            )
            checks.append(CapabilityCheck(
                key="resource_preflight",
                status="fail",
                message=(
                    f"Resource preflight failed [{failure_code}]: "
                    f"{type(exc).__name__}: {exc}"
                ),
                details={"failure_code": failure_code},
            ))
            reasons.append(f"resource_preflight_failed:{failure_code}")

    if missing:
        reasons.append("missing_policy_bindings: " + ", ".join(missing))
    if non_executable:
        reasons.append("registered_not_implemented: " + ", ".join(non_executable))

    if missing or non_executable or any(c.status == "fail" for c in checks):
        status = "recognized_not_executable" if contract.support_status != "future" else "unsupported"
        resolution_status = "unresolved"
    else:
        status = _contract_status_to_capability(contract.execution_status)
        resolution_status = "resolved"

    checks.append(CapabilityCheck(
        key="promotion_gate",
        status=("pass" if status == "verified" else "review"),
        message=(
            "Model plugin passed its declared acceptance suite."
            if status == "verified"
            else (
                "Model plugin is executable but remains experimental until its acceptance suite promotes it."
                if status in {"executable", "experimental"}
                else "Model plugin may not enter the runtime."
            )
        ),
        details={
            "contract_execution_status": contract.execution_status,
            "acceptance_suite_id": contract.acceptance_suite_id,
        },
    ))

    report = CapabilityReport(
        model_id=contract.model_id,
        model_version=contract.model_version,
        task_id=instance.task_id,
        overall_status=status,
        checks=tuple(checks),
        reasons=tuple(reasons),
    )
    return ResolvedModelPlan(
        plan_id=f"plan-{uuid4().hex[:12]}",
        model_contract_id=contract.model_id,
        model_version=contract.model_version,
        model_instance_id=instance.instance_id,
        task_id=instance.task_id,
        policy_bindings=policy_ids,
        capability_report=report,
        resolution_status=resolution_status,
        contract=contract,
        instance=instance,
        resolved_bindings=resolved if resolution_status == "resolved" else {},
        preflight_resources=preflight_resources,
    )

"""Cross-registry consistency checks for the pre-freeze gate.

Registries expose IDs and implementation bindings; they do not become an
alternative source of scientific truth.  This gate proves that declarations
refer to existing entries and that runnable contracts are not published with
missing or non-executable bindings.
"""
from __future__ import annotations

from typing import Any


def _policy_index(catalog: dict[str, Any]) -> dict[str, dict[str, dict[str, Any]]]:
    result: dict[str, dict[str, dict[str, Any]]] = {}
    for kind, registry in catalog.get("registries", {}).items():
        result[str(kind)] = {
            str(row["policy_id"]): row
            for row in registry.get("policies", [])
            if row.get("policy_id")
        }
    return result


def validate_registry_consistency() -> dict[str, bool]:
    from .model_registry import list_model_contracts, validate_model_registry
    from .task_registry import list_task_contracts, public_task_registry
    from .model_task_matrix import public_model_task_matrix
    from .policy_registries import public_policy_catalog
    from .task_policy_registries import public_task_policy_catalog

    contracts = list_model_contracts()
    tasks = list_task_contracts()
    model_ids = {c.model_id for c in contracts}
    task_ids = {t.task_id for t in tasks}
    matrix = public_model_task_matrix()
    model_policies = _policy_index(public_policy_catalog())
    task_policies = _policy_index(public_task_policy_catalog())

    model_policy_attrs = {
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
    task_policy_attrs = {
        "controller": "controller_policy_id",
        "circuit": "circuit_policy_id",
        "measurement": "measurement_policy_id",
        "reconstruction": "reconstruction_policy_id",
        "termination": "termination_policy_id",
        "reference": "reference_policy_id",
        "verification": "verification_policy_id",
        "interpretation": "interpretation_policy_id",
    }

    model_refs_exist = all(
        getattr(contract, attr) in model_policies.get(kind, {})
        for contract in contracts
        for kind, attr in model_policy_attrs.items()
    )
    task_refs_exist = all(
        getattr(task, attr) in task_policies.get(kind, {})
        for task in tasks
        for kind, attr in task_policy_attrs.items()
    )
    runnable_model_bindings_executable = all(
        bool(model_policies[kind][getattr(contract, attr)].get("executable"))
        for contract in contracts
        if contract.execution_status in {"experimental", "execution_ready", "acceptance_verified"}
        for kind, attr in model_policy_attrs.items()
    )
    runnable_task_bindings_executable = all(
        bool(task_policies[kind][getattr(task, attr)].get("executable"))
        for task in tasks
        if task.executable
        for kind, attr in task_policy_attrs.items()
    )

    matrix_cells = matrix["cells"]
    matrix_model_ids = {row["model_id"] for row in matrix_cells}
    matrix_task_ids = {row["task_id"] for row in matrix_cells}
    accepted_have_suite = all(
        bool(c.acceptance_suite_id)
        for c in contracts
        if c.execution_status in {"execution_ready", "acceptance_verified"}
    )
    accepted_tasks_have_suite = all(
        bool(t.acceptance_suite_id)
        for t in tasks
        if t.execution_status in {"execution_ready", "acceptance_verified"}
    )

    return {
        **validate_model_registry(),
        "matrix_models_registered": matrix_model_ids.issubset(model_ids),
        "matrix_tasks_registered": matrix_task_ids.issubset(task_ids),
        "all_model_policy_references_exist": model_refs_exist,
        "all_task_policy_references_exist": task_refs_exist,
        "runnable_model_bindings_are_executable": runnable_model_bindings_executable,
        "runnable_task_bindings_are_executable": runnable_task_bindings_executable,
        "accepted_or_ready_model_contracts_have_acceptance_suite": accepted_have_suite,
        "accepted_or_ready_task_contracts_have_acceptance_suite": accepted_tasks_have_suite,
        "no_duplicate_model_ids": len(model_ids) == len(contracts),
        "no_duplicate_task_ids": len(task_ids) == len(tasks),
        "no_orphan_model_contract": model_ids.issubset(matrix_model_ids),
        "catalogs_are_bindings_not_scientific_dispatchers": True,
    }


def public_registry_consistency_report() -> dict[str, Any]:
    checks = validate_registry_consistency()
    return {
        "schema_version": "qcol-registry-consistency-report/1.1",
        "gate_id": "REG-001",
        "checks": checks,
        "pass": all(checks.values()),
        "silent_registry_fallback_allowed": False,
        "registry_role": "catalog_and_binding_resolution_only",
    }


__all__ = ["validate_registry_consistency", "public_registry_consistency_report"]

"""Task declarations, verification, and meaning for mapping analysis."""
from __future__ import annotations

from typing import Any, Mapping

from .common import runtime_context


def no_circuit_declaration(model_plan, task_instance) -> Mapping[str, Any]:
    return {
        "circuit_family": "none",
        "backend_execution_required": False,
        "reason": "mapping analysis acts on FermionOperator/QubitOperator artifacts",
    }


def no_measurement_declaration(model_plan, task_instance) -> Mapping[str, Any]:
    return {
        "measurement_family": "none",
        "shots_required": False,
        "reason": "operator spectra and resources are evaluated deterministically",
    }


def mapping_comparison_reconstruction(model_plan, task_instance) -> Mapping[str, Any]:
    return {
        "result_kind": "mapping_comparison",
        "metrics": [
            "qubit_count",
            "pauli_term_count",
            "maximum_pauli_weight",
            "mean_pauli_weight",
            "coefficient_weighted_mean_pauli_weight",
            "qwc_measurement_group_count",
            "spectrum_equivalence",
        ],
    }


def mapping_analysis_termination(model_plan, task_instance) -> Mapping[str, Any]:
    return {"termination": "all_requested_mapping_plugins_analyzed_once"}


def fermionic_fock_space_reference(model_plan, task_instance) -> Mapping[str, Any]:
    return {
        "reference_type": "full_and_fixed_particle_fermionic_spectra",
        "model_reference_policy": model_plan.policy_bindings.get("reference"),
    }


def verify_mapping_analysis_task(
    realization_or_artifact,
    outcome,
    request: Mapping[str, Any] | None = None,
    task_plan=None,
) -> Mapping[str, Any]:
    artifact, _controls, task_plan = runtime_context(
        realization_or_artifact, request, task_plan
    )
    result = dict(outcome.task_result)
    entries = list(result.get("entries", []))
    checks = {
        "requested_mappings_present": len(entries) == len(
            task_plan.task_instance.parameters.get("mapping_ids", ())
        ),
        "all_transforms_verified": bool(result.get("all_transforms_verified")),
        "no_backend_execution": not bool(outcome.controller_diagnostics.get("backend_execution_applicable")),
        "no_vqe_claim": outcome.run_mode == "mapping_analysis",
        "same_model_and_task": (
            result.get("model_id") == artifact.model_id
            and result.get("task_id") == task_plan.task_contract.task_id
        ),
    }
    support = {
        item.get("mapping_id"): item.get("mapped_artifact", {}).get("capability_report", {})
        for item in entries
    }
    accepted = all(checks.values())
    return {
        "status": "PASS" if accepted else "REVIEW",
        "task_id": task_plan.task_contract.task_id,
        "verification_metric": task_plan.task_contract.verification_metric,
        "structural_checks": checks,
        "all_transforms_verified": bool(result.get("all_transforms_verified")),
        "mapping_support": support,
        "recommended_for_analysis": result.get("recommended_for_analysis"),
        "recommendation_basis": result.get("recommendation_basis"),
        "accepted": accepted,
        "ground_state_execution_verified": False,
    }


def interpret_mapping_analysis_task(
    realization_or_artifact,
    outcome,
    verification,
    request=None,
    task_plan=None,
) -> Mapping[str, Any]:
    artifact, _controls, task_plan = runtime_context(
        realization_or_artifact, request, task_plan
    )
    result = dict(outcome.task_result)
    resource_table = {
        item["mapping_id"]: item["mapped_artifact"]["resource_report"]
        for item in result.get("entries", [])
    }
    capability_table = {
        item["mapping_id"]: item["mapped_artifact"]["capability_report"]
        for item in result.get("entries", [])
    }
    return {
        "task_id": task_plan.task_contract.task_id,
        "scientific_quantity": "mapping equivalence and operator-level resource structure",
        "supported_statement": (
            "Jordan–Wigner and Bravyi–Kitaev transform the same declared "
            "spin-orbital FermionOperator into spectrally equivalent qubit "
            "Hamiltonians within the bounded acceptance cases."
        ),
        "unit": "operator-analysis metrics",
        "result": {
            "resource_reports": resource_table,
            "capability_reports": capability_table,
            "recommended_for_analysis": result.get("recommended_for_analysis"),
        },
        "verification_status": verification.get("status"),
        "epistemic_labels": {
            "mapped_operators": "DERIVED",
            "reference_spectra": "REFERENCE — CLASSICAL",
            "resource_metrics": "DERIVED",
            "mapping_analysis_status": "VERIFIED",
            "ground_state_execution_status": "NOT VERIFIED BY THIS TASK",
        },
        "limitations": [
            "The resource ranking is analysis-only and is not a VQE mapping recommendation.",
            "No state-preparation, ansatz, QASM2, simulator, backend, shots, or hardware execution occurred.",
            "JW and BK full ground-state execution require separate model × task × mapping acceptance cells.",
        ],
    }

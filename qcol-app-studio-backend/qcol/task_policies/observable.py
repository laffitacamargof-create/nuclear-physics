"""Observable-task verification and bounded interpretation."""
from __future__ import annotations

from typing import Any, Mapping

import numpy as np

from .common import runtime_context


def verify_observable_task(realization_or_artifact, outcome, request: Mapping[str, Any] | None = None, task_plan=None) -> Mapping[str, Any]:
    artifact, _controls, task_plan = runtime_context(realization_or_artifact, request, task_plan)
    result = outcome.task_result
    observed = np.asarray(result.get("occupations", []), dtype=float)
    stderr = np.asarray(result.get("occupation_standard_errors", []), dtype=float)
    reference_raw = result.get("reference_occupations")
    structural_checks = {
        "artifact_contract_valid": True,
        "observable_qasm_validated": bool(result.get("translation_check", {}).get("validated")),
        "observable_semantic_check": bool(
            result.get("translation_check", {}).get("semantic_check", {}).get("passed", True)
        ),
        "occupation_vector_length": observed.size == artifact.n_qubits,
        "occupation_sum_matches_pair_number": abs(
            float(result.get("sum_occupations", 0.0))
            - float(result.get("target_pair_number", 1))
        ) <= max(0.05, 3.0 / max(float(result.get("shots", 1)) ** 0.5, 1.0)),
    }
    if reference_raw is None:
        return {
            "status": "NOT_RUN",
            "task_id": task_plan.task_contract.task_id,
            "reason": "No model-specific observable reference is available.",
            "structural_checks": structural_checks,
            "sector_leakage": result.get("sector_leakage"),
        }

    reference = np.asarray(reference_raw, dtype=float)
    if reference.shape != observed.shape:
        return {
            "status": "FAIL",
            "task_id": task_plan.task_contract.task_id,
            "reason": "Observable reference shape does not match the measured vector.",
            "structural_checks": structural_checks,
        }
    errors = np.abs(observed - reference)
    abs_floor = float(task_plan.task_instance.parameters.get("observable_abs_floor", 0.03))
    thresholds = np.maximum(3.0 * stderr, abs_floor)
    leakage = float(result.get("sector_leakage", 1.0))
    leakage_stderr = float(result.get("sector_leakage_standard_error", 0.0))
    leakage_floor = float(task_plan.task_instance.parameters.get("sector_leakage_floor", 0.01))
    leakage_threshold = max(3.0 * leakage_stderr, leakage_floor)
    accepted = (
        all(structural_checks.values())
        and bool(np.all(errors <= thresholds))
        and leakage <= leakage_threshold
    )
    return {
        "status": "PASS" if accepted else "REVIEW",
        "task_id": task_plan.task_contract.task_id,
        "verification_metric": task_plan.task_contract.verification_metric,
        "structural_checks": structural_checks,
        "observed_occupations": observed.tolist(),
        "reference_occupations": reference.tolist(),
        "absolute_errors": errors.tolist(),
        "acceptance_thresholds": thresholds.tolist(),
        "maximum_absolute_error": float(np.max(errors)) if errors.size else None,
        "sector_leakage": leakage,
        "sector_leakage_threshold": leakage_threshold,
        "accepted": bool(accepted),
        "state_source": outcome.parameter_source,
        "not_a_vqe_result": outcome.parameter_source == "acceptance_fixture_exact_derived",
    }


def interpret_observable_task(realization_or_artifact, outcome, verification, request=None, task_plan=None) -> Mapping[str, Any]:
    artifact, _controls, task_plan = runtime_context(realization_or_artifact, request, task_plan)
    result = outcome.task_result
    return {
        "task_id": task_plan.task_contract.task_id,
        "scientific_quantity": "pair occupations across the declared one-pair levels",
        "supported_statement": (
            "The single-pass OpenQASM 2 workflow estimates the pair-occupation "
            "probability of each declared level and measures leakage from the one-pair sector."
        ),
        "unit": "dimensionless occupation probability",
        "result": {
            "occupations": result.get("occupations"),
            "occupation_standard_errors": result.get("occupation_standard_errors"),
            "sector_leakage": result.get("sector_leakage"),
        },
        "verification_status": verification.get("status"),
        "epistemic_labels": {
            "occupations": "MEASURED / DERIVED FROM COUNTS",
            "reference_occupations": "REFERENCE — CLASSICAL",
            "state_source": outcome.parameter_source,
        },
        "limitations": [
            "The acceptance fixture is exact-derived and is not a VQE convergence result."
            if outcome.parameter_source == "acceptance_fixture_exact_derived"
            else "The result applies only to the explicitly prepared parameter point.",
            "Only pair occupations in the pair-mapping one-pair route are acceptance-verified in this release.",
            "No real-hardware execution was performed.",
        ],
    }

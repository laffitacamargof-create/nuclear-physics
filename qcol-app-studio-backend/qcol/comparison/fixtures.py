"""Deterministic Phase C scenarios for tests, catalogs, and notebooks."""
from __future__ import annotations
from copy import deepcopy
from typing import Any

from .engine import build_decision_record, compare_runs
from .policies import DECLARED_METRICS_POLICY_ID, MAPPING_RESOURCE_POLICY_ID

SCENARIO_IDS = ("adopt", "reject", "inconclusive", "mapping_adopt")


def _vqe_snapshot(
    run_id: str,
    *,
    shots: int,
    standard_error: float,
    absolute_error: float,
    status: str = "PASS",
    leakage: float = 0.0,
    patch_field: str = "",
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "status": "completed",
        "evidence_available": True,
        "evidence_schema": "qcol-pipeline-evidence/1.0",
        "request": {
            "model_id": "fermion.general_spin_orbital",
            "task_id": "ground_state_energy",
            "resolved_variant_id": "realization.general_spin_orbital.ground_state.jw.wp11.v1",
            "shots": shots,
            "seed": 42,
        },
        "artifact": {
            "model_id": "fermion.general_spin_orbital",
            "n_qubits": 4,
        },
        "result": {
            "status": status,
            "task_id": "ground_state_energy",
            "shots_per_group": shots,
            "standard_error": standard_error,
            "reconstructed_energy": -0.75,
            "optimizer_converged": True,
            "verification": {
                "status": status,
                "absolute_error": absolute_error,
                "acceptance_threshold": 0.05,
                "sector_leakage": leakage,
                "sector_leakage_threshold": 1e-8,
                "evidence_complete": True,
            },
        },
        "phase_c": {"patch_field": patch_field},
    }


def _mapping_snapshot(run_id: str, mapping_id: str, metrics: dict[str, float]) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "status": "completed",
        "evidence_available": True,
        "evidence_schema": "qcol-pipeline-evidence/1.0",
        "request": {
            "model_id": "fermion.general_spin_orbital",
            "task_id": "mapping_analysis",
            "task_parameters": {"mapping_ids": [mapping_id]},
        },
        "artifact": {"model_id": "fermion.general_spin_orbital", "n_qubits": int(metrics["n_qubits"])},
        "result": {
            "status": "PASS",
            "task_id": "mapping_analysis",
            "task_result": {
                "all_transforms_verified": True,
                "entries": [{
                    "mapping_id": mapping_id,
                    "transform_verified": True,
                    "resource_report": metrics,
                }],
            },
        },
        "phase_c": {"selected_mapping_id": mapping_id, "patch_field": "/task_parameters/mapping_ids"},
    }


def build_phase_c_scenario(name: str) -> dict[str, Any]:
    if name == "adopt":
        baseline = _vqe_snapshot("baseline-adopt", shots=1024, standard_error=0.020, absolute_error=0.025)
        candidate = _vqe_snapshot("candidate-adopt", shots=8192, standard_error=0.006, absolute_error=0.012, patch_field="/shots")
        policy = DECLARED_METRICS_POLICY_ID
    elif name == "reject":
        baseline = _vqe_snapshot("baseline-reject", shots=4096, standard_error=0.008, absolute_error=0.012)
        candidate = _vqe_snapshot("candidate-reject", shots=4096, standard_error=0.010, absolute_error=0.11, status="REVIEW", patch_field="/max_evaluations")
        policy = DECLARED_METRICS_POLICY_ID
    elif name == "inconclusive":
        baseline = _vqe_snapshot("baseline-inconclusive", shots=4096, standard_error=0.010, absolute_error=0.020)
        candidate = _vqe_snapshot("candidate-inconclusive", shots=8192, standard_error=0.010, absolute_error=0.019, patch_field="/shots")
        policy = DECLARED_METRICS_POLICY_ID
    elif name == "mapping_adopt":
        baseline = _mapping_snapshot("baseline-mapping", "jordan_wigner.v1", {
            "n_qubits": 4, "pauli_term_count": 18, "maximum_pauli_weight": 4,
            "coefficient_weighted_mean_pauli_weight": 2.6, "qwc_group_estimate": 7,
            "transformation_time_seconds": 0.020,
        })
        candidate = _mapping_snapshot("candidate-mapping", "bravyi_kitaev.v1", {
            "n_qubits": 4, "pauli_term_count": 16, "maximum_pauli_weight": 3,
            "coefficient_weighted_mean_pauli_weight": 2.1, "qwc_group_estimate": 6,
            "transformation_time_seconds": 0.018,
        })
        policy = MAPPING_RESOURCE_POLICY_ID
    else:
        raise KeyError(name)
    comparison = compare_runs(
        baseline=deepcopy(baseline), candidate=deepcopy(candidate), policy=policy,
        explicit_user_approval=True,
    )
    decision = build_decision_record(comparison)
    return {
        "schema_version": "qcol-phase-c-scenario/1.0",
        "scenario_id": name,
        "explicit_user_approval": True,
        "baseline": baseline,
        "candidate": candidate,
        "comparison": comparison.to_dict(),
        "decision_record": decision.to_dict(),
    }


__all__ = ["SCENARIO_IDS", "build_phase_c_scenario"]

"""Acceptance gates for post-freeze Execution Realization E1.

The gates prove an execution extension on the frozen baseline:
transport conformance, one verified energy evaluation, Golden Slice A
(one-pair), and Golden Slice B (QHO).  They call the unchanged shared pipeline
through an explicit ExecutionAdapter selection.
"""
from __future__ import annotations

from pathlib import Path
import math
from typing import Any, Mapping

import cirq

from .e1 import LOCAL_AER_ADAPTER_ID, run_pipeline_with_execution_adapter
from .registry import get_execution_adapter


def _adapter_records(result) -> list[Mapping[str, Any]]:
    return [
        record
        for record in list(getattr(result, "raw_records", ()) or ())
        if isinstance(record, Mapping)
    ]


def _records_use_local_aer(result) -> bool:
    records = _adapter_records(result)
    return bool(records) and all(
        record.get("execution_adapter", {}).get("adapter_id") == LOCAL_AER_ADAPTER_ID
        and record.get("canonical_execution_result", {})
        .get("metadata", {})
        .get("hardware_submission_performed") is False
        for record in records
    )


def _save_evidence(artifact, result, evidence_root: Path | str | None):
    if evidence_root is None:
        return None
    from qcol.evidence import save_and_archive_pipeline_evidence

    path, archive = save_and_archive_pipeline_evidence(
        artifact,
        result,
        Path(evidence_root),
    )
    return {"directory": str(path), "archive": str(archive)}


def run_transport_conformance_suite(*, shots: int = 256, seed: int = 42) -> dict[str, Any]:
    adapter = get_execution_adapter(LOCAL_AER_ADAPTER_ID)
    q0, q1 = cirq.LineQubit.range(2)
    fixtures = (
        (
            "identity_zero",
            cirq.Circuit(cirq.measure(q0, key="m")),
            lambda counts: counts == {"0": shots},
        ),
        (
            "x_one",
            cirq.Circuit(cirq.X(q0), cirq.measure(q0, key="m")),
            lambda counts: counts == {"1": shots},
        ),
        (
            "bell",
            cirq.Circuit(
                cirq.H(q0),
                cirq.CNOT(q0, q1),
                cirq.measure(q0, q1, key="m"),
            ),
            lambda counts: set(counts).issubset({"00", "11"})
            and sum(counts.values()) == shots,
        ),
        (
            "swapped_measurement_map",
            cirq.Circuit(cirq.X(q0), cirq.measure(q1, q0, key="m")),
            lambda counts: counts == {"10": shots},
        ),
    )
    rows = []
    for offset, (fixture_id, circuit, predicate) in enumerate(fixtures):
        record = adapter.run_measurement(
            circuit,
            repetitions=int(shots),
            seed=int(seed + offset),
        )
        counts = dict(record.counts)
        rows.append(
            {
                "fixture_id": fixture_id,
                "passed": bool(predicate(counts)),
                "counts": counts,
                "shots": record.shots_observed,
                "adapter": record.adapter.to_dict(),
                "metadata": dict(record.metadata),
            }
        )
    return {
        "schema_version": "qcol-post-freeze-e1-transport-conformance/1.0",
        "adapter_id": LOCAL_AER_ADAPTER_ID,
        "shots_per_fixture": int(shots),
        "passed": all(row["passed"] for row in rows),
        "fixtures": rows,
        "claim": (
            "Cirq executable -> OpenQASM 2 adapter transport -> Qiskit Aer -> "
            "canonical q[0]...q[n-1] records"
        ),
    }


def one_energy_evaluation_request() -> dict[str, Any]:
    return {
        "method": "custom",
        "problem": "pauli_input",
        "parameters": {
            "pauli_terms": "X0: 1.0",
            "n_qubits": 1,
            "ansatz_layers": 1,
            "energy_unit": "dimensionless",
        },
        "task_id": "ground_state_energy",
        "target_backend": "ibm",
        "execution_mode": "local_simulator",
        "run_mode": "single_evaluation",
        "initial_parameters": [math.pi / 2, math.pi],
        "shots": 512,
        "final_shots": 512,
        "seed": 7,
        "acceptance_abs_floor": 0.05,
    }


def run_one_energy_evaluation(*, evidence_root: Path | str | None = None) -> dict[str, Any]:
    artifact, result = run_pipeline_with_execution_adapter(
        one_energy_evaluation_request()
    )
    threshold = max(3.0 * float(result.standard_error or 0.0), 0.05)
    energy = float(result.reconstructed_energy)
    passed = bool(
        result.status == "PASS"
        and abs(energy + 1.0) <= threshold
        and _records_use_local_aer(result)
        and result.hardware_submission_performed is False
    )
    return {
        "schema_version": "qcol-post-freeze-e1-one-energy-evaluation/1.0",
        "passed": passed,
        "model_id": getattr(artifact, "model_id", None),
        "task_id": result.task_id,
        "run_id": result.run_id,
        "status": result.status,
        "reconstructed_energy": energy,
        "reference_energy": -1.0,
        "standard_error": result.standard_error,
        "acceptance_threshold": threshold,
        "adapter_id": LOCAL_AER_ADAPTER_ID,
        "same_shared_pipeline": True,
        "hardware_submission_performed": result.hardware_submission_performed,
        "verification": result.verification,
        "evidence": _save_evidence(artifact, result, evidence_root),
    }


def one_pair_golden_request() -> dict[str, Any]:
    return {
        "method": "fermion_pairing",
        "problem": "four_level_one_pair",
        "parameters": {
            "mapping": "pair_mapping",
            "epsilon": [0.0, 1.0, 2.0, 3.0],
            "g": 0.5,
            "n_particles": 2,
            "n_pairs": 1,
            "energy_unit": "MeV",
        },
        "task_id": "ground_state_energy",
        "target_backend": "ibm",
        "execution_mode": "local_simulator",
        "run_mode": "vqe",
        "shots": 256,
        "final_shots": 512,
        "max_evaluations": 4,
        "energy_tolerance": 0.05,
        "seed": 42,
        "acceptance_abs_floor": 0.10,
    }


def run_golden_slice_a_one_pair(*, evidence_root: Path | str | None = None) -> dict[str, Any]:
    from qcol.realization import resolve_request_to_quantum_realization

    request = one_pair_golden_request()
    preview = resolve_request_to_quantum_realization(request)
    fixture = preview.problem_artifact.parameter_fixture
    if not fixture or not fixture.get("values"):
        raise RuntimeError("The one-pair acceptance fixture is unavailable.")
    request["initial_parameters"] = [float(value) for value in fixture["values"]]
    artifact, result = run_pipeline_with_execution_adapter(request)
    passed = bool(
        result.status == "PASS"
        and result.optimizer_name == "COBYLA"
        and result.optimizer_evaluations >= 1
        and _records_use_local_aer(result)
        and result.hardware_submission_performed is False
    )
    return {
        "schema_version": "qcol-post-freeze-e1-golden-slice-a/1.0",
        "slice_id": "golden_slice_A_one_pair",
        "passed": passed,
        "model_id": getattr(artifact, "model_id", None),
        "task_id": result.task_id,
        "run_id": result.run_id,
        "status": result.status,
        "reconstructed_energy": result.reconstructed_energy,
        "standard_error": result.standard_error,
        "optimizer": result.optimizer_name,
        "optimizer_evaluations": result.optimizer_evaluations,
        "adapter_id": LOCAL_AER_ADAPTER_ID,
        "acceptance_fixture_source": fixture.get("source"),
        "protected_mapping_claim": "Pair Mapping remains restricted to the declared seniority-zero domain.",
        "evidence": _save_evidence(artifact, result, evidence_root),
    }


def qho_golden_request() -> dict[str, Any]:
    return {
        "model_id": "nuclear.qho.free",
        "method": "oscillator",
        "problem": "nuclear.qho.free",
        "task_id": "ground_state_energy",
        "parameters": {"n_modes": 3, "omega": 1.0},
        "target_backend": "google",
        "execution_mode": "local_simulator",
        "run_mode": "single_evaluation",
        "initial_parameters": [0.0, 0.0],
        "shots": 512,
        "final_shots": 512,
        "seed": 61,
        "acceptance_abs_floor": 0.10,
    }


def run_golden_slice_b_qho(*, evidence_root: Path | str | None = None) -> dict[str, Any]:
    artifact, result = run_pipeline_with_execution_adapter(qho_golden_request())
    reference = float(result.verification.get("reference_energy", 2.5))
    energy = float(result.reconstructed_energy)
    threshold = max(3.0 * float(result.standard_error or 0.0), 0.10)
    passed = bool(
        result.status == "PASS"
        and abs(energy - reference) <= threshold
        and _records_use_local_aer(result)
        and result.hardware_submission_performed is False
    )
    return {
        "schema_version": "qcol-post-freeze-e1-golden-slice-b/1.0",
        "slice_id": "golden_slice_B_QHO",
        "passed": passed,
        "model_id": getattr(artifact, "model_id", None),
        "task_id": result.task_id,
        "run_id": result.run_id,
        "status": result.status,
        "reconstructed_energy": energy,
        "reference_energy": reference,
        "standard_error": result.standard_error,
        "acceptance_threshold": threshold,
        "adapter_id": LOCAL_AER_ADAPTER_ID,
        "cell_status_unchanged": "experimental",
        "scientific_promotion_claimed": False,
        "evidence": _save_evidence(artifact, result, evidence_root),
    }


__all__ = [
    "one_energy_evaluation_request",
    "one_pair_golden_request",
    "qho_golden_request",
    "run_golden_slice_a_one_pair",
    "run_golden_slice_b_qho",
    "run_one_energy_evaluation",
    "run_transport_conformance_suite",
]

"""Single-pass observable measurements built on the same QASM2/PyQASM path."""
from __future__ import annotations

import math
from typing import Any, Dict, Mapping, Optional, Sequence

import cirq
from cirq.contrib.qasm_import import circuit_from_qasm
import numpy as np

from .control import CancellationToken
from .contracts import ProblemArtifact
from .events import EventCallback, PipelineEvent
from .measurement import circuit_metrics
from .execution import get_execution_adapter
from .modeling import bind_parameters
from .translation import (
    compare_circuit_semantics,
    export_openqasm2,
    ordered_imported_qubits,
    translate_measurement_free_circuit,
    validate_and_unroll_openqasm2,
)


def _emit(callback: Optional[EventCallback], **kwargs) -> None:
    if callback is not None:
        callback(PipelineEvent(**kwargs))


def _problem_artifact(realization_or_artifact):
    if hasattr(realization_or_artifact, "problem_artifact"):
        return realization_or_artifact.problem_artifact
    return realization_or_artifact


def reference_pair_occupations(artifact: ProblemArtifact) -> Optional[list[float]]:
    reference = artifact.exact_reference
    if reference is None:
        return None
    amplitudes = np.asarray(reference.get("target_state_amplitudes", []), dtype=complex)
    if amplitudes.ndim != 1 or amplitudes.size != artifact.n_qubits:
        return None
    probabilities = np.abs(amplitudes) ** 2
    norm = float(np.sum(probabilities))
    if norm <= 0:
        return None
    return [float(v / norm) for v in probabilities]


def select_observable_parameters(artifact: ProblemArtifact, task_parameters: Mapping[str, Any]) -> tuple[np.ndarray, str]:
    source = str(task_parameters.get("state_source", "acceptance_fixture"))
    if source == "acceptance_fixture":
        fixture = artifact.parameter_fixture or {}
        values = fixture.get("values")
        if values is None:
            raise ValueError("This model has no acceptance fixture for observable estimation.")
        return np.asarray(values, dtype=float), "acceptance_fixture_exact_derived"
    if source == "initial_parameters":
        return np.asarray(artifact.initial_parameters, dtype=float), "model_initial_parameters"
    if source == "explicit_parameters":
        values = task_parameters.get("parameter_values", [])
        return np.asarray(values, dtype=float), "user_explicit_parameters"
    raise ValueError(f"Unsupported observable state_source: {source!r}")


def execute_pair_occupation_observable(
    realization_or_artifact,
    parameter_values: Sequence[float],
    *,
    shots: int,
    seed: int,
    run_id: str,
    event_callback: Optional[EventCallback] = None,
    cancellation_token: Optional[CancellationToken] = None,
    execution_adapter_id: str = "execution.local_cirq.v1",
) -> Dict[str, Any]:
    """Measure all pair-occupation qubits in one shared Z-basis circuit."""
    artifact = _problem_artifact(realization_or_artifact)
    if artifact.mapping != "pair_mapping":
        raise ValueError("The verified pair-occupation task currently requires pair_mapping.")
    if shots <= 0:
        raise ValueError("shots must be positive.")
    execution_adapter = get_execution_adapter(execution_adapter_id)

    def check(location: str) -> None:
        if cancellation_token is not None:
            cancellation_token.raise_if_cancelled(location=location)

    values = np.asarray(parameter_values, dtype=float)
    if values.shape != (len(artifact.parameter_symbols),):
        raise ValueError(
            f"Observable task expected {len(artifact.parameter_symbols)} parameters, received {values.shape}."
        )
    ordered_qubits = tuple(cirq.LineQubit.range(artifact.n_qubits))
    bound = bind_parameters(artifact.ansatz_template, artifact.parameter_symbols, values)

    _emit(
        event_callback,
        run_id=run_id,
        stage="bind",
        status="completed",
        message="Bound the prepared-state parameters for the observable task.",
        metrics={"task": "observable_estimation", "parameter_count": len(values)},
        artifact_refs=["observable_bound_state"],
    )

    check("before_observable_translation")
    measurement_free = translate_measurement_free_circuit(
        bound,
        ordered_qubits,
        strict_semantic_check=True,
    )
    circuit = bound.copy()
    circuit.append(cirq.measure(*ordered_qubits, key="pair_occupations"))
    _emit(
        event_callback,
        run_id=run_id,
        stage="measurement",
        status="completed",
        message="Built one shared Z-basis circuit for pair-occupation observables.",
        metrics={
            "task": "observable_estimation",
            "group_count": 1,
            "basis": "Z",
            "observable_count": artifact.n_qubits,
        },
        artifact_refs=["observable_measurement_plan"],
    )
    raw_qasm2 = export_openqasm2(circuit, ordered_qubits)
    validation = validate_and_unroll_openqasm2(raw_qasm2)
    imported = circuit_from_qasm(validation["unrolled_qasm"])
    imported_order = ordered_imported_qubits(imported, artifact.n_qubits)
    semantic = compare_circuit_semantics(
        circuit,
        imported,
        ordered_qubits,
        imported_order,
        ignore_terminal_measurements=True,
    )
    if semantic.get("performed") and not semantic.get("passed"):
        raise AssertionError("Observable QASM2 semantic round trip failed.")

    _emit(
        event_callback,
        run_id=run_id,
        stage="translation",
        status="completed",
        message="Observable circuit exported to OpenQASM 2 and validated/unrolled by PyQASM.",
        metrics={
            "task": "observable_estimation",
            "validated": True,
            "semantic_passed": semantic.get("passed"),
        },
        artifact_refs=["observable_qasm2"],
    )

    check("before_observable_execute")
    adapter_result = execution_adapter.run_measurement(
        imported, repetitions=shots, seed=seed
    )
    check("after_observable_execute")
    bits = adapter_result.measurement_bits
    measured_qubits = adapter_result.imported_qubit_order
    counts = dict(adapter_result.counts)
    occupations = np.mean(bits, axis=0).astype(float)
    occupation_stderr = np.sqrt(np.maximum(occupations * (1.0 - occupations), 0.0) / shots)

    pair_number = int((artifact.target_sector or {}).get("pair_number", 1))
    sector_membership = np.sum(bits, axis=1) == pair_number
    sector_leakage = float(1.0 - np.mean(sector_membership))
    sector_stderr = math.sqrt(max(sector_leakage * (1.0 - sector_leakage), 0.0) / shots)
    reference = reference_pair_occupations(artifact)

    _emit(
        event_callback,
        run_id=run_id,
        stage="execute",
        status="completed",
        message=f"Executed one Z-basis observable circuit with {shots} shots.",
        metrics={"task": "observable_estimation", "shots": shots, "distinct_outcomes": len(counts)},
    )
    _emit(
        event_callback,
        run_id=run_id,
        stage="evidence",
        status="completed",
        message="Preserved observable counts, QASM2 artifacts, and provenance.",
        metrics={"task": "observable_estimation", "record_count": 1},
        artifact_refs=["observable_counts", "observable_qasm2"],
    )
    _emit(
        event_callback,
        run_id=run_id,
        stage="reconstruct",
        status="completed",
        message="Reconstructed pair occupations and measured sector leakage.",
        metrics={
            "task": "observable_estimation",
            "occupations": [float(v) for v in occupations],
            "sector_leakage": sector_leakage,
        },
        artifact_refs=["observable_result"],
    )

    return {
        "result_kind": "pair_occupations",
        "observable_ids": [f"pair_occupation.level_{i}" for i in range(artifact.n_qubits)],
        "occupations": [float(v) for v in occupations],
        "occupation_standard_errors": [float(v) for v in occupation_stderr],
        "sum_occupations": float(np.sum(occupations)),
        "sector_leakage": sector_leakage,
        "sector_leakage_standard_error": float(sector_stderr),
        "target_pair_number": pair_number,
        "reference_occupations": reference,
        "shots": int(shots),
        "counts": counts,
        "measured_qubit_order": list(measured_qubits),
        "execution_adapter": adapter_result.adapter.to_dict(),
        "translation_check": {
            "measurement_free": measurement_free,
            "validated": bool(validation["validated"]),
            "semantic_check": semantic,
            "raw_qasm2": raw_qasm2,
            "unrolled_qasm2": validation["unrolled_qasm"],
            "logical_metrics": circuit_metrics(circuit),
            "roundtrip_metrics": circuit_metrics(imported),
        },
        "records": [{
            "group_id": "pair_occupations_z_basis",
            "basis": {str(i): "Z" for i in range(artifact.n_qubits)},
            "counts": counts,
            "raw_qasm2": raw_qasm2,
            "unrolled_qasm2": validation["unrolled_qasm"],
            "pyqasm_validated": bool(validation["validated"]),
            "qasm_semantic_check": semantic,
            "execution_adapter": adapter_result.adapter.to_dict(),
            "canonical_execution_result": adapter_result.public_dict(include_counts=True),
        }],
    }

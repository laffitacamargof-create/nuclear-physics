"""Hamiltonian measurement planning and sampled-record reconstruction."""
from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Mapping, Sequence, Tuple

import cirq
import numpy as np
from openfermion import QubitOperator

from .translation import ordered_imported_qubits

PauliTerm = Tuple[Tuple[int, str], ...]


def real_coefficient(value: complex, tolerance: float = 1e-10) -> float:
    coefficient = complex(value)
    if abs(coefficient.imag) > tolerance:
        raise ValueError(f"Complex Hamiltonian coefficient: {coefficient}")
    return float(coefficient.real)


def qwc_compatible(
    group_basis: Mapping[int, str],
    term_basis: Mapping[int, str],
) -> bool:
    for qubit_index, pauli in term_basis.items():
        active = group_basis.get(qubit_index)
        if active is not None and active != pauli:
            return False
    return True


def build_qwc_measurement_plan(
    qubit_operator: QubitOperator,
) -> Dict[str, Any]:
    identity_coefficient = 0.0
    non_identity_terms: List[Tuple[PauliTerm, float]] = []

    for term, coefficient in qubit_operator.terms.items():
        real_value = real_coefficient(coefficient)
        if len(term) == 0:
            identity_coefficient += real_value
        else:
            non_identity_terms.append((tuple(term), real_value))

    # Longer terms first gives stable, compact groups for this Hamiltonian.
    non_identity_terms.sort(key=lambda item: (-len(item[0]), item[0]))

    groups: List[Dict[str, Any]] = []
    for term, coefficient in non_identity_terms:
        term_basis = {int(index): str(pauli) for index, pauli in term}

        for group in groups:
            if qwc_compatible(group["basis"], term_basis):
                group["basis"].update(term_basis)
                group["terms"].append(
                    {"term": term, "coefficient": coefficient}
                )
                break
        else:
            groups.append(
                {
                    "basis": dict(term_basis),
                    "terms": [{"term": term, "coefficient": coefficient}],
                }
            )

    for group_id, group in enumerate(groups):
        group["group_id"] = group_id

    return {
        "identity_coefficient": identity_coefficient,
        "groups": groups,
    }


def format_pauli_term(term: PauliTerm) -> str:
    if not term:
        return "I"
    return " ".join(f"{pauli}{index}" for index, pauli in term)


def circuit_metrics(circuit: cirq.Circuit) -> Dict[str, Any]:
    gate_counts: Counter[str] = Counter()
    two_qubit_operations = 0

    for operation in circuit.all_operations():
        gate_name = type(operation.gate).__name__
        gate_counts[gate_name] += 1
        if len(operation.qubits) == 2:
            two_qubit_operations += 1

    return {
        "moments": len(circuit),
        "operations": sum(gate_counts.values()),
        "two_qubit_operations": two_qubit_operations,
        "gate_counts": dict(gate_counts),
    }


def extract_measurement_matrix(
    result: cirq.Result,
    executed_circuit: cirq.Circuit,
) -> Tuple[np.ndarray, List[cirq.Qid]]:
    measured_qubits = ordered_imported_qubits(executed_circuit)
    position = {qubit: index for index, qubit in enumerate(measured_qubits)}

    repetitions = next(iter(result.measurements.values())).shape[0]
    bits = np.full(
        (repetitions, len(measured_qubits)),
        fill_value=-1,
        dtype=np.int8,
    )

    for operation in executed_circuit.all_operations():
        if not isinstance(operation.gate, cirq.MeasurementGate):
            continue

        key = cirq.measurement_key_name(operation)
        values = np.asarray(result.measurements[key], dtype=np.int8)
        if values.ndim == 1:
            values = values[:, np.newaxis]

        for column, qubit in enumerate(operation.qubits):
            bits[:, position[qubit]] = values[:, column]

    if np.any(bits < 0):
        raise AssertionError("Not every imported QASM qubit was measured.")
    return bits, measured_qubits


def counts_from_measurements(bits: np.ndarray) -> Dict[str, int]:
    counter = Counter(
        "".join(str(int(bit)) for bit in row)
        for row in bits
    )
    return dict(sorted(counter.items()))


def reconstruct_group(
    group: Mapping[str, Any],
    bits: np.ndarray,
) -> Dict[str, Any]:
    shots = int(bits.shape[0])
    per_shot_group_energy = np.zeros(shots, dtype=float)
    term_expectations: Dict[str, float] = {}

    for item in group["terms"]:
        term: PauliTerm = tuple(item["term"])
        coefficient = float(item["coefficient"])
        indices = [int(index) for index, _ in term]

        eigenvalues = np.prod(
            1 - 2 * bits[:, indices],
            axis=1,
        )
        expectation = float(np.mean(eigenvalues))
        label = format_pauli_term(term)

        term_expectations[label] = expectation
        per_shot_group_energy += coefficient * eigenvalues

    contribution = float(np.mean(per_shot_group_energy))
    variance_of_mean = (
        float(np.var(per_shot_group_energy, ddof=1)) / shots
        if shots > 1
        else 0.0
    )

    return {
        "term_expectations": term_expectations,
        "energy_contribution": contribution,
        "variance_of_mean": variance_of_mean,
    }


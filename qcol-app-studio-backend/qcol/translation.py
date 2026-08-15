"""OpenQASM 2 export, PyQASM validation/unrolling, and bounded semantic checks."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Mapping, Sequence

import cirq
from cirq.contrib.qasm_import import circuit_from_qasm
import numpy as np
import pyqasm

from .config import (
    QASM_EQUIVALENCE_ATOL,
    QASM_EQUIVALENCE_MAX_QUBITS,
    QCOL_QASM2_EXTERNAL_GATES,
)


def add_measurement_basis_and_readout(
    bound_template: cirq.Circuit,
    group: Mapping[str, Any],
    ordered_qubits: Sequence[cirq.Qid],
) -> cirq.Circuit:
    circuit = bound_template.copy()
    for qubit_index, pauli in sorted(group["basis"].items()):
        qubit = ordered_qubits[int(qubit_index)]
        if pauli == "X":
            circuit.append(cirq.H(qubit))
        elif pauli == "Y":
            circuit.append(cirq.S(qubit) ** -1)
            circuit.append(cirq.H(qubit))
        elif pauli == "Z":
            pass
        else:
            raise ValueError(f"Unsupported Pauli basis: {pauli}")
    circuit.append(cirq.measure(*ordered_qubits, key=f"group_{group['group_id']}"))
    return circuit


def export_openqasm2(
    circuit: cirq.Circuit,
    ordered_qubits: Sequence[cirq.Qid],
) -> str:
    kwargs = {
        "header": "QCOL - numerically bound circuit",
        "precision": 15,
        "qubit_order": list(ordered_qubits),
    }
    try:
        qasm_text = circuit.to_qasm(version="2.0", **kwargs)
    except TypeError:
        # Cirq 1.3/1.4 compatibility profile.
        qasm_text = circuit.to_qasm(**kwargs)
    if "OPENQASM 2.0;" not in qasm_text:
        raise AssertionError("Cirq did not export OpenQASM 2.0.")
    return qasm_text


def validate_and_unroll_openqasm2(qasm_text: str) -> Dict[str, Any]:
    if "OPENQASM 2.0;" not in qasm_text:
        raise ValueError("Only OpenQASM 2.0 is accepted in this workflow.")

    module = pyqasm.loads(qasm_text)
    module.validate()
    qubit_count = int(module.num_qubits)
    try:
        depth_before = int(module.depth(decompose_native_gates=False))
    except Exception:
        depth_before = None

    # Preserve the gate basis Cirq already emits and can re-import. PyQASM still
    # validates the program and expands custom/high-level constructs.
    module.unroll(external_gates=list(QCOL_QASM2_EXTERNAL_GATES))
    unrolled_qasm = pyqasm.dumps(module)
    if "OPENQASM 2.0;" not in unrolled_qasm:
        raise AssertionError("PyQASM did not preserve the OpenQASM 2 contract.")
    try:
        depth_after = int(module.depth(decompose_native_gates=False))
    except Exception:
        depth_after = None

    return {
        "validated": True,
        "num_qubits": qubit_count,
        "depth_before_unroll": depth_before,
        "depth_after_unroll": depth_after,
        "unroll_strategy": "preserve_cirq_supported_qasm2_basis",
        "external_gates": list(QCOL_QASM2_EXTERNAL_GATES),
        "unrolled_qasm": unrolled_qasm,
    }


def numeric_suffix(value: Any) -> int:
    match = re.search(r"(\d+)$", str(value))
    if match is None:
        raise ValueError(f"Cannot infer a numeric qubit index from {value!r}.")
    return int(match.group(1))


def ordered_imported_qubits(
    circuit: cirq.Circuit,
    expected_n_qubits: int | None = None,
) -> List[cirq.Qid]:
    qubits = sorted(circuit.all_qubits(), key=numeric_suffix)
    indices = [numeric_suffix(qubit) for qubit in qubits]
    if expected_n_qubits is not None:
        expected = list(range(expected_n_qubits))
        if indices != expected:
            raise AssertionError(
                "Imported QASM qubit labels do not preserve q[0]...q[n-1]: "
                f"received indices {indices}, expected {expected}."
            )
    return qubits


def _unitary_process_fidelity(left: np.ndarray, right: np.ndarray) -> float:
    if left.shape != right.shape or left.ndim != 2 or left.shape[0] != left.shape[1]:
        raise ValueError("Unitary matrices must be square and have matching shapes.")
    dimension = left.shape[0]
    overlap = np.trace(left.conj().T @ right) / dimension
    return float(abs(overlap) ** 2)


def compare_circuit_semantics(
    reference_circuit: cirq.Circuit,
    candidate_circuit: cirq.Circuit,
    reference_order: Sequence[cirq.Qid],
    candidate_order: Sequence[cirq.Qid],
    *,
    ignore_terminal_measurements: bool,
) -> Dict[str, Any]:
    """Compare small circuits up to global phase in complex128 precision."""
    if len(reference_order) != len(candidate_order):
        return {
            "performed": True,
            "passed": False,
            "reason": "qubit_count_mismatch",
            "reference_qubits": len(reference_order),
            "candidate_qubits": len(candidate_order),
        }
    if len(reference_order) > QASM_EQUIVALENCE_MAX_QUBITS:
        return {
            "performed": False,
            "passed": None,
            "reason": (
                "exact semantic comparison skipped above the bounded "
                f"{QASM_EQUIVALENCE_MAX_QUBITS}-qubit limit"
            ),
        }

    reference_u = reference_circuit.unitary(
        qubit_order=list(reference_order),
        qubits_that_should_be_present=list(reference_order),
        ignore_terminal_measurements=ignore_terminal_measurements,
        dtype=np.complex128,
    )
    candidate_u = candidate_circuit.unitary(
        qubit_order=list(candidate_order),
        qubits_that_should_be_present=list(candidate_order),
        ignore_terminal_measurements=ignore_terminal_measurements,
        dtype=np.complex128,
    )
    fidelity = _unitary_process_fidelity(reference_u, candidate_u)
    equivalent = bool(
        cirq.linalg.allclose_up_to_global_phase(
            reference_u, candidate_u, atol=QASM_EQUIVALENCE_ATOL
        )
    )
    return {
        "performed": True,
        "passed": equivalent,
        "unitary_equivalent_up_to_global_phase": equivalent,
        "unitary_process_fidelity_up_to_global_phase": fidelity,
        "atol": QASM_EQUIVALENCE_ATOL,
    }


def translate_measurement_free_circuit(
    bound_circuit: cirq.Circuit,
    ordered_qubits: Sequence[cirq.Qid],
    *,
    strict_semantic_check: bool,
) -> Dict[str, Any]:
    raw_qasm2 = export_openqasm2(bound_circuit, ordered_qubits)
    validation = validate_and_unroll_openqasm2(raw_qasm2)
    if validation["num_qubits"] != len(ordered_qubits):
        raise AssertionError(
            "Measurement-free QASM2 translation changed the qubit-register size."
        )

    raw_imported = circuit_from_qasm(raw_qasm2)
    unrolled_imported = circuit_from_qasm(validation["unrolled_qasm"])
    raw_order = ordered_imported_qubits(raw_imported, len(ordered_qubits))
    unrolled_order = ordered_imported_qubits(unrolled_imported, len(ordered_qubits))

    if strict_semantic_check:
        raw_semantics = compare_circuit_semantics(
            bound_circuit,
            raw_imported,
            ordered_qubits,
            raw_order,
            ignore_terminal_measurements=False,
        )
        unrolled_semantics = compare_circuit_semantics(
            bound_circuit,
            unrolled_imported,
            ordered_qubits,
            unrolled_order,
            ignore_terminal_measurements=False,
        )
        performed = bool(raw_semantics.get("performed") and unrolled_semantics.get("performed"))
        passed = (
            bool(raw_semantics.get("passed") and unrolled_semantics.get("passed"))
            if performed
            else True
        )
    else:
        raw_semantics = {
            "performed": False,
            "passed": None,
            "reason": "intermediate optimizer evaluation: exact unitary check deferred",
        }
        unrolled_semantics = dict(raw_semantics)
        performed = False
        passed = True

    return {
        "validated": bool(validation["validated"]),
        "num_qubits": int(validation["num_qubits"]),
        "depth_before_unroll": validation["depth_before_unroll"],
        "depth_after_unroll": validation["depth_after_unroll"],
        "unroll_strategy": validation["unroll_strategy"],
        "external_gates": validation["external_gates"],
        "semantic_check_performed": performed,
        "raw_roundtrip": raw_semantics,
        "unrolled_roundtrip": unrolled_semantics,
        "passed": passed,
        "imported_qubit_order": [str(qubit) for qubit in unrolled_order],
        "raw_qasm2": raw_qasm2,
        "unrolled_qasm2": validation["unrolled_qasm"],
        "executable_circuit": unrolled_imported,
        "executable_qubit_order": unrolled_order,
    }

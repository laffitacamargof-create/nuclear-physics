"""Qiskit/Aer result normalization for the post-freeze E1 adapter.

The baseline canonical convention is one column per logical qubit in
``q[0], q[1], ..., q[n-1]`` order. Qiskit displays classical memory with
classical bit zero on the right. E1 therefore decodes memory through the
explicit OpenQASM 2 measurement map rather than by reversing strings
heuristically.

This module owns only provider/transport normalization. It deliberately does
not modify the frozen QCOL translation helpers or scientific runtime.
"""
from __future__ import annotations

from collections import Counter
from numbers import Integral
import re
from typing import Any, Sequence

import numpy as np

_QREG_RE = re.compile(r"^\s*qreg\s+([A-Za-z_]\w*)\[(\d+)\]\s*;\s*$", re.I)
_CREG_RE = re.compile(r"^\s*creg\s+([A-Za-z_]\w*)\[(\d+)\]\s*;\s*$", re.I)
_MEASURE_SCALAR_RE = re.compile(
    r"^\s*measure\s+([A-Za-z_]\w*)\[(\d+)\]\s*->\s*([A-Za-z_]\w*)\[(\d+)\]\s*;\s*$",
    re.I,
)
_MEASURE_REGISTER_RE = re.compile(
    r"^\s*measure\s+([A-Za-z_]\w*)\s*->\s*([A-Za-z_]\w*)\s*;\s*$",
    re.I,
)
_QUBIT_LABEL_PATTERNS = (
    re.compile(r"^q\[(\d+)\]$"),
    re.compile(r"^q_(\d+)$"),
    re.compile(r"^q\((\d+)\)$"),
    re.compile(r"^(\d+)$"),
)


def _clean_lines(qasm_text: str) -> tuple[str, ...]:
    lines: list[str] = []
    for raw in str(qasm_text).splitlines():
        value = raw.split("//", 1)[0].strip()
        if value:
            lines.append(value)
    return tuple(lines)


def qasm_registers(qasm_text: str) -> tuple[dict[str, int], dict[str, int]]:
    """Return QASM register declarations in declaration order."""
    qregs: dict[str, int] = {}
    cregs: dict[str, int] = {}
    for line in _clean_lines(qasm_text):
        match = _QREG_RE.match(line)
        if match:
            name, size = match.group(1), int(match.group(2))
            if name in qregs or name in cregs:
                raise ValueError(f"Duplicate QASM register declaration: {name!r}.")
            qregs[name] = size
            continue
        match = _CREG_RE.match(line)
        if match:
            name, size = match.group(1), int(match.group(2))
            if name in qregs or name in cregs:
                raise ValueError(f"Duplicate QASM register declaration: {name!r}.")
            cregs[name] = size
    return qregs, cregs


def _register_offsets(registers: dict[str, int]) -> dict[str, int]:
    """Map each declared register to Qiskit's flat bit-index offset."""
    offsets: dict[str, int] = {}
    cursor = 0
    for name, size in registers.items():
        offsets[name] = cursor
        cursor += int(size)
    return offsets


def execution_qubit_index(value: Any) -> int:
    """Return the explicit logical index of a bounded E1 execution qubit.

    The shared pipeline normally hands the adapter QASM-imported NamedQubits,
    while transport conformance uses Cirq LineQubits. Both are legitimate
    representations of the same q[0]...q[n-1] execution profile.
    """
    direct = getattr(value, "x", None)
    if isinstance(direct, Integral):
        return int(direct)
    text = str(value).strip()
    for pattern in _QUBIT_LABEL_PATTERNS:
        match = pattern.match(text)
        if match:
            return int(match.group(1))
    raise ValueError(
        "E1 cannot infer an explicit q[0]...q[n-1] index from "
        f"execution qubit {value!r}."
    )


def ordered_execution_qubits(
    circuit: Any,
    expected_n_qubits: int | None = None,
) -> tuple[Any, ...]:
    """Order LineQubit or QASM-imported qubits by their explicit logical index."""
    indexed = [(execution_qubit_index(qubit), qubit) for qubit in circuit.all_qubits()]
    indices = [index for index, _ in indexed]
    if len(indices) != len(set(indices)):
        raise ValueError(f"Execution qubit labels reuse logical indices: {indices}.")
    indexed.sort(key=lambda item: item[0])
    ordered_indices = [index for index, _ in indexed]
    expected_count = len(indexed) if expected_n_qubits is None else int(expected_n_qubits)
    expected = list(range(expected_count))
    if ordered_indices != expected:
        raise ValueError(
            "E1 execution qubits must represent q[0]...q[n-1] exactly once: "
            f"received {ordered_indices}, expected {expected}."
        )
    return tuple(qubit for _, qubit in indexed)


def qasm_measurement_pairs(
    qasm_text: str,
    *,
    expected_n_qubits: int,
) -> tuple[tuple[int, int], ...]:
    """Return explicit ``(logical qubit index, flat classical index)`` pairs.

    E1 keeps the frozen one-quantum-register profile. It accepts one or more
    *declared* classical registers because a PyQASM-validated circuit re-imported
    into Cirq can be re-emitted with one classical register per measurement key.
    The registers are flattened only through their explicit declaration order and
    measurement statements; no scientific or bit-order inference is performed.
    """
    qregs, cregs = qasm_registers(qasm_text)
    if len(qregs) != 1 or not cregs:
        raise ValueError(
            "E1 LocalAer accepts exactly one qreg and one or more declared cregs; "
            f"received qregs={qregs}, cregs={cregs}."
        )
    qreg_name, qreg_size = next(iter(qregs.items()))
    expected_n_qubits = int(expected_n_qubits)
    if qreg_size != expected_n_qubits:
        raise ValueError(
            f"QASM qreg size {qreg_size} does not match {expected_n_qubits}."
        )
    offsets = _register_offsets(cregs)

    pairs: list[tuple[int, int]] = []
    measured_qubits: set[int] = set()
    used_clbits: set[int] = set()

    def add_pair(qindex_i: int, clbit_i: int) -> None:
        if qindex_i in measured_qubits:
            raise ValueError(
                f"The QASM measurement map measures logical qubit q[{qindex_i}] more than once."
            )
        if clbit_i in used_clbits:
            raise ValueError(
                f"The QASM measurement map reuses flat classical bit {clbit_i}."
            )
        measured_qubits.add(qindex_i)
        used_clbits.add(clbit_i)
        pairs.append((qindex_i, clbit_i))

    for line in _clean_lines(qasm_text):
        scalar = _MEASURE_SCALAR_RE.match(line)
        if scalar:
            qreg, qindex, creg, cindex = scalar.groups()
            if qreg != qreg_name or creg not in cregs:
                raise ValueError("Measurement uses an undeclared register layout.")
            qindex_i = int(qindex)
            cindex_i = int(cindex)
            if not 0 <= qindex_i < qreg_size:
                raise ValueError(f"Measurement qubit index {qindex_i} is out of range.")
            if not 0 <= cindex_i < cregs[creg]:
                raise ValueError(f"Measurement classical index {cindex_i} is out of range.")
            add_pair(qindex_i, offsets[creg] + cindex_i)
            continue
        register = _MEASURE_REGISTER_RE.match(line)
        if register:
            qreg, creg = register.groups()
            if qreg != qreg_name or creg not in cregs:
                raise ValueError("Register measurement uses an unexpected register.")
            if cregs[creg] < expected_n_qubits:
                raise ValueError("Register measurement does not cover every logical qubit.")
            for index in range(expected_n_qubits):
                add_pair(index, offsets[creg] + index)

    pairs.sort(key=lambda item: item[0])
    if [item[0] for item in pairs] != list(range(expected_n_qubits)):
        raise ValueError(
            "The QASM measurement map does not cover q[0]...q[n-1] exactly once."
        )
    return tuple(pairs)


def qiskit_measurement_pairs(circuit) -> tuple[tuple[int, int], ...]:
    pairs: list[tuple[int, int]] = []
    for item in circuit.data:
        operation = item.operation if hasattr(item, "operation") else item[0]
        qargs = item.qubits if hasattr(item, "qubits") else item[1]
        cargs = item.clbits if hasattr(item, "clbits") else item[2]
        if getattr(operation, "name", "") != "measure":
            continue
        pairs.append(
            (
                int(circuit.find_bit(qargs[0]).index),
                int(circuit.find_bit(cargs[0]).index),
            )
        )
    return tuple(sorted(pairs))


def _clean_memory_word(word: str, *, n_clbits: int) -> str:
    # Qiskit separates classical registers with spaces and displays the highest
    # flat classical indices on the left. Removing separators therefore retains
    # the global c[n-1]...c[0] convention used by ``find_bit(...).index``.
    clean = str(word).replace(" ", "").replace("_", "")
    if clean.startswith("0x"):
        clean = format(int(clean, 16), f"0{n_clbits}b")
    if len(clean) < n_clbits:
        clean = clean.zfill(n_clbits)
    if len(clean) != n_clbits or any(char not in "01" for char in clean):
        raise ValueError(
            f"Raw Qiskit memory word {word!r} is not {n_clbits} binary bits."
        )
    return clean


def normalize_qiskit_memory(
    memory: Sequence[str],
    *,
    n_clbits: int,
    n_qubits: int,
    measurement_pairs: Sequence[tuple[int, int]],
) -> np.ndarray:
    by_qubit = {int(qubit): int(clbit) for qubit, clbit in measurement_pairs}
    if set(by_qubit) != set(range(int(n_qubits))):
        raise ValueError("Measurement pairs do not cover all logical qubits.")
    matrix = np.empty((len(memory), int(n_qubits)), dtype=np.int8)
    for row, raw_word in enumerate(memory):
        word = _clean_memory_word(raw_word, n_clbits=int(n_clbits))
        for logical_index in range(int(n_qubits)):
            clbit_index = by_qubit[logical_index]
            matrix[row, logical_index] = int(word[-(clbit_index + 1)])
    return matrix


def canonical_counts(bits: np.ndarray) -> dict[str, int]:
    matrix = np.asarray(bits, dtype=np.int8)
    if matrix.ndim != 2 or np.any((matrix != 0) & (matrix != 1)):
        raise ValueError("Canonical measurement data must be a 2D binary matrix.")
    counts = Counter("".join(str(int(bit)) for bit in row) for row in matrix)
    return dict(sorted((key, int(value)) for key, value in counts.items()))


__all__ = [
    "canonical_counts",
    "execution_qubit_index",
    "normalize_qiskit_memory",
    "ordered_execution_qubits",
    "qasm_measurement_pairs",
    "qasm_registers",
    "qiskit_measurement_pairs",
]

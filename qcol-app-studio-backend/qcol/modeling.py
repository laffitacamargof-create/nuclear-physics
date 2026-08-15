"""Scientific model construction, encodings, ansatz templates, and references."""
from __future__ import annotations

import ast
from itertools import product
import math
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import cirq
import numpy as np
import sympy
from openfermion import FermionOperator, QubitOperator, get_sparse_operator
from openfermion.linalg import jw_configuration_state

from .config import NUMERIC_TOL

def build_pair_qubit_hamiltonian(
    level_energies: Sequence[float],
    pairing_strength: float,
) -> QubitOperator:
    """Map the seniority-zero pairing model to one qubit per level."""
    qubit_hamiltonian = QubitOperator()

    for p, energy in enumerate(level_energies):
        # (2*epsilon_p - g) n_p, where n_p = (I - Z_p)/2
        qubit_hamiltonian += QubitOperator((), float(energy) - pairing_strength / 2)
        qubit_hamiltonian += QubitOperator(
            ((p, "Z"),),
            -float(energy) + pairing_strength / 2,
        )

    for p in range(len(level_energies)):
        for q in range(p + 1, len(level_energies)):
            coefficient = -pairing_strength / 2
            qubit_hamiltonian += QubitOperator(
                ((p, "X"), (q, "X")),
                coefficient,
            )
            qubit_hamiltonian += QubitOperator(
                ((p, "Y"), (q, "Y")),
                coefficient,
            )

    qubit_hamiltonian.compress()
    return qubit_hamiltonian
def build_guided_occupation_hamiltonian(
    onsite_energies: Sequence[float],
    coupling: Any,
    *,
    energy_offset: float = 0.0,
) -> Tuple[QubitOperator, np.ndarray, np.ndarray]:
    """Build a bounded no-code occupation/coupling Hamiltonian.

    The declared model is

        H = E0 I + sum_i epsilon_i n_i
            - 1/2 sum_{i<j} G_ij (X_i X_j + Y_i Y_j),

    with n_i=(I-Z_i)/2 and a symmetric, non-negative G matrix.  This
    preserves total excitation number and is intentionally narrower than an
    arbitrary custom Hamiltonian.
    """
    onsite = np.asarray(onsite_energies, dtype=float)
    if onsite.ndim != 1 or onsite.size < 2:
        raise ValueError("At least two onsite energies are required.")
    if not np.all(np.isfinite(onsite)):
        raise ValueError("Onsite energies contain non-finite values.")
    if not math.isfinite(float(energy_offset)):
        raise ValueError("Energy offset must be finite.")

    couplings = coupling_matrix(coupling, int(onsite.size))
    if np.any(couplings < -NUMERIC_TOL):
        raise ValueError(
            "Guided couplings must be non-negative; the Hamiltonian applies "
            "the declared minus sign explicitly."
        )

    operator = QubitOperator((), float(energy_offset))
    for mode, epsilon in enumerate(onsite):
        # epsilon*n, n=(I-Z)/2
        operator += QubitOperator((), float(epsilon) / 2)
        operator += QubitOperator(((mode, "Z"),), -float(epsilon) / 2)

    for left in range(int(onsite.size)):
        for right in range(left + 1, int(onsite.size)):
            coefficient = -float(couplings[left, right]) / 2
            if abs(coefficient) <= NUMERIC_TOL:
                continue
            operator += QubitOperator(((left, "X"), (right, "X")), coefficient)
            operator += QubitOperator(((left, "Y"), (right, "Y")), coefficient)

    operator.compress()
    return operator, onsite, couplings


def basis_index(occupied_modes: Sequence[int], n_qubits: int) -> int:
    """Use OpenFermion's convention to locate a computational basis state."""
    state = jw_configuration_state(list(occupied_modes), n_qubits)
    if hasattr(state, "toarray"):
        state = state.toarray()
    state = np.asarray(state).reshape(-1)
    nonzero = np.flatnonzero(np.abs(state) > NUMERIC_TOL)
    if len(nonzero) != 1:
        raise AssertionError("Expected one computational-basis index.")
    return int(nonzero[0])
def append_number_conserving_givens(
    circuit: cirq.Circuit,
    left: cirq.Qid,
    right: cirq.Qid,
    theta: Any,
) -> None:
    """
    Apply a real Givens rotation in the {|10>, |01>} subspace.

    The controlled-RY is decomposed into RY and CNOT operations so the
    numerically bound circuit exports cleanly to OpenQASM 2.
    """
    circuit.append(cirq.CNOT(right, left))
    circuit.append(cirq.ry(theta / 2).on(right))
    circuit.append(cirq.CNOT(left, right))
    circuit.append(cirq.ry(-theta / 2).on(right))
    circuit.append(cirq.CNOT(left, right))
    circuit.append(cirq.CNOT(right, left))


def build_pair_ansatz_template(
    symbolic_parameters: Sequence[Any],
    ordered_qubits: Sequence[cirq.Qid],
) -> cirq.Circuit:
    expected_parameters = max(len(ordered_qubits) - 1, 0)
    if len(symbolic_parameters) != expected_parameters:
        raise ValueError(
            f"Expected {expected_parameters} parameters, "
            f"received {len(symbolic_parameters)}."
        )

    circuit = cirq.Circuit()
    if ordered_qubits:
        circuit.append(cirq.X(ordered_qubits[0]))

    for index, theta in enumerate(symbolic_parameters):
        append_number_conserving_givens(
            circuit,
            ordered_qubits[index],
            ordered_qubits[index + 1],
            theta,
        )
    return circuit
def chain_angles_from_positive_real_state(amplitudes: Sequence[float]) -> np.ndarray:
    """
    Convert a non-negative real one-excitation state into chain-Givens angles.

    For the attractive Phase 1 pairing Hamiltonian, the selected ground-state
    eigenvector can be chosen with non-negative amplitudes.
    """
    vector = np.asarray(amplitudes, dtype=float)
    vector = vector / np.linalg.norm(vector)

    if np.any(vector < -NUMERIC_TOL):
        raise ValueError(
            "This bounded synthesis helper expects a non-negative real state."
        )
    if len(vector) <= 1:
        return np.asarray([], dtype=float)

    angles: List[float] = []
    for index in range(len(vector) - 2):
        tail_norm = float(np.linalg.norm(vector[index + 1 :]))
        angles.append(2 * math.atan2(tail_norm, float(vector[index])))

    angles.append(2 * math.atan2(float(vector[-1]), float(vector[-2])))
    return np.asarray(angles, dtype=float)


def bind_parameters(
    template: cirq.Circuit,
    symbols: Sequence[Any],
    values: Sequence[float],
) -> cirq.Circuit:
    if len(symbols) != len(values):
        raise ValueError("Parameter-name and parameter-value lengths differ.")
    resolver = cirq.ParamResolver(
        {str(symbol): float(value) for symbol, value in zip(symbols, values)}
    )
    bound = cirq.resolve_parameters(template, resolver)
    if cirq.is_parameterized(bound):
        raise AssertionError("The bound circuit still contains symbols.")
    return bound


def one_excitation_target_vector(
    amplitudes: Sequence[float],
    n_qubits: int,
) -> np.ndarray:
    """Embed level amplitudes in Cirq's q0...q(n-1) ordering."""
    state = np.zeros(2**n_qubits, dtype=complex)
    for level, amplitude in enumerate(amplitudes):
        bits = ["0"] * n_qubits
        bits[level] = "1"
        state[int("".join(bits), 2)] = amplitude
    return state
_PAULI_MATRICES = {
    "I": np.eye(2, dtype=complex),
    "X": np.array([[0, 1], [1, 0]], dtype=complex),
    "Y": np.array([[0, -1j], [1j, 0]], dtype=complex),
    "Z": np.array([[1, 0], [0, -1]], dtype=complex),
}


def operator_matrix(operator: QubitOperator, n_qubits: int) -> np.ndarray:
    matrix = get_sparse_operator(operator, n_qubits=n_qubits).toarray()
    if not np.allclose(matrix, matrix.conj().T, atol=1e-9):
        raise ValueError("The QubitOperator is not Hermitian.")
    return matrix


def matrix_to_qubit_operator(
    matrix: np.ndarray,
    n_qubits: int,
    *,
    atol: float = 1e-10,
) -> QubitOperator:
    """Pauli-decompose a small matrix using q0 as the most-significant factor."""
    matrix = np.asarray(matrix, dtype=complex)
    dimension = 2**n_qubits
    if matrix.shape != (dimension, dimension):
        raise ValueError(
            f"Matrix shape {matrix.shape} does not match {n_qubits} qubits."
        )
    if n_qubits > 4:
        raise ValueError(
            "The bounded custom route limits dense-matrix Pauli decomposition to at most 4 qubits."
        )
    if not np.all(np.isfinite(matrix)):
        raise ValueError("Matrix entries must be finite.")
    if not np.allclose(matrix, matrix.conj().T, atol=1e-9):
        raise ValueError("Custom matrix must be Hermitian.")

    labels = tuple(_PAULI_MATRICES)
    result = QubitOperator()
    for pauli_labels in product(labels, repeat=n_qubits):
        pauli_matrix = np.array([[1]], dtype=complex)
        for label in pauli_labels:
            pauli_matrix = np.kron(pauli_matrix, _PAULI_MATRICES[label])
        coefficient = np.trace(pauli_matrix.conj().T @ matrix) / dimension
        if abs(coefficient) <= atol:
            continue
        if abs(coefficient.imag) > atol:
            raise ValueError(
                f"Hermitian Pauli coefficient unexpectedly complex: {coefficient}"
            )
        term = tuple(
            (qubit_index, label)
            for qubit_index, label in enumerate(pauli_labels)
            if label != "I"
        )
        result += QubitOperator(term, float(coefficient.real))

    result.compress()
    reconstructed = operator_matrix(result, n_qubits)
    if not np.allclose(reconstructed, matrix, atol=1e-8):
        raise AssertionError("Matrix-to-Pauli decomposition changed the operator.")
    return result


def parse_custom_matrix(value: Any) -> Tuple[np.ndarray, int]:
    if isinstance(value, str):
        try:
            value = ast.literal_eval(value)
        except (SyntaxError, ValueError) as error:
            raise ValueError(f"Could not parse the custom matrix: {error}") from error

    matrix = np.asarray(value, dtype=complex)
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise ValueError("Custom matrix must be square.")
    if matrix.shape[0] < 2:
        raise ValueError("Bounded custom matrices must describe at least one qubit.")
    n_qubits_float = math.log2(matrix.shape[0])
    n_qubits = int(round(n_qubits_float))
    if 2**n_qubits != matrix.shape[0]:
        raise ValueError("Custom matrix dimension must be a power of two.")
    if not np.all(np.isfinite(matrix)):
        raise ValueError("Custom matrix entries must be finite.")
    if not np.allclose(matrix, matrix.conj().T, atol=1e-9):
        raise ValueError("Custom matrix must be Hermitian.")
    return matrix, n_qubits


def parse_custom_pauli(
    value: Mapping[str, Any] | str,
    *,
    declared_n_qubits: Optional[int] = None,
) -> Tuple[QubitOperator, int]:
    if isinstance(value, str):
        parsed: Dict[str, float] = {}
        for line in value.splitlines():
            line = line.strip()
            if not line:
                continue
            if ":" not in line:
                raise ValueError(
                    "Each Pauli line must have the form 'X0 Z1: coefficient'."
                )
            term, coefficient = line.rsplit(":", 1)
            normalized_term = term.strip()
            parsed[normalized_term] = (
                parsed.get(normalized_term, 0.0) + float(coefficient.strip())
            )
        value = parsed

    operator = QubitOperator()
    for raw_term, raw_coefficient in value.items():
        coefficient = float(raw_coefficient)
        if not math.isfinite(coefficient):
            raise ValueError("Pauli coefficients must be finite real numbers.")
        term = str(raw_term).strip()
        if term.upper() == "I":
            term = ""
        operator += QubitOperator(term, coefficient)
    operator.compress()

    active_indices = [
        int(index)
        for term in operator.terms
        for index, _ in term
    ]
    inferred = max(active_indices, default=-1) + 1
    if declared_n_qubits is None:
        if inferred == 0:
            raise ValueError(
                "n_qubits is required when the custom operator is identity-only."
            )
        n_qubits = inferred
    else:
        n_qubits = int(declared_n_qubits)
        if n_qubits <= 0:
            raise ValueError("n_qubits must be positive.")
        if inferred > n_qubits:
            raise ValueError(
                f"Pauli input needs at least {inferred} qubits, not {n_qubits}."
            )

    operator_matrix(operator, n_qubits)
    return operator, n_qubits


def phase_align_nonnegative_real(
    state: Sequence[complex],
) -> Optional[np.ndarray]:
    vector = np.asarray(state, dtype=complex)
    vector = vector / np.linalg.norm(vector)
    nonzero = np.flatnonzero(np.abs(vector) > NUMERIC_TOL)
    if not len(nonzero):
        return None
    phase = np.angle(vector[int(nonzero[0])])
    aligned = vector * np.exp(-1j * phase)
    if np.max(np.abs(aligned.imag)) > 1e-9:
        return None
    real_vector = aligned.real
    if np.min(real_vector) < -1e-9:
        return None
    real_vector[np.abs(real_vector) < 1e-12] = 0.0
    return real_vector / np.linalg.norm(real_vector)


def single_qubit_ry_rz_parameters(state: Sequence[complex]) -> np.ndarray:
    """Prepare any one-qubit pure state using RY(theta) followed by RZ(phi)."""
    vector = np.asarray(state, dtype=complex)
    vector = vector / np.linalg.norm(vector)
    a, b = vector
    if abs(a) <= NUMERIC_TOL:
        return np.asarray([math.pi, 0.0], dtype=float)
    aligned = vector * np.exp(-1j * np.angle(a))
    theta = 2 * math.atan2(abs(aligned[1]), abs(aligned[0]))
    phi = float(np.angle(aligned[1])) if abs(aligned[1]) > NUMERIC_TOL else 0.0
    return np.asarray([theta, phi], dtype=float)


def build_generic_ansatz_template(
    n_qubits: int,
    *,
    n_layers: int = 1,
) -> Tuple[cirq.Circuit, Tuple[Any, ...]]:
    if n_qubits <= 0 or n_layers <= 0:
        raise ValueError("n_qubits and n_layers must be positive.")
    qubits = tuple(cirq.LineQubit.range(n_qubits))
    symbols: List[Any] = []
    circuit = cirq.Circuit()

    for layer in range(n_layers):
        for qubit_index, qubit in enumerate(qubits):
            theta = sympy.Symbol(f"theta_l{layer}_q{qubit_index}")
            phi = sympy.Symbol(f"phi_l{layer}_q{qubit_index}")
            symbols.extend([theta, phi])
            circuit.append(cirq.ry(theta).on(qubit))
            circuit.append(cirq.rz(phi).on(qubit))
        for qubit_index in range(n_qubits - 1):
            circuit.append(cirq.CNOT(qubits[qubit_index], qubits[qubit_index + 1]))

    return circuit, tuple(symbols)


def normalized_parameter_vector(value: Any, length: int, name: str) -> np.ndarray:
    if np.isscalar(value):
        vector = np.full(length, float(value), dtype=float)
    else:
        vector = np.asarray(value, dtype=float)
    if vector.shape != (length,):
        raise ValueError(f"{name} must be a scalar or a length-{length} vector.")
    if not np.all(np.isfinite(vector)):
        raise ValueError(f"{name} contains non-finite values.")
    return vector


def coupling_matrix(value: Any, n_modes: int) -> np.ndarray:
    if np.isscalar(value):
        matrix = np.full((n_modes, n_modes), float(value), dtype=float)
        np.fill_diagonal(matrix, 0.0)
    else:
        matrix = np.asarray(value, dtype=float)
        if matrix.shape != (n_modes, n_modes):
            raise ValueError(
                f"coupling must be scalar or a {n_modes}x{n_modes} matrix."
            )
        matrix = matrix.copy()
        if not np.allclose(matrix, matrix.T, atol=1e-10):
            raise ValueError("The coupling matrix must be symmetric.")
        if not np.allclose(np.diag(matrix), 0.0, atol=1e-10):
            raise ValueError("The coupling-matrix diagonal must be zero.")
    if not np.all(np.isfinite(matrix)):
        raise ValueError("The coupling matrix contains non-finite values.")
    return matrix


def build_hard_core_oscillator_hamiltonian(
    omega: Any,
    coupling: Any,
    kappa: Any,
    n_modes: int,
) -> Tuple[QubitOperator, np.ndarray, np.ndarray, np.ndarray]:
    """One qubit per mode: omega_k(n_k+1/2), n_k in {0,1}, plus hopping."""
    if n_modes <= 0:
        raise ValueError("n_modes must be positive.")
    frequencies = normalized_parameter_vector(omega, n_modes, "omega")
    spin_orbit = normalized_parameter_vector(kappa, n_modes, "kappa")
    if np.any(frequencies <= 0):
        raise ValueError("All oscillator frequencies must be positive.")
    couplings = coupling_matrix(coupling, n_modes)
    if np.any(couplings < -NUMERIC_TOL):
        raise ValueError(
            "The predefined oscillator pairing strengths must be non-negative; "
            "the Hamiltonian applies the physical minus sign explicitly."
        )

    operator = QubitOperator()
    for mode in range(n_modes):
        # omega(n+1/2), n=(I-Z)/2 -> omega*I - omega*Z/2
        operator += QubitOperator((), float(frequencies[mode]))
        operator += QubitOperator(
            ((mode, "Z"),),
            -float(frequencies[mode]) / 2 - float(spin_orbit[mode]),
        )

    for left in range(n_modes):
        for right in range(left + 1, n_modes):
            # Team-module convention: -G/2 * (XX + YY), with G >= 0.
            coefficient = -float(couplings[left, right]) / 2
            if abs(coefficient) <= NUMERIC_TOL:
                continue
            operator += QubitOperator(
                ((left, "X"), (right, "X")), coefficient
            )
            operator += QubitOperator(
                ((left, "Y"), (right, "Y")), coefficient
            )

    operator.compress()
    return operator, frequencies, spin_orbit, couplings


def exact_reference_from_matrix(
    matrix: np.ndarray,
    *,
    reference_scope: str,
    acceptance_abs_floor: float,
    target_state_labels: Optional[List[str]] = None,
) -> Dict[str, Any]:
    eigenvalues, eigenvectors = np.linalg.eigh(np.asarray(matrix, dtype=complex))
    gap = (
        float(eigenvalues[1] - eigenvalues[0])
        if len(eigenvalues) > 1
        else None
    )
    return {
        "kind": "small_system_exact_diagonalization",
        "reference_scope": reference_scope,
        "reference_energy": float(np.real(eigenvalues[0])),
        "spectrum": [float(np.real(value)) for value in eigenvalues],
        "gap": gap,
        # Keep complex amplitudes in memory; metadata() converts them to JSON-safe form.
        "target_state_amplitudes": [complex(value) for value in eigenvectors[:, 0]],
        "target_state_labels": target_state_labels,
        "acceptance_abs_floor": float(acceptance_abs_floor),
    }
def build_pairing_fermion_hamiltonian_explicit(
    level_energies: Sequence[float],
    pairing_strength: float,
) -> FermionOperator:
    hamiltonian = FermionOperator()
    n_local_levels = len(level_energies)

    for level, energy in enumerate(level_energies):
        for spin_offset in (0, 1):
            index = 2 * level + spin_offset
            hamiltonian += FermionOperator(
                ((index, 1), (index, 0)), float(energy)
            )

    for p in range(n_local_levels):
        p_plus, p_minus = 2 * p, 2 * p + 1
        for q in range(n_local_levels):
            q_plus, q_minus = 2 * q, 2 * q + 1
            hamiltonian += FermionOperator(
                (
                    (p_plus, 1),
                    (p_minus, 1),
                    (q_minus, 0),
                    (q_plus, 0),
                ),
                -float(pairing_strength),
            )

    hamiltonian.compress()
    return hamiltonian


"""Pure resource-estimation implementations bound by versioned rule IDs."""
from __future__ import annotations


def estimate_one_excitation_chain_parameter_count(*, n_qubits: int, n_layers: int = 1) -> int:
    n_qubits = int(n_qubits)
    n_layers = int(n_layers)
    if n_qubits < 0:
        raise ValueError("n_qubits must be non-negative.")
    if n_layers < 1:
        raise ValueError("n_layers must be at least one.")
    # The chain has one nearest-neighbour Givens angle per edge.
    return max(n_qubits - 1, 0)


def estimate_generic_ry_rz_parameter_count(*, n_qubits: int, n_layers: int = 1) -> int:
    n_qubits = int(n_qubits)
    n_layers = int(n_layers)
    if n_qubits < 0:
        raise ValueError("n_qubits must be non-negative.")
    if n_layers < 1:
        raise ValueError("n_layers must be at least one.")
    return 2 * n_qubits * n_layers

"""Mapping-aware Jordan--Wigner fermionic ansatz primitives.

WP11 replaces the production endpoint-only qubit exchange with an explicitly
fermionic construction.  A nonadjacent single excitation is implemented by a
fermionic-swap network:

    move the target mode next to the source with FSWAPs
    -> apply the adjacent fermionic Givens rotation
    -> undo the FSWAPs.

The conjugated circuit implements

    exp(theta * (a_target^ a_source - a_source^ a_target))

under the declared Jordan--Wigner mode ordering.  Every primitive is decomposed
into H, CNOT, RY, and RZ gates so a numerically bound circuit remains exportable
to OpenQASM 2 and checkable by PyQASM.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Any, Mapping, Sequence, Tuple

import cirq
import numpy as np
import sympy

from ...model_contracts import ModelContractError
from ...modeling import append_number_conserving_givens


JW_MAPPED_ANSATZ_POLICY_ID = "jw.ansatz.mapped_fermionic_swap_network.v1"
JW_MAPPED_ANSATZ_VERSION = "1.0.0"
JW_MAPPED_GENERATOR_CONVENTION = (
    "G(source,target)=a_target^ a_source-a_source^ a_target"
)


@dataclass(frozen=True)
class JWFermionicExcitationRoute:
    source_mode: int
    target_mode: int
    adjacent_pair: Tuple[int, int]
    forward_fswaps: Tuple[Tuple[int, int], ...]
    inverse_fswaps: Tuple[Tuple[int, int], ...]
    parameter_name: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_mode": int(self.source_mode),
            "target_mode": int(self.target_mode),
            "adjacent_pair": list(self.adjacent_pair),
            "forward_fswaps": [list(pair) for pair in self.forward_fswaps],
            "inverse_fswaps": [list(pair) for pair in self.inverse_fswaps],
            "parameter_name": self.parameter_name,
            "generator_convention": JW_MAPPED_GENERATOR_CONVENTION,
        }


def append_qasm2_fswap(
    circuit: cirq.Circuit,
    left: cirq.Qid,
    right: cirq.Qid,
) -> None:
    """Append the fermionic SWAP using only H and CNOT gates.

    FSWAP = SWAP * CZ.  The extra -1 phase on |11> is the fermionic sign that
    distinguishes mode permutation from an ordinary qubit SWAP.
    """
    # Ordinary SWAP.
    circuit.append(cirq.CNOT(left, right))
    circuit.append(cirq.CNOT(right, left))
    circuit.append(cirq.CNOT(left, right))
    # CZ, decomposed for conservative QASM2 interoperability.
    circuit.append(cirq.H(right))
    circuit.append(cirq.CNOT(left, right))
    circuit.append(cirq.H(right))


def append_adjacent_fermionic_givens(
    circuit: cirq.Circuit,
    left: cirq.Qid,
    right: cirq.Qid,
    theta: Any,
) -> None:
    """Append exp(theta * (a_right^ a_left-a_left^ a_right)).

    ``append_number_conserving_givens`` uses a historical half-angle
    parameterization.  Passing ``2*theta`` makes the public WP11 parameter the
    physical generator angle required by the conformance equation.
    """
    append_number_conserving_givens(circuit, left, right, 2 * theta)


def append_jw_mapped_single_excitation(
    circuit: cirq.Circuit,
    ordered_qubits: Sequence[cirq.Qid],
    source_mode: int,
    target_mode: int,
    theta: Any,
    *,
    parameter_name: str = "theta",
) -> JWFermionicExcitationRoute:
    """Append a JW-correct single excitation for arbitrary ordered modes.

    The routine supports either direction.  Reversing source and target
    reverses the anti-Hermitian generator and therefore negates the angle.
    """
    n_modes = len(tuple(ordered_qubits))
    source = int(source_mode)
    target = int(target_mode)
    if source == target:
        raise ModelContractError("A fermionic excitation requires two distinct modes.")
    if not 0 <= source < n_modes or not 0 <= target < n_modes:
        raise ModelContractError(
            f"Excitation modes must lie inside 0..{n_modes - 1}: "
            f"source={source}, target={target}."
        )

    low = min(source, target)
    high = max(source, target)
    effective_theta = theta if source < target else -theta
    qubits = tuple(ordered_qubits)

    forward = tuple((index, index + 1) for index in range(high - 1, low, -1))
    for left_index, right_index in forward:
        append_qasm2_fswap(circuit, qubits[left_index], qubits[right_index])

    append_adjacent_fermionic_givens(
        circuit,
        qubits[low],
        qubits[low + 1],
        effective_theta,
    )

    inverse = tuple(reversed(forward))
    for left_index, right_index in inverse:
        append_qasm2_fswap(circuit, qubits[left_index], qubits[right_index])

    return JWFermionicExcitationRoute(
        source_mode=source,
        target_mode=target,
        adjacent_pair=(low, low + 1),
        forward_fswaps=forward,
        inverse_fswaps=inverse,
        parameter_name=str(parameter_name),
    )


def append_jw_number_phase(
    circuit: cirq.Circuit,
    qubit: cirq.Qid,
    theta: Any,
) -> None:
    """Append a mapped one-mode number phase, up to a global phase."""
    circuit.append(cirq.rz(theta).on(qubit))


def append_jw_density_density_phase(
    circuit: cirq.Circuit,
    left: cirq.Qid,
    right: cirq.Qid,
    theta: Any,
) -> None:
    """Append a QASM2-safe diagonal two-mode mapped phase."""
    circuit.append(cirq.CNOT(left, right))
    circuit.append(cirq.rz(theta).on(right))
    circuit.append(cirq.CNOT(left, right))


def jw_mapped_ansatz_parameter_count(n_modes: int, n_layers: int) -> int:
    n_modes = int(n_modes)
    n_layers = int(n_layers)
    if n_modes < 2:
        raise ModelContractError("JW ground-state ansatz requires at least two modes.")
    if n_layers < 1:
        raise ModelContractError("ansatz_layers must be positive.")
    pair_count = n_modes * (n_modes - 1) // 2
    return n_layers * (2 * pair_count + n_modes)


def build_jw_mapped_fermionic_ansatz(
    n_modes: int,
    n_layers: int,
    *,
    maximum_modes: int = 4,
    maximum_layers: int = 2,
) -> tuple[cirq.Circuit, tuple[Any, ...], Mapping[str, Any]]:
    """Build the bounded WP11 mapped-fermionic ansatz.

    Exchange parameters are exact mapped single-excitation generators.  Local
    Z and ZZ blocks are mapped diagonal number/density generators.  The family
    therefore has ``mapped_fermionic_generator`` semantics within the declared
    2--4-mode fixed-particle JW composition.
    """
    n_modes = int(n_modes)
    n_layers = int(n_layers)
    if not 2 <= n_modes <= int(maximum_modes):
        raise ModelContractError(
            f"The WP11 JW composition supports 2–{int(maximum_modes)} modes."
        )
    if not 1 <= n_layers <= int(maximum_layers):
        raise ModelContractError(
            f"ansatz_layers must lie between 1 and {int(maximum_layers)}."
        )

    qubits = tuple(cirq.LineQubit.range(n_modes))
    pairs = tuple(combinations(range(n_modes), 2))
    circuit = cirq.Circuit()
    symbols: list[Any] = []
    blocks: list[dict[str, Any]] = []
    routes: list[dict[str, Any]] = []

    for layer in range(n_layers):
        ordered_pairs = pairs if layer % 2 == 0 else tuple(reversed(pairs))
        exchange_names: list[str] = []
        for source, target in ordered_pairs:
            symbol = sympy.Symbol(f"jw_ex_l{layer}_{source}_{target}")
            symbols.append(symbol)
            exchange_names.append(str(symbol))
            route = append_jw_mapped_single_excitation(
                circuit,
                qubits,
                source,
                target,
                symbol,
                parameter_name=str(symbol),
            )
            routes.append({"layer": layer, **route.to_dict()})

        local_phase_names: list[str] = []
        for mode in range(n_modes):
            symbol = sympy.Symbol(f"jw_z_l{layer}_{mode}")
            symbols.append(symbol)
            local_phase_names.append(str(symbol))
            append_jw_number_phase(circuit, qubits[mode], symbol)

        correlation_names: list[str] = []
        for left, right in ordered_pairs:
            symbol = sympy.Symbol(f"jw_zz_l{layer}_{left}_{right}")
            symbols.append(symbol)
            correlation_names.append(str(symbol))
            append_jw_density_density_phase(
                circuit,
                qubits[left],
                qubits[right],
                symbol,
            )

        blocks.append(
            {
                "layer": layer,
                "exchange_parameters": exchange_names,
                "local_phase_parameters": local_phase_names,
                "correlation_parameters": correlation_names,
            }
        )

    expected = jw_mapped_ansatz_parameter_count(n_modes, n_layers)
    if len(symbols) != expected:
        raise AssertionError(
            f"JW mapped ansatz parameter count mismatch: {len(symbols)} != {expected}"
        )

    metadata = {
        "policy_id": JW_MAPPED_ANSATZ_POLICY_ID,
        "policy_version": JW_MAPPED_ANSATZ_VERSION,
        "family": "jw_mapped_fermionic_swap_network",
        "ansatz_semantic_class": "mapped_fermionic_generator",
        "generator_domain": "fermionic_single_excitation_and_diagonal_number_generators",
        "generator_convention": JW_MAPPED_GENERATOR_CONVENTION,
        "n_layers": n_layers,
        "pair_connectivity": "all_to_all_via_reversible_fermionic_swap_networks",
        "parameter_formula": "layers * (2*C(n_modes,2) + n_modes) = layers*n_modes^2",
        "conserves_particle_number_by_construction": True,
        "mapped_generator_semantics": True,
        "nonadjacent_fermionic_signs": "implemented_by_fswap_conjugation",
        "mode_order_aware": True,
        "composition_conformance": "acceptance_verified_wp11",
        "qasm2_gate_basis": ["x", "h", "cx", "ry", "rz", "measure"],
        "parameter_blocks": blocks,
        "fermionic_excitation_routes": routes,
        "scientific_boundary": (
            "Accepted only for the declared Jordan–Wigner ordered-mode, fixed-particle, "
            "single-species composition at 2–4 modes and one or two layers. This is not "
            "a universality claim for arbitrary correlated fermionic systems."
        ),
    }
    return circuit, tuple(symbols), metadata


# ---------------------------------------------------------------------------
# Dependency-light exact generator helpers used by tests and Evidence.
# ---------------------------------------------------------------------------


def occupation_from_basis_index(index: int, n_modes: int) -> tuple[int, ...]:
    return tuple((int(index) >> (int(n_modes) - 1 - mode)) & 1 for mode in range(int(n_modes)))


def basis_index_from_occupation(occupation: Sequence[int]) -> int:
    values = tuple(int(value) & 1 for value in occupation)
    n_modes = len(values)
    return int(sum(value << (n_modes - 1 - mode) for mode, value in enumerate(values)))


def _annihilate(occupation: tuple[int, ...], mode: int):
    if occupation[mode] == 0:
        return None, 0
    sign = -1 if sum(occupation[:mode]) % 2 else 1
    updated = list(occupation)
    updated[mode] = 0
    return tuple(updated), sign


def _create(occupation: tuple[int, ...], mode: int):
    if occupation[mode] == 1:
        return None, 0
    sign = -1 if sum(occupation[:mode]) % 2 else 1
    updated = list(occupation)
    updated[mode] = 1
    return tuple(updated), sign


def exact_fermionic_single_excitation_generator(
    n_modes: int,
    source_mode: int,
    target_mode: int,
) -> np.ndarray:
    """Return the full Fock-space matrix of a_t^ a_s-a_s^ a_t."""
    n_modes = int(n_modes)
    source = int(source_mode)
    target = int(target_mode)
    if source == target:
        raise ValueError("source_mode and target_mode must differ")
    dimension = 1 << n_modes
    matrix = np.zeros((dimension, dimension), dtype=np.complex128)

    def add_term(create_mode: int, annihilate_mode: int, coefficient: float) -> None:
        for column in range(dimension):
            occupation = occupation_from_basis_index(column, n_modes)
            after_a, sign_a = _annihilate(occupation, annihilate_mode)
            if after_a is None:
                continue
            after_c, sign_c = _create(after_a, create_mode)
            if after_c is None:
                continue
            row = basis_index_from_occupation(after_c)
            matrix[row, column] += coefficient * sign_a * sign_c

    add_term(target, source, +1.0)
    add_term(source, target, -1.0)
    return matrix


def fixed_particle_indices(n_modes: int, particle_number: int) -> tuple[int, ...]:
    return tuple(
        index
        for index in range(1 << int(n_modes))
        if int(index).bit_count() == int(particle_number)
    )


def restrict_matrix_to_particle_sector(
    matrix: np.ndarray,
    *,
    n_modes: int,
    particle_number: int,
) -> np.ndarray:
    indices = fixed_particle_indices(n_modes, particle_number)
    return np.asarray(matrix, dtype=np.complex128)[np.ix_(indices, indices)]


__all__ = [
    "JW_MAPPED_ANSATZ_POLICY_ID",
    "JW_MAPPED_ANSATZ_VERSION",
    "JW_MAPPED_GENERATOR_CONVENTION",
    "JWFermionicExcitationRoute",
    "append_qasm2_fswap",
    "append_adjacent_fermionic_givens",
    "append_jw_mapped_single_excitation",
    "append_jw_number_phase",
    "append_jw_density_density_phase",
    "jw_mapped_ansatz_parameter_count",
    "build_jw_mapped_fermionic_ansatz",
    "occupation_from_basis_index",
    "basis_index_from_occupation",
    "exact_fermionic_single_excitation_generator",
    "fixed_particle_indices",
    "restrict_matrix_to_particle_sector",
]

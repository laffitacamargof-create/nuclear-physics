"""JW ground-state support for the bounded general spin-orbital cell.

Phase A.3.2 adds the first circuit-executed cell on top of the representation
and mapping foundation built in Phase A.3.1:

    general spin-orbital × ground-state energy × Jordan–Wigner.

The implementation is deliberately bounded. It prepares a declared JW
occupation determinant. WP11 adds a production mapping-aware fermionic-swap
network ansatz; the earlier endpoint-only qubit exchange remains available only
as the frozen WP0 negative composition fixture.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from math import atan2
from typing import Any, Dict, Iterable, Mapping, Sequence, Tuple

import cirq
import numpy as np
import sympy

from ...model_contracts import ModelContractError
from ...modeling import append_number_conserving_givens, basis_index
from .jw_fermionic_ansatz import (
    build_jw_mapped_fermionic_ansatz,
    jw_mapped_ansatz_parameter_count,
)


JW_GROUND_STATE_CELL_ID = "fermion.general_spin_orbital::ground_state_energy"
JW_GROUND_STATE_MAX_MODES = 4
JW_GROUND_STATE_MAX_LAYERS = 2
JW_SECTOR_LEAKAGE_TOLERANCE = 1e-10


@dataclass(frozen=True)
class JWGroundStateAcceptancePreset:
    preset_id: str
    label: str
    n_modes: int
    target_particle_number: int
    mode_labels: Tuple[str, ...]
    one_body_terms: Tuple[Tuple[int, int, float], ...]
    two_body_terms: Tuple[Tuple[int, int, int, int, float], ...]
    initial_occupied_modes: Tuple[int, ...]
    ansatz_layers: int
    expected_reference_energy: float
    acceptance_abs_floor: float = 0.03

    def request(self, *, run_mode: str = "single_evaluation") -> Dict[str, Any]:
        return {
            "model_id": "fermion.general_spin_orbital",
            "method": "general_spin_orbital",
            "problem": "jw_ground_state",
            "task_id": "ground_state_energy",
            "mapping_id": "jordan_wigner.v1",
            "execution_mode": "local_simulator",
            "target_backend": "google",
            "run_mode": run_mode,
            "shots": 8192,
            "final_shots": 16384,
            "max_evaluations": 120,
            "energy_tolerance": 0.002,
            "convergence_patience": 8,
            "rhobeg": 0.5,
            "acceptance_abs_floor": self.acceptance_abs_floor,
            "sector_leakage_floor": JW_SECTOR_LEAKAGE_TOLERANCE,
            "seed": 42,
            "parameters": {
                "n_modes": self.n_modes,
                "particle_species": "neutron",
                "mode_labels": list(self.mode_labels),
                "one_body_terms": [list(item) for item in self.one_body_terms],
                "two_body_terms": [list(item) for item in self.two_body_terms],
                "target_particle_number": self.target_particle_number,
                "initial_occupied_modes": list(self.initial_occupied_modes),
                "ansatz_layers": self.ansatz_layers,
                "declared_symmetries": ["particle_number"],
                "coefficient_convention": "explicit_operator_coefficient",
                "operator_ordering_convention": "a_p^ a_q^ a_s a_r",
                "constant": 0.0,
                "energy_unit": "MeV",
            },
            "requested_observables": ["sector_energy", "particle_number"],
            # mapping_id is a resolver control and sector_leakage_floor is a
            # verification control; neither belongs to TaskInstance.parameters.
        }


# Exact values were independently derived in the fixed-particle Fock-space
# matrices.  The four-mode interaction is U * sum_{p<q} n_p n_q, which is a
# non-zero two-body input but a constant shift inside the N=2 sector.  This
# makes the acceptance target an exactly representable Slater determinant while
# still exercising the general one-/two-body input contract.
GENERAL_SPIN_ORBITAL_JW_ACCEPTANCE_PRESETS: Tuple[JWGroundStateAcceptancePreset, ...] = (
    JWGroundStateAcceptancePreset(
        preset_id="two_modes_one_particle",
        label="Two modes / one particle / hopping",
        n_modes=2,
        target_particle_number=1,
        mode_labels=("neutron|a|m=+1/2", "neutron|b|m=+1/2"),
        one_body_terms=(
            (0, 0, 0.0),
            (1, 1, 1.0),
            (0, 1, 0.30),
            (1, 0, 0.30),
        ),
        two_body_terms=tuple(),
        initial_occupied_modes=(0,),
        ansatz_layers=1,
        expected_reference_energy=-0.08309518948453004,
        acceptance_abs_floor=0.02,
    ),
    JWGroundStateAcceptancePreset(
        preset_id="four_modes_two_particles",
        label="Four modes / two particles / one- and two-body input",
        n_modes=4,
        target_particle_number=2,
        mode_labels=(
            "neutron|a|m=+1/2",
            "neutron|a|m=-1/2",
            "neutron|b|m=+1/2",
            "neutron|b|m=-1/2",
        ),
        one_body_terms=(
            (0, 0, 0.0),
            (1, 1, 0.2),
            (2, 2, 1.0),
            (3, 3, 1.2),
            (0, 2, 0.15),
            (2, 0, 0.15),
            (1, 3, -0.10),
            (3, 1, -0.10),
        ),
        two_body_terms=tuple(
            (p, q, p, q, 0.08)
            for p, q in combinations(range(4), 2)
        ),
        initial_occupied_modes=(0, 1),
        ansatz_layers=1,
        expected_reference_energy=0.24808272319519392,
        acceptance_abs_floor=0.03,
    ),
)


def jw_ansatz_parameter_count(n_modes: int, n_layers: int) -> int:
    n_modes = int(n_modes)
    n_layers = int(n_layers)
    if n_modes < 2:
        raise ModelContractError("JW ground-state ansatz requires at least two modes.")
    if n_layers < 1:
        raise ModelContractError("ansatz_layers must be positive.")
    pair_count = n_modes * (n_modes - 1) // 2
    # exchange + local RZ + pairwise ZZ for every layer
    return n_layers * (2 * pair_count + n_modes)


def _declared_initial_modes(parameters: Mapping[str, Any]) -> Tuple[int, ...]:
    value = parameters.get("initial_occupied_modes", ())
    if value is None or value == "":
        return tuple()
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return tuple()
        return tuple(int(item.strip()) for item in text.split(",") if item.strip())
    return tuple(int(item) for item in value)


def select_initial_occupied_modes(spin_instance, parameters: Mapping[str, Any]) -> Tuple[int, ...]:
    """Choose a determinant without using the exact many-body reference.

    A user declaration wins.  Otherwise the policy fills the modes with the
    lowest real diagonal one-body energies.  This is an inspectable one-body
    heuristic, not a classical many-body warm start.
    """
    target = int(spin_instance.total_target_particles)
    supplied = _declared_initial_modes(parameters)
    if supplied:
        occupied = supplied
        strategy = "user_declared"
    else:
        diagonal = np.zeros(spin_instance.n_modes, dtype=float)
        for term in spin_instance.one_body_terms:
            if term.p == term.q:
                if abs(term.coefficient.imag) > 1e-10:
                    raise ModelContractError(
                        "Diagonal one-body energies must be real when deriving the initial determinant."
                    )
                diagonal[term.p] += float(term.coefficient.real)
        occupied = tuple(
            int(index)
            for index in sorted(range(spin_instance.n_modes), key=lambda i: (diagonal[i], i))[:target]
        )
        strategy = "lowest_declared_one_body_diagonal"

    if len(occupied) != target:
        raise ModelContractError(
            f"Initial occupation requires exactly {target} modes, received {len(occupied)}."
        )
    if len(set(occupied)) != len(occupied):
        raise ModelContractError("Initial occupied modes must be unique.")
    if any(index < 0 or index >= spin_instance.n_modes for index in occupied):
        raise ModelContractError(
            f"Initial occupied modes must lie inside 0..{spin_instance.n_modes - 1}."
        )
    # Store the strategy on the mutable return convention used by the policy.
    select_initial_occupied_modes.last_strategy = strategy  # type: ignore[attr-defined]
    return tuple(sorted(occupied))


select_initial_occupied_modes.last_strategy = "not_run"  # type: ignore[attr-defined]


def append_jw_zz_phase(
    circuit: cirq.Circuit,
    left: cirq.Qid,
    right: cirq.Qid,
    theta: Any,
) -> None:
    """Append exp(-i theta Z_left Z_right / 2) in QASM2-safe gates."""
    circuit.append(cirq.CNOT(left, right))
    circuit.append(cirq.rz(theta).on(right))
    circuit.append(cirq.CNOT(left, right))


def build_jw_number_preserving_ansatz(
    n_modes: int,
    n_layers: int,
) -> Tuple[cirq.Circuit, Tuple[Any, ...], Mapping[str, Any]]:
    """Build the frozen WP0 particle-number-preserving candidate circuit.

    Each layer contains endpoint-only real qubit exchanges, local RZ phases,
    and all-to-all ZZ correlation phases.  The circuit preserves total
    computational-basis population under JW occupation coding.  It is not
    accepted as a mapped fermionic-generator ansatz for nonadjacent modes; WP0
    keeps it unchanged so the failure remains a permanent regression fixture.
    """
    n_modes = int(n_modes)
    n_layers = int(n_layers)
    if not 2 <= n_modes <= JW_GROUND_STATE_MAX_MODES:
        raise ModelContractError(
            f"The Phase A.3.2 JW execution cell supports 2–{JW_GROUND_STATE_MAX_MODES} modes."
        )
    if not 1 <= n_layers <= JW_GROUND_STATE_MAX_LAYERS:
        raise ModelContractError(
            f"ansatz_layers must lie between 1 and {JW_GROUND_STATE_MAX_LAYERS}."
        )

    qubits = tuple(cirq.LineQubit.range(n_modes))
    pairs = tuple(combinations(range(n_modes), 2))
    circuit = cirq.Circuit()
    symbols: list[Any] = []
    blocks: list[dict[str, Any]] = []

    for layer in range(n_layers):
        ordered_pairs = pairs if layer % 2 == 0 else tuple(reversed(pairs))
        exchange_names = []
        for left, right in ordered_pairs:
            symbol = sympy.Symbol(f"jw_ex_l{layer}_{left}_{right}")
            symbols.append(symbol)
            exchange_names.append(str(symbol))
            append_number_conserving_givens(
                circuit, qubits[left], qubits[right], symbol
            )

        local_phase_names = []
        for mode in range(n_modes):
            symbol = sympy.Symbol(f"jw_z_l{layer}_{mode}")
            symbols.append(symbol)
            local_phase_names.append(str(symbol))
            circuit.append(cirq.rz(symbol).on(qubits[mode]))

        correlation_names = []
        for left, right in ordered_pairs:
            symbol = sympy.Symbol(f"jw_zz_l{layer}_{left}_{right}")
            symbols.append(symbol)
            correlation_names.append(str(symbol))
            append_jw_zz_phase(circuit, qubits[left], qubits[right], symbol)

        blocks.append({
            "layer": layer,
            "exchange_parameters": exchange_names,
            "local_phase_parameters": local_phase_names,
            "correlation_parameters": correlation_names,
        })

    expected = jw_ansatz_parameter_count(n_modes, n_layers)
    if len(symbols) != expected:
        raise AssertionError(f"JW ansatz parameter count mismatch: {len(symbols)} != {expected}")
    metadata = {
        "family": "jw_number_preserving_exchange_phase",
        "n_layers": n_layers,
        "pair_connectivity": "all_to_all_with_reversed_order_on_alternating_layers",
        "parameter_formula": "layers * (2*C(n_modes,2) + n_modes) = layers*n_modes^2",
        "conserves_particle_number_by_construction": True,
        "ansatz_semantic_class": "qubit_native",
        "mapped_generator_equivalence": "failed_for_nonadjacent_jw_excitations",
        "composition_conformance": "failed",
        "failure_code": "ANSATZ_GENERATOR_MAPPING_MISMATCH",
        "do_not_describe_as": "JW-mapped fermionic excitation ansatz",
        "qasm2_gate_basis": ["x", "cx", "ry", "rz", "measure"],
        "parameter_blocks": blocks,
        "scientific_boundary": (
            "This frozen candidate is particle-number preserving but is not equivalent "
            "to nonadjacent JW-mapped fermionic excitation generators. It is retained "
            "only as the WP0 negative composition fixture until Phase A.3.2c."
        ),
    }
    return circuit, tuple(symbols), metadata


def fixed_particle_sector_basis(n_modes: int, particle_number: int) -> Tuple[Tuple[int, ...], Tuple[int, ...]]:
    occupations = tuple(combinations(range(int(n_modes)), int(particle_number)))
    indices = tuple(basis_index(item, int(n_modes)) for item in occupations)
    return occupations, indices


def exact_fixed_particle_reference(
    fermion_operator: Any,
    *,
    n_modes: int,
    particle_number: int,
    acceptance_abs_floor: float,
    validity: Mapping[str, Any],
) -> Dict[str, Any]:
    """Independent bounded reference from the FermionOperator Fock-space matrix."""
    from openfermion import get_sparse_operator

    matrix = np.asarray(
        get_sparse_operator(fermion_operator, n_qubits=int(n_modes)).toarray(),
        dtype=np.complex128,
    )
    if not np.allclose(matrix, matrix.conj().T, atol=1e-10):
        raise ModelContractError("The FermionOperator matrix is not Hermitian.")
    occupations, indices = fixed_particle_sector_basis(n_modes, particle_number)
    if not indices:
        raise ModelContractError("The declared fixed-particle sector is empty.")
    sector_matrix = matrix[np.ix_(indices, indices)]
    sector_matrix = (sector_matrix + sector_matrix.conj().T) / 2
    eigenvalues, eigenvectors = np.linalg.eigh(sector_matrix)
    full_spectrum = np.linalg.eigvalsh((matrix + matrix.conj().T) / 2)
    labels = ["occupied_modes_" + "_".join(map(str, item)) for item in occupations]
    return {
        "kind": "small_exact_general_spin_orbital_fixed_particle_sector",
        "reference_scope": (
            f"general spin-orbital FermionOperator in the fixed N={particle_number} "
            f"sector of {n_modes} modes"
        ),
        "reference_energy": float(np.real(eigenvalues[0])),
        "spectrum": [float(np.real(value)) for value in eigenvalues],
        "full_spectrum": [float(np.real(value)) for value in full_spectrum],
        "target_sector_spectrum": [float(np.real(value)) for value in eigenvalues],
        "gap": (
            None if len(eigenvalues) < 2
            else float(np.real(eigenvalues[1] - eigenvalues[0]))
        ),
        "target_state_amplitudes": [complex(value) for value in eigenvectors[:, 0]],
        "target_state_labels": labels,
        "sector_basis_occupations": [list(item) for item in occupations],
        "sector_basis_indices": [int(value) for value in indices],
        "target_particle_number": int(particle_number),
        "target_popcount": int(particle_number),
        "acceptance_abs_floor": float(acceptance_abs_floor),
        "reference_provenance": (
            "Exact diagonalisation of the standardized FermionOperator projected "
            "onto the declared fixed-particle occupation basis; independent of the "
            "sampled VQE estimate."
        ),
        "validity": dict(validity),
    }


def _lowest_eigenvector_rotation(e_left: float, e_right: float, hopping: float) -> float:
    """Physical generator angle for the lower eigenvector of a real 2x2 block."""
    matrix = np.asarray([[e_left, hopping], [hopping, e_right]], dtype=float)
    _, vectors = np.linalg.eigh(matrix)
    vector = np.asarray(vectors[:, 0], dtype=float)
    # Choose a stable global sign with a non-negative source-mode component.
    if vector[0] < 0:
        vector *= -1
    return float(atan2(float(vector[1]), float(vector[0])))


def acceptance_fixture_parameters(
    parameter_names: Sequence[str],
    preset_id: str,
) -> Tuple[float, ...]:
    """Return the WP11 mapped-generator acceptance point, never a runtime default."""
    values = {str(name): 0.0 for name in parameter_names}
    if preset_id == "two_modes_one_particle":
        values["jw_ex_l0_0_1"] = _lowest_eigenvector_rotation(0.0, 1.0, 0.30)
    elif preset_id == "four_modes_two_particles":
        values["jw_ex_l0_0_2"] = _lowest_eigenvector_rotation(0.0, 1.0, 0.15)
        values["jw_ex_l0_1_3"] = _lowest_eigenvector_rotation(0.2, 1.2, -0.10)
    else:
        raise KeyError(f"Unknown JW ground-state acceptance preset {preset_id!r}.")
    return tuple(float(values[str(name)]) for name in parameter_names)


def legacy_bare_exchange_fixture_parameters(
    parameter_names: Sequence[str],
    preset_id: str,
) -> Tuple[float, ...]:
    """Historical half-angle parameters for the permanent WP0 negative fixture."""
    values = {str(name): 0.0 for name in parameter_names}
    if preset_id == "two_modes_one_particle":
        values["jw_ex_l0_0_1"] = 2.0 * _lowest_eigenvector_rotation(0.0, 1.0, 0.30)
    elif preset_id == "four_modes_two_particles":
        values["jw_ex_l0_0_2"] = 2.0 * _lowest_eigenvector_rotation(0.0, 1.0, 0.15)
        values["jw_ex_l0_1_3"] = 2.0 * _lowest_eigenvector_rotation(0.2, 1.2, -0.10)
    else:
        raise KeyError(f"Unknown JW ground-state acceptance preset {preset_id!r}.")
    return tuple(float(values[str(name)]) for name in parameter_names)

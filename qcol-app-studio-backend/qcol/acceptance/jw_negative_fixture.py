"""Known-invalid JW composition fixture frozen by WP0.

The fixture separates two facts that the old Phase A.3.2 test conflated:

* the current bare endpoint exchange preserves computational-basis particle
  number; and
* it is not equivalent to a nonadjacent Jordan-Wigner-mapped fermionic
  excitation because it cannot condition the relative sign on the parity of
  intermediate modes.

The dependency-light calculation below is intentionally independent of Cirq,
OpenFermion, the optimizer, and sampled execution.  A scientific-stack helper
at the bottom verifies that the current runtime implementation reproduces the
same frozen failure when those libraries are installed.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
import math
from typing import Any, Dict, Iterable, Sequence, Tuple

from ..compatibility import CompatibilityFailureCode, get_failure_spec

JW_NEGATIVE_FIXTURE_ID = "jw.nonadjacent.bare_exchange.four_modes_two_particles.v1"
EXPECTED_REFERENCE_ENERGY = 0.24808272319519392
EXPECTED_BARE_EXCHANGE_ENERGY = 0.33427716819288117
EXPECTED_ABSOLUTE_ENERGY_ERROR = 0.08619444499768725
EXPECTED_STATE_FIDELITY = 0.9182158057476059
FIXTURE_NUMERICAL_TOLERANCE = 1e-10


@dataclass(frozen=True)
class JWNegativeFixtureReport:
    fixture_id: str
    failure_code: str
    failure_message: str
    particle_number_preserved: bool
    mapped_generator_equivalent: bool
    nonadjacent_source_mode: int
    nonadjacent_target_mode: int
    intermediate_modes: Tuple[int, ...]
    even_intermediate_parity_exact_sign: int
    odd_intermediate_parity_exact_sign: int
    bare_exchange_even_sign: int
    bare_exchange_odd_sign: int
    reference_energy: float
    bare_exchange_energy: float
    absolute_energy_error: float
    state_fidelity: float
    sector_leakage: float
    expected_exact_sector_amplitudes: Tuple[float, ...]
    observed_bare_exchange_amplitudes: Tuple[float, ...]
    sector_basis_occupations: Tuple[Tuple[int, ...], ...]
    accepted_as_positive_fixture: bool
    negative_regression_passed: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": "qcol-jw-negative-fixture/1.0",
            "fixture_id": self.fixture_id,
            "failure_code": self.failure_code,
            "failure_message": self.failure_message,
            "particle_number_preserved": bool(self.particle_number_preserved),
            "mapped_generator_equivalent": bool(self.mapped_generator_equivalent),
            "nonadjacent_source_mode": self.nonadjacent_source_mode,
            "nonadjacent_target_mode": self.nonadjacent_target_mode,
            "intermediate_modes": list(self.intermediate_modes),
            "parity_sign_check": {
                "even_intermediate_parity_exact_sign": self.even_intermediate_parity_exact_sign,
                "odd_intermediate_parity_exact_sign": self.odd_intermediate_parity_exact_sign,
                "bare_exchange_even_sign": self.bare_exchange_even_sign,
                "bare_exchange_odd_sign": self.bare_exchange_odd_sign,
            },
            "reference_energy": self.reference_energy,
            "bare_exchange_energy": self.bare_exchange_energy,
            "absolute_energy_error": self.absolute_energy_error,
            "state_fidelity": self.state_fidelity,
            "sector_leakage": self.sector_leakage,
            "sector_basis_occupations": [list(item) for item in self.sector_basis_occupations],
            "expected_exact_sector_amplitudes": list(self.expected_exact_sector_amplitudes),
            "observed_bare_exchange_amplitudes": list(self.observed_bare_exchange_amplitudes),
            "accepted_as_positive_fixture": bool(self.accepted_as_positive_fixture),
            "negative_regression_passed": bool(self.negative_regression_passed),
            "interpretation": (
                "PASS means QCOL correctly rejected the known-invalid composition. "
                "It does not mean the JW ground-state cell is accepted."
            ),
        }


def _annihilate(occupation: Tuple[int, ...], mode: int) -> tuple[Tuple[int, ...] | None, int]:
    if occupation[mode] == 0:
        return None, 0
    sign = -1 if sum(occupation[:mode]) % 2 else 1
    updated = list(occupation)
    updated[mode] = 0
    return tuple(updated), sign


def _create(occupation: Tuple[int, ...], mode: int) -> tuple[Tuple[int, ...] | None, int]:
    if occupation[mode] == 1:
        return None, 0
    sign = -1 if sum(occupation[:mode]) % 2 else 1
    updated = list(occupation)
    updated[mode] = 1
    return tuple(updated), sign


def _one_body_action(occupation: Tuple[int, ...], p: int, q: int) -> tuple[Tuple[int, ...] | None, int]:
    after_annihilation, sign_a = _annihilate(occupation, q)
    if after_annihilation is None:
        return None, 0
    after_creation, sign_c = _create(after_annihilation, p)
    if after_creation is None:
        return None, 0
    return after_creation, sign_a * sign_c


def _two_body_action(
    occupation: Tuple[int, ...], p: int, q: int, r: int, s: int
) -> tuple[Tuple[int, ...] | None, int]:
    # Contract convention: a_p^ a_q^ a_s a_r; rightmost operator acts first.
    current: Tuple[int, ...] | None = occupation
    sign = 1
    for operation, mode in ((_annihilate, r), (_annihilate, s), (_create, q), (_create, p)):
        if current is None:
            return None, 0
        current, local_sign = operation(current, mode)
        sign *= local_sign
    return current, sign


def _sector_basis(n_modes: int, particle_number: int) -> tuple[Tuple[Tuple[int, ...], ...], Dict[Tuple[int, ...], int]]:
    occupied_sets = tuple(combinations(range(n_modes), particle_number))
    occupations = tuple(
        tuple(1 if mode in occupied else 0 for mode in range(n_modes))
        for occupied in occupied_sets
    )
    return occupations, {occupation: index for index, occupation in enumerate(occupations)}


def _fixture_hamiltonian() -> tuple[list[list[float]], Tuple[Tuple[int, ...], ...]]:
    """Build the frozen six-dimensional sector matrix using only the stdlib.

    Gate A is intentionally independent of NumPy/Cirq/OpenFermion.  The full
    scientific gate repeats the same fixture through the live quantum stack.
    """
    n_modes = 4
    particle_number = 2
    occupations, index = _sector_basis(n_modes, particle_number)
    size = len(occupations)
    matrix = [[0.0 for _ in range(size)] for _ in range(size)]
    one_body_terms = (
        (0, 0, 0.0),
        (1, 1, 0.2),
        (2, 2, 1.0),
        (3, 3, 1.2),
        (0, 2, 0.15),
        (2, 0, 0.15),
        (1, 3, -0.10),
        (3, 1, -0.10),
    )
    two_body_terms = tuple(
        (p, q, p, q, 0.08)
        for p, q in combinations(range(n_modes), 2)
    )

    for column, occupation in enumerate(occupations):
        for p, q, coefficient in one_body_terms:
            target, sign = _one_body_action(occupation, p, q)
            if target is not None and target in index:
                matrix[index[target]][column] += coefficient * sign
        for p, q, r, s_mode, coefficient in two_body_terms:
            target, sign = _two_body_action(
                occupation, p, q, r, s_mode
            )
            if target is not None and target in index:
                matrix[index[target]][column] += coefficient * sign

    symmetric = [
        [
            0.5 * (matrix[row][column] + matrix[column][row])
            for column in range(size)
        ]
        for row in range(size)
    ]
    return symmetric, occupations


def _lowest_real_eigenvector(
    e_left: float,
    e_right: float,
    hopping: float,
) -> tuple[tuple[float, float], float]:
    """Return the normalized lower eigenvector/eigenvalue of a 2x2 block."""
    if abs(hopping) <= 1e-15:
        if e_left <= e_right:
            return (1.0, 0.0), float(e_left)
        return (0.0, 1.0), float(e_right)

    discriminant = math.sqrt(
        (e_left - e_right) ** 2 + 4.0 * hopping**2
    )
    eigenvalue = 0.5 * (e_left + e_right - discriminant)
    left = 1.0
    right = (eigenvalue - e_left) / hopping
    norm = math.hypot(left, right)
    left /= norm
    right /= norm
    if left < 0.0:
        left *= -1.0
        right *= -1.0
    return (left, right), float(eigenvalue)


def _dot(left: Sequence[float], right: Sequence[float]) -> float:
    return float(sum(a * b for a, b in zip(left, right)))


def _quadratic_form(
    vector: Sequence[float],
    matrix: Sequence[Sequence[float]],
) -> float:
    return float(
        sum(
            vector[row] * matrix[row][column] * vector[column]
            for row in range(len(vector))
            for column in range(len(vector))
        )
    )


def _vectors_close(
    left: Sequence[float],
    right: Sequence[float],
    *,
    tolerance: float,
) -> bool:
    return all(abs(a - b) <= tolerance for a, b in zip(left, right))

def _fermionic_move_sign(occupation: Sequence[int], source: int, target: int) -> int:
    occ = tuple(int(value) for value in occupation)
    moved, sign = _one_body_action(occ, target, source)
    if moved is None:
        raise ValueError("The fixture state does not permit the declared fermionic move.")
    return int(sign)


def evaluate_frozen_jw_negative_fixture() -> JWNegativeFixtureReport:
    """Evaluate the frozen failure using only Python's standard library."""
    hamiltonian, occupations = _fixture_hamiltonian()

    first_orbital, first_energy = _lowest_real_eigenvector(
        0.0, 1.0, 0.15
    )
    second_orbital, second_energy = _lowest_real_eigenvector(
        0.2, 1.2, -0.10
    )
    c_a, s_a = first_orbital
    c_b, s_b = second_orbital

    # Basis order: (0,1), (0,2), (0,3), (1,2), (1,3), (2,3).
    # The exact antisymmetric state differs from the bare endpoint exchange in
    # the sign of the (1,2) component.
    bare_state = (
        c_a * c_b,
        0.0,
        c_a * s_b,
        s_a * c_b,
        0.0,
        s_a * s_b,
    )
    correct_state = (
        c_a * c_b,
        0.0,
        c_a * s_b,
        -s_a * c_b,
        0.0,
        s_a * s_b,
    )

    # Every two-particle configuration in the frozen fixture receives the same
    # density interaction shift of 0.08 MeV.
    reference_energy = float(first_energy + second_energy + 0.08)
    correct_energy = _quadratic_form(correct_state, hamiltonian)
    bare_energy = _quadratic_form(bare_state, hamiltonian)
    energy_error = abs(bare_energy - reference_energy)
    fidelity = abs(_dot(correct_state, bare_state)) ** 2

    even_occupation = (1, 0, 0, 0)
    odd_occupation = (1, 1, 0, 0)
    exact_even_sign = _fermionic_move_sign(
        even_occupation, source=0, target=2
    )
    exact_odd_sign = _fermionic_move_sign(
        odd_occupation, source=0, target=2
    )
    # An endpoint-only exchange cannot inspect mode 1; its sign is identical in
    # the even- and odd-intermediate-parity cases.
    bare_even_sign = 1
    bare_odd_sign = 1

    particle_number_preserved = all(
        sum(item) == 2
        for item, amplitude in zip(occupations, bare_state)
        if abs(amplitude) > 1e-14
    )
    sector_leakage = 0.0 if particle_number_preserved else 1.0
    mapped_equivalent = (
        exact_even_sign == bare_even_sign
        and exact_odd_sign == bare_odd_sign
        and _vectors_close(
            bare_state,
            correct_state,
            tolerance=FIXTURE_NUMERICAL_TOLERANCE,
        )
    )
    failure = get_failure_spec(
        CompatibilityFailureCode.ANSATZ_GENERATOR_MAPPING_MISMATCH
    )
    negative_pass = (
        particle_number_preserved
        and not mapped_equivalent
        and exact_even_sign == -exact_odd_sign
        and bare_even_sign == bare_odd_sign
        and math.isclose(
            correct_energy,
            reference_energy,
            abs_tol=FIXTURE_NUMERICAL_TOLERANCE,
        )
        and math.isclose(
            reference_energy,
            EXPECTED_REFERENCE_ENERGY,
            abs_tol=FIXTURE_NUMERICAL_TOLERANCE,
        )
        and math.isclose(
            bare_energy,
            EXPECTED_BARE_EXCHANGE_ENERGY,
            abs_tol=FIXTURE_NUMERICAL_TOLERANCE,
        )
        and math.isclose(
            energy_error,
            EXPECTED_ABSOLUTE_ENERGY_ERROR,
            abs_tol=FIXTURE_NUMERICAL_TOLERANCE,
        )
        and math.isclose(
            fidelity,
            EXPECTED_STATE_FIDELITY,
            abs_tol=FIXTURE_NUMERICAL_TOLERANCE,
        )
    )

    occupied_labels = tuple(
        tuple(index for index, bit in enumerate(item) if bit)
        for item in occupations
    )
    return JWNegativeFixtureReport(
        fixture_id=JW_NEGATIVE_FIXTURE_ID,
        failure_code=failure.code.value,
        failure_message=failure.message,
        particle_number_preserved=particle_number_preserved,
        mapped_generator_equivalent=mapped_equivalent,
        nonadjacent_source_mode=0,
        nonadjacent_target_mode=2,
        intermediate_modes=(1,),
        even_intermediate_parity_exact_sign=exact_even_sign,
        odd_intermediate_parity_exact_sign=exact_odd_sign,
        bare_exchange_even_sign=bare_even_sign,
        bare_exchange_odd_sign=bare_odd_sign,
        reference_energy=reference_energy,
        bare_exchange_energy=bare_energy,
        absolute_energy_error=energy_error,
        state_fidelity=fidelity,
        sector_leakage=sector_leakage,
        expected_exact_sector_amplitudes=tuple(correct_state),
        observed_bare_exchange_amplitudes=tuple(bare_state),
        sector_basis_occupations=occupied_labels,
        accepted_as_positive_fixture=False,
        negative_regression_passed=negative_pass,
    )

def evaluate_runtime_jw_negative_fixture() -> Dict[str, Any]:
    """Verify that the archived bare-exchange implementation matches the frozen failure.

    This function is imported only by the scientific acceptance gate.  It does
    not modify the runtime or reinterpret a sampled VQE result.
    """
    import numpy as np
    import cirq
    from openfermion import get_sparse_operator

    from ..modeling import bind_parameters
    from ..models.general_spin_orbital.jw_ground_state import (
        GENERAL_SPIN_ORBITAL_JW_ACCEPTANCE_PRESETS,
        JW_SECTOR_LEAKAGE_TOLERANCE,
        build_jw_number_preserving_ansatz,
        legacy_bare_exchange_fixture_parameters,
    )
    from ..realization import resolve_request_to_quantum_realization

    preset = next(
        item for item in GENERAL_SPIN_ORBITAL_JW_ACCEPTANCE_PRESETS
        if item.preset_id == "four_modes_two_particles"
    )
    request = preset.request(run_mode="single_evaluation")
    realization = resolve_request_to_quantum_realization(request)
    artifact = realization.runtime_artifact
    legacy_variational, legacy_symbols, _ = build_jw_number_preserving_ansatz(
        artifact.n_qubits,
        preset.ansatz_layers,
    )
    legacy_template = cirq.Circuit(realization.initial_state_circuit)
    legacy_template += cirq.Circuit(legacy_variational)
    names = [str(symbol) for symbol in legacy_symbols]
    parameters = legacy_bare_exchange_fixture_parameters(names, preset.preset_id)
    bound = bind_parameters(legacy_template, legacy_symbols, parameters)
    qubits = tuple(cirq.LineQubit.range(artifact.n_qubits))
    state = np.asarray(
        cirq.Simulator(dtype=np.complex128)
        .simulate(bound, qubit_order=qubits)
        .final_state_vector,
        dtype=np.complex128,
    )
    matrix = np.asarray(
        get_sparse_operator(
            artifact.hamiltonian_payload,
            n_qubits=artifact.n_qubits,
        ).toarray(),
        dtype=np.complex128,
    )
    energy = float(np.real(np.vdot(state, matrix @ state)))
    probabilities = np.abs(state) ** 2
    target = int(artifact.target_sector["particle_number"])
    in_sector = sum(
        float(probability)
        for index, probability in enumerate(probabilities)
        if int(index).bit_count() == target
    )
    leakage = max(0.0, 1.0 - in_sector)
    reference = float(artifact.exact_reference["reference_energy"])
    pure = evaluate_frozen_jw_negative_fixture()
    matches_frozen_failure = (
        abs(energy - pure.bare_exchange_energy) <= 1e-9
        and abs(reference - pure.reference_energy) <= 1e-10
        and leakage <= JW_SECTOR_LEAKAGE_TOLERANCE
        and abs(energy - reference) > 1e-4
    )
    return {
        "schema_version": "qcol-jw-negative-runtime-check/1.0",
        "fixture_id": pure.fixture_id,
        "failure_code": pure.failure_code,
        "failure_message": pure.failure_message,
        "runtime_energy": energy,
        "frozen_bare_exchange_energy": pure.bare_exchange_energy,
        "reference_energy": reference,
        "absolute_energy_error": abs(energy - reference),
        "sector_leakage": leakage,
        "particle_number_preserved": leakage <= JW_SECTOR_LEAKAGE_TOLERANCE,
        "mapped_generator_equivalent": False,
        "matches_frozen_failure": matches_frozen_failure,
        "accepted_as_positive_fixture": False,
    }

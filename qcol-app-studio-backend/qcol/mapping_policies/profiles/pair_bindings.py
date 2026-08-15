"""Executable bindings for the migrated seniority-zero Pair Mapping policy.

The functions in this module are intentionally small wrappers around the
already accepted QCOL reduced-pairing implementation.  Public policy contracts
store only the versioned binding IDs declared in :mod:`pair_mapping`; the
callables remain runtime-only.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def _normalize_bits(bitstring: str | Sequence[int] | Sequence[bool]) -> tuple[int, ...]:
    if isinstance(bitstring, str):
        text = bitstring.strip().replace(" ", "")
        if not text or any(char not in {"0", "1"} for char in text):
            raise ValueError("Pair-occupation bitstrings must contain only 0 and 1.")
        return tuple(int(char) for char in text)
    bits = tuple(int(value) for value in bitstring)
    if not bits or any(value not in {0, 1} for value in bits):
        raise ValueError("Pair-occupation vectors must contain only 0 and 1.")
    return bits


def pair_basis_encoder(*, occupied_levels: Sequence[int], n_levels: int) -> tuple[int, ...]:
    """Encode intact-pair occupations as one qubit per declared pair level."""
    n_levels = int(n_levels)
    occupied = tuple(int(value) for value in occupied_levels)
    if n_levels <= 0:
        raise ValueError("n_levels must be positive.")
    if len(set(occupied)) != len(occupied):
        raise ValueError("occupied_levels must not contain duplicates.")
    if any(value < 0 or value >= n_levels for value in occupied):
        raise ValueError("occupied_levels contains an index outside the declared pair-level order.")
    selected = set(occupied)
    return tuple(1 if index in selected else 0 for index in range(n_levels))


def pair_basis_decoder(*, bitstring: str | Sequence[int] | Sequence[bool]) -> tuple[int, ...]:
    """Decode pair-occupation qubits into occupied pair-level indices."""
    bits = _normalize_bits(bitstring)
    return tuple(index for index, value in enumerate(bits) if value == 1)


def pair_seniority_zero_subspace(*, occupations: str | Sequence[int] | Sequence[bool], seniority: int = 0) -> bool:
    """Return whether a pair-occupation state belongs to the declared code space."""
    _normalize_bits(occupations)
    return int(seniority) == 0


def pair_number_popcount(*, bitstring: str | Sequence[int] | Sequence[bool]) -> int:
    """In Pair Mapping, raw popcount is the number of intact pairs."""
    return int(sum(_normalize_bits(bitstring)))


def particle_number_from_pair_bits(*, bitstring: str | Sequence[int] | Sequence[bool]) -> int:
    """Two physical fermions are represented by every occupied pair qubit."""
    return 2 * pair_number_popcount(bitstring=bitstring)


def seniority_zero_domain_diagnostic(*, metadata: Mapping[str, Any]) -> bool:
    """Seniority is fixed by the declared reduced-pairing physical domain."""
    return (
        int(metadata.get("seniority", -1)) == 0
        and str(metadata.get("physical_domain", "")) in {
            "reduced_pairing",
            "reduced_pairing_seniority_zero",
        }
    )


def real_parameter_vector(*, values: Sequence[float]) -> tuple[float, ...]:
    return tuple(float(value) for value in values)


def qwc_grouping(*, pauli_terms: Sequence[Any]) -> tuple[Any, ...]:
    """Public binding placeholder for the already shared QWC grouping service."""
    return tuple(pauli_terms)


def term_expectation_reconstruction(*, expectations: Sequence[float], coefficients: Sequence[float]) -> float:
    if len(expectations) != len(coefficients):
        raise ValueError("expectations and coefficients must have equal length.")
    return float(sum(float(e) * float(c) for e, c in zip(expectations, coefficients)))


def pair_verification_handler(*, result: Mapping[str, Any], reference: Mapping[str, Any]) -> Mapping[str, Any]:
    estimate = float(result.get("estimate", result.get("energy", 0.0)))
    reference_energy = float(reference.get("reference_energy", reference.get("energy", 0.0)))
    return {
        "estimate": estimate,
        "reference_energy": reference_energy,
        "absolute_error": abs(estimate - reference_energy),
        "pair_sector_declared": True,
        "seniority_zero_declared": True,
    }


def pair_operator_transform(*, context: Any, hamiltonian: Any, sector: Any) -> Any:
    """Lazy wrapper around the accepted live Pair Mapping implementation."""
    from qcol.models.reduced_pairing_common import pair_mapping_policy

    return pair_mapping_policy(context, hamiltonian, sector)


def pair_state_one_pair(*, context: Any, mapping: Any, sector: Any) -> Any:
    from qcol.models.reduced_pairing_one_pair.policies import one_pair_state_preparation_policy

    return one_pair_state_preparation_policy(context, mapping, sector)


def pair_state_multi_pair(*, context: Any, mapping: Any, sector: Any) -> Any:
    from qcol.models.reduced_pairing_multi_pair.policies import multi_pair_state_preparation_policy

    return multi_pair_state_preparation_policy(context, mapping, sector)


def pair_ansatz_one_pair(*, context: Any, mapping: Any, sector: Any, initial_state: Any, reference: Any = None) -> Any:
    from qcol.models.reduced_pairing_one_pair.policies import one_pair_chain_ansatz_policy

    return one_pair_chain_ansatz_policy(context, mapping, sector, initial_state, reference)


def pair_ansatz_multi_pair(*, context: Any, mapping: Any, sector: Any, initial_state: Any, reference: Any = None) -> Any:
    from qcol.models.reduced_pairing_multi_pair.policies import multi_pair_ansatz_policy

    return multi_pair_ansatz_policy(context, mapping, sector, initial_state, reference)


def pair_measurement_builder(*, context: Any, mapping: Any, ansatz: Any) -> Any:
    from qcol.models.reduced_pairing_common import pauli_energy_qwc_measurement_policy

    return pauli_energy_qwc_measurement_policy(context, mapping, ansatz)


def pair_reference_solver(*, context: Any, mapping: Any, sector: Any) -> Any:
    from qcol.models.reduced_pairing_common import exact_pair_sector_reference_policy

    return exact_pair_sector_reference_policy(context, mapping, sector)


def pair_resource_assessor(*, context: Any, mapping: Any = None, ansatz: Any = None, measurement_plan: Any = None) -> Any:
    from qcol.models.reduced_pairing_common import pair_resource_policy

    return pair_resource_policy(context, mapping, ansatz, measurement_plan)


__all__ = [
    "pair_basis_encoder",
    "pair_basis_decoder",
    "pair_seniority_zero_subspace",
    "pair_number_popcount",
    "particle_number_from_pair_bits",
    "seniority_zero_domain_diagnostic",
    "real_parameter_vector",
    "qwc_grouping",
    "term_expectation_reconstruction",
    "pair_verification_handler",
    "pair_operator_transform",
    "pair_state_one_pair",
    "pair_state_multi_pair",
    "pair_ansatz_one_pair",
    "pair_ansatz_multi_pair",
    "pair_measurement_builder",
    "pair_reference_solver",
    "pair_resource_assessor",
]

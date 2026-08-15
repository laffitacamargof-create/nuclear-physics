"""Dependency-light executable fixtures used to prove WP3 registry mechanics.

These callables are not migrated Pair/JW/BK production policies.  They provide
small deterministic functions so the contract-ID → binding-ID → callable chain
can be tested without changing scientific runtime behaviour.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any


def operator_mapper(operator: Any, context: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return {
        "kind": "wp3_fixture_mapped_operator",
        "source": operator,
        "context_id": None if context is None else context.get("context_id"),
    }


def occupation_encoder(
    occupations: Sequence[int],
    context: Mapping[str, Any] | None = None,
) -> tuple[int, ...]:
    return tuple(int(value) for value in occupations)


def occupation_decoder(
    bitstring: Sequence[int] | str,
    context: Mapping[str, Any] | None = None,
) -> tuple[int, ...]:
    if isinstance(bitstring, str):
        return tuple(int(char) for char in bitstring.strip())
    return tuple(int(value) for value in bitstring)


def distributed_occupation_decoder(
    encoded_bits: Sequence[int] | str,
    context: Mapping[str, Any] | None = None,
) -> tuple[int, ...]:
    # Schema fixture only: it demonstrates a mapping-specific decoder binding.
    # It does not claim to implement a production BK convention.
    return occupation_decoder(encoded_bits, context=context)


def full_fock_space(
    state: Sequence[int],
    context: Mapping[str, Any] | None = None,
) -> bool:
    return all(int(value) in (0, 1) for value in state)


def particle_popcount_diagnostic(
    bitstring: Sequence[int] | str,
    context: Mapping[str, Any] | None = None,
) -> int:
    return sum(occupation_decoder(bitstring, context=context))


def nonlocal_particle_operator(
    n_qubits: int,
    context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "kind": "wp3_fixture_nonlocal_particle_operator",
        "n_qubits": int(n_qubits),
        "context_id": None if context is None else context.get("context_id"),
    }


def standard_mapping_resources(
    mapped_operator: Any,
    context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "n_qubits": int((context or {}).get("n_qubits", 0)),
        "pauli_term_count": 0 if mapped_operator is None else 1,
        "maximum_pauli_weight": 0 if mapped_operator is None else 1,
        "fixture_only": True,
    }


def state_preparation(
    occupations: Sequence[int],
    context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "kind": "wp3_fixture_state_preparation",
        "occupations": list(occupation_encoder(occupations, context=context)),
    }


def mapped_generator_ansatz(
    generators: Iterable[Any],
    parameters: Sequence[float],
    context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "kind": "wp3_fixture_mapped_generator_ansatz",
        "generator_count": len(tuple(generators)),
        "parameters": [float(value) for value in parameters],
        "fixture_only": True,
    }


def real_parameter_vector(
    values: Sequence[float],
    context: Mapping[str, Any] | None = None,
) -> tuple[float, ...]:
    return tuple(float(value) for value in values)


def measurement_builder(
    mapped_observables: Sequence[Any],
    context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "kind": "wp3_fixture_measurement_plan",
        "observable_count": len(mapped_observables),
        "fixture_only": True,
    }


def qwc_grouping(
    pauli_terms: Sequence[Any],
    context: Mapping[str, Any] | None = None,
) -> list[list[Any]]:
    return [[term] for term in pauli_terms]


def term_expectation_reconstruction(
    expectations: Sequence[float],
    coefficients: Sequence[float],
    context: Mapping[str, Any] | None = None,
) -> float:
    if len(expectations) != len(coefficients):
        raise ValueError("expectations and coefficients must have the same length")
    return float(sum(float(e) * float(c) for e, c in zip(expectations, coefficients)))


def source_domain_exact_solver(
    matrix: Sequence[Sequence[float]],
    sector: Any = None,
) -> dict[str, Any]:
    diagonal = [float(row[index]) for index, row in enumerate(matrix)]
    return {
        "reference_value": min(diagonal) if diagonal else 0.0,
        "sector": sector,
        "fixture_only": True,
    }


def verification(
    result: float,
    reference: float,
    tolerance: float | None = None,
) -> dict[str, Any]:
    threshold = 0.0 if tolerance is None else float(tolerance)
    error = abs(float(result) - float(reference))
    return {
        "passed": error <= threshold,
        "absolute_error": error,
        "threshold": threshold,
        "fixture_only": True,
    }


def wrong_signature_fixture(unrelated: Any) -> Any:
    return unrelated


NOT_A_CALLABLE = {"fixture": "not callable"}


__all__ = [
    "operator_mapper",
    "occupation_encoder",
    "occupation_decoder",
    "distributed_occupation_decoder",
    "full_fock_space",
    "particle_popcount_diagnostic",
    "nonlocal_particle_operator",
    "standard_mapping_resources",
    "state_preparation",
    "mapped_generator_ansatz",
    "real_parameter_vector",
    "measurement_builder",
    "qwc_grouping",
    "term_expectation_reconstruction",
    "source_domain_exact_solver",
    "verification",
    "wrong_signature_fixture",
    "NOT_A_CALLABLE",
]

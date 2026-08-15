"""Runtime-only implementation bindings for WP9/WP10 mapping migrations.

Public policy contracts contain only exact binding IDs.  The callables here
wrap the already accepted QCOL/OpenFermion mapper and analysis components; no
new optimization, measurement, QASM, execution, reconstruction, or evidence
runtime is created by policy migration.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def _bits(values: Sequence[int] | Sequence[bool] | str) -> tuple[int, ...]:
    if isinstance(values, str):
        text = values.strip().replace(" ", "")
        if not text or any(ch not in "01" for ch in text):
            raise ValueError("bitstring must contain only 0 and 1")
        return tuple(int(ch) for ch in text)
    bits = tuple(int(v) for v in values)
    if not bits or any(v not in {0, 1} for v in bits):
        raise ValueError("occupation/code vectors must contain only 0 and 1")
    return bits


# ---------------------------------------------------------------------------
# Jordan--Wigner mapper-level bindings
# ---------------------------------------------------------------------------

def jw_operator_transform(*, fermion_operator: Any, n_modes: int) -> Any:
    from qcol.mappings import JWMappingPlugin

    return JWMappingPlugin().transform_hamiltonian(
        fermion_operator, n_modes=int(n_modes)
    )


def jw_basis_encoder(*, occupations: Sequence[int]) -> tuple[int, ...]:
    return _bits(occupations)


def jw_basis_decoder(*, bitstring: Sequence[int] | str) -> tuple[int, ...]:
    return _bits(bitstring)


def jw_full_fock_subspace(*, bitstring: Sequence[int] | str, n_modes: int) -> bool:
    return len(_bits(bitstring)) == int(n_modes)


def jw_particle_number_popcount(*, bitstring: Sequence[int] | str) -> int:
    return int(sum(_bits(bitstring)))


def jw_fermion_parity(*, bitstring: Sequence[int] | str) -> int:
    return int(sum(_bits(bitstring)) % 2)


def jw_resource_assessor(*, mapped_operator: Any = None, n_modes: int = 0) -> Mapping[str, Any]:
    terms = getattr(mapped_operator, "terms", {}) if mapped_operator is not None else {}
    weights = [len(term) for term in terms]
    return {
        "n_modes": int(n_modes),
        "n_qubits": int(n_modes),
        "pauli_term_count": len(terms),
        "maximum_pauli_weight": max(weights, default=0),
        "metric_scope": "operator_level",
    }


def jw_occupation_determinant_state(*, context: Any, mapping: Any, sector: Any) -> Any:
    from qcol.models.general_spin_orbital.policies import general_spin_orbital_state_policy

    return general_spin_orbital_state_policy(context, mapping, sector)


def jw_current_bare_exchange_ansatz(
    *, context: Any, mapping: Any, sector: Any, initial_state: Any
) -> Any:
    """Build the archived endpoint-only composition as a negative fixture."""
    from qcol.model_execution_types import AnsatzBuildResult
    from qcol.models.general_spin_orbital.jw_ground_state import (
        build_jw_number_preserving_ansatz,
    )

    n_layers = int(context.instance.parameters.get("ansatz_layers", 1))
    circuit, symbols, metadata = build_jw_number_preserving_ansatz(
        mapping.n_qubits, n_layers
    )
    return AnsatzBuildResult(
        variational_circuit=circuit,
        parameter_symbols=symbols,
        initial_parameters=tuple(0.0 for _ in symbols),
        family="jw_number_preserving_exchange_phase_wp0_negative_fixture",
        parameter_fixture=None,
        metadata={
            **dict(metadata),
            "mapping_id": "jordan_wigner.v1",
            "target_particle_number": int(sector.target_sector["particle_number"]),
            "initial_occupied_modes": list(initial_state.occupied_indices),
            "acceptance_status": "rejected_negative_fixture",
        },
    )


def jw_mapped_fermionic_ansatz(
    *, context: Any, mapping: Any, sector: Any, initial_state: Any
) -> Any:
    """Return the production WP11 mapped-fermionic ansatz composition."""
    from qcol.models.general_spin_orbital.policies import (
        general_spin_orbital_ansatz_policy,
    )

    return general_spin_orbital_ansatz_policy(
        context, mapping, sector, initial_state
    )


# ---------------------------------------------------------------------------
# Bravyi--Kitaev mapper-level bindings
# ---------------------------------------------------------------------------

def bk_operator_transform(*, fermion_operator: Any, n_modes: int) -> Any:
    from qcol.mappings import BKMappingPlugin

    return BKMappingPlugin().transform_hamiltonian(
        fermion_operator, n_modes=int(n_modes)
    )


def bk_basis_encoder(*, occupations: Sequence[int]) -> tuple[int, ...]:
    from qcol.mappings import BKMappingPlugin

    return BKMappingPlugin().encode_occupation_state(_bits(occupations))


def bk_basis_decoder(*, bitstring: Sequence[int] | str) -> tuple[int, ...]:
    from qcol.mappings import BKMappingPlugin

    return BKMappingPlugin().decode_basis_bitstring(_bits(bitstring))


def bk_full_fock_subspace(*, bitstring: Sequence[int] | str, n_modes: int) -> bool:
    return len(_bits(bitstring)) == int(n_modes)


def bk_particle_number_from_code(*, bitstring: Sequence[int] | str) -> int:
    """Interpret particle number through the mapping-specific decoder.

    Raw BK qubit popcount is deliberately never used as particle number.
    """
    return int(sum(bk_basis_decoder(bitstring=bitstring)))


def bk_fermion_parity_from_code(*, bitstring: Sequence[int] | str) -> int:
    return int(bk_particle_number_from_code(bitstring=bitstring) % 2)


def bk_resource_assessor(*, mapped_operator: Any = None, n_modes: int = 0) -> Mapping[str, Any]:
    terms = getattr(mapped_operator, "terms", {}) if mapped_operator is not None else {}
    weights = [len(term) for term in terms]
    return {
        "n_modes": int(n_modes),
        "n_qubits": int(n_modes),
        "pauli_term_count": len(terms),
        "maximum_pauli_weight": max(weights, default=0),
        "metric_scope": "operator_level",
        "raw_popcount_is_particle_number": False,
    }


# ---------------------------------------------------------------------------
# Shared analysis/reference/measurement bindings
# ---------------------------------------------------------------------------

def identity_parameter_vector(*, values: Sequence[float]) -> tuple[float, ...]:
    return tuple(float(value) for value in values)




def analysis_no_state(*, mapped_operators: Sequence[Any]) -> Mapping[str, Any]:
    """Return an explicit no-state declaration for deterministic mapping analysis."""
    return {"analysis_only": True, "state_preparation_applicable": False, "mapped_operator_count": len(tuple(mapped_operators))}


def analysis_no_ansatz(*, mapped_operators: Sequence[Any]) -> Mapping[str, Any]:
    """Return an explicit no-ansatz declaration for deterministic mapping analysis."""
    return {"analysis_only": True, "ansatz_applicable": False, "mapped_operator_count": len(tuple(mapped_operators))}

def mapping_analysis_measurement_builder(*, mapped_operators: Sequence[Any]) -> tuple[Any, ...]:
    """Declare operator-level analysis; no shots or circuit are constructed."""
    return tuple(mapped_operators)


def mapping_analysis_grouping(*, mapped_operators: Sequence[Any]) -> tuple[Any, ...]:
    return tuple(mapped_operators)


def mapping_comparison_reconstruction(*, reports: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
    return {"entries": [dict(item) for item in reports], "analysis_only": True}


def fock_space_reference_solver(*, fermion_operator: Any, n_modes: int, particle_number: int) -> Mapping[str, Any]:
    """Independent source-domain reference used by migration acceptance."""
    from openfermion import get_sparse_operator, number_operator
    import numpy as np

    h = np.asarray(
        get_sparse_operator(fermion_operator, n_qubits=int(n_modes)).toarray(),
        dtype=np.complex128,
    )
    n_op = number_operator(int(n_modes))
    n_mat = np.asarray(
        get_sparse_operator(n_op, n_qubits=int(n_modes)).toarray(),
        dtype=np.complex128,
    )
    n_values, n_vectors = np.linalg.eigh((n_mat + n_mat.conj().T) / 2)
    selector = np.isclose(n_values, float(particle_number), atol=1e-8, rtol=0.0)
    basis = n_vectors[:, selector]
    sector = basis.conj().T @ h @ basis
    return {
        "full_spectrum": [float(v) for v in np.linalg.eigvalsh((h + h.conj().T) / 2)],
        "sector_spectrum": [float(v) for v in np.linalg.eigvalsh((sector + sector.conj().T) / 2)],
        "particle_number": int(particle_number),
        "constructed_from_tested_mapping": False,
    }


def mapping_equivalence_verification(*, report: Mapping[str, Any], reference: Mapping[str, Any]) -> Mapping[str, Any]:
    return {
        "transform_verified": bool(report.get("transform_verified", False)),
        "reference_independent": not bool(reference.get("constructed_from_tested_mapping", True)),
        "analysis_only": True,
    }


def pauli_energy_measurement_builder(*, context: Any, mapping: Any, ansatz: Any) -> Any:
    from qcol.models.general_spin_orbital.policies import general_spin_orbital_measurement_policy

    return general_spin_orbital_measurement_policy(context, mapping, ansatz)


def fixed_particle_reference_solver(*, context: Any, mapping: Any, sector: Any) -> Any:
    from qcol.models.general_spin_orbital.policies import general_spin_orbital_reference_policy

    return general_spin_orbital_reference_policy(context, mapping, sector)


def ground_state_verification_handler(*, result: Mapping[str, Any], reference: Mapping[str, Any]) -> Mapping[str, Any]:
    estimate = float(result.get("estimate", result.get("energy", 0.0)))
    exact = float(reference.get("reference_energy", reference.get("energy", 0.0)))
    return {
        "estimate": estimate,
        "reference_energy": exact,
        "absolute_error": abs(estimate - exact),
        "reference_independent": not bool(reference.get("constructed_from_tested_mapping", False)),
    }


__all__ = [
    "jw_operator_transform",
    "jw_basis_encoder",
    "jw_basis_decoder",
    "jw_full_fock_subspace",
    "jw_particle_number_popcount",
    "jw_fermion_parity",
    "jw_resource_assessor",
    "jw_occupation_determinant_state",
    "jw_current_bare_exchange_ansatz",
    "jw_mapped_fermionic_ansatz",
    "bk_operator_transform",
    "bk_basis_encoder",
    "bk_basis_decoder",
    "bk_full_fock_subspace",
    "bk_particle_number_from_code",
    "bk_fermion_parity_from_code",
    "bk_resource_assessor",
    "identity_parameter_vector",
    "analysis_no_state",
    "analysis_no_ansatz",
    "mapping_analysis_measurement_builder",
    "mapping_analysis_grouping",
    "mapping_comparison_reconstruction",
    "fock_space_reference_solver",
    "mapping_equivalence_verification",
    "pauli_energy_measurement_builder",
    "fixed_particle_reference_solver",
    "ground_state_verification_handler",
]

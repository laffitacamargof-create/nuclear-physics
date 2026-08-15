"""Mapping analysis and equivalence verification for the same FermionOperator."""
from __future__ import annotations

import time
from typing import Iterable, Sequence, Tuple

import numpy as np

from .base import MappedProblemArtifact, MappingAnalysisEntry, MappingComparisonReport
from .metrics import mapping_resource_report
from .registry import get_mapping_plugin


def _dense(operator, n_qubits: int) -> np.ndarray:
    from openfermion import get_sparse_operator
    matrix = get_sparse_operator(operator, n_qubits=n_qubits).toarray()
    return np.asarray(matrix, dtype=np.complex128)


def _spectrum(matrix: np.ndarray) -> np.ndarray:
    return np.linalg.eigvalsh((matrix + matrix.conj().T) / 2)


def _sector_spectrum(hamiltonian: np.ndarray, number_operator: np.ndarray, target: int, tolerance: float = 1e-8) -> np.ndarray:
    number_values, vectors = np.linalg.eigh((number_operator + number_operator.conj().T) / 2)
    selector = np.isclose(number_values, float(target), atol=tolerance, rtol=0.0)
    if not np.any(selector):
        raise ValueError(f"No states found in particle-number sector N={target}.")
    basis = vectors[:, selector]
    projected = basis.conj().T @ hamiltonian @ basis
    return _spectrum(projected)


def _max_error(left: Sequence[float], right: Sequence[float]) -> float:
    a = np.asarray(left, dtype=float)
    b = np.asarray(right, dtype=float)
    if a.shape != b.shape:
        return float("inf")
    return float(np.max(np.abs(a - b))) if a.size else 0.0


def analyze_mappings(
    *,
    model_id: str,
    spin_instance,
    fermion_operator,
    particle_number_operator,
    mapping_ids: Iterable[str],
    coefficient_threshold: float = 1e-12,
    equivalence_tolerance: float = 1e-8,
) -> MappingComparisonReport:
    n_modes = int(spin_instance.n_modes)
    target = int(spin_instance.total_target_particles)
    fermion_matrix = _dense(fermion_operator, n_modes)
    number_matrix = _dense(particle_number_operator, n_modes)
    reference_full = _spectrum(fermion_matrix)
    reference_sector = _sector_spectrum(fermion_matrix, number_matrix, target)
    reference_number_spectrum = _spectrum(number_matrix)

    entries = []
    for mapping_id in mapping_ids:
        plugin = get_mapping_plugin(mapping_id)
        compatibility = plugin.check_compatibility(spin_instance, task_id="mapping_analysis")
        if not compatibility.compatible:
            raise ValueError(f"Mapping {mapping_id} is not compatible: {compatibility.reasons}")
        started = time.perf_counter()
        mapped_h = plugin.transform_hamiltonian(fermion_operator, n_modes=n_modes)
        elapsed = time.perf_counter() - started
        mapped_n = plugin.transform_observable(particle_number_operator, n_modes=n_modes)
        resource = mapping_resource_report(
            mapping_id,
            mapped_h,
            n_modes=n_modes,
            n_qubits=n_modes,
            transform_seconds=elapsed,
            coefficient_threshold=coefficient_threshold,
        )
        h_matrix = _dense(mapped_h, n_modes)
        n_matrix = _dense(mapped_n, n_modes)
        mapped_full = _spectrum(h_matrix)
        mapped_sector = _sector_spectrum(h_matrix, n_matrix, target)
        number_spectrum = _spectrum(n_matrix)
        full_error = _max_error(reference_full, mapped_full)
        sector_error = _max_error(reference_sector, mapped_sector)
        number_error = _max_error(reference_number_spectrum, number_spectrum)
        hermitian = bool(np.allclose(h_matrix, h_matrix.conj().T, atol=equivalence_tolerance, rtol=0.0))
        commutator_norm = float(np.linalg.norm(h_matrix @ n_matrix - n_matrix @ h_matrix))
        verified = bool(
            hermitian
            and full_error <= equivalence_tolerance
            and sector_error <= equivalence_tolerance
            and number_error <= equivalence_tolerance
            and commutator_norm <= 10 * equivalence_tolerance
        )
        capability = plugin.capability_report(spin_instance)
        artifact = MappedProblemArtifact(
            mapping_id=plugin.mapping_id,
            mapping_version=plugin.mapping_version,
            qubit_hamiltonian=mapped_h,
            mapped_particle_number_operator=mapped_n,
            n_qubits=n_modes,
            mode_to_qubit_order=plugin.occupation_encoding_metadata(n_modes),
            target_sector={"particle_number": target, "particle_numbers": dict(spin_instance.target_particle_numbers)},
            preserved_symmetries=tuple(spin_instance.declared_symmetries),
            occupation_encoding=plugin.occupation_encoding_metadata(n_modes),
            resource_report=resource,
            compatibility_report=compatibility,
            capability_report=capability,
            mapping_provenance={
                "library": "OpenFermion",
                "mapping_function": plugin.mapping_id,
                "mode_ordering": [item.to_dict() for item in spin_instance.mode_labels],
                "coefficient_threshold": coefficient_threshold,
            },
        )
        entries.append(MappingAnalysisEntry(
            mapping_id=mapping_id,
            mapped_artifact=artifact,
            full_spectrum_max_abs_error=full_error,
            target_sector_spectrum_max_abs_error=sector_error,
            particle_number_spectrum_max_abs_error=number_error,
            hamiltonian_hermitian=hermitian,
            particle_number_commutator_norm=commutator_norm,
            transform_verified=verified,
        ))

    # The foundation does not recommend a mapping for VQE.  This analysis-only
    # ranking selects the lowest coefficient-weighted mean Pauli weight, with
    # term count as a deterministic tie-breaker.
    verified_entries = [item for item in entries if item.transform_verified]
    recommended = None
    basis = "No verified mapping result was available."
    if verified_entries:
        selected = min(
            verified_entries,
            key=lambda item: (
                item.mapped_artifact.resource_report.coefficient_weighted_mean_pauli_weight,
                item.mapped_artifact.resource_report.pauli_term_count,
                item.mapping_id,
            ),
        )
        recommended = selected.mapping_id
        basis = (
            "Analysis-only ranking by coefficient-weighted mean Pauli weight, "
            "then Pauli-term count. This is not a ground-state execution recommendation."
        )
    return MappingComparisonReport(
        model_id=model_id,
        task_id="mapping_analysis",
        n_modes=n_modes,
        target_particle_number=target,
        coefficient_threshold=float(coefficient_threshold),
        reference_full_spectrum=tuple(float(v) for v in reference_full),
        reference_target_sector_spectrum=tuple(float(v) for v in reference_sector),
        entries=tuple(entries),
        recommended_for_analysis=recommended,
        recommendation_basis=basis,
    )

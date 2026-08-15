"""Shared reduced-pairing policies.

The multi-pair state preparation and occupied-to-virtual Givens network are
adapted from Bathri's earlier QCOL implementation.  They are extracted here as
model-specific policies and no longer carry the legacy UI/orchestrator around
them.
"""
from __future__ import annotations

from itertools import combinations
from math import comb
from typing import Any, Mapping, Sequence, Tuple

import cirq
import numpy as np
import sympy
from openfermion import bravyi_kitaev, get_sparse_operator, jordan_wigner

from ..measurement import build_qwc_measurement_plan
from ..model_execution_types import (
    AnsatzBuildResult,
    HamiltonianBuildResult,
    MappingResult,
    ModelBuildContext,
    ResourceAssessment,
    SectorValidationResult,
    StatePreparationResult,
)
from .reduced_pairing_multi_pair.reference import build_reduced_pairing_sector_matrix

from ..modeling import (
    append_number_conserving_givens,
    basis_index,
    build_pair_qubit_hamiltonian,
    build_pairing_fermion_hamiltonian_explicit,
    exact_reference_from_matrix,
    operator_matrix,
)


def reduced_pairing_hamiltonian_policy(
    context: ModelBuildContext,
) -> HamiltonianBuildResult:
    p = dict(context.instance.parameters)
    epsilon = np.asarray(p["epsilon"], dtype=float)
    g = float(p["g"])
    n_levels = int(p["n_levels"])
    if epsilon.shape != (n_levels,):
        raise ValueError(f"epsilon must contain exactly {n_levels} values.")
    if not np.all(np.isfinite(epsilon)) or not np.isfinite(g) or g <= 0:
        raise ValueError("Reduced-pairing parameters require finite epsilon and G > 0.")
    fermion_operator = build_pairing_fermion_hamiltonian_explicit(epsilon, g)
    return HamiltonianBuildResult(
        domain_hamiltonian=fermion_operator,
        representation="fermion_operator_second_quantized_reduced_pairing",
        parameters={
            "n_levels": n_levels,
            "epsilon": epsilon.tolist(),
            "g": g,
            "n_pairs": int(p["n_pairs"]),
            "n_particles": int(p["n_particles"]),
            "seniority": int(p["seniority"]),
        },
        units=dict(context.instance.units),
        metadata={
            "model_family": "reduced_pairing",
            "spin_orbitals": 2 * n_levels,
        },
        provenance={
            "builder": "qcol.models.reduced_pairing_common.reduced_pairing_hamiltonian_policy",
        },
    )


def reduced_pairing_sector_policy(
    context: ModelBuildContext,
    hamiltonian: HamiltonianBuildResult,
) -> SectorValidationResult:
    p = dict(context.instance.parameters)
    n_levels = int(p["n_levels"])
    n_pairs = int(p["n_pairs"])
    n_particles = int(p["n_particles"])
    seniority = int(p["seniority"])
    checks = {
        "n_pairs_positive": n_pairs > 0,
        "n_pairs_below_levels": n_pairs < n_levels,
        "particle_pair_relation": n_particles == 2 * n_pairs,
        "seniority_zero": seniority == 0,
        "target_sector_matches_parameters": dict(context.instance.target_sector)
        == {
            "particle_number": n_particles,
            "pair_number": n_pairs,
            "seniority": seniority,
        },
    }
    if not all(checks.values()):
        failed = [key for key, value in checks.items() if not value]
        raise ValueError("Invalid reduced-pairing sector: " + ", ".join(failed))
    return SectorValidationResult(
        target_sector={
            "particle_number": n_particles,
            "pair_number": n_pairs,
            "seniority": seniority,
        },
        conserved_quantities=("particle_number", "pair_number", "seniority"),
        validation_checks=checks,
        metadata={
            "pair_sector_dimension": comb(n_levels, n_pairs),
            "computational_sector": f"Hamming weight {n_pairs}",
        },
    )


def pair_sector_indices(n_levels: int, n_pairs: int) -> Tuple[int, ...]:
    return tuple(
        basis_index(occupied, n_levels)
        for occupied in combinations(range(n_levels), n_pairs)
    )


def paired_spin_orbital_sector_indices(
    n_levels: int,
    n_pairs: int,
) -> Tuple[int, ...]:
    indices = []
    n_spin_orbitals = 2 * n_levels
    for occupied_levels in combinations(range(n_levels), n_pairs):
        occupied_spin_orbitals = []
        for level in occupied_levels:
            occupied_spin_orbitals.extend([2 * level, 2 * level + 1])
        indices.append(basis_index(occupied_spin_orbitals, n_spin_orbitals))
    return tuple(indices)


def pair_mapping_policy(
    context: ModelBuildContext,
    hamiltonian: HamiltonianBuildResult,
    sector: SectorValidationResult,
) -> MappingResult:
    p = dict(context.instance.parameters)
    epsilon = np.asarray(p["epsilon"], dtype=float)
    g = float(p["g"])
    n_levels = int(p["n_levels"])
    n_pairs = int(p["n_pairs"])

    pair_operator = build_pair_qubit_hamiltonian(epsilon, g)
    pair_operator.compress()
    pair_matrix = operator_matrix(pair_operator, n_levels)
    pair_indices = pair_sector_indices(n_levels, n_pairs)
    pair_sector = pair_matrix[np.ix_(pair_indices, pair_indices)]

    jw_operator = jordan_wigner(hamiltonian.domain_hamiltonian)
    jw_operator.compress()
    n_spin_orbitals = 2 * n_levels
    jw_matrix = get_sparse_operator(jw_operator, n_qubits=n_spin_orbitals).tocsc()
    jw_indices = paired_spin_orbital_sector_indices(n_levels, n_pairs)
    jw_sector = jw_matrix[jw_indices, :][:, jw_indices].toarray()

    validation = {
        "pair_operator_hermitian": bool(
            np.allclose(pair_matrix, pair_matrix.conj().T, atol=1e-10)
        ),
        "pair_mapping_matches_jw_paired_sector": bool(
            np.allclose(pair_sector, jw_sector, atol=1e-9)
        ),
        "sector_dimension_matches_combinatorics": len(pair_indices)
        == comb(n_levels, n_pairs),
    }
    if not all(validation.values()):
        failed = [key for key, value in validation.items() if not value]
        raise AssertionError("Pair mapping validation failed: " + ", ".join(failed))

    return MappingResult(
        qubit_hamiltonian=pair_operator,
        n_qubits=n_levels,
        mapping_name="pair_mapping",
        encoding="one_qubit_per_level_pair_occupation_seniority_zero",
        mapping_metadata={
            "policy_id": context.contract.mapping_policy_id,
            "source_representation": hamiltonian.representation,
            "n_spin_orbitals_before_reduction": n_spin_orbitals,
            "n_pair_qubits": n_levels,
            "target_hamming_weight": n_pairs,
            "sector_dimension": len(pair_indices),
            "formula": {
                "pair_occupation": "n_p -> (I-Z_p)/2",
                "pair_hopping": "P_p^dag P_q + h.c. -> (X_p X_q + Y_p Y_q)/2",
            },
        },
        orbital_to_qubit_order={
            str(level): {
                "qubit": level,
                "meaning": f"pair occupation of level {level}",
                "spin_orbitals": [2 * level, 2 * level + 1],
            }
            for level in range(n_levels)
        },
        preserved_symmetries=("fixed pair number", "seniority zero"),
        crosscheck_payloads={
            "fermion_operator": hamiltonian.domain_hamiltonian,
            "jordan_wigner": jw_operator,
            "pair_sector_indices": pair_indices,
            "jw_paired_sector_indices": jw_indices,
        },
        validation_checks=validation,
    )


def jordan_wigner_mapping_policy(
    context: ModelBuildContext,
    hamiltonian: HamiltonianBuildResult,
    sector: SectorValidationResult,
) -> MappingResult:
    """General JW mapping binding, registered for future plugins.

    Current reduced-pairing contracts select pair mapping; this implementation
    exists so the resolver can bind future general-fermionic contracts without
    changing the shared runtime.
    """
    p = dict(context.instance.parameters)
    n_levels = int(p["n_levels"])
    operator = jordan_wigner(hamiltonian.domain_hamiltonian)
    operator.compress()
    n_qubits = 2 * n_levels
    matrix = get_sparse_operator(operator, n_qubits=n_qubits)
    return MappingResult(
        qubit_hamiltonian=operator,
        n_qubits=n_qubits,
        mapping_name="jordan_wigner",
        encoding="spin_orbital_occupation",
        mapping_metadata={
            "policy_id": "jordan_wigner.v1",
            "n_spin_orbitals": n_qubits,
            "pauli_terms": len(operator.terms),
        },
        orbital_to_qubit_order={
            str(index): {"qubit": index, "meaning": f"spin-orbital occupation {index}"}
            for index in range(n_qubits)
        },
        preserved_symmetries=("fermion parity",),
        validation_checks={
            "operator_hermitian": bool(
                np.allclose(matrix.toarray(), matrix.toarray().conj().T, atol=1e-10)
            )
        },
    )



def bravyi_kitaev_mapping_policy(
    context: ModelBuildContext,
    hamiltonian: HamiltonianBuildResult,
    sector: SectorValidationResult,
) -> MappingResult:
    p = dict(context.instance.parameters)
    n_levels = int(p["n_levels"])
    n_qubits = 2 * n_levels
    operator = bravyi_kitaev(hamiltonian.domain_hamiltonian, n_qubits=n_qubits)
    operator.compress()
    matrix = get_sparse_operator(operator, n_qubits=n_qubits)
    return MappingResult(
        qubit_hamiltonian=operator,
        n_qubits=n_qubits,
        mapping_name="bravyi_kitaev",
        encoding="bravyi_kitaev_spin_orbital_encoding",
        mapping_metadata={
            "policy_id": "bravyi_kitaev.v1",
            "n_spin_orbitals": n_qubits,
            "pauli_terms": len(operator.terms),
            "sector_note": (
                "Computational-basis popcount is not particle number under BK; "
                "state preparation and sector diagnostics must be BK-aware."
            ),
        },
        orbital_to_qubit_order={
            str(index): {
                "qubit": index,
                "meaning": "BK parity/update-set encoded qubit",
                "source_spin_orbital": index,
            }
            for index in range(n_qubits)
        },
        preserved_symmetries=("fermion parity",),
        validation_checks={
            "operator_hermitian": bool(
                np.allclose(matrix.toarray(), matrix.toarray().conj().T, atol=1e-10)
            )
        },
    )

def lowest_level_pair_state_policy(
    context: ModelBuildContext,
    mapping: MappingResult,
    sector: SectorValidationResult,
) -> StatePreparationResult:
    n_pairs = int(context.instance.parameters["n_pairs"])
    qubits = tuple(cirq.LineQubit.range(mapping.n_qubits))
    circuit = cirq.Circuit(cirq.X(qubits[index]) for index in range(n_pairs))
    return StatePreparationResult(
        circuit=circuit,
        label=f"lowest_{n_pairs}_levels_pair_occupied",
        occupied_indices=tuple(range(n_pairs)),
        metadata={
            "basis_bitstring": "1" * n_pairs + "0" * (mapping.n_qubits - n_pairs),
            "target_hamming_weight": n_pairs,
            "source": "Bathri multi-pair state preparation, extracted as a policy",
        },
    )


def bathri_multi_pair_ansatz_policy(
    context: ModelBuildContext,
    mapping: MappingResult,
    sector: SectorValidationResult,
    initial_state: StatePreparationResult,
    reference: Mapping[str, Any] | None = None,
) -> AnsatzBuildResult:
    """Bathri's occupied-to-virtual, pair-number-conserving Givens network."""
    n_pairs = int(context.instance.parameters["n_pairs"])
    n_levels = int(context.instance.parameters["n_levels"])
    parameter_count = n_pairs * (n_levels - n_pairs)
    symbols = tuple(sympy.symbols(f"theta_0:{parameter_count}"))
    qubits = tuple(cirq.LineQubit.range(n_levels))
    circuit = cirq.Circuit()
    cursor = 0
    for occupied in range(n_pairs):
        for virtual in range(n_pairs, n_levels):
            append_number_conserving_givens(
                circuit,
                qubits[occupied],
                qubits[virtual],
                symbols[cursor],
            )
            cursor += 1
    return AnsatzBuildResult(
        variational_circuit=circuit,
        parameter_symbols=symbols,
        initial_parameters=tuple(0.0 for _ in symbols),
        family="bathri_multi_pair_occupied_to_virtual_givens",
        parameter_fixture=None,
        metadata={
            "source": "Bathri qcol_platform ansatz.py::build_pair_mapped_ansatz",
            "parameter_formula": "n_pairs * (n_levels - n_pairs)",
            "conserves_pair_number_by_construction": True,
            "acceptance_note": (
                "Execution-ready experimental ansatz; promotion to acceptance-verified "
                "requires the plugin acceptance matrix."
            ),
        },
    )


def exact_pair_sector_reference_policy(
    context: ModelBuildContext,
    mapping: MappingResult,
    sector: SectorValidationResult,
) -> Mapping[str, Any]:
    n_levels = int(context.instance.parameters["n_levels"])
    n_pairs = int(context.instance.parameters["n_pairs"])
    epsilon = context.instance.parameters["epsilon"]
    g = float(context.instance.parameters["g"])

    # Independent model-space reference: do not derive the reference from the
    # same qubit operator being verified.
    sector_matrix, occupied_basis = build_reduced_pairing_sector_matrix(
        epsilon, g, n_pairs
    )
    labels = [
        "pairs_in_levels_" + "_".join(map(str, occupied))
        for occupied in occupied_basis
    ]
    reference = exact_reference_from_matrix(
        sector_matrix,
        reference_scope=f"{n_pairs}-pair seniority-zero sector",
        acceptance_abs_floor=float(
            context.request_metadata.get("acceptance_abs_floor", 0.05)
        ),
        target_state_labels=labels,
    )
    reference.update({
        "sector_dimension": len(occupied_basis),
        "target_popcount": n_pairs,
        "kind": "independent_direct_fixed_pair_sector",
        "reference_provenance": (
            "Direct reduced-pairing matrix elements in the seniority-zero "
            "pair-occupation basis; independent of the qubit mapping."
        ),
        "validity": context.contract.reference_validity.to_dict(),
    })
    return reference


def pair_resource_policy(
    context: ModelBuildContext,
    mapping: MappingResult | None = None,
    ansatz: AnsatzBuildResult | None = None,
    measurement_plan: Mapping[str, Any] | None = None,
) -> ResourceAssessment | Mapping[str, Any]:
    n_levels = int(context.instance.parameters["n_levels"])
    n_pairs = int(context.instance.parameters["n_pairs"])
    parameter_count = n_pairs * (n_levels - n_pairs)
    sector_dimension = comb(n_levels, n_pairs)
    envelope = context.contract.resource_validity
    within = (
        (envelope.simulator_max_qubits is None or n_levels <= envelope.simulator_max_qubits)
        and (
            envelope.maximum_parameter_count is None
            or parameter_count <= envelope.maximum_parameter_count
        )
    )
    if mapping is None:
        return {
            "estimated_n_qubits": n_levels,
            "estimated_parameter_count": parameter_count,
            "estimated_sector_dimension": sector_dimension,
            "within_declared_envelope": within,
        }
    groups = 0 if measurement_plan is None else len(measurement_plan.get("groups", []))
    return ResourceAssessment(
        status="within_envelope" if within else "outside_envelope",
        n_qubits=mapping.n_qubits,
        parameter_count=0 if ansatz is None else len(ansatz.parameter_symbols),
        pauli_term_count=len(mapping.qubit_hamiltonian.terms),
        measurement_group_count=groups,
        estimated_sector_dimension=sector_dimension,
        within_declared_envelope=within,
        notes=tuple(envelope.notes),
    )


def pauli_energy_qwc_measurement_policy(
    context: ModelBuildContext,
    mapping: MappingResult,
    ansatz: AnsatzBuildResult,
) -> Mapping[str, Any]:
    return build_qwc_measurement_plan(mapping.qubit_hamiltonian)


def external_variational_energy_runtime_policy(
    context: ModelBuildContext,
) -> Mapping[str, Any]:
    return {
        "runtime_policy_id": "external_variational_energy.v1",
        "task_id": context.instance.task_id,
        "shared_runtime": "qcol.orchestrator + qcol.optimizer",
    }

"""Callable policies for the hard-core oscillator model contract."""
from __future__ import annotations

from itertools import combinations
from typing import Any, Mapping

import numpy as np

from ...model_execution_types import HamiltonianBuildResult, ModelBuildContext
from ...modeling import basis_index, build_hard_core_oscillator_hamiltonian, exact_reference_from_matrix, operator_matrix
from ..direct_qubit_common import (
    bounded_direct_resource_policy,
    direct_mapping_policy,
    external_variational_energy_runtime_policy,
    lowest_mode_state_policy,
    one_excitation_chain_ansatz_policy,
    one_excitation_sector_policy,
    qwc_measurement_policy,
)


def oscillator_hamiltonian_policy(context: ModelBuildContext) -> HamiltonianBuildResult:
    p = dict(context.instance.parameters)
    n_modes = int(p["n_modes"])
    operator, frequencies, shifts, couplings = build_hard_core_oscillator_hamiltonian(
        p.get("omega", 1.0), p.get("coupling", 0.2), p.get("kappa", 0.0), n_modes
    )
    return HamiltonianBuildResult(
        domain_hamiltonian=operator,
        representation="qubit_operator_hard_core_modes",
        parameters={
            "n_modes": n_modes,
            "omega": frequencies.tolist(),
            "coupling_matrix": couplings.tolist(),
            "kappa": shifts.tolist(),
            "n_quanta": 1,
        },
        units=dict(context.instance.units),
        metadata={
            "n_qubits": n_modes,
            "mapping_name": "direct_hard_core_mode_encoding",
            "encoding": "one_qubit_per_mode_hard_core_occupation_n_in_0_1",
            "qubit_meanings": {str(i): f"occupation of oscillator mode {i}" for i in range(n_modes)},
        },
        provenance={"builder": "oscillator_hard_core.oscillator_hamiltonian_policy"},
    )


def oscillator_reference_policy(context, mapping, sector):
    n_modes = mapping.n_qubits
    matrix = operator_matrix(mapping.qubit_hamiltonian, n_modes)
    indices = [basis_index([mode], n_modes) for mode in range(n_modes)]
    sector_matrix = matrix[np.ix_(indices, indices)]
    result = exact_reference_from_matrix(
        sector_matrix,
        reference_scope="fixed one-quantum hard-core oscillator sector",
        acceptance_abs_floor=float(context.request_metadata.get("acceptance_abs_floor", 0.05)),
        target_state_labels=[f"quantum_in_mode_{mode}" for mode in range(n_modes)],
    )
    result["validity"] = context.contract.reference_validity.to_dict()
    return result


def oscillator_interpretation_policy(context, mapping, sector, reference, resource):
    return {
        "scientific_quantity": "lowest energy in the declared one-quantum hard-core oscillator sector",
        "supported_statement": (
            "The sampled OpenQASM 2 workflow reconstructs the energy of the declared "
            "coupled hard-core oscillator-mode model in its one-quantum sector."
        ),
        "limitations": list(context.contract.limitations),
        "model_owner": context.contract.scientific_owner,
        "scientific_review_status": context.contract.scientific_review_status,
        "model_contract": context.contract.to_dict(),
        "resource_assessment": resource.to_dict(),
    }

oscillator_sector_policy = one_excitation_sector_policy
oscillator_mapping_policy = direct_mapping_policy
oscillator_state_preparation_policy = lowest_mode_state_policy
oscillator_ansatz_policy = one_excitation_chain_ansatz_policy
oscillator_measurement_policy = qwc_measurement_policy
oscillator_resource_policy = bounded_direct_resource_policy
oscillator_runtime_policy = external_variational_energy_runtime_policy

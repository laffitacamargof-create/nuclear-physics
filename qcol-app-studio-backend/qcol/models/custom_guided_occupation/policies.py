"""Policies for the guided no-code custom occupation/coupling route."""
from __future__ import annotations

from typing import Mapping
import numpy as np

from ...model_execution_types import HamiltonianBuildResult, ModelBuildContext
from ...modeling import basis_index, build_guided_occupation_hamiltonian, exact_reference_from_matrix, operator_matrix
from ..direct_qubit_common import (
    bounded_direct_resource_policy,
    direct_mapping_policy,
    external_variational_energy_runtime_policy,
    lowest_mode_state_policy,
    one_excitation_chain_ansatz_policy,
    one_excitation_sector_policy,
    qwc_measurement_policy,
)


def guided_hamiltonian_policy(context: ModelBuildContext) -> HamiltonianBuildResult:
    p = dict(context.instance.parameters)
    n_modes = int(p["n_modes"])
    operator, onsite, couplings = build_guided_occupation_hamiltonian(
        p["onsite_energies"], p.get("coupling_matrix", 0.2),
        energy_offset=float(p.get("energy_offset", 0.0)),
    )
    return HamiltonianBuildResult(
        domain_hamiltonian=operator,
        representation="qubit_operator_guided_occupation_coupling",
        parameters={
            "model_name": str(p.get("model_name", "custom occupation-coupling model")),
            "n_modes": n_modes,
            "onsite_energies": onsite.tolist(),
            "coupling_matrix": couplings.tolist(),
            "energy_offset": float(p.get("energy_offset", 0.0)),
            "n_excitations": 1,
        },
        units=dict(context.instance.units),
        metadata={
            "n_qubits": n_modes,
            "mapping_name": "direct_guided_occupation_encoding",
            "encoding": "one_qubit_per_mode_hard_core_occupation",
            "qubit_meanings": {str(i): f"occupation of declared mode {i}" for i in range(n_modes)},
        },
        provenance={"builder":"custom_guided_occupation.guided_hamiltonian_policy"},
    )


def guided_reference_policy(context, mapping, sector):
    n_modes = mapping.n_qubits
    matrix = operator_matrix(mapping.qubit_hamiltonian, n_modes)
    indices = [basis_index([mode], n_modes) for mode in range(n_modes)]
    sector_matrix = matrix[np.ix_(indices, indices)]
    result = exact_reference_from_matrix(
        sector_matrix,
        reference_scope="declared one-excitation guided custom sector",
        acceptance_abs_floor=float(context.request_metadata.get("acceptance_abs_floor",0.05)),
        target_state_labels=[f"excitation_in_mode_{mode}" for mode in range(n_modes)],
    )
    result["validity"] = context.contract.reference_validity.to_dict()
    return result


def guided_interpretation_policy(context, mapping, sector, reference, resource):
    return {
        "scientific_quantity":"lowest energy in the declared one-excitation custom model",
        "supported_statement":(
            "The sampled OpenQASM 2 workflow reconstructs the energy of the user-declared "
            "occupation/coupling Hamiltonian in its one-excitation sector."
        ),
        "limitations":list(context.contract.limitations),
        "model_contract":context.contract.to_dict(),
        "resource_assessment":resource.to_dict(),
    }

guided_sector_policy = one_excitation_sector_policy
guided_mapping_policy = direct_mapping_policy
guided_state_preparation_policy = lowest_mode_state_policy
guided_ansatz_policy = one_excitation_chain_ansatz_policy
guided_measurement_policy = qwc_measurement_policy
guided_resource_policy = bounded_direct_resource_policy
guided_runtime_policy = external_variational_energy_runtime_policy

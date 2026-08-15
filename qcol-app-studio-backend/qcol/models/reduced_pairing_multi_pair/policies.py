"""Callable policy bindings for Bathri's independent multi-pair plugin."""
from __future__ import annotations

from typing import Any, Mapping

from ...model_execution_types import ModelBuildContext
from ..reduced_pairing_common import (
    bathri_multi_pair_ansatz_policy,
    exact_pair_sector_reference_policy,
    external_variational_energy_runtime_policy,
    lowest_level_pair_state_policy,
    pair_mapping_policy,
    pair_resource_policy,
    pauli_energy_qwc_measurement_policy,
    reduced_pairing_hamiltonian_policy,
    reduced_pairing_sector_policy,
)


def multi_pair_interpretation_policy(
    context: ModelBuildContext,
    mapping,
    sector,
    reference,
    resource,
) -> Mapping[str, Any]:
    n_pairs = int(context.instance.parameters["n_pairs"])
    return {
        "scientific_quantity": (
            f"lowest energy in the declared {n_pairs}-pair seniority-zero sector"
        ),
        "supported_statement": (
            "The sampled OpenQASM 2 workflow reconstructs the energy of the "
            "declared reduced pairing Hamiltonian in its fixed multi-pair "
            "seniority-zero sector."
        ),
        "limitations": list(context.contract.limitations),
        "model_contract": context.contract.to_dict(),
        "supported_task": context.instance.task_id,
        "resource_assessment": resource.to_dict(),
        "implementation_provenance": (
            "Multi-pair state preparation and occupied-to-virtual Givens structure "
            "were extracted from Bathri's earlier qcol_platform implementation."
        ),
    }


multi_pair_hamiltonian_policy = reduced_pairing_hamiltonian_policy
multi_pair_sector_policy = reduced_pairing_sector_policy
multi_pair_mapping_policy = pair_mapping_policy
multi_pair_state_preparation_policy = lowest_level_pair_state_policy
multi_pair_ansatz_policy = bathri_multi_pair_ansatz_policy
multi_pair_measurement_policy = pauli_energy_qwc_measurement_policy
multi_pair_reference_policy = exact_pair_sector_reference_policy
multi_pair_resource_policy = pair_resource_policy
multi_pair_runtime_policy = external_variational_energy_runtime_policy

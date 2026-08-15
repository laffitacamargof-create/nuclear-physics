"""Policies for bounded custom qubit Hamiltonians."""
from __future__ import annotations

from typing import Any

from ...model_execution_types import HamiltonianBuildResult, ModelBuildContext
from ...modeling import exact_reference_from_matrix, operator_matrix, parse_custom_matrix, parse_custom_pauli
from ..direct_qubit_common import (
    bounded_direct_resource_policy,
    direct_mapping_policy,
    external_variational_energy_runtime_policy,
    generic_ry_rz_ansatz_policy,
    no_sector_policy,
    qwc_measurement_policy,
    zero_state_policy,
)


def custom_qubit_hamiltonian_policy(context: ModelBuildContext) -> HamiltonianBuildResult:
    p=dict(context.instance.parameters)
    route=str(p.get("input_route","matrix")).lower()
    if route == "matrix":
        matrix,n_qubits=parse_custom_matrix(p.get("matrix"))
        from ...modeling import matrix_to_qubit_operator
        operator=matrix_to_qubit_operator(matrix,n_qubits)
        route_metadata={"input_route":"matrix","matrix_shape":list(matrix.shape)}
    elif route == "pauli":
        operator,n_qubits=parse_custom_pauli(p.get("pauli_terms"),declared_n_qubits=int(p.get("n_qubits",1)))
        route_metadata={"input_route":"pauli"}
    else:
        raise ValueError("input_route must be 'matrix' or 'pauli'.")
    if n_qubits > 6:
        raise ValueError("The bounded custom route supports at most six qubits.")
    return HamiltonianBuildResult(
        domain_hamiltonian=operator,
        representation="qubit_operator_custom",
        parameters={
            "input_route":route,
            "n_qubits":n_qubits,
            "ansatz_layers":int(p.get("ansatz_layers",1)),
        },
        units=dict(context.instance.units),
        metadata={
            "n_qubits":n_qubits,
            "mapping_name":"direct_custom_qubit",
            "encoding":"user_declared_qubit_basis",
            "mapping_metadata":route_metadata,
        },
        provenance={"builder":"custom_qubit_hamiltonian.custom_qubit_hamiltonian_policy"},
    )


def custom_full_reference_policy(context,mapping,sector):
    matrix=operator_matrix(mapping.qubit_hamiltonian,mapping.n_qubits)
    result=exact_reference_from_matrix(
        matrix,
        reference_scope="full declared custom qubit Hilbert space",
        acceptance_abs_floor=float(context.request_metadata.get("acceptance_abs_floor",0.05)),
        target_state_labels=[f"basis_{i}" for i in range(matrix.shape[0])],
    )
    result["validity"]=context.contract.reference_validity.to_dict()
    return result


def custom_interpretation_policy(context,mapping,sector,reference,resource):
    return {
        "scientific_quantity":"lowest eigenvalue of the declared custom qubit Hamiltonian",
        "supported_statement":(
            "The sampled OpenQASM 2 workflow reconstructs the ground-state energy "
            "of the declared custom qubit Hamiltonian."
        ),
        "limitations":list(context.contract.limitations),
        "model_contract":context.contract.to_dict(),
        "resource_assessment":resource.to_dict(),
    }

custom_sector_policy=no_sector_policy
custom_mapping_policy=direct_mapping_policy
custom_state_preparation_policy=zero_state_policy
custom_ansatz_policy=generic_ry_rz_ansatz_policy
custom_measurement_policy=qwc_measurement_policy
custom_resource_policy=bounded_direct_resource_policy
custom_runtime_policy=external_variational_energy_runtime_policy

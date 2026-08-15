"""Common policies for models that already build a qubit Hamiltonian."""
from __future__ import annotations

from typing import Any, Mapping

from .direct_qubit_resources import bounded_direct_resource_policy

import cirq
import numpy as np
import sympy

from ..measurement import build_qwc_measurement_plan
from ..model_execution_types import (
    AnsatzBuildResult,
    MappingResult,
    SectorValidationResult,
    StatePreparationResult,
)
from ..modeling import basis_index, build_pair_ansatz_template, exact_reference_from_matrix, operator_matrix


def direct_mapping_policy(context, hamiltonian, sector) -> MappingResult:
    operator = hamiltonian.domain_hamiltonian
    n_qubits = int(hamiltonian.metadata["n_qubits"])
    matrix = operator_matrix(operator, n_qubits)
    validation = {
        "operator_hermitian": bool(np.allclose(matrix, matrix.conj().T, atol=1e-10)),
        "direct_mapping_declared": True,
    }
    return MappingResult(
        qubit_hamiltonian=operator,
        n_qubits=n_qubits,
        mapping_name=str(hamiltonian.metadata.get("mapping_name", "direct_qubit")),
        encoding=str(hamiltonian.metadata.get("encoding", "direct_qubit")),
        mapping_metadata={
            "policy_id": context.contract.mapping_policy_id,
            "source_representation": hamiltonian.representation,
            "n_qubits": n_qubits,
            **dict(hamiltonian.metadata.get("mapping_metadata", {})),
        },
        orbital_to_qubit_order={
            str(index): {
                "qubit": index,
                "meaning": str(
                    hamiltonian.metadata.get("qubit_meanings", {}).get(
                        str(index), f"declared qubit {index}"
                    )
                ),
            }
            for index in range(n_qubits)
        },
        preserved_symmetries=tuple(sector.conserved_quantities),
        validation_checks=validation,
    )


def one_excitation_sector_policy(context, hamiltonian) -> SectorValidationResult:
    n_quanta = int(context.instance.parameters.get("n_quanta", context.instance.parameters.get("n_excitations", 1)))
    if n_quanta != 1:
        raise ValueError("This bounded route supports exactly one excitation/quantum.")
    return SectorValidationResult(
        target_sector={"excitation_number": 1},
        conserved_quantities=("excitation_number",),
        validation_checks={"one_excitation_sector": True},
        metadata={"computational_sector": "Hamming weight 1"},
    )


def no_sector_policy(context, hamiltonian) -> SectorValidationResult:
    return SectorValidationResult(
        target_sector=dict(context.instance.target_sector),
        conserved_quantities=tuple(context.contract.conserved_quantities),
        validation_checks={"declared_sector_is_optional": True},
        metadata={"computational_sector": "not constrained by the generic route"},
    )


def lowest_mode_state_policy(context, mapping, sector) -> StatePreparationResult:
    qubits = tuple(cirq.LineQubit.range(mapping.n_qubits))
    circuit = cirq.Circuit(cirq.X(qubits[0]))
    return StatePreparationResult(
        circuit=circuit,
        label="lowest_mode_occupied",
        occupied_indices=(0,),
        metadata={"basis_bitstring": "1" + "0" * (mapping.n_qubits - 1)},
    )


def zero_state_policy(context, mapping, sector) -> StatePreparationResult:
    return StatePreparationResult(
        circuit=cirq.Circuit(),
        label="computational_zero_state",
        occupied_indices=tuple(),
        metadata={"basis_bitstring": "0" * mapping.n_qubits},
    )


def one_excitation_chain_ansatz_policy(
    context,
    mapping,
    sector,
    initial_state,
    reference=None,
) -> AnsatzBuildResult:
    n_qubits = mapping.n_qubits
    symbols = tuple(sympy.symbols(f"theta_0:{max(n_qubits - 1, 0)}"))
    full = build_pair_ansatz_template(symbols, tuple(cirq.LineQubit.range(n_qubits)))
    variational = cirq.Circuit(
        op for op in full.all_operations() if not (
            isinstance(op.gate, cirq.XPowGate)
            and len(op.qubits) == 1
            and op.qubits[0] == cirq.LineQubit(0)
            and float(op.gate.exponent) % 2 == 1
        )
    )
    return AnsatzBuildResult(
        variational_circuit=variational,
        parameter_symbols=symbols,
        initial_parameters=tuple(0.0 for _ in symbols),
        family="one_excitation_chain_givens",
        parameter_fixture=None,
        metadata={"conserves_excitation_number": True},
    )


def generic_ry_rz_ansatz_policy(
    context,
    mapping,
    sector,
    initial_state,
    reference=None,
) -> AnsatzBuildResult:
    from ..modeling import build_generic_ansatz_template

    n_layers = int(context.instance.parameters.get("ansatz_layers", 1))
    circuit, symbols = build_generic_ansatz_template(mapping.n_qubits, n_layers=n_layers)
    return AnsatzBuildResult(
        variational_circuit=circuit,
        parameter_symbols=symbols,
        initial_parameters=tuple(0.0 for _ in symbols),
        family="generic_ry_rz_linear_cnot",
        parameter_fixture=None,
        metadata={"n_layers": n_layers},
    )


def qwc_measurement_policy(context, mapping, ansatz):
    return build_qwc_measurement_plan(mapping.qubit_hamiltonian)


def exact_one_excitation_reference_policy(context, mapping, sector):
    import numpy as np
    n_qubits = mapping.n_qubits
    matrix = operator_matrix(mapping.qubit_hamiltonian, n_qubits)
    indices = [basis_index([mode], n_qubits) for mode in range(n_qubits)]
    sector_matrix = matrix[np.ix_(indices, indices)]
    result = exact_reference_from_matrix(
        sector_matrix,
        reference_scope=f"one-excitation sector of {context.contract.label}",
        acceptance_abs_floor=float(context.request_metadata.get("acceptance_abs_floor", 0.05)),
        target_state_labels=[f"excitation_in_mode_{mode}" for mode in range(n_qubits)],
    )
    result["validity"] = context.contract.reference_validity.to_dict()
    return result

def external_variational_energy_runtime_policy(context):
    return {
        "runtime_policy_id": "external_variational_energy.v1",
        "task_id": context.instance.task_id,
        "shared_runtime": "qcol.orchestrator + qcol.optimizer",
    }

"""Callable policy bindings for the verified one-pair plugin."""
from __future__ import annotations

from typing import Any, Mapping

import cirq
import numpy as np
import sympy

from ...model_execution_types import AnsatzBuildResult, ModelBuildContext
from ...modeling import (
    build_pair_ansatz_template,
    chain_angles_from_positive_real_state,
    phase_align_nonnegative_real,
)
from ..reduced_pairing_common import (
    exact_pair_sector_reference_policy,
    external_variational_energy_runtime_policy,
    lowest_level_pair_state_policy,
    pair_mapping_policy,
    pair_resource_policy,
    pauli_energy_qwc_measurement_policy,
    reduced_pairing_hamiltonian_policy,
    reduced_pairing_sector_policy,
)


def one_pair_chain_ansatz_policy(
    context: ModelBuildContext,
    mapping,
    sector,
    initial_state,
    reference: Mapping[str, Any] | None = None,
) -> AnsatzBuildResult:
    n_levels = int(context.instance.parameters["n_levels"])
    symbols = tuple(sympy.symbols(f"theta_0:{n_levels - 1}"))
    qubits = tuple(cirq.LineQubit.range(n_levels))
    # Existing helper includes X(q0); remove that preparation because the
    # state-preparation policy now owns it.
    full = build_pair_ansatz_template(symbols, qubits)
    variational = cirq.Circuit(
        op for op in full.all_operations() if not (
            isinstance(op.gate, cirq.XPowGate)
            and len(op.qubits) == 1
            and op.qubits[0] == qubits[0]
            and float(op.gate.exponent) % 2 == 1
        )
    )

    fixture = None
    if reference is not None:
        target_state = phase_align_nonnegative_real(
            np.asarray(reference.get("target_state_amplitudes", []), dtype=complex)
        )
        if target_state is not None:
            fixture = {
                "source": "exact_small_sector_state_to_chain_givens",
                "values": chain_angles_from_positive_real_state(target_state).tolist(),
                "not_a_vqe_result": True,
            }

    return AnsatzBuildResult(
        variational_circuit=variational,
        parameter_symbols=symbols,
        initial_parameters=tuple(0.0 for _ in symbols),
        family="one_pair_chain_givens",
        parameter_fixture=fixture,
        metadata={
            "conserves_pair_number_by_construction": True,
            "regression_anchor": True,
        },
    )


def one_pair_interpretation_policy(
    context: ModelBuildContext,
    mapping,
    sector,
    reference,
    resource,
) -> Mapping[str, Any]:
    return {
        "scientific_quantity": "lowest energy in the declared one-pair sector",
        "supported_statement": (
            "The sampled OpenQASM 2 workflow reconstructs the energy of the "
            "declared reduced pairing Hamiltonian in its one-pair seniority-zero sector."
        ),
        "limitations": list(context.contract.limitations),
        "model_contract": context.contract.to_dict(),
        "supported_task": context.instance.task_id,
        "resource_assessment": resource.to_dict(),
    }


# Re-export common policies under stable import paths used by the registry.
one_pair_hamiltonian_policy = reduced_pairing_hamiltonian_policy
one_pair_sector_policy = reduced_pairing_sector_policy
one_pair_mapping_policy = pair_mapping_policy
one_pair_state_preparation_policy = lowest_level_pair_state_policy
one_pair_measurement_policy = pauli_energy_qwc_measurement_policy
one_pair_reference_policy = exact_pair_sector_reference_policy
one_pair_resource_policy = pair_resource_policy
one_pair_runtime_policy = external_variational_energy_runtime_policy

"""Plugin-owned scientific-identity derivations used at the composition root.

These helpers are implementation details behind ``ModelPlugin`` descriptors.
They carry already-resolved identities into the canonical artifact; they never
consult UI metadata and never re-run compatibility resolution.
"""
from __future__ import annotations

from typing import Any, Mapping


def pair_encoding_context(*, instance, mapping, task_plan=None) -> str:
    n_levels = int(instance.parameters.get("n_levels", mapping.n_qubits))
    n_pairs = int(instance.target_sector.get("pair_number", instance.parameters.get("n_pairs", 1)))
    return f"pair.encoding-context.{n_levels}levels.{n_pairs}pairs.v1"


def hard_core_encoding_context(*, instance, mapping, task_plan=None) -> str:
    n_modes = int(instance.parameters.get("n_modes", mapping.n_qubits))
    number = int(instance.target_sector.get("excitation_number", instance.parameters.get("n_quanta", 1)))
    return f"hard_core_mode.encoding-context.{n_modes}modes.N{number}.v1"


def guided_encoding_context(*, instance, mapping, task_plan=None) -> str:
    n_modes = int(instance.parameters.get("n_modes", mapping.n_qubits))
    number = int(instance.target_sector.get("excitation_number", instance.parameters.get("n_excitations", 1)))
    return f"guided_occupation.encoding-context.{n_modes}modes.N{number}.v1"


def custom_qubit_encoding_context(*, instance, mapping, task_plan=None) -> str:
    return f"custom_qubit.encoding-context.{int(mapping.n_qubits)}qubits.v1"


def spin_orbital_encoding_context(*, instance, mapping, task_plan=None) -> str:
    n_modes = int(instance.parameters.get("n_modes", mapping.n_qubits))
    task_id = instance.task_id if task_plan is None else task_plan.task_contract.task_id
    if task_id == "mapping_analysis":
        return f"spin_orbital.mode_order.{n_modes}.v1"
    number = int(instance.target_sector.get("particle_number", instance.parameters.get("target_particle_number", 0)))
    return f"jw.encoding-context.{n_modes}modes.N{number}.v1"


def _task_identity(model_plan, task_plan):
    if task_plan is None:
        return model_plan.instance.task_id, None
    return task_plan.task_contract.task_id, task_plan.task_execution_plan


def default_scientific_identity(
    *, model_plan, task_plan, mapping, ansatz, encoding_context_id: str
) -> Mapping[str, Any]:
    """Carry the already-resolved model/task policy identities."""
    contract = model_plan.contract
    task_id, execution = _task_identity(model_plan, task_plan)
    observable_task = task_id == "observable_estimation" and execution is not None
    return {
        "encoding_context_id": encoding_context_id,
        "mapping_policy_id": contract.mapping_policy_id,
        "state_preparation_policy_id": contract.state_preparation_policy_id,
        "ansatz_policy_id": str(ansatz.metadata.get("policy_id", contract.ansatz_policy_id)),
        "measurement_policy_id": execution.measurement_policy_id if observable_task else contract.measurement_policy_id,
        "reference_policy_id": execution.reference_policy_id if observable_task else contract.reference_policy_id,
        "controller_id": execution.controller_policy_id if execution is not None else contract.runtime_policy_id,
    }


def spin_orbital_scientific_identity(
    *, model_plan, task_plan, mapping, ansatz, encoding_context_id: str
) -> Mapping[str, Any]:
    """Carry task-aware spin-orbital identities behind the model plugin seam."""
    task_id, execution = _task_identity(model_plan, task_plan)
    if task_id == "mapping_analysis":
        return {
            "encoding_context_id": encoding_context_id,
            "mapping_policy_id": model_plan.contract.mapping_policy_id,
            "state_preparation_policy_id": "analysis_only_state.v1",
            "ansatz_policy_id": "analysis_only_ansatz.v1",
            "measurement_policy_id": execution.measurement_policy_id if execution is not None else "mapping_analysis.no_measurement.v1",
            "reference_policy_id": execution.reference_policy_id if execution is not None else "fermionic_fock_space_spectrum.v1",
            "controller_id": execution.controller_policy_id if execution is not None else "single_pass.mapping_analysis.v1",
        }
    return {
        "encoding_context_id": encoding_context_id,
        "mapping_policy_id": "jordan_wigner.spin_orbital.v1",
        "state_preparation_policy_id": "jw.state.occupation_determinant.v1",
        "ansatz_policy_id": str(ansatz.metadata.get("policy_id", "jw.ansatz.mapped_fermionic_swap_network.v1")),
        "measurement_policy_id": "jw.measurement.pauli_energy_qwc.v1",
        "reference_policy_id": "jw.reference.fixed_particle_sector.v1",
        "controller_id": execution.controller_policy_id if execution is not None else "external_variational_energy.v1",
    }


__all__ = [
    "pair_encoding_context",
    "hard_core_encoding_context",
    "guided_encoding_context",
    "custom_qubit_encoding_context",
    "spin_orbital_encoding_context",
    "default_scientific_identity",
    "spin_orbital_scientific_identity",
]

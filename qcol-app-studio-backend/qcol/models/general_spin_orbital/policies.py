"""Model-policy bindings for the general spin-orbital representation.

The same representation plugin supports two task cells without duplicating the
shared runtime:

* ``mapping_analysis`` — deterministic JW/BK transformation and resources;
* ``ground_state_energy`` — the bounded JW execution cell added in Phase A.3.2.

The policy IDs are task-aware dispatch points.  The TaskContract still chooses
the controller; these policies only build model-specific scientific artifacts.
"""
from __future__ import annotations

from math import comb
from typing import Any, Mapping

import cirq
import numpy as np

from ...mappings import get_mapping_plugin
from ...measurement import build_qwc_measurement_plan
from ...model_execution_types import (
    AnsatzBuildResult,
    HamiltonianBuildResult,
    MappingResult,
    ModelBuildContext,
    ResourceAssessment,
    SectorValidationResult,
    StatePreparationResult,
)
from ...spin_orbital import SpinOrbitalInstance, build_fermion_operator
from .jw_fermionic_ansatz import (
    build_jw_mapped_fermionic_ansatz,
    jw_mapped_ansatz_parameter_count,
)
from .jw_ground_state import (
    JW_GROUND_STATE_MAX_LAYERS,
    JW_GROUND_STATE_MAX_MODES,
    exact_fixed_particle_reference,
    select_initial_occupied_modes,
)


def _task(context: ModelBuildContext) -> str:
    return str(context.instance.task_id)


def _requested_mapping_id(context: ModelBuildContext) -> str:
    """Return the resolver-level mapping selection.

    New requests declare ``mapping_id`` at request scope. A legacy
    task-parameter fallback is retained for archived requests.
    """
    if context.request_metadata.get("mapping_id") is not None:
        return str(context.request_metadata["mapping_id"])
    legacy = dict(context.request_metadata.get("task_parameters", {}))
    return str(legacy.get("mapping_id", "jordan_wigner.v1"))


def general_spin_orbital_hamiltonian_policy(
    context: ModelBuildContext,
) -> HamiltonianBuildResult:
    spin_instance = SpinOrbitalInstance.from_model_instance(context.instance)
    built = build_fermion_operator(spin_instance)
    return HamiltonianBuildResult(
        domain_hamiltonian=built.fermion_operator,
        representation="general_spin_orbital_fermion_operator",
        parameters={
            **dict(context.instance.parameters),
            "spin_orbital_contract": spin_instance.to_dict(),
        },
        units=dict(context.instance.units),
        metadata={
            **dict(built.metadata),
            "n_qubits": spin_instance.n_modes,
            "particle_number_operator": built.particle_number_operator,
            "spin_orbital_instance": spin_instance,
        },
        provenance={
            "builder": "qcol.spin_orbital.builder:build_fermion_operator",
            "representation_contract": context.contract.representation_contract,
            "source_provenance": dict(spin_instance.source_provenance),
            "task_id": _task(context),
        },
    )


def general_spin_orbital_sector_policy(
    context: ModelBuildContext,
    hamiltonian: HamiltonianBuildResult,
) -> SectorValidationResult:
    spin_instance = hamiltonian.metadata["spin_orbital_instance"]
    target = int(spin_instance.total_target_particles)
    task_id = _task(context)
    validation = {
        "target_particle_number_nonnegative": target >= 0,
        "target_particle_number_within_modes": target <= spin_instance.n_modes,
        "mode_order_declared": len(spin_instance.mode_labels) == spin_instance.n_modes,
        "particle_number_declared": "particle_number" in spin_instance.declared_symmetries,
    }
    if task_id == "ground_state_energy":
        validation.update({
            "nontrivial_ground_state_sector": 0 < target < spin_instance.n_modes,
            "jw_execution_mode_bound": spin_instance.n_modes <= JW_GROUND_STATE_MAX_MODES,
            "single_species_execution_cell": (
                len(spin_instance.particle_species) == 1
                and len(spin_instance.target_particle_numbers) == 1
                and len({mode.species for mode in spin_instance.mode_labels}) == 1
            ),
        })
    return SectorValidationResult(
        target_sector={
            "particle_number": target,
            "particle_numbers": dict(spin_instance.target_particle_numbers),
        },
        conserved_quantities=tuple(spin_instance.declared_symmetries),
        validation_checks=validation,
        metadata={
            "spin_orbital_instance": spin_instance.to_dict(),
            "sector_interpretation": "fixed total particle-number eigenspace",
            "task_id": task_id,
        },
    )


def general_spin_orbital_primary_jw_mapping_policy(
    context: ModelBuildContext,
    hamiltonian: HamiltonianBuildResult,
    sector: SectorValidationResult,
) -> MappingResult:
    spin_instance = hamiltonian.metadata["spin_orbital_instance"]
    particle_number_operator = hamiltonian.metadata["particle_number_operator"]
    plugin = get_mapping_plugin("jordan_wigner.v1")
    task_id = _task(context)
    requested_mapping = _requested_mapping_id(context)
    if task_id == "ground_state_energy" and requested_mapping != "jordan_wigner.v1":
        raise ValueError(
            "The Phase A.3.2 execution cell is Jordan–Wigner only. "
            f"Requested mapping: {requested_mapping!r}."
        )
    compatibility = plugin.check_compatibility(spin_instance, task_id=task_id)
    if not compatibility.compatible:
        raise ValueError(
            "Jordan–Wigner is not compatible with the declared spin-orbital "
            f"request: {compatibility.reasons}"
        )
    mapped_h = plugin.transform_hamiltonian(
        hamiltonian.domain_hamiltonian,
        n_modes=spin_instance.n_modes,
    )
    mapped_n = plugin.transform_observable(
        particle_number_operator,
        n_modes=spin_instance.n_modes,
    )
    mapping_capability = plugin.capability_report(spin_instance)
    if task_id == "ground_state_energy" and not mapping_capability.ground_state_execution_ready:
        raise ValueError(
            "The registered JW plugin has not declared the bounded ground-state "
            "execution capability required by Phase A.3.2."
        )
    return MappingResult(
        qubit_hamiltonian=mapped_h,
        n_qubits=spin_instance.n_modes,
        mapping_name="jordan_wigner",
        encoding="spin_orbital_occupation_jordan_wigner",
        mapping_metadata={
            "policy_id": context.contract.mapping_policy_id,
            "mapping_plugin_id": plugin.mapping_id,
            "mapping_plugin_version": plugin.mapping_version,
            "selection_role": (
                "primary execution mapping for the bounded JW ground-state cell"
                if task_id == "ground_state_energy"
                else "primary inspectable artifact for mapping analysis"
            ),
            "mapping_candidates": list(context.contract.compatible_mapping_ids),
            "raw_popcount_is_particle_number": True,
            "sector_bit_count_key": "particle_number",
            "compatibility_report": compatibility.to_dict(),
            "capability_report": mapping_capability.to_dict(),
            "task_id": task_id,
        },
        orbital_to_qubit_order={
            str(mode.index): {
                "qubit": mode.index,
                "species": mode.species,
                "orbital": mode.orbital,
                "projection": mode.projection,
            }
            for mode in spin_instance.mode_labels
        },
        preserved_symmetries=tuple(spin_instance.declared_symmetries),
        crosscheck_payloads={
            "fermion_operator": hamiltonian.domain_hamiltonian,
            "particle_number_operator": particle_number_operator,
            "mapped_particle_number_operator": mapped_n,
            "spin_orbital_instance": spin_instance,
            "mapping_candidates": tuple(context.contract.compatible_mapping_ids),
        },
        validation_checks={
            "mapping_plugin_compatible": compatibility.compatible,
            "primary_mapping_is_jw": True,
            "mode_to_qubit_order_complete": True,
            "jw_popcount_matches_particle_number": True,
            "ground_state_mapping_capability": (
                True if task_id != "ground_state_energy"
                else mapping_capability.ground_state_execution_ready
            ),
        },
    )


def general_spin_orbital_state_policy(
    context: ModelBuildContext,
    mapping: MappingResult,
    sector: SectorValidationResult,
) -> StatePreparationResult:
    if _task(context) == "mapping_analysis":
        return StatePreparationResult(
            circuit=cirq.Circuit(),
            label="analysis_only_no_state_preparation",
            occupied_indices=tuple(),
            metadata={
                "applicable": False,
                "reason": "mapping_analysis compares operators and does not execute a prepared state",
            },
        )

    if mapping.mapping_name != "jordan_wigner":
        raise ValueError("The Phase A.3.2 ground-state cell is JW-only.")
    spin_instance = mapping.crosscheck_payloads["spin_orbital_instance"]
    occupied = select_initial_occupied_modes(spin_instance, context.instance.parameters)
    qubits = tuple(cirq.LineQubit.range(mapping.n_qubits))
    circuit = cirq.Circuit(cirq.X(qubits[index]) for index in occupied)
    occupation_vector = [1 if index in occupied else 0 for index in range(mapping.n_qubits)]
    return StatePreparationResult(
        circuit=circuit,
        label="jw_occupation_determinant",
        occupied_indices=occupied,
        metadata={
            "applicable": True,
            "mapping_id": "jordan_wigner.v1",
            "occupation_vector": occupation_vector,
            "basis_bitstring": "".join(str(value) for value in occupation_vector),
            "target_particle_number": int(sector.target_sector["particle_number"]),
            "selection_strategy": str(select_initial_occupied_modes.last_strategy),
            "exact_reference_used_for_state_preparation": False,
            "state_preparation_gates": [f"X(q{index})" for index in occupied],
        },
    )


def general_spin_orbital_ansatz_policy(
    context: ModelBuildContext,
    mapping: MappingResult,
    sector: SectorValidationResult,
    initial_state: StatePreparationResult,
    reference: Mapping[str, Any] | None = None,
) -> AnsatzBuildResult:
    if _task(context) == "mapping_analysis":
        return AnsatzBuildResult(
            variational_circuit=cirq.Circuit(),
            parameter_symbols=tuple(),
            initial_parameters=tuple(),
            family="analysis_only_no_ansatz",
            parameter_fixture=None,
            metadata={
                "applicable": False,
                "reason": "Phase A.3.1 verifies transformations and resources, not VQE",
            },
        )

    n_layers = int(context.instance.parameters.get("ansatz_layers", 1))
    circuit, symbols, metadata = build_jw_mapped_fermionic_ansatz(
        mapping.n_qubits,
        n_layers,
    )
    metadata = {
        **dict(metadata),
        "mapping_id": "jordan_wigner.v1",
        "target_particle_number": int(sector.target_sector["particle_number"]),
        "initial_occupied_modes": list(initial_state.occupied_indices),
        "sector_leakage_expected": 0.0,
        "acceptance_status": "acceptance_verified_wp11",
    }
    return AnsatzBuildResult(
        variational_circuit=circuit,
        parameter_symbols=symbols,
        initial_parameters=tuple(0.0 for _ in symbols),
        family="jw_mapped_fermionic_swap_network",
        parameter_fixture=None,
        metadata=metadata,
    )


def general_spin_orbital_measurement_policy(
    context: ModelBuildContext,
    mapping: MappingResult,
    ansatz: AnsatzBuildResult,
):
    return build_qwc_measurement_plan(mapping.qubit_hamiltonian)


def _dense(operator: Any, n_qubits: int) -> np.ndarray:
    from openfermion import get_sparse_operator

    return np.asarray(
        get_sparse_operator(operator, n_qubits=n_qubits).toarray(),
        dtype=np.complex128,
    )


def _fixed_number_spectrum(
    hamiltonian_matrix: np.ndarray,
    number_matrix: np.ndarray,
    target: int,
    *,
    tolerance: float = 1e-8,
) -> np.ndarray:
    values, vectors = np.linalg.eigh((number_matrix + number_matrix.conj().T) / 2)
    selector = np.isclose(values, float(target), atol=tolerance, rtol=0.0)
    if not np.any(selector):
        raise ValueError(f"No states found in target particle-number sector N={target}.")
    basis = vectors[:, selector]
    projected = basis.conj().T @ hamiltonian_matrix @ basis
    return np.linalg.eigvalsh((projected + projected.conj().T) / 2)


def general_spin_orbital_reference_policy(
    context: ModelBuildContext,
    mapping: MappingResult,
    sector: SectorValidationResult,
):
    fermion_operator = mapping.crosscheck_payloads["fermion_operator"]
    n_modes = mapping.n_qubits
    target = int(sector.target_sector["particle_number"])
    if _task(context) == "ground_state_energy":
        return exact_fixed_particle_reference(
            fermion_operator,
            n_modes=n_modes,
            particle_number=target,
            acceptance_abs_floor=float(
                context.request_metadata.get("acceptance_abs_floor", 0.03)
            ),
            validity=context.contract.reference_validity.to_dict(),
        )

    particle_number_operator = mapping.crosscheck_payloads["particle_number_operator"]
    h_matrix = _dense(fermion_operator, n_modes)
    n_matrix = _dense(particle_number_operator, n_modes)
    full_spectrum = np.linalg.eigvalsh((h_matrix + h_matrix.conj().T) / 2)
    sector_spectrum = _fixed_number_spectrum(h_matrix, n_matrix, target)
    return {
        "kind": "exact_spin_orbital_fock_space_and_fixed_particle_sector",
        "reference_scope": (
            f"full {n_modes}-mode Fock space and fixed particle-number sector N={target}"
        ),
        "reference_energy": float(sector_spectrum[0]),
        "full_spectrum": [float(value) for value in full_spectrum],
        "target_sector_spectrum": [float(value) for value in sector_spectrum],
        "target_particle_number": target,
        "validity": context.contract.reference_validity.to_dict(),
        "analysis_only": True,
    }


def general_spin_orbital_resource_policy(
    context: ModelBuildContext,
    mapping: MappingResult | None = None,
    ansatz: AnsatzBuildResult | None = None,
    measurement_plan: Mapping[str, Any] | None = None,
):
    n_modes = int(context.instance.parameters.get("n_modes", 0))
    task_id = _task(context)
    if task_id == "mapping_analysis":
        parameter_count = 0
        within = 2 <= n_modes <= 8
        sector_dimension = None
        notes = (
            "Exact JW/BK mapping analysis is bounded to at most eight modes.",
            "No circuit or backend resource claim is made.",
        )
    else:
        n_layers = int(context.instance.parameters.get("ansatz_layers", 1))
        target = int(context.instance.parameters.get("target_particle_number", 0))
        parameter_count = (
            jw_mapped_ansatz_parameter_count(n_modes, n_layers)
            if n_modes >= 2 and n_layers >= 1 else 0
        )
        requested_mapping = _requested_mapping_id(context)
        spin_instance = SpinOrbitalInstance.from_model_instance(context.instance)
        single_species = (
            len(spin_instance.particle_species) == 1
            and len(spin_instance.target_particle_numbers) == 1
            and len({mode.species for mode in spin_instance.mode_labels}) == 1
        )
        within = (
            2 <= n_modes <= JW_GROUND_STATE_MAX_MODES
            and 0 < target < n_modes
            and 1 <= n_layers <= JW_GROUND_STATE_MAX_LAYERS
            and parameter_count <= 32
            and requested_mapping == "jordan_wigner.v1"
            and single_species
        )
        sector_dimension = comb(n_modes, target) if 0 <= target <= n_modes else None
        notes = (
            "Phase A.3.2 executes only Jordan–Wigner on 2–4 modes.",
            "The mapping-aware fermionic swap-network ansatz is bounded to one or two layers and at most 32 parameters.",
            "BK remains analysis-only in this release.",
        )

    if mapping is None:
        return {
            "estimated_n_qubits": n_modes,
            "estimated_parameter_count": parameter_count,
            "estimated_sector_dimension": sector_dimension,
            "within_declared_envelope": within,
            "task_id": task_id,
            "requested_mapping": (
                None if task_id == "mapping_analysis" else requested_mapping
            ),
            "single_species_execution_cell": (
                None if task_id == "mapping_analysis" else single_species
            ),
            "mapping_candidates": (
                list(context.contract.compatible_mapping_ids)
                if task_id == "mapping_analysis" else ["jordan_wigner.v1"]
            ),
        }
    groups = len((measurement_plan or {}).get("groups", []))
    return ResourceAssessment(
        status="within_envelope" if within else "outside_envelope",
        n_qubits=mapping.n_qubits,
        parameter_count=(
            parameter_count if ansatz is None else len(ansatz.parameter_symbols)
        ),
        pauli_term_count=len(mapping.qubit_hamiltonian.terms),
        measurement_group_count=groups,
        estimated_sector_dimension=sector_dimension,
        within_declared_envelope=within,
        notes=notes,
    )


def general_spin_orbital_runtime_policy(context: ModelBuildContext):
    task_id = _task(context)
    return {
        "runtime_policy_id": context.contract.runtime_policy_id,
        "task_id": task_id,
        "selected_runtime": (
            "qcol.controllers.mapping_analysis"
            if task_id == "mapping_analysis"
            else "qcol.controllers.optimizer_loop + qcol.runtime"
        ),
        "backend_required": task_id == "ground_state_energy",
        "shots_required": task_id == "ground_state_energy",
        "qasm_execution_required": task_id == "ground_state_energy",
    }


def general_spin_orbital_interpretation_policy(
    context: ModelBuildContext,
    mapping: MappingResult,
    sector: SectorValidationResult,
    reference: Mapping[str, Any] | None,
    resource: ResourceAssessment,
):
    if _task(context) == "mapping_analysis":
        return {
            "scientific_quantity": "fermion-to-qubit mapping equivalence and operator-resource structure",
            "supported_statement": (
                "The declared finite spin-orbital Hamiltonian is represented in a "
                "standardized FermionOperator form and is eligible for registered "
                "mapping-analysis plugins."
            ),
            "limitations": list(context.contract.limitations),
            "representation_contract": context.contract.representation_contract,
            "compatible_mappings": list(context.contract.compatible_mapping_ids),
            "resource_assessment": resource.to_dict(),
        }
    return {
        "scientific_quantity": "lowest energy in the declared fixed-particle spin-orbital sector",
        "supported_statement": (
            "The shared sampled workflow prepares a JW-encoded fixed-particle state, "
            "applies a particle-number-preserving ansatz, reconstructs the mapped "
            "Hamiltonian expectation, and compares it with an exact bounded fixed-sector reference."
        ),
        "unit": context.instance.units.get("energy", "unspecified"),
        "mapping": "jordan_wigner.v1",
        "target_sector": dict(sector.target_sector),
        "limitations": list(context.contract.limitations),
        "resource_assessment": resource.to_dict(),
        "execution_boundary": (
            "Bounded local-simulator cell for 2–4 modes. BK ground-state execution "
            "is not enabled. Strongly correlated inputs may require a richer ansatz "
            "and may return REVIEW rather than PASS."
        ),
    }


# Backward-compatible names retained for archived Phase A.3.1 imports.
analysis_only_state_policy = general_spin_orbital_state_policy
analysis_only_ansatz_policy = general_spin_orbital_ansatz_policy
analysis_only_measurement_policy = general_spin_orbital_measurement_policy
small_exact_spin_orbital_reference_policy = general_spin_orbital_reference_policy
bounded_spin_orbital_mapping_resource_policy = general_spin_orbital_resource_policy
mapping_analysis_runtime_policy = general_spin_orbital_runtime_policy
mapping_analysis_model_interpretation_policy = general_spin_orbital_interpretation_policy

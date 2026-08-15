"""Model × task execution matrix.

Executability belongs to a cell, not to a model or task in isolation.  Every
cell declares its own status, reference validity, resource envelope, resolved
policy intent, and acceptance suite.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Tuple

from .model_contracts import ModelContractError
from .task_registry import canonical_task_id

CELL_STATUSES = {
    "acceptance_verified",
    "execution_ready",
    "experimental",
    "planned",
    "registered",
    "not_applicable",
    "unsupported",
}


@dataclass(frozen=True)
class ModelTaskCell:
    model_id: str
    task_id: str
    status: str
    label: str
    resolved_policy_intent: Mapping[str, str] = field(default_factory=dict)
    reference_validity: Mapping[str, Any] = field(default_factory=dict)
    resource_envelope: Mapping[str, Any] = field(default_factory=dict)
    acceptance_suite_id: Optional[str] = None
    notes: Tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.status not in CELL_STATUSES:
            raise ModelContractError(f"Unsupported model-task cell status {self.status!r}.")

    @property
    def runnable(self) -> bool:
        return self.status in {"acceptance_verified", "execution_ready", "experimental"}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cell_id": f"{self.model_id}::{self.task_id}",
            "model_id": self.model_id,
            "task_id": self.task_id,
            "status": self.status,
            "runnable": self.runnable,
            "label": self.label,
            "resolved_policy_intent": dict(self.resolved_policy_intent),
            "reference_validity": dict(self.reference_validity),
            "resource_envelope": dict(self.resource_envelope),
            "acceptance_suite_id": self.acceptance_suite_id,
            "notes": list(self.notes),
        }


GROUND = "ground_state_energy"
OBS = "observable_estimation"
EXCITED = "excited_states"
TIME = "time_evolution"
PHASE = "eigenphase"
MAP_ANALYSIS = "mapping_analysis"


def _cell(model_id: str, task_id: str, status: str, label: str, **kwargs) -> ModelTaskCell:
    return ModelTaskCell(model_id=model_id, task_id=task_id, status=status, label=label, **kwargs)


_CELLS: Dict[tuple[str, str], ModelTaskCell] = {}


def register_model_task_cell(cell: ModelTaskCell) -> None:
    key = (cell.model_id, canonical_task_id(cell.task_id))
    if key in _CELLS:
        raise ModelContractError(f"Model-task cell already registered: {key}")
    _CELLS[key] = cell


# Frozen ground-state cells: these must not change numerically under task-axis refactoring.
register_model_task_cell(_cell(
    "nuclear.reduced_pairing.one_pair", GROUND, "acceptance_verified",
    "Verified one-pair ground-state cell",
    resolved_policy_intent={"controller": "external_variational_energy.v1", "reference": "small_exact_one_pair_sector.v1"},
    reference_validity={"kind": "exact one-pair sector", "declared_scale": "2–6 levels"},
    resource_envelope={"simulator_max_qubits": 6},
    acceptance_suite_id="acceptance.cell.one_pair.ground_state.v1",
    notes=("Regression anchor for the model × task matrix.",),
))
register_model_task_cell(_cell(
    "nuclear.reduced_pairing.multi_pair", GROUND, "experimental",
    "Bathri multi-pair ground-state cell",
    resolved_policy_intent={"controller": "external_variational_energy.v1", "reference": "small_exact_multi_pair_sector.v1"},
    reference_validity={"kind": "small exact fixed-pair sector", "declared_scale": "4–6 levels; 2–3 pairs"},
    resource_envelope={"simulator_max_qubits": 6},
    acceptance_suite_id="acceptance.cell.multi_pair.ground_state.v1",
    notes=("Independent plugin; promotion awaits full acceptance matrix.",),
))
register_model_task_cell(_cell(
    "nuclear.oscillator.hard_core.one_quantum", GROUND, "experimental",
    "Hard-core oscillator ground-state integration cell",
    resolved_policy_intent={"controller": "external_variational_energy.v1", "reference": "small_exact_one_excitation_sector.v1"},
    reference_validity={"kind": "exact one-excitation sector", "scientific_review": "pending module-owner review"},
    resource_envelope={"simulator_max_qubits": 6},
    acceptance_suite_id="acceptance.cell.oscillator.ground_state.v1",
))
# Four independent QHO contracts reuse the same hard-core oscillator policies.
for _qho_id, _qho_label in (
    ("nuclear.qho.free", "Free QHO ground-state cell"),
    ("nuclear.qho.pairing", "Pairing QHO ground-state cell"),
    ("nuclear.qho.spinorbit", "Spin-orbit-shift QHO ground-state cell"),
    ("nuclear.qho.full", "Full QHO ground-state cell"),
):
    register_model_task_cell(_cell(
        _qho_id, GROUND, "experimental", _qho_label,
        resolved_policy_intent={
            "controller": "external_variational_energy.v1",
            "mapping": "direct_hard_core_mode_encoding.v1",
            "state_preparation": "lowest_mode_state.v1",
            "ansatz": "one_excitation_chain_givens.v1",
            "reference": "small_exact_one_excitation_sector.v1",
        },
        reference_validity={
            "kind": "exact one-excitation sector",
            "declared_scale": "2–6 modes; one quantum",
        },
        resource_envelope={"simulator_max_qubits": 6},
        acceptance_suite_id=f"acceptance.cell.{_qho_id}.ground_state.v1",
        notes=(
            "Structurally integrated QHO contract; the shared runtime is unchanged.",
            "Cell remains experimental until its own scientific acceptance evidence is promoted.",
        ),
    ))


register_model_task_cell(_cell(
    "custom.occupation_coupling.one_excitation", GROUND, "execution_ready",
    "Guided custom occupation-model ground-state cell",
    resolved_policy_intent={"controller": "external_variational_energy.v1", "reference": "small_exact_one_excitation_sector.v1"},
    reference_validity={"kind": "exact one-excitation sector", "route": "bounded no-code"},
    resource_envelope={"simulator_max_qubits": 6},
    acceptance_suite_id="acceptance.cell.custom_guided.ground_state.v1",
))
register_model_task_cell(_cell(
    "custom.qubit_hamiltonian", GROUND, "execution_ready",
    "Bounded custom qubit ground-state cell",
    resolved_policy_intent={"controller": "external_variational_energy.v1", "reference": "small_exact_full_space.v1"},
    reference_validity={"kind": "exact full-space while bounded input fits"},
    resource_envelope={"simulator_max_qubits": 6},
    acceptance_suite_id="acceptance.cell.custom_qubit.ground_state.v1",
))

# First verified second column.
register_model_task_cell(_cell(
    "nuclear.reduced_pairing.one_pair", OBS, "acceptance_verified",
    "Verified one-pair pair-occupation observable cell",
    resolved_policy_intent={
        "controller": "single_pass.observable.v1",
        "measurement": "declared_observable_measurement.v1",
        "verification": "observable_error_with_uncertainty.v1",
    },
    reference_validity={
        "kind": "exact-state pair occupations",
        "state_source": "acceptance fixture only for the verified acceptance case",
    },
    resource_envelope={"simulator_max_qubits": 6, "measurement_circuits": 1},
    acceptance_suite_id="acceptance.cell.one_pair.observable.v1",
    notes=("Single-pass controller; no optimizer loop.", "Acceptance fixture is not a VQE result."),
))

# Honest roadmap cells.
for model_id in (
    "nuclear.reduced_pairing.multi_pair",
    "nuclear.oscillator.hard_core.one_quantum",
    "custom.occupation_coupling.one_excitation",
    "custom.qubit_hamiltonian",
):
    register_model_task_cell(_cell(model_id, OBS, "planned", "Observable task planned for this model"))

for model_id in (
    "nuclear.reduced_pairing.one_pair",
    "nuclear.reduced_pairing.multi_pair",
    "nuclear.oscillator.hard_core.one_quantum",
    "custom.occupation_coupling.one_excitation",
    "custom.qubit_hamiltonian",
):
    register_model_task_cell(_cell(model_id, EXCITED, "planned", "Excited-state task registered for future cell-specific acceptance"))
    register_model_task_cell(_cell(model_id, PHASE, "planned", "Eigenphase task registered for future cell-specific acceptance"))

register_model_task_cell(_cell(
    "nuclear.oscillator.hard_core.one_quantum", TIME, "planned",
    "Oscillator time-evolution cell — natural fit, not implemented",
    reference_validity={"kind": "task-specific trajectory reference required"},
))
for model_id in (
    "nuclear.reduced_pairing.one_pair",
    "nuclear.reduced_pairing.multi_pair",
    "custom.occupation_coupling.one_excitation",
    "custom.qubit_hamiltonian",
):
    register_model_task_cell(_cell(model_id, TIME, "planned", "Time-evolution cell registered but unresolved"))



# Phase A.3.1: first verified mapping-analysis cell.
register_model_task_cell(_cell(
    "fermion.general_spin_orbital", MAP_ANALYSIS, "acceptance_verified",
    "Verified JW/BK mapping-analysis cell",
    resolved_policy_intent={
        "controller": "single_pass.mapping_analysis.v1",
        "mappings": "jordan_wigner.v1 + bravyi_kitaev.v1",
        "verification": "mapping_equivalence_and_resources.v1",
    },
    reference_validity={
        "kind": "exact full and fixed-particle Fermionic Fock-space spectra",
        "declared_scale": "2–8 modes",
    },
    resource_envelope={
        "exact_max_modes": 8,
        "backend_required": False,
        "shots_required": False,
    },
    acceptance_suite_id="acceptance.cell.general_spin_orbital.mapping_analysis.v1",
    notes=(
        "JW and BK are verified for transformation and analysis only.",
        "This cell does not verify VQE state preparation or ground-state execution.",
    ),
))
register_model_task_cell(_cell(
    "fermion.general_spin_orbital", GROUND, "acceptance_verified",
    "Acceptance-verified bounded general spin-orbital JW ground-state cell",
    resolved_policy_intent={
        "mapping": "jordan_wigner.v1",
        "state_preparation": "JW occupation determinant",
        "ansatz": "jw_mapped_fermionic_swap_network",
        "ansatz_semantic_class": "mapped_fermionic_generator",
        "composition_status": "acceptance_verified",
        "historical_negative_fixture": "ANSATZ_GENERATOR_MAPPING_MISMATCH",
        "controller": "external_variational_energy.v1",
        "measurement": "model_resolved_energy_measurement.v1",
        "reference": "exact fixed-particle FermionOperator diagonalisation",
        "bravyi_kitaev.v1": "analysis_only_not_executable",
    },
    reference_validity={
        "kind": "exact fixed-particle spin-orbital sector",
        "declared_scale": "2–4 modes; 1 <= N < n_modes",
    },
    resource_envelope={
        "simulator_max_qubits": 4,
        "ansatz_layers": "1–2",
        "maximum_parameter_count": 32,
        "mapping": "jordan_wigner.v1 only",
        "backend": "local simulator",
    },
    acceptance_suite_id="acceptance.cell.general_spin_orbital.jw_ground_state.wp11.v1",
    notes=(
        "WP11 replaces the production bare exchange with exact mapped single-excitation generators routed by FSWAPs.",
        "The WP0 bare-exchange failure remains archived as a permanent negative regression fixture.",
        "Mapper, composition, and cell gates pass at the declared 2–4-mode fixed-particle scale.",
        "BK remains transformation and analysis only.",
    ),
))
for _task_id in (OBS, EXCITED, TIME, PHASE):
    register_model_task_cell(_cell(
        "fermion.general_spin_orbital", _task_id, "planned",
        "General spin-orbital task registered for future cell-specific acceptance",
    ))

def get_model_task_cell(model_id: str, task_id: str) -> ModelTaskCell:
    key = (str(model_id), canonical_task_id(task_id))
    try:
        return _CELLS[key]
    except KeyError as exc:
        raise ModelContractError(f"No model-task cell is registered for {key}.") from exc


def list_model_task_cells() -> Tuple[ModelTaskCell, ...]:
    return tuple(_CELLS[key] for key in sorted(_CELLS))


def public_model_task_matrix() -> Dict[str, Any]:
    from .model_registry import list_model_contracts
    from .task_registry import list_task_contracts

    rows = [contract.model_id for contract in list_model_contracts()]
    columns = [contract.task_id for contract in list_task_contracts()]
    cells = [cell.to_dict() for cell in list_model_task_cells()]
    # WP12 keeps the matrix strictly two-dimensional.  Each cell publishes only
    # a compact realization-variant summary and an endpoint; full internal
    # mapping/state/ansatz/reference records remain inside the selected cell.
    from .realization_variants.public_surface import build_model_task_realization_registry

    variant_registry = build_model_task_realization_registry()
    summaries = {key: view.matrix_summary() for key, view in variant_registry.items()}
    for cell in cells:
        cell["realization_variants"] = summaries[cell["cell_id"]]
    return {
        "schema_version": "qcol-model-task-matrix/1.1",
        "principle": "A runnable feature is one verified model × task cell, not a model or task in isolation.",
        "surface_rule": "The public matrix remains Model × Task; realization variants are internal records inside each cell.",
        "matrix_dimensions": ["model", "task"],
        "rows": rows,
        "columns": columns,
        "cells": cells,
        "realization_variant_catalog_endpoint": "/catalog/model-task-realizations",
    }

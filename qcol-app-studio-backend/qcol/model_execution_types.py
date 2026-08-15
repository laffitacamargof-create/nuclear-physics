"""Typed intermediate results used by model-policy callables."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from .model_contracts import ModelContract, ModelInstance


@dataclass(frozen=True)
class ModelBuildContext:
    contract: ModelContract
    instance: ModelInstance
    request_metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class HamiltonianBuildResult:
    domain_hamiltonian: Any
    representation: str
    parameters: Mapping[str, Any]
    units: Mapping[str, str]
    metadata: Mapping[str, Any] = field(default_factory=dict)
    provenance: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SectorValidationResult:
    target_sector: Mapping[str, Any]
    conserved_quantities: Tuple[str, ...]
    validation_checks: Mapping[str, bool]
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MappingResult:
    qubit_hamiltonian: Any
    n_qubits: int
    mapping_name: str
    encoding: str
    mapping_metadata: Mapping[str, Any]
    orbital_to_qubit_order: Mapping[str, Any]
    preserved_symmetries: Tuple[str, ...]
    crosscheck_payloads: Mapping[str, Any] = field(default_factory=dict)
    validation_checks: Mapping[str, bool] = field(default_factory=dict)


@dataclass(frozen=True)
class StatePreparationResult:
    circuit: Any
    label: str
    occupied_indices: Tuple[int, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AnsatzBuildResult:
    variational_circuit: Any
    parameter_symbols: Tuple[Any, ...]
    initial_parameters: Tuple[float, ...]
    family: str
    parameter_fixture: Optional[Mapping[str, Any]] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ResourceAssessment:
    status: str
    n_qubits: int
    parameter_count: int
    pauli_term_count: int
    measurement_group_count: int
    estimated_sector_dimension: Optional[int]
    within_declared_envelope: bool
    notes: Tuple[str, ...] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "n_qubits": int(self.n_qubits),
            "parameter_count": int(self.parameter_count),
            "pauli_term_count": int(self.pauli_term_count),
            "measurement_group_count": int(self.measurement_group_count),
            "estimated_sector_dimension": self.estimated_sector_dimension,
            "within_declared_envelope": bool(self.within_declared_envelope),
            "notes": list(self.notes),
            "metadata": dict(self.metadata),
        }

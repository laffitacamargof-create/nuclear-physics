"""Mapping-plugin contracts and analysis artifacts."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple


@dataclass(frozen=True)
class MappingCompatibilityReport:
    mapping_id: str
    model_compatible: bool
    task_compatible: bool
    compatible: bool
    checks: Mapping[str, bool]
    reasons: Tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mapping_id": self.mapping_id,
            "model_compatible": self.model_compatible,
            "task_compatible": self.task_compatible,
            "compatible": self.compatible,
            "checks": dict(self.checks),
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class MappingCapabilityReport:
    mapping_id: str
    mapping_version: str
    model_compatible: bool
    transform_available: bool
    transform_verified: bool
    observable_transform_ready: bool
    analysis_ready: bool
    occupation_encoding_ready: bool
    particle_number_observable_ready: bool
    sector_verification_ready: bool
    ground_state_execution_ready: bool
    support_by_task: Mapping[str, str]
    missing_capabilities: Tuple[str, ...]
    overall_status: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mapping_id": self.mapping_id,
            "mapping_version": self.mapping_version,
            "model_compatible": self.model_compatible,
            "transform_available": self.transform_available,
            "transform_verified": self.transform_verified,
            "observable_transform_ready": self.observable_transform_ready,
            "analysis_ready": self.analysis_ready,
            "occupation_encoding_ready": self.occupation_encoding_ready,
            "particle_number_observable_ready": self.particle_number_observable_ready,
            "sector_verification_ready": self.sector_verification_ready,
            "ground_state_execution_ready": self.ground_state_execution_ready,
            "support_by_task": dict(self.support_by_task),
            "missing_capabilities": list(self.missing_capabilities),
            "overall_status": self.overall_status,
        }


@dataclass(frozen=True)
class MappingResourceReport:
    mapping_id: str
    n_modes: int
    n_qubits: int
    pauli_term_count: int
    identity_term_count: int
    minimum_pauli_weight: int
    maximum_pauli_weight: int
    mean_pauli_weight: float
    median_pauli_weight: float
    coefficient_weighted_mean_pauli_weight: float
    coefficient_l1_norm: float
    axis_support_profile: Mapping[str, int]
    qwc_measurement_group_count: int
    transform_seconds: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mapping_id": self.mapping_id,
            "n_modes": self.n_modes,
            "n_qubits": self.n_qubits,
            "pauli_term_count": self.pauli_term_count,
            "identity_term_count": self.identity_term_count,
            "minimum_pauli_weight": self.minimum_pauli_weight,
            "maximum_pauli_weight": self.maximum_pauli_weight,
            "mean_pauli_weight": self.mean_pauli_weight,
            "median_pauli_weight": self.median_pauli_weight,
            "coefficient_weighted_mean_pauli_weight": self.coefficient_weighted_mean_pauli_weight,
            "coefficient_l1_norm": self.coefficient_l1_norm,
            "axis_support_profile": dict(self.axis_support_profile),
            "qwc_measurement_group_count": self.qwc_measurement_group_count,
            "transform_seconds": self.transform_seconds,
        }


@dataclass(frozen=True)
class MappedProblemArtifact:
    mapping_id: str
    mapping_version: str
    qubit_hamiltonian: Any = field(repr=False, compare=False)
    mapped_particle_number_operator: Any = field(repr=False, compare=False)
    n_qubits: int = 0
    mode_to_qubit_order: Mapping[str, Any] = field(default_factory=dict)
    target_sector: Mapping[str, Any] = field(default_factory=dict)
    preserved_symmetries: Tuple[str, ...] = field(default_factory=tuple)
    occupation_encoding: Mapping[str, Any] = field(default_factory=dict)
    resource_report: Optional[MappingResourceReport] = None
    compatibility_report: Optional[MappingCompatibilityReport] = None
    capability_report: Optional[MappingCapabilityReport] = None
    mapping_provenance: Mapping[str, Any] = field(default_factory=dict)

    def to_public_dict(self) -> Dict[str, Any]:
        return {
            "mapping_id": self.mapping_id,
            "mapping_version": self.mapping_version,
            "n_qubits": self.n_qubits,
            "mode_to_qubit_order": dict(self.mode_to_qubit_order),
            "target_sector": dict(self.target_sector),
            "preserved_symmetries": list(self.preserved_symmetries),
            "occupation_encoding": dict(self.occupation_encoding),
            "resource_report": None if self.resource_report is None else self.resource_report.to_dict(),
            "compatibility_report": None if self.compatibility_report is None else self.compatibility_report.to_dict(),
            "capability_report": None if self.capability_report is None else self.capability_report.to_dict(),
            "mapping_provenance": dict(self.mapping_provenance),
            "operator_payload_withheld": True,
        }


@dataclass(frozen=True)
class MappingAnalysisEntry:
    mapping_id: str
    mapped_artifact: MappedProblemArtifact
    full_spectrum_max_abs_error: float
    target_sector_spectrum_max_abs_error: float
    particle_number_spectrum_max_abs_error: float
    hamiltonian_hermitian: bool
    particle_number_commutator_norm: float
    transform_verified: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mapping_id": self.mapping_id,
            "mapped_artifact": self.mapped_artifact.to_public_dict(),
            "full_spectrum_max_abs_error": self.full_spectrum_max_abs_error,
            "target_sector_spectrum_max_abs_error": self.target_sector_spectrum_max_abs_error,
            "particle_number_spectrum_max_abs_error": self.particle_number_spectrum_max_abs_error,
            "hamiltonian_hermitian": self.hamiltonian_hermitian,
            "particle_number_commutator_norm": self.particle_number_commutator_norm,
            "transform_verified": self.transform_verified,
        }


@dataclass(frozen=True)
class MappingComparisonReport:
    model_id: str
    task_id: str
    n_modes: int
    target_particle_number: int
    coefficient_threshold: float
    reference_full_spectrum: Tuple[float, ...]
    reference_target_sector_spectrum: Tuple[float, ...]
    entries: Tuple[MappingAnalysisEntry, ...]
    recommended_for_analysis: Optional[str]
    recommendation_basis: str
    evidence_scope: str = "mapping transformation and operator-resource analysis only"

    @property
    def all_transforms_verified(self) -> bool:
        return bool(self.entries) and all(item.transform_verified for item in self.entries)

    def entry(self, mapping_id: str) -> MappingAnalysisEntry:
        for item in self.entries:
            if item.mapping_id == mapping_id:
                return item
        raise KeyError(mapping_id)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "task_id": self.task_id,
            "n_modes": self.n_modes,
            "target_particle_number": self.target_particle_number,
            "coefficient_threshold": self.coefficient_threshold,
            "reference_full_spectrum": list(self.reference_full_spectrum),
            "reference_target_sector_spectrum": list(self.reference_target_sector_spectrum),
            "entries": [item.to_dict() for item in self.entries],
            "all_transforms_verified": self.all_transforms_verified,
            "recommended_for_analysis": self.recommended_for_analysis,
            "recommendation_basis": self.recommendation_basis,
            "evidence_scope": self.evidence_scope,
        }


class FermionToQubitMappingPlugin(ABC):
    mapping_id: str
    mapping_version: str
    label: str
    support_by_task: Mapping[str, str] = {}
    execution_boundary: str = "not declared"

    def public_descriptor(self) -> Dict[str, Any]:
        return {
            "mapping_id": self.mapping_id,
            "mapping_version": self.mapping_version,
            "label": self.label,
            "support_by_task": dict(self.support_by_task),
            "execution_boundary": self.execution_boundary,
        }

    @abstractmethod
    def check_compatibility(self, spin_instance, *, task_id: str) -> MappingCompatibilityReport:
        raise NotImplementedError

    @abstractmethod
    def transform_hamiltonian(self, fermion_operator, *, n_modes: int):
        raise NotImplementedError

    @abstractmethod
    def transform_observable(self, fermion_operator, *, n_modes: int):
        raise NotImplementedError

    @abstractmethod
    def encode_occupation_state(self, occupations: Sequence[int]) -> Tuple[int, ...]:
        raise NotImplementedError

    @abstractmethod
    def decode_basis_bitstring(self, bitstring: Sequence[int]) -> Tuple[int, ...]:
        raise NotImplementedError

    @abstractmethod
    def occupation_encoding_metadata(self, n_modes: int) -> Mapping[str, Any]:
        """Describe how occupation vectors are represented by qubit basis bits."""
        raise NotImplementedError

    @abstractmethod
    def capability_report(self, spin_instance) -> MappingCapabilityReport:
        raise NotImplementedError

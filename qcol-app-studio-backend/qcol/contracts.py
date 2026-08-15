"""Shared contracts between model builders, the external VQE runtime, UI, and evidence."""
from __future__ import annotations

from dataclasses import dataclass, field, fields as dataclass_fields, is_dataclass
import math
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

import cirq
import numpy as np
from openfermion import QubitOperator

from .config import NUMERIC_TOL
from .measurement import PauliTerm, format_pauli_term, real_coefficient


def json_safe(value: Any) -> Any:
    """Convert project values into deterministic JSON-safe data.

    Runtime-only scientific objects are represented by small provenance stubs
    rather than being passed to ``json.dumps``. Full circuit artifacts remain in
    separately retained OpenQASM 2 files.
    """
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if math.isnan(value):
            return "NaN"
        if math.isinf(value):
            return "Infinity" if value > 0 else "-Infinity"
        return value
    if isinstance(value, np.ndarray):
        return json_safe(value.tolist())
    if isinstance(value, np.generic):
        return json_safe(value.item())
    if isinstance(value, complex):
        if abs(value.imag) <= NUMERIC_TOL:
            return float(value.real)
        return {"real": float(value.real), "imag": float(value.imag)}
    if isinstance(value, cirq.Circuit):
        return {
            "__type__": "cirq.Circuit",
            "withheld": True,
            "reason": "runtime-only object; inspect retained OpenQASM 2 artifacts",
            "moment_count": len(value),
            "operation_count": sum(1 for _ in value.all_operations()),
            "qubits": [str(qubit) for qubit in sorted(value.all_qubits())],
        }
    if isinstance(value, cirq.Qid):
        return str(value)
    if isinstance(value, QubitOperator):
        return {
            "__type__": "openfermion.QubitOperator",
            "withheld": True,
            "reason": "runtime-only operator; inspect ProblemArtifact metadata",
            "term_count": len(value.terms),
        }
    if is_dataclass(value):
        return {field.name: json_safe(getattr(value, field.name)) for field in dataclass_fields(value)}
    if isinstance(value, Mapping):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, set):
        return [json_safe(item) for item in sorted(value, key=str)]
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if value.__class__.__module__.startswith("sympy"):
        return str(value)
    return {
        "__type__": f"{value.__class__.__module__}.{value.__class__.__name__}",
        "withheld": True,
        "reason": "object is not part of the JSON evidence contract",
    }


def serializable_measurement_plan(plan: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "identity_coefficient": float(plan["identity_coefficient"]),
        "groups": [
            {
                "group_id": int(group["group_id"]),
                "basis": {
                    str(index): str(pauli)
                    for index, pauli in sorted(group["basis"].items())
                },
                "terms": [
                    {
                        "term": format_pauli_term(tuple(item["term"])),
                        "coefficient": float(item["coefficient"]),
                    }
                    for item in group["terms"]
                ],
            }
            for group in plan["groups"]
        ],
    }


@dataclass
class ProblemArtifact:
    """The common scientific/software contract returned by every model builder."""

    artifact_id: str
    model_id: str
    method: str
    problem: str
    parameters: Dict[str, Any]
    units: Dict[str, str]
    target_sector: Optional[Dict[str, Any]]
    encoding: str
    mapping: Optional[str]
    n_qubits: int
    qubit_order: str
    symmetries: List[str]
    scientific_context: Dict[str, Any]

    hamiltonian_payload: QubitOperator = field(repr=False)
    ansatz_template: cirq.Circuit = field(repr=False)
    parameter_symbols: Tuple[Any, ...] = field(repr=False)
    initial_parameters: List[float]
    measurement_plan: Dict[str, Any] = field(repr=False)

    parameter_fixture: Optional[Dict[str, Any]] = None
    exact_reference: Optional[Dict[str, Any]] = None
    crosscheck_payloads: Dict[str, Any] = field(default_factory=dict, repr=False)
    validation_checks: Dict[str, bool] = field(default_factory=dict)
    provenance: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if self.n_qubits <= 0:
            raise ValueError("n_qubits must be positive.")
        if not isinstance(self.hamiltonian_payload, QubitOperator):
            raise TypeError("hamiltonian_payload must be an OpenFermion QubitOperator.")
        if not isinstance(self.ansatz_template, cirq.Circuit):
            raise TypeError("ansatz_template must be a Cirq Circuit.")
        if len(self.parameter_symbols) != len(self.initial_parameters):
            raise ValueError("Parameter symbols and initial values differ in length.")

        declared_names = {str(symbol) for symbol in self.parameter_symbols}
        circuit_names = set(cirq.parameter_names(self.ansatz_template))
        if circuit_names != declared_names:
            raise ValueError(
                "The declared parameter schema does not match the symbolic circuit: "
                f"declared={sorted(declared_names)}, circuit={sorted(circuit_names)}"
            )

        expected_qubits = set(cirq.LineQubit.range(self.n_qubits))
        unexpected_qubits = set(self.ansatz_template.all_qubits()) - expected_qubits
        if unexpected_qubits:
            raise ValueError(f"Ansatz contains undeclared qubits: {unexpected_qubits}")

        expected_identity = 0.0
        expected_terms: Dict[PauliTerm, float] = {}
        for term, coefficient in self.hamiltonian_payload.terms.items():
            real_value = real_coefficient(coefficient)
            if not term:
                expected_identity += real_value
                continue
            for qubit_index, pauli in term:
                if not 0 <= int(qubit_index) < self.n_qubits:
                    raise ValueError(
                        f"Hamiltonian term {term} uses qubit {qubit_index} "
                        f"outside [0, {self.n_qubits - 1}]."
                    )
                if pauli not in {"X", "Y", "Z"}:
                    raise ValueError(f"Unsupported Pauli label {pauli!r}.")
            expected_terms[tuple(term)] = real_value

        observed_identity = float(self.measurement_plan.get("identity_coefficient", 0.0))
        if not math.isclose(
            observed_identity, expected_identity, rel_tol=0.0, abs_tol=1e-10
        ):
            raise ValueError(
                "Measurement identity coefficient mismatch: "
                f"{observed_identity} vs {expected_identity}"
            )

        observed_terms: Dict[PauliTerm, float] = {}
        observed_group_ids: set[int] = set()
        for group in self.measurement_plan.get("groups", []):
            group_id = int(group["group_id"])
            if group_id in observed_group_ids:
                raise ValueError(f"Duplicate measurement group_id: {group_id}")
            observed_group_ids.add(group_id)
            basis = {int(index): str(pauli) for index, pauli in group["basis"].items()}
            for item in group["terms"]:
                term = tuple((int(index), str(pauli)) for index, pauli in item["term"])
                if term in observed_terms:
                    raise ValueError(f"Measurement term appears more than once: {term}")
                if any(basis.get(index) != pauli for index, pauli in term):
                    raise ValueError(
                        f"Measurement basis {basis} does not implement term {term}."
                    )
                observed_terms[term] = float(item["coefficient"])

        if set(observed_terms) != set(expected_terms):
            missing = set(expected_terms) - set(observed_terms)
            extra = set(observed_terms) - set(expected_terms)
            raise ValueError(f"Measurement-plan mismatch. missing={missing}, extra={extra}")
        for term, expected_coefficient in expected_terms.items():
            if not math.isclose(
                observed_terms[term], expected_coefficient, rel_tol=0.0, abs_tol=1e-10
            ):
                raise ValueError(
                    f"Measurement coefficient mismatch for {term}: "
                    f"{observed_terms[term]} vs {expected_coefficient}"
                )

        for label, values in (
            ("initial_parameters", self.initial_parameters),
            (
                "parameter_fixture",
                [] if self.parameter_fixture is None else self.parameter_fixture.get("values", []),
            ),
        ):
            if values and len(values) != len(self.parameter_symbols):
                raise ValueError(f"{label} does not match the parameter schema.")
            if values and not np.all(np.isfinite(np.asarray(values, dtype=float))):
                raise ValueError(f"{label} contains non-finite values.")

        if self.exact_reference is not None:
            reference_energy = float(self.exact_reference["reference_energy"])
            if not math.isfinite(reference_energy):
                raise ValueError("The classical reference energy is not finite.")

        failed_checks = [
            name for name, passed in self.validation_checks.items() if not bool(passed)
        ]
        if failed_checks:
            raise ValueError(f"Builder validation checks failed: {failed_checks}")

    def metadata(self) -> Dict[str, Any]:
        return json_safe({
            "artifact_id": self.artifact_id,
            "model_id": self.model_id,
            "method": self.method,
            "problem": self.problem,
            "parameters": self.parameters,
            "units": self.units,
            "target_sector": self.target_sector,
            "encoding": self.encoding,
            "mapping": self.mapping,
            "n_qubits": self.n_qubits,
            "qubit_order": self.qubit_order,
            "symmetries": self.symmetries,
            "scientific_context": self.scientific_context,
            "parameter_names": [str(symbol) for symbol in self.parameter_symbols],
            "initial_parameters": self.initial_parameters,
            "parameter_fixture": self.parameter_fixture,
            "measurement_plan": serializable_measurement_plan(self.measurement_plan),
            "exact_reference": self.exact_reference,
            "validation_checks": self.validation_checks,
            "provenance": self.provenance,
        })


@dataclass
class RunResult:
    """One complete single-evaluation or external-VQE run."""

    run_id: str
    artifact_id: str
    method: str
    problem: str
    status: str
    run_mode: str
    execution_mode: str
    target_backend: str
    adapter_status: str
    hardware_submission_performed: bool
    shots_per_group: int
    seed: int

    optimizer_name: Optional[str]
    optimizer_converged: bool
    optimizer_message: str
    optimizer_evaluations: int
    optimizer_tolerance: float
    parameter_source: str
    optimizer_diagnostics: Dict[str, Any]
    initial_parameters: List[float]
    final_parameters: List[float]
    convergence_history: List[Dict[str, Any]]

    request_summary: Dict[str, Any]
    translation_check: Dict[str, Any]
    raw_records: List[Dict[str, Any]]
    term_expectations: Dict[str, float]
    reconstructed_energy: Optional[float]
    standard_error: Optional[float]

    verification: Dict[str, Any]
    meaning: Dict[str, Any]
    environment: Dict[str, str]
    timestamps: Dict[str, str]
    journey_events: List[Dict[str, Any]] = field(default_factory=list)
    reference_policy: str = "mentor_decision_pending"
    task_id: str = "ground_state_energy"
    controller_id: Optional[str] = None
    model_task_cell_id: Optional[str] = None
    task_result: Dict[str, Any] = field(default_factory=dict)
    task_verification: Dict[str, Any] = field(default_factory=dict)
    task_meaning: Dict[str, Any] = field(default_factory=dict)
    model_task_plan: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self, *, include_artifacts: bool = True) -> Dict[str, Any]:
        # Normalize frozen MappingProxyType/dataclass payloads before any mutation.
        # copy.deepcopy(mappingproxy) raises ``cannot pickle 'mappingproxy' object``.
        records = json_safe(self.raw_records)
        translation = json_safe(self.translation_check)
        if not isinstance(records, list):
            records = []
        if not isinstance(translation, dict):
            translation = {}
        if not include_artifacts:
            for record in records:
                record.pop("raw_qasm2", None)
                record.pop("unrolled_qasm2", None)
            translation.pop("raw_qasm2", None)
            translation.pop("unrolled_qasm2", None)
        return json_safe({
            "run_id": self.run_id,
            "artifact_id": self.artifact_id,
            "method": self.method,
            "problem": self.problem,
            "status": self.status,
            "run_mode": self.run_mode,
            "execution_mode": self.execution_mode,
            "target_backend": self.target_backend,
            "adapter_status": self.adapter_status,
            "hardware_submission_performed": self.hardware_submission_performed,
            "shots_per_group": self.shots_per_group,
            "seed": self.seed,
            "optimizer_name": self.optimizer_name,
            "optimizer_converged": self.optimizer_converged,
            "optimizer_message": self.optimizer_message,
            "optimizer_evaluations": self.optimizer_evaluations,
            "optimizer_tolerance": self.optimizer_tolerance,
            "parameter_source": self.parameter_source,
            "optimizer_diagnostics": self.optimizer_diagnostics,
            "initial_parameters": self.initial_parameters,
            "final_parameters": self.final_parameters,
            "convergence_history": self.convergence_history,
            "request_summary": self.request_summary,
            "translation_check": translation,
            "raw_records": records,
            "term_expectations": self.term_expectations,
            "reconstructed_energy": self.reconstructed_energy,
            "standard_error": self.standard_error,
            "verification": self.verification,
            "meaning": self.meaning,
            "environment": self.environment,
            "timestamps": self.timestamps,
            "journey_events": self.journey_events,
            "reference_policy": self.reference_policy,
            "task_id": self.task_id,
            "controller_id": self.controller_id,
            "model_task_cell_id": self.model_task_cell_id,
            "task_result": self.task_result,
            "task_verification": self.task_verification,
            "task_meaning": self.task_meaning,
            "model_task_plan": self.model_task_plan,
        })

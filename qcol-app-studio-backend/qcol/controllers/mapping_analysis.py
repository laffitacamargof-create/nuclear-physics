"""Single-pass controller for the Phase A.3.1 Mapping Explorer."""
from __future__ import annotations

from typing import Any

from .base import ControllerOutcome
from ..events import PipelineEvent
from ..mappings import analyze_mappings


def _emit(callback, **kwargs) -> None:
    if callback is not None:
        callback(PipelineEvent(**kwargs))


def _qubit_operator_terms(operator) -> list[dict[str, Any]]:
    terms = []
    for pauli_term, coefficient in sorted(
        operator.terms.items(), key=lambda item: (len(item[0]), str(item[0]))
    ):
        label = "I" if not pauli_term else " ".join(
            f"{axis}{index}" for index, axis in pauli_term
        )
        value = complex(coefficient)
        terms.append({
            "pauli_string": label,
            "coefficient": {"real": float(value.real), "imag": float(value.imag)},
            "pauli_weight": len(pauli_term),
        })
    return terms


def run_mapping_analysis_controller(
    realization,
    *,
    run_id: str,
    event_callback=None,
    cancellation_token=None,
) -> ControllerOutcome:
    def check(location: str) -> None:
        if cancellation_token is not None:
            cancellation_token.raise_if_cancelled(location=location)

    artifact = realization.problem_artifact
    task_plan = realization.task_plan
    task_parameters = dict(realization.task_instance.parameters)
    mapping_ids = tuple(task_parameters.get("mapping_ids") or (
        "jordan_wigner.v1",
        "bravyi_kitaev.v1",
    ))
    coefficient_threshold = float(task_parameters.get("coefficient_threshold", 1e-12))
    equivalence_tolerance = float(task_parameters.get("equivalence_tolerance", 1e-8))

    payloads = artifact.crosscheck_payloads
    spin_instance = payloads.get("spin_orbital_instance")
    fermion_operator = payloads.get("fermion_operator")
    number_operator = payloads.get("particle_number_operator")
    if spin_instance is None or fermion_operator is None or number_operator is None:
        raise ValueError(
            "Mapping analysis requires a SpinOrbitalInstance, FermionOperator, and "
            "particle-number operator in the resolved artifact."
        )

    _emit(
        event_callback,
        run_id=run_id,
        stage="mapping_analysis",
        status="running",
        message="Transforming the same FermionOperator with eligible mapping plugins.",
        metrics={
            "mapping_ids": list(mapping_ids),
            "n_modes": spin_instance.n_modes,
            "target_particle_number": spin_instance.total_target_particles,
        },
        artifact_refs=["fermion_operator", "mapping_plugins"],
    )
    check("before_mapping_analysis")
    report = analyze_mappings(
        model_id=artifact.model_id,
        spin_instance=spin_instance,
        fermion_operator=fermion_operator,
        particle_number_operator=number_operator,
        mapping_ids=mapping_ids,
        coefficient_threshold=coefficient_threshold,
        equivalence_tolerance=equivalence_tolerance,
    )
    check("after_mapping_analysis")

    public_report = report.to_dict()
    compact_resources = {
        entry.mapping_id: entry.mapped_artifact.resource_report.to_dict()
        for entry in report.entries
    }
    capability_reports = {
        entry.mapping_id: entry.mapped_artifact.capability_report.to_dict()
        for entry in report.entries
    }
    _emit(
        event_callback,
        run_id=run_id,
        stage="mapping_analysis",
        status="completed" if report.all_transforms_verified else "review",
        message=(
            "JW and BK transformations passed the declared analysis acceptance checks."
            if report.all_transforms_verified
            else "At least one mapping transformation requires review."
        ),
        metrics={
            "all_transforms_verified": report.all_transforms_verified,
            "recommended_for_analysis": report.recommended_for_analysis,
            "resource_reports": compact_resources,
            "capability_reports": capability_reports,
        },
        artifact_refs=["mapping_comparison_report", "mapped_problem_artifacts"],
    )
    _emit(
        event_callback,
        run_id=run_id,
        stage="evidence",
        status="completed",
        message="Preserved the input contract, mapped operators, capability reports, and resource metrics.",
        metrics={"mapping_count": len(report.entries), "backend_execution": False},
        artifact_refs=["mapping_analysis_evidence"],
    )
    _emit(
        event_callback,
        run_id=run_id,
        stage="reconstruct",
        status="completed",
        message="Reconstructed a comparable mapping-resource and semantic-equivalence report.",
        metrics={
            "result_kind": "mapping_comparison",
            "all_transforms_verified": report.all_transforms_verified,
        },
        artifact_refs=["mapping_comparison_report"],
    )

    records = []
    for entry in report.entries:
        records.append({
            "mapping_id": entry.mapping_id,
            "transform_verified": entry.transform_verified,
            "full_spectrum_max_abs_error": entry.full_spectrum_max_abs_error,
            "target_sector_spectrum_max_abs_error": entry.target_sector_spectrum_max_abs_error,
            "particle_number_spectrum_max_abs_error": entry.particle_number_spectrum_max_abs_error,
            "resource_report": entry.mapped_artifact.resource_report.to_dict(),
            "capability_report": entry.mapped_artifact.capability_report.to_dict(),
            "mapping_provenance": dict(entry.mapped_artifact.mapping_provenance),
            # Retained only in the private evidence payload. Public API views
            # compact raw_records and expose the report/capability metadata.
            "qubit_hamiltonian_terms": _qubit_operator_terms(
                entry.mapped_artifact.qubit_hamiltonian
            ),
            "mapped_particle_number_terms": _qubit_operator_terms(
                entry.mapped_artifact.mapped_particle_number_operator
            ),
        })
    final_execution = {
        "translation_check": {
            "passed": bool(report.all_transforms_verified),
            "applicable": True,
            "kind": "fermion_to_qubit_mapping_equivalence",
            "qasm_applicable": False,
            "reason": "mapping_analysis verifies operator transforms without circuit execution",
            "mapping_checks": records,
        },
        "records": records,
        "term_expectations": {},
        "energy": None,
        "standard_error": None,
        "shots_per_group": 0,
    }
    return ControllerOutcome(
        controller_id=realization.controller_id,
        task_id=realization.task_id,
        run_mode="mapping_analysis",
        final_execution=final_execution,
        task_result=public_report,
        parameter_source="declared_spin_orbital_contract",
        initial_parameters=[],
        final_parameters=[],
        history=[{
            "evaluation": 1,
            "role": "mapping_analysis",
            "mapping_ids": list(mapping_ids),
            "all_transforms_verified": report.all_transforms_verified,
        }],
        controller_converged=True,
        controller_message="Mapping analysis completed in one deterministic pass.",
        controller_evaluations=1,
        controller_tolerance=equivalence_tolerance,
        controller_name=None,
        controller_diagnostics={
            "optimizer_applicable": False,
            "backend_execution_applicable": False,
            "shots_applicable": False,
            "qasm_execution_applicable": False,
            "evidence_scope": report.evidence_scope,
        },
    )

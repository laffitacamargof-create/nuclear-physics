"""Public, epistemically labelled views for the QCOL dashboard.

This module never imports Cirq/OpenFermion and never changes scientific results.
It decomposes the already-produced public RunResult into honest UI judgments and
source labels so the web client cannot accidentally present one broad PASS as
optimizer convergence, physical-state fidelity, and scientific acceptance.
"""
from __future__ import annotations

from dataclasses import fields as dataclass_fields, is_dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from .public_contract_views import scientific_realization_view


def _public_json_safe(value: Any) -> Any:
    """Clone already-public values without importing the scientific stack."""
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return _public_json_safe(value.to_dict())
    if is_dataclass(value):
        return {field.name: _public_json_safe(getattr(value, field.name)) for field in dataclass_fields(value)}
    if isinstance(value, Mapping):
        return {str(key): _public_json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_public_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


QASM_STRUCTURAL_KEYS = (
    "measurement_free_qasm_validated",
    "measurement_free_semantic_check",
    "all_qasm_groups_validated",
    "all_final_measurement_semantic_checks",
)


def _finite_number(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


def _judgment(status: str, label: str, detail: str, source: str) -> Dict[str, str]:
    return {
        "status": status,
        "label": label,
        "detail": detail,
        "source": source,
    }


def qasm_semantic_fidelity_from_public_result(result: Mapping[str, Any]) -> Optional[float]:
    check = result.get("translation_check")
    if not isinstance(check, Mapping):
        return None
    for branch in ("unrolled_roundtrip", "raw_roundtrip", "semantic_check"):
        item = check.get(branch)
        if not isinstance(item, Mapping):
            continue
        value = _finite_number(item.get("unitary_process_fidelity_up_to_global_phase"))
        if value is not None:
            return value
    measurement_free = check.get("measurement_free")
    if isinstance(measurement_free, Mapping):
        for branch in ("unrolled_roundtrip", "raw_roundtrip"):
            item = measurement_free.get(branch)
            if not isinstance(item, Mapping):
                continue
            value = _finite_number(item.get("unitary_process_fidelity_up_to_global_phase"))
            if value is not None:
                return value
    return None


def build_verification_judgments(result: Optional[Mapping[str, Any]]) -> Dict[str, Dict[str, str]]:
    if not result:
        waiting = _judgment("WAITING", "Waiting", "No completed RunResult is available.", "RunRecord.status")
        return {
            "pipeline_integrity": waiting,
            "qasm_semantic_preservation": waiting,
            "statistical_consistency": waiting,
            "optimizer_convergence": waiting,
            "scientific_acceptance": waiting,
        }

    task_id = str(result.get("task_id", "ground_state_energy"))
    verification = result.get("verification")
    verification = verification if isinstance(verification, Mapping) else {}
    structural = verification.get("structural_checks")
    structural = structural if isinstance(structural, Mapping) else {}

    structural_values = [bool(value) for value in structural.values()]
    if structural_values:
        pipeline_pass = all(structural_values)
        pipeline = _judgment(
            "PASS" if pipeline_pass else "FAIL",
            "Pipeline integrity",
            "All declared artifact, measurement, and execution-contract checks passed."
            if pipeline_pass
            else "At least one structural or interface-contract check failed.",
            "RunResult.verification.structural_checks",
        )
    else:
        pipeline = _judgment(
            "REVIEW",
            "Pipeline integrity",
            "No structural-check map was published for this result.",
            "RunResult.verification.structural_checks",
        )

    qasm_present = [key for key in QASM_STRUCTURAL_KEYS if key in structural]
    if task_id == "mapping_analysis":
        qasm = _judgment(
            "NOT_APPLICABLE",
            "QASM semantic preservation",
            "Mapping analysis verifies operator transformations directly; no circuit or OpenQASM 2 artifact is constructed.",
            "RunResult.translation_check.qasm_applicable",
        )
    elif qasm_present:
        qasm_pass = all(bool(structural[key]) for key in qasm_present)
        qasm = _judgment(
            "PASS" if qasm_pass else "FAIL",
            "QASM semantic preservation",
            "OpenQASM 2 / PyQASM validation and semantic round-trip checks passed."
            if qasm_pass
            else "One or more QASM validation or semantic-preservation checks failed.",
            "RunResult.verification.structural_checks",
        )
    else:
        qasm = _judgment(
            "REVIEW",
            "QASM semantic preservation",
            "QASM-specific checks were not available in the public result.",
            "RunResult.translation_check",
        )

    if task_id == "mapping_analysis":
        accepted = bool(verification.get("accepted", verification.get("all_transforms_verified", False)))
        statistical = _judgment(
            "PASS" if accepted else "REVIEW",
            "Mapping equivalence",
            (
                "JW and BK preserve the declared full-space, fixed-particle-sector, and particle-number spectra within tolerance."
                if accepted else
                "One or more transformation, sector, Hermiticity, or particle-number checks require review."
            ),
            "RunResult.task_verification",
        )
        reference = 1.0 if verification.get("all_transforms_verified") is not None else None
    elif task_id == "observable_estimation":
        max_error = _finite_number(verification.get("maximum_absolute_error"))
        accepted = bool(verification.get("accepted", False))
        statistical = _judgment(
            "PASS" if accepted else "REVIEW",
            "Observable consistency",
            (
                f"Measured observables satisfy the declared uncertainty thresholds; max error={max_error:.6g}."
                if accepted and max_error is not None
                else "One or more observable or sector-leakage checks require review."
            ),
            "RunResult.task_verification",
        )
        reference = 1.0 if verification.get("reference_occupations") is not None else None
    else:
        reference = _finite_number(verification.get("reference_energy"))
        absolute_error = _finite_number(verification.get("absolute_error"))
        threshold = _finite_number(verification.get("acceptance_threshold"))
        if reference is None:
            statistical = _judgment(
                "NOT_RUN",
                "Statistical consistency",
                "No exact/sector reference was declared; exact-comparison consistency was not run.",
                "ProblemArtifact.exact_reference",
            )
        elif absolute_error is not None and threshold is not None:
            consistent = absolute_error <= threshold
            statistical = _judgment(
                "PASS" if consistent else "REVIEW",
                "Statistical consistency",
                (
                    f"|E − E_ref| = {absolute_error:.6g} is within the declared threshold {threshold:.6g}."
                    if consistent
                    else f"|E − E_ref| = {absolute_error:.6g} exceeds the declared threshold {threshold:.6g}."
                ),
                "RunResult.verification.absolute_error / acceptance_threshold",
            )
        else:
            statistical = _judgment(
                "REVIEW",
                "Statistical consistency",
                "Reference information exists, but the public error/threshold pair is incomplete.",
                "RunResult.verification",
            )

    run_mode = str(result.get("run_mode", ""))
    if run_mode in {"single_evaluation", "observable_single_pass", "mapping_analysis"}:
        optimizer = _judgment(
            "NOT_APPLICABLE",
            "Optimizer convergence",
            ("Mapping analysis is deterministic and has no optimizer." if run_mode == "mapping_analysis" else ("This was a single-pass observable task; no optimizer is part of this TaskContract." if run_mode == "observable_single_pass" else "This was one validated θ evaluation, not an optimizer-convergence claim.")),
            "RunResult.run_mode",
        )
    else:
        converged = bool(result.get("optimizer_converged", False))
        optimizer = _judgment(
            "PASS" if converged else "REVIEW",
            "Optimizer convergence",
            "The external optimizer reported convergence."
            if converged
            else "The external optimizer stopped without satisfying its convergence flag.",
            "RunResult.optimizer_converged",
        )

    core_status = str(result.get("status", verification.get("status", "REVIEW"))).upper()
    scientific_pass = (
        core_status == "PASS"
        and pipeline.get("status") == "PASS"
        and qasm.get("status") in {"PASS", "NOT_APPLICABLE"}
        and statistical.get("status") == "PASS"
        and optimizer.get("status") in {"PASS", "NOT_APPLICABLE"}
    )
    if reference is None:
        scientific_status = "LIMITED"
        scientific_detail = (
            "The pipeline produced a bounded result, but exact-reference scientific acceptance is limited."
        )
    elif scientific_pass:
        scientific_status = "PASS"
        scientific_detail = (
            "The result passed structural, task-reference/equivalence, and all applicable QASM and controller checks."
        )
    else:
        scientific_status = "REVIEW"
        scientific_detail = (
            "The result is not promoted to full scientific PASS because one or more distinct judgments remain under review."
        )
    scientific = _judgment(
        scientific_status,
        "Scientific acceptance",
        scientific_detail,
        "Derived UI judgment from verified RunResult fields",
    )

    return {
        "pipeline_integrity": pipeline,
        "qasm_semantic_preservation": qasm,
        "statistical_consistency": statistical,
        "optimizer_convergence": optimizer,
        "scientific_acceptance": scientific,
    }


def build_source_ledger(
    *,
    run_id: str,
    artifact: Optional[Mapping[str, Any]],
    result: Optional[Mapping[str, Any]],
) -> list[Dict[str, Any]]:
    rows: list[Dict[str, Any]] = []
    if result:
        task_id = str(result.get("task_id", "ground_state_energy"))
        if task_id == "mapping_analysis":
            task_result = result.get("task_result")
            if isinstance(task_result, Mapping):
                rows.append({
                    "key": "mapping_comparison_report",
                    "label": "JW / BK MappingComparisonReport",
                    "classification": "DERIVED + VERIFIED",
                    "run_id": run_id,
                    "source": "RunResult.task_result",
                    "value": {
                        "all_transforms_verified": task_result.get("all_transforms_verified"),
                        "recommended_for_analysis": task_result.get("recommended_for_analysis"),
                        "evidence_scope": task_result.get("evidence_scope"),
                    },
                })
                for item in task_result.get("entries", []):
                    mapped = item.get("mapped_artifact", {}) if isinstance(item, Mapping) else {}
                    rows.append({
                        "key": f"mapping_resource:{item.get('mapping_id')}",
                        "label": f"Mapping resources — {item.get('mapping_id')}",
                        "classification": "DERIVED",
                        "run_id": run_id,
                        "source": "RunResult.task_result.entries[].mapped_artifact.resource_report",
                        "value": mapped.get("resource_report"),
                    })
                    rows.append({
                        "key": f"mapping_capability:{item.get('mapping_id')}",
                        "label": f"Mapping capability — {item.get('mapping_id')}",
                        "classification": "DECLARED + VERIFIED",
                        "run_id": run_id,
                        "source": "RunResult.task_result.entries[].mapped_artifact.capability_report",
                        "value": mapped.get("capability_report"),
                    })
        if result.get("reconstructed_energy") is not None:
            rows.append({
                "key": "reconstructed_energy",
                "label": "Reconstructed energy",
                "classification": "DERIVED",
                "run_id": run_id,
                "source": "RunResult.reconstructed_energy",
                "value": result.get("reconstructed_energy"),
            })
        if result.get("standard_error") is not None:
            rows.append({
                "key": "standard_error",
                "label": "Shot standard error",
                "classification": "DERIVED",
                "run_id": run_id,
                "source": "RunResult.standard_error",
                "value": result.get("standard_error"),
            })
        rows.append({
            "key": "counts",
            "label": "Measurement counts",
            "classification": "MEASURED",
            "run_id": run_id,
            "source": "RunResult.raw_records (evidence ZIP)",
            "value": result.get("payload_summary", {}).get("measurement_record_count")
            if isinstance(result.get("payload_summary"), Mapping)
            else None,
        })
        verification = result.get("verification")
        if isinstance(verification, Mapping) and task_id != "observable_estimation":
            rows.extend([
                {
                    "key": "reference_energy",
                    "label": "Exact/sector reference",
                    "classification": "REFERENCE — CLASSICAL",
                    "run_id": run_id,
                    "source": "ProblemArtifact.exact_reference.reference_energy",
                    "value": verification.get("reference_energy"),
                },
                {
                    "key": "absolute_error",
                    "label": "Absolute energy error",
                    "classification": "DERIVED",
                    "run_id": run_id,
                    "source": "RunResult.verification.absolute_error",
                    "value": verification.get("absolute_error"),
                },
            ])
        task_result = result.get("task_result")
        if isinstance(task_result, Mapping) and task_result.get("result_kind") == "pair_occupations":
            rows.extend([
                {
                    "key": "pair_occupations",
                    "label": "Pair occupations",
                    "classification": "MEASURED / DERIVED",
                    "run_id": run_id,
                    "source": "RunResult.task_result.occupations",
                    "value": task_result.get("occupations"),
                },
                {
                    "key": "reference_pair_occupations",
                    "label": "Pair occupations reference",
                    "classification": "REFERENCE — CLASSICAL",
                    "run_id": run_id,
                    "source": "RunResult.task_result.reference_occupations",
                    "value": task_result.get("reference_occupations"),
                },
                {
                    "key": "sector_leakage",
                    "label": "Sector leakage",
                    "classification": "DERIVED",
                    "run_id": run_id,
                    "source": "RunResult.task_result.sector_leakage",
                    "value": task_result.get("sector_leakage"),
                },
            ])
        qasm_fidelity = qasm_semantic_fidelity_from_public_result(result)
        rows.append({
            "key": "qasm_semantic_fidelity",
            "label": "QASM semantic fidelity",
            "classification": "VERIFIED",
            "run_id": run_id,
            "source": "RunResult.translation_check semantic round trip",
            "value": qasm_fidelity,
            "note": "Translation fidelity; not physical-state fidelity.",
        })
    if artifact:
        rows.append({
            "key": "problem_artifact",
            "label": "Shared computational contract",
            "classification": "DECLARED",
            "run_id": run_id,
            "source": "ProblemArtifact.metadata",
            "value": artifact.get("artifact_id"),
        })
        scientific_context = artifact.get("scientific_context")
        problem_contract = (
            scientific_context.get("problem_contract")
            if isinstance(scientific_context, Mapping)
            else None
        )
        if isinstance(problem_contract, Mapping):
            rows.append({
                "key": "fermion_entry_contract",
                "label": "Legacy fermion entry contract",
                "classification": "ENTRY / PROVENANCE",
                "run_id": run_id,
                "source": "ProblemArtifact.scientific_context.problem_contract",
                "value": {
                    "problem_id": problem_contract.get("problem_id"),
                    "schema_version": problem_contract.get("schema_version"),
                    "support_status": problem_contract.get("support_status"),
                },
                "note": "Entry metadata is not scientific authority after resolution.",
            })
        try:
            view = scientific_realization_view(artifact).to_dict()
        except (TypeError, ValueError, KeyError):
            view = None
        if view is not None:
            rows.append({
                "key": "scientific_realization",
                "label": "Canonical scientific realization",
                "classification": "RESOLVED / PUBLIC CONTRACT",
                "run_id": run_id,
                "source": "ScientificRealizationView v1",
                "value": view,
            })
    return rows


def build_active_realization_view(
    *,
    artifact: Optional[Mapping[str, Any]],
    result: Optional[Mapping[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Return the WP12 cell/variant identity for a completed or in-progress run.

    The UI receives a compact public record only; no callable or scientific
    object crosses the service boundary.
    """
    if not artifact and not result:
        return None
    model_id = None
    task_id = None
    if isinstance(artifact, Mapping):
        try:
            scientific = scientific_realization_view(artifact)
        except (TypeError, ValueError, KeyError):
            scientific = None
        if scientific is not None:
            model_id = scientific.model_id
            task_id = scientific.task_id
    if not task_id and isinstance(result, Mapping):
        task_id = result.get("task_id")
    if not model_id or not task_id:
        return None
    try:
        from qcol.realization_variants import get_model_task_realization_view
        view = get_model_task_realization_view(str(model_id), str(task_id))
    except (KeyError, ImportError):
        return None
    payload = view.to_dict()
    if str(task_id) == "mapping_analysis":
        active = [item for item in payload["variants"] if item["runnable"]]
    else:
        active = [
            item for item in payload["variants"]
            if item["variant_id"] == payload.get("default_variant_id")
        ]
    return {
        "cell_id": payload["cell_id"],
        "model_id": str(model_id),
        "task_id": str(task_id),
        "cell_status": payload["cell_status"],
        "default_variant_id": payload.get("default_variant_id"),
        "active_variant_ids": [item["variant_id"] for item in active],
        "active_variants": active,
        "variants_endpoint": payload["variants_endpoint"],
    }


def build_dashboard_view(
    *,
    run_id: str,
    status: str,
    artifact: Optional[Mapping[str, Any]],
    result: Optional[Mapping[str, Any]],
    journey_state: Optional[Mapping[str, Any]],
    evidence_available: bool,
) -> Dict[str, Any]:
    result_copy = _public_json_safe(result) if isinstance(result, Mapping) else None
    artifact_copy = _public_json_safe(artifact) if isinstance(artifact, Mapping) else None
    judgments = build_verification_judgments(result_copy)
    ledger = build_source_ledger(run_id=run_id, artifact=artifact_copy, result=result_copy)
    try:
        scientific = (
            scientific_realization_view(artifact_copy).to_dict()
            if isinstance(artifact_copy, Mapping) else None
        )
    except (TypeError, ValueError, KeyError):
        scientific = None
    return {
        "run_id": run_id,
        "lifecycle_status": status,
        "epistemic_status": judgments,
        "source_ledger": ledger,
        "scientific_realization": scientific,
        "qasm_semantic_fidelity": (
            qasm_semantic_fidelity_from_public_result(result_copy)
            if result_copy
            else None
        ),
        "feedback": {
            "enabled": True,
            "status": "POST_RUN",
            "label": "Deterministic feedback and user-approved Try / Compare",
            "classification": "GOVERNED / EVIDENCE-BOUND",
        },
        "evidence_available": bool(evidence_available),
        "realization": build_active_realization_view(
            artifact=artifact_copy,
            result=result_copy,
        ),
        "journey_completed": bool(
            isinstance(journey_state, Mapping) and journey_state.get("completed")
        ),
    }

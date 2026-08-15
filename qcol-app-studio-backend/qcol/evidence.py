"""Evidence persistence for the interactive QCOL journey."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
from typing import Any, Mapping, Tuple

from .contracts import ProblemArtifact, RunResult, json_safe, serializable_measurement_plan


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(json_safe(payload), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _write_full_execution_artifacts(
    destination: Path,
    *,
    translation_check: Mapping[str, object],
    records: list[dict],
) -> None:
    """Write one full retained execution point (best/final)."""
    (destination / "qasm2_raw").mkdir(parents=True, exist_ok=True)
    (destination / "qasm2_unrolled").mkdir(parents=True, exist_ok=True)
    (destination / "counts").mkdir(parents=True, exist_ok=True)

    (destination / "bound_ansatz_raw.qasm").write_text(
        str(translation_check.get("raw_qasm2", "")), encoding="utf-8"
    )
    (destination / "bound_ansatz_unrolled.qasm").write_text(
        str(translation_check.get("unrolled_qasm2", "")), encoding="utf-8"
    )

    for record in records:
        raw_group_id = record.get("group_id", "unknown")
        safe_group_id = "".join(
            ch if str(ch).isalnum() or ch in {"-", "_"} else "_"
            for ch in str(raw_group_id)
        ) or "unknown"
        if "raw_qasm2" in record:
            (destination / "qasm2_raw" / f"group_{safe_group_id}.qasm").write_text(
                str(record["raw_qasm2"]), encoding="utf-8"
            )
        if "unrolled_qasm2" in record:
            (destination / "qasm2_unrolled" / f"group_{safe_group_id}.qasm").write_text(
                str(record["unrolled_qasm2"]), encoding="utf-8"
            )
        if "counts" in record:
            _write_json(destination / "counts" / f"group_{safe_group_id}.json", record["counts"])


def save_pipeline_evidence(
    artifact: ProblemArtifact,
    result: RunResult,
    root: Path | str = "qcol_phase_a_evidence",
    *,
    advisor_context: Mapping[str, Any] | None = None,
    advisor_report: Mapping[str, Any] | None = None,
) -> Path:
    """Save summaries for every iteration and full artifacts for best/final."""
    root_path = Path(root)
    run_path = root_path / result.run_id
    if run_path.exists():
        shutil.rmtree(run_path)
    run_path.mkdir(parents=True)

    iteration_summaries = [
        {
            "evaluation": item.get("evaluation"),
            "role": item.get("role"),
            "theta": item.get("theta"),
            "energy": item.get("energy"),
            "standard_error": item.get("standard_error"),
            "best_energy": item.get("best_energy"),
            "delta_energy": item.get("delta_energy"),
            "seed": item.get("seed"),
            "evidence_summary": item.get("evidence_summary"),
        }
        for item in result.convergence_history
    ]

    payloads = {
        "request.json": result.request_summary,
        "problem_artifact.json": artifact.metadata(),
        "measurement_plan.json": serializable_measurement_plan(artifact.measurement_plan),
        "iteration_summaries.json": iteration_summaries,
        "optimizer_history.json": {
            "run_mode": result.run_mode,
            "optimizer": result.optimizer_name,
            "converged": result.optimizer_converged,
            "message": result.optimizer_message,
            "evaluations": result.optimizer_evaluations,
            "tolerance": result.optimizer_tolerance,
            "parameter_source": result.parameter_source,
            "optimizer_diagnostics": result.optimizer_diagnostics,
            "initial_parameters": result.initial_parameters,
            "final_parameters": result.final_parameters,
            "history": result.convergence_history,
        },
        "journey_events.json": result.journey_events,
        "translation_check.json": {
            key: value
            for key, value in result.translation_check.items()
            if key not in {"raw_qasm2", "unrolled_qasm2"}
        },
        "run_result.json": result.to_dict(include_artifacts=False),
        "verification_report.json": result.verification,
        "meaning.json": result.meaning,
        "task_result.json": result.task_result,
        "task_verification.json": result.task_verification,
        "task_meaning.json": result.task_meaning,
        "model_task_plan.json": result.model_task_plan,
        "environment.json": result.environment,
        "reference_policy.json": {
            "policy": result.reference_policy,
            "note": "Production exact-reference policy awaits mentor confirmation.",
        },
        "artifact_retention_policy.json": (
            {
                "task": "mapping_analysis",
                "input_contract": "full standardized spin-orbital instance and provenance",
                "mapped_artifacts": "JW/BK QubitOperator terms, mapped particle-number operators, capability/compatibility reports",
                "reference": "full-space and fixed-particle Fermionic spectra",
                "resources": "operator-level metrics and comparison report",
                "qasm2_backend_shots": "not applicable",
            }
            if result.task_id == "mapping_analysis"
            else {
                "all_iterations": "compact summaries",
                "best_point": "full QASM2, counts, and translation artifacts",
                "final_point": "full QASM2, counts, and translation artifacts",
                "best_and_final_relation": (
                    "Ground-state controllers retain best/final execution points. "
                    "Single-pass tasks retain their one final task execution point."
                ),
            }
        ),
    }
    for filename, payload in payloads.items():
        _write_json(run_path / filename, payload)

    # Phase B is a post-run, read-only interpretation layer.  When available,
    # retain its sanitized context and deterministic report beside the same
    # scientific evidence chain; never pickle callables or scientific objects.
    if advisor_context is not None or advisor_report is not None:
        advisor_path = run_path / "advisor"
        advisor_path.mkdir(parents=True, exist_ok=True)
        if advisor_context is not None:
            _write_json(advisor_path / "advisor_context.json", advisor_context)
        if advisor_report is not None:
            _write_json(advisor_path / "advisor_report.json", advisor_report)
            cards = advisor_report.get("cards", []) if isinstance(advisor_report, Mapping) else []
            _write_json(advisor_path / "recommendation_cards.json", cards)
        _write_json(advisor_path / "safety_contract.json", {
            "deterministic": True,
            "llm_used": False,
            "problem_artifact_mutated": False,
            "run_result_mutated": False,
            "evidence_mutated": False,
            "verification_mutated": False,
            "same_pipeline_entrypoint": "qcol.orchestrator.run_pipeline",
            "user_approval_required_for_patch": True,
            "new_evidence_required_after_rerun": True,
            "verification_retains_final_authority": True,
        })

    if result.task_id == "mapping_analysis":
        mapping_path = run_path / "mapping_analysis"
        mapping_path.mkdir(parents=True, exist_ok=True)
        _write_json(mapping_path / "comparison_report.json", result.task_result)
        _write_json(mapping_path / "verification.json", result.task_verification or result.verification)
        for record in result.raw_records:
            mapping_id = str(record.get("mapping_id", "mapping")).replace(".v1", "")
            safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in mapping_id)
            _write_json(mapping_path / f"{safe}_resource_report.json", record.get("resource_report", {}))
            _write_json(mapping_path / f"{safe}_capability_report.json", record.get("capability_report", {}))
            _write_json(mapping_path / f"{safe}_compatibility_and_provenance.json", {
                "mapping_id": record.get("mapping_id"),
                "transform_verified": record.get("transform_verified"),
                "full_spectrum_max_abs_error": record.get("full_spectrum_max_abs_error"),
                "target_sector_spectrum_max_abs_error": record.get("target_sector_spectrum_max_abs_error"),
                "particle_number_spectrum_max_abs_error": record.get("particle_number_spectrum_max_abs_error"),
                "mapping_provenance": record.get("mapping_provenance", {}),
            })
            _write_json(mapping_path / f"{safe}_qubit_hamiltonian.json", {
                "mapping_id": record.get("mapping_id"),
                "terms": record.get("qubit_hamiltonian_terms", []),
            })
            _write_json(mapping_path / f"{safe}_particle_number_operator.json", {
                "mapping_id": record.get("mapping_id"),
                "terms": record.get("mapped_particle_number_terms", []),
            })
        _write_json(mapping_path / "execution_boundary.json", {
            "backend_execution": False,
            "shots": "not applicable",
            "qasm2": "not applicable",
            "vqe": "not claimed",
            "scope": "fermion-to-qubit transformation, equivalence, capability, and operator-resource analysis",
        })
    else:
        final_path = run_path / "final"
        _write_full_execution_artifacts(
            final_path,
            translation_check=result.translation_check,
            records=result.raw_records,
        )
        # The optimizer deliberately performs a strict final re-evaluation of its
        # best theta. Preserve a separately named best folder even when both roles
        # refer to the same physical execution point.
        best_path = run_path / "best"
        shutil.copytree(final_path, best_path)

    # Task-specific records are kept separately from the supporting energy records.
    task_records = result.task_result.get("records", []) if isinstance(result.task_result, Mapping) else []
    if task_records:
        task_path = run_path / "task"
        task_path.mkdir(parents=True, exist_ok=True)
        for index, record in enumerate(task_records):
            stem = str(record.get("group_id", f"task_{index}"))
            if "raw_qasm2" in record:
                (task_path / f"{stem}_raw.qasm").write_text(str(record["raw_qasm2"]), encoding="utf-8")
            if "unrolled_qasm2" in record:
                (task_path / f"{stem}_unrolled.qasm").write_text(str(record["unrolled_qasm2"]), encoding="utf-8")
            if "counts" in record:
                _write_json(task_path / f"{stem}_counts.json", record["counts"])

    # Compatibility copies exist only for circuit-execution tasks. Mapping
    # analysis records an explicit non-applicability boundary instead of empty QASM.
    if result.task_id != "mapping_analysis":
        (run_path / "final_bound_ansatz_raw.qasm").write_text(
            str(result.translation_check.get("raw_qasm2", "")), encoding="utf-8"
        )
        (run_path / "final_bound_ansatz_unrolled.qasm").write_text(
            str(result.translation_check.get("unrolled_qasm2", "")), encoding="utf-8"
        )

    files = sorted(path for path in run_path.rglob("*") if path.is_file())
    manifest = {
        "artifact_id": artifact.artifact_id,
        "run_id": result.run_id,
        "method": artifact.method,
        "problem": artifact.problem,
        "status": result.status,
        "task_id": result.task_id,
        "controller_id": result.controller_id,
        "model_task_cell_id": result.model_task_cell_id,
        "reference_policy": result.reference_policy,
        "files": [
            {
                "path": str(path.relative_to(run_path)),
                "sha256": sha256_file(path),
            }
            for path in files
        ],
    }
    _write_json(run_path / "manifest.json", manifest)
    return run_path


def archive_pipeline_evidence(run_path: Path | str) -> Path:
    path = Path(run_path)
    archive = shutil.make_archive(
        str(path),
        "zip",
        root_dir=path.parent,
        base_dir=path.name,
    )
    return Path(archive)


def save_and_archive_pipeline_evidence(
    artifact: ProblemArtifact,
    result: RunResult,
    root: Path | str = "qcol_phase_a_evidence",
    *,
    advisor_context: Mapping[str, Any] | None = None,
    advisor_report: Mapping[str, Any] | None = None,
) -> Tuple[Path, Path]:
    run_path = save_pipeline_evidence(
        artifact,
        result,
        root,
        advisor_context=advisor_context,
        advisor_report=advisor_report,
    )
    return run_path, archive_pipeline_evidence(run_path)

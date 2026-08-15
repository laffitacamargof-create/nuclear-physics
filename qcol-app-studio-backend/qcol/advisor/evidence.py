"""Deterministic, strict-JSON Phase B evidence export."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from qcol.realization_policies.base import contract_fingerprint, json_contract_value

from .catalog import (
    PHASE_B_PROJECT_VERSION,
    PHASE_B_RELEASE_ID,
    deterministic_advisor_catalog_fingerprint,
    public_deterministic_advisor_catalog,
    validate_deterministic_advisor_catalog,
)


PHASE_B_EVIDENCE_SCHEMA_VERSION = "qcol-phase-b-deterministic-advisor-evidence/1.0"
PHASE_B_EVIDENCE_ARCHIVE_ID = "qcol.phase-b.deterministic-advisor.evidence.v1"
_FORBIDDEN_EXTENSIONS = (".pkl", ".pickle", ".joblib", ".dill")


@dataclass(frozen=True)
class ExportedPhaseBAdvisorEvidence:
    output_directory: Path
    archive_path: Path
    manifest_path: Path


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(json_contract_value(payload), indent=2, sort_keys=True, allow_nan=False),
        encoding="utf-8",
    )


def _source_fingerprints(project_root: str | Path | None) -> dict[str, str]:
    if project_root is None:
        return {}
    root = Path(project_root)
    relative_paths = (
        "qcol/advisor/enums.py",
        "qcol/advisor/contracts.py",
        "qcol/advisor/context.py",
        "qcol/advisor/rules.py",
        "qcol/advisor/engine.py",
        "qcol/advisor/catalog.py",
        "qcol/advisor/evidence.py",
        "qcol/advisor/advisor_context.py",
        "qcol/advisor/advisor_rules.py",
        "qcol/advisor/fixtures.py",
        "qcol/advisor/recommendations.py",
        "qcol/advisor/request_patch.py",
        "qcol/advisor/__init__.py",
        "qcol/governance/patches.py",
        "qcol/run_manager.py",
        "qcol/evidence.py",
        "qcol/api.py",
        "qcol/catalog.py",
        "qcol/app.py",
        "qcol/orchestrator.py",
        "qcol/web/index.html",
        "qcol/web/styles.css",
        "qcol/web/app.js",
        "qcol/journey.py",
        "scripts/run_phase_b_gate.py",
        "scripts/export_phase_b_advisor_evidence.py",
        "setup_windows.bat",
        "check_environment.py",
        "test_phase_b_advisor_windows.bat",
        "test_phase_b_full_windows.bat",
        "tests/test_phase_b_advisor_context.py",
        "tests/test_phase_b_advisor_rules.py",
        "tests/test_phase_b_patch_boundary.py",
        "tests/test_phase_b_api.py",
        "tests/test_phase_b_ui_static.py",
        "tests/test_phase_b_evidence.py",
        "tests/test_phase_b_release_gate.py",
        "tests/test_phase_b_run_manager.py",
        "tests/test_phase_b_notebook_static.py",
        "README.md",
        "START_HERE.txt",
        "QCOL_Phase_B_Deterministic_Advisor.ipynb",
    )
    output: dict[str, str] = {}
    for relative in relative_paths:
        path = root / relative
        if path.exists():
            output[relative] = contract_fingerprint({"source": path.read_text(encoding="utf-8")})
    return output


def export_phase_b_advisor_evidence(
    output_directory: str | Path,
    *,
    project_root: str | Path | None = None,
) -> ExportedPhaseBAdvisorEvidence:
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    catalog = public_deterministic_advisor_catalog()
    validation = validate_deterministic_advisor_catalog()
    scenarios = catalog["scenario_catalog"]
    files: dict[str, Any] = {
        "deterministic_advisor_catalog.json": catalog,
        "advisor_rule_catalog.json": catalog["rule_catalog"],
        "advisor_context_contract.json": catalog["context_contract"],
        "allowed_request_patch_registry.json": catalog["allowed_request_patch_registry"],
        "candidate_request_boundary.json": catalog["candidate_request_boundary"],
        "advisor_safety_contract.json": catalog["safety_contract"],
        "phase_b_definition_of_done.json": catalog["phase_b_definition_of_done"],
        "phase_b_validation.json": validation,
        "foundation_fingerprints.json": catalog["foundation_fingerprints"],
    }
    for scenario, payload in scenarios.items():
        files[f"scenario_{scenario}_context.json"] = payload["context"]
        files[f"scenario_{scenario}_recommendations.json"] = payload["report"]
    for name, payload in files.items():
        _write_json(output / name, payload)
    source = _source_fingerprints(project_root)
    _write_json(output / "source_fingerprints.json", source)
    manifest = {
        "schema_version": PHASE_B_EVIDENCE_SCHEMA_VERSION,
        "archive_id": PHASE_B_EVIDENCE_ARCHIVE_ID,
        "release_id": PHASE_B_RELEASE_ID,
        "project_version": PHASE_B_PROJECT_VERSION,
        "catalog_fingerprint": deterministic_advisor_catalog_fingerprint(),
        "validation_passed": all(validation.values()),
        "deterministic_rules_only": True,
        "advisor_runtime_implemented": True,
        "llm_runtime_used": False,
        "problem_artifact_mutated": False,
        "run_result_mutated": False,
        "evidence_mutated": False,
        "verification_mutated": False,
        "same_pipeline_entrypoint": "qcol.orchestrator.run_pipeline",
        "user_approval_required": True,
        "execution_performed_by_advisor": False,
        "strict_json": True,
        "python_pickling_used": False,
        "callable_payload_withheld": True,
        "second_runtime_created": False,
        "files": sorted([*files.keys(), "source_fingerprints.json", "manifest.json"]),
    }
    manifest_path = output / "manifest.json"
    _write_json(manifest_path, manifest)
    archive = output.with_suffix(".zip")
    with ZipFile(archive, "w", compression=ZIP_DEFLATED, compresslevel=9) as bundle:
        for path in sorted(output.iterdir()):
            if not path.is_file():
                continue
            if path.suffix.lower() in _FORBIDDEN_EXTENSIONS:
                raise RuntimeError(f"Phase B Evidence cannot contain pickle file {path.name!r}.")
            info = ZipInfo(filename=path.name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            bundle.writestr(info, path.read_bytes(), compress_type=ZIP_DEFLATED, compresslevel=9)
    return ExportedPhaseBAdvisorEvidence(
        output_directory=output,
        archive_path=archive,
        manifest_path=manifest_path,
    )


__all__ = [
    "PHASE_B_EVIDENCE_SCHEMA_VERSION",
    "PHASE_B_EVIDENCE_ARCHIVE_ID",
    "ExportedPhaseBAdvisorEvidence",
    "export_phase_b_advisor_evidence",
]

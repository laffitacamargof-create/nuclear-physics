"""Evidence exporter for the WP0 mapping-realization baseline freeze."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from importlib import metadata
import json
from pathlib import Path
import shutil
from typing import Any, Dict, Mapping

from .jw_negative_fixture import (
    evaluate_frozen_jw_negative_fixture,
    evaluate_runtime_jw_negative_fixture,
)
from .mapping_baseline import (
    assert_wp0_baseline,
    baseline_fingerprint,
    public_mapping_realization_baseline,
)
from ..compatibility import public_failure_code_registry, validate_failure_code_registry


@dataclass(frozen=True)
class BaselineEvidenceExport:
    output_directory: Path
    archive_path: Path
    scientific_checks_included: bool
    manifest: Mapping[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "output_directory": str(self.output_directory),
            "archive_path": str(self.archive_path),
            "scientific_checks_included": bool(self.scientific_checks_included),
            "manifest": dict(self.manifest),
        }


def _json_write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )


def _hash_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _source_fingerprints(project_root: Path) -> Dict[str, str]:
    relatives = (
        "qcol/models/general_spin_orbital/jw_ground_state.py",
        "qcol/modeling.py",
        "qcol/mappings/jordan_wigner.py",
        "qcol/mappings/bravyi_kitaev.py",
        "qcol/models/reduced_pairing_one_pair/acceptance.py",
        "qcol/model_task_matrix.py",
        "qcol/acceptance/jw_negative_fixture.py",
        "qcol/request_boundaries.py",
        "qcol/request_validation.py",
        "qcol/acceptance/baselines/mapping_realization_baseline.v1.json",
    )
    return {
        relative: _hash_file(project_root / relative)
        for relative in relatives
        if (project_root / relative).exists()
    }


def _dependency_versions() -> Dict[str, Any]:
    distributions = (
        "numpy",
        "scipy",
        "cirq-core",
        "openfermion",
        "pyqasm",
        "gradio",
        "fastapi",
    )
    versions: Dict[str, Any] = {}
    for name in distributions:
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            versions[name] = None
    return versions


def _mapping_analysis_request() -> Dict[str, Any]:
    return {
        "method": "general_spin_orbital",
        "problem": "mapping_explorer",
        "task_id": "mapping_analysis",
        "parameters": {
            "n_modes": 4,
            "particle_species": "neutron",
            "mode_labels": (
                "neutron|a|m=+1/2\n"
                "neutron|a|m=-1/2\n"
                "neutron|b|m=+1/2\n"
                "neutron|b|m=-1/2"
            ),
            "one_body_terms": (
                "0,0,0.0\n1,1,0.2\n2,2,1.0\n3,3,1.2\n"
                "0,2,0.15\n2,0,0.15\n1,3,-0.1\n3,1,-0.1"
            ),
            "two_body_terms": "0,1,0,1,0.3",
            "target_particle_number": 2,
            "declared_symmetries": ["particle_number"],
            "coefficient_convention": "explicit_operator_coefficient",
            "energy_unit": "MeV",
        },
        "task_parameters": {
            "mapping_ids": ["jordan_wigner.v1", "bravyi_kitaev.v1"],
            "coefficient_threshold": 1e-12,
            "equivalence_tolerance": 1e-8,
        },
        "requested_observables": ["mapping_resources", "mapping_equivalence"],
        "target_backend": "none",
        "execution_mode": "analysis_only",
        "run_mode": "mapping_analysis",
        "shots": 0,
        "final_shots": 0,
        "max_evaluations": 1,
        "seed": 0,
    }


def collect_scientific_baseline_checks() -> Dict[str, Any]:
    """Run the positive anchors and the known-invalid JW negative fixture."""
    from ..contracts import json_safe
    from ..models.reduced_pairing_one_pair import (
        acceptance_request,
        assert_one_pair_regression,
        build_one_pair_quantum_realization,
    )
    from ..orchestrator import run_pipeline

    one_pair_realization = build_one_pair_quantum_realization(acceptance_request())
    one_pair_realization.validate_bridge()
    one_pair_report = assert_one_pair_regression(one_pair_realization.runtime_artifact)

    mapping_artifact, mapping_result = run_pipeline(_mapping_analysis_request())
    entries = {
        item["mapping_id"]: item
        for item in mapping_result.task_result["entries"]
    }
    if mapping_result.status != "PASS":
        raise AssertionError(mapping_result.verification)
    if set(entries) != {"jordan_wigner.v1", "bravyi_kitaev.v1"}:
        raise AssertionError(f"Unexpected mapping-analysis entries: {sorted(entries)}")

    jw_negative = evaluate_runtime_jw_negative_fixture()
    if not jw_negative["matches_frozen_failure"]:
        raise AssertionError(jw_negative)

    return json_safe({
        "schema_version": "qcol-wp0-scientific-baseline-checks/1.0",
        "one_pair_positive_regression_anchor": one_pair_report.to_dict(),
        "mapping_analysis": {
            "status": mapping_result.status,
            "all_transforms_verified": mapping_result.task_result["all_transforms_verified"],
            "jordan_wigner": entries["jordan_wigner.v1"],
            "bravyi_kitaev": entries["bravyi_kitaev.v1"],
            "qasm_applicable": mapping_result.translation_check["qasm_applicable"],
            "shots": mapping_result.shots_per_group,
            "hardware_submitted": mapping_result.hardware_submission_performed,
            "artifact_id": mapping_artifact.artifact_id,
        },
        "jw_invalid_composition_negative_fixture": jw_negative,
        "scientific_status_promoted": False,
    })


def export_mapping_baseline_evidence(
    output_root: str | Path,
    *,
    include_scientific_checks: bool,
    project_root: str | Path | None = None,
) -> BaselineEvidenceExport:
    root = Path(output_root).resolve()
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    project = Path(project_root).resolve() if project_root is not None else Path(__file__).resolve().parents[2]

    baseline_checks = assert_wp0_baseline()
    failure_checks = validate_failure_code_registry()
    if not all(failure_checks.values()):
        raise AssertionError(failure_checks)

    baseline = public_mapping_realization_baseline()
    negative = evaluate_frozen_jw_negative_fixture().to_dict()
    _json_write(root / "baseline_status_matrix.json", baseline)
    _json_write(root / "stable_failure_code_registry.json", public_failure_code_registry())
    _json_write(root / "jw_invalid_composition_negative_fixture.json", negative)
    _json_write(root / "baseline_validation.json", {
        "baseline_checks": baseline_checks,
        "failure_code_checks": failure_checks,
        "baseline_fingerprint": baseline_fingerprint(baseline),
    })
    _json_write(root / "source_fingerprints.json", _source_fingerprints(project))
    _json_write(root / "dependency_versions.json", _dependency_versions())

    scientific_payload = None
    if include_scientific_checks:
        scientific_payload = collect_scientific_baseline_checks()
        _json_write(root / "scientific_baseline_checks.json", scientific_payload)

    files = sorted(path for path in root.iterdir() if path.is_file())
    file_hashes = {path.name: _hash_file(path) for path in files}
    manifest = {
        "schema_version": "qcol-wp0-baseline-evidence-manifest/1.0",
        "baseline_id": baseline["baseline_id"],
        "baseline_fingerprint": baseline_fingerprint(baseline),
        "scientific_checks_included": bool(include_scientific_checks),
        "scientific_status_promoted": False,
        "files": file_hashes,
        "exit_statement": (
            "Verified paths preserved; experimental paths unchanged; "
            "known invalid JW composition rejected as expected; no scientific status promoted."
        ),
    }
    _json_write(root / "manifest.json", manifest)
    archive_path = Path(shutil.make_archive(str(root), "zip", root_dir=root))
    return BaselineEvidenceExport(
        output_directory=root,
        archive_path=archive_path,
        scientific_checks_included=include_scientific_checks,
        manifest=manifest,
    )

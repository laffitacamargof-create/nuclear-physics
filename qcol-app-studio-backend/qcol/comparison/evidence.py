"""Strict-JSON Phase C comparison evidence exporters."""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import shutil
import zipfile
from typing import Any, Mapping

from qcol.realization_policies.base import json_contract_value
from .catalog import phase_c_catalog_fingerprint, public_phase_c_catalog, validate_phase_c_catalog
from .contracts import ComparisonDecisionRecord, RunComparison
from .policies import public_comparison_policy_catalog

_FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)


def _json_bytes(payload: Any) -> bytes:
    return (json.dumps(json_contract_value(payload), indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _deterministic_zip(path: Path, files: Mapping[str, bytes]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, date_time=_FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, files[name])
    return path


@dataclass(frozen=True)
class ExportedComparisonEvidence:
    archive_path: Path
    manifest: dict[str, Any]


def export_phase_c_catalog_evidence(root: Path | str) -> ExportedComparisonEvidence:
    root = Path(root)
    catalog = public_phase_c_catalog()
    payloads = {
        "phase_c_catalog.json": _json_bytes(catalog),
        "comparison_policy_catalog.json": _json_bytes(public_comparison_policy_catalog()),
        "phase_c_validation.json": _json_bytes(validate_phase_c_catalog()),
        "foundation_fingerprints.json": _json_bytes({"phase_b_catalog_fingerprint": "8b043bef963bf60c12483b748ea46ef740ada1a7077d8a5a58165c9032d915c1"}),
    }
    manifest = {
        "schema_version": "qcol-phase-c-evidence-manifest/1.0",
        "catalog_fingerprint": phase_c_catalog_fingerprint(),
        "files": [{"path": name, "sha256": _sha256_bytes(data)} for name, data in sorted(payloads.items())],
        "strict_json": True,
        "pickle_used": False,
        "callable_payload_withheld": True,
        "same_pipeline_required": True,
        "silent_replacement_allowed": False,
    }
    payloads["manifest.json"] = _json_bytes(manifest)
    archive = _deterministic_zip(root / "qcol_phase_c_try_compare_evidence.zip", payloads)
    return ExportedComparisonEvidence(archive_path=archive, manifest=manifest)


def export_run_comparison_evidence(
    root: Path | str,
    *,
    comparison: RunComparison,
    decision: ComparisonDecisionRecord,
    baseline_snapshot: Mapping[str, Any],
    candidate_snapshot: Mapping[str, Any],
) -> ExportedComparisonEvidence:
    root = Path(root)
    folder = root / comparison.comparison_id
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    payloads = {
        "comparison.json": _json_bytes(comparison.to_dict()),
        "decision_record.json": _json_bytes(decision.to_dict()),
        "baseline_public_snapshot.json": _json_bytes(baseline_snapshot),
        "candidate_public_snapshot.json": _json_bytes(candidate_snapshot),
    }
    manifest = {
        "schema_version": "qcol-run-comparison-evidence-manifest/1.0",
        "comparison_id": comparison.comparison_id,
        "baseline_run_id": comparison.baseline_run_id,
        "candidate_run_id": comparison.candidate_run_id,
        "outcome": comparison.outcome.value,
        "files": [{"path": name, "sha256": _sha256_bytes(data)} for name, data in sorted(payloads.items())],
        "automatic_replacement_performed": False,
        "verification_retains_final_authority": True,
    }
    payloads["manifest.json"] = _json_bytes(manifest)
    for name, data in payloads.items():
        (folder / name).write_bytes(data)
    archive = _deterministic_zip(root / f"{comparison.comparison_id}.zip", payloads)
    return ExportedComparisonEvidence(archive_path=archive, manifest=manifest)


__all__ = ["ExportedComparisonEvidence", "export_phase_c_catalog_evidence", "export_run_comparison_evidence"]

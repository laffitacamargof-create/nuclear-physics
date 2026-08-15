"""WP1 evidence exporter for the shared mapping-realization vocabulary."""
from __future__ import annotations

from dataclasses import dataclass
from importlib import metadata
import hashlib
import json
from pathlib import Path
import shutil
from typing import Any, Dict, Iterable

from qcol import __version__
from qcol.acceptance.mapping_baseline import baseline_fingerprint
from qcol.compatibility import public_failure_code_registry
from qcol.mapping_policies import (
    public_mapping_realization_vocabulary,
    validate_mapping_realization_vocabulary,
    vocabulary_fingerprint,
)


@dataclass(frozen=True)
class VocabularyEvidenceExport:
    output_dir: Path
    archive_path: Path
    manifest_path: Path


def _json_write(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _dependency_versions() -> Dict[str, Any]:
    names = (
        "numpy",
        "scipy",
        "cirq-core",
        "openfermion",
        "pyqasm",
        "fastapi",
        "gradio",
    )
    versions: Dict[str, Any] = {}
    for name in names:
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            versions[name] = None
    return versions


def _source_fingerprints(project_root: Path) -> Dict[str, str]:
    relative_paths = (
        "qcol/mapping_policies/enums.py",
        "qcol/mapping_policies/primitives.py",
        "qcol/mapping_policies/vocabulary.py",
        "qcol/mapping_policies/__init__.py",
        "qcol/acceptance/vocabulary_evidence.py",
        "qcol/api.py",
        "qcol/catalog.py",
        "qcol/compatibility/failure_codes.py",
        "qcol/acceptance/baselines/mapping_realization_baseline.v1.json",
    )
    result: Dict[str, str] = {}
    for relative in relative_paths:
        path = project_root / relative
        if path.exists():
            result[relative] = _hash_file(path)
    return result


def export_mapping_vocabulary_evidence(
    output: str | Path,
    *,
    project_root: str | Path | None = None,
) -> VocabularyEvidenceExport:
    """Write a reproducible WP1 evidence directory and ZIP archive."""
    root = Path(project_root or Path(__file__).resolve().parents[2]).resolve()
    output_dir = Path(output).resolve()
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    vocabulary = public_mapping_realization_vocabulary()
    validation = validate_mapping_realization_vocabulary(vocabulary)
    if not all(validation.values()):
        failed = [name for name, passed in validation.items() if not passed]
        raise AssertionError("WP1 vocabulary evidence validation failed: " + ", ".join(failed))

    _json_write(output_dir / "mapping_realization_vocabulary.json", vocabulary)
    _json_write(output_dir / "vocabulary_validation.json", validation)
    _json_write(
        output_dir / "vocabulary_fingerprint.json",
        {
            "schema_version": "qcol-vocabulary-fingerprint/1.0",
            "vocabulary_fingerprint": vocabulary_fingerprint(vocabulary),
            "wp0_baseline_fingerprint": baseline_fingerprint(),
            "scientific_behavior_change": False,
        },
    )
    _json_write(
        output_dir / "stable_failure_code_registry.json",
        public_failure_code_registry(),
    )
    _json_write(output_dir / "dependency_versions.json", _dependency_versions())
    _json_write(
        output_dir / "source_fingerprints.json",
        _source_fingerprints(root),
    )

    files = sorted(path for path in output_dir.iterdir() if path.is_file())
    manifest = {
        "schema_version": "qcol-wp1-vocabulary-evidence/1.0",
        "phase": "Phase A.3.2a",
        "work_package": "WP1 — Shared Exported Vocabulary",
        "project_version": __version__,
        "scientific_behavior_change": False,
        "vocabulary_fingerprint": vocabulary_fingerprint(vocabulary),
        "wp0_baseline_fingerprint": baseline_fingerprint(),
        "files": [
            {
                "name": path.name,
                "sha256": _hash_file(path),
                "size_bytes": path.stat().st_size,
            }
            for path in files
        ],
        "exit_statement": (
            "Shared vocabulary exported; semantic overclaiming guardrails pass; "
            "WP0 scientific statuses remain unchanged."
        ),
    }
    manifest_path = output_dir / "manifest.json"
    _json_write(manifest_path, manifest)

    archive_base = output_dir.parent / output_dir.name
    archive_path = Path(
        shutil.make_archive(
            str(archive_base),
            "zip",
            root_dir=output_dir,
        )
    )
    return VocabularyEvidenceExport(
        output_dir=output_dir,
        archive_path=archive_path,
        manifest_path=manifest_path,
    )


__all__ = ["VocabularyEvidenceExport", "export_mapping_vocabulary_evidence"]

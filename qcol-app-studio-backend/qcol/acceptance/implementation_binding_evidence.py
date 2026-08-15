"""WP3 evidence exporter for implementation-binding registries."""
from __future__ import annotations

from dataclasses import dataclass
from importlib import metadata
import hashlib
import json
from pathlib import Path
import shutil
from typing import Any

from qcol import __version__
from qcol.acceptance.mapping_baseline import baseline_fingerprint
from qcol.implementation_bindings import (
    implementation_binding_catalog_fingerprint,
    public_implementation_binding_catalog,
    validate_implementation_binding_registry,
)
from qcol.mapping_policies import vocabulary_fingerprint
from qcol.policy_contract_catalog import policy_contract_catalog_fingerprint


@dataclass(frozen=True)
class ImplementationBindingEvidenceExport:
    output_dir: Path
    archive_path: Path
    manifest_path: Path


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _dependency_versions() -> dict[str, str | None]:
    result: dict[str, str | None] = {}
    for name in (
        "numpy",
        "scipy",
        "cirq-core",
        "openfermion",
        "pyqasm",
        "fastapi",
        "gradio",
    ):
        try:
            result[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            result[name] = None
    return result


def _source_fingerprints(project_root: Path) -> dict[str, str]:
    paths = (
        "qcol/implementation_bindings/__init__.py",
        "qcol/implementation_bindings/enums.py",
        "qcol/implementation_bindings/contracts.py",
        "qcol/implementation_bindings/registry.py",
        "qcol/implementation_bindings/contract_index.py",
        "qcol/implementation_bindings/builtin.py",
        "qcol/implementation_bindings/fixtures.py",
        "qcol/implementation_bindings/catalog.py",
        "qcol/policy_contract_catalog.py",
        "qcol/api.py",
        "qcol/catalog.py",
    )
    return {
        relative: _sha(project_root / relative)
        for relative in paths
        if (project_root / relative).exists()
    }


def export_implementation_binding_evidence(
    output: str | Path,
    *,
    project_root: str | Path | None = None,
) -> ImplementationBindingEvidenceExport:
    root = Path(project_root or Path(__file__).resolve().parents[2]).resolve()
    output_dir = Path(output).resolve()
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    catalog = public_implementation_binding_catalog()
    checks = validate_implementation_binding_registry(catalog)
    if not all(checks.values()):
        failed = [key for key, value in checks.items() if not value]
        raise AssertionError(
            "WP3 implementation-binding validation failed: " + ", ".join(failed)
        )

    _write_json(output_dir / "implementation_binding_catalog.json", catalog)
    _write_json(output_dir / "binding_validation.json", checks)
    _write_json(
        output_dir / "resolved_binding_plan.json",
        catalog["resolved_example_plan"],
    )
    _write_json(
        output_dir / "known_contract_missing_binding.json",
        catalog["known_contract_missing_binding"],
    )
    _write_json(
        output_dir / "recognized_not_executable_binding.json",
        catalog["recognized_not_executable_binding"],
    )
    _write_json(
        output_dir / "foundation_fingerprints.json",
        {
            "schema_version": "qcol-wp3-foundation-fingerprints/1.0",
            "wp0_baseline_fingerprint": baseline_fingerprint(),
            "wp1_vocabulary_fingerprint": vocabulary_fingerprint(),
            "wp2_contract_catalog_fingerprint": policy_contract_catalog_fingerprint(),
            "wp3_binding_catalog_fingerprint": implementation_binding_catalog_fingerprint(catalog),
            "scientific_behavior_change": False,
        },
    )
    _write_json(output_dir / "dependency_versions.json", _dependency_versions())
    _write_json(output_dir / "source_fingerprints.json", _source_fingerprints(root))

    files = sorted(path for path in output_dir.iterdir() if path.is_file())
    manifest = {
        "schema_version": "qcol-wp3-implementation-binding-evidence/1.0",
        "phase": "Phase A.3.2a",
        "work_package": "WP3 — Registries and Implementation Bindings",
        "project_version": __version__,
        "scientific_behavior_change": False,
        "live_policy_migration_performed": False,
        "silent_fallback_allowed": False,
        "wp0_baseline_fingerprint": baseline_fingerprint(),
        "wp1_vocabulary_fingerprint": vocabulary_fingerprint(),
        "wp2_contract_catalog_fingerprint": policy_contract_catalog_fingerprint(),
        "wp3_binding_catalog_fingerprint": implementation_binding_catalog_fingerprint(catalog),
        "files": [
            {
                "name": path.name,
                "sha256": _sha(path),
                "size_bytes": path.stat().st_size,
            }
            for path in files
        ],
        "exit_statement": (
            "Declarative contract IDs resolve through exact versioned binding IDs; "
            "missing or unavailable implementations return recognized_not_executable; "
            "public evidence contains metadata and no callable payload."
        ),
    }
    manifest_path = output_dir / "manifest.json"
    _write_json(manifest_path, manifest)
    archive_path = Path(
        shutil.make_archive(str(output_dir), "zip", root_dir=output_dir)
    )
    return ImplementationBindingEvidenceExport(
        output_dir=output_dir,
        archive_path=archive_path,
        manifest_path=manifest_path,
    )


__all__ = [
    "ImplementationBindingEvidenceExport",
    "export_implementation_binding_evidence",
]

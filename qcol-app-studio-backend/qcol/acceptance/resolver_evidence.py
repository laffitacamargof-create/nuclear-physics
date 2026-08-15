"""WP5 evidence exporter for realization resolution and runtime-entry decisions."""
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
from qcol.compatibility import compatibility_rule_catalog_fingerprint
from qcol.implementation_bindings import implementation_binding_catalog_fingerprint
from qcol.mapping_policies import vocabulary_fingerprint
from qcol.policy_contract_catalog import policy_contract_catalog_fingerprint
from qcol.realization_variants import (
    build_wp5_resolution_bundle,
    public_realization_resolver_catalog,
    realization_resolver_catalog_fingerprint,
    validate_realization_resolver,
)


@dataclass(frozen=True)
class RealizationResolverEvidenceExport:
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
        "qcol/realization_variants/__init__.py",
        "qcol/realization_variants/enums.py",
        "qcol/realization_variants/contracts.py",
        "qcol/realization_variants/fixtures.py",
        "qcol/realization_variants/resolver.py",
        "qcol/realization_variants/runtime_gate.py",
        "qcol/realization_variants/catalog.py",
        "qcol/compatibility/rule_registry.py",
        "qcol/implementation_bindings/registry.py",
        "qcol/api.py",
        "qcol/catalog.py",
        "qcol/__init__.py",
    )
    return {
        relative: _sha(project_root / relative)
        for relative in paths
        if (project_root / relative).exists()
    }


def export_realization_resolver_evidence(
    output: str | Path,
    *,
    project_root: str | Path | None = None,
) -> RealizationResolverEvidenceExport:
    root = Path(project_root or Path(__file__).resolve().parents[2]).resolve()
    output_dir = Path(output).resolve()
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    catalog = public_realization_resolver_catalog()
    checks = validate_realization_resolver(catalog)
    if not all(checks.values()):
        failed = [key for key, value in checks.items() if not value]
        raise AssertionError(
            "WP5 realization-resolver validation failed: " + ", ".join(failed)
        )
    bundle = build_wp5_resolution_bundle()
    resolutions = bundle["resolutions"]
    dispatches = bundle["dispatches"]

    _write_json(output_dir / "realization_resolver_catalog.json", catalog)
    _write_json(output_dir / "resolver_validation.json", checks)
    for name, resolution in resolutions.items():
        _write_json(
            output_dir / f"{name}_resolution.json",
            resolution.to_public_dict(),
        )
    _write_json(
        output_dir / "runtime_entry_dispatch_reports.json",
        {name: value.to_dict() for name, value in dispatches.items()},
    )
    _write_json(
        output_dir / "foundation_fingerprints.json",
        {
            "schema_version": "qcol-wp5-foundation-fingerprints/1.0",
            "wp0_baseline_fingerprint": baseline_fingerprint(),
            "wp1_vocabulary_fingerprint": vocabulary_fingerprint(),
            "wp2_contract_catalog_fingerprint": policy_contract_catalog_fingerprint(),
            "wp3_binding_catalog_fingerprint": implementation_binding_catalog_fingerprint(),
            "wp4_rule_catalog_fingerprint": compatibility_rule_catalog_fingerprint(),
            "wp5_resolver_catalog_fingerprint": realization_resolver_catalog_fingerprint(catalog),
            "live_policy_migration_performed": False,
            "scientific_status_promoted": False,
        },
    )
    _write_json(output_dir / "dependency_versions.json", _dependency_versions())
    _write_json(output_dir / "source_fingerprints.json", _source_fingerprints(root))

    files = sorted(path for path in output_dir.iterdir() if path.is_file())
    manifest = {
        "schema_version": "qcol-wp5-realization-resolver-evidence/1.0",
        "phase": "Phase A.3.2a",
        "work_package": "WP5 — Resolver and Compatibility Reports",
        "project_version": __version__,
        "live_resolver_gate_enforced": True,
        "legacy_runtime_rewired": False,
        "live_policy_migration_performed": False,
        "scientific_status_promoted": False,
        "second_runtime_created": False,
        "silent_fallback_allowed": False,
        "wp0_baseline_fingerprint": baseline_fingerprint(),
        "wp1_vocabulary_fingerprint": vocabulary_fingerprint(),
        "wp2_contract_catalog_fingerprint": policy_contract_catalog_fingerprint(),
        "wp3_binding_catalog_fingerprint": implementation_binding_catalog_fingerprint(),
        "wp4_rule_catalog_fingerprint": compatibility_rule_catalog_fingerprint(),
        "wp5_resolver_catalog_fingerprint": realization_resolver_catalog_fingerprint(catalog),
        "files": [
            {
                "name": path.name,
                "sha256": _sha(path),
                "size_bytes": path.stat().st_size,
            }
            for path in files
        ],
        "exit_statement": (
            "Every candidate produces one explicit resolved realization variant, "
            "compatibility report, resource report, evidence status, and runtime-entry "
            "decision; fatal scientific failures and missing exact bindings invoke no "
            "runtime path; analysis-only tasks remain analysis-only."
        ),
    }
    manifest_path = output_dir / "manifest.json"
    _write_json(manifest_path, manifest)
    archive_path = Path(
        shutil.make_archive(str(output_dir), "zip", root_dir=output_dir)
    )
    return RealizationResolverEvidenceExport(
        output_dir=output_dir,
        archive_path=archive_path,
        manifest_path=manifest_path,
    )


__all__ = [
    "RealizationResolverEvidenceExport",
    "export_realization_resolver_evidence",
]

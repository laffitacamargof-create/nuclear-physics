"""WP4 evidence exporter for the compatibility-rule registry."""
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
from qcol.compatibility import (
    build_wp4_evaluation_bundle,
    compatibility_rule_catalog_fingerprint,
    public_compatibility_rule_catalog,
    validate_compatibility_rule_registry,
)
from qcol.implementation_bindings import implementation_binding_catalog_fingerprint
from qcol.mapping_policies import vocabulary_fingerprint
from qcol.policy_contract_catalog import policy_contract_catalog_fingerprint


@dataclass(frozen=True)
class CompatibilityRuleEvidenceExport:
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
        "qcol/compatibility/__init__.py",
        "qcol/compatibility/enums.py",
        "qcol/compatibility/rule_contracts.py",
        "qcol/compatibility/predicates.py",
        "qcol/compatibility/bindings.py",
        "qcol/compatibility/builtin_rules.py",
        "qcol/compatibility/rule_registry.py",
        "qcol/compatibility/fixtures.py",
        "qcol/compatibility/catalog.py",
        "qcol/compatibility/failure_codes.py",
        "qcol/implementation_bindings/enums.py",
        "qcol/api.py",
        "qcol/catalog.py",
    )
    return {
        relative: _sha(project_root / relative)
        for relative in paths
        if (project_root / relative).exists()
    }


def export_compatibility_rule_evidence(
    output: str | Path,
    *,
    project_root: str | Path | None = None,
) -> CompatibilityRuleEvidenceExport:
    root = Path(project_root or Path(__file__).resolve().parents[2]).resolve()
    output_dir = Path(output).resolve()
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    catalog = public_compatibility_rule_catalog()
    checks = validate_compatibility_rule_registry(catalog)
    if not all(checks.values()):
        failed = [key for key, value in checks.items() if not value]
        raise AssertionError(
            "WP4 compatibility-rule validation failed: " + ", ".join(failed)
        )
    bundle = build_wp4_evaluation_bundle()

    _write_json(output_dir / "compatibility_rule_catalog.json", catalog)
    _write_json(output_dir / "rule_validation.json", checks)
    _write_json(
        output_dir / "valid_execution_tuple_report.json",
        bundle["valid_execution_report"].to_dict(),
    )
    _write_json(
        output_dir / "mapping_analysis_not_applicable_report.json",
        bundle["mapping_analysis_report"].to_dict(),
    )
    _write_json(
        output_dir / "known_invalid_jw_composition_report.json",
        bundle["invalid_jw_report"].to_dict(),
    )
    _write_json(
        output_dir / "negative_rule_fixture_results.json",
        {
            rule_id: result.to_dict()
            for rule_id, result in bundle["negative_results"].items()
        },
    )
    _write_json(
        output_dir / "foundation_fingerprints.json",
        {
            "schema_version": "qcol-wp4-foundation-fingerprints/1.0",
            "wp0_baseline_fingerprint": baseline_fingerprint(),
            "wp1_vocabulary_fingerprint": vocabulary_fingerprint(),
            "wp2_contract_catalog_fingerprint": policy_contract_catalog_fingerprint(),
            "wp3_binding_catalog_fingerprint": implementation_binding_catalog_fingerprint(),
            "wp4_rule_catalog_fingerprint": compatibility_rule_catalog_fingerprint(catalog),
            "scientific_behavior_change": False,
        },
    )
    _write_json(output_dir / "dependency_versions.json", _dependency_versions())
    _write_json(output_dir / "source_fingerprints.json", _source_fingerprints(root))

    files = sorted(path for path in output_dir.iterdir() if path.is_file())
    manifest = {
        "schema_version": "qcol-wp4-compatibility-rule-evidence/1.0",
        "phase": "Phase A.3.2a",
        "work_package": "WP4 — Compatibility Rule Registry",
        "project_version": __version__,
        "scientific_behavior_change": False,
        "live_rule_gate_enforced": False,
        "live_policy_migration_performed": False,
        "silent_fallback_allowed": False,
        "pairwise_and_global_phases_separate": True,
        "wp0_baseline_fingerprint": baseline_fingerprint(),
        "wp1_vocabulary_fingerprint": vocabulary_fingerprint(),
        "wp2_contract_catalog_fingerprint": policy_contract_catalog_fingerprint(),
        "wp3_binding_catalog_fingerprint": implementation_binding_catalog_fingerprint(),
        "wp4_rule_catalog_fingerprint": compatibility_rule_catalog_fingerprint(catalog),
        "files": [
            {
                "name": path.name,
                "sha256": _sha(path),
                "size_bytes": path.stat().st_size,
            }
            for path in files
        ],
        "exit_statement": (
            "Nine exact versioned relation rules are registered; pairwise rules "
            "and global invariants remain separate; every negative fixture emits "
            "its stable failure code; the known-invalid JW composition is rejected "
            "by the ansatz-semantic rule; no live runtime behavior changed."
        ),
    }
    manifest_path = output_dir / "manifest.json"
    _write_json(manifest_path, manifest)
    archive_path = Path(
        shutil.make_archive(str(output_dir), "zip", root_dir=output_dir)
    )
    return CompatibilityRuleEvidenceExport(
        output_dir=output_dir,
        archive_path=archive_path,
        manifest_path=manifest_path,
    )


__all__ = [
    "CompatibilityRuleEvidenceExport",
    "export_compatibility_rule_evidence",
]

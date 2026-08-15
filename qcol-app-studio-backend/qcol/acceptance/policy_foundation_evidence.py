"""WP6/WP7 and complete Phase A.3.2a evidence exporters."""
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
from qcol.realization_variants import realization_resolver_catalog_fingerprint

from .fingerprint_catalog import (
    acceptance_fingerprint_catalog_fingerprint,
    public_acceptance_fingerprint_catalog,
    validate_acceptance_fingerprint_catalog,
)
from .harness_catalog import (
    acceptance_harness_catalog_fingerprint,
    public_acceptance_harness_catalog,
    validate_acceptance_harness_catalog,
)


@dataclass(frozen=True)
class AcceptanceFingerprintEvidenceExport:
    output_dir: Path
    archive_path: Path
    manifest_path: Path


@dataclass(frozen=True)
class AcceptanceHarnessEvidenceExport:
    output_dir: Path
    archive_path: Path
    manifest_path: Path


@dataclass(frozen=True)
class PolicyFoundationEvidenceExport:
    output_dir: Path
    archive_path: Path
    manifest_path: Path


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _dependencies() -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    for name in ("numpy", "scipy", "cirq-core", "openfermion", "pyqasm", "ply", "fastapi", "gradio"):
        try:
            out[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            out[name] = None
    return out


def _foundation() -> dict[str, str]:
    return {
        "wp0": baseline_fingerprint(),
        "wp1": vocabulary_fingerprint(),
        "wp2": policy_contract_catalog_fingerprint(),
        "wp3": implementation_binding_catalog_fingerprint(),
        "wp4": compatibility_rule_catalog_fingerprint(),
        "wp5": realization_resolver_catalog_fingerprint(),
        "wp6": acceptance_fingerprint_catalog_fingerprint(),
        "wp7": acceptance_harness_catalog_fingerprint(),
    }


def _source_fingerprints(project_root: Path) -> dict[str, str]:
    paths = (
        "qcol/acceptance/fingerprint.py",
        "qcol/acceptance/fingerprint_fixtures.py",
        "qcol/acceptance/fingerprint_catalog.py",
        "qcol/acceptance/harness.py",
        "qcol/acceptance/harness_fixtures.py",
        "qcol/acceptance/harness_catalog.py",
        "qcol/acceptance/policy_foundation_evidence.py",
        "qcol/acceptance/tolerance_profiles.py",
        "qcol/api.py",
        "qcol/catalog.py",
        "qcol/__init__.py",
    )
    return {relative: _sha(project_root / relative) for relative in paths if (project_root / relative).exists()}


def _finalize(output_dir: Path, manifest: dict[str, Any]) -> tuple[Path, Path]:
    files = sorted(path for path in output_dir.rglob("*") if path.is_file() and path.name != "manifest.json")
    manifest["files"] = [
        {"name": str(path.relative_to(output_dir)).replace("\\", "/"), "sha256": _sha(path), "size_bytes": path.stat().st_size}
        for path in files
    ]
    manifest_path = output_dir / "manifest.json"
    _write_json(manifest_path, manifest)
    archive_path = Path(shutil.make_archive(str(output_dir), "zip", root_dir=output_dir))
    return archive_path, manifest_path


def export_acceptance_fingerprint_evidence(
    output: str | Path,
    *,
    project_root: str | Path | None = None,
) -> AcceptanceFingerprintEvidenceExport:
    root = Path(project_root or Path(__file__).resolve().parents[2]).resolve()
    output_dir = Path(output).resolve()
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    catalog = public_acceptance_fingerprint_catalog()
    checks = validate_acceptance_fingerprint_catalog(catalog)
    if not all(checks.values()):
        raise AssertionError("WP6 fingerprint validation failed: " + ", ".join(k for k, v in checks.items() if not v))
    _write_json(output_dir / "acceptance_fingerprint_catalog.json", catalog)
    _write_json(output_dir / "fingerprint_validation.json", checks)
    _write_json(output_dir / "exact_current_fingerprint.json", catalog["current_fingerprint"])
    _write_json(output_dir / "exact_acceptance_record.json", catalog["acceptance_record"])
    _write_json(output_dir / "exact_match_report.json", catalog["exact_match_report"])
    _write_json(output_dir / "staleness_scenarios.json", catalog["staleness_scenarios"])
    _write_json(output_dir / "four_mode_vs_twenty_mode.json", catalog["four_mode_cannot_promote_twenty_mode"])
    _write_json(output_dir / "foundation_fingerprints.json", _foundation())
    _write_json(output_dir / "dependency_versions.json", _dependencies())
    _write_json(output_dir / "source_fingerprints.json", _source_fingerprints(root))
    archive, manifest = _finalize(output_dir, {
        "schema_version": "qcol-wp6-acceptance-fingerprint-evidence/1.0",
        "phase": "Phase A.3.2a",
        "work_package": "WP6 — Acceptance Evidence Fingerprint",
        "project_version": __version__,
        "catalog_fingerprint": acceptance_fingerprint_catalog_fingerprint(catalog),
        "stable_stale_code": "ACCEPTANCE_EVIDENCE_STALE",
        "live_policy_migration_performed": False,
        "scientific_behavior_change": False,
        "second_runtime_created": False,
        "exit_statement": "Every acceptance claim is tied to one exact composition, dependency set, and declared scale; any relevant change makes the evidence stale.",
    })
    return AcceptanceFingerprintEvidenceExport(output_dir, archive, manifest)


def export_acceptance_harness_evidence(
    output: str | Path,
    *,
    project_root: str | Path | None = None,
) -> AcceptanceHarnessEvidenceExport:
    root = Path(project_root or Path(__file__).resolve().parents[2]).resolve()
    output_dir = Path(output).resolve()
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    catalog = public_acceptance_harness_catalog()
    checks = validate_acceptance_harness_catalog(catalog)
    if not all(checks.values()):
        raise AssertionError("WP7 harness validation failed: " + ", ".join(k for k, v in checks.items() if not v))
    _write_json(output_dir / "acceptance_harness_catalog.json", catalog)
    _write_json(output_dir / "harness_validation.json", checks)
    _write_json(output_dir / "execution_gate_contracts.json", catalog["execution_gate_contracts"])
    _write_json(output_dir / "analysis_gate_contracts.json", catalog["analysis_gate_contracts"])
    _write_json(output_dir / "tolerance_profile_registry.json", catalog["tolerance_profile_registry"])
    _write_json(output_dir / "baseline_classifications.json", catalog["baseline_classifications"])
    _write_json(output_dir / "baseline_status_preservation.json", catalog["baseline_status_preservation"])
    _write_json(output_dir / "a3_2a_exit_checks.json", catalog["a3_2a_exit_checks"])
    _write_json(output_dir / "foundation_fingerprints.json", _foundation())
    _write_json(output_dir / "dependency_versions.json", _dependencies())
    _write_json(output_dir / "source_fingerprints.json", _source_fingerprints(root))
    archive, manifest = _finalize(output_dir, {
        "schema_version": "qcol-wp7-generic-acceptance-harness-evidence/1.0",
        "phase": "Phase A.3.2a",
        "work_package": "WP7 — Generic Three-Gate Acceptance Harness",
        "project_version": __version__,
        "catalog_fingerprint": acceptance_harness_catalog_fingerprint(catalog),
        "a3_2a_exit_ready": catalog["a3_2a_exit_ready"],
        "live_policy_migration_performed": False,
        "scientific_status_promoted": False,
        "scientific_behavior_change": False,
        "second_runtime_created": False,
        "exit_statement": "The generic mapper/composition/cell harness classifies all frozen baseline variants using exact versioned tolerance profiles and matching evidence fingerprints.",
    })
    return AcceptanceHarnessEvidenceExport(output_dir, archive, manifest)


def export_policy_foundation_evidence(
    output: str | Path,
    *,
    project_root: str | Path | None = None,
) -> PolicyFoundationEvidenceExport:
    root = Path(project_root or Path(__file__).resolve().parents[2]).resolve()
    output_dir = Path(output).resolve()
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    wp6 = public_acceptance_fingerprint_catalog()
    wp7 = public_acceptance_harness_catalog()
    checks6 = validate_acceptance_fingerprint_catalog(wp6)
    checks7 = validate_acceptance_harness_catalog(wp7)
    if not all(checks6.values()) or not all(checks7.values()):
        raise AssertionError("Phase A.3.2a policy-foundation evidence cannot be exported before WP6/WP7 validation passes.")
    _write_json(output_dir / "wp6_acceptance_fingerprint_catalog.json", wp6)
    _write_json(output_dir / "wp7_acceptance_harness_catalog.json", wp7)
    _write_json(output_dir / "wp6_validation.json", checks6)
    _write_json(output_dir / "wp7_validation.json", checks7)
    _write_json(output_dir / "a3_2a_exit_checks.json", wp7["a3_2a_exit_checks"])
    _write_json(output_dir / "all_foundation_fingerprints.json", _foundation())
    _write_json(output_dir / "dependency_versions.json", _dependencies())
    _write_json(output_dir / "source_fingerprints.json", _source_fingerprints(root))
    archive, manifest = _finalize(output_dir, {
        "schema_version": "qcol-phase-a3.2a-policy-foundation-evidence/1.0",
        "phase": "Phase A.3.2a",
        "work_packages": ["WP0", "WP1", "WP2", "WP3", "WP4", "WP5", "WP6", "WP7"],
        "project_version": __version__,
        "wp6_catalog_fingerprint": acceptance_fingerprint_catalog_fingerprint(wp6),
        "wp7_catalog_fingerprint": acceptance_harness_catalog_fingerprint(wp7),
        "a3_2a_exit_ready": wp7["a3_2a_exit_ready"],
        "live_policy_migration_performed": False,
        "scientific_status_promoted": False,
        "scientific_behavior_change": False,
        "second_runtime_created": False,
        "next_phase": "Phase A.3.2b — Policy Migration (WP8–WP10)",
        "exit_statement": "Policy Foundation is complete: baseline, vocabulary, declarative contracts, exact bindings, relation rules, resolver reports, exact evidence fingerprints, and the generic three-gate harness are operational without changing accepted scientific behavior.",
    })
    return PolicyFoundationEvidenceExport(output_dir, archive, manifest)


__all__ = [
    "AcceptanceFingerprintEvidenceExport",
    "AcceptanceHarnessEvidenceExport",
    "PolicyFoundationEvidenceExport",
    "export_acceptance_fingerprint_evidence",
    "export_acceptance_harness_evidence",
    "export_policy_foundation_evidence",
]

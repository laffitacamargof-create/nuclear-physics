"""WP2 evidence exporter for declarative mapping-realization policy contracts."""
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
from qcol.mapping_policies import vocabulary_fingerprint
from qcol.policy_contract_catalog import (
    policy_contract_catalog_fingerprint,
    public_declarative_policy_contract_catalog,
    validate_declarative_policy_contracts,
)


@dataclass(frozen=True)
class PolicyContractEvidenceExport:
    output_dir: Path
    archive_path: Path
    manifest_path: Path


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _dependency_versions() -> dict[str, str | None]:
    result: dict[str, str | None] = {}
    for name in ("numpy", "scipy", "cirq-core", "openfermion", "pyqasm", "fastapi", "gradio"):
        try:
            result[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            result[name] = None
    return result


def _source_fingerprints(project_root: Path) -> dict[str, str]:
    paths = (
        "qcol/mapping_policies/contracts.py",
        "qcol/mapping_policies/enums.py",
        "qcol/mapping_policies/primitives.py",
        "qcol/realization_policies/base.py",
        "qcol/realization_policies/ordering.py",
        "qcol/realization_policies/sector.py",
        "qcol/realization_policies/state_preparation.py",
        "qcol/realization_policies/ansatz.py",
        "qcol/realization_policies/measurement.py",
        "qcol/realization_policies/reference.py",
        "qcol/realization_policies/verification.py",
        "qcol/acceptance/tolerance_profiles.py",
        "qcol/policy_contract_catalog.py",
        "qcol/api.py",
        "qcol/catalog.py",
    )
    return {
        relative: _sha(project_root / relative)
        for relative in paths
        if (project_root / relative).exists()
    }


def export_policy_contract_evidence(
    output: str | Path,
    *,
    project_root: str | Path | None = None,
) -> PolicyContractEvidenceExport:
    root = Path(project_root or Path(__file__).resolve().parents[2]).resolve()
    output_dir = Path(output).resolve()
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    catalog = public_declarative_policy_contract_catalog()
    validation = validate_declarative_policy_contracts(catalog)
    if not all(validation.values()):
        failed = [key for key, value in validation.items() if not value]
        raise AssertionError("WP2 policy-contract validation failed: " + ", ".join(failed))

    _write_json(output_dir / "declarative_policy_contract_catalog.json", catalog)
    _write_json(output_dir / "contract_validation.json", validation)
    _write_json(
        output_dir / "contract_fingerprints.json",
        {
            "schema_version": "qcol-wp2-contract-fingerprints/1.0",
            "wp2_contract_catalog_fingerprint": policy_contract_catalog_fingerprint(catalog),
            "wp1_vocabulary_fingerprint": vocabulary_fingerprint(),
            "wp0_baseline_fingerprint": baseline_fingerprint(),
            "scientific_behavior_change": False,
        },
    )
    _write_json(output_dir / "dependency_versions.json", _dependency_versions())
    _write_json(output_dir / "source_fingerprints.json", _source_fingerprints(root))

    files = sorted(path for path in output_dir.iterdir() if path.is_file())
    manifest = {
        "schema_version": "qcol-wp2-declarative-policy-contract-evidence/1.0",
        "phase": "Phase A.3.2a",
        "work_package": "WP2 — Declarative Policy Contracts",
        "project_version": __version__,
        "scientific_behavior_change": False,
        "wp0_baseline_fingerprint": baseline_fingerprint(),
        "wp1_vocabulary_fingerprint": vocabulary_fingerprint(),
        "wp2_contract_catalog_fingerprint": policy_contract_catalog_fingerprint(catalog),
        "contracts_are_executable": False,
        "live_policy_migration_performed": False,
        "files": [
            {"name": path.name, "sha256": _sha(path), "size_bytes": path.stat().st_size}
            for path in files
        ],
        "exit_statement": (
            "Declarative contracts are frozen, strict-JSON, capability-based, and free of Python callables; "
            "WP0/WP1 fingerprints and scientific runtime behaviour are unchanged."
        ),
    }
    manifest_path = output_dir / "manifest.json"
    _write_json(manifest_path, manifest)
    archive_path = Path(shutil.make_archive(str(output_dir), "zip", root_dir=output_dir))
    return PolicyContractEvidenceExport(output_dir, archive_path, manifest_path)


__all__ = ["PolicyContractEvidenceExport", "export_policy_contract_evidence"]

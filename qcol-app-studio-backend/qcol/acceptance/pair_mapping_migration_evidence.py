"""Evidence exporter for WP8 Pair Mapping policy migration."""
from __future__ import annotations

from dataclasses import dataclass
from importlib import metadata
import hashlib
import json
from pathlib import Path
import shutil
from typing import Any, Mapping

from qcol import __version__
from qcol.acceptance.mapping_baseline import baseline_fingerprint
from qcol.compatibility import compatibility_rule_catalog_fingerprint
from qcol.implementation_bindings import implementation_binding_catalog_fingerprint
from qcol.mapping_policies import vocabulary_fingerprint
from qcol.policy_contract_catalog import policy_contract_catalog_fingerprint
from qcol.realization_variants import realization_resolver_catalog_fingerprint
from qcol.acceptance import (
    acceptance_fingerprint_catalog_fingerprint,
    acceptance_harness_catalog_fingerprint,
)


@dataclass(frozen=True)
class PairMappingMigrationEvidenceExport:
    output_dir: Path
    archive_path: Path
    manifest_path: Path
    scientific_checks_included: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "output_dir": str(self.output_dir),
            "archive_path": str(self.archive_path),
            "manifest_path": str(self.manifest_path),
            "scientific_checks_included": self.scientific_checks_included,
        }


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _dependencies() -> dict[str, str | None]:
    names = ("numpy", "scipy", "cirq-core", "openfermion", "pyqasm", "ply", "fastapi", "gradio")
    result: dict[str, str | None] = {}
    for name in names:
        try:
            result[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            result[name] = None
    return result


def _foundation_fingerprints() -> dict[str, str]:
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
        "qcol/mapping_policies/profiles/pair_mapping.py",
        "qcol/mapping_policies/profiles/pair_bindings.py",
        "qcol/models/reduced_pairing_common.py",
        "qcol/models/reduced_pairing_one_pair/contract.py",
        "qcol/models/reduced_pairing_multi_pair/contract.py",
        "qcol/builtin_policies.py",
        "qcol/catalog.py",
        "qcol/api.py",
        "qcol/__init__.py",
    )
    return {
        relative: _sha(project_root / relative)
        for relative in paths
        if (project_root / relative).exists()
    }


def collect_pair_mapping_scientific_regressions() -> dict[str, Any]:
    """Run accepted one-pair and experimental multi-pair live routes."""
    from qcol.contracts import json_safe
    from qcol.models.reduced_pairing_one_pair import (
        acceptance_request,
        assert_one_pair_regression,
        build_one_pair_quantum_realization,
    )
    from qcol.models.reduced_pairing_multi_pair.acceptance import assess_multi_pair_artifact
    from qcol.model_instance_adapters import instance_from_request
    from qcol.resolver import resolve_model
    from qcol.realization import build_quantum_realization
    from qcol.orchestrator import run_pipeline

    one_request = acceptance_request()
    one_realization = build_one_pair_quantum_realization(one_request)
    one_realization.validate_bridge()
    one_report = assert_one_pair_regression(one_realization.runtime_artifact)

    multi_request = {
        "method": "fermion_pairing",
        "problem": "multi_pair_seniority_zero",
        "parameters": {
            "n_levels": 4,
            "epsilon": [0.0, 1.0, 2.0, 3.0],
            "g": 0.5,
            "n_pairs": 2,
            "n_particles": 4,
            "seniority": 0,
            "mapping": "pair_mapping",
            "energy_unit": "MeV",
        },
        "target_backend": "ibm",
        "execution_mode": "local_simulator",
        "run_mode": "single_evaluation",
        "shots": 256,
        "seed": 17,
        "acceptance_abs_floor": 0.15,
    }
    instance = instance_from_request(multi_request)
    plan = resolve_model(instance, request_metadata=multi_request)
    realization = build_quantum_realization(plan, request_metadata=multi_request)
    realization.validate_bridge()
    multi_structural = assess_multi_pair_artifact(realization.runtime_artifact)
    artifact, result = run_pipeline(multi_request)

    return json_safe({
        "schema_version": "qcol-wp8-pair-scientific-regressions/1.0",
        "one_pair": {
            "status": "acceptance_verified",
            "mapping_policy_id": one_realization.mapping_metadata.get("policy_id"),
            "regression": one_report.to_dict(),
        },
        "multi_pair": {
            "status": "experimental",
            "mapping_policy_id": realization.mapping_metadata.get("policy_id"),
            "structural_report": multi_structural.to_dict(),
            "runtime_status": result.status,
            "run_mode": result.run_mode,
            "hardware_submission_performed": result.hardware_submission_performed,
            "artifact_model_id": artifact.model_id,
        },
        "scientific_status_promoted": False,
        "scientific_behavior_change": False,
    })


def export_pair_mapping_migration_evidence(
    output: str | Path,
    *,
    include_scientific_checks: bool = False,
    project_root: str | Path | None = None,
) -> PairMappingMigrationEvidenceExport:
    from qcol.mapping_policies.profiles import (
        pair_mapping_migration_catalog_fingerprint,
        public_pair_mapping_migration_catalog,
        validate_pair_mapping_migration,
    )

    root = Path(project_root or Path(__file__).resolve().parents[2]).resolve()
    output_dir = Path(output).resolve()
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    catalog = public_pair_mapping_migration_catalog()
    checks = validate_pair_mapping_migration(catalog)
    if not all(checks.values()):
        failed = [key for key, value in checks.items() if not value]
        raise AssertionError("WP8 Pair Mapping migration validation failed: " + ", ".join(failed))

    _write_json(output_dir / "pair_mapping_migration_catalog.json", catalog)
    _write_json(output_dir / "migration_validation.json", checks)
    _write_json(output_dir / "pair_mapping_profile.json", catalog["profile"])
    _write_json(output_dir / "pair_mapping_policy_contracts.json", catalog["contracts"])
    _write_json(output_dir / "pair_mapping_binding_registry.json", catalog["binding_registry"])
    _write_json(output_dir / "one_pair_resolution.json", catalog["resolutions"]["one_pair"])
    _write_json(output_dir / "multi_pair_resolution.json", catalog["resolutions"]["multi_pair"])
    _write_json(output_dir / "one_pair_three_gate_acceptance.json", catalog["acceptance_harness"]["one_pair"])
    _write_json(output_dir / "multi_pair_three_gate_acceptance.json", catalog["acceptance_harness"]["multi_pair"])
    _write_json(output_dir / "status_preservation.json", catalog["status_preservation"])
    _write_json(output_dir / "foundation_fingerprints.json", _foundation_fingerprints())
    _write_json(output_dir / "dependency_versions.json", _dependencies())
    _write_json(output_dir / "source_fingerprints.json", _source_fingerprints(root))

    if include_scientific_checks:
        _write_json(output_dir / "scientific_regressions.json", collect_pair_mapping_scientific_regressions())

    files = sorted(path for path in output_dir.rglob("*") if path.is_file() and path.name != "manifest.json")
    manifest: dict[str, Any] = {
        "schema_version": "qcol-wp8-pair-mapping-migration-evidence/1.0",
        "phase": "Phase A.3.2b",
        "work_package": "WP8 — Migrate Pair Mapping",
        "project_version": __version__,
        "catalog_fingerprint": pair_mapping_migration_catalog_fingerprint(catalog),
        "mapping_scope": "restricted_seniority_zero_subspace",
        "preserved_algebra": "quasispin / hard-core-pair algebra",
        "one_pair_status": "acceptance_verified",
        "multi_pair_status": "experimental",
        "live_policy_migration_performed": True,
        "scientific_status_promoted": False,
        "scientific_behavior_change": False,
        "second_runtime_created": False,
        "scientific_checks_included": include_scientific_checks,
        "files": [
            {
                "name": str(path.relative_to(output_dir)).replace("\\", "/"),
                "sha256": _sha(path),
                "size_bytes": path.stat().st_size,
            }
            for path in files
        ],
        "exit_statement": (
            "Pair Mapping is migrated as a restricted seniority-zero pair-occupation policy. "
            "One-pair remains the accepted regression anchor and multi-pair remains experimental."
        ),
    }
    manifest_path = output_dir / "manifest.json"
    _write_json(manifest_path, manifest)
    archive_path = Path(shutil.make_archive(str(output_dir), "zip", root_dir=output_dir))
    return PairMappingMigrationEvidenceExport(output_dir, archive_path, manifest_path, include_scientific_checks)


__all__ = [
    "PairMappingMigrationEvidenceExport",
    "collect_pair_mapping_scientific_regressions",
    "export_pair_mapping_migration_evidence",
]

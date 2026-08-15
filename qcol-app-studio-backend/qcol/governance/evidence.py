"""Deterministic WP13 governance and Phase B handoff evidence export."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from qcol.realization_policies.base import contract_fingerprint, json_contract_value

from .catalog import (
    A32C_RELEASE_ID,
    WP13_PROJECT_VERSION,
    build_a3_2c_release_decision,
    build_phase_b_handoff_contract,
    governance_catalog_fingerprint,
    public_governance_catalog,
    validate_wp13_governance_catalog,
)
from .contracts import GovernanceReleaseManifest
from .patches import (
    allowed_request_patch_registry_fingerprint,
    public_allowed_request_patch_registry,
)


WP13_EVIDENCE_SCHEMA_VERSION = "qcol-wp13-governance-release-evidence/1.0"
WP13_EVIDENCE_ARCHIVE_ID = "qcol.wp13.governance.release.evidence.v1"
_FORBIDDEN_EXTENSIONS = (".pkl", ".pickle", ".joblib", ".dill")


@dataclass(frozen=True)
class ExportedWP13Evidence:
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
        "qcol/governance/enums.py",
        "qcol/governance/contracts.py",
        "qcol/governance/patches.py",
        "qcol/governance/catalog.py",
        "qcol/governance/evidence.py",
        "qcol/governance/__init__.py",
        "qcol/compatibility/report.py",
        "qcol/realization_variants/contracts.py",
        "qcol/acceptance/fingerprint.py",
        "qcol/acceptance/harness.py",
        "qcol/catalog.py",
        "qcol/api.py",
        "qcol/web/index.html",
    )
    fingerprints: dict[str, str] = {}
    for relative in relative_paths:
        path = root / relative
        if path.exists():
            fingerprints[relative] = contract_fingerprint(
                {"source": path.read_text(encoding="utf-8")}
            )
    return fingerprints


def build_wp13_release_manifest() -> GovernanceReleaseManifest:
    catalog = public_governance_catalog()
    release = build_a3_2c_release_decision()
    governed_assets = catalog["governed_assets"]
    schema_versions = {
        "governance_catalog": catalog["schema_version"],
        "phase_b_handoff": catalog["phase_b_handoff"]["schema_version"],
        "release_decision": release.schema_version,
        "request_patch_registry": catalog["allowed_request_patch_registry"]["schema_version"],
        "published_status": (
            None if not catalog["published_statuses"] else catalog["published_statuses"][0]["schema_version"]
        ),
    }
    implementation_versions = {
        item["asset_id"]: item["implementation_version"]
        for item in governed_assets
        if item.get("implementation_version") is not None
    }
    return GovernanceReleaseManifest(
        manifest_id="qcol.wp13.governed-release-manifest.v1",
        manifest_version="1.0.0",
        project_version=WP13_PROJECT_VERSION,
        governance_catalog_fingerprint=governance_catalog_fingerprint(),
        allowed_patch_registry_fingerprint=allowed_request_patch_registry_fingerprint(),
        release_decision_fingerprint=release.fingerprint(),
        schema_versions=schema_versions,
        implementation_versions=implementation_versions,
        evidence_archive_id=WP13_EVIDENCE_ARCHIVE_ID,
        evidence_reproducible=True,
        callable_payload_withheld=True,
        python_pickling_used=False,
        second_runtime_created=False,
    )


def export_wp13_governance_evidence(
    output_directory: str | Path,
    *,
    project_root: str | Path | None = None,
) -> ExportedWP13Evidence:
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)

    catalog = public_governance_catalog()
    validation = validate_wp13_governance_catalog()
    release = build_a3_2c_release_decision()
    handoff = build_phase_b_handoff_contract()
    patch_registry = public_allowed_request_patch_registry()
    release_manifest = build_wp13_release_manifest()

    files: dict[str, Any] = {
        "governance_catalog.json": catalog,
        "scientific_owners.json": {
            "schema_version": "qcol-scientific-owner-registry/1.0",
            "owners": catalog["scientific_owners"],
        },
        "governed_assets.json": {
            "schema_version": "qcol-governed-asset-registry/1.0",
            "assets": catalog["governed_assets"],
        },
        "acceptance_evidence_ownership.json": {
            "schema_version": "qcol-acceptance-evidence-ownership-registry/1.0",
            "records": catalog["acceptance_evidence_ownership"],
        },
        "deprecation_rules.json": {
            "schema_version": "qcol-deprecation-rule-registry/1.0",
            "rules": catalog["deprecation_rules"],
        },
        "migration_rules.json": {
            "schema_version": "qcol-migration-rule-registry/1.0",
            "rules": catalog["migration_rules"],
        },
        "published_scientific_statuses.json": {
            "schema_version": "qcol-published-status-registry/1.0",
            "records": catalog["published_statuses"],
            "unqualified_mapping_verified_badge_allowed": False,
        },
        "allowed_request_patch_registry.json": patch_registry,
        "phase_b_handoff.json": handoff.to_dict(),
        "a3_2c_release_decision.json": release.to_dict(),
        "wp13_validation.json": validation,
        "foundation_fingerprints.json": catalog["foundation_fingerprints"],
        "release_manifest.json": release_manifest.to_dict(),
    }
    for name, payload in files.items():
        _write_json(output / name, payload)

    source_fingerprints = _source_fingerprints(project_root)
    _write_json(output / "source_fingerprints.json", source_fingerprints)

    archive_manifest = {
        "schema_version": WP13_EVIDENCE_SCHEMA_VERSION,
        "archive_id": WP13_EVIDENCE_ARCHIVE_ID,
        "release_id": A32C_RELEASE_ID,
        "project_version": WP13_PROJECT_VERSION,
        "governance_catalog_fingerprint": governance_catalog_fingerprint(),
        "allowed_request_patch_registry_fingerprint": allowed_request_patch_registry_fingerprint(),
        "release_decision_fingerprint": release.fingerprint(),
        "validation_passed": all(validation.values()),
        "phase_a3_2c_exit_ready": release.phase_a3_2c_exit_ready,
        "phase_b_handoff_ready": release.phase_b_handoff_ready,
        "phase_b_advisor_runtime_implemented": False,
        "evidence_reproducible": True,
        "strict_json": True,
        "python_pickling_used": False,
        "callable_payload_withheld": True,
        "second_runtime_created": False,
        "forbidden_extensions": list(_FORBIDDEN_EXTENSIONS),
        "files": sorted([*files.keys(), "source_fingerprints.json", "manifest.json"]),
    }
    manifest_path = output / "manifest.json"
    _write_json(manifest_path, archive_manifest)

    archive = output.with_suffix(".zip")
    with ZipFile(archive, "w", compression=ZIP_DEFLATED, compresslevel=9) as bundle:
        for path in sorted(output.iterdir()):
            if not path.is_file():
                continue
            if path.suffix.lower() in _FORBIDDEN_EXTENSIONS:
                raise RuntimeError(f"WP13 Evidence cannot contain pickle file {path.name!r}.")
            info = ZipInfo(filename=path.name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            bundle.writestr(
                info,
                path.read_bytes(),
                compress_type=ZIP_DEFLATED,
                compresslevel=9,
            )
    return ExportedWP13Evidence(
        output_directory=output,
        archive_path=archive,
        manifest_path=manifest_path,
    )


__all__ = [
    "WP13_EVIDENCE_SCHEMA_VERSION",
    "WP13_EVIDENCE_ARCHIVE_ID",
    "ExportedWP13Evidence",
    "build_wp13_release_manifest",
    "export_wp13_governance_evidence",
]

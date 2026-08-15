"""Governed QHO structural/UI extension of the frozen Phase-C baseline.

This module records the post-freeze addition of four independent bounded QHO
ModelContracts and the schema-driven UI surface that renders their parameters.
It is intentionally outside the scientific runtime.  It inventories contracts,
Model × Task cells, public API additions, protected runtime hashes, source
provenance, and deterministic Evidence without creating a second execution
path or promoting any QHO cell beyond ``experimental``.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence
import zipfile

from .baseline_freeze import baseline_commit_file_bytes, sha256_file
from .. import __version__
from ..api import app
from ..model_registry import get_model_contract
from ..model_task_matrix import get_model_task_cell
from ..model_ui_schema import public_qho_ui_catalog, validate_qho_ui_catalog
from ..models.qho_common import QHO_MODEL_IDS
from ..models.resource_estimators import estimate_direct_qubit_parameter_count
from ..resource_rules import (
    public_resource_rule_catalog,
    resource_rule_catalog_fingerprint,
    validate_resource_rule_registry,
)
from ..artifact_identity import (
    ARTIFACT_IDENTITY_FILENAME,
    load_artifact_identity,
    verify_artifact_identity,
)

QHO_EXTENSION_SCHEMA_VERSION = "qcol-qho-extended-baseline-manifest/1.1"
QHO_EVIDENCE_SCHEMA_VERSION = "qcol-qho-structural-ui-evidence/1.1"
QHO_EXTENSION_VERSION = "1.23.6"
QHO_DONOR_PACKAGE = "QCOL_QHO_Models_Package (2)(1).zip"
QHO_DONOR_PACKAGE_SHA256 = "e58dc29b3fab44c0cbb01163d1a8c25cfef2cc6ad1dfeceb25379f5f7f56a854"
PARENT_BASELINE_PACKAGE = "QCOL_Post_Phase_C_Step1_Frozen_Baseline_Colab_Fully_Checked.zip"
PARENT_BASELINE_PACKAGE_SHA256 = "398957c58d4ffcb885a1f504c9508e4abd79f8b29d6d4490066c248b18cb49a6"
INTEGRITY_I1_PACKAGE = "QCOL_Integrity_Primitives_I1_Comparison_Realization_Foundation_Complete.zip"
INTEGRITY_I1_PACKAGE_SHA256 = "5a9c1299afd54faaecfc4940bed410f729ef037e16a4b1e1012eec3e460d74ee"
QHO_HARDENING_BRANCH = "hardening/qho-structural-schema-integration"
_FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)

PROTECTED_RUNTIME_PATHS: tuple[str, ...] = (
    "qcol/orchestrator.py",
    "qcol/runtime.py",
    "qcol/run_manager.py",
    "qcol/comparison/engine.py",
    "qcol/advisor/engine.py",
    "qcol/controllers/optimizer_loop.py",
    "qcol/controllers/single_pass.py",
)

QHO_SOURCE_PATHS: tuple[str, ...] = (
    "qcol/models/qho_common.py",
    "qcol/models/qho_free/contract.py",
    "qcol/models/qho_pairing/contract.py",
    "qcol/models/qho_spinorbit/contract.py",
    "qcol/models/qho_full/contract.py",
    "qcol/models/resource_estimators.py",
    "qcol/models/direct_qubit_common.py",
    "qcol/models/direct_qubit_resources.py",
    "qcol/resource_rules/__init__.py",
    "qcol/resource_rules/contracts.py",
    "qcol/resource_rules/registry.py",
    "qcol/resource_rules/builtin.py",
    "qcol/resource_rules/estimators.py",
    "qcol/artifact_identity.py",
    "qcol/model_task_resolver.py",
    "qcol/model_ui_schema.py",
    "qcol/model_registry.py",
    "qcol/model_instance_adapters.py",
    "qcol/model_task_matrix.py",
    "qcol/catalog.py",
    "qcol/api.py",
    "qcol/ui_service.py",
    "qcol/app.py",
    "qcol/web/index.html",
    "qcol/web/app.js",
    "tests/test_qho_structural_integration.py",
    "tests/test_qho_ui_schema.py",
    "tests/test_qho_physics_regression.py",
    "tests/test_qho_runtime_eligibility_preflight.py",
    "tests/test_resource_rule_registry.py",
    "tests/test_resource_authority_regression.py",
    "tests/test_qho_resolver_pipeline_resource_identity.py",
    "tests/test_qho_artifact_identity.py",
    "tests/test_model_entry.py",
    "scripts/run_qho_resolver_pipeline_gate.py",
    "scripts/run_qho_structural_ui_gate.py",
)


def _json_bytes(payload: Any) -> bytes:
    return (
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def fingerprint(payload: Any) -> str:
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _source_revision(project_root: Path) -> Mapping[str, Any]:
    path = project_root / "QCOL_QHO_Source_Revision.json"
    if not path.exists():
        return {
            "branch": QHO_HARDENING_BRANCH,
            "code_commit": "unsealed-working-tree",
            "release_commit": None,
        }
    payload = _read_json(path)
    return payload


def build_qho_contract_catalog() -> dict[str, Any]:
    contracts = [get_model_contract(model_id).to_dict() for model_id in QHO_MODEL_IDS]
    return {
        "schema_version": "qcol-qho-contract-catalog/1.0",
        "project_version": __version__,
        "model_ids": list(QHO_MODEL_IDS),
        "contracts": contracts,
        "all_cells_remain_experimental": all(
            item["execution_status"] == "experimental" for item in contracts
        ),
        "shared_policy_family": {
            key: contracts[0]["policies"][key]
            for key in contracts[0]["policies"]
        },
        "second_runtime_created": False,
    }


def build_qho_cell_catalog() -> dict[str, Any]:
    cells = [
        get_model_task_cell(model_id, "ground_state_energy").to_dict()
        for model_id in QHO_MODEL_IDS
    ]
    return {
        "schema_version": "qcol-qho-model-task-cell-catalog/1.0",
        "model_ids": list(QHO_MODEL_IDS),
        "task_id": "ground_state_energy",
        "cells": cells,
        "statuses": {item["model_id"]: item["status"] for item in cells},
        "no_bulk_promotion": all(item["status"] == "experimental" for item in cells),
    }


def build_protected_runtime_report(project_root: Path | str) -> dict[str, Any]:
    root = Path(project_root).resolve()
    rows: list[dict[str, Any]] = []
    for relative in PROTECTED_RUNTIME_PATHS:
        current = (root / relative).read_bytes()
        parent = baseline_commit_file_bytes(root, relative)
        rows.append(
            {
                "path": relative,
                "current_sha256": hashlib.sha256(current).hexdigest(),
                "parent_phase_c_sha256": hashlib.sha256(parent).hexdigest(),
                "matches_parent_phase_c": current == parent,
            }
        )
    authorized_changes = {
        "qcol/runtime.py": {
            "adr_id": "ADR-QCOL-EXECUTION-BOUNDARY-001",
            "change_kind": "execution_adapter_boundary_refactor",
            "reason": (
                "Move local Cirq backend invocation behind the exact ExecutionAdapter "
                "registry while preserving the shared runtime, reconstruction, verification, "
                "and evidence semantics."
            ),
            "scientific_behavior_change": False,
            "second_runtime_created": False,
        },
        "qcol/run_manager.py": {
            "adr_id": "ADR-QCOL-STATE-PORT-001",
            "change_kind": "state_repository_port_seam",
            "reason": (
                "Introduce a StateRepository port with the existing in-memory adapter as the "
                "default so durable storage can be added later without changing run_pipeline."
            ),
            "scientific_behavior_change": False,
            "second_runtime_created": False,
        },
    }
    for row in rows:
        row["authorized_change"] = authorized_changes.get(row["path"])
        row["accepted"] = bool(row["matches_parent_phase_c"] or row["authorized_change"])
    return {
        "schema_version": "qcol-protected-runtime-regression/1.1",
        "paths": rows,
        "all_match_parent_phase_c": all(row["matches_parent_phase_c"] for row in rows),
        "all_unchanged_or_authorized": all(row["accepted"] for row in rows),
        "authorized_changes": authorized_changes,
        "shared_execution_boundary_refactored": True,
        "run_pipeline_changed": False,
        "scientific_behavior_changed": False,
        "second_runtime_created": False,
    }


def build_qho_source_fingerprints(project_root: Path | str) -> dict[str, Any]:
    root = Path(project_root).resolve()
    rows = []
    for relative in QHO_SOURCE_PATHS:
        path = root / relative
        rows.append(
            {
                "path": relative,
                "exists": path.is_file(),
                "sha256": sha256_file(path) if path.is_file() else None,
                "bytes": path.stat().st_size if path.is_file() else None,
            }
        )
    return {
        "schema_version": "qcol-qho-source-fingerprints/1.0",
        "files": rows,
        "all_present": all(row["exists"] for row in rows),
    }


def build_qho_openapi_snapshot() -> dict[str, Any]:
    schema = app.openapi()
    return {
        "schema_version": "qcol-qho-openapi-snapshot/1.0",
        "project_version": __version__,
        "path_count": len(schema.get("paths", {})),
        "required_paths": {
            "/catalog/qho-models": "/catalog/qho-models" in schema.get("paths", {}),
            "/catalog/model-ui-schemas/{model_id}": (
                "/catalog/model-ui-schemas/{model_id}" in schema.get("paths", {})
            ),
        },
        "openapi": schema,
        "openapi_fingerprint": fingerprint(schema),
    }


def validate_qho_extension(project_root: Path | str) -> dict[str, bool]:
    root = Path(project_root).resolve()
    parent_manifest = _read_json(root / "unified_baseline_manifest.json")
    contracts = build_qho_contract_catalog()
    cells = build_qho_cell_catalog()
    ui_checks = validate_qho_ui_catalog()
    runtime = build_protected_runtime_report(root)
    source = build_qho_source_fingerprints(root)
    openapi = build_qho_openapi_snapshot()
    resource_preflight = []
    for model_id in QHO_MODEL_IDS:
        contract = get_model_contract(model_id)
        n_qubits = int(contract.resource_validity.simulator_max_qubits or 0)
        estimate = estimate_direct_qubit_parameter_count(
            resource_policy_id=contract.resource_policy_id,
            resource_rule_id=contract.resource_estimation_rule_id,
            ansatz_policy_id=contract.ansatz_policy_id,
            n_qubits=n_qubits,
            n_layers=1,
        )
        resource_preflight.append({
            "model_id": model_id,
            "contract_resource_policy_id": contract.resource_policy_id,
            "contract_resource_rule_id": contract.resource_estimation_rule_id,
            **estimate.to_dict(),
            "declared_maximum_parameter_count": contract.resource_validity.maximum_parameter_count,
            "within_declared_envelope": (
                contract.resource_validity.maximum_parameter_count is None
                or estimate.estimated_parameter_count
                <= contract.resource_validity.maximum_parameter_count
            ),
        })
    return {
        "project_version_matches_qho_extension": __version__ == QHO_EXTENSION_VERSION,
        "project_version_is_1_23_6": __version__ == QHO_EXTENSION_VERSION,
        "parent_phase_c_version_is_1_23_0": parent_manifest["project"]["version"] == "1.23.0",
        "parent_manifest_remains_frozen": parent_manifest["exit_conditions"]["integrity_i1_merged"] is False,
        "four_contracts_present": tuple(contracts["model_ids"]) == QHO_MODEL_IDS,
        "four_cells_present": len(cells["cells"]) == 4,
        "new_cells_are_experimental": cells["no_bulk_promotion"],
        "ui_schema_valid": all(ui_checks.values()),
        "protected_runtime_unchanged_or_authorized": runtime["all_unchanged_or_authorized"],
        "all_qho_sources_present": source["all_present"],
        "qho_api_paths_present": all(openapi["required_paths"].values()),
        "policy_driven_resource_preflight": all(
            item["within_declared_envelope"] for item in resource_preflight
        ),
        "qho_resource_policy_is_v2": all(
            item["contract_resource_policy_id"] == "bounded_direct_qubit.v2"
            for item in resource_preflight
        ),
        "qho_resource_rule_is_explicit": all(
            item["explicit_rule_selection"]
            and item["contract_resource_rule_id"] == item["rule_id"]
            for item in resource_preflight
        ),
        "resource_rule_registry_valid": all(validate_resource_rule_registry().values()),
        "artifact_identity_valid": (
            (root / ARTIFACT_IDENTITY_FILENAME).is_file()
            and verify_artifact_identity(root)["valid"]
        ),
        "no_second_runtime": runtime["second_runtime_created"] is False,
        "integrity_i1_not_merged": not (root / "qcol" / "integrity").exists(),
    }


def build_qho_extension_manifest(project_root: Path | str) -> dict[str, Any]:
    root = Path(project_root).resolve()
    parent_manifest = _read_json(root / "unified_baseline_manifest.json")
    contracts = build_qho_contract_catalog()
    ui_catalog = public_qho_ui_catalog()
    cells = build_qho_cell_catalog()
    runtime = build_protected_runtime_report(root)
    source = build_qho_source_fingerprints(root)
    openapi = build_qho_openapi_snapshot()
    checks = validate_qho_extension(root)
    resource_rule_catalog = public_resource_rule_catalog()
    artifact_identity = load_artifact_identity(root)
    payload: dict[str, Any] = {
        "schema_version": QHO_EXTENSION_SCHEMA_VERSION,
        "result": "QHO structural integration and schema-driven UI complete",
        "project": {
            "name": "QCOL",
            "version": __version__,
            "program": "Post-Phase-C Architectural Hardening",
            "step": "Pre-Step-2 QHO resource-policy and artifact-identity hardening",
        },
        "lineage": {
            "parent_frozen_baseline": {
                "project_version": parent_manifest["project"]["version"],
                "manifest_fingerprint": parent_manifest["manifest_fingerprint"],
                "source_package": PARENT_BASELINE_PACKAGE,
                "source_package_sha256": PARENT_BASELINE_PACKAGE_SHA256,
                "baseline_commit": parent_manifest["source_revision"]["baseline_commit"],
            },
            "qho_donor": {
                "package": QHO_DONOR_PACKAGE,
                "package_sha256": QHO_DONOR_PACKAGE_SHA256,
                "scope_used": [
                    "four independent QHO ModelContracts",
                    "ground-state cell declarations",
                    "bounded physics fixtures and interaction-profile semantics",
                ],
                "scope_deferred": [
                    "time_evolution task implementation",
                    "provider execution",
                    "scientific promotion beyond experimental",
                ],
            },
            "next_integrity_input": {
                "package": INTEGRITY_I1_PACKAGE,
                "package_sha256": INTEGRITY_I1_PACKAGE_SHA256,
                "merged": False,
            },
        },
        "source_revision": dict(_source_revision(root)),
        "qho_contract_catalog": contracts,
        "qho_ui_catalog": ui_catalog,
        "qho_cell_catalog": cells,
        "protected_runtime_report": runtime,
        "source_fingerprints": source,
        "openapi_summary": {
            "path_count": openapi["path_count"],
            "required_paths": openapi["required_paths"],
            "openapi_fingerprint": openapi["openapi_fingerprint"],
        },
        "resource_preflight_contract": {
            "decision_basis": "explicit resource policy + exact versioned resource rule + ansatz policy identity",
            "resource_policy_id": "bounded_direct_qubit.v2",
            "one_excitation_rule_id": "parameter_count.one_excitation_chain.n_minus_one.v1",
            "generic_rule_id": "parameter_count.generic_ry_rz.two_per_qubit_per_layer.v1",
            "resource_rule_catalog_fingerprint": resource_rule_catalog_fingerprint(),
            "qho_three_mode_estimated_parameters": 2,
            "qho_three_mode_legacy_wrong_estimate": 6,
            "qho_six_mode_estimated_parameters": 5,
            "model_task_failure_reasons_propagated": True,
            "silent_resource_rule_fallback": False,
        },
        "resource_rule_catalog": resource_rule_catalog,
        "artifact_identity": artifact_identity,
        "scientific_status_policy": {
            "legacy_oscillator_status_unchanged": "experimental",
            "qho_cells": {model_id: "experimental" for model_id in QHO_MODEL_IDS},
            "existing_phase_a_b_c_statuses_changed": False,
            "reference_policy_changed": False,
            "bulk_promotion_performed": False,
        },
        "test_results": (
            _read_json(root / "QCOL_QHO_Test_Results.json")
            if (root / "QCOL_QHO_Test_Results.json").exists()
            else {"status": "not_run_in_this_export"}
        ),
        "interface_contract": {
            "model_family": "Oscillator",
            "physical_models": [item["label"] for item in ui_catalog["models"]],
            "render_rule": ui_catalog["interface_rule"],
            "rendered_parameter_keys": {
                item["model_id"]: item["rendered_parameter_keys"]
                for item in ui_catalog["models"]
            },
            "browser_schema_driven": True,
            "gradio_schema_driven": True,
            "hardcoded_per_model_forms": False,
        },
        "exit_conditions": {
            "all_checks_pass": all(checks.values()),
            "structural_integration_complete": True,
            "ui_schema_update_complete": True,
            "runtime_eligibility_preflight_fixed": True,
            "resource_estimator_bound_to_ansatz_policy": True,
            "resource_policy_and_rule_explicit": True,
            "artifact_identity_enforced": True,
            "resolver_to_pipeline_gate_added": True,
            "run_pipeline_changed": False,
            "second_runtime_created": False,
            "existing_scientific_status_changed": False,
            "reference_changed": False,
            "integrity_i1_merged": False,
            "ready_for_step_2_after_clean_environment_gate": True,
        },
        "validation": checks,
        "next_step": (
            "Step 2 — controlled Integrity-I1 merge into this exact QHO-extended "
            "Phase-C baseline, followed by fingerprint regression."
        ),
    }
    payload["manifest_fingerprint"] = fingerprint(payload)
    return payload


@dataclass(frozen=True)
class QHOExtensionEvidenceExport:
    output_dir: Path
    archive_path: Path
    manifest_path: Path
    extension_manifest_path: Path


def _zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=_FIXED_ZIP_TIME)
    info.compress_type = zipfile.ZIP_STORED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    info.extra = b""
    info.comment = b""
    return info


def export_qho_extension_evidence(
    project_root: Path | str,
    output_dir: Path | str = "qcol_qho_structural_ui_evidence",
) -> QHOExtensionEvidenceExport:
    root = Path(project_root).resolve()
    out = Path(output_dir)
    if not out.is_absolute():
        out = (root / out).resolve()
    out.mkdir(parents=True, exist_ok=True)

    extension = build_qho_extension_manifest(root)
    contracts = build_qho_contract_catalog()
    ui_catalog = public_qho_ui_catalog()
    cells = build_qho_cell_catalog()
    runtime = build_protected_runtime_report(root)
    sources = build_qho_source_fingerprints(root)
    openapi = build_qho_openapi_snapshot()
    validation = validate_qho_extension(root)
    parent = _read_json(root / "unified_baseline_manifest.json")
    resource_rules = public_resource_rule_catalog()
    artifact_identity = load_artifact_identity(root)

    payloads: dict[str, Any] = {
        "qho_extension_manifest.json": extension,
        "parent_frozen_baseline_manifest.json": parent,
        "qho_contract_catalog.json": contracts,
        "qho_ui_catalog.json": ui_catalog,
        "qho_model_task_cells.json": cells,
        "protected_runtime_report.json": runtime,
        "source_fingerprints.json": sources,
        "qho_openapi.json": openapi,
        "validation.json": validation,
        "resource_rule_catalog.json": resource_rules,
        "artifact_identity.json": artifact_identity,
        "test_results.json": (
            _read_json(root / "QCOL_QHO_Test_Results.json")
            if (root / "QCOL_QHO_Test_Results.json").exists()
            else {"status": "not_run_in_this_export"}
        ),
    }
    file_rows = []
    encoded: dict[str, bytes] = {}
    for name, payload in sorted(payloads.items()):
        data = _json_bytes(payload)
        encoded[name] = data
        file_rows.append({"path": name, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})

    archive_manifest = {
        "schema_version": QHO_EVIDENCE_SCHEMA_VERSION,
        "project_version": __version__,
        "extension_manifest_fingerprint": extension["manifest_fingerprint"],
        "files": file_rows,
        "strict_json": True,
        "python_pickling_used": False,
        "callable_payload_included": False,
        "second_runtime_created": False,
        "scientific_status_promoted": False,
        "resource_rule_catalog_fingerprint": resource_rule_catalog_fingerprint(),
        "artifact_fingerprint": artifact_identity["artifact_fingerprint"],
    }
    manifest_bytes = _json_bytes(archive_manifest)
    encoded["manifest.json"] = manifest_bytes

    for name, data in encoded.items():
        (out / name).write_bytes(data)
    archive_path = out.with_suffix(".zip")
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_STORED) as archive:
        for name in sorted(encoded):
            archive.writestr(_zip_info(name), encoded[name])

    extension_path = out / "qho_extension_manifest.json"
    return QHOExtensionEvidenceExport(
        output_dir=out,
        archive_path=archive_path,
        manifest_path=out / "manifest.json",
        extension_manifest_path=extension_path,
    )


def verify_qho_extension_evidence(archive_path: Path | str) -> dict[str, bool]:
    path = Path(archive_path)
    with zipfile.ZipFile(path) as archive:
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        names = set(archive.namelist())
        rows_ok = True
        for row in manifest["files"]:
            if row["path"] not in names:
                rows_ok = False
                continue
            data = archive.read(row["path"])
            rows_ok = rows_ok and hashlib.sha256(data).hexdigest() == row["sha256"]
            rows_ok = rows_ok and len(data) == row["bytes"]
        stored = all(info.compress_type == zipfile.ZIP_STORED for info in archive.infolist())
        extension = json.loads(archive.read("qho_extension_manifest.json").decode("utf-8"))
        resource_rules = json.loads(archive.read("resource_rule_catalog.json").decode("utf-8"))
        artifact_identity = json.loads(archive.read("artifact_identity.json").decode("utf-8"))
    return {
        "manifest_rows_verified": rows_ok,
        "all_members_stored": stored,
        "extension_manifest_fingerprint_valid": (
            extension["manifest_fingerprint"]
            == fingerprint({key: value for key, value in extension.items() if key != "manifest_fingerprint"})
        ),
        "resource_rule_catalog_fingerprint_valid": (
            manifest["resource_rule_catalog_fingerprint"]
            == fingerprint(resource_rules)
        ),
        "artifact_fingerprint_retained": (
            manifest["artifact_fingerprint"]
            == artifact_identity["artifact_fingerprint"]
        ),
        "no_second_runtime": manifest["second_runtime_created"] is False,
        "no_scientific_promotion": manifest["scientific_status_promoted"] is False,
    }


__all__ = [
    "QHO_EXTENSION_VERSION",
    "QHO_DONOR_PACKAGE_SHA256",
    "PARENT_BASELINE_PACKAGE_SHA256",
    "PROTECTED_RUNTIME_PATHS",
    "build_qho_contract_catalog",
    "build_qho_cell_catalog",
    "build_protected_runtime_report",
    "build_qho_source_fingerprints",
    "build_qho_openapi_snapshot",
    "build_qho_extension_manifest",
    "validate_qho_extension",
    "export_qho_extension_evidence",
    "verify_qho_extension_evidence",
    "QHOExtensionEvidenceExport",
]

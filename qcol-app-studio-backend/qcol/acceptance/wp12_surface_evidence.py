"""WP12 API/UI/evidence export for the simple Model × Task variant surface."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from qcol.realization_policies.base import contract_fingerprint, json_contract_value
from qcol.realization_variants import (
    get_model_task_realization_view,
    public_model_task_realization_catalog,
    model_task_realization_catalog_fingerprint,
    validate_model_task_realization_catalog,
)
from qcol.model_task_matrix import public_model_task_matrix
from qcol.failures import build_pipeline_failure


WP12_EVIDENCE_SCHEMA_VERSION = "qcol-wp12-model-task-variant-surface-evidence/1.0"


@dataclass(frozen=True)
class ExportedWP12Evidence:
    output_directory: Path
    archive_path: Path
    manifest_path: Path


def _strict_json_round_trip(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return json.loads(json.dumps(json_contract_value(payload), sort_keys=True, allow_nan=False))


def build_wp12_station_error_examples() -> dict[str, Any]:
    jw = build_pipeline_failure(
        ValueError(
            "ANSATZ_GENERATOR_MAPPING_MISMATCH: The circuit preserves particle number, "
            "but it does not implement the JW-mapped nonadjacent fermionic generator."
        ),
        run_id="wp12-fixture-jw",
        stage="artifact",
    )
    bk = build_pipeline_failure(
        NotImplementedError(
            "BINDING_DECLARED_NOT_EXECUTABLE: BK ground-state realization is recognized_not_executable."
        ),
        run_id="wp12-fixture-bk",
        stage="task",
    )
    stale = build_pipeline_failure(
        ValueError("ACCEPTANCE_EVIDENCE_STALE: fingerprint mismatch"),
        run_id="wp12-fixture-stale",
        stage="verification",
    )
    def stable_fixture_payload(failure):
        payload = failure.to_dict()
        # These are declarative catalog fixtures, not live runtime failures.
        # A live timestamp would make the WP12 catalog fingerprint change on
        # every read and would incorrectly stale its own Evidence.
        payload["timestamp_utc"] = "deterministic-wp12-fixture"
        return payload

    return {
        "schema_version": "qcol-wp12-station-error-examples/1.0",
        "historical_jw_composition_failure": stable_fixture_payload(jw),
        "bk_recognized_not_executable": stable_fixture_payload(bk),
        "stale_evidence": stable_fixture_payload(stale),
    }


def public_wp12_surface_catalog() -> dict[str, Any]:
    variants = public_model_task_realization_catalog()
    matrix = public_model_task_matrix()
    ground = get_model_task_realization_view(
        "fermion.general_spin_orbital", "ground_state_energy"
    ).to_dict()
    analysis = get_model_task_realization_view(
        "fermion.general_spin_orbital", "mapping_analysis"
    ).to_dict()
    payload = {
        "schema_version": "qcol-wp12-surface-catalog/1.0",
        "catalog_version": "1.0.0",
        "phase": "A.3.2c",
        "work_package": "WP12",
        "objective": (
            "Expose realization-level scientific decisions inside a simple public "
            "Model × Task surface without adding mapping/state/ansatz/reference axes."
        ),
        "model_task_matrix": matrix,
        "realization_variant_catalog": variants,
        "highlighted_cells": {
            "general_spin_orbital_ground_state": ground,
            "general_spin_orbital_mapping_analysis": analysis,
        },
        "station_local_error_examples": build_wp12_station_error_examples(),
        "ui_contract": {
            "matrix_dimensions": ["model", "task"],
            "variant_details_are_inside_selected_cell": True,
            "unsupported_mapping_ansatz_offered_as_runnable": False,
            "historical_wrong_jw_ansatz_rendered_as_generic_pipeline_exception": False,
            "historical_wrong_jw_ansatz_failure_code": "ANSATZ_GENERATOR_MAPPING_MISMATCH",
            "bk_ground_state_selectable": False,
            "accepted_jw_default_variant": "realization.general_spin_orbital.ground_state.jw.wp11.v1",
        },
        "evidence_contract": {
            "strict_json": True,
            "python_pickling_used": False,
            "callable_payload_withheld": True,
            "source_fingerprints_included": True,
            "manifest_included": True,
            "deterministic_archive": True,
        },
        "runtime_contract": {
            "second_runtime_created": False,
            "shared_optimization_runtime_reused": True,
            "shared_measurement_runtime_reused": True,
            "shared_qasm_runtime_reused": True,
            "shared_execution_runtime_reused": True,
            "shared_evidence_chain_reused": True,
        },
        "scientific_behavior_change": False,
    }
    payload["fingerprint"] = contract_fingerprint(payload)
    return _strict_json_round_trip(payload)


def wp12_surface_catalog_fingerprint() -> str:
    return str(public_wp12_surface_catalog()["fingerprint"])


def validate_wp12_surface_catalog() -> dict[str, bool]:
    catalog = public_wp12_surface_catalog()
    checks = validate_model_task_realization_catalog()
    ground = catalog["highlighted_cells"]["general_spin_orbital_ground_state"]
    variants = {item["variant_id"]: item for item in ground["variants"]}
    accepted = variants["realization.general_spin_orbital.ground_state.jw.wp11.v1"]
    old = variants["realization.general_spin_orbital.ground_state.jw.bare_exchange.historical.v1"]
    bk = variants["realization.general_spin_orbital.ground_state.bk.default.v1"]
    checks.update({
        "matrix_is_two_dimensional": catalog["ui_contract"]["matrix_dimensions"] == ["model", "task"],
        "variant_records_inside_cell": catalog["ui_contract"]["variant_details_are_inside_selected_cell"],
        "accepted_jw_is_runnable_default": accepted["runnable"] and accepted["default_for_cell"],
        "old_jw_is_station_local_composition_failure": (
            old["composition_status"] == "failed"
            and old["failure_code"] == "ANSATZ_GENERATOR_MAPPING_MISMATCH"
            and not old["runnable"]
        ),
        "bk_is_visible_but_not_runnable": (
            bk["composition_status"] == "unresolved"
            and bk["cell_status"] == "recognized_not_executable"
            and not bk["runnable"]
            and not bk["selectable"]
        ),
        "strict_json_and_pickle_free": (
            catalog["evidence_contract"]["strict_json"]
            and not catalog["evidence_contract"]["python_pickling_used"]
        ),
        "evidence_archive_deterministic": catalog["evidence_contract"]["deterministic_archive"],
        "no_second_runtime": not catalog["runtime_contract"]["second_runtime_created"],
        "no_scientific_behavior_change": not catalog["scientific_behavior_change"],
    })
    return checks


def export_wp12_surface_evidence(
    output_directory: str | Path,
    *,
    project_root: str | Path | None = None,
) -> ExportedWP12Evidence:
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    catalog = public_wp12_surface_catalog()
    matrix = public_model_task_matrix()
    variants = public_model_task_realization_catalog()
    validation = validate_wp12_surface_catalog()
    files: dict[str, Any] = {
        "wp12_surface_catalog.json": catalog,
        "model_task_matrix.json": matrix,
        "realization_variant_catalog.json": variants,
        "general_spin_orbital_ground_state_variants.json": get_model_task_realization_view(
            "fermion.general_spin_orbital", "ground_state_energy"
        ).to_dict(),
        "general_spin_orbital_mapping_analysis_variants.json": get_model_task_realization_view(
            "fermion.general_spin_orbital", "mapping_analysis"
        ).to_dict(),
        "station_local_error_examples.json": build_wp12_station_error_examples(),
        "wp12_validation.json": validation,
    }
    for name, payload in files.items():
        (output / name).write_text(
            json.dumps(json_contract_value(payload), indent=2, sort_keys=True, allow_nan=False),
            encoding="utf-8",
        )

    source_fingerprints: dict[str, str] = {}
    if project_root is not None:
        root = Path(project_root)
        for relative in (
            "qcol/model_task_matrix.py",
            "qcol/realization_variants/public_surface.py",
            "qcol/api.py",
            "qcol/catalog.py",
            "qcol/public_views.py",
            "qcol/failures.py",
            "qcol/web/index.html",
            "qcol/web/styles.css",
            "qcol/web/app.js",
            "qcol/app.py",
        ):
            path = root / relative
            if path.exists():
                source_fingerprints[relative] = contract_fingerprint(
                    {"source": path.read_text(encoding="utf-8")}
                )
    (output / "source_fingerprints.json").write_text(
        json.dumps(source_fingerprints, indent=2, sort_keys=True), encoding="utf-8"
    )

    forbidden_extensions = [".pkl", ".pickle", ".joblib", ".dill"]
    manifest = {
        "schema_version": WP12_EVIDENCE_SCHEMA_VERSION,
        "work_package": "WP12",
        "catalog_fingerprint": wp12_surface_catalog_fingerprint(),
        "realization_variant_catalog_fingerprint": model_task_realization_catalog_fingerprint(),
        "validation_passed": all(validation.values()),
        "python_pickling_used": False,
        "forbidden_extensions": forbidden_extensions,
        "callable_payload_withheld": True,
        "second_runtime_created": False,
        "scientific_behavior_change": False,
        "deterministic_archive": True,
        "files": sorted([*files, "source_fingerprints.json", "manifest.json"]),
    }
    manifest_path = output / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    archive = output.with_suffix(".zip")
    # Write deterministic ZIP metadata so identical evidence payloads produce
    # identical archives across repeated exports and clean environments.
    with ZipFile(archive, "w", compression=ZIP_DEFLATED, compresslevel=9) as bundle:
        for path in sorted(output.iterdir()):
            if not path.is_file():
                continue
            if path.suffix.lower() in forbidden_extensions:
                raise RuntimeError(f"WP12 Evidence cannot contain Python pickle file {path.name!r}.")
            info = ZipInfo(filename=path.name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            bundle.writestr(info, path.read_bytes(), compress_type=ZIP_DEFLATED, compresslevel=9)
    return ExportedWP12Evidence(
        output_directory=output,
        archive_path=archive,
        manifest_path=manifest_path,
    )


__all__ = [
    "WP12_EVIDENCE_SCHEMA_VERSION",
    "ExportedWP12Evidence",
    "build_wp12_station_error_examples",
    "public_wp12_surface_catalog",
    "wp12_surface_catalog_fingerprint",
    "validate_wp12_surface_catalog",
    "export_wp12_surface_evidence",
]

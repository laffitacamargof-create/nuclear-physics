"""Deterministic project-artifact identity and loaded-module origin checks.

The Colab bootstrap uses this module after safe extraction.  Identity is based
on source hashes, not directory names, so an old extraction cannot masquerade
as the current release merely because it contains a familiar manifest file.
"""
from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path
import sys
from types import ModuleType
from typing import Any, Dict, Iterable, Mapping, Sequence

ARTIFACT_IDENTITY_SCHEMA_VERSION = "qcol-project-artifact-identity/1.0"
ARTIFACT_IDENTITY_FILENAME = "QCOL_Pre_Unified_Baseline_Semantic_Authority_Identity_v1.json"
DEFAULT_MODULES: tuple[str, ...] = (
    "qcol",
    "qcol.model_contracts.base",
    "qcol.model_contracts.classification",
    "qcol.semantic_authority.contracts",
    "qcol.semantic_authority.registry",
    "qcol.semantic_authority.builtin",
    "qcol.semantic_authority.audit",
    "qcol.semantic_identity",
    "qcol.evidence_transfer",
    "qcol.resource_rules.contracts",
    "qcol.resource_rules.registry",
    "qcol.resource_rules.builtin",
    "qcol.models.resource_estimators",
    "qcol.models.direct_qubit_resources",
    "qcol.model_instance_adapters",
    "qcol.model_ui_schema",
    "qcol.execution.contracts",
    "qcol.execution.descriptors",
    "qcol.execution.registry",
    "qcol.execution.local_cirq",
    "qcol.runtime",
    "qcol.observable_runtime",
    "qcol.resolver",
    "qcol.model_task_resolver",
    "qcol.realization",
    "qcol.orchestrator",
    "qcol.catalog",
    "qcol.api",
    "qcol.hardening.semantic_authority",
    "qcol.scientific_core",
    "qcol.composition_root",
    "qcol.parameter_ownership",
    "qcol.failure_model",
    "qcol.architecture_gates",
    "qcol.registry_consistency",
    "qcol.versioning",
    "qcol.observability",
    "qcol.environment_gate",
    "qcol.freeze_manifest",
    "qcol.freeze_sequence",
    "qcol.state.ports",
    "qcol.state.memory",
)


class ArtifactIdentityError(RuntimeError):
    pass


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path | str) -> str:
    return sha256_bytes(Path(path).read_bytes())


def canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _source_paths(project_root: Path) -> tuple[Path, ...]:
    roots = (project_root / "qcol", project_root / "scripts", project_root / "tests")
    paths: list[Path] = []
    for base in roots:
        if not base.exists():
            continue
        paths.extend(
            path
            for path in base.rglob("*.py")
            if "__pycache__" not in path.parts
        )
    for name in ("pyproject.toml", "requirements-colab-scientific.txt"):
        path = project_root / name
        if path.is_file():
            paths.append(path)
    return tuple(sorted(set(paths), key=lambda p: p.as_posix()))


def build_source_inventory(project_root: Path | str) -> dict[str, Any]:
    root = Path(project_root).resolve()
    files = []
    for path in _source_paths(root):
        relative = path.relative_to(root).as_posix()
        files.append(
            {
                "path": relative,
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
        )
    tree_fingerprint = sha256_bytes(canonical_json_bytes(files))
    return {
        "schema_version": "qcol-source-inventory/1.0",
        "file_count": len(files),
        "files": files,
        "tree_fingerprint": tree_fingerprint,
    }


def _module_relative_path(module_name: str) -> str:
    if module_name == "qcol":
        return "qcol/__init__.py"
    return module_name.replace(".", "/") + ".py"


def build_artifact_identity(
    project_root: Path | str,
    *,
    release_id: str,
    project_version: str,
    parent_manifest_fingerprint: str,
    expected_modules: Sequence[str] = DEFAULT_MODULES,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    inventory = build_source_inventory(root)
    modules = []
    for module_name in expected_modules:
        relative = _module_relative_path(module_name)
        path = root / relative
        if not path.is_file():
            raise ArtifactIdentityError(
                f"Expected module source {relative!r} is missing."
            )
        modules.append(
            {
                "module": module_name,
                "relative_path": relative,
                "sha256": sha256_file(path),
            }
        )
    payload = {
        "schema_version": ARTIFACT_IDENTITY_SCHEMA_VERSION,
        "release_id": str(release_id),
        "project_version": str(project_version),
        "parent_manifest_fingerprint": str(parent_manifest_fingerprint),
        "source_inventory": inventory,
        "expected_module_origins": modules,
        "runtime_contract": {
            "clean_qcol_module_cache_required": True,
            "module_origin_must_be_inside_project_root": True,
            "source_hash_match_required": True,
            "directory_name_is_not_identity": True,
        },
    }
    payload["artifact_fingerprint"] = sha256_bytes(canonical_json_bytes(payload))
    return payload


def write_artifact_identity(
    project_root: Path | str,
    *,
    release_id: str,
    project_version: str,
    parent_manifest_fingerprint: str,
) -> Path:
    root = Path(project_root).resolve()
    identity = build_artifact_identity(
        root,
        release_id=release_id,
        project_version=project_version,
        parent_manifest_fingerprint=parent_manifest_fingerprint,
    )
    path = root / ARTIFACT_IDENTITY_FILENAME
    path.write_text(
        json.dumps(identity, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def load_artifact_identity(project_root: Path | str) -> dict[str, Any]:
    path = Path(project_root).resolve() / ARTIFACT_IDENTITY_FILENAME
    if not path.is_file():
        raise ArtifactIdentityError(f"Artifact identity file is missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def verify_artifact_identity(
    project_root: Path | str,
    *,
    expected_fingerprint: str | None = None,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    recorded = load_artifact_identity(root)
    fingerprint = str(recorded.get("artifact_fingerprint", ""))
    payload = dict(recorded)
    payload.pop("artifact_fingerprint", None)
    self_hash_valid = fingerprint == sha256_bytes(canonical_json_bytes(payload))
    current_inventory = build_source_inventory(root)
    inventory_match = (
        current_inventory["tree_fingerprint"]
        == recorded["source_inventory"]["tree_fingerprint"]
    )
    module_hashes_match = True
    missing_modules: list[str] = []
    mismatched_modules: list[str] = []
    for row in recorded.get("expected_module_origins", []):
        path = root / row["relative_path"]
        if not path.is_file():
            module_hashes_match = False
            missing_modules.append(row["module"])
        elif sha256_file(path) != row["sha256"]:
            module_hashes_match = False
            mismatched_modules.append(row["module"])
    expected_match = expected_fingerprint is None or fingerprint == expected_fingerprint
    checks = {
        "identity_self_hash_valid": self_hash_valid,
        "source_tree_fingerprint_matches": inventory_match,
        "critical_module_hashes_match": module_hashes_match,
        "expected_artifact_fingerprint_matches": expected_match,
        "missing_modules": missing_modules,
        "mismatched_modules": mismatched_modules,
        "artifact_fingerprint": fingerprint,
        "project_version": recorded.get("project_version"),
        "release_id": recorded.get("release_id"),
    }
    checks["valid"] = all(
        checks[key]
        for key in (
            "identity_self_hash_valid",
            "source_tree_fingerprint_matches",
            "critical_module_hashes_match",
            "expected_artifact_fingerprint_matches",
        )
    )
    return checks


def purge_loaded_qcol_modules() -> tuple[str, ...]:
    removed = []
    for name in sorted(
        [name for name in sys.modules if name == "qcol" or name.startswith("qcol.")],
        reverse=True,
    ):
        removed.append(name)
        sys.modules.pop(name, None)
    importlib.invalidate_caches()
    return tuple(removed)


def loaded_module_origin_report(
    project_root: Path | str,
    *,
    module_names: Sequence[str] = DEFAULT_MODULES,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    identity = load_artifact_identity(root)
    expected = {
        row["module"]: row for row in identity.get("expected_module_origins", [])
    }
    rows = []
    for module_name in module_names:
        module = importlib.import_module(module_name)
        origin = Path(getattr(module, "__file__", "")).resolve()
        expected_row = expected[module_name]
        expected_path = (root / expected_row["relative_path"]).resolve()
        inside_root = origin.is_relative_to(root)
        exact_path = origin == expected_path
        hash_match = origin.is_file() and sha256_file(origin) == expected_row["sha256"]
        rows.append(
            {
                "module": module_name,
                "origin": str(origin),
                "expected_origin": str(expected_path),
                "inside_project_root": inside_root,
                "exact_origin": exact_path,
                "source_hash_match": hash_match,
            }
        )
    return {
        "schema_version": "qcol-loaded-module-origin-report/1.0",
        "project_root": str(root),
        "modules": rows,
        "all_origins_valid": all(
            row["inside_project_root"]
            and row["exact_origin"]
            and row["source_hash_match"]
            for row in rows
        ),
    }


def assert_loaded_artifact_identity(
    project_root: Path | str,
    *,
    expected_fingerprint: str | None = None,
) -> dict[str, Any]:
    identity_checks = verify_artifact_identity(
        project_root, expected_fingerprint=expected_fingerprint
    )
    if not identity_checks["valid"]:
        raise ArtifactIdentityError(
            "Project artifact identity failed: "
            + json.dumps(identity_checks, sort_keys=True)
        )
    origin = loaded_module_origin_report(project_root)
    if not origin["all_origins_valid"]:
        raise ArtifactIdentityError(
            "Loaded qcol module origin failed: " + json.dumps(origin, sort_keys=True)
        )
    return {"identity": identity_checks, "module_origin": origin}

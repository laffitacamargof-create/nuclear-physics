"""Build the deterministic *pre-merge* Unified Baseline candidate manifest.

The actual Unified Baseline may only be issued after the controlled Integrity
I1 merge, post-merge fingerprint regression, the full unified regression pack,
and a clean isolated-environment proof.  This module intentionally cannot
claim the final freeze while ``integrity_i1_merged`` is false.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import subprocess
from typing import Any

from . import __version__
from .artifact_identity import build_source_inventory
from .semantic_authority import semantic_authority_catalog_fingerprint
from .resource_rules import resource_rule_catalog_fingerprint
from .environment_gate import public_environment_manifest
from .versioning import public_version_compatibility_policy
from .request_boundaries import copy_plain_data
from .freeze_sequence import public_unified_freeze_sequence_contract


def _file_hash(path: Path) -> str | None:
    return sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def _git_value(root: Path, *args: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *args], cwd=root, text=True, capture_output=True, check=False
        )
    except OSError:
        return None
    return completed.stdout.strip() if completed.returncode == 0 else None


def _catalog_hash(payload: Any) -> str:
    normalized = copy_plain_data(payload)
    return sha256(
        json.dumps(
            normalized,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def build_unified_baseline_candidate_manifest(project_root: Path | str) -> dict[str, Any]:
    from .model_registry import public_model_registry
    from .task_registry import public_task_registry
    from .policy_contract_catalog import policy_contract_catalog_fingerprint
    from .architecture_gates import public_architecture_gate_report
    from .registry_consistency import public_registry_consistency_report
    from .failure_model import public_failure_model_contract
    from .composition_root import public_composition_root_contract
    from .state import public_state_boundary_contract
    from .observability import public_observability_contract

    root = Path(project_root).resolve()
    model_catalog = public_model_registry()
    task_catalog = public_task_registry()
    test_result_path = root / "QCOL_Pre_Unified_Baseline_Test_Results.json"
    test_results = (
        json.loads(test_result_path.read_text(encoding="utf-8"))
        if test_result_path.is_file()
        else {}
    )
    environment_result_path = root / "QCOL_Environment_Reproducibility_Result.json"
    environment_result = (
        json.loads(environment_result_path.read_text(encoding="utf-8"))
        if environment_result_path.is_file()
        else {}
    )

    scientific_pass = test_results.get("scientific_regression_gate") == "pass"
    qcol_environment_pass = test_results.get("qcol_environment_consistency_gate") == "pass"
    integrity_donor_pass = test_results.get("integrity_i1", {}).get("status") == "pass"
    clean_isolated_proof = bool(
        environment_result.get("evaluation", {})
        .get("clean_isolated_environment_proof", {})
        .get("satisfied", False)
    )
    ready_for_merge = scientific_pass and qcol_environment_pass and integrity_donor_pass

    source_inventory = build_source_inventory(root)
    final_freeze_blockers = [
        "controlled_integrity_i1_merge_not_performed",
        "post_merge_fingerprint_regression_not_performed",
        "full_unified_pre_freeze_regression_not_performed",
        "unified_baseline_manifest_not_issued",
    ]
    if not clean_isolated_proof:
        final_freeze_blockers.append("clean_isolated_environment_proof_missing")

    manifest: dict[str, Any] = {
        "schema_version": "qcol-pre-merge-unified-baseline-candidate/1.0",
        "manifest_kind": "pre_merge_candidate",
        "baseline_id": f"PRE-MERGE-UNIFIED-BASELINE-CANDIDATE-{__version__}",
        "freeze_status": (
            "pre_merge_candidate_ready_for_integrity_merge"
            if ready_for_merge
            else "pre_merge_candidate_pending_gates"
        ),
        "project_version": __version__,
        "created_at": None,
        "created_at_policy": "the_final_unified_manifest_is_issued_only_after_merge_and_full_regression",
        "source_identity": {
            "git_commit": _git_value(root, "rev-parse", "HEAD"),
            "git_branch": _git_value(root, "rev-parse", "--abbrev-ref", "HEAD"),
            "source_tree_sha256": source_inventory["tree_fingerprint"],
            "source_file_count": source_inventory["file_count"],
            "pyproject_sha256": _file_hash(root / "pyproject.toml"),
            "source_revision_record_sha256": _file_hash(root / "QCOL_QHO_Source_Revision.json"),
            "artifact_identity_sha256": _file_hash(root / "QCOL_Pre_Unified_Baseline_Semantic_Authority_Identity_v1.json"),
        },
        "catalog_fingerprints": {
            "model_contract_catalog": _catalog_hash(model_catalog),
            "task_contract_catalog": _catalog_hash(task_catalog),
            "declarative_policy_catalog": policy_contract_catalog_fingerprint(),
            "resource_rule_catalog": resource_rule_catalog_fingerprint(),
            "semantic_authority_catalog": semantic_authority_catalog_fingerprint(),
        },
        "evidence_schema_version": "qcol-evidence-manifest/1.x",
        "api_schema_version": "FastAPI OpenAPI snapshot generated for the candidate",
        "environment": public_environment_manifest(root),
        "environment_gate_result": environment_result,
        "architecture": {
            "composition_root": public_composition_root_contract(),
            "failure_model": public_failure_model_contract(),
            "version_policy": public_version_compatibility_policy(),
            "state_boundary": public_state_boundary_contract(),
            "observability": public_observability_contract(),
            "architecture_gates": public_architecture_gate_report(root),
            "registry_consistency": public_registry_consistency_report(),
        },
        "architecture_adr_files": [p.name for p in sorted(root.glob("QCOL_ADR_*.json"))],
        "test_manifest": {
            "results_file": test_result_path.name,
            "results_sha256": _file_hash(test_result_path),
            "clean_scientific_gate_status": test_results.get("scientific_regression_gate", "pending"),
            "qcol_environment_consistency_gate": test_results.get("qcol_environment_consistency_gate", "pending"),
            "host_environment_diagnostics": test_results.get("host_environment_diagnostics", "pending"),
            "clean_isolated_environment_proof": clean_isolated_proof,
            "integrity_i1_donor_gate": test_results.get("integrity_i1", {}).get("status", "pending"),
            "ready_for_controlled_integrity_i1_merge": ready_for_merge,
            "ready_for_unified_baseline_freeze": False,
            "all_previously_accepted_outcomes_must_remain_unchanged": True,
        },
        "freeze_sequence": public_unified_freeze_sequence_contract(),
        "integrity_i1_donor_verified": integrity_donor_pass,
        "integrity_i1_merged": False,
        "post_merge_fingerprint_regression_passed": False,
        "full_unified_pre_freeze_regression_passed": False,
        "unified_baseline_manifest_issued": False,
        "ready_for_controlled_integrity_i1_merge": ready_for_merge,
        "ready_for_unified_baseline_freeze": False,
        "final_freeze_blockers": final_freeze_blockers,
        "second_runtime_created": False,
    }
    normalized = copy_plain_data(manifest)
    normalized["manifest_fingerprint"] = _catalog_hash(normalized)
    return normalized


__all__ = ["build_unified_baseline_candidate_manifest"]

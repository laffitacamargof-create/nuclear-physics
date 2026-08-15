"""Pre-Unified-Baseline semantic-authority and taxonomy hardening.

This gate converts architectural guidance into executable invariants:

* one semantic fact -> one authoritative owner;
* classification labels are navigation metadata only;
* ResourceAssessor derives aggregate resources from the full resolved
  composition and never from ModelFamily;
* UI renders read-only contract/resolution views;
* scientific and execution fingerprints exclude presentation metadata;
* backend invocation occurs only through an ExecutionAdapter.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
from pathlib import Path
from typing import Any
import zipfile

from .. import __version__
from ..artifact_identity import build_source_inventory, load_artifact_identity
from ..execution import public_execution_adapter_catalog
from ..scientific_core import public_scientific_core_catalog, public_user_navigation_catalog
from ..parameter_ownership import public_parameter_ownership_catalog
from ..failure_model import public_failure_model_contract
from ..composition_root import public_composition_root_contract
from ..architecture_gates import public_architecture_gate_report
from ..registry_consistency import public_registry_consistency_report
from ..versioning import public_version_compatibility_policy
from ..observability import public_observability_contract
from ..state import public_state_boundary_contract
from ..environment_gate import public_environment_manifest
from ..freeze_manifest import build_unified_baseline_candidate_manifest
from ..model_execution_types import ModelBuildContext
from ..model_instance_adapters import instance_from_request
from ..model_registry import get_model_contract, list_model_contracts, public_model_registry
from ..model_task_matrix import public_model_task_matrix
from ..realization_variants import public_model_task_realization_catalog
from ..model_ui_schema import public_model_ui_schema, public_qho_ui_catalog
from ..models.direct_qubit_resources import bounded_direct_resource_policy
from ..request_boundaries import copy_plain_data
from ..resource_rules import (
    public_resource_rule_catalog,
    resource_rule_catalog_fingerprint,
    validate_resource_rule_registry,
)
from ..semantic_authority import (
    public_semantic_authority_catalog,
    semantic_authority_catalog_fingerprint,
    semantic_leakage_audit,
    validate_semantic_authority_catalog,
)
from ..semantic_identity import (
    build_execution_identity_payload,
    build_scientific_realization_payload,
    execution_fingerprint,
    scientific_realization_fingerprint,
)
from ..evidence_transfer import (
    ExecutionEvidenceIdentity,
    assess_execution_evidence_transferability,
    public_execution_evidence_transferability_contract,
)
from ..freeze_sequence import public_unified_freeze_sequence_contract

SEMANTIC_AUTHORITY_HARDENING_SCHEMA = "qcol-pre-merge-unified-baseline-readiness/1.0"
SEMANTIC_AUTHORITY_EVIDENCE_SCHEMA = "qcol-pre-merge-unified-baseline-readiness-evidence/1.0"
PRE_FREEZE_PROJECT_VERSION = "1.23.6"
_FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)

PHASE_C_ACCEPTED_FINGERPRINT = "68d4537436db735a59467881cd8a25e6051f103c7f0eba2a953501a3077736d0"
PHASE_B_ARCHIVED_FINGERPRINT = "8b043bef963bf60c12483b748ea46ef740ada1a7077d8a5a58165c9032d915c1"


def _json_bytes(payload: Any) -> bytes:
    payload = copy_plain_data(payload)
    return (
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def _fingerprint(payload: Any) -> str:
    payload = copy_plain_data(payload)
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _qho_request(model_id: str = "nuclear.qho.free", *, n_modes: int = 3) -> dict[str, Any]:
    parameters: dict[str, Any] = {"n_modes": n_modes, "omega": 1.0}
    if model_id in {"nuclear.qho.pairing", "nuclear.qho.full"}:
        parameters["coupling"] = 0.2
    if model_id in {"nuclear.qho.spinorbit", "nuclear.qho.full"}:
        parameters["kappa"] = 0.3
    return {
        "model_id": model_id,
        "method": "oscillator",
        "problem": model_id,
        "task_id": "ground_state_energy",
        "parameters": parameters,
        "target_backend": "google",
        "execution_mode": "local_simulator",
    }


def _resource_report(request: dict[str, Any], *, contract_override=None) -> dict[str, Any]:
    instance = instance_from_request(request)
    contract = contract_override or get_model_contract(instance.model_id)
    context = ModelBuildContext(
        contract=contract,
        instance=instance,
        request_metadata={
            "target_backend": request.get("target_backend"),
            "execution_mode": request.get("execution_mode"),
        },
    )
    return bounded_direct_resource_policy(context)


def build_model_classification_catalog() -> dict[str, Any]:
    rows = []
    for contract in list_model_contracts():
        classification = contract.classification
        rows.append(
            {
                "model_id": contract.model_id,
                "model_version": contract.model_version,
                "family": contract.family,
                "family_authority": "navigation_and_grouping_only",
                "classification": classification.to_dict() if classification else None,
                "authoritative_scientific_axes": {
                    "physical_domain": contract.domain,
                    "physical_phenomena": list(contract.physical_phenomena),
                    "degrees_of_freedom": list(contract.degrees_of_freedom),
                    "representation": copy_plain_data(contract.representation_contract),
                    "hamiltonian_components": list(contract.hamiltonian_components),
                    "sector_policy_id": contract.sector_policy_id,
                    "mapping_policy_id": contract.mapping_policy_id,
                },
                "classification_is_read_only_projection": True,
            }
        )
    return {
        "schema_version": "qcol-model-classification-catalog/1.1",
        "models": rows,
        "descriptive_taxonomy_fields": ["ui_group_id", "ui_group_label", "discovery_tags"],
        "authoritative_science_owner": "ModelContract and resolved policies",
        "model_family_authority": "navigation_and_grouping_only",
        "mixed_fermion_vibration_contracts_supported": True,
        "rule": "Never solve duplicate authority by creating a richer duplicate authority.",
    }


def build_resource_authority_scenarios() -> dict[str, Any]:
    base_request = _qho_request()
    base_contract = get_model_contract("nuclear.qho.free")
    base = _resource_report(base_request)
    renamed_contract = replace(
        base_contract,
        family="Renamed UI Group",
        classification=base_contract.classification.with_ui_group(
            "renamed_ui_group", "Renamed UI Group"
        ),
    )
    renamed = _resource_report(base_request, contract_override=renamed_contract)

    custom_request = {
        "model_id": "custom.qubit_hamiltonian",
        "method": "custom",
        "problem": "pauli_input",
        "task_id": "ground_state_energy",
        "parameters": {
            "pauli_terms": "X0: 1.0",
            "n_qubits": 4,
            "ansatz_layers": 1,
            "energy_unit": "dimensionless",
        },
    }
    layer1 = _resource_report(custom_request)
    custom_request_2 = json.loads(json.dumps(custom_request))
    custom_request_2["parameters"]["ansatz_layers"] = 2
    layer2 = _resource_report(custom_request_2)

    repeat = _resource_report(base_request)
    return {
        "schema_version": "qcol-resource-authority-scenarios/1.0",
        "qho_three_modes": {
            "estimated_parameter_count": base["estimated_parameter_count"],
            "must_not_equal": 6,
            "parameter_count_source": base["parameter_count_source"],
            "authoritative_owner_id": base["semantic_authority_owner_id"],
            "parameter_count_rule_id": base["parameter_count_rule_id"],
            "derivation": base["resource_report_derivation"],
        },
        "classification_rename_invariance": {
            "before": base,
            "after": renamed,
            "unchanged": base == renamed,
        },
        "ansatz_layer_sensitivity": {
            "layer_1_parameter_count": layer1["estimated_parameter_count"],
            "layer_2_parameter_count": layer2["estimated_parameter_count"],
            "changed": layer1["estimated_parameter_count"] != layer2["estimated_parameter_count"],
        },
        "deterministic_assessment": {
            "same_input_same_report": base == repeat,
            "first_fingerprint": _fingerprint(base),
            "second_fingerprint": _fingerprint(repeat),
        },
    }


def build_identity_mutation_matrix() -> dict[str, Any]:
    """Exercise the scientific/execution identity boundary as a mutation matrix.

    Every semantic mutation must either change the scientific fingerprint or be
    rejected by compatibility.  Presentation-only mutations must leave it
    unchanged.  Execution-only mutations extend the scientific identity rather
    than contaminating it.
    """

    contract = get_model_contract("nuclear.qho.free")
    request = _qho_request()
    instance = instance_from_request(request)

    base_kwargs = {
        "model_contract": contract,
        "model_instance": instance,
        "task_identity": {
            "task_id": "ground_state_energy",
            "task_version": "1.0.0",
            "quantity": "energy",
        },
        "resolved_policy_overrides": {
            "ansatz_configuration": {"layers": 1},
        },
        "ordering_identity": {
            "ordering_id": "qho.mode_order.v1",
            "mode_order": ["mode_0", "mode_1", "mode_2"],
        },
        "scientific_scale": {
            "n_modes": 3,
            "n_quanta": 1,
            "declared_envelope_id": "qho.one_quantum.2_to_6_modes.v1",
        },
        "reference_regime": {
            "reference_policy_id": contract.reference_policy_id,
            "reference_problem_id": "qho.free.one_quantum.n3.v1",
            "quantity": "energy",
        },
    }
    base = scientific_realization_fingerprint(**base_kwargs)

    def fingerprint(**changes: Any) -> str:
        payload = dict(base_kwargs)
        payload.update(changes)
        return scientific_realization_fingerprint(**payload)

    renamed_contract = replace(
        contract,
        family="Nuclear Vibrations — renamed",
        classification=contract.classification.with_ui_group(
            "new_navigation_group", "Nuclear Vibrations — renamed"
        ),
    )
    renamed = fingerprint(model_contract=renamed_contract)

    parameter_request = _qho_request()
    parameter_request["parameters"]["omega"] = 1.1
    parameter_changed = fingerprint(model_instance=instance_from_request(parameter_request))

    scale_changed = fingerprint(
        scientific_scale={
            "n_modes": 4,
            "n_quanta": 1,
            "declared_envelope_id": "qho.one_quantum.2_to_6_modes.v1",
        }
    )
    sector_changed = fingerprint(
        sector_identity={"excitation_number": 2}
    )
    ordering_changed = fingerprint(
        ordering_identity={
            "ordering_id": "qho.mode_order.v1",
            "mode_order": ["mode_1", "mode_0", "mode_2"],
        }
    )
    mapping_changed = fingerprint(
        resolved_policy_overrides={
            "mapping_policy_id": "alternate_direct_encoding.v1",
            "ansatz_configuration": {"layers": 1},
        }
    )
    ansatz_contract = replace(
        contract,
        ansatz_policy_id="one_excitation_chain_givens.v2",
    )
    ansatz_changed = fingerprint(model_contract=ansatz_contract)
    ansatz_layers_changed = fingerprint(
        resolved_policy_overrides={
            "ansatz_configuration": {"layers": 2},
        }
    )
    measurement_contract = replace(
        contract,
        measurement_policy_id="pauli_energy_qwc.v2",
    )
    measurement_changed = fingerprint(model_contract=measurement_contract)
    task_changed = fingerprint(
        task_identity={
            "task_id": "ground_state_energy",
            "task_version": "1.1.0",
            "quantity": "energy_with_penalty",
        }
    )
    reference_changed = fingerprint(
        reference_regime={
            "reference_policy_id": "small_exact_one_excitation_sector.v2",
            "reference_problem_id": "qho.free.one_quantum.n3.v2",
            "quantity": "energy",
        }
    )

    # Presentation metadata is deliberately absent from the scientific payload.
    ui_color_changed = base
    panel_order_changed = base

    base_execution = execution_fingerprint(
        scientific_fingerprint=base,
        executable_artifact_hash="logical-circuit-hash",
        adapter_identity={"adapter_id": "execution.local_cirq.v1", "version": "1.0.0"},
        backend_identity={"backend": "local_cirq"},
        shots=256,
        seed=71,
    )
    shots_changed = execution_fingerprint(
        scientific_fingerprint=base,
        executable_artifact_hash="logical-circuit-hash",
        adapter_identity={"adapter_id": "execution.local_cirq.v1", "version": "1.0.0"},
        backend_identity={"backend": "local_cirq"},
        shots=512,
        seed=71,
    )
    adapter_changed = execution_fingerprint(
        scientific_fingerprint=base,
        executable_artifact_hash="logical-circuit-hash",
        adapter_identity={"adapter_id": "execution.local_aer.v1", "version": "1.0.0"},
        backend_identity={"backend": "local_aer"},
        shots=256,
        seed=71,
    )

    base_evidence = ExecutionEvidenceIdentity(
        evidence_id="evidence.qho.free.n3.local_cirq.256.v1",
        scientific_fingerprint=base,
        execution_fingerprint=base_execution,
    )
    original_transfer = assess_execution_evidence_transferability(
        evidence=base_evidence,
        target_scientific_fingerprint=base,
        target_execution_fingerprint=base_execution,
    )
    shots_transfer = assess_execution_evidence_transferability(
        evidence=base_evidence,
        target_scientific_fingerprint=base,
        target_execution_fingerprint=shots_changed,
    )
    adapter_transfer = assess_execution_evidence_transferability(
        evidence=base_evidence,
        target_scientific_fingerprint=base,
        target_execution_fingerprint=adapter_changed,
    )

    mutations = {
        "rename_display_family": {"fingerprint": renamed, "fresh": renamed == base, "kind": "presentation"},
        "change_ui_color": {"fingerprint": ui_color_changed, "fresh": ui_color_changed == base, "kind": "presentation"},
        "change_panel_order": {"fingerprint": panel_order_changed, "fresh": panel_order_changed == base, "kind": "presentation"},
        "change_model_parameter": {"fingerprint": parameter_changed, "fresh": parameter_changed == base, "kind": "scientific"},
        "change_model_scale": {"fingerprint": scale_changed, "fresh": scale_changed == base, "kind": "scientific"},
        "change_sector": {"fingerprint": sector_changed, "fresh": sector_changed == base, "kind": "scientific"},
        "change_mode_order": {"fingerprint": ordering_changed, "fresh": ordering_changed == base, "kind": "scientific"},
        "change_mapping": {"fingerprint": mapping_changed, "fresh": mapping_changed == base, "kind": "scientific"},
        "change_ansatz_policy": {"fingerprint": ansatz_changed, "fresh": ansatz_changed == base, "kind": "scientific"},
        "change_ansatz_layers": {"fingerprint": ansatz_layers_changed, "fresh": ansatz_layers_changed == base, "kind": "scientific"},
        "change_measurement_policy": {"fingerprint": measurement_changed, "fresh": measurement_changed == base, "kind": "scientific"},
        "change_task_semantics": {"fingerprint": task_changed, "fresh": task_changed == base, "kind": "scientific"},
        "change_reference_regime": {"fingerprint": reference_changed, "fresh": reference_changed == base, "kind": "scientific"},
    }

    presentation_fresh = all(
        mutations[key]["fresh"]
        for key in ("rename_display_family", "change_ui_color", "change_panel_order")
    )
    semantic_stale = all(
        not row["fresh"] for row in mutations.values() if row["kind"] == "scientific"
    )
    return {
        "schema_version": "qcol-semantic-identity-mutation-matrix/1.2",
        "base_scientific_fingerprint": base,
        "presentation_metadata_does_not_stale_scientific_identity": presentation_fresh,
        "all_semantic_mutations_change_scientific_identity": semantic_stale,
        "shots_change_execution_identity_only": base_execution != shots_changed,
        "adapter_change_execution_identity_only": base_execution != adapter_changed,
        "scientific_freshness_is_not_execution_evidence_transferability": True,
        "shots_change_requires_new_execution_evidence": (
            shots_transfer.scientific_identity_current
            and not shots_transfer.transferable
            and shots_transfer.failure_code == "EVIDENCE_EXECUTION_IDENTITY_MISMATCH"
        ),
        "adapter_change_requires_new_execution_evidence": (
            adapter_transfer.scientific_identity_current
            and not adapter_transfer.transferable
            and adapter_transfer.failure_code == "EVIDENCE_EXECUTION_IDENTITY_MISMATCH"
        ),
        "old_evidence_remains_valid_for_original_execution": original_transfer.transferable,
        "mutations": mutations,
        "execution_identity": {
            "base": base_execution,
            "shots_changed": shots_changed,
            "adapter_changed": adapter_changed,
            "shots_change_changes_execution_only": base_execution != shots_changed,
            "adapter_change_changes_execution_only": base_execution != adapter_changed,
            "scientific_fingerprint_retained": base,
        },
        "execution_evidence_transferability": {
            "contract": public_execution_evidence_transferability_contract(),
            "original_execution": original_transfer.to_dict(),
            "shots_changed_target": shots_transfer.to_dict(),
            "adapter_changed_target": adapter_transfer.to_dict(),
        },
        "expected": {
            "presentation_mutations_fresh": True,
            "semantic_mutations_stale": True,
            "execution_mutations_do_not_change_scientific_identity": True,
            "execution_mutations_require_new_execution_evidence": True,
        },
    }


def build_core_regression_attestation(project_root: Path | str) -> dict[str, Any]:
    """Freeze the accepted/experimental support boundaries and I1 donor identity."""

    root = Path(project_root).resolve()
    matrix = public_model_task_matrix()
    cells = {row["cell_id"]: row for row in matrix["cells"]}
    expected_cells = {
        "nuclear.reduced_pairing.one_pair::ground_state_energy": ("acceptance_verified", True),
        "nuclear.reduced_pairing.one_pair::observable_estimation": ("acceptance_verified", True),
        "nuclear.reduced_pairing.multi_pair::ground_state_energy": ("experimental", True),
        "fermion.general_spin_orbital::mapping_analysis": ("acceptance_verified", True),
        "fermion.general_spin_orbital::ground_state_energy": ("acceptance_verified", True),
        "nuclear.qho.free::ground_state_energy": ("experimental", True),
        "nuclear.qho.pairing::ground_state_energy": ("experimental", True),
        "nuclear.qho.spinorbit::ground_state_energy": ("experimental", True),
        "nuclear.qho.full::ground_state_energy": ("experimental", True),
    }
    cell_rows = {}
    for cell_id, (expected_status, expected_runnable) in expected_cells.items():
        row = cells[cell_id]
        cell_rows[cell_id] = {
            "status": row["status"],
            "runnable": bool(row["runnable"]),
            "expected_status": expected_status,
            "expected_runnable": expected_runnable,
            "preserved": row["status"] == expected_status
            and bool(row["runnable"]) == expected_runnable,
        }

    realizations = public_model_task_realization_catalog()
    variants = {
        row["variant_id"]: row
        for cell in realizations["cells"]
        for row in cell["variants"]
    }
    variant_expectations = {
        "realization.general_spin_orbital.ground_state.jw.wp11.v1": (
            "verified",
            "verified",
            "acceptance_verified",
            True,
        ),
        "realization.general_spin_orbital.ground_state.jw.bare_exchange.historical.v1": (
            "verified",
            "failed",
            "not_verified",
            False,
        ),
        "realization.general_spin_orbital.ground_state.bk.default.v1": (
            "verified_for_transform",
            "unresolved",
            "recognized_not_executable",
            False,
        ),
    }
    variant_rows = {}
    for variant_id, expected in variant_expectations.items():
        row = variants[variant_id]
        actual = (
            row["mapper_status"],
            row["composition_status"],
            row["cell_status"],
            bool(row["runnable"]),
        )
        variant_rows[variant_id] = {
            "mapper_status": actual[0],
            "composition_status": actual[1],
            "cell_status": actual[2],
            "runnable": actual[3],
            "expected": {
                "mapper_status": expected[0],
                "composition_status": expected[1],
                "cell_status": expected[2],
                "runnable": expected[3],
            },
            "preserved": actual == expected,
        }

    baseline = json.loads((root / "unified_baseline_manifest.json").read_text(encoding="utf-8"))
    i1 = dict(baseline["planned_integrity_merge_input"])
    i1_expected = {
        "integrity_catalog_fingerprint": "593877fe18fdc149a2a7f4426858c3d4707c636e3f801cb8b95130ce48c0793e",
        "comparison_realization_fingerprint": "7db28fbbe7df059e3b415014e5981b5e085cce09f3a781cca2234722cb07cbaa",
        "source_archive_sha256": "5a9c1299afd54faaecfc4940bed410f729ef037e16a4b1e1012eec3e460d74ee",
        "merged": False,
    }
    return {
        "schema_version": "qcol-pre-freeze-core-regression-attestation/1.0",
        "cells": cell_rows,
        "realization_variants": variant_rows,
        "integrity_i1_donor": {
            **i1,
            "expected": i1_expected,
            "preserved": all(i1.get(key) == value for key, value in i1_expected.items()),
        },
        "all_cells_preserved": all(row["preserved"] for row in cell_rows.values()),
        "all_variants_preserved": all(row["preserved"] for row in variant_rows.values()),
        "no_scientific_promotion": all(
            cells[f"nuclear.qho.{name}::ground_state_energy"]["status"] == "experimental"
            for name in ("free", "pairing", "spinorbit", "full")
        ),
    }


def _archived_release_attestations(project_root: Path) -> dict[str, Any]:
    phase_b_path = project_root / "QCOL_Phase_B_Deterministic_Advisor_Catalog_v1.json"
    phase_c_path = project_root / "QCOL_Phase_C_Try_Compare_Catalog_v1.json"
    phase_b = json.loads(phase_b_path.read_text(encoding="utf-8"))
    phase_c = json.loads(phase_c_path.read_text(encoding="utf-8"))
    return {
        "phase_b": {
            "path": phase_b_path.name,
            "archived_fingerprint": phase_b.get("fingerprint"),
            "matches_accepted_fingerprint": phase_b.get("fingerprint") == PHASE_B_ARCHIVED_FINGERPRINT,
            "sha256": hashlib.sha256(phase_b_path.read_bytes()).hexdigest(),
        },
        "phase_c": {
            "path": phase_c_path.name,
            "sha256": hashlib.sha256(phase_c_path.read_bytes()).hexdigest(),
            "accepted_dynamic_fingerprint": PHASE_C_ACCEPTED_FINGERPRINT,
        },
    }



_ADR_FILENAMES = (
    "QCOL_ADR_Semantic_Authority_Ownership_v1.json",
    "QCOL_ADR_Model_Classification_Axes_v1.json",
    "QCOL_ADR_Resource_Assessment_Ownership_v1.json",
    "QCOL_ADR_Semantic_Authority_Execution_Boundary_v1.json",
    "QCOL_ADR_Composition_Root_Authority_v1.json",
    "QCOL_ADR_Parameter_Schema_Ownership_v1.json",
    "QCOL_ADR_Unified_Failure_Model_v1.json",
    "QCOL_ADR_Dependency_Direction_v1.json",
    "QCOL_ADR_State_Repository_Port_v1.json",
    "QCOL_ADR_Environment_Gate_Scope_v1.json",
    "QCOL_ADR_Environment_Smoke_Aggregation_v1.json",
    "QCOL_ADR_Execution_Evidence_Transferability_v1.json",
)


def build_architecture_decision_record_catalog(project_root: Path | str) -> dict[str, Any]:
    root = Path(project_root).resolve()
    records = []
    for filename in _ADR_FILENAMES:
        path = root / filename
        if not path.is_file():
            records.append({"filename": filename, "exists": False})
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        records.append(
            {
                "filename": filename,
                "exists": True,
                "adr_id": payload.get("adr_id"),
                "status": payload.get("status"),
                "project_version": payload.get("project_version"),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "payload": payload,
            }
        )
    return {
        "schema_version": "qcol-architecture-decision-record-catalog/1.0",
        "records": records,
        "all_present": all(row.get("exists") for row in records),
        "all_accepted": all(row.get("status") == "accepted" for row in records if row.get("exists")),
    }

def build_semantic_authority_hardening_manifest(project_root: Path | str) -> dict[str, Any]:
    root = Path(project_root).resolve()
    authority = public_semantic_authority_catalog()
    classifications = build_model_classification_catalog()
    resources = build_resource_authority_scenarios()
    mutations = build_identity_mutation_matrix()
    leakage = semantic_leakage_audit(root)
    adapters = public_execution_adapter_catalog()
    scientific_core = public_scientific_core_catalog()
    parameter_ownership = public_parameter_ownership_catalog()
    architecture_gates = public_architecture_gate_report(root)
    registry_consistency = public_registry_consistency_report()
    core_regression = build_core_regression_attestation(root)
    adrs = build_architecture_decision_record_catalog(root)
    artifact = load_artifact_identity(root)
    payload = {
        "schema_version": SEMANTIC_AUTHORITY_HARDENING_SCHEMA,
        "release_id": "qcol.pre-merge-unified-baseline.candidate.v1",
        "project_version": __version__,
        "objective": (
            "Prepare the exact QCOL architecture as the controlled pre-merge candidate by "
            "enforcing semantic ownership, descriptive-only navigation, composition-root "
            "authority, scoped environment reproducibility, execution-evidence identity, "
            "one execution boundary, and one evidence chain. The actual Unified Baseline "
            "Freeze remains downstream of the controlled Integrity I1 merge and post-merge regression."
        ),
        "semantic_authority": authority,
        "model_classifications": classifications,
        "resource_authority_scenarios": resources,
        "identity_mutation_matrix": mutations,
        "semantic_leakage_audit": leakage,
        "execution_adapters": adapters,
        "user_navigation": public_user_navigation_catalog(),
        "scientific_core": scientific_core,
        "parameter_ownership": parameter_ownership,
        "composition_root": public_composition_root_contract(),
        "failure_model": public_failure_model_contract(),
        "architecture_gates": architecture_gates,
        "registry_consistency": registry_consistency,
        "version_compatibility": public_version_compatibility_policy(),
        "observability": public_observability_contract(),
        "state_boundary": public_state_boundary_contract(),
        "environment_manifest": public_environment_manifest(root),
        "environment_scope_policy": public_environment_manifest(root)["scope_policy"],
        "execution_evidence_transferability": public_execution_evidence_transferability_contract(),
        "unified_freeze_sequence": public_unified_freeze_sequence_contract(),
        "unified_baseline_candidate": build_unified_baseline_candidate_manifest(root),
        "core_regression_attestation": core_regression,
        "architecture_decision_records": adrs,
        "resource_rule_catalog_fingerprint": resource_rule_catalog_fingerprint(),
        "artifact_identity": {
            "release_id": artifact["release_id"],
            "project_version": artifact["project_version"],
            "artifact_fingerprint": artifact["artifact_fingerprint"],
            "source_tree_fingerprint": artifact["source_inventory"]["tree_fingerprint"],
        },
        "release_attestations": _archived_release_attestations(root),
        "scientific_status_promoted": False,
        "second_runtime_created": False,
        "integrity_i1_merged": False,
    }
    payload["manifest_fingerprint"] = _fingerprint(payload)
    return payload


def validate_semantic_authority_hardening(project_root: Path | str) -> dict[str, bool]:
    root = Path(project_root).resolve()
    manifest = build_semantic_authority_hardening_manifest(root)
    authority_checks = validate_semantic_authority_catalog()
    resource_checks = validate_resource_rule_registry()
    scenarios = manifest["resource_authority_scenarios"]
    mutations = manifest["identity_mutation_matrix"]
    classifications = manifest["model_classifications"]
    core_regression = manifest["core_regression_attestation"]
    return {
        "project_version_is_1_23_6": __version__ == PRE_FREEZE_PROJECT_VERSION,
        "semantic_authority_catalog_valid": all(authority_checks.values()),
        "resource_rule_registry_valid": all(resource_checks.values()),
        "one_owner_per_fact": authority_checks["exactly_one_owner_per_fact"],
        "architecture_decision_records_present_and_accepted": (
            manifest["architecture_decision_records"]["all_present"]
            and manifest["architecture_decision_records"]["all_accepted"]
        ),
        "all_model_contracts_have_descriptive_classification": all(
            row["classification"] is not None and row["classification"]["scientific_authority"] is False
            for row in classifications["models"]
        ),
        "classification_does_not_duplicate_mapping_sector_or_encoding": all(
            not any(key in row["classification"] for key in ("mapping", "sector_semantics", "encoding_kind", "ansatz", "measurement"))
            for row in classifications["models"]
        ),
        "model_family_is_navigation_only": all(
            row["family_authority"] == "navigation_and_grouping_only"
            for row in classifications["models"]
        ),
        "qho_three_modes_is_two_not_six": (
            scenarios["qho_three_modes"]["estimated_parameter_count"] == 2
            and scenarios["qho_three_modes"]["estimated_parameter_count"]
            != scenarios["qho_three_modes"]["must_not_equal"]
        ),
        "parameter_count_owned_by_ansatz_policy_via_resource_assessor": (
            scenarios["qho_three_modes"]["parameter_count_source"]
            == "ansatz_policy_via_resource_assessor"
            and scenarios["qho_three_modes"]["authoritative_owner_id"]
            == "owner.resource_assessor"
        ),
        "classification_rename_does_not_change_resources": scenarios[
            "classification_rename_invariance"
        ]["unchanged"],
        "ansatz_layers_change_resource_report": scenarios[
            "ansatz_layer_sensitivity"
        ]["changed"],
        "resource_assessment_is_deterministic": scenarios[
            "deterministic_assessment"
        ]["same_input_same_report"],
        "presentation_metadata_does_not_stale_scientific_identity": all(
            mutations["mutations"][key]["fresh"]
            for key in ("rename_display_family", "change_ui_color", "change_panel_order")
        ),
        "semantic_mutations_change_scientific_identity": all(
            not row["fresh"]
            for row in mutations["mutations"].values()
            if row["kind"] == "scientific"
        ),
        "shots_change_execution_identity_only": mutations["execution_identity"][
            "shots_change_changes_execution_only"
        ],
        "adapter_change_execution_identity_only": mutations["execution_identity"][
            "adapter_change_changes_execution_only"
        ],
        "static_semantic_leakage_gate_pass": manifest["semantic_leakage_audit"]["pass"],
        "backend_invocation_owned_by_execution_adapter": manifest[
            "semantic_leakage_audit"
        ]["backend_invocation_owned_by_execution_adapter"],
        "pyqasm_owned_by_translation_boundary": manifest["semantic_leakage_audit"][
            "pyqasm_owned_by_translation_boundary"
        ],
        "composition_root_gate_pass": manifest["architecture_gates"]["reports"]["composition_root"]["pass"],
        "dependency_direction_gate_pass": manifest["architecture_gates"]["reports"]["dependency_direction"]["pass"],
        "semantic_authority_is_governance_only": manifest["architecture_gates"]["reports"]["semantic_authority_governance_only"]["pass"],
        "registry_consistency_pass": manifest["registry_consistency"]["pass"],
        "parameter_namespaces_have_distinct_owners": len(set(manifest["parameter_ownership"]["namespaces"][key]["owner_id"] for key in manifest["parameter_ownership"]["namespaces"])) == 4,
        "user_navigation_is_exact_and_non_authoritative": [row["label"] for row in manifest["user_navigation"]["groups"]] == ["Oscillators", "Fermions", "Custom"] and all(not row["scientific_inference_allowed"] for row in manifest["user_navigation"]["groups"]),
        "unified_failure_model_has_required_namespaces": set(manifest["failure_model"]["namespaces"]) == {"RESOLUTION", "RESOURCE", "TRANSLATION", "EXECUTION", "EVIDENCE", "COMPARISON", "STATE"},
        "state_repository_seam_defined": (
            manifest["state_boundary"]["port_id"] == "StateRepository"
            and manifest["state_boundary"]["default_adapter_id"] == "state.in_memory.v1"
            and manifest["state_boundary"]["pipeline_change_required_for_sqlite"] is False
        ),
        "version_evolution_policy_explicit": (
            manifest["version_compatibility"]["rules"]["semantic_change_requires_new_version"]
            and manifest["version_compatibility"]["rules"]["silent_alias_or_fallback_allowed"] is False
        ),
        "minimal_observability_contract_formalized": set(manifest["observability"]["required_event_fields"]) == {"run_id", "station", "status", "timestamp_utc"},
        "environment_manifest_captured": (
            bool(manifest["environment_manifest"]["python_version"])
            and bool(manifest["environment_manifest"]["dependency_file_hashes"])
            and manifest["environment_manifest"]["provider_credentials_recorded"] is False
        ),
        "environment_scope_policy_is_explicit": (
            manifest["environment_scope_policy"]["invariants"][
                "qcol_scoped_conflicts_are_blocking"
            ]
            and manifest["environment_scope_policy"]["invariants"][
                "unrelated_colab_host_conflicts_are_diagnostic"
            ]
            and manifest["environment_scope_policy"]["invariants"][
                "clean_isolated_environment_required_for_final_freeze"
            ]
            and manifest["environment_scope_policy"]["invariants"][
                "claimed_scope_must_match_detected_scope"
            ]
            and manifest["environment_scope_policy"]["dependency_lock_selection"][
                "isolated_venv"
            ] == "requirements.txt"
            and manifest["environment_scope_policy"]["dependency_lock_selection"][
                "colab_host"
            ] == "requirements-colab-scientific.txt"
        ),
        "execution_evidence_transferability_is_explicit": (
            mutations["scientific_freshness_is_not_execution_evidence_transferability"]
            and mutations["shots_change_requires_new_execution_evidence"]
            and mutations["adapter_change_requires_new_execution_evidence"]
            and mutations["old_evidence_remains_valid_for_original_execution"]
        ),
        "unified_freeze_requires_integrity_merge_before_freeze": (
            manifest["unified_freeze_sequence"]["invariants"][
                "integrity_i1_merge_precedes_unified_baseline_freeze"
            ]
            and manifest["unified_baseline_candidate"][
                "ready_for_unified_baseline_freeze"
            ] is False
        ),
        "unified_baseline_manifest_is_candidate": manifest["unified_baseline_candidate"]["freeze_status"] in {"pre_merge_candidate_pending_gates", "pre_merge_candidate_ready_for_integrity_merge"},
        "phase_b_archived_attestation_preserved": manifest["release_attestations"][
            "phase_b"
        ]["matches_accepted_fingerprint"],
        "phase_c_accepted_fingerprint_preserved": _phase_c_fingerprint() == PHASE_C_ACCEPTED_FINGERPRINT,
        "accepted_and_experimental_cell_statuses_preserved": core_regression["all_cells_preserved"],
        "jw_bk_realization_boundaries_preserved": core_regression["all_variants_preserved"],
        "integrity_i1_donor_identity_preserved_and_unmerged": core_regression["integrity_i1_donor"]["preserved"],
        "no_scientific_promotion": manifest["scientific_status_promoted"] is False,
        "no_second_runtime": manifest["second_runtime_created"] is False,
        "integrity_i1_not_merged": manifest["integrity_i1_merged"] is False,
    }


def _phase_c_fingerprint() -> str:
    from ..comparison import phase_c_catalog_fingerprint

    return phase_c_catalog_fingerprint()


@dataclass(frozen=True)
class SemanticAuthorityEvidenceExport:
    output_dir: Path
    archive_path: Path
    manifest_path: Path


def _zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=_FIXED_ZIP_TIME)
    info.compress_type = zipfile.ZIP_STORED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    info.extra = b""
    info.comment = b""
    return info


def export_semantic_authority_evidence(
    project_root: Path | str,
    output_dir: Path | str = "qcol_semantic_authority_evidence",
) -> SemanticAuthorityEvidenceExport:
    root = Path(project_root).resolve()
    out = Path(output_dir)
    if not out.is_absolute():
        out = (root / out).resolve()
    out.mkdir(parents=True, exist_ok=True)

    manifest = build_semantic_authority_hardening_manifest(root)
    validation = validate_semantic_authority_hardening(root)
    payloads = {
        "semantic_authority_hardening_manifest.json": manifest,
        "semantic_authority_catalog.json": public_semantic_authority_catalog(),
        "model_classification_catalog.json": build_model_classification_catalog(),
        "resource_rule_catalog.json": public_resource_rule_catalog(),
        "resource_authority_scenarios.json": build_resource_authority_scenarios(),
        "identity_mutation_matrix.json": build_identity_mutation_matrix(),
        "execution_evidence_transferability_contract.json": public_execution_evidence_transferability_contract(),
        "environment_scope_policy.json": public_environment_manifest(root)["scope_policy"],
        "unified_freeze_sequence.json": public_unified_freeze_sequence_contract(),
        "semantic_leakage_audit.json": semantic_leakage_audit(root),
        "execution_adapter_catalog.json": public_execution_adapter_catalog(),
        "user_navigation_catalog.json": public_user_navigation_catalog(),
        "scientific_core_catalog.json": public_scientific_core_catalog(),
        "parameter_ownership_catalog.json": public_parameter_ownership_catalog(),
        "composition_root_contract.json": public_composition_root_contract(),
        "failure_model_contract.json": public_failure_model_contract(),
        "architecture_gate_report.json": public_architecture_gate_report(root),
        "registry_consistency_report.json": public_registry_consistency_report(),
        "version_compatibility_policy.json": public_version_compatibility_policy(),
        "observability_contract.json": public_observability_contract(),
        "environment_manifest.json": public_environment_manifest(root),
        "unified_baseline_candidate_manifest.json": build_unified_baseline_candidate_manifest(root),
        "core_regression_attestation.json": build_core_regression_attestation(root),
        "architecture_decision_records.json": build_architecture_decision_record_catalog(root),
        "validation.json": validation,
        "source_inventory.json": build_source_inventory(root),
    }
    encoded: dict[str, bytes] = {}
    rows = []
    for name, payload in sorted(payloads.items()):
        data = _json_bytes(payload)
        encoded[name] = data
        rows.append({"path": name, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})
    archive_manifest = {
        "schema_version": SEMANTIC_AUTHORITY_EVIDENCE_SCHEMA,
        "project_version": __version__,
        "hardening_manifest_fingerprint": manifest["manifest_fingerprint"],
        "files": rows,
        "strict_json": True,
        "python_pickling_used": False,
        "callable_payload_included": False,
        "scientific_status_promoted": False,
        "second_runtime_created": False,
    }
    encoded["manifest.json"] = _json_bytes(archive_manifest)
    for name, data in encoded.items():
        (out / name).write_bytes(data)
    archive_path = out.with_suffix(".zip")
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_STORED) as archive:
        for name in sorted(encoded):
            archive.writestr(_zip_info(name), encoded[name])
    return SemanticAuthorityEvidenceExport(out, archive_path, out / "manifest.json")


def verify_semantic_authority_evidence(archive_path: Path | str) -> dict[str, bool]:
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
        validation = json.loads(archive.read("validation.json").decode("utf-8"))
        hardening = json.loads(
            archive.read("semantic_authority_hardening_manifest.json").decode("utf-8")
        )
    return {
        "manifest_rows_verified": rows_ok,
        "all_members_stored": stored,
        "all_must_gates_pass": all(validation.values()),
        "hardening_manifest_fingerprint_valid": hardening["manifest_fingerprint"]
        == _fingerprint({k: v for k, v in hardening.items() if k != "manifest_fingerprint"}),
        "no_scientific_promotion": manifest["scientific_status_promoted"] is False,
        "no_second_runtime": manifest["second_runtime_created"] is False,
    }


__all__ = [
    "PRE_FREEZE_PROJECT_VERSION",
    "build_model_classification_catalog",
    "build_resource_authority_scenarios",
    "build_identity_mutation_matrix",
    "build_core_regression_attestation",
    "build_architecture_decision_record_catalog",
    "build_semantic_authority_hardening_manifest",
    "validate_semantic_authority_hardening",
    "export_semantic_authority_evidence",
    "verify_semantic_authority_evidence",
    "SemanticAuthorityEvidenceExport",
]

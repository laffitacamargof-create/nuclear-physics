"""WP12 public Model × Task surface with internal realization variants.

The public capability map remains two-dimensional.  A cell may expose one or
more *internal* realization variants, but those mappings, state preparations,
ansätze, references, and support boundaries are not promoted to independent UI
axes.  This keeps the physicist-first interface simple while preserving the
scientific decisions required by the resolver and acceptance system.

This module is dependency-light and strict-JSON-safe.  It stores no executable
callable and does not enter the scientific runtime.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple

from qcol.realization_policies.base import DeclarativeContract, contract_fingerprint


WP12_SURFACE_SCHEMA_VERSION = "qcol-model-task-realization-surface/1.0"
WP12_VARIANT_SCHEMA_VERSION = "qcol-public-realization-variant/1.0"
WP12_SURFACE_VERSION = "1.0.0"


@dataclass(frozen=True)
class PublicRealizationVariant(DeclarativeContract):
    """One honest internal realization beneath a Model × Task cell."""

    variant_id: str
    model_id: str
    task_id: str
    label: str
    mapping_id: str
    mapping_label: str
    mapper_status: str
    composition_status: str
    cell_status: str
    runtime_status: str
    runnable: bool
    selectable: bool
    runtime_path: str
    support_scope: str
    mapping_convention_id: Optional[str] = None
    state_preparation_policy_id: Optional[str] = None
    ansatz_policy_id: Optional[str] = None
    ansatz_semantic_class: Optional[str] = None
    measurement_policy_id: Optional[str] = None
    reference_policy_id: Optional[str] = None
    verification_policy_id: Optional[str] = None
    acceptance_suite_id: Optional[str] = None
    evidence_fingerprint: Optional[str] = None
    failure_code: Optional[str] = None
    failure_message: Optional[str] = None
    suggested_action: Optional[str] = None
    historical: bool = False
    default_for_cell: bool = False
    limitations: Tuple[str, ...] = field(default_factory=tuple)
    aliases: Tuple[str, ...] = field(default_factory=tuple)
    provenance: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = WP12_VARIANT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.runnable and not self.selectable:
            raise ValueError("A runnable public realization variant must be selectable.")
        if self.runtime_status in {"recognized_not_executable", "blocked", "rejected"} and self.runnable:
            raise ValueError("A blocked or unavailable realization variant cannot be runnable.")
        if self.composition_status == "failed" and not self.failure_code:
            raise ValueError("A failed composition must publish a stable failure code.")
        if self.historical and self.default_for_cell:
            raise ValueError("A historical negative variant cannot be the default realization.")

    @property
    def cell_id(self) -> str:
        return f"{self.model_id}::{self.task_id}"

    def to_dict(self) -> Dict[str, Any]:
        payload = super().to_dict()
        payload["cell_id"] = self.cell_id
        payload["status_triplet"] = {
            "mapper": self.mapper_status,
            "composition": self.composition_status,
            "cell": self.cell_status,
        }
        payload["callable_payload_withheld"] = True
        return payload


@dataclass(frozen=True)
class ModelTaskCellRealizationView(DeclarativeContract):
    """Two-dimensional cell plus its internal realization records."""

    model_id: str
    task_id: str
    cell_label: str
    cell_status: str
    cell_runnable: bool
    default_variant_id: Optional[str]
    variants: Tuple[PublicRealizationVariant, ...]
    schema_version: str = "qcol-model-task-cell-realizations/1.0"

    def __post_init__(self) -> None:
        ids = [item.variant_id for item in self.variants]
        if len(ids) != len(set(ids)):
            raise ValueError("Realization variant IDs must be unique inside one cell.")
        defaults = [item.variant_id for item in self.variants if item.default_for_cell]
        if self.default_variant_id is None and defaults:
            raise ValueError("A declared default variant must match default_variant_id.")
        if self.default_variant_id is not None:
            if self.default_variant_id not in ids:
                raise ValueError("default_variant_id must name a variant in the cell.")
            if defaults != [self.default_variant_id]:
                raise ValueError("Exactly one matching default_for_cell variant is required.")

    @property
    def cell_id(self) -> str:
        return f"{self.model_id}::{self.task_id}"

    def to_dict(self) -> Dict[str, Any]:
        payload = super().to_dict()
        payload.update({
            "cell_id": self.cell_id,
            "variant_count": len(self.variants),
            "runnable_variant_count": sum(1 for item in self.variants if item.runnable),
            "variants_endpoint": (
                f"/catalog/model-task-realizations/cell/{self.model_id}/{self.task_id}"
            ),
            "variants": [item.to_dict() for item in self.variants],
            "callable_payload_withheld": True,
        })
        return payload

    def matrix_summary(self) -> Dict[str, Any]:
        return {
            "cell_id": self.cell_id,
            "model_id": self.model_id,
            "task_id": self.task_id,
            "status": self.cell_status,
            "runnable": self.cell_runnable,
            "variant_count": len(self.variants),
            "runnable_variant_count": sum(1 for item in self.variants if item.runnable),
            "default_variant_id": self.default_variant_id,
            "variants_endpoint": (
                f"/catalog/model-task-realizations/cell/{self.model_id}/{self.task_id}"
            ),
        }


def _generic_variant_from_cell(cell: Any) -> PublicRealizationVariant:
    intent = dict(getattr(cell, "resolved_policy_intent", {}) or {})
    mapping_id = str(intent.get("mapping") or intent.get("mappings") or "model_contract_default")
    runtime_status = (
        "execution_allowed"
        if bool(getattr(cell, "runnable", False))
        else "recognized_not_executable"
    )
    return PublicRealizationVariant(
        variant_id=f"realization.{cell.model_id}.{cell.task_id}.default.v1",
        model_id=cell.model_id,
        task_id=cell.task_id,
        label=f"{cell.label} — declared default realization",
        mapping_id=mapping_id,
        mapping_label=mapping_id.replace("_", " "),
        mapper_status=("verified" if bool(getattr(cell, "runnable", False)) else "not_evaluated"),
        composition_status=(
            "verified"
            if cell.status in {"acceptance_verified", "execution_ready"}
            else "review"
            if cell.status == "experimental"
            else "not_applicable"
        ),
        cell_status=cell.status,
        runtime_status=runtime_status,
        runnable=bool(getattr(cell, "runnable", False)),
        selectable=bool(getattr(cell, "runnable", False)),
        runtime_path=("shared_execution_pipeline" if bool(getattr(cell, "runnable", False)) else "none"),
        support_scope=str((getattr(cell, "reference_validity", {}) or {}).get("declared_scale") or cell.label),
        acceptance_suite_id=getattr(cell, "acceptance_suite_id", None),
        default_for_cell=True,
        limitations=tuple(str(item) for item in (getattr(cell, "notes", ()) or ())),
        provenance={
            "source": "ModelTaskCell",
            "wp12_surface_only": True,
            "scientific_status_changed": False,
        },
    )


def _special_variants() -> Dict[str, Tuple[PublicRealizationVariant, ...]]:
    """Return the variant-rich cells whose internal composition matters publicly."""
    from qcol.mapping_policies.profiles import (
        public_pair_mapping_migration_catalog,
        public_spin_orbital_mapping_migration_catalog,
        public_wp11_jw_accepted_composition_catalog,
    )

    pair = public_pair_mapping_migration_catalog()
    spin = public_spin_orbital_mapping_migration_catalog()
    wp11 = public_wp11_jw_accepted_composition_catalog()
    wp11_fp = str(wp11["acceptance_fingerprint"]["fingerprint"])

    one_pair = PublicRealizationVariant(
        variant_id="realization.reduced_pairing.one_pair.pair_mapping.v1",
        model_id="nuclear.reduced_pairing.one_pair",
        task_id="ground_state_energy",
        label="Pair mapping — verified one-pair ground-state realization",
        mapping_id="pair_mapping.seniority_zero.v1",
        mapping_label="Pair mapping",
        mapping_convention_id="qcol.pair_mapping.seniority_zero.v1",
        mapper_status="verified",
        composition_status="verified",
        cell_status="acceptance_verified",
        runtime_status="execution_allowed",
        runnable=True,
        selectable=True,
        runtime_path="shared_execution_pipeline",
        support_scope="Declared one-pair seniority-zero regression envelope",
        state_preparation_policy_id="pair.state.one_pair_reference.v1",
        ansatz_policy_id="pair.ansatz.one_pair.mapping_native_verified.v1",
        ansatz_semantic_class="mapping_native_verified",
        reference_policy_id="pair.reference.one_pair_sector.v1",
        acceptance_suite_id="acceptance.cell.one_pair.ground_state.v1",
        default_for_cell=True,
        aliases=("pair_mapping.v1",),
        limitations=(
            "Restricted to the declared seniority-zero pair-occupation domain.",
            "It does not claim full single-fermion Fock-space semantics.",
        ),
        provenance={
            "phase": "A.3.2b",
            "work_package": "WP8",
            "catalog_fingerprint": pair["fingerprint"],
        },
    )
    multi_pair = PublicRealizationVariant(
        variant_id="realization.reduced_pairing.multi_pair.pair_mapping.v1",
        model_id="nuclear.reduced_pairing.multi_pair",
        task_id="ground_state_energy",
        label="Pair mapping — experimental multi-pair realization",
        mapping_id="pair_mapping.seniority_zero.v1",
        mapping_label="Pair mapping",
        mapping_convention_id="qcol.pair_mapping.seniority_zero.v1",
        mapper_status="verified",
        composition_status="review",
        cell_status="experimental",
        runtime_status="execution_allowed_with_review",
        runnable=True,
        selectable=True,
        runtime_path="shared_execution_pipeline",
        support_scope="4–6 levels; 2–3 pairs; declared seniority zero",
        state_preparation_policy_id="pair.state.multi_pair_reference.v1",
        ansatz_policy_id="pair.ansatz.multi_pair.qubit_native.v1",
        ansatz_semantic_class="qubit_native",
        reference_policy_id="pair.reference.multi_pair_sector.v1",
        acceptance_suite_id="acceptance.cell.multi_pair.ground_state.v1",
        default_for_cell=True,
        limitations=(
            "The mapper is verified, but composition and cell promotion remain under review.",
            "A successful individual run does not change the experimental cell status.",
        ),
        provenance={
            "phase": "A.3.2b",
            "work_package": "WP8",
            "catalog_fingerprint": pair["fingerprint"],
        },
    )

    jw_analysis = PublicRealizationVariant(
        variant_id="realization.general_spin_orbital.mapping_analysis.jw.v1",
        model_id="fermion.general_spin_orbital",
        task_id="mapping_analysis",
        label="Jordan–Wigner mapping-analysis realization",
        mapping_id="jordan_wigner.spin_orbital.v1",
        mapping_label="Jordan–Wigner",
        mapping_convention_id="openfermion.jordan_wigner.ordered_modes.little_endian.v1",
        mapper_status="verified",
        composition_status="not_applicable",
        cell_status="acceptance_verified",
        runtime_status="analysis_only_allowed",
        runnable=True,
        selectable=True,
        runtime_path="analysis_controller",
        support_scope="2–8 modes; deterministic transform/equivalence/resource analysis",
        reference_policy_id="fermion.reference.fock_space_spectrum.v1",
        acceptance_suite_id="acceptance.cell.general_spin_orbital.mapping_analysis.v1",
        default_for_cell=True,
        aliases=("jordan_wigner.v1",),
        limitations=("No state preparation, ansatz, shots, QASM circuit, simulator, or VQE claim.",),
        provenance={"phase": "A.3.2b", "work_package": "WP9", "catalog_fingerprint": spin["fingerprint"]},
    )
    bk_analysis = PublicRealizationVariant(
        variant_id="realization.general_spin_orbital.mapping_analysis.bk.v1",
        model_id="fermion.general_spin_orbital",
        task_id="mapping_analysis",
        label="Bravyi–Kitaev mapping-analysis realization",
        mapping_id="bravyi_kitaev.spin_orbital.default.v1",
        mapping_label="Bravyi–Kitaev",
        mapping_convention_id="openfermion.bravyi_kitaev.default_code.v1",
        mapper_status="verified",
        composition_status="not_applicable",
        cell_status="acceptance_verified",
        runtime_status="analysis_only_allowed",
        runnable=True,
        selectable=True,
        runtime_path="analysis_controller",
        support_scope="2–8 modes; deterministic transform/equivalence/resource analysis",
        reference_policy_id="fermion.reference.fock_space_spectrum.v1",
        acceptance_suite_id="acceptance.cell.general_spin_orbital.mapping_analysis.v1",
        aliases=("bravyi_kitaev.v1",),
        limitations=(
            "Raw BK bitstring popcount is not physical particle number.",
            "No state preparation, ansatz, shots, QASM circuit, simulator, or VQE claim.",
        ),
        provenance={"phase": "A.3.2b", "work_package": "WP10", "catalog_fingerprint": spin["fingerprint"]},
    )

    jw_accepted = PublicRealizationVariant(
        variant_id=str(wp11["variant_id"]),
        model_id="fermion.general_spin_orbital",
        task_id="ground_state_energy",
        label="JW mapped-fermionic ground-state realization — accepted",
        mapping_id="jordan_wigner.spin_orbital.v1",
        mapping_label="Jordan–Wigner",
        mapping_convention_id=str(wp11["mapping_convention_id"]),
        mapper_status="verified",
        composition_status="verified",
        cell_status="acceptance_verified",
        runtime_status="execution_allowed",
        runnable=True,
        selectable=True,
        runtime_path="shared_execution_pipeline",
        support_scope="2–4 modes; one species; fixed 1 ≤ N < n_modes; 1–2 ansatz layers; local simulator acceptance path",
        state_preparation_policy_id="jw.state.occupation_determinant.v1",
        ansatz_policy_id=str(wp11["ansatz_policy"]["policy_id"]),
        ansatz_semantic_class=str(wp11["ansatz_policy"]["semantic_class"]),
        measurement_policy_id="jw.measurement.pauli_energy_qwc.v1",
        reference_policy_id="jw.reference.fixed_particle_sector.v1",
        verification_policy_id="jw.verification.three_gate.v1",
        acceptance_suite_id=str(wp11["promotion_record"]["acceptance_suite_id"]),
        evidence_fingerprint=wp11_fp,
        default_for_cell=True,
        limitations=(
            "Acceptance is exact-fingerprint and declared-scale bound; it is not a claim for arbitrary mode counts.",
            "Execution uses the existing shared local-simulator runtime; provider adapters remain separate.",
        ),
        provenance={"phase": "A.3.2c", "work_package": "WP11", "catalog_fingerprint": contract_fingerprint(wp11)},
    )
    jw_historical = PublicRealizationVariant(
        variant_id="realization.general_spin_orbital.ground_state.jw.bare_exchange.historical.v1",
        model_id="fermion.general_spin_orbital",
        task_id="ground_state_energy",
        label="JW bare qubit-exchange realization — historical rejected fixture",
        mapping_id="jordan_wigner.spin_orbital.v1",
        mapping_label="Jordan–Wigner",
        mapping_convention_id="openfermion.jordan_wigner.ordered_modes.little_endian.v1",
        mapper_status="verified",
        composition_status="failed",
        cell_status="not_verified",
        runtime_status="rejected",
        runnable=False,
        selectable=False,
        runtime_path="none",
        support_scope="Historical WP0/WP9 negative regression fixture only",
        ansatz_policy_id="jw.ansatz.current_bare_qubit_exchange.v1",
        ansatz_semantic_class="qubit_native",
        failure_code="ANSATZ_GENERATOR_MAPPING_MISMATCH",
        failure_message=(
            "The circuit preserves particle number, but it does not implement the "
            "JW-mapped nonadjacent fermionic generator."
        ),
        suggested_action=(
            "Use the accepted mapped-fermionic FSWAP-routed JW variant or provide "
            "mapping-native generator-equivalence evidence."
        ),
        historical=True,
        limitations=("Never offered as a runnable choice.",),
        provenance={"phase": "A.3.2a/A.3.2b", "work_package": "WP0/WP9", "permanent_negative_fixture": True},
    )
    bk_ground = PublicRealizationVariant(
        variant_id="realization.general_spin_orbital.ground_state.bk.default.v1",
        model_id="fermion.general_spin_orbital",
        task_id="ground_state_energy",
        label="BK ground-state realization — recognized, not executable",
        mapping_id="bravyi_kitaev.spin_orbital.default.v1",
        mapping_label="Bravyi–Kitaev",
        mapping_convention_id="openfermion.bravyi_kitaev.default_code.v1",
        mapper_status="verified_for_transform",
        composition_status="unresolved",
        cell_status="recognized_not_executable",
        runtime_status="recognized_not_executable",
        runnable=False,
        selectable=False,
        runtime_path="none",
        support_scope="Transformation and mapping analysis only",
        state_preparation_policy_id="bk.state.encoded_occupation_circuit.v1",
        ansatz_policy_id="bk.ansatz.mapping_aware_ground_state.v1",
        ansatz_semantic_class="mapped_fermionic_generator",
        reference_policy_id="bk.reference.fixed_particle_sector.v1",
        failure_code="BINDING_DECLARED_NOT_EXECUTABLE",
        failure_message=(
            "BK-aware state preparation, nonlocal particle-sector diagnostics, "
            "ansatz composition, and cell evidence are not accepted in this release."
        ),
        suggested_action="Use BK for mapping analysis, or use the accepted JW ground-state realization.",
        limitations=(
            "raw_popcount_is_particle_number = false",
            "Full ground-state execution remains disabled until BK-specific composition and cell gates pass.",
        ),
        provenance={"phase": "A.3.2b", "work_package": "WP10", "catalog_fingerprint": spin["fingerprint"]},
    )

    return {
        one_pair.cell_id: (one_pair,),
        multi_pair.cell_id: (multi_pair,),
        jw_analysis.cell_id: (jw_analysis, bk_analysis),
        jw_accepted.cell_id: (jw_accepted, jw_historical, bk_ground),
    }


def build_model_task_realization_registry() -> Dict[str, ModelTaskCellRealizationView]:
    from qcol.model_task_matrix import list_model_task_cells

    special = _special_variants()
    registry: Dict[str, ModelTaskCellRealizationView] = {}
    for cell in list_model_task_cells():
        cell_id = f"{cell.model_id}::{cell.task_id}"
        variants = special.get(cell_id)
        if variants is None:
            variants = (_generic_variant_from_cell(cell),)
        defaults = [item.variant_id for item in variants if item.default_for_cell]
        default_variant_id = defaults[0] if defaults else None
        registry[cell_id] = ModelTaskCellRealizationView(
            model_id=cell.model_id,
            task_id=cell.task_id,
            cell_label=cell.label,
            cell_status=cell.status,
            cell_runnable=cell.runnable,
            default_variant_id=default_variant_id,
            variants=tuple(variants),
        )
    return registry


def get_model_task_realization_view(model_id: str, task_id: str) -> ModelTaskCellRealizationView:
    key = f"{model_id}::{task_id}"
    registry = build_model_task_realization_registry()
    try:
        return registry[key]
    except KeyError as exc:
        raise KeyError(f"Unknown Model × Task cell: {key}") from exc


def get_public_realization_variant(variant_id: str) -> PublicRealizationVariant:
    for cell in build_model_task_realization_registry().values():
        for variant in cell.variants:
            if variant.variant_id == variant_id or variant_id in variant.aliases:
                return variant
    raise KeyError(f"Unknown realization variant: {variant_id}")


def public_model_task_realization_catalog() -> Dict[str, Any]:
    registry = build_model_task_realization_registry()
    cells = [registry[key].to_dict() for key in sorted(registry)]
    variant_index = {
        variant["variant_id"]: variant
        for cell in cells
        for variant in cell["variants"]
    }
    payload = {
        "schema_version": WP12_SURFACE_SCHEMA_VERSION,
        "surface_version": WP12_SURFACE_VERSION,
        "principle": (
            "The public capability map remains Model × Task. Mapping, state, ansatz, "
            "reference, and acceptance identities are internal realization variants inside each cell."
        ),
        "ui_rule": (
            "Do not turn mappings, ansätze, sectors, references, or controllers into independent matrix axes."
        ),
        "cells": cells,
        "variant_index": variant_index,
        "variant_count": len(variant_index),
        "runnable_variants": sorted(
            item["variant_id"] for item in variant_index.values() if item["runnable"]
        ),
        "blocked_variants": sorted(
            item["variant_id"] for item in variant_index.values() if not item["runnable"]
        ),
        "guardrails": {
            "unsupported_variant_offered_as_runnable": False,
            "historical_jw_failure_is_generic_pipeline_exception": False,
            "historical_jw_failure_code": "ANSATZ_GENERATOR_MAPPING_MISMATCH",
            "bk_ground_state_selectable": False,
            "callable_payload_withheld": True,
            "matrix_dimension_count": 2,
            "second_runtime_created": False,
            "scientific_behavior_change": False,
        },
    }
    payload["fingerprint"] = contract_fingerprint(payload)
    return payload


def model_task_realization_catalog_fingerprint() -> str:
    return str(public_model_task_realization_catalog()["fingerprint"])


def validate_model_task_realization_catalog() -> Dict[str, bool]:
    catalog = public_model_task_realization_catalog()
    ground = get_model_task_realization_view("fermion.general_spin_orbital", "ground_state_energy")
    variants = {item.variant_id: item for item in ground.variants}
    accepted = variants["realization.general_spin_orbital.ground_state.jw.wp11.v1"]
    historical = variants["realization.general_spin_orbital.ground_state.jw.bare_exchange.historical.v1"]
    bk = variants["realization.general_spin_orbital.ground_state.bk.default.v1"]
    return {
        "strict_model_task_surface": catalog["guardrails"]["matrix_dimension_count"] == 2,
        "accepted_jw_is_default_and_runnable": accepted.default_for_cell and accepted.runnable,
        "historical_jw_is_failed_not_runnable": (
            historical.composition_status == "failed"
            and historical.failure_code == "ANSATZ_GENERATOR_MAPPING_MISMATCH"
            and not historical.runnable
            and not historical.selectable
        ),
        "bk_ground_is_unresolved_not_executable": (
            bk.mapper_status == "verified_for_transform"
            and bk.composition_status == "unresolved"
            and bk.cell_status == "recognized_not_executable"
            and not bk.runnable
            and not bk.selectable
        ),
        "no_unsupported_variant_offered_as_runnable": all(
            item["runnable"] == item["selectable"]
            for item in catalog["variant_index"].values()
        ),
        "no_callables_in_public_catalog": catalog["guardrails"]["callable_payload_withheld"],
        "no_second_runtime": not catalog["guardrails"]["second_runtime_created"],
        "no_scientific_behavior_change": not catalog["guardrails"]["scientific_behavior_change"],
    }


__all__ = [
    "WP12_SURFACE_SCHEMA_VERSION",
    "WP12_VARIANT_SCHEMA_VERSION",
    "WP12_SURFACE_VERSION",
    "PublicRealizationVariant",
    "ModelTaskCellRealizationView",
    "build_model_task_realization_registry",
    "get_model_task_realization_view",
    "get_public_realization_variant",
    "public_model_task_realization_catalog",
    "model_task_realization_catalog_fingerprint",
    "validate_model_task_realization_catalog",
]

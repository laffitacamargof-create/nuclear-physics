"""Deterministic WP6 fingerprint fixtures built on the accepted WP5 resolver tuple."""
from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping

from qcol.policy_contract_catalog import build_wp2_contract_examples
from qcol.realization_variants import build_wp5_resolution_bundle

from .fingerprint import (
    AcceptanceEvidenceFingerprint,
    AcceptanceEvidenceRecord,
    DeclaredScaleContract,
    DependencyFingerprint,
    component_identity,
    binding_identities_from_public_plan,
)


WP6_DEPENDENCIES = {
    "python": "3.12",
    "qcol": "1.15.0",
    "numpy": "1.26.4",
    "scipy": "1.13.1",
    "cirq-core": "1.4.1",
    "openfermion": "1.6.1",
    "pyqasm": "1.0.4",
    "ply": "3.11",
}


def _payload_component(
    role: str,
    payload: Mapping[str, Any] | None,
    *,
    id_keys: tuple[str, ...],
    version_keys: tuple[str, ...] = ("policy_version", "version"),
    convention_id: str | None = None,
    applicability: str = "required",
):
    data = dict(payload or {})
    component_id = next((str(data[key]) for key in id_keys if data.get(key)), "not_applicable")
    component_version = next((str(data[key]) for key in version_keys if data.get(key)), "1.0.0")
    if component_id == "not_applicable":
        data = {"applicability": "not_applicable", "role": role}
        applicability = "not_applicable"
    return component_identity(
        role=role,
        component_id=component_id,
        component_version=component_version,
        snapshot=data,
        convention_id=convention_id,
        applicability=applicability,
    )


def build_wp6_valid_fingerprint() -> AcceptanceEvidenceFingerprint:
    bundle = build_wp5_resolution_bundle()
    resolution = bundle["resolutions"]["valid_execution"]
    context = resolution.candidate.rule_context.to_dict()
    examples = build_wp2_contract_examples()

    mapping = context["mapping"]
    ordering = context["ordering"]
    sector = context["sector"]
    state = context["state_preparation"]
    ansatz = context["ansatz"]
    measurement = context["measurement"]
    reference = context["reference"]
    model = context["model"]
    task = context["task"]

    sector_profiles = tuple(
        _payload_component(
            f"sector_profile.{row['quantity_id']}",
            row,
            id_keys=("profile_id", "quantity_id"),
        )
        for row in mapping.get("sector_profiles", ())
    )
    if not sector_profiles:
        sector_profiles = (
            _payload_component(
                "sector_profile.target",
                sector,
                id_keys=("sector_fingerprint",),
            ),
        )

    encoding_snapshot = {
        "encoding_context_fingerprint": ordering["encoding_context_fingerprint"],
        "mapping_convention_id": mapping["convention_id"],
        "ordering_id": ordering["ordering_id"],
        "sector_fingerprint": sector["sector_fingerprint"],
    }
    verification = examples["verification_policy"]
    tolerance = examples["tolerance_profile"]

    return AcceptanceEvidenceFingerprint(
        fingerprint_id="wp6.acceptance-fingerprint.valid-execution.v1",
        fingerprint_version="1.0.0",
        source_problem_fingerprint=str(model["source_problem_fingerprint"]),
        model_contract=_payload_component(
            "model_contract",
            {**model, "model_version": "1.0.0"},
            id_keys=("model_id",),
            version_keys=("model_version",),
        ),
        task_contract=_payload_component(
            "task_contract",
            {**task, "task_version": "1.0.0"},
            id_keys=("task_id",),
            version_keys=("task_version",),
        ),
        mapping_policy=_payload_component(
            "mapping_policy",
            {**mapping, "policy_version": "1.0.0"},
            id_keys=("policy_id", "mapping_id"),
            convention_id=str(mapping["convention_id"]),
        ),
        mode_ordering=_payload_component(
            "mode_ordering",
            {**ordering, "ordering_version": "1.0.0"},
            id_keys=("ordering_id",),
            version_keys=("ordering_version",),
        ),
        encoding_context=component_identity(
            role="encoding_context",
            component_id=str(ordering["encoding_context_fingerprint"]),
            component_version="1.0.0",
            snapshot=encoding_snapshot,
            convention_id=str(mapping["convention_id"]),
        ),
        sector_profiles=sector_profiles,
        state_preparation_policy=_payload_component(
            "state_preparation_policy",
            {**state, "policy_version": "1.0.0"},
            id_keys=("policy_id",),
            convention_id=str(mapping["convention_id"]),
        ),
        ansatz_policy=_payload_component(
            "ansatz_policy",
            {**ansatz, "policy_version": "1.0.0"},
            id_keys=("policy_id",),
            convention_id=str(mapping["convention_id"]),
        ),
        measurement_policy=_payload_component(
            "measurement_policy",
            {**measurement, "policy_version": "1.0.0"},
            id_keys=("policy_id",),
        ),
        reference_policy=_payload_component(
            "reference_policy",
            {**reference, "policy_version": "1.0.0"},
            id_keys=("policy_id",),
        ),
        verification_policy=component_identity(
            role="verification_policy",
            component_id=verification.policy_id,
            component_version=verification.policy_version,
            snapshot=verification.to_dict(),
        ),
        tolerance_profile=component_identity(
            role="tolerance_profile",
            component_id=tolerance.profile_id,
            component_version=tolerance.profile_version,
            snapshot=tolerance.to_dict(),
        ),
        implementation_bindings=binding_identities_from_public_plan(
            resolution.binding_plan.to_public_dict()
        ),
        dependencies=DependencyFingerprint(
            dependency_set_id="wp6.pinned-scientific-stack.v1",
            dependency_set_version="1.0.0",
            versions=WP6_DEPENDENCIES,
        ),
        declared_scale=DeclaredScaleContract(
            scale_id="wp6.general-spin-orbital.4m.2n.v1",
            scale_version="1.0.0",
            dimensions={
                "n_modes": int(resolution.candidate.declared_scale["n_modes"]),
                "n_particles": int(resolution.candidate.declared_scale["n_particles"]),
                "task": "ground_state_energy",
                "mapping": "jordan_wigner",
            },
            scope_statement="Exact WP6 fixture scale; no extrapolation beyond this declared composition and size.",
        ),
    )


def build_wp6_acceptance_record() -> AcceptanceEvidenceRecord:
    fingerprint = build_wp6_valid_fingerprint()
    return AcceptanceEvidenceRecord(
        record_id="wp6.acceptance-record.valid-execution.v1",
        record_version="1.0.0",
        acceptance_suite_id="wp7.generic-three-gate-harness.v1",
        resolved_variant_id="wp5.valid-execution.v1",
        evidence_fingerprint=fingerprint,
        accepted_claim="The exact bounded fixture is eligible for three-gate acceptance at the declared 4-mode, 2-particle scale only.",
        gate_report_ids=(
            "wp7.mapper.valid-execution.v1",
            "wp7.composition.valid-execution.v1",
            "wp7.cell.valid-execution.v1",
        ),
        evidence_archive_id="qcol_wp6_wp7_policy_foundation_evidence",
        created_by="qcol.wp6.fixture-builder.v1",
    )


def build_wp6_mutated_fingerprints() -> dict[str, AcceptanceEvidenceFingerprint]:
    base = build_wp6_valid_fingerprint()
    mutations: dict[str, AcceptanceEvidenceFingerprint] = {}

    def changed_component(component, *, suffix: str, convention_id: str | None = None):
        return replace(
            component,
            component_id=f"{component.component_id}.{suffix}",
            snapshot_fingerprint=("a" if component.snapshot_fingerprint[0] != "a" else "b") + component.snapshot_fingerprint[1:],
            convention_id=convention_id if convention_id is not None else component.convention_id,
        )

    mutations["model_contract_changed"] = replace(base, model_contract=changed_component(base.model_contract, suffix="changed"))
    mutations["task_contract_changed"] = replace(base, task_contract=changed_component(base.task_contract, suffix="changed"))
    mutations["mapping_convention_changed"] = replace(
        base,
        mapping_policy=changed_component(
            base.mapping_policy,
            suffix="new-convention",
            convention_id="openfermion.jw.alternate_endian.v2",
        ),
    )
    mutations["ordering_changed"] = replace(base, mode_ordering=changed_component(base.mode_ordering, suffix="reordered"))
    mutations["encoding_context_changed"] = replace(base, encoding_context=changed_component(base.encoding_context, suffix="changed"))
    mutations["sector_changed"] = replace(base, sector_profiles=(changed_component(base.sector_profiles[0], suffix="n3"),))
    mutations["state_preparation_changed"] = replace(base, state_preparation_policy=changed_component(base.state_preparation_policy, suffix="changed"))
    mutations["ansatz_changed"] = replace(base, ansatz_policy=changed_component(base.ansatz_policy, suffix="changed"))
    mutations["measurement_changed"] = replace(base, measurement_policy=changed_component(base.measurement_policy, suffix="changed"))
    mutations["reference_changed"] = replace(base, reference_policy=changed_component(base.reference_policy, suffix="changed"))
    mutations["verification_changed"] = replace(base, verification_policy=changed_component(base.verification_policy, suffix="changed"))
    mutations["tolerance_changed"] = replace(base, tolerance_profile=changed_component(base.tolerance_profile, suffix="looser"))
    mutations["dependency_changed"] = replace(
        base,
        dependencies=DependencyFingerprint(
            dependency_set_id=base.dependencies.dependency_set_id,
            dependency_set_version="1.0.1",
            versions={**dict(base.dependencies.versions), "openfermion": "1.8.1"},
        ),
    )
    mutations["declared_scale_20_modes"] = replace(
        base,
        declared_scale=DeclaredScaleContract(
            scale_id="wp6.general-spin-orbital.20m.10n.v1",
            scale_version="1.0.0",
            dimensions={
                "n_modes": 20,
                "n_particles": 10,
                "task": "ground_state_energy",
                "mapping": "jordan_wigner",
            },
            scope_statement="Different 20-mode scale; the 4-mode record is not evidence for this realization.",
        ),
    )
    return mutations


__all__ = [
    "WP6_DEPENDENCIES",
    "build_wp6_valid_fingerprint",
    "build_wp6_acceptance_record",
    "build_wp6_mutated_fingerprints",
]

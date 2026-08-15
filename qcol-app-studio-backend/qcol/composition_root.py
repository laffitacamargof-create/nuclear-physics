"""Step-2 composition-root contract for downstream scientific authority."""
from __future__ import annotations

from typing import Any

from .model_contracts import QuantumRealizationArtifact
from .runtime_integrity import stable_sha256


def public_composition_root_contract() -> dict[str, Any]:
    payload = {
        "schema_version": "qcol-composition-root-contract/2.0",
        "composition_root_type": "QuantumRealizationArtifact",
        "carrier_status": "confirmed",
        "executable_projection_type": "ProblemArtifact",
        "root_owner_id": "owner.capability_resolver",
        "invariant_id": "ARCH-COMP-001",
        "rule": (
            "The Resolver selects the complete scientific composition exactly once. "
            "Downstream services consume the canonical artifact and exact implementation "
            "bindings; they may not reconstruct or re-select scientific choices."
        ),
        "public_extension_seams": [
            "ModelPlugin",
            "TaskPlugin",
            "ExecutionAdapter",
        ],
        "internal_consumers_read_canonical_ir_directly": True,
        "external_consumers_read_public_view": True,
        "public_views_are_internal_bus": False,
        "downstream_reselection_allowed": False,
        "forbidden_downstream_actions": [
            "choose mapping",
            "choose encoding context",
            "choose sector",
            "choose state preparation",
            "choose ansatz",
            "choose measurement policy",
            "choose reference",
        ],
    }
    payload["fingerprint"] = stable_sha256(payload)
    return payload


def composition_root_identity(
    realization: QuantumRealizationArtifact,
) -> dict[str, Any]:
    payload = {
        "realization_id": realization.realization_id,
        "model_id": realization.model_id,
        "model_version": realization.model_version,
        "task_id": realization.task_id,
        "problem_artifact_id": realization.problem_artifact_id,
        "encoding_context_id": realization.encoding_context_id,
        "mapping_policy_id": realization.mapping_policy_id,
        "state_preparation_policy_id": realization.state_preparation_policy_id,
        "ansatz_policy_id": realization.ansatz_policy_id,
        "measurement_policy_id": realization.measurement_policy_id,
        "reference_policy_id": realization.reference_policy_id,
        "controller_id": realization.controller_id,
        "scientific_fingerprint": realization.scientific_fingerprint,
        "acceptance_certificate": dict(realization.acceptance_certificate),
        "resolved_plan_id": realization.resolved_plan_snapshot.get("plan_id"),
        "model_task_plan_id": realization.model_task_plan_snapshot.get("plan_id"),
    }
    return {
        "schema_version": "qcol-composition-root-identity/2.0",
        "payload": payload,
        "fingerprint": stable_sha256(payload),
    }


__all__ = ["public_composition_root_contract", "composition_root_identity"]

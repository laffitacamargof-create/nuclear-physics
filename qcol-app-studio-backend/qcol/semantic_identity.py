"""Hierarchical, classification-independent scientific and execution identities.

Scientific identity captures facts that change the scientific meaning of a
resolved realization.  Execution identity extends it with transport/backend
settings.  UI grouping, colors, labels, and panel ordering are intentionally
excluded.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .model_contracts import ModelContract, ModelInstance
from .runtime_integrity import stable_sha256

SCIENTIFIC_REALIZATION_IDENTITY_SCHEMA = "qcol-scientific-realization-identity/1.0"
EXECUTION_IDENTITY_SCHEMA = "qcol-execution-identity/1.0"


def _plain(value: Any) -> Any:
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return _plain(value.to_dict())
    if isinstance(value, Mapping):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_plain(v) for v in value]
    return value


def _policy_identity(contract: ModelContract) -> dict[str, Any]:
    return {
        "hamiltonian_policy_id": contract.hamiltonian_policy_id,
        "sector_policy_id": contract.sector_policy_id,
        "mapping_policy_id": contract.mapping_policy_id,
        "state_preparation_policy_id": contract.state_preparation_policy_id,
        "ansatz_policy_id": contract.ansatz_policy_id,
        "measurement_policy_id": contract.measurement_policy_id,
        "reference_policy_id": contract.reference_policy_id,
        "resource_policy_id": contract.resource_policy_id,
        "resource_estimation_rule_id": contract.resource_estimation_rule_id,
        "runtime_policy_id": contract.runtime_policy_id,
        "interpretation_policy_id": contract.interpretation_policy_id,
    }


def build_scientific_realization_payload(
    *,
    model_contract: ModelContract,
    model_instance: ModelInstance,
    task_identity: Mapping[str, Any] | None = None,
    resolved_policy_overrides: Mapping[str, Any] | None = None,
    ordering_identity: Mapping[str, Any] | None = None,
    sector_identity: Mapping[str, Any] | None = None,
    scientific_scale: Mapping[str, Any] | None = None,
    reference_regime: Mapping[str, Any] | None = None,
    representation_identity: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the canonical scientific identity payload.

    ``ModelContract.family`` and the complete descriptive classification are
    excluded.  Scientific identity is built only from authoritative model facts,
    instances, policies, ordering, sector, scale, and reference regimes.
    """
    policies = _policy_identity(model_contract)
    policies.update(_plain(resolved_policy_overrides or {}))
    instance = model_instance.to_dict()
    instance.pop("source_metadata", None)
    instance.pop("instance_id", None)
    return {
        "schema_version": SCIENTIFIC_REALIZATION_IDENTITY_SCHEMA,
        "model_contract": {
            "model_id": model_contract.model_id,
            "model_version": model_contract.model_version,
            "domain": model_contract.domain,
            "problem_type": model_contract.problem_type,
            "physical_phenomena": list(model_contract.physical_phenomena),
            "degrees_of_freedom": list(model_contract.degrees_of_freedom),
            "hamiltonian_components": list(model_contract.hamiltonian_components),
            "representation_contract": _plain(model_contract.representation_contract),
            "units": _plain(model_contract.units),
        },
        "model_instance": instance,
        "task_identity": _plain(
            task_identity
            or {"task_id": model_instance.task_id, "task_version": "declared-by-registry"}
        ),
        "policies": policies,
        "ordering_identity": _plain(ordering_identity or {}),
        "sector_identity": _plain(sector_identity or model_instance.target_sector),
        "scientific_scale": _plain(
            scientific_scale
            or {
                "resource_validity": model_contract.resource_validity.to_dict(),
                "reference_validity": model_contract.reference_validity.to_dict(),
            }
        ),
        "reference_regime": _plain(
            reference_regime
            or {
                "reference_policy_id": model_contract.reference_policy_id,
                "validity": model_contract.reference_validity.to_dict(),
            }
        ),
        "representation_identity": _plain(
            representation_identity
            or {
                "representation_contract": model_contract.representation_contract,
                "mapping_policy_id": model_contract.mapping_policy_id,
            }
        ),
        "excluded_presentation_fields": [
            "model_family",
            "ui_group_id",
            "ui_group_label",
            "model_classification_contract",
            "discovery_tags",
            "display_label",
            "ui_color",
            "panel_order",
        ],
    }


def scientific_realization_fingerprint(**kwargs: Any) -> str:
    return stable_sha256(build_scientific_realization_payload(**kwargs))


def build_execution_identity_payload(
    *,
    scientific_fingerprint: str,
    executable_artifact_hash: str,
    adapter_identity: Mapping[str, Any],
    backend_identity: Mapping[str, Any],
    shots: int,
    seed: int | None,
    execution_settings: Mapping[str, Any] | None = None,
    circuit_hashes: Sequence[str] = (),
) -> dict[str, Any]:
    return {
        "schema_version": EXECUTION_IDENTITY_SCHEMA,
        "scientific_realization_fingerprint": str(scientific_fingerprint),
        "executable_artifact_hash": str(executable_artifact_hash),
        "adapter_identity": _plain(adapter_identity),
        "backend_identity": _plain(backend_identity),
        "shots": int(shots),
        "seed": None if seed is None else int(seed),
        "execution_settings": _plain(execution_settings or {}),
        "circuit_hashes": [str(v) for v in circuit_hashes],
    }


def execution_fingerprint(**kwargs: Any) -> str:
    return stable_sha256(build_execution_identity_payload(**kwargs))


@dataclass(frozen=True)
class SemanticIdentityRecord:
    identity_id: str
    scientific_payload: Mapping[str, Any]
    scientific_fingerprint: str
    execution_payload: Mapping[str, Any] | None = None
    execution_fingerprint: str | None = None
    limitations: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "qcol-semantic-identity-record/1.0",
            "identity_id": self.identity_id,
            "scientific_payload": _plain(self.scientific_payload),
            "scientific_fingerprint": self.scientific_fingerprint,
            "execution_payload": _plain(self.execution_payload),
            "execution_fingerprint": self.execution_fingerprint,
            "limitations": list(self.limitations),
        }


__all__ = [
    "SCIENTIFIC_REALIZATION_IDENTITY_SCHEMA",
    "EXECUTION_IDENTITY_SCHEMA",
    "SemanticIdentityRecord",
    "build_scientific_realization_payload",
    "scientific_realization_fingerprint",
    "build_execution_identity_payload",
    "execution_fingerprint",
]

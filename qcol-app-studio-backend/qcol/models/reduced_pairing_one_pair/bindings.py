"""Compatibility bindings for the verified one-pair model plugin.

The public names are retained for older notebooks, but they now delegate to the
actual callable Capability Resolver rather than returning a Phase-2 declaration.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping

from ...model_contracts import CapabilityReport, ModelInstance, QuantumRealizationArtifact, ResolvedModelPlan
from ...model_instance_adapters import one_pair_instance
from .contract import MODEL_ID, ONE_PAIR_MODEL_CONTRACT

ONE_PAIR_POLICY_BINDINGS: Dict[str, str] = {
    "hamiltonian": ONE_PAIR_MODEL_CONTRACT.hamiltonian_policy_id,
    "sector": ONE_PAIR_MODEL_CONTRACT.sector_policy_id,
    "mapping": ONE_PAIR_MODEL_CONTRACT.mapping_policy_id,
    "state_preparation": ONE_PAIR_MODEL_CONTRACT.state_preparation_policy_id,
    "ansatz": ONE_PAIR_MODEL_CONTRACT.ansatz_policy_id,
    "measurement": ONE_PAIR_MODEL_CONTRACT.measurement_policy_id,
    "reference": ONE_PAIR_MODEL_CONTRACT.reference_policy_id,
    "resource": ONE_PAIR_MODEL_CONTRACT.resource_policy_id,
    "runtime": ONE_PAIR_MODEL_CONTRACT.runtime_policy_id,
    "interpretation": ONE_PAIR_MODEL_CONTRACT.interpretation_policy_id,
}


def model_instance_from_request(request: Mapping[str, Any]) -> ModelInstance:
    return one_pair_instance(request, ONE_PAIR_MODEL_CONTRACT)


def declared_resolved_plan(instance: ModelInstance) -> ResolvedModelPlan:
    """Backward-compatible name returning the actual callable resolved plan."""
    from ...resolver import resolve_model
    return resolve_model(instance)


def declared_capability_report(instance: ModelInstance) -> CapabilityReport:
    return declared_resolved_plan(instance).capability_report


def build_one_pair_quantum_realization(request: Mapping[str, Any]) -> QuantumRealizationArtifact:
    from ...realization import resolve_request_to_quantum_realization
    payload = dict(request)
    payload["model_id"] = MODEL_ID
    payload.setdefault("method", "fermion_pairing")
    realization = resolve_request_to_quantum_realization(payload)
    realization.validate_bridge()
    return realization

"""Request normalization shared by UI, API, CLI, tests, and scientific runtime."""
from __future__ import annotations

from typing import Any, Dict, Mapping

from .fermion_registry import normalize_fermion_request
from .entry_normalization import normalize_once
from .model_instance_adapters import instance_from_request
from .request_boundaries import normalize_request_boundaries


def normalize_run_request(request: Mapping[str, Any]) -> Dict[str, Any]:
    """Normalize a request through both problem and model contracts.

    The legacy fermion problem registry still owns problem-specific UI rules
    (for example, the four-level benchmark is fixed to exactly four levels),
    while the domain-neutral ModelContract owns the executable model plugin.
    The result preserves legacy fields and adds canonical model/task/sector
    metadata. Invalid requests are rejected before a RunRecord is created.
    """
    payload = normalize_request_boundaries(request)
    if str(payload.get("method", "")) == "fermion_pairing":
        payload = normalize_fermion_request(payload, require_executable=True)

    payload = normalize_once(payload, source="shared_request_boundary")
    instance = instance_from_request(payload)
    public_instance = instance.to_dict()
    payload["task_id"] = instance.task_id
    payload["parameters"] = public_instance["parameters"]
    payload["target_sector"] = public_instance["target_sector"]
    payload["requested_observables"] = public_instance["requested_observables"]
    payload["model_version"] = instance.model_version
    # Return only ordinary dict/list/tuple request data. This makes repeated
    # normalization idempotent and prevents frozen contract mappings from
    # leaking back into request-boundary deepcopy operations.
    return normalize_request_boundaries(payload)

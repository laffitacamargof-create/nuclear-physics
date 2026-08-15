"""Compatibility builder for the verified one-pair model plugin.

The actual construction is now performed by the domain-neutral capability
resolver and policy registries.  This wrapper keeps older notebook/test imports
valid without preserving a second builder implementation.
"""
from __future__ import annotations

from typing import Any, Mapping


def build_one_pair_problem_artifact(request: Mapping[str, Any]):
    from ...realization import resolve_request_to_quantum_realization

    payload = dict(request)
    payload["model_id"] = "nuclear.reduced_pairing.one_pair"
    payload.setdefault("method", "fermion_pairing")
    return resolve_request_to_quantum_realization(payload).runtime_artifact

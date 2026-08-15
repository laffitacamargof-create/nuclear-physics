"""Public declarative realization-policy contracts introduced by WP2.

Contracts are loaded lazily so the mapping and sector packages are safe under
all import orders.  Public behavior and serialized contract payloads are
unchanged.
"""
from __future__ import annotations

from importlib import import_module
from typing import Any

from .base import PolicyContractError, DeclarativeContract, contains_callable

_LAZY = {
    "ModeOrderingContract": ("qcol.realization_policies.ordering", "ModeOrderingContract"),
    "EncodingContext": ("qcol.realization_policies.ordering", "EncodingContext"),
    "SectorEncodingProfile": ("qcol.realization_policies.sector", "SectorEncodingProfile"),
    "StatePreparationPolicyContract": (
        "qcol.realization_policies.state_preparation",
        "StatePreparationPolicyContract",
    ),
    "AnsatzPolicyContract": ("qcol.realization_policies.ansatz", "AnsatzPolicyContract"),
    "MeasurementPolicyContract": (
        "qcol.realization_policies.measurement",
        "MeasurementPolicyContract",
    ),
    "ReferencePolicyContract": ("qcol.realization_policies.reference", "ReferencePolicyContract"),
    "VerificationPolicyContract": (
        "qcol.realization_policies.verification",
        "VerificationPolicyContract",
    ),
}


def __getattr__(name: str) -> Any:
    target = _LAZY.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, attribute_name = target
    value = getattr(import_module(module_name), attribute_name)
    globals()[name] = value
    return value


__all__ = [
    "PolicyContractError",
    "DeclarativeContract",
    "contains_callable",
    "ModeOrderingContract",
    "EncodingContext",
    "SectorEncodingProfile",
    "StatePreparationPolicyContract",
    "AnsatzPolicyContract",
    "MeasurementPolicyContract",
    "ReferencePolicyContract",
    "VerificationPolicyContract",
]

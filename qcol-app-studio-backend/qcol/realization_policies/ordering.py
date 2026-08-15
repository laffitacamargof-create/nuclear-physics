"""Mode ordering and shared encoding-context declarations."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .base import (
    DeclarativeContract,
    PolicyContractError,
    freeze_json,
    require_text,
    require_token,
)


MODE_ORDERING_SCHEMA_VERSION = "qcol-mode-ordering-contract/1.0"
ENCODING_CONTEXT_SCHEMA_VERSION = "qcol-encoding-context/1.0"


@dataclass(frozen=True)
class ModeOrderingContract(DeclarativeContract):
    ordering_id: str
    ordering_version: str
    ordered_mode_labels: tuple[str, ...]
    mode_index_convention: str
    qubit_index_convention: str
    endian_convention: str
    bitstring_display_convention: str
    species_order: tuple[str, ...] = field(default_factory=tuple)
    spin_order: tuple[str, ...] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = MODE_ORDERING_SCHEMA_VERSION

    def __post_init__(self) -> None:
        require_token("ordering_id", self.ordering_id)
        require_token("ordering_version", self.ordering_version)
        labels = tuple(require_text("ordered_mode_labels", str(item)) for item in self.ordered_mode_labels)
        if not labels:
            raise PolicyContractError("ordered_mode_labels must contain at least one mode.")
        if len(set(labels)) != len(labels):
            raise PolicyContractError("ordered_mode_labels must be unique and ordered explicitly.")
        object.__setattr__(self, "ordered_mode_labels", labels)
        for name in (
            "mode_index_convention",
            "qubit_index_convention",
            "endian_convention",
            "bitstring_display_convention",
        ):
            require_token(name, getattr(self, name))
        object.__setattr__(self, "species_order", tuple(require_text("species_order", str(v)) for v in self.species_order))
        object.__setattr__(self, "spin_order", tuple(require_text("spin_order", str(v)) for v in self.spin_order))
        object.__setattr__(self, "metadata", freeze_json(self.metadata, path="ModeOrderingContract.metadata"))

    @property
    def n_modes(self) -> int:
        return len(self.ordered_mode_labels)


@dataclass(frozen=True)
class EncodingContext(DeclarativeContract):
    context_id: str
    context_version: str
    mapping_policy_id: str
    mapping_policy_version: str
    mapping_convention_id: str
    mode_ordering: ModeOrderingContract
    n_qubits: int
    target_sector_fingerprint: str
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = ENCODING_CONTEXT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in (
            "context_id",
            "context_version",
            "mapping_policy_id",
            "mapping_policy_version",
            "mapping_convention_id",
            "target_sector_fingerprint",
        ):
            require_token(name, getattr(self, name))
        if not isinstance(self.mode_ordering, ModeOrderingContract):
            raise PolicyContractError("mode_ordering must be a ModeOrderingContract.")
        if int(self.n_qubits) <= 0:
            raise PolicyContractError("n_qubits must be positive.")
        object.__setattr__(self, "n_qubits", int(self.n_qubits))
        object.__setattr__(self, "metadata", freeze_json(self.metadata, path="EncodingContext.metadata"))

    @property
    def mode_ordering_fingerprint(self) -> str:
        return self.mode_ordering.fingerprint()

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload["mode_ordering_fingerprint"] = self.mode_ordering_fingerprint
        return payload


__all__ = [
    "MODE_ORDERING_SCHEMA_VERSION",
    "ENCODING_CONTEXT_SCHEMA_VERSION",
    "ModeOrderingContract",
    "EncodingContext",
]

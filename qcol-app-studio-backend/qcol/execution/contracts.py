"""Execution-boundary contracts.

Adapters own transport, backend invocation, and canonical result normalization.
They never reinterpret Hamiltonians, sectors, ansätze, or references.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Protocol, Sequence, runtime_checkable


@dataclass(frozen=True)
class ExecutionAdapterDescriptor:
    adapter_id: str
    adapter_version: str
    provider: str
    execution_mode: str
    backend_kind: str
    capabilities: tuple[str, ...]
    limitations: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "qcol-execution-adapter-descriptor/1.0",
            "adapter_id": self.adapter_id,
            "adapter_version": self.adapter_version,
            "provider": self.provider,
            "execution_mode": self.execution_mode,
            "backend_kind": self.backend_kind,
            "capabilities": list(self.capabilities),
            "limitations": list(self.limitations),
        }


@runtime_checkable
class ExecutionAdapter(Protocol):
    """The only behavioural public extension seam in Step 2."""

    descriptor: ExecutionAdapterDescriptor

    def run_measurement(
        self,
        circuit: Any,
        *,
        repetitions: int,
        seed: int,
    ) -> "CanonicalExecutionResult": ...

    def simulate_statevector(
        self,
        circuit: Any,
        *,
        qubit_order: Iterable[Any],
    ) -> Any: ...


@dataclass(frozen=True)
class CanonicalExecutionResult:
    measurement_bits: Any
    counts: Mapping[str, int]
    imported_qubit_order: tuple[str, ...]
    shots_requested: int
    shots_observed: int
    adapter: ExecutionAdapterDescriptor
    raw_result_type: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def public_dict(self, *, include_counts: bool = True) -> dict[str, Any]:
        return {
            "schema_version": "qcol-canonical-execution-result/1.0",
            "counts": (
                {str(k): int(v) for k, v in self.counts.items()}
                if include_counts
                else None
            ),
            "imported_qubit_order": list(self.imported_qubit_order),
            "shots_requested": int(self.shots_requested),
            "shots_observed": int(self.shots_observed),
            "adapter": self.adapter.to_dict(),
            "raw_result_type": self.raw_result_type,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ExecutionRequestParameterSpec:
    key: str
    label: str
    kind: str
    default: Any = None
    minimum: int | float | None = None
    allowed_values: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "kind": self.kind,
            "default": self.default,
            "minimum": self.minimum,
            "allowed_values": list(self.allowed_values),
        }


@dataclass(frozen=True)
class ExecutionRequestContract:
    contract_id: str
    contract_version: str
    parameter_schema: tuple[ExecutionRequestParameterSpec, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "qcol-execution-request-contract/1.0",
            "contract_id": self.contract_id,
            "contract_version": self.contract_version,
            "owner_id": "owner.execution_target",
            "parameter_schema": [row.to_dict() for row in self.parameter_schema],
            "ui_projection_only": True,
        }


DEFAULT_EXECUTION_REQUEST_CONTRACT = ExecutionRequestContract(
    contract_id="execution.request.local_and_provider_target.v1",
    contract_version="1.0.0",
    parameter_schema=(
        ExecutionRequestParameterSpec(
            "target_backend",
            "Provider target",
            "choice",
            "ibm",
            allowed_values=("ibm", "google", "aws"),
        ),
        ExecutionRequestParameterSpec(
            "execution_mode",
            "Execution mode",
            "choice",
            "local_simulator",
            allowed_values=("local_simulator",),
        ),
        ExecutionRequestParameterSpec(
            "shots", "Shots per measurement group", "integer", 1024, minimum=1
        ),
        ExecutionRequestParameterSpec(
            "final_shots",
            "Final shots per measurement group",
            "integer",
            1024,
            minimum=1,
        ),
        ExecutionRequestParameterSpec("seed", "Execution seed", "integer", 42),
    ),
)


def public_execution_request_contract() -> dict[str, Any]:
    return DEFAULT_EXECUTION_REQUEST_CONTRACT.to_dict()


__all__ = [
    "ExecutionAdapter",
    "ExecutionAdapterDescriptor",
    "CanonicalExecutionResult",
    "ExecutionRequestParameterSpec",
    "ExecutionRequestContract",
    "DEFAULT_EXECUTION_REQUEST_CONTRACT",
    "public_execution_request_contract",
]

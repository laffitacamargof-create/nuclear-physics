"""Dependency-light execution-boundary public API.

Registry access is imported lazily so the single Step-2 plugin registry can
register the built-in execution adapter without a package-import cycle.
"""
from .contracts import (
    CanonicalExecutionResult,
    ExecutionAdapter,
    ExecutionAdapterDescriptor,
    ExecutionRequestParameterSpec,
    ExecutionRequestContract,
    DEFAULT_EXECUTION_REQUEST_CONTRACT,
    public_execution_request_contract,
)
from .descriptors import LOCAL_AER_DESCRIPTOR, LOCAL_CIRQ_DESCRIPTOR


def get_execution_adapter(adapter_id: str = "execution.local_cirq.v1"):
    from .registry import get_execution_adapter as _get

    return _get(adapter_id)


def public_execution_adapter_catalog():
    from .registry import public_execution_adapter_catalog as _catalog

    return _catalog()


def run_pipeline_with_execution_adapter(request, *, adapter_id="execution.local_aer.v1"):
    from .e1 import run_pipeline_with_execution_adapter as _run
    return _run(request, adapter_id=adapter_id)


def __getattr__(name):
    if name == "ExecutionAdapterRegistryError":
        from .registry import ExecutionAdapterRegistryError

        return ExecutionAdapterRegistryError
    raise AttributeError(name)


__all__ = [
    "CanonicalExecutionResult",
    "ExecutionAdapter",
    "ExecutionAdapterDescriptor",
    "ExecutionRequestParameterSpec",
    "ExecutionRequestContract",
    "DEFAULT_EXECUTION_REQUEST_CONTRACT",
    "public_execution_request_contract",
    "LOCAL_CIRQ_DESCRIPTOR",
    "LOCAL_AER_DESCRIPTOR",
    "ExecutionAdapterRegistryError",
    "get_execution_adapter",
    "public_execution_adapter_catalog",
    "run_pipeline_with_execution_adapter",
]

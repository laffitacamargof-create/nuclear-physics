"""Post-freeze E1 entry helpers.

These helpers select a registered ExecutionAdapter and then call the frozen
``run_pipeline(request)`` unchanged.  They are not a second scientific
workflow.
"""
from __future__ import annotations

from typing import Any, Mapping

from .registry import get_execution_adapter
from .selection import use_execution_adapter

LOCAL_AER_ADAPTER_ID = "execution.local_aer.v1"


def _attest_result_adapter(result, *, adapter_id: str) -> None:
    records = list(getattr(result, "raw_records", ()) or ())
    used = {
        str(record.get("execution_adapter", {}).get("adapter_id", ""))
        for record in records
        if isinstance(record, Mapping)
    }
    used.discard("")
    if records and used != {adapter_id}:
        raise AssertionError(
            f"Expected every execution record to use {adapter_id!r}; observed {sorted(used)!r}."
        )
    result.adapter_status = (
        f"accepted post-freeze execution adapter {adapter_id}; "
        "local ideal simulator; no remote provider or hardware submission"
    )


def run_pipeline_with_execution_adapter(
    request: Mapping[str, Any],
    *,
    adapter_id: str = LOCAL_AER_ADAPTER_ID,
):
    """Execute through the frozen pipeline with an explicit adapter selection."""
    get_execution_adapter(adapter_id)  # exact binding/Protocol validation
    from qcol.orchestrator import run_pipeline

    with use_execution_adapter(adapter_id):
        artifact, result = run_pipeline(request)
    _attest_result_adapter(result, adapter_id=adapter_id)
    return artifact, result


__all__ = ["LOCAL_AER_ADAPTER_ID", "run_pipeline_with_execution_adapter"]

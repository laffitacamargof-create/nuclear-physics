"""WP5 runtime-entry guard.

This is a gate in front of the existing shared QCOL execution services, not a second runtime.  It
routes an accepted analysis-only variant to an analysis handler and an accepted
circuit variant to the shared execution handler.  Rejected or unresolved
variants invoke neither.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from qcol.realization_policies.base import json_contract_value

from .contracts import RealizationResolution, RuntimeDispatchReport
from .enums import RuntimeEntryStatus, RuntimePath


def _public_result(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return json_contract_value(value)
    if hasattr(value, "to_dict"):
        return json_contract_value(value.to_dict())
    return {"result_type": f"{type(value).__module__}.{type(value).__name__}", "repr": str(value)}


def dispatch_resolved_variant(
    resolution: RealizationResolution,
    *,
    analysis_runner: Callable[[dict[str, Any]], Any] | None = None,
    execution_runner: Callable[[dict[str, Any]], Any] | None = None,
) -> RuntimeDispatchReport:
    if not isinstance(resolution, RealizationResolution):
        raise TypeError("resolution must be RealizationResolution.")
    decision = resolution.variant.runtime_entry
    trace = [
        "resolver_complete",
        f"runtime_entry_status={decision.status.value}",
        f"requested_path={decision.path.value}",
    ]
    if not decision.permitted:
        trace.extend(
            [
                "runtime_entry_blocked",
                "measurement_not_called",
                "qasm_not_called",
                "simulator_not_called",
                "hardware_not_called",
            ]
        )
        return RuntimeDispatchReport(
            variant_id=resolution.variant.variant_id,
            entry_status=decision.status,
            requested_path=RuntimePath.NONE,
            dispatched=False,
            invoked_handler=None,
            blocked_codes=decision.blocking_codes,
            trace=tuple(trace),
            result_summary={},
        )

    public_payload = resolution.to_public_dict()
    if decision.path is RuntimePath.ANALYSIS_CONTROLLER:
        if analysis_runner is None:
            trace.append("analysis_handler_missing")
            return RuntimeDispatchReport(
                variant_id=resolution.variant.variant_id,
                entry_status=RuntimeEntryStatus.DEFERRED,
                requested_path=RuntimePath.ANALYSIS_CONTROLLER,
                dispatched=False,
                invoked_handler=None,
                blocked_codes=("ANALYSIS_HANDLER_MISSING",),
                trace=tuple(trace),
                result_summary={},
            )
        result = analysis_runner(public_payload)
        trace.extend(
            [
                "analysis_controller_invoked",
                "shared_execution_pipeline_not_called",
                "measurement_not_called",
                "qasm_not_called",
            ]
        )
        return RuntimeDispatchReport(
            variant_id=resolution.variant.variant_id,
            entry_status=decision.status,
            requested_path=RuntimePath.ANALYSIS_CONTROLLER,
            dispatched=True,
            invoked_handler="analysis_runner",
            blocked_codes=(),
            trace=tuple(trace),
            result_summary=_public_result(result),
        )

    if execution_runner is None:
        trace.append("shared_execution_handler_missing")
        return RuntimeDispatchReport(
            variant_id=resolution.variant.variant_id,
            entry_status=RuntimeEntryStatus.DEFERRED,
            requested_path=RuntimePath.SHARED_EXECUTION_PIPELINE,
            dispatched=False,
            invoked_handler=None,
            blocked_codes=("SHARED_EXECUTION_HANDLER_MISSING",),
            trace=tuple(trace),
            result_summary={},
        )
    result = execution_runner(public_payload)
    trace.extend(
        [
            "existing_shared_execution_pipeline_invoked",
            "no_second_runtime_created",
        ]
    )
    return RuntimeDispatchReport(
        variant_id=resolution.variant.variant_id,
        entry_status=decision.status,
        requested_path=RuntimePath.SHARED_EXECUTION_PIPELINE,
        dispatched=True,
        invoked_handler="execution_runner",
        blocked_codes=(),
        trace=tuple(trace),
        result_summary=_public_result(result),
    )


__all__ = ["dispatch_resolved_variant"]

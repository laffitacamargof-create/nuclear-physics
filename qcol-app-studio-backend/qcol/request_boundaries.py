"""Hard boundaries between model, task, and run-control parameters.

The ModelContract validates physical/model parameters only. TaskContract
parameters describe the selected scientific controller. Mapping selection,
acceptance thresholds, backend controls, and sampling controls remain at
request scope.

Legacy interfaces sometimes nested request-level controls inside
``parameters`` or ``task_parameters``. The helpers below hoist only known
request-level keys, reject conflicts, and leave genuinely undeclared task
parameters visible to TaskContract validation.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Mapping


RUN_CONTROL_KEYS = frozenset({
    "acceptance_abs_floor",
    "sector_leakage_floor",
    "mapping_id",
    "shots",
    "final_shots",
    "max_evaluations",
    "energy_tolerance",
    "convergence_patience",
    "rhobeg",
    "seed",
    "run_mode",
    "target_backend",
    "execution_mode",
    "interface_mode",
    "model_family_label",
    "initial_parameters",
    "task_id",
    "task_parameters",
    "requested_observables",
    "model_id",
    "model_version",
})

# These values appeared inside ``task_parameters`` in some Phase A.3.2
# requests, but they are not parameters declared by the ground-state
# TaskContract.
REQUEST_LEVEL_TASK_CONTROL_KEYS = frozenset({
    "mapping_id",
    "sector_leakage_floor",
    "acceptance_abs_floor",
})


class RequestBoundaryError(ValueError):
    """Raised when one control is declared inconsistently across scopes."""


def copy_plain_data(value: Any) -> Any:
    """Recursively copy request data without pickling frozen mapping views.

    QCOL contracts deliberately freeze nested mappings with ``MappingProxyType``.
    A normalized request may therefore contain read-only mappings when it is
    passed through a second boundary. ``copy.deepcopy`` cannot pickle those
    views. This helper converts every Mapping into an ordinary dict while
    preserving the surrounding sequence type and independently copying scalar
    or scientific leaf values.
    """
    if isinstance(value, Mapping):
        return {key: copy_plain_data(item) for key, item in value.items()}
    if isinstance(value, list):
        return [copy_plain_data(item) for item in value]
    if isinstance(value, tuple):
        return tuple(copy_plain_data(item) for item in value)
    if isinstance(value, set):
        return {copy_plain_data(item) for item in value}
    if isinstance(value, frozenset):
        return frozenset(copy_plain_data(item) for item in value)
    return deepcopy(value)


def _mapping_copy(value: Any, *, label: str) -> Dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise RequestBoundaryError(f"{label} must be a mapping.")
    copied = copy_plain_data(value)
    assert isinstance(copied, dict)
    return copied


def _hoist(
    payload: Dict[str, Any],
    *,
    container_key: str,
    keys: frozenset[str],
) -> Dict[str, Any]:
    nested = _mapping_copy(payload.get(container_key, {}), label=f"request.{container_key}")
    for key in sorted(keys):
        if key not in nested:
            continue
        nested_value = nested.pop(key)
        if key in payload and payload[key] != nested_value:
            raise RequestBoundaryError(
                f"Conflicting request-level value for {key!r}: "
                f"request root={payload[key]!r}, "
                f"{container_key}={nested_value!r}."
            )
        payload.setdefault(key, nested_value)
    payload[container_key] = nested
    return payload


def separate_model_and_run_parameters(request: Mapping[str, Any]) -> Dict[str, Any]:
    """Hoist known run controls accidentally nested inside model parameters."""
    payload = copy_plain_data(request)
    if not isinstance(payload, dict):
        raise RequestBoundaryError("request must be a mapping.")
    return _hoist(payload, container_key="parameters", keys=RUN_CONTROL_KEYS)


def separate_task_and_request_controls(request: Mapping[str, Any]) -> Dict[str, Any]:
    """Hoist mapping/verification controls accidentally nested in task parameters.

    Unknown task parameters are not discarded; TaskContract validation still
    rejects them. This function repairs only the explicitly supported legacy
    boundary.
    """
    payload = copy_plain_data(request)
    if not isinstance(payload, dict):
        raise RequestBoundaryError("request must be a mapping.")
    return _hoist(
        payload,
        container_key="task_parameters",
        keys=REQUEST_LEVEL_TASK_CONTROL_KEYS,
    )


def normalize_request_boundaries(request: Mapping[str, Any]) -> Dict[str, Any]:
    """Apply model-parameter and task-parameter boundaries idempotently."""
    return separate_task_and_request_controls(
        separate_model_and_run_parameters(request)
    )

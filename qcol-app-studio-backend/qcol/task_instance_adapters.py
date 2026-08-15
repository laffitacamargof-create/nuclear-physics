"""Request-to-TaskInstance factories selected by TaskPlugin descriptors."""
from __future__ import annotations

from typing import Any, Dict, Mapping
from uuid import uuid4

from .task_contracts import TaskContract, TaskInstance


def _default_task_parameters(contract: TaskContract) -> Dict[str, Any]:
    parameters: Dict[str, Any] = {}
    for spec in contract.parameter_schema:
        if spec.default is not None:
            parameters[spec.key] = spec.default
    return parameters


def _build_task_instance(
    contract: TaskContract,
    *,
    parameters: Mapping[str, Any],
    observables: tuple[str, ...],
    source: str = "QCOL request",
) -> TaskInstance:
    instance = TaskInstance(
        instance_id=f"task-instance-{uuid4().hex[:12]}",
        task_id=contract.task_id,
        task_version=contract.task_version,
        parameters=dict(parameters),
        requested_observables=tuple(observables),
        source_metadata={"source": source},
    )
    instance.validate_against(contract)
    return instance


def ground_state_task_instance(
    request: Mapping[str, Any],
    contract: TaskContract,
) -> TaskInstance:
    parameters = _default_task_parameters(contract)
    parameters.update(dict(request.get("task_parameters", {})))
    parameters["run_mode"] = str(
        request.get("run_mode", parameters.get("run_mode", "vqe"))
    )
    parameters["optimizer"] = str(
        request.get("optimizer", parameters.get("optimizer", "COBYLA"))
    )
    parameters["max_evaluations"] = int(
        request.get("max_evaluations", parameters.get("max_evaluations", 40))
    )
    parameters["optimizer_tolerance"] = float(
        request.get(
            "optimizer_tolerance",
            parameters.get("optimizer_tolerance", 1e-3),
        )
    )
    return _build_task_instance(
        contract,
        parameters=parameters,
        observables=("energy",),
    )


def mapping_analysis_task_instance(
    request: Mapping[str, Any],
    contract: TaskContract,
) -> TaskInstance:
    parameters = _default_task_parameters(contract)
    parameters.update(dict(request.get("task_parameters", {})))
    mapping_ids = parameters.get("mapping_ids") or (
        "jordan_wigner.v1",
        "bravyi_kitaev.v1",
    )
    if isinstance(mapping_ids, str):
        mapping_ids = tuple(
            item.strip() for item in mapping_ids.split(",") if item.strip()
        )
    parameters["mapping_ids"] = tuple(mapping_ids)
    parameters["coefficient_threshold"] = float(
        parameters.get("coefficient_threshold", 1e-12)
    )
    parameters["equivalence_tolerance"] = float(
        parameters.get("equivalence_tolerance", 1e-8)
    )
    return _build_task_instance(
        contract,
        parameters=parameters,
        observables=("mapping_resources", "mapping_equivalence"),
    )


def observable_task_instance(
    request: Mapping[str, Any],
    contract: TaskContract,
) -> TaskInstance:
    parameters = _default_task_parameters(contract)
    parameters.update(dict(request.get("task_parameters", {})))
    observables = tuple(
        request.get("requested_observables")
        or parameters.get("observable_ids")
        or ("pair_occupations",)
    )
    parameters["observable_ids"] = observables
    if "parameter_values" in parameters:
        parameters["parameter_values"] = tuple(
            parameters.get("parameter_values") or ()
        )
    return _build_task_instance(
        contract,
        parameters=parameters,
        observables=observables,
    )


def future_task_instance(
    request: Mapping[str, Any],
    contract: TaskContract,
) -> TaskInstance:
    parameters = _default_task_parameters(contract)
    parameters.update(dict(request.get("task_parameters", {})))
    observables = tuple(request.get("requested_observables") or ())
    return _build_task_instance(
        contract,
        parameters=parameters,
        observables=observables,
    )


def task_instance_from_request(request: Mapping[str, Any]) -> TaskInstance:
    from .plugin_registry import get_task_plugin

    plugin = get_task_plugin(request.get("task_id") or "ground_state_energy")
    return plugin.build_instance(request)


__all__ = [
    "task_instance_from_request",
    "ground_state_task_instance",
    "mapping_analysis_task_instance",
    "observable_task_instance",
    "future_task_instance",
]

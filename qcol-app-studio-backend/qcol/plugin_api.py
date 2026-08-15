"""The two descriptor-based scientific extension seams.

Step 2 exposes exactly three public extension concepts across QCOL:
``ModelPlugin``, ``TaskPlugin``, and ``ExecutionAdapter``.  Model and task
variation is primarily declarative, so frozen descriptors are sufficient.
Execution is behavioural and is represented by the protocol in
:mod:`qcol.execution.contracts`.

Descriptors bind existing semantic owners; they do not restate their science.
Public projections expose only exact binding identities, never callable
payloads.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping


ModelInstanceFactory = Callable[[Mapping[str, Any], Any], Any]
TaskInstanceFactory = Callable[[Mapping[str, Any], Any], Any]
EncodingContextFactory = Callable[..., str]
ScientificIdentityFactory = Callable[..., Mapping[str, Any]]


def _binding(value: Callable[..., Any]) -> str:
    module = getattr(value, "__module__", None)
    name = getattr(value, "__qualname__", None) or getattr(value, "__name__", None)
    if not module or not name:
        raise TypeError("Plugin callables must publish an exact module-qualified binding.")
    return f"{module}:{name}"


@dataclass(frozen=True)
class ModelPlugin:
    """One registration surface for a model extension.

    ``contract`` remains the OWNER of model science.  The descriptor selects
    only boundary materialisation and the two plugin-owned identity factories
    needed by the composition root.
    """

    plugin_id: str
    plugin_version: str
    contract: Any = field(repr=False, compare=False)
    instance_factory: ModelInstanceFactory = field(repr=False, compare=False)
    encoding_context_factory: EncodingContextFactory = field(
        repr=False, compare=False
    )
    scientific_identity_factory: ScientificIdentityFactory = field(
        repr=False, compare=False
    )
    capabilities: tuple[str, ...] = field(default_factory=tuple)
    mapping_acceptance_modes: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if str(self.contract.model_id) != str(self.plugin_id):
            raise ValueError("ModelPlugin plugin_id must equal ModelContract.model_id.")
        for label, value in (
            ("instance_factory", self.instance_factory),
            ("encoding_context_factory", self.encoding_context_factory),
            ("scientific_identity_factory", self.scientific_identity_factory),
        ):
            if not callable(value):
                raise TypeError(f"ModelPlugin {label} must be callable.")
        object.__setattr__(
            self,
            "capabilities",
            tuple(sorted({str(value) for value in self.capabilities})),
        )
        modes = tuple((str(task_id), str(mode)) for task_id, mode in self.mapping_acceptance_modes)
        allowed = {"full", "analysis_only", "not_applicable"}
        if any(mode not in allowed for _, mode in modes):
            raise ValueError("Unsupported mapping acceptance mode.")
        if len({task_id for task_id, _ in modes}) != len(modes):
            raise ValueError("Mapping acceptance modes must have unique task IDs.")
        object.__setattr__(self, "mapping_acceptance_modes", tuple(sorted(modes)))

    def build_instance(self, request: Mapping[str, Any]) -> Any:
        return self.instance_factory(request, self.contract)

    def encoding_context(self, **kwargs: Any) -> str:
        value = str(self.encoding_context_factory(**kwargs)).strip()
        if not value:
            raise ValueError(f"ModelPlugin {self.plugin_id!r} returned an empty encoding context.")
        return value

    def mapping_acceptance_mode(self, task_id: str) -> str:
        return dict(self.mapping_acceptance_modes).get(str(task_id), "not_applicable")

    def scientific_identity(self, **kwargs: Any) -> Mapping[str, Any]:
        payload = dict(self.scientific_identity_factory(**kwargs))
        required = {
            "mapping_policy_id",
            "state_preparation_policy_id",
            "ansatz_policy_id",
            "measurement_policy_id",
            "reference_policy_id",
            "controller_id",
        }
        missing = sorted(key for key in required if not str(payload.get(key) or "").strip())
        if missing:
            raise ValueError(
                f"ModelPlugin {self.plugin_id!r} scientific identity is missing {missing}."
            )
        return payload

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "qcol-model-plugin/1.0",
            "plugin_id": self.plugin_id,
            "plugin_version": self.plugin_version,
            "contract_id": self.contract.model_id,
            "contract_version": self.contract.model_version,
            "supported_tasks": list(self.contract.supported_tasks),
            "execution_status": self.contract.execution_status,
            "capabilities": list(self.capabilities),
            "mapping_acceptance_modes": dict(self.mapping_acceptance_modes),
            "instance_factory_binding": _binding(self.instance_factory),
            "encoding_context_binding": _binding(self.encoding_context_factory),
            "scientific_identity_binding": _binding(self.scientific_identity_factory),
            "callable_payload_withheld": True,
        }


@dataclass(frozen=True)
class TaskPlugin:
    """One registration surface for a task extension.

    The TaskContract remains the OWNER of task semantics.  This descriptor
    carries only executable selection behaviour that previously appeared as
    task-ID branching in the shared resolver.
    """

    plugin_id: str
    plugin_version: str
    contract: Any = field(repr=False, compare=False)
    instance_factory: TaskInstanceFactory = field(repr=False, compare=False)
    controller_structure: str = "single_pass"
    controller_stage: str = "bind"
    controller_message: str = "Starting the resolved single-pass task controller."
    observable_match_mode: str = "requested_all"
    observable_any_of: tuple[str, ...] = field(default_factory=tuple)
    observable_aliases: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if str(self.contract.task_id) != str(self.plugin_id):
            raise ValueError("TaskPlugin plugin_id must equal TaskContract.task_id.")
        if not callable(self.instance_factory):
            raise TypeError("TaskPlugin instance_factory must be callable.")
        if self.observable_match_mode not in {
            "requested_all",
            "required_all",
            "any_of",
            "none",
        }:
            raise ValueError("Unsupported observable_match_mode.")

    def build_instance(self, request: Mapping[str, Any]) -> Any:
        return self.instance_factory(request, self.contract)

    def observables_compatible(
        self,
        *,
        requested: set[str],
        supported: set[str],
    ) -> bool:
        aliases = dict(self.observable_aliases)
        expanded = requested | {aliases.get(value, value) for value in requested}
        if self.observable_match_mode == "none":
            return True
        if self.observable_match_mode == "any_of":
            return bool(set(self.observable_any_of) & supported)
        if self.observable_match_mode == "required_all":
            return set(self.contract.required_model_observables).issubset(supported)
        return bool(expanded & supported) and all(
            value in supported or aliases.get(value) in supported
            for value in requested
        )

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "qcol-task-plugin/1.0",
            "plugin_id": self.plugin_id,
            "plugin_version": self.plugin_version,
            "contract_id": self.contract.task_id,
            "contract_version": self.contract.task_version,
            "support_status": self.contract.support_status,
            "execution_status": self.contract.execution_status,
            "controller_structure": self.controller_structure,
            "controller_stage": self.controller_stage,
            "observable_match_mode": self.observable_match_mode,
            "instance_factory_binding": _binding(self.instance_factory),
            "callable_payload_withheld": True,
        }


__all__ = [
    "ModelPlugin",
    "TaskPlugin",
    "ModelInstanceFactory",
    "TaskInstanceFactory",
    "EncodingContextFactory",
    "ScientificIdentityFactory",
]

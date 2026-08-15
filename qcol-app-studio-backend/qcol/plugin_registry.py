"""The single in-repository registration authority for Step 2.

The registry is partitioned by the three public extension seams but remains one
internal composition-time service.  Historical model/task/execution registry
modules are read-only compatibility projections over this authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Any

from .execution.contracts import ExecutionAdapter, ExecutionAdapterDescriptor
from .plugin_api import ModelPlugin, TaskPlugin

PUBLIC_EXTENSION_SEAMS = ("ModelPlugin", "TaskPlugin", "ExecutionAdapter")


class PluginRegistryError(KeyError):
    pass


@dataclass(frozen=True)
class _ExecutionBinding:
    descriptor: ExecutionAdapterDescriptor
    import_path: str
    implementation_status: str = "implemented"

    @property
    def plugin_id(self) -> str:
        return self.descriptor.adapter_id

    def load(self) -> ExecutionAdapter:
        if self.implementation_status != "implemented":
            raise PluginRegistryError(
                f"Execution adapter {self.plugin_id!r} is recognized but not executable."
            )
        module_name, attribute = self.import_path.split(":", 1)
        value = getattr(import_module(module_name), attribute)
        if not isinstance(value, ExecutionAdapter):
            raise PluginRegistryError(
                f"Execution adapter {self.plugin_id!r} does not satisfy ExecutionAdapter."
            )
        return value

    def to_public_dict(self) -> dict[str, Any]:
        return {
            **self.descriptor.to_dict(),
            "binding_id": f"binding.{self.plugin_id}",
            "import_path": self.import_path,
            "implementation_status": self.implementation_status,
            "callable_payload_withheld": True,
        }


class PluginRegistry:
    def __init__(self) -> None:
        self._models: dict[str, ModelPlugin] = {}
        self._tasks: dict[str, TaskPlugin] = {}
        self._task_aliases: dict[str, str] = {}
        self._executions: dict[str, _ExecutionBinding] = {}

    def register_model(self, plugin: ModelPlugin, *, replace: bool = False) -> None:
        if plugin.plugin_id in self._models and not replace:
            raise PluginRegistryError(f"Model plugin already registered: {plugin.plugin_id!r}")
        self._models[plugin.plugin_id] = plugin

    def register_task(self, plugin: TaskPlugin, *, replace: bool = False) -> None:
        if plugin.plugin_id in self._tasks and not replace:
            raise PluginRegistryError(f"Task plugin already registered: {plugin.plugin_id!r}")
        self._tasks[plugin.plugin_id] = plugin
        for alias in plugin.contract.all_ids:
            existing = self._task_aliases.get(alias)
            if existing is not None and existing != plugin.plugin_id and not replace:
                raise PluginRegistryError(
                    f"Task alias {alias!r} already belongs to {existing!r}."
                )
            self._task_aliases[alias] = plugin.plugin_id

    def register_execution(
        self,
        descriptor: ExecutionAdapterDescriptor,
        *,
        import_path: str,
        implementation_status: str = "implemented",
        replace: bool = False,
    ) -> None:
        binding = _ExecutionBinding(
            descriptor=descriptor,
            import_path=str(import_path),
            implementation_status=str(implementation_status),
        )
        if binding.plugin_id in self._executions and not replace:
            raise PluginRegistryError(
                f"Execution adapter already registered: {binding.plugin_id!r}"
            )
        self._executions[binding.plugin_id] = binding

    def model(self, plugin_id: str) -> ModelPlugin:
        _ensure_builtins(self)
        try:
            return self._models[str(plugin_id)]
        except KeyError as exc:
            raise PluginRegistryError(
                f"Unknown model plugin {plugin_id!r}. Available: {sorted(self._models)}"
            ) from exc

    def canonical_task_id(self, task_id: str | None) -> str:
        _ensure_builtins(self)
        value = (
            "ground_state_energy"
            if task_id is None or not str(task_id).strip()
            else str(task_id)
        )
        try:
            return self._task_aliases[value]
        except KeyError as exc:
            raise PluginRegistryError(
                f"Unknown task plugin {value!r}. Available: {sorted(self._tasks)}"
            ) from exc

    def task(self, task_id: str) -> TaskPlugin:
        _ensure_builtins(self)
        return self._tasks[self.canonical_task_id(task_id)]

    def execution_binding(self, adapter_id: str) -> _ExecutionBinding:
        _ensure_builtins(self)
        try:
            return self._executions[str(adapter_id)]
        except KeyError as exc:
            raise PluginRegistryError(
                f"Execution adapter {adapter_id!r} is not registered as executable."
            ) from exc

    def execution(self, adapter_id: str) -> ExecutionAdapter:
        return self.execution_binding(adapter_id).load()

    def models(self) -> tuple[ModelPlugin, ...]:
        _ensure_builtins(self)
        return tuple(self._models[key] for key in sorted(self._models))

    def tasks(self) -> tuple[TaskPlugin, ...]:
        _ensure_builtins(self)
        return tuple(self._tasks[key] for key in sorted(self._tasks))

    def executions(self) -> tuple[_ExecutionBinding, ...]:
        _ensure_builtins(self)
        return tuple(self._executions[key] for key in sorted(self._executions))

    def public_catalog(self) -> dict[str, Any]:
        return {
            "schema_version": "qcol-internal-plugin-registry/1.0",
            "public_extension_seams": list(PUBLIC_EXTENSION_SEAMS),
            "one_internal_registry": True,
            "model_plugins": [row.to_public_dict() for row in self.models()],
            "task_plugins": [row.to_public_dict() for row in self.tasks()],
            "execution_adapters": [row.to_public_dict() for row in self.executions()],
            "task_aliases": dict(sorted(self._task_aliases.items())),
            "python_package_entry_points_enabled": False,
            "silent_fallback_allowed": False,
            "callable_payload_withheld": True,
        }


REGISTRY = PluginRegistry()
_BUILTINS_REGISTERED = False


def _ensure_builtins(registry: PluginRegistry = REGISTRY) -> None:
    global _BUILTINS_REGISTERED
    if _BUILTINS_REGISTERED:
        return
    # Mark first to make recursive compatibility imports idempotent while the
    # built-in module is loading; failures reset the flag.
    _BUILTINS_REGISTERED = True
    try:
        from .builtin_plugins import register_builtin_plugins

        register_builtin_plugins(registry)
    except Exception:
        _BUILTINS_REGISTERED = False
        raise


def get_model_plugin(plugin_id: str) -> ModelPlugin:
    return REGISTRY.model(plugin_id)


def get_task_plugin(task_id: str) -> TaskPlugin:
    return REGISTRY.task(task_id)


def canonical_task_plugin_id(task_id: str | None) -> str:
    return REGISTRY.canonical_task_id(task_id)


def get_execution_plugin(adapter_id: str = "execution.local_cirq.v1") -> ExecutionAdapter:
    return REGISTRY.execution(adapter_id)


def list_model_plugins() -> tuple[ModelPlugin, ...]:
    return REGISTRY.models()


def list_task_plugins() -> tuple[TaskPlugin, ...]:
    return REGISTRY.tasks()


def list_execution_bindings() -> tuple[_ExecutionBinding, ...]:
    return REGISTRY.executions()


def public_plugin_registry() -> dict[str, Any]:
    return REGISTRY.public_catalog()


__all__ = [
    "PUBLIC_EXTENSION_SEAMS",
    "PluginRegistry",
    "PluginRegistryError",
    "REGISTRY",
    "get_model_plugin",
    "get_task_plugin",
    "canonical_task_plugin_id",
    "get_execution_plugin",
    "list_model_plugins",
    "list_task_plugins",
    "list_execution_bindings",
    "public_plugin_registry",
]

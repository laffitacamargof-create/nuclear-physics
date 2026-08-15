"""Lazy callable registries for task/controller policies."""
from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from types import MappingProxyType
from typing import Any, Callable, Dict, Mapping, Optional, Tuple

TASK_POLICY_KINDS = (
    "controller",
    "circuit",
    "measurement",
    "reconstruction",
    "termination",
    "reference",
    "verification",
    "interpretation",
)


class TaskPolicyRegistryError(RuntimeError):
    pass


@dataclass(frozen=True)
class TaskPolicyBinding:
    policy_id: str
    kind: str
    import_path: str
    description: str
    implementation_status: str = "implemented"
    version: str = "1"
    provenance: Mapping[str, Any] = None

    def __post_init__(self) -> None:
        if self.kind not in TASK_POLICY_KINDS:
            raise TaskPolicyRegistryError(f"Unknown task policy kind {self.kind!r}.")
        if not self.policy_id.strip() or ":" not in self.import_path:
            raise TaskPolicyRegistryError("Task policy requires a non-empty ID and module:attribute import path.")
        if self.implementation_status not in {"implemented", "not_implemented"}:
            raise TaskPolicyRegistryError("Unsupported implementation_status.")
        object.__setattr__(self, "provenance", MappingProxyType(dict(self.provenance or {})))

    @property
    def executable(self) -> bool:
        return self.implementation_status == "implemented"

    def load(self) -> Callable[..., Any]:
        if not self.executable:
            raise TaskPolicyRegistryError(f"Task policy {self.policy_id!r} is registered but not implemented.")
        module_name, attribute = self.import_path.split(":", 1)
        value = getattr(import_module(module_name), attribute)
        if not callable(value):
            raise TaskPolicyRegistryError(f"Resolved task policy {self.policy_id!r} is not callable.")
        return value

    def to_dict(self) -> Dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "kind": self.kind,
            "import_path": self.import_path,
            "description": self.description,
            "implementation_status": self.implementation_status,
            "executable": self.executable,
            "version": self.version,
            "provenance": dict(self.provenance),
        }


class TaskCallableRegistry:
    def __init__(self, kind: str) -> None:
        if kind not in TASK_POLICY_KINDS:
            raise TaskPolicyRegistryError(f"Unknown task policy kind {kind!r}.")
        self.kind = kind
        self._bindings: Dict[str, TaskPolicyBinding] = {}

    def declare(
        self,
        policy_id: str,
        import_path: str,
        description: str,
        *,
        implementation_status: str = "implemented",
        version: str = "1",
        provenance: Optional[Mapping[str, Any]] = None,
        replace: bool = False,
    ) -> None:
        if policy_id in self._bindings and not replace:
            raise TaskPolicyRegistryError(f"Task policy already registered: {policy_id!r}")
        self._bindings[policy_id] = TaskPolicyBinding(
            policy_id=policy_id,
            kind=self.kind,
            import_path=import_path,
            description=description,
            implementation_status=implementation_status,
            version=version,
            provenance=dict(provenance or {}),
        )

    def has(self, policy_id: str, *, executable: bool = False) -> bool:
        binding = self._bindings.get(str(policy_id))
        if binding is None:
            return False
        return binding.executable if executable else True

    def binding(self, policy_id: str) -> TaskPolicyBinding:
        try:
            return self._bindings[str(policy_id)]
        except KeyError as exc:
            raise TaskPolicyRegistryError(
                f"Unknown {self.kind} task policy {policy_id!r}. Available: {sorted(self._bindings)}"
            ) from exc

    def resolve(self, policy_id: str) -> Callable[..., Any]:
        return self.binding(policy_id).load()

    def list(self) -> Tuple[TaskPolicyBinding, ...]:
        return tuple(self._bindings[key] for key in sorted(self._bindings))

    def to_dict(self) -> Dict[str, Any]:
        return {"kind": self.kind, "policies": [item.to_dict() for item in self.list()]}


CONTROLLER_REGISTRY = TaskCallableRegistry("controller")
CIRCUIT_TASK_REGISTRY = TaskCallableRegistry("circuit")
TASK_MEASUREMENT_REGISTRY = TaskCallableRegistry("measurement")
RECONSTRUCTION_TASK_REGISTRY = TaskCallableRegistry("reconstruction")
TERMINATION_REGISTRY = TaskCallableRegistry("termination")
TASK_REFERENCE_REGISTRY = TaskCallableRegistry("reference")
VERIFICATION_TASK_REGISTRY = TaskCallableRegistry("verification")
TASK_INTERPRETATION_REGISTRY = TaskCallableRegistry("interpretation")

TASK_REGISTRIES: Mapping[str, TaskCallableRegistry] = MappingProxyType({
    "controller": CONTROLLER_REGISTRY,
    "circuit": CIRCUIT_TASK_REGISTRY,
    "measurement": TASK_MEASUREMENT_REGISTRY,
    "reconstruction": RECONSTRUCTION_TASK_REGISTRY,
    "termination": TERMINATION_REGISTRY,
    "reference": TASK_REFERENCE_REGISTRY,
    "verification": VERIFICATION_TASK_REGISTRY,
    "interpretation": TASK_INTERPRETATION_REGISTRY,
})


def public_task_policy_catalog() -> Dict[str, Any]:
    from .builtin_task_policies import register_builtin_task_policies
    register_builtin_task_policies()
    return {
        "registry_version": "qcol-task-policy-registry/1.0",
        "registries": {kind: registry.to_dict() for kind, registry in TASK_REGISTRIES.items()},
    }

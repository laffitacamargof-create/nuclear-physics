"""Lazy callable policy registries for the QCOL model-plugin architecture.

Model contracts contain only stable policy IDs.  These registries bind each ID
at runtime to a certified callable.  Import paths are resolved lazily so model
catalogs and APIs remain inspectable without importing Cirq/OpenFermion.
"""
from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from types import MappingProxyType
from typing import Any, Callable, Dict, Iterable, Mapping, Optional, Tuple


POLICY_KINDS = (
    "hamiltonian",
    "sector",
    "mapping",
    "state_preparation",
    "ansatz",
    "measurement",
    "reference",
    "resource",
    "runtime",
    "interpretation",
)


class PolicyRegistryError(RuntimeError):
    """Raised when a policy ID cannot be resolved honestly."""


@dataclass(frozen=True)
class PolicyBinding:
    policy_id: str
    kind: str
    import_path: str
    description: str
    implementation_status: str = "implemented"  # implemented | not_implemented
    version: str = "1"
    provenance: Mapping[str, Any] = None

    def __post_init__(self) -> None:
        if not self.policy_id.strip():
            raise PolicyRegistryError("policy_id must be non-empty.")
        if self.kind not in POLICY_KINDS:
            raise PolicyRegistryError(f"Unknown policy kind {self.kind!r}.")
        if ":" not in self.import_path:
            raise PolicyRegistryError(
                f"Policy {self.policy_id!r} import_path must be module:function."
            )
        if self.implementation_status not in {"implemented", "not_implemented"}:
            raise PolicyRegistryError(
                f"Unsupported implementation status {self.implementation_status!r}."
            )
        object.__setattr__(self, "provenance", MappingProxyType(dict(self.provenance or {})))

    @property
    def executable(self) -> bool:
        return self.implementation_status == "implemented"

    def load(self) -> Callable[..., Any]:
        if not self.executable:
            raise PolicyRegistryError(
                f"Policy {self.policy_id!r} is registered but not implemented."
            )
        module_name, attribute = self.import_path.split(":", 1)
        module = import_module(module_name)
        value = getattr(module, attribute)
        if not callable(value):
            raise PolicyRegistryError(
                f"Resolved policy {self.policy_id!r} is not callable."
            )
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


class CallablePolicyRegistry:
    def __init__(self, kind: str) -> None:
        if kind not in POLICY_KINDS:
            raise PolicyRegistryError(f"Unknown policy kind {kind!r}.")
        self.kind = kind
        self._bindings: Dict[str, PolicyBinding] = {}

    def register(self, binding: PolicyBinding, *, replace: bool = False) -> None:
        if binding.kind != self.kind:
            raise PolicyRegistryError(
                f"Cannot register {binding.kind!r} policy in {self.kind!r} registry."
            )
        if binding.policy_id in self._bindings and not replace:
            raise PolicyRegistryError(
                f"Policy {binding.policy_id!r} is already registered."
            )
        self._bindings[binding.policy_id] = binding

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
        self.register(
            PolicyBinding(
                policy_id=policy_id,
                kind=self.kind,
                import_path=import_path,
                description=description,
                implementation_status=implementation_status,
                version=version,
                provenance=dict(provenance or {}),
            ),
            replace=replace,
        )

    def binding(self, policy_id: str) -> PolicyBinding:
        try:
            return self._bindings[str(policy_id)]
        except KeyError as exc:
            raise PolicyRegistryError(
                f"Unknown {self.kind} policy {policy_id!r}. "
                f"Available: {sorted(self._bindings)}"
            ) from exc

    def resolve(self, policy_id: str) -> Callable[..., Any]:
        return self.binding(policy_id).load()

    def has(self, policy_id: str, *, executable: bool = False) -> bool:
        binding = self._bindings.get(str(policy_id))
        if binding is None:
            return False
        return binding.executable if executable else True

    def list(self) -> Tuple[PolicyBinding, ...]:
        return tuple(self._bindings[key] for key in sorted(self._bindings))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "policies": [binding.to_dict() for binding in self.list()],
        }


HAMILTONIAN_REGISTRY = CallablePolicyRegistry("hamiltonian")
SECTOR_REGISTRY = CallablePolicyRegistry("sector")
MAPPING_REGISTRY = CallablePolicyRegistry("mapping")
STATE_PREPARATION_REGISTRY = CallablePolicyRegistry("state_preparation")
ANSATZ_REGISTRY = CallablePolicyRegistry("ansatz")
MEASUREMENT_REGISTRY = CallablePolicyRegistry("measurement")
REFERENCE_REGISTRY = CallablePolicyRegistry("reference")
RESOURCE_REGISTRY = CallablePolicyRegistry("resource")
RUNTIME_REGISTRY = CallablePolicyRegistry("runtime")
INTERPRETATION_REGISTRY = CallablePolicyRegistry("interpretation")

REGISTRIES: Mapping[str, CallablePolicyRegistry] = MappingProxyType({
    "hamiltonian": HAMILTONIAN_REGISTRY,
    "sector": SECTOR_REGISTRY,
    "mapping": MAPPING_REGISTRY,
    "state_preparation": STATE_PREPARATION_REGISTRY,
    "ansatz": ANSATZ_REGISTRY,
    "measurement": MEASUREMENT_REGISTRY,
    "reference": REFERENCE_REGISTRY,
    "resource": RESOURCE_REGISTRY,
    "runtime": RUNTIME_REGISTRY,
    "interpretation": INTERPRETATION_REGISTRY,
})


def resolve_policy(kind: str, policy_id: str) -> Callable[..., Any]:
    try:
        registry = REGISTRIES[str(kind)]
    except KeyError as exc:
        raise PolicyRegistryError(f"Unknown policy kind {kind!r}.") from exc
    return registry.resolve(policy_id)


def public_policy_catalog() -> Dict[str, Any]:
    from .builtin_policies import register_builtin_policies
    register_builtin_policies()
    return {
        "registry_version": "qcol-callable-policy-registry/1.0",
        "registries": {kind: registry.to_dict() for kind, registry in REGISTRIES.items()},
    }


def validate_policy_registries(*, import_callables: bool = False) -> Dict[str, Any]:
    from .builtin_policies import register_builtin_policies
    register_builtin_policies()
    duplicate_ids: Dict[str, list[str]] = {}
    id_to_kinds: Dict[str, list[str]] = {}
    load_errors: Dict[str, str] = {}
    for kind, registry in REGISTRIES.items():
        for binding in registry.list():
            id_to_kinds.setdefault(binding.policy_id, []).append(kind)
            if import_callables and binding.executable:
                try:
                    binding.load()
                except Exception as exc:  # pragma: no cover - environment-specific
                    load_errors[binding.policy_id] = f"{type(exc).__name__}: {exc}"
    for policy_id, kinds in id_to_kinds.items():
        if len(kinds) > 1:
            duplicate_ids[policy_id] = kinds
    return {
        "registry_kinds_complete": set(REGISTRIES) == set(POLICY_KINDS),
        "all_registries_nonempty": all(registry.list() for registry in REGISTRIES.values()),
        "policy_ids_unique_across_kinds": not duplicate_ids,
        "duplicates": duplicate_ids,
        "load_errors": load_errors,
        "callable_imports_pass": not load_errors,
    }

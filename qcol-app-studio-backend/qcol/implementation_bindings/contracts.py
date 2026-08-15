"""Declarative metadata and public reports for WP3 implementation bindings.

The callable itself is never stored in a public contract or evidence snapshot.
The registry owns executable objects internally and exposes only JSON-safe
metadata and structured resolution reports.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from qcol.mapping_policies import CheckStatus, PolicyStatus
from qcol.realization_policies.base import (
    DeclarativeContract,
    PolicyContractError,
    freeze_json,
    require_text,
    require_token,
)

from .enums import BindingFailureCode, BindingKind


IMPLEMENTATION_BINDING_SCHEMA_VERSION = "qcol-implementation-binding-contract/1.0"
BINDING_REQUIREMENT_SCHEMA_VERSION = "qcol-binding-requirement/1.0"
BINDING_RESOLUTION_SCHEMA_VERSION = "qcol-binding-resolution-report/1.0"
RESOLVED_BINDING_PLAN_SCHEMA_VERSION = "qcol-resolved-binding-plan/1.0"

_EXECUTABLE_STATUSES = frozenset({
    PolicyStatus.EXPERIMENTAL,
    PolicyStatus.EXECUTABLE,
    PolicyStatus.EXECUTION_READY,
    PolicyStatus.VERIFIED,
    PolicyStatus.ACCEPTANCE_VERIFIED,
})


@dataclass(frozen=True)
class ImplementationBindingContract(DeclarativeContract):
    """JSON-safe metadata describing how one binding may be loaded.

    ``import_path`` is metadata, not a loaded Python object.  It may be ``None``
    for a recognized-but-not-executable policy.  The exact callable is loaded
    lazily by :class:`ImplementationBindingRegistry`.
    """

    binding_id: str
    binding_version: str
    display_name: str
    kind: BindingKind
    provider: str
    implementation_version: str
    convention_id: str
    source_revision: str
    import_path: str | None
    expected_parameters: tuple[str, ...] = field(default_factory=tuple)
    support_status: PolicyStatus = PolicyStatus.EXECUTION_READY
    description: str = ""
    limitations: tuple[str, ...] = field(default_factory=tuple)
    provenance: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = IMPLEMENTATION_BINDING_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in (
            "binding_id",
            "binding_version",
            "provider",
            "implementation_version",
            "convention_id",
            "source_revision",
        ):
            require_token(name, getattr(self, name))
        require_text("display_name", self.display_name)
        if self.description:
            require_text("description", self.description)
        if not isinstance(self.kind, BindingKind):
            raise PolicyContractError("kind must be BindingKind.")
        if not isinstance(self.support_status, PolicyStatus):
            raise PolicyContractError("support_status must be PolicyStatus.")

        if self.import_path is not None:
            path = require_text("import_path", self.import_path)
            if ":" not in path:
                raise PolicyContractError(
                    "import_path must use the form 'module.path:attribute'."
                )
            module_name, attribute_name = path.split(":", 1)
            if not module_name.strip() or not attribute_name.strip():
                raise PolicyContractError(
                    "import_path must contain a non-empty module and attribute."
                )
            object.__setattr__(self, "import_path", path)

        executable = self.support_status in _EXECUTABLE_STATUSES
        if executable and self.import_path is None:
            raise PolicyContractError(
                "An executable binding must declare an import_path."
            )
        if not executable and self.import_path is not None:
            # A recognized-but-unavailable implementation may retain a future
            # import location, but it must never be loaded while unavailable.
            pass

        params = tuple(require_token("expected_parameters", str(item)) for item in self.expected_parameters)
        if len(set(params)) != len(params):
            raise PolicyContractError("expected_parameters must not contain duplicates.")
        object.__setattr__(self, "expected_parameters", params)
        object.__setattr__(
            self,
            "limitations",
            tuple(require_text("limitations", str(item)) for item in self.limitations),
        )
        object.__setattr__(
            self,
            "provenance",
            freeze_json(self.provenance, path="ImplementationBindingContract.provenance"),
        )

    @property
    def declares_executable(self) -> bool:
        return self.support_status in _EXECUTABLE_STATUSES

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload["declares_executable"] = self.declares_executable
        payload["callable_payload_withheld"] = True
        return payload


@dataclass(frozen=True)
class BindingRequirement(DeclarativeContract):
    contract_id: str
    contract_type: str
    role: str
    binding_id: str
    binding_kind: BindingKind
    required: bool = True
    expected_binding_version: str | None = None
    expected_convention_id: str | None = None
    schema_version: str = BINDING_REQUIREMENT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in ("contract_id", "contract_type", "role", "binding_id"):
            require_token(name, getattr(self, name))
        if not isinstance(self.binding_kind, BindingKind):
            raise PolicyContractError("binding_kind must be BindingKind.")
        for name in ("expected_binding_version", "expected_convention_id"):
            value = getattr(self, name)
            if value is not None:
                require_token(name, value)


@dataclass(frozen=True)
class BindingResolutionReport(DeclarativeContract):
    requirement: BindingRequirement
    check_status: CheckStatus
    policy_status: PolicyStatus
    code: BindingFailureCode
    message: str
    binding_metadata: Mapping[str, Any] = field(default_factory=dict)
    details: Mapping[str, Any] = field(default_factory=dict)
    suggested_action: str | None = None
    schema_version: str = BINDING_RESOLUTION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.requirement, BindingRequirement):
            raise PolicyContractError("requirement must be BindingRequirement.")
        if not isinstance(self.check_status, CheckStatus):
            raise PolicyContractError("check_status must be CheckStatus.")
        if not isinstance(self.policy_status, PolicyStatus):
            raise PolicyContractError("policy_status must be PolicyStatus.")
        if not isinstance(self.code, BindingFailureCode):
            raise PolicyContractError("code must be BindingFailureCode.")
        require_text("message", self.message)
        if self.suggested_action is not None:
            require_text("suggested_action", self.suggested_action)
        object.__setattr__(
            self,
            "binding_metadata",
            freeze_json(self.binding_metadata, path="BindingResolutionReport.binding_metadata"),
        )
        object.__setattr__(
            self,
            "details",
            freeze_json(self.details, path="BindingResolutionReport.details"),
        )

    @property
    def resolved(self) -> bool:
        return self.check_status is CheckStatus.PASS and self.code is BindingFailureCode.RESOLVED

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload["resolved"] = self.resolved
        payload["callable_payload_withheld"] = True
        return payload


@dataclass(frozen=True)
class ResolvedImplementation:
    """Internal runtime object combining a public report and a callable.

    This class intentionally does not inherit ``DeclarativeContract``.  Its
    callable is runtime-only and must never be serialized.  Use
    :meth:`to_public_dict` for API/evidence output.
    """

    report: BindingResolutionReport
    callable_object: Callable[..., Any] | None = field(default=None, repr=False, compare=False)

    @property
    def executable(self) -> bool:
        return self.report.resolved and callable(self.callable_object)

    def to_public_dict(self) -> dict[str, Any]:
        payload = self.report.to_dict()
        payload["runtime_callable_loaded"] = self.executable
        payload["callable_payload_withheld"] = True
        return payload


@dataclass(frozen=True)
class ResolvedBindingPlan:
    plan_id: str
    contract_ids: tuple[str, ...]
    implementations: tuple[ResolvedImplementation, ...]
    scientific_behavior_change: bool = False
    live_policy_migration_performed: bool = False
    schema_version: str = RESOLVED_BINDING_PLAN_SCHEMA_VERSION

    @property
    def required_resolutions(self) -> tuple[ResolvedImplementation, ...]:
        return tuple(
            item for item in self.implementations if item.report.requirement.required
        )

    @property
    def all_required_resolved(self) -> bool:
        return all(item.executable for item in self.required_resolutions)

    @property
    def overall_status(self) -> PolicyStatus:
        return (
            PolicyStatus.EXECUTION_READY
            if self.all_required_resolved
            else PolicyStatus.RECOGNIZED_NOT_EXECUTABLE
        )

    def callable_by_role(self) -> dict[str, Callable[..., Any]]:
        return {
            item.report.requirement.role: item.callable_object
            for item in self.implementations
            if item.executable and item.callable_object is not None
        }

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "plan_id": self.plan_id,
            "contract_ids": list(self.contract_ids),
            "overall_status": self.overall_status.value,
            "all_required_resolved": self.all_required_resolved,
            "scientific_behavior_change": self.scientific_behavior_change,
            "live_policy_migration_performed": self.live_policy_migration_performed,
            "implementations": [item.to_public_dict() for item in self.implementations],
            "callable_payload_withheld": True,
        }


__all__ = [
    "IMPLEMENTATION_BINDING_SCHEMA_VERSION",
    "BINDING_REQUIREMENT_SCHEMA_VERSION",
    "BINDING_RESOLUTION_SCHEMA_VERSION",
    "RESOLVED_BINDING_PLAN_SCHEMA_VERSION",
    "ImplementationBindingContract",
    "BindingRequirement",
    "BindingResolutionReport",
    "ResolvedImplementation",
    "ResolvedBindingPlan",
]

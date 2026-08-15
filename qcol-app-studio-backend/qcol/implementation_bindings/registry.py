"""Versioned implementation-binding registry for QCOL WP3.

Public policy contracts store only binding IDs.  This registry owns the lazy
connection from those IDs to Python callables.  Every failed lookup/import is
returned as a structured ``recognized_not_executable`` report; no ImportError
or silent fallback is allowed to cross the registry boundary.
"""
from __future__ import annotations

from importlib import import_module
import inspect
from types import MappingProxyType
from typing import Any, Callable, Mapping

from qcol.mapping_policies import CheckStatus, PolicyStatus

from .contracts import (
    BindingRequirement,
    BindingResolutionReport,
    ImplementationBindingContract,
    ResolvedImplementation,
)
from .enums import BindingFailureCode, BindingKind


class BindingRegistryDefinitionError(ValueError):
    """Raised only for programmer errors while constructing the registry."""


class ImplementationBindingRegistry:
    def __init__(self, *, registry_id: str, registry_version: str) -> None:
        if not str(registry_id).strip() or not str(registry_version).strip():
            raise BindingRegistryDefinitionError(
                "registry_id and registry_version must be non-empty."
            )
        self.registry_id = str(registry_id)
        self.registry_version = str(registry_version)
        self._contracts: dict[str, ImplementationBindingContract] = {}
        self._attached_callables: dict[str, Callable[..., Any]] = {}

    def register(
        self,
        contract: ImplementationBindingContract,
        *,
        callable_object: Callable[..., Any] | None = None,
        replace: bool = False,
    ) -> None:
        if not isinstance(contract, ImplementationBindingContract):
            raise BindingRegistryDefinitionError(
                "contract must be ImplementationBindingContract."
            )
        if contract.binding_id in self._contracts and not replace:
            raise BindingRegistryDefinitionError(
                f"Binding {contract.binding_id!r} is already registered."
            )
        if callable_object is not None and not callable(callable_object):
            raise BindingRegistryDefinitionError(
                "callable_object must be callable when supplied."
            )
        self._contracts[contract.binding_id] = contract
        if callable_object is not None:
            self._attached_callables[contract.binding_id] = callable_object
        elif replace:
            self._attached_callables.pop(contract.binding_id, None)

    def unregister(self, binding_id: str) -> None:
        self._contracts.pop(str(binding_id), None)
        self._attached_callables.pop(str(binding_id), None)

    def binding_contract(self, binding_id: str) -> ImplementationBindingContract | None:
        return self._contracts.get(str(binding_id))

    def has(self, binding_id: str) -> bool:
        return str(binding_id) in self._contracts

    def list_contracts(self) -> tuple[ImplementationBindingContract, ...]:
        return tuple(self._contracts[key] for key in sorted(self._contracts))

    def _metadata(self, contract: ImplementationBindingContract) -> dict[str, Any]:
        return {
            "binding_id": contract.binding_id,
            "binding_version": contract.binding_version,
            "kind": contract.kind.value,
            "provider": contract.provider,
            "implementation_version": contract.implementation_version,
            "convention_id": contract.convention_id,
            "source_revision": contract.source_revision,
            "import_path": contract.import_path,
            "support_status": contract.support_status.value,
            "callable_payload_withheld": True,
        }

    def _report(
        self,
        requirement: BindingRequirement,
        *,
        check_status: CheckStatus,
        policy_status: PolicyStatus,
        code: BindingFailureCode,
        message: str,
        contract: ImplementationBindingContract | None = None,
        details: Mapping[str, Any] | None = None,
        suggested_action: str | None = None,
    ) -> BindingResolutionReport:
        return BindingResolutionReport(
            requirement=requirement,
            check_status=check_status,
            policy_status=policy_status,
            code=code,
            message=message,
            binding_metadata=(
                {} if contract is None else self._metadata(contract)
            ),
            details=dict(details or {}),
            suggested_action=suggested_action,
        )

    @staticmethod
    def _validate_signature(
        callable_object: Callable[..., Any],
        contract: ImplementationBindingContract,
    ) -> tuple[bool, dict[str, Any]]:
        try:
            signature = inspect.signature(callable_object)
        except (TypeError, ValueError) as exc:
            return False, {
                "reason": "signature_unavailable",
                "exception_type": type(exc).__name__,
                "exception_message": str(exc),
            }

        parameters = signature.parameters
        accepts_varkw = any(
            item.kind is inspect.Parameter.VAR_KEYWORD
            for item in parameters.values()
        )
        names = {
            name
            for name, item in parameters.items()
            if item.kind
            not in {
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            }
        }
        missing_expected = [
            name
            for name in contract.expected_parameters
            if name not in names and not accepts_varkw
        ]
        required_callable_parameters = [
            name
            for name, item in parameters.items()
            if item.kind
            in {
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.KEYWORD_ONLY,
            }
            and item.default is inspect.Parameter.empty
            and name not in {"self", "cls"}
        ]
        undeclared_required = [
            name
            for name in required_callable_parameters
            if name not in contract.expected_parameters
        ]
        return (
            not missing_expected and not undeclared_required,
            {
                "signature": str(signature),
                "expected_parameters": list(contract.expected_parameters),
                "missing_expected_parameters": missing_expected,
                "undeclared_required_parameters": undeclared_required,
                "accepts_var_keyword": accepts_varkw,
            },
        )

    def resolve(self, requirement: BindingRequirement) -> ResolvedImplementation:
        """Resolve exactly one declared binding requirement.

        The function never searches for alternatives.  Missing, unavailable,
        incompatible, or broken bindings return a structured report with
        ``PolicyStatus.RECOGNIZED_NOT_EXECUTABLE``.
        """

        contract = self.binding_contract(requirement.binding_id)
        if contract is None:
            report = self._report(
                requirement,
                check_status=CheckStatus.BLOCKED,
                policy_status=PolicyStatus.RECOGNIZED_NOT_EXECUTABLE,
                code=BindingFailureCode.NOT_REGISTERED,
                message=(
                    f"Contract {requirement.contract_id!r} is recognized, but "
                    f"binding {requirement.binding_id!r} is not registered."
                ),
                details={
                    "registry_id": self.registry_id,
                    "registry_version": self.registry_version,
                    "silent_fallback_performed": False,
                },
                suggested_action=(
                    "Install or register the exact versioned binding; do not "
                    "substitute another implementation silently."
                ),
            )
            return ResolvedImplementation(report=report)

        if contract.kind is not requirement.binding_kind:
            report = self._report(
                requirement,
                check_status=CheckStatus.FAIL,
                policy_status=PolicyStatus.RECOGNIZED_NOT_EXECUTABLE,
                code=BindingFailureCode.KIND_MISMATCH,
                message=(
                    f"Binding {contract.binding_id!r} is registered as "
                    f"{contract.kind.value!r}, not {requirement.binding_kind.value!r}."
                ),
                contract=contract,
                details={"silent_fallback_performed": False},
                suggested_action="Register a binding with the required role and exact ID.",
            )
            return ResolvedImplementation(report=report)

        if (
            requirement.expected_binding_version is not None
            and contract.binding_version != requirement.expected_binding_version
        ):
            report = self._report(
                requirement,
                check_status=CheckStatus.FAIL,
                policy_status=PolicyStatus.RECOGNIZED_NOT_EXECUTABLE,
                code=BindingFailureCode.VERSION_MISMATCH,
                message=(
                    f"Binding version {contract.binding_version!r} does not match "
                    f"required version {requirement.expected_binding_version!r}."
                ),
                contract=contract,
                details={"silent_fallback_performed": False},
                suggested_action="Register the exact required binding version.",
            )
            return ResolvedImplementation(report=report)

        if (
            requirement.expected_convention_id is not None
            and contract.convention_id != requirement.expected_convention_id
        ):
            report = self._report(
                requirement,
                check_status=CheckStatus.FAIL,
                policy_status=PolicyStatus.RECOGNIZED_NOT_EXECUTABLE,
                code=BindingFailureCode.CONVENTION_MISMATCH,
                message=(
                    f"Binding convention {contract.convention_id!r} does not match "
                    f"required convention {requirement.expected_convention_id!r}."
                ),
                contract=contract,
                details={"silent_fallback_performed": False},
                suggested_action="Register the exact convention required by the contract.",
            )
            return ResolvedImplementation(report=report)

        if not contract.declares_executable:
            report = self._report(
                requirement,
                check_status=CheckStatus.BLOCKED,
                policy_status=PolicyStatus.RECOGNIZED_NOT_EXECUTABLE,
                code=BindingFailureCode.DECLARED_NOT_EXECUTABLE,
                message=(
                    f"Binding {contract.binding_id!r} is recognized but is not "
                    "declared executable in this release."
                ),
                contract=contract,
                details={"silent_fallback_performed": False},
                suggested_action="Provide the missing implementation and acceptance evidence.",
            )
            return ResolvedImplementation(report=report)

        callable_object = self._attached_callables.get(contract.binding_id)
        if callable_object is None:
            assert contract.import_path is not None  # enforced by contract
            module_name, attribute_name = contract.import_path.split(":", 1)
            try:
                module = import_module(module_name)
            except Exception as exc:  # environment/import boundary
                report = self._report(
                    requirement,
                    check_status=CheckStatus.BLOCKED,
                    policy_status=PolicyStatus.RECOGNIZED_NOT_EXECUTABLE,
                    code=BindingFailureCode.IMPORT_FAILED,
                    message=(
                        f"Binding {contract.binding_id!r} could not import its "
                        "declared provider implementation."
                    ),
                    contract=contract,
                    details={
                        "exception_type": type(exc).__name__,
                        "exception_message": str(exc),
                        "silent_fallback_performed": False,
                    },
                    suggested_action=(
                        "Install the declared provider/dependency version or "
                        "register the exact implementation binding."
                    ),
                )
                return ResolvedImplementation(report=report)
            try:
                callable_object = getattr(module, attribute_name)
            except AttributeError as exc:
                report = self._report(
                    requirement,
                    check_status=CheckStatus.BLOCKED,
                    policy_status=PolicyStatus.RECOGNIZED_NOT_EXECUTABLE,
                    code=BindingFailureCode.ATTRIBUTE_MISSING,
                    message=(
                        f"Binding {contract.binding_id!r} imported module "
                        f"{module_name!r}, but attribute {attribute_name!r} is absent."
                    ),
                    contract=contract,
                    details={
                        "exception_type": type(exc).__name__,
                        "exception_message": str(exc),
                        "silent_fallback_performed": False,
                    },
                    suggested_action="Correct the versioned binding import path.",
                )
                return ResolvedImplementation(report=report)

        if not callable(callable_object):
            report = self._report(
                requirement,
                check_status=CheckStatus.FAIL,
                policy_status=PolicyStatus.RECOGNIZED_NOT_EXECUTABLE,
                code=BindingFailureCode.NOT_CALLABLE,
                message=(
                    f"Binding {contract.binding_id!r} resolved to a non-callable object."
                ),
                contract=contract,
                details={
                    "resolved_type": (
                        f"{type(callable_object).__module__}."
                        f"{type(callable_object).__name__}"
                    ),
                    "silent_fallback_performed": False,
                },
                suggested_action="Point the binding to a callable implementation.",
            )
            return ResolvedImplementation(report=report)

        signature_ok, signature_details = self._validate_signature(
            callable_object, contract
        )
        if not signature_ok:
            report = self._report(
                requirement,
                check_status=CheckStatus.FAIL,
                policy_status=PolicyStatus.RECOGNIZED_NOT_EXECUTABLE,
                code=BindingFailureCode.SIGNATURE_MISMATCH,
                message=(
                    f"Binding {contract.binding_id!r} is callable, but its "
                    "signature does not satisfy the declared binding contract."
                ),
                contract=contract,
                details={
                    **signature_details,
                    "silent_fallback_performed": False,
                },
                suggested_action="Update the callable or publish a new binding version.",
            )
            return ResolvedImplementation(report=report)

        report = self._report(
            requirement,
            check_status=CheckStatus.PASS,
            policy_status=contract.support_status,
            code=BindingFailureCode.RESOLVED,
            message=(
                f"Resolved exact binding {contract.binding_id!r} to a callable "
                "with validated metadata and signature."
            ),
            contract=contract,
            details={
                **signature_details,
                "registry_id": self.registry_id,
                "registry_version": self.registry_version,
                "silent_fallback_performed": False,
            },
        )
        return ResolvedImplementation(
            report=report,
            callable_object=callable_object,
        )

    def public_catalog(self) -> dict[str, Any]:
        return {
            "schema_version": "qcol-implementation-binding-registry/1.0",
            "registry_id": self.registry_id,
            "registry_version": self.registry_version,
            "count": len(self._contracts),
            "bindings": [contract.to_dict() for contract in self.list_contracts()],
            "callable_payload_withheld": True,
        }

    @property
    def contracts(self) -> Mapping[str, ImplementationBindingContract]:
        return MappingProxyType(dict(self._contracts))


__all__ = [
    "BindingRegistryDefinitionError",
    "ImplementationBindingRegistry",
]

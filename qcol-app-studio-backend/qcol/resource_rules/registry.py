"""Exact-ID registry for resource-estimation rules and policy compatibility."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from importlib import import_module
import json
from typing import Any, Callable, Dict, Mapping, Tuple

from .contracts import (
    ResourceEstimationRuleContract,
    ResourcePolicyRuleProfile,
    ResourceRuleBinding,
    ResourceRuleEvaluation,
)
from ..runtime_integrity import SemanticDerivationRecord, stable_sha256


class ResourceRuleRegistryError(RuntimeError):
    """An explicit, stable resource-rule resolution failure."""

    def __init__(self, failure_code: str, message: str) -> None:
        super().__init__(message)
        self.failure_code = str(failure_code)


@dataclass(frozen=True)
class RegisteredResourceRule:
    contract: ResourceEstimationRuleContract
    binding: ResourceRuleBinding

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract": self.contract.to_dict(),
            "binding": self.binding.to_dict(),
        }


class ResourceRuleRegistry:
    def __init__(self) -> None:
        self._rules: Dict[str, RegisteredResourceRule] = {}
        self._policy_profiles: Dict[str, ResourcePolicyRuleProfile] = {}

    def register_rule(
        self,
        contract: ResourceEstimationRuleContract,
        binding: ResourceRuleBinding,
        *,
        replace: bool = False,
    ) -> None:
        if contract.rule_id != binding.rule_id:
            raise ResourceRuleRegistryError(
                "RESOURCE_RULE_BINDING_MISMATCH",
                "Resource rule contract ID does not match its binding rule ID.",
            )
        if contract.rule_id in self._rules and not replace:
            raise ResourceRuleRegistryError(
                "RESOURCE_RULE_DUPLICATE_ID",
                f"Resource rule {contract.rule_id!r} is already registered.",
            )
        self._rules[contract.rule_id] = RegisteredResourceRule(contract, binding)

    def register_policy_profile(
        self, profile: ResourcePolicyRuleProfile, *, replace: bool = False
    ) -> None:
        if profile.resource_policy_id in self._policy_profiles and not replace:
            raise ResourceRuleRegistryError(
                "RESOURCE_POLICY_PROFILE_DUPLICATE_ID",
                f"Resource policy profile {profile.resource_policy_id!r} is already registered.",
            )
        self._policy_profiles[profile.resource_policy_id] = profile

    def has_rule(self, rule_id: str) -> bool:
        return str(rule_id) in self._rules

    def rule(self, rule_id: str) -> RegisteredResourceRule:
        try:
            return self._rules[str(rule_id)]
        except KeyError as exc:
            raise ResourceRuleRegistryError(
                "RESOURCE_RULE_NOT_REGISTERED",
                f"Resource rule {rule_id!r} is not registered.",
            ) from exc

    def policy_profile(self, resource_policy_id: str) -> ResourcePolicyRuleProfile:
        try:
            return self._policy_profiles[str(resource_policy_id)]
        except KeyError as exc:
            raise ResourceRuleRegistryError(
                "RESOURCE_POLICY_RULE_PROFILE_MISSING",
                f"Resource policy {resource_policy_id!r} has no rule profile.",
            ) from exc

    def _load(self, binding: ResourceRuleBinding) -> Callable[..., int]:
        if not binding.executable:
            raise ResourceRuleRegistryError(
                "RESOURCE_RULE_RECOGNIZED_NOT_EXECUTABLE",
                f"Resource rule binding {binding.binding_id!r} is not executable.",
            )
        module_name, attribute = binding.import_path.split(":", 1)
        value = getattr(import_module(module_name), attribute)
        if not callable(value):
            raise ResourceRuleRegistryError(
                "RESOURCE_RULE_BINDING_NOT_CALLABLE",
                f"Resource rule binding {binding.binding_id!r} is not callable.",
            )
        return value

    def evaluate(
        self,
        *,
        resource_policy_id: str,
        rule_id: str | None,
        ansatz_policy_id: str,
        inputs: Mapping[str, int],
        explicit_rule_selection: bool,
    ) -> ResourceRuleEvaluation:
        profile = self.policy_profile(resource_policy_id)
        if not rule_id:
            if profile.requires_explicit_rule:
                raise ResourceRuleRegistryError(
                    "RESOURCE_RULE_ID_REQUIRED",
                    f"Resource policy {resource_policy_id!r} requires an explicit resource rule ID.",
                )
            raise ResourceRuleRegistryError(
                "RESOURCE_RULE_ID_MISSING",
                "No resource-estimation rule ID was supplied.",
            )
        rule_id = str(rule_id)
        if rule_id not in profile.allowed_rule_ids:
            raise ResourceRuleRegistryError(
                "RESOURCE_POLICY_RULE_MISMATCH",
                f"Rule {rule_id!r} is not allowed by resource policy {resource_policy_id!r}.",
            )
        registered = self.rule(rule_id)
        contract = registered.contract
        if ansatz_policy_id not in contract.supported_ansatz_policy_ids:
            raise ResourceRuleRegistryError(
                "RESOURCE_RULE_ANSATZ_MISMATCH",
                f"Rule {rule_id!r} does not support ansatz policy {ansatz_policy_id!r}.",
            )
        missing_inputs = [name for name in contract.required_inputs if name not in inputs]
        if missing_inputs:
            raise ResourceRuleRegistryError(
                "RESOURCE_RULE_INPUT_MISSING",
                f"Rule {rule_id!r} is missing inputs {missing_inputs}.",
            )
        callable_rule = self._load(registered.binding)
        kwargs = {name: int(inputs[name]) for name in contract.required_inputs}
        value = int(callable_rule(**kwargs))
        if value < 0:
            raise ResourceRuleRegistryError(
                "RESOURCE_RULE_NEGATIVE_ESTIMATE",
                f"Rule {rule_id!r} returned a negative parameter count.",
            )
        derivation_inputs = {
            "resource_policy_id": str(resource_policy_id),
            "resource_rule_id": contract.rule_id,
            "resource_rule_version": contract.rule_version,
            "ansatz_policy_id": str(ansatz_policy_id),
            **kwargs,
        }
        derivation_output = {
            "estimated_parameter_count": value,
        }
        derivation = SemanticDerivationRecord(
            derivation_id=(
                "derivation.resource.parameter_count."
                + stable_sha256({"inputs": derivation_inputs, "output": derivation_output})[:16]
            ),
            derivation_version="1.0.0",
            fact_id=contract.semantic_fact_id,
            authoritative_owner_id=contract.authoritative_owner_id,
            derivation_rule_id=contract.rule_id,
            explicit_inputs=derivation_inputs,
            output=derivation_output,
            source_fact_ids=contract.source_semantic_fact_ids,
        )
        return ResourceRuleEvaluation(
            resource_policy_id=str(resource_policy_id),
            rule_id=contract.rule_id,
            rule_version=contract.rule_version,
            binding_id=registered.binding.binding_id,
            binding_version=registered.binding.binding_version,
            ansatz_policy_id=str(ansatz_policy_id),
            estimated_parameter_count=value,
            input_snapshot=kwargs,
            explicit_rule_selection=bool(explicit_rule_selection),
            semantic_derivation=derivation.to_dict(),
        )

    def rules_for_ansatz(self, ansatz_policy_id: str) -> Tuple[str, ...]:
        return tuple(
            rule_id
            for rule_id, registered in sorted(self._rules.items())
            if ansatz_policy_id in registered.contract.supported_ansatz_policy_ids
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": "qcol-resource-rule-registry/1.0",
            "rules": [self._rules[key].to_dict() for key in sorted(self._rules)],
            "resource_policy_profiles": [
                self._policy_profiles[key].to_dict()
                for key in sorted(self._policy_profiles)
            ],
            "silent_fallback_allowed": False,
        }


RESOURCE_RULE_REGISTRY = ResourceRuleRegistry()


def _canonical_json(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def public_resource_rule_catalog() -> Dict[str, Any]:
    from .builtin import register_builtin_resource_rules

    register_builtin_resource_rules()
    return RESOURCE_RULE_REGISTRY.to_dict()


def resource_rule_catalog_fingerprint() -> str:
    return hashlib.sha256(_canonical_json(public_resource_rule_catalog())).hexdigest()


def validate_resource_rule_registry() -> Dict[str, bool]:
    catalog = public_resource_rule_catalog()
    rule_ids = [row["contract"]["rule_id"] for row in catalog["rules"]]
    profile_ids = [row["resource_policy_id"] for row in catalog["resource_policy_profiles"]]
    return {
        "rules_present": bool(rule_ids),
        "rule_ids_unique": len(rule_ids) == len(set(rule_ids)),
        "policy_profiles_present": bool(profile_ids),
        "policy_profile_ids_unique": len(profile_ids) == len(set(profile_ids)),
        "strict_json_safe": isinstance(json.loads(json.dumps(catalog)), dict),
        "no_silent_fallback": catalog["silent_fallback_allowed"] is False,
        "all_bindings_exact": all(
            row["contract"]["rule_id"] == row["binding"]["rule_id"]
            for row in catalog["rules"]
        ),
    }

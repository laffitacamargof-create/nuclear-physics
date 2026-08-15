"""Versioned, testable compatibility-rule registry for QCOL WP4."""
from __future__ import annotations

import hashlib
import json
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from qcol.implementation_bindings import (
    BindingKind,
    BindingRequirement,
    ImplementationBindingRegistry,
)
from qcol.mapping_policies import CheckStatus, Severity

from .bindings import build_wp4_predicate_binding_registry
from .builtin_rules import RULES
from .enums import CompatibilityRulePhase
from .rule_contracts import (
    CompatibilityCheckResult,
    CompatibilityRuleContract,
    CompatibilityRuleEvaluationReport,
    PredicateResult,
    RuleEvaluationContext,
)


class CompatibilityRuleRegistryError(ValueError):
    """Raised for programmer errors while building the rule registry."""


class CompatibilityRuleRegistry:
    """Own rule declarations and evaluate exact predicate bindings.

    The registry never searches for a substitute predicate.  Missing or broken
    predicate bindings produce a BLOCKED result carrying the structured WP3
    binding code.  Scientific failure codes are emitted only when the predicate
    runs and the relation itself fails/requires review.
    """

    def __init__(
        self,
        *,
        registry_id: str,
        registry_version: str,
        predicate_bindings: ImplementationBindingRegistry,
    ) -> None:
        if not str(registry_id).strip() or not str(registry_version).strip():
            raise CompatibilityRuleRegistryError(
                "registry_id and registry_version must be non-empty."
            )
        if not isinstance(predicate_bindings, ImplementationBindingRegistry):
            raise CompatibilityRuleRegistryError(
                "predicate_bindings must be ImplementationBindingRegistry."
            )
        self.registry_id = str(registry_id)
        self.registry_version = str(registry_version)
        self.predicate_bindings = predicate_bindings
        self._rules: dict[str, CompatibilityRuleContract] = {}
        self._order: list[str] = []

    def register(
        self,
        rule: CompatibilityRuleContract,
        *,
        replace: bool = False,
    ) -> None:
        if not isinstance(rule, CompatibilityRuleContract):
            raise CompatibilityRuleRegistryError(
                "rule must be CompatibilityRuleContract."
            )
        if rule.rule_id in self._rules and not replace:
            raise CompatibilityRuleRegistryError(
                f"Rule {rule.rule_id!r} is already registered."
            )
        if rule.rule_id not in self._rules:
            self._order.append(rule.rule_id)
        self._rules[rule.rule_id] = rule

    def rule(self, rule_id: str) -> CompatibilityRuleContract | None:
        return self._rules.get(str(rule_id))

    def list_rules(self) -> tuple[CompatibilityRuleContract, ...]:
        return tuple(self._rules[rule_id] for rule_id in self._order)

    def _binding_requirement(
        self,
        rule: CompatibilityRuleContract,
    ) -> BindingRequirement:
        return BindingRequirement(
            contract_id=rule.rule_id,
            contract_type="CompatibilityRuleContract",
            role=f"compatibility_rule.{rule.rule_id}",
            binding_id=rule.predicate_binding_id,
            binding_kind=BindingKind.COMPATIBILITY_PREDICATE,
            expected_binding_version=rule.predicate_binding_version,
            expected_convention_id=rule.predicate_convention_id,
        )

    def evaluate_rule(
        self,
        context: RuleEvaluationContext,
        rule_id: str,
    ) -> CompatibilityCheckResult:
        if not isinstance(context, RuleEvaluationContext):
            raise TypeError("context must be RuleEvaluationContext.")
        rule = self.rule(rule_id)
        if rule is None:
            raise KeyError(f"Unknown compatibility rule: {rule_id}")

        resolution = self.predicate_bindings.resolve(
            self._binding_requirement(rule)
        )
        if not resolution.executable:
            report = resolution.report
            return CompatibilityCheckResult(
                rule_id=rule.rule_id,
                rule_version=rule.rule_version,
                phase=rule.phase,
                participants=rule.participants,
                status=CheckStatus.BLOCKED,
                severity=Severity.FATAL,
                message=(
                    "The compatibility rule is declared, but its exact predicate "
                    "binding is not executable."
                ),
                binding_code=report.code.value,
                evidence={
                    "binding_resolution": report.to_dict(),
                    "scientific_rule_not_evaluated": True,
                },
                details={"silent_fallback_performed": False},
                suggested_action=(
                    report.suggested_action
                    or "Register the exact predicate binding before resolution."
                ),
            )

        predicate = resolution.callable_object
        assert predicate is not None
        try:
            outcome = predicate(context=context)
        except Exception as exc:  # predicate implementation boundary
            return CompatibilityCheckResult(
                rule_id=rule.rule_id,
                rule_version=rule.rule_version,
                phase=rule.phase,
                participants=rule.participants,
                status=CheckStatus.BLOCKED,
                severity=Severity.FATAL,
                message="The compatibility predicate raised an implementation error.",
                binding_code="COMPATIBILITY_PREDICATE_EXECUTION_FAILED",
                evidence={
                    "binding_id": rule.predicate_binding_id,
                    "exception_type": type(exc).__name__,
                    "exception_message": str(exc),
                    "scientific_rule_not_evaluated": True,
                },
                details={"silent_fallback_performed": False},
                suggested_action=(
                    "Correct and reaccept the exact versioned predicate binding; "
                    "do not substitute another rule silently."
                ),
            )
        if not isinstance(outcome, PredicateResult):
            return CompatibilityCheckResult(
                rule_id=rule.rule_id,
                rule_version=rule.rule_version,
                phase=rule.phase,
                participants=rule.participants,
                status=CheckStatus.BLOCKED,
                severity=Severity.FATAL,
                message="The compatibility predicate returned an invalid result type.",
                binding_code="COMPATIBILITY_PREDICATE_RESULT_INVALID",
                evidence={
                    "binding_id": rule.predicate_binding_id,
                    "returned_type": (
                        f"{type(outcome).__module__}.{type(outcome).__name__}"
                    ),
                    "scientific_rule_not_evaluated": True,
                },
                details={"silent_fallback_performed": False},
                suggested_action=(
                    "Return PredicateResult from the exact registered predicate."
                ),
            )

        scientific_code = None
        if outcome.status in {CheckStatus.FAIL, CheckStatus.REVIEW}:
            scientific_code = rule.failure_code.value
        return CompatibilityCheckResult(
            rule_id=rule.rule_id,
            rule_version=rule.rule_version,
            phase=rule.phase,
            participants=rule.participants,
            status=outcome.status,
            severity=rule.severity,
            message=outcome.message,
            failure_code=scientific_code,
            evidence=outcome.evidence,
            details={
                **dict(outcome.details),
                "predicate_binding_id": rule.predicate_binding_id,
                "predicate_binding_version": rule.predicate_binding_version,
                "predicate_convention_id": rule.predicate_convention_id,
                "silent_fallback_performed": False,
            },
            suggested_action=(
                outcome.suggested_action
                or (rule.suggested_action if scientific_code else None)
            ),
        )

    def evaluate(
        self,
        context: RuleEvaluationContext,
        *,
        rule_ids: Iterable[str] | None = None,
    ) -> CompatibilityRuleEvaluationReport:
        selected = tuple(rule_ids) if rule_ids is not None else tuple(self._order)
        results = tuple(self.evaluate_rule(context, rule_id) for rule_id in selected)
        pairwise = tuple(
            result
            for result in results
            if result.phase is CompatibilityRulePhase.PAIRWISE
        )
        global_results = tuple(
            result
            for result in results
            if result.phase is CompatibilityRulePhase.GLOBAL_INVARIANT
        )
        digest_payload = {
            "context_id": context.context_id,
            "rule_results": [result.to_dict() for result in results],
        }
        report_id = "compat-report-" + hashlib.sha256(
            json.dumps(
                digest_payload,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        ).hexdigest()[:16]
        return CompatibilityRuleEvaluationReport(
            report_id=report_id,
            context_id=context.context_id,
            pairwise_results=pairwise,
            global_results=global_results,
            runtime_gate_enforced=False,
            scientific_behavior_change=False,
        )

    def public_catalog(self) -> dict[str, Any]:
        rules = [rule.to_dict() for rule in self.list_rules()]
        return {
            "schema_version": "qcol-compatibility-rule-registry/1.0",
            "registry_id": self.registry_id,
            "registry_version": self.registry_version,
            "rule_count": len(rules),
            "rules": rules,
            "pairwise_rule_ids": [
                rule.rule_id
                for rule in self.list_rules()
                if rule.phase is CompatibilityRulePhase.PAIRWISE
            ],
            "global_invariant_rule_ids": [
                rule.rule_id
                for rule in self.list_rules()
                if rule.phase is CompatibilityRulePhase.GLOBAL_INVARIANT
            ],
            "predicate_bindings": self.predicate_bindings.public_catalog(),
            "callable_payload_withheld": True,
            "silent_fallback_allowed": False,
        }

    @property
    def rules(self) -> Mapping[str, CompatibilityRuleContract]:
        return MappingProxyType(dict(self._rules))


def build_wp4_rule_registry() -> CompatibilityRuleRegistry:
    registry = CompatibilityRuleRegistry(
        registry_id="qcol.compatibility.rules.v1",
        registry_version="1.0.0",
        predicate_bindings=build_wp4_predicate_binding_registry(),
    )
    for rule in RULES:
        registry.register(rule)
    return registry


__all__ = [
    "CompatibilityRuleRegistryError",
    "CompatibilityRuleRegistry",
    "build_wp4_rule_registry",
]

"""Backward-compatible helpers backed by the versioned resource-rule registry."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ..resource_rules import (
    RESOURCE_RULE_REGISTRY,
    register_builtin_resource_rules,
)


@dataclass(frozen=True)
class ParameterCountEstimate:
    ansatz_policy_id: str
    rule_id: str
    estimated_parameter_count: int
    resource_policy_id: str = "bounded_direct_qubit.v1"
    binding_id: str | None = None
    explicit_rule_selection: bool = False
    semantic_derivation: Mapping[str, Any] | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "resource_policy_id": self.resource_policy_id,
            "ansatz_policy_id": self.ansatz_policy_id,
            "rule_id": self.rule_id,
            "resource_rule_binding_id": self.binding_id,
            "estimated_parameter_count": self.estimated_parameter_count,
            "explicit_rule_selection": self.explicit_rule_selection,
            "semantic_derivation": dict(self.semantic_derivation or {}),
        }


def _unique_rule_for_ansatz(ansatz_policy_id: str) -> str:
    register_builtin_resource_rules()
    matches = RESOURCE_RULE_REGISTRY.rules_for_ansatz(ansatz_policy_id)
    if len(matches) != 1:
        from ..resource_rules import ResourceRuleRegistryError

        raise ResourceRuleRegistryError(
            "RESOURCE_RULE_INFERENCE_AMBIGUOUS",
            f"Expected exactly one legacy rule for ansatz {ansatz_policy_id!r}; found {matches}.",
        )
    return matches[0]


def estimate_direct_qubit_parameter_count(
    *,
    ansatz_policy_id: str,
    n_qubits: int,
    n_layers: int = 1,
    resource_policy_id: str = "bounded_direct_qubit.v1",
    resource_rule_id: str | None = None,
) -> ParameterCountEstimate:
    """Evaluate a parameter-count rule without consulting ModelContract.family.

    ``bounded_direct_qubit.v2`` requires ``resource_rule_id`` explicitly.  The
    v1 default is retained only for frozen legacy contracts and infers the
    unique rule from the versioned ansatz policy ID.
    """
    register_builtin_resource_rules()
    explicit = resource_rule_id is not None
    if resource_rule_id is None:
        resource_rule_id = _unique_rule_for_ansatz(ansatz_policy_id)
    evaluation = RESOURCE_RULE_REGISTRY.evaluate(
        resource_policy_id=resource_policy_id,
        rule_id=resource_rule_id,
        ansatz_policy_id=ansatz_policy_id,
        inputs={"n_qubits": int(n_qubits), "n_layers": int(n_layers)},
        explicit_rule_selection=explicit,
    )
    return ParameterCountEstimate(
        ansatz_policy_id=evaluation.ansatz_policy_id,
        rule_id=evaluation.rule_id,
        estimated_parameter_count=evaluation.estimated_parameter_count,
        resource_policy_id=evaluation.resource_policy_id,
        binding_id=evaluation.binding_id,
        explicit_rule_selection=evaluation.explicit_rule_selection,
        semantic_derivation=evaluation.semantic_derivation,
    )

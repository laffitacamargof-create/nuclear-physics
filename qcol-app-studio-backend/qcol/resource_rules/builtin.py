"""Built-in resource-estimation contracts and exact callable bindings."""
from __future__ import annotations

from .contracts import (
    ResourceEstimationRuleContract,
    ResourcePolicyRuleProfile,
    ResourceRuleBinding,
)
from .registry import RESOURCE_RULE_REGISTRY

_REGISTERED = False

ONE_EXCITATION_RULE_ID = "parameter_count.one_excitation_chain.n_minus_one.v1"
GENERIC_RY_RZ_RULE_ID = "parameter_count.generic_ry_rz.two_per_qubit_per_layer.v1"


def register_builtin_resource_rules() -> None:
    global _REGISTERED
    if _REGISTERED:
        return

    RESOURCE_RULE_REGISTRY.register_rule(
        ResourceEstimationRuleContract(
            rule_id=ONE_EXCITATION_RULE_ID,
            rule_version="1.0.0",
            label="One-excitation chain parameter count",
            description=(
                "Count one nearest-neighbour Givens parameter per chain edge; "
                "Nθ = max(n_qubits − 1, 0)."
            ),
            metric_id="ansatz_parameter_count",
            output_key="estimated_parameter_count",
            supported_ansatz_policy_ids=("one_excitation_chain_givens.v1",),
            required_inputs=("n_qubits", "n_layers"),
            formula_label="max(n_qubits - 1, 0)",
            semantic_fact_id="fact.resource.ansatz_parameter_count",
            authoritative_owner_id="owner.resource_assessor",
            source_semantic_fact_ids=(
                "fact.scientific.ansatz_parameterization",
                "fact.scientific.resolved_realization",
            ),
            limitations=(
                "Valid only for the registered one_excitation_chain_givens.v1 ansatz.",
                "n_layers is retained in the input identity but does not multiply the v1 chain count.",
            ),
        ),
        ResourceRuleBinding(
            binding_id="binding.resource_rule.one_excitation_chain.n_minus_one.v1",
            binding_version="1.0.0",
            rule_id=ONE_EXCITATION_RULE_ID,
            import_path=(
                "qcol.resource_rules.estimators:"
                "estimate_one_excitation_chain_parameter_count"
            ),
            implementation_status="implemented",
            provider="QCOL",
            source_revision="post-phase-c-qho-resource-hardening.v1",
            provenance={
                "scientific_owner": "QCOL architecture",
                "derived_from_ansatz_policy": "one_excitation_chain_givens.v1",
            },
        ),
    )

    RESOURCE_RULE_REGISTRY.register_rule(
        ResourceEstimationRuleContract(
            rule_id=GENERIC_RY_RZ_RULE_ID,
            rule_version="1.0.0",
            label="Generic RY/RZ layered parameter count",
            description="Count two one-qubit rotation parameters per qubit per layer.",
            metric_id="ansatz_parameter_count",
            output_key="estimated_parameter_count",
            supported_ansatz_policy_ids=("generic_ry_rz_linear_cnot.v1",),
            required_inputs=("n_qubits", "n_layers"),
            formula_label="2 * n_qubits * n_layers",
            semantic_fact_id="fact.resource.ansatz_parameter_count",
            authoritative_owner_id="owner.resource_assessor",
            source_semantic_fact_ids=(
                "fact.scientific.ansatz_parameterization",
                "fact.scientific.resolved_realization",
            ),
            limitations=(
                "Valid only for generic_ry_rz_linear_cnot.v1.",
            ),
        ),
        ResourceRuleBinding(
            binding_id="binding.resource_rule.generic_ry_rz.two_per_qubit_per_layer.v1",
            binding_version="1.0.0",
            rule_id=GENERIC_RY_RZ_RULE_ID,
            import_path=(
                "qcol.resource_rules.estimators:"
                "estimate_generic_ry_rz_parameter_count"
            ),
            implementation_status="implemented",
            provider="QCOL",
            source_revision="post-phase-c-qho-resource-hardening.v1",
            provenance={
                "scientific_owner": "QCOL architecture",
                "derived_from_ansatz_policy": "generic_ry_rz_linear_cnot.v1",
            },
        ),
    )

    # Legacy v1 may infer the unique rule from the ansatz ID to preserve frozen
    # pre-QHO model contracts.  New QHO contracts use v2, which requires an
    # explicit rule ID and never falls back.
    RESOURCE_RULE_REGISTRY.register_policy_profile(
        ResourcePolicyRuleProfile(
            resource_policy_id="bounded_direct_qubit.v1",
            profile_version="1.0.0",
            allowed_rule_ids=(ONE_EXCITATION_RULE_ID, GENERIC_RY_RZ_RULE_ID),
            requires_explicit_rule=False,
            description="Legacy direct-qubit resource policy with ansatz-ID rule inference.",
        )
    )
    RESOURCE_RULE_REGISTRY.register_policy_profile(
        ResourcePolicyRuleProfile(
            resource_policy_id="bounded_direct_qubit.v2",
            profile_version="2.0.0",
            allowed_rule_ids=(ONE_EXCITATION_RULE_ID, GENERIC_RY_RZ_RULE_ID),
            requires_explicit_rule=True,
            description=(
                "Direct-qubit resource policy requiring the ModelContract to "
                "declare an exact versioned resource-estimation rule."
            ),
        )
    )

    _REGISTERED = True


register_builtin_resource_rules()

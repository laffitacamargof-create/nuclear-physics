"""Versioned Phase C comparison policies."""
from __future__ import annotations
from .contracts import ComparisonPolicyContract
from .enums import ComparisonKind

DECLARED_METRICS_POLICY_ID = "declared_metrics_and_uncertainty.v1"
MAPPING_RESOURCE_POLICY_ID = "mapping_resources_and_equivalence.v1"


def build_comparison_policies() -> tuple[ComparisonPolicyContract, ...]:
    return (
        ComparisonPolicyContract(
            policy_id=DECLARED_METRICS_POLICY_ID,
            policy_version="1.0.0",
            comparison_kind=ComparisonKind.EXECUTABLE_VQE,
            required_identity_fields=("model_id", "task_id", "evidence_schema", "pipeline_entrypoint"),
            required_metrics=("verification_status", "evidence_completeness", "sector_leakage"),
            optional_metrics=(
                "absolute_error", "standard_error", "reconstructed_energy", "optimizer_converged",
                "shots", "qubits", "circuit_depth", "two_qubit_cost", "runtime_seconds",
            ),
            uncertainty_rule="Use max(numerical_floor, sigma_multiplier*sqrt(se_baseline^2+se_candidate^2)); missing uncertainty makes a numerical preference inconclusive.",
            missing_metric_rule="Missing required safety/verification metrics rejects the candidate; missing optional comparison metrics yields INCONCLUSIVE.",
            acceptance_rule="Candidate must pass its own declared verification and preserve the declared sector; comparison never overrides either run's verification.",
            physical_accuracy_ranking_allowed=True,
            description="Compare a user-approved executable candidate against its baseline using declared metrics, uncertainty, and each run's own verification.",
        ),
        ComparisonPolicyContract(
            policy_id=MAPPING_RESOURCE_POLICY_ID,
            policy_version="1.0.0",
            comparison_kind=ComparisonKind.MAPPING_ANALYSIS,
            required_identity_fields=("model_id", "task_id", "source_problem_fingerprint", "evidence_schema"),
            required_metrics=("transformation_verified",),
            optional_metrics=("qubits", "pauli_terms", "maximum_pauli_weight", "mean_pauli_weight", "grouping_estimate", "transformation_time"),
            uncertainty_rule="No sampled uncertainty is used for deterministic operator-resource metrics.",
            missing_metric_rule="Missing resource metrics yield INCONCLUSIVE rather than an invented preference.",
            acceptance_rule="Both mappings must independently pass transformation/equivalence checks; resource preference is not a claim of greater physical accuracy.",
            physical_accuracy_ranking_allowed=False,
            description="Compare verified mapping-analysis outputs on the same operator and ordering using resource metrics only.",
        ),
    )


def get_comparison_policy(policy_id: str) -> ComparisonPolicyContract:
    for item in build_comparison_policies():
        if item.policy_id == policy_id:
            return item
    raise KeyError(policy_id)


def public_comparison_policy_catalog() -> dict:
    return {
        "schema_version": "qcol-comparison-policy-catalog/1.0",
        "policies": [item.to_dict() for item in build_comparison_policies()],
        "outcomes": ["ADOPT", "REJECT", "INCONCLUSIVE"],
        "silent_replacement_allowed": False,
        "same_pipeline_required": True,
    }


__all__ = [
    "DECLARED_METRICS_POLICY_ID", "MAPPING_RESOURCE_POLICY_ID",
    "build_comparison_policies", "get_comparison_policy", "public_comparison_policy_catalog",
]

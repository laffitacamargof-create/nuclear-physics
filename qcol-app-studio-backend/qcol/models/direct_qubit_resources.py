"""Framework-independent resource assessment for direct-qubit realizations.

The public resource contract is intentionally dependency-light.  Scientific
components declare their local semantics; the ResourceAssessor is the single
authoritative owner of aggregate resource facts and derives them from the
complete resolved composition.  No ModelFamily or UI label participates in
resource decisions.
"""
from __future__ import annotations

from typing import Any, Mapping

from ..model_execution_types import (
    AnsatzBuildResult,
    MappingResult,
    ModelBuildContext,
    ResourceAssessment,
)
from ..runtime_integrity import SemanticDerivationRecord, stable_sha256
from .resource_estimators import estimate_direct_qubit_parameter_count


def _aggregate_inputs(
    context: ModelBuildContext,
    *,
    n_qubits: int,
    n_layers: int,
    estimated_parameter_count: int,
    mapping: MappingResult | None,
    ansatz: AnsatzBuildResult | None,
    measurement_plan: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return the explicit, classification-independent derivation inputs."""

    groups = 0 if measurement_plan is None else len(measurement_plan.get("groups", []))
    actual_parameter_count = (
        estimated_parameter_count
        if ansatz is None
        else len(ansatz.parameter_symbols)
    )
    actual_qubit_count = n_qubits if mapping is None else int(mapping.n_qubits)
    return {
        "model_contract_id": context.contract.model_id,
        "model_contract_version": context.contract.model_version,
        "task_id": context.instance.task_id,
        "mapping_policy_id": context.contract.mapping_policy_id,
        "sector_policy_id": context.contract.sector_policy_id,
        "state_preparation_policy_id": context.contract.state_preparation_policy_id,
        "ansatz_policy_id": context.contract.ansatz_policy_id,
        "measurement_policy_id": context.contract.measurement_policy_id,
        "resource_policy_id": context.contract.resource_policy_id,
        "resource_estimation_rule_id": context.contract.resource_estimation_rule_id,
        "runtime_policy_id": context.contract.runtime_policy_id,
        "target_backend": context.request_metadata.get("target_backend"),
        "execution_mode": context.request_metadata.get("execution_mode"),
        "declared_n_qubits": int(n_qubits),
        "resolved_n_qubits": int(actual_qubit_count),
        "ansatz_layers": int(n_layers),
        "estimated_parameter_count": int(estimated_parameter_count),
        "resolved_parameter_count": int(actual_parameter_count),
        "measurement_group_count": int(groups),
    }

RESOLVED_COMPOSITION_RESOURCE_DERIVATION_RULE_ID = (
    "resource_assessment.resolved_composition.v1"
)


def _aggregate_derivation(
    context: ModelBuildContext,
    *,
    n_qubits: int,
    n_layers: int,
    estimated_parameter_count: int,
    parameter_derivation: Mapping[str, Any],
    within_declared_envelope: bool,
    mapping: MappingResult | None,
    ansatz: AnsatzBuildResult | None,
    measurement_plan: Mapping[str, Any] | None,
) -> SemanticDerivationRecord:
    inputs = _aggregate_inputs(
        context,
        n_qubits=n_qubits,
        n_layers=n_layers,
        estimated_parameter_count=estimated_parameter_count,
        mapping=mapping,
        ansatz=ansatz,
        measurement_plan=measurement_plan,
    )
    output = {
        "estimated_n_qubits": int(n_qubits),
        "resolved_n_qubits": int(inputs["resolved_n_qubits"]),
        "estimated_parameter_count": int(estimated_parameter_count),
        "resolved_parameter_count": int(inputs["resolved_parameter_count"]),
        "measurement_group_count": int(inputs["measurement_group_count"]),
        "within_declared_envelope": bool(within_declared_envelope),
        "parameter_count_derivation_fingerprint": parameter_derivation.get(
            "derivation_fingerprint"
        ),
    }
    return SemanticDerivationRecord(
        derivation_id=(
            "derivation.resource.aggregate_report."
            + stable_sha256({"inputs": inputs, "output": output})[:16]
        ),
        derivation_version="1.0.0",
        fact_id="fact.resource.aggregate_report",
        authoritative_owner_id="owner.resource_assessor",
        derivation_rule_id=RESOLVED_COMPOSITION_RESOURCE_DERIVATION_RULE_ID,
        explicit_inputs=inputs,
        output=output,
        source_fact_ids=(
            "fact.scientific.model_definition",
            "fact.scientific.task_requirements",
            "fact.scientific.encoding_semantics",
            "fact.scientific.ansatz_parameterization",
            "fact.scientific.execution_target_constraints",
            "fact.scientific.resolved_realization",
            "fact.resource.ansatz_parameter_count",
        ),
    )


def bounded_direct_resource_policy(
    context: ModelBuildContext,
    mapping: MappingResult | None = None,
    ansatz: AnsatzBuildResult | None = None,
    measurement_plan: Mapping[str, Any] | None = None,
):
    """Assess a direct-qubit realization from explicit policy identities.

    Parameter-count semantics are owned by the declared ``AnsatzPolicy`` and
    evaluated through its exact resource rule.  Aggregate resources are then
    derived by this ResourceAssessor from the complete resolved composition.
    ``ModelContract.family`` and UI grouping labels are never consulted.
    """

    n_qubits = int(
        context.instance.parameters.get(
            "n_modes", context.instance.parameters.get("n_qubits", 1)
        )
    )
    layers = int(context.instance.parameters.get("ansatz_layers", 1))
    parameter_estimate = estimate_direct_qubit_parameter_count(
        resource_policy_id=context.contract.resource_policy_id,
        resource_rule_id=context.contract.resource_estimation_rule_id,
        ansatz_policy_id=context.contract.ansatz_policy_id,
        n_qubits=n_qubits,
        n_layers=layers,
    )
    estimate_params = parameter_estimate.estimated_parameter_count
    envelope = context.contract.resource_validity
    within = (
        envelope.simulator_max_qubits is None
        or n_qubits <= envelope.simulator_max_qubits
    ) and (
        envelope.maximum_parameter_count is None
        or estimate_params <= envelope.maximum_parameter_count
    )

    parameter_derivation = dict(parameter_estimate.semantic_derivation or {})
    aggregate_derivation = _aggregate_derivation(
        context,
        n_qubits=n_qubits,
        n_layers=layers,
        estimated_parameter_count=estimate_params,
        parameter_derivation=parameter_derivation,
        within_declared_envelope=within,
        mapping=mapping,
        ansatz=ansatz,
        measurement_plan=measurement_plan,
    )

    identity = {
        "ansatz_policy_id": parameter_estimate.ansatz_policy_id,
        "resource_policy_id": parameter_estimate.resource_policy_id,
        "parameter_count_rule_id": parameter_estimate.rule_id,
        "resource_rule_binding_id": parameter_estimate.binding_id,
        "explicit_resource_rule": parameter_estimate.explicit_rule_selection,
        "parameter_count_source": "ansatz_policy_via_resource_assessor",
        "semantic_authority_owner_id": "owner.resource_assessor",
        "parameter_count_derivation": parameter_derivation,
        "resource_report_derivation": aggregate_derivation.to_dict(),
    }

    if mapping is None:
        return {
            "estimated_n_qubits": n_qubits,
            "estimated_parameter_count": estimate_params,
            **identity,
            "within_declared_envelope": within,
        }

    groups = 0 if measurement_plan is None else len(measurement_plan.get("groups", []))
    return ResourceAssessment(
        status="within_envelope" if within else "outside_envelope",
        n_qubits=mapping.n_qubits,
        parameter_count=0 if ansatz is None else len(ansatz.parameter_symbols),
        pauli_term_count=len(mapping.qubit_hamiltonian.terms),
        measurement_group_count=groups,
        estimated_sector_dimension=None,
        within_declared_envelope=within,
        notes=tuple(envelope.notes),
        metadata={
            **identity,
            "preflight_estimated_parameter_count": estimate_params,
            "preflight_estimated_n_qubits": n_qubits,
        },
    )


__all__ = [
    "RESOLVED_COMPOSITION_RESOURCE_DERIVATION_RULE_ID",
    "bounded_direct_resource_policy",
]

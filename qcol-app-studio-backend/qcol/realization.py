"""Build a QuantumRealizationArtifact from an actual ResolvedModelPlan."""
from __future__ import annotations

from typing import Any, Mapping, Optional
from uuid import uuid4

import cirq

from .contracts import ProblemArtifact
from .model_contracts import ModelContractError, QuantumRealizationArtifact, ResolvedModelPlan
from .model_execution_types import ModelBuildContext, ResourceAssessment
from .runtime_integrity import scientific_identity_fingerprint, stable_sha256
from .plugin_registry import get_model_plugin
from .request_boundaries import copy_plain_data


_RUNTIME_CONTROL_KEYS = (
    "execution_mode",
    "target_backend",
    "shots",
    "final_shots",
    "seed",
    "run_mode",
    "initial_parameters",
    "max_evaluations",
    "energy_tolerance",
    "optimizer_tolerance",
    "convergence_patience",
    "rhobeg",
    "acceptance_abs_floor",
    "sector_leakage_floor",
)


def _runtime_controls(request_metadata: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: copy_plain_data(request_metadata[key])
        for key in _RUNTIME_CONTROL_KEYS
        if key in request_metadata
    }


def _request_summary(request_metadata: Mapping[str, Any]) -> dict[str, Any]:
    return {
        str(key): copy_plain_data(value)
        for key, value in request_metadata.items()
        if key != "initial_parameters"
    }


def build_quantum_realization(
    plan: ResolvedModelPlan,
    *,
    request_metadata: Optional[Mapping[str, Any]] = None,
    model_task_plan: Any = None,
) -> QuantumRealizationArtifact:
    if not plan.actual_resolved:
        raise ModelContractError(
            "Quantum realization requires an actual callable ResolvedModelPlan."
        )
    if not plan.capability_report.may_enter_runtime:
        raise ModelContractError("Capability resolution did not authorize runtime entry.")
    assert plan.contract is not None and plan.instance is not None
    context = ModelBuildContext(
        contract=plan.contract,
        instance=plan.instance,
        request_metadata=dict(request_metadata or {}),
    )

    hamiltonian = plan.binding("hamiltonian")(context)
    sector = plan.binding("sector")(context, hamiltonian)
    mapping = plan.binding("mapping")(context, hamiltonian, sector)
    reference = plan.binding("reference")(context, mapping, sector)
    initial_state = plan.binding("state_preparation")(context, mapping, sector)
    ansatz = plan.binding("ansatz")(
        context, mapping, sector, initial_state, reference
    )
    measurement_plan = plan.binding("measurement")(context, mapping, ansatz)
    resource = plan.binding("resource")(context, mapping, ansatz, measurement_plan)
    if not isinstance(resource, ResourceAssessment):
        raise ModelContractError("Resource policy did not return ResourceAssessment.")
    if not resource.within_declared_envelope:
        raise ModelContractError(
            "Resolved model exceeds the plugin's declared resource validity envelope."
        )
    runtime_declaration = plan.binding("runtime")(context)
    interpretation = plan.binding("interpretation")(
        context, mapping, sector, reference, resource
    )

    # The ModelPlugin is selected once at the composition root.  It carries the
    # exact identity factories required to fill the canonical IR without model
    # branches in the shared core.
    model_plugin = get_model_plugin(plan.contract.model_id)
    task_id = (
        plan.instance.task_id
        if model_task_plan is None
        else model_task_plan.task_contract.task_id
    )
    encoding_context_id = model_plugin.encoding_context(
        instance=plan.instance,
        mapping=mapping,
        task_plan=model_task_plan,
    )
    identity = dict(model_plugin.scientific_identity(
        model_plan=plan,
        task_plan=model_task_plan,
        mapping=mapping,
        ansatz=ansatz,
        encoding_context_id=encoding_context_id,
    ))
    mapping_policy_id = str(identity["mapping_policy_id"])
    state_preparation_policy_id = str(identity["state_preparation_policy_id"])
    ansatz_policy_id = str(identity["ansatz_policy_id"])
    measurement_policy_id = str(identity["measurement_policy_id"])
    reference_policy_id = str(identity["reference_policy_id"])
    controller_id = str(identity["controller_id"])
    scientific_fingerprint = scientific_identity_fingerprint(
        model_id=plan.contract.model_id,
        task_id=task_id,
        target_sector=dict(sector.target_sector),
        encoding_context_id=encoding_context_id,
        mapping_policy_id=mapping_policy_id,
        state_preparation_policy_id=state_preparation_policy_id,
        ansatz_policy_id=ansatz_policy_id,
        measurement_policy_id=measurement_policy_id,
        reference_policy_id=reference_policy_id,
    )
    canonical_ir_view = {
        "schema_version": "qcol-scientific-realization-view/1.0",
        "model_id": plan.contract.model_id,
        "task_id": task_id,
        "target_sector": dict(sector.target_sector),
        "encoding_context_id": encoding_context_id,
        "mapping_policy_id": mapping_policy_id,
        "state_preparation_policy_id": state_preparation_policy_id,
        "ansatz_policy_id": ansatz_policy_id,
        "measurement_policy_id": measurement_policy_id,
        "reference_policy_id": reference_policy_id,
        "controller_id": controller_id,
        "scientific_fingerprint": scientific_fingerprint,
    }

    template = cirq.Circuit(initial_state.circuit)
    template += cirq.Circuit(ansatz.variational_circuit)

    validation_checks = {
        **{str(k): bool(v) for k, v in sector.validation_checks.items()},
        **{str(k): bool(v) for k, v in mapping.validation_checks.items()},
        "all_policy_bindings_resolved": plan.actual_resolved,
        "resource_within_declared_envelope": resource.within_declared_envelope,
        "runtime_policy_matches_contract": (
            str(runtime_declaration.get("runtime_policy_id"))
            == plan.contract.runtime_policy_id
        ),
    }

    parameter_schema = {
        "names": [str(symbol) for symbol in ansatz.parameter_symbols],
        "initial_values": [float(v) for v in ansatz.initial_parameters],
        "family": ansatz.family,
        "metadata": dict(ansatz.metadata),
    }
    initial_state_metadata = {
        "label": initial_state.label,
        "occupied_indices": list(initial_state.occupied_indices),
        "metadata": dict(initial_state.metadata),
    }
    mapping_metadata = {
        **dict(mapping.mapping_metadata),
        "mapping_name": mapping.mapping_name,
        "encoding": mapping.encoding,
        "policy_id": mapping_policy_id,
        "encoding_context_id": encoding_context_id,
    }
    realization_id = f"realization-{uuid4().hex[:12]}"
    problem_artifact_id = f"artifact-{uuid4().hex[:12]}"
    composition_root_payload = {
        "schema_version": "qcol-composition-root-identity/1.0",
        "realization_id": realization_id,
        "model_id": plan.contract.model_id,
        "model_version": plan.contract.model_version,
        "task_id": task_id,
        "resolved_plan_id": plan.plan_id,
        "problem_artifact_id": problem_artifact_id,
        "rule": "ARCH-COMP-001",
        "encoding_context_id": encoding_context_id,
        "mapping_policy_id": mapping_policy_id,
        "scientific_fingerprint": scientific_fingerprint,
    }
    composition_root_fingerprint = stable_sha256(composition_root_payload)

    reference_declaration = {
        "policy_id": reference_policy_id,
        "available": reference is not None,
        "kind": None if reference is None else reference.get("kind"),
        "scope": None if reference is None else reference.get("reference_scope"),
        "validity": plan.contract.reference_validity.to_dict(),
    }

    cell_snapshot = {} if model_task_plan is None else dict(model_task_plan.cell_snapshot)
    published_cell_status = cell_snapshot.get("status")
    if published_cell_status == "acceptance_verified":
        published_cell_gate = "PASS"
    elif published_cell_status in {"experimental", "execution_ready"}:
        published_cell_gate = "REVIEW"
    else:
        published_cell_gate = "NOT_EXECUTABLE"
    # Mapping acceptance applicability is declared by the ModelPlugin.  The
    # shared composition root never infers scientific scope from a model name,
    # task name, or mapping-string convention.
    mapping_acceptance_mode = model_plugin.mapping_acceptance_mode(task_id)
    if mapping_acceptance_mode == "analysis_only":
        mapper_status = "PASS"
        composition_status = "NOT_APPLICABLE"
    elif mapping_acceptance_mode == "full":
        mapper_status = "PASS"
        composition_status = (
            "PASS" if published_cell_status == "acceptance_verified" else "REVIEW"
        )
    else:
        mapper_status = "NOT_APPLICABLE"
        composition_status = "NOT_APPLICABLE"
    acceptance_certificate = {
        "schema_version": "qcol-runtime-acceptance-certificate/1.0",
        "model_task_plan_id": None if model_task_plan is None else model_task_plan.plan_id,
        "model_task_cell_id": cell_snapshot.get("cell_id"),
        "acceptance_suite_id": cell_snapshot.get("acceptance_suite_id", plan.contract.acceptance_suite_id),
        "published_cell_status": published_cell_status,
        "declared_scale": cell_snapshot.get("validated_scale", cell_snapshot.get("resource_envelope", {})),
        "mapping_policy_id": mapping_policy_id,
        "mapping_acceptance_mode": mapping_acceptance_mode,
        "encoding_context_id": encoding_context_id,
        "policy_encoding_contexts": {
            name: encoding_context_id
            for name in ("mapping", "state_preparation", "ansatz", "measurement", "reference", "task_operators")
        },
        "mapper_gate": {
            "status": mapper_status,
            "source": (
                "resolved mapping policy + Mapping Integrity Profile"
                if mapping_acceptance_mode != "not_applicable"
                else "direct encoding; Mapping-Realization mapper gate not applicable"
            ),
        },
        "composition_gate": {
            "status": composition_status,
            "source": "Capability Resolver",
        },
        "cell_gate": {
            "published_status": published_cell_gate,
            "runtime_verification_status": "PENDING",
        },
        "three_gate_semantics_preserved": True,
    }

    problem_artifact = ProblemArtifact(
        artifact_id=problem_artifact_id,
        model_id=plan.contract.model_id,
        method=str(context.request_metadata.get("method", plan.contract.domain)),
        problem=str(
            plan.instance.source_metadata.get(
                "legacy_problem", plan.contract.problem_type
            )
        ),
        parameters=dict(hamiltonian.parameters),
        units=dict(plan.instance.units),
        target_sector=dict(sector.target_sector),
        encoding=mapping.encoding,
        mapping=mapping.mapping_name,
        n_qubits=int(mapping.n_qubits),
        qubit_order=(
            "Explicit orbital/mode-to-qubit ordering is retained in "
            "QuantumRealizationArtifact.orbital_to_qubit_order; QASM register order "
            "is q[0]...q[n-1]."
        ),
        symmetries=list(mapping.preserved_symmetries),
        scientific_context={
            **dict(interpretation),
            "model_contract": plan.contract.to_dict(),
            "resolved_model_plan": plan.to_dict(),
            "capability_report": plan.capability_report.to_dict(),
            "runtime_policy": runtime_declaration,
            "task_contract": (None if model_task_plan is None else model_task_plan.task_contract.to_dict()),
            "task_execution_plan": (None if model_task_plan is None else model_task_plan.task_execution_plan.to_dict()),
            "model_task_cell": (None if model_task_plan is None else dict(model_task_plan.cell_snapshot)),
            "canonical_ir": canonical_ir_view,
            "acceptance_certificate": acceptance_certificate,
            "composition_root": {
                **composition_root_payload,
                "fingerprint": composition_root_fingerprint,
                "downstream_reinference_allowed": False,
            },
        },
        hamiltonian_payload=mapping.qubit_hamiltonian,
        ansatz_template=template,
        parameter_symbols=tuple(ansatz.parameter_symbols),
        initial_parameters=[float(v) for v in ansatz.initial_parameters],
        measurement_plan=dict(measurement_plan),
        parameter_fixture=(
            None if ansatz.parameter_fixture is None else dict(ansatz.parameter_fixture)
        ),
        exact_reference=None if reference is None else dict(reference),
        crosscheck_payloads={
            **dict(mapping.crosscheck_payloads),
            "domain_hamiltonian": hamiltonian.domain_hamiltonian,
        },
        validation_checks=validation_checks,
        provenance={
            "model_contract_id": plan.contract.model_id,
            "model_contract_version": plan.contract.model_version,
            "model_instance_id": plan.instance.instance_id,
            "resolved_plan_id": plan.plan_id,
            "policy_bindings": dict(plan.policy_bindings),
            "hamiltonian_provenance": dict(hamiltonian.provenance),
            "quantum_realization": {
                "mapping_metadata": mapping_metadata,
                "orbital_to_qubit_order": dict(mapping.orbital_to_qubit_order),
                "initial_state": initial_state_metadata,
                "parameter_schema": parameter_schema,
                "resource_report": resource.to_dict(),
                "reference_declaration": reference_declaration,
                "canonical_ir": canonical_ir_view,
                "acceptance_certificate": acceptance_certificate,
            },
            "acceptance_suite_id": plan.contract.acceptance_suite_id,
            "task_contract_id": (None if model_task_plan is None else model_task_plan.task_contract.task_id),
            "task_contract_version": (None if model_task_plan is None else model_task_plan.task_contract.task_version),
            "model_task_plan_id": (None if model_task_plan is None else model_task_plan.plan_id),
            "model_task_cell": (None if model_task_plan is None else dict(model_task_plan.cell_snapshot)),
            "composition_root": {
                **composition_root_payload,
                "fingerprint": composition_root_fingerprint,
                "downstream_reinference_allowed": False,
            },
        },
    )
    problem_artifact.validate()

    request_payload = dict(request_metadata or {})
    realization = QuantumRealizationArtifact(
        realization_id=realization_id,
        model_id=plan.contract.model_id,
        model_version=plan.contract.model_version,
        task_id=task_id,
        runtime_policy_id=controller_id,
        problem_artifact_id=problem_artifact.artifact_id,
        contract_snapshot=plan.contract.to_dict(),
        instance_snapshot=plan.instance.to_dict(),
        capability_report=plan.capability_report,
        runtime_artifact=problem_artifact,
        qubit_hamiltonian_payload=mapping.qubit_hamiltonian,
        initial_state_circuit=initial_state.circuit,
        parameterized_ansatz_circuit=template,
        measurement_plan_payload=problem_artifact.measurement_plan,
        resolved_plan_snapshot=plan.to_dict(),
        mapping_metadata=mapping_metadata,
        orbital_to_qubit_order=dict(mapping.orbital_to_qubit_order),
        preserved_symmetries=tuple(mapping.preserved_symmetries),
        initial_state=initial_state_metadata,
        parameter_schema=parameter_schema,
        resource_report=resource.to_dict(),
        reference_declaration=reference_declaration,
        task_contract_snapshot=({} if model_task_plan is None else model_task_plan.task_contract.to_dict()),
        task_instance_snapshot=({} if model_task_plan is None else model_task_plan.task_instance.to_dict()),
        model_task_plan_snapshot=({} if model_task_plan is None else model_task_plan.to_dict()),
        task_execution_plan=({} if model_task_plan is None else model_task_plan.task_execution_plan.to_dict()),
        model_task_plan=model_task_plan,
        encoding_context_id=encoding_context_id,
        mapping_policy_id=mapping_policy_id,
        state_preparation_policy_id=state_preparation_policy_id,
        ansatz_policy_id=ansatz_policy_id,
        measurement_policy_id=measurement_policy_id,
        reference_policy_id=reference_policy_id,
        controller_id=controller_id,
        scientific_fingerprint=scientific_fingerprint,
        acceptance_certificate=acceptance_certificate,
        run_controls=_runtime_controls(request_payload),
        request_summary=_request_summary(request_payload),
    )
    realization.validate_bridge()
    return realization


def resolve_request_to_quantum_realization(request: Mapping[str, Any]) -> QuantumRealizationArtifact:
    """Resolve a request through the model × task architecture.

    The same normalized request is used for TaskInstance validation and for
    model-policy metadata, preventing mapping/verification controls from
    leaking into the TaskContract.
    """
    from .model_task_resolver import resolve_model_task_request
    from .request_boundaries import normalize_request_boundaries

    bounded_request = normalize_request_boundaries(request)
    model_task_plan = resolve_model_task_request(bounded_request)
    if not model_task_plan.capability_report.may_enter_runtime:
        raise ModelContractError(
            "Model × task request is not executable: "
            + "; ".join(model_task_plan.capability_report.reasons)
        )
    realization = build_quantum_realization(
        model_task_plan.model_plan,
        request_metadata=bounded_request,
        model_task_plan=model_task_plan,
    )
    return realization

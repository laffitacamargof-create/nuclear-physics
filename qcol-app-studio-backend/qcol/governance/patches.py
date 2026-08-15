"""Machine-readable Phase B request-patch allowlist.

WP13 does not implement an advisor.  It defines the only request fields a
future deterministic advisor may propose, validates a candidate patch, and
returns a structured hypothesis report without mutating any scientific truth.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping, Sequence

from qcol.mapping_policies import CheckStatus, DecisionStatus
from qcol.realization_policies.base import contract_fingerprint, json_contract_value

from .contracts import (
    AllowedRequestPatchContract,
    RequestPatchCandidate,
    RequestPatchValidationReport,
)
from .enums import PatchOperation, PatchValueType


PATCH_REGISTRY_ID = "qcol.phase_b.allowed_request_patches.v1"
PATCH_REGISTRY_VERSION = "1.0.0"

JW_GROUND_VARIANT = "realization.general_spin_orbital.ground_state.jw.wp11.v1"
PAIR_ONE_VARIANT = "realization.reduced_pairing.one_pair.pair_mapping.v1"
PAIR_MULTI_VARIANT = "realization.reduced_pairing.multi_pair.pair_mapping.v1"
OSCILLATOR_VARIANT = "realization.nuclear.oscillator.hard_core.one_quantum.ground_state_energy.default.v1"
CUSTOM_GUIDED_VARIANT = "realization.custom.occupation_coupling.one_excitation.ground_state_energy.default.v1"
CUSTOM_QUBIT_VARIANT = "realization.custom.qubit_hamiltonian.ground_state_energy.default.v1"
JW_ANALYSIS_VARIANT = "realization.general_spin_orbital.mapping_analysis.jw.v1"
BK_ANALYSIS_VARIANT = "realization.general_spin_orbital.mapping_analysis.bk.v1"

EXECUTION_VARIANTS = (
    JW_GROUND_VARIANT,
    PAIR_ONE_VARIANT,
    PAIR_MULTI_VARIANT,
    OSCILLATOR_VARIANT,
    CUSTOM_GUIDED_VARIANT,
    CUSTOM_QUBIT_VARIANT,
)
OPTIMIZER_VARIANTS = EXECUTION_VARIANTS
ANALYSIS_VARIANTS = (JW_ANALYSIS_VARIANT, BK_ANALYSIS_VARIANT)

FORBIDDEN_FIELD_PATHS = (
    "/acceptance_abs_floor",
    "/sector_leakage_floor",
    "/reference",
    "/reference_policy",
    "/verification",
    "/verification_thresholds",
    "/evidence",
    "/problem_artifact",
    "/run_result",
    "/mapping_id",
)


def build_allowed_request_patch_contracts() -> tuple[AllowedRequestPatchContract, ...]:
    common_execution = EXECUTION_VARIANTS
    common_tasks = ("ground_state_energy",)
    return (
        AllowedRequestPatchContract(
            patch_rule_id="advisor.patch.shots.v1",
            field_path="/shots",
            operation=PatchOperation.REPLACE,
            applies_to_variant_ids=common_execution,
            applies_to_task_ids=common_tasks,
            value_type=PatchValueType.INTEGER,
            minimum=256,
            maximum=32768,
            reason_codes=("REDUCE_SAMPLING_UNCERTAINTY", "COMPARE_SHOT_BUDGET"),
            description=(
                "Propose a new per-group shot count. This changes sampling precision only; "
                "it does not alter the scientific acceptance threshold."
            ),
        ),
        AllowedRequestPatchContract(
            patch_rule_id="advisor.patch.final_shots.v1",
            field_path="/final_shots",
            operation=PatchOperation.REPLACE,
            applies_to_variant_ids=common_execution,
            applies_to_task_ids=common_tasks,
            value_type=PatchValueType.INTEGER,
            minimum=256,
            maximum=65536,
            reason_codes=("REDUCE_FINAL_ESTIMATE_UNCERTAINTY",),
            description="Propose a final-evaluation shot count for a new run.",
        ),
        AllowedRequestPatchContract(
            patch_rule_id="advisor.patch.max_evaluations.v1",
            field_path="/max_evaluations",
            operation=PatchOperation.REPLACE,
            applies_to_variant_ids=OPTIMIZER_VARIANTS,
            applies_to_task_ids=common_tasks,
            value_type=PatchValueType.INTEGER,
            minimum=1,
            maximum=500,
            reason_codes=("EXTEND_OPTIMIZER_BUDGET", "REDUCE_OPTIMIZER_BUDGET"),
            description=(
                "Propose a bounded optimizer-evaluation budget. The controller remains the "
                "existing external optimizer loop."
            ),
        ),
        AllowedRequestPatchContract(
            patch_rule_id="advisor.patch.energy_tolerance.v1",
            field_path="/energy_tolerance",
            operation=PatchOperation.REPLACE,
            applies_to_variant_ids=OPTIMIZER_VARIANTS,
            applies_to_task_ids=common_tasks,
            value_type=PatchValueType.NUMBER,
            minimum=1e-6,
            maximum=0.1,
            reason_codes=("ADJUST_OPTIMIZER_STOPPING_RULE",),
            description=(
                "Propose an optimizer stopping tolerance. This is not a scientific "
                "verification or acceptance threshold."
            ),
        ),
        AllowedRequestPatchContract(
            patch_rule_id="advisor.patch.seed.v1",
            field_path="/seed",
            operation=PatchOperation.REPLACE,
            applies_to_variant_ids=common_execution,
            applies_to_task_ids=common_tasks,
            value_type=PatchValueType.INTEGER,
            minimum=0,
            maximum=2147483647,
            reason_codes=("REPEAT_WITH_NEW_SEED", "CHECK_SEED_STABILITY"),
            description="Propose a reproducibility or seed-stability rerun.",
        ),
        AllowedRequestPatchContract(
            patch_rule_id="advisor.patch.warm_start.v1",
            field_path="/initial_parameters",
            operation=PatchOperation.REPLACE,
            applies_to_variant_ids=OPTIMIZER_VARIANTS,
            applies_to_task_ids=common_tasks,
            value_type=PatchValueType.VECTOR_NUMBER,
            source_constraints=(
                "source must be previous_run.final_parameters",
                "source run must have the same resolved realization fingerprint",
            ),
            forbidden_sources=(
                "exact_reference",
                "exact_eigenvector",
                "reference_amplitudes",
                "classical_ground_state_vector",
            ),
            preconditions=(
                "source_run_id is present",
                "same_variant_fingerprint is true",
            ),
            reason_codes=("WARM_START_FROM_PREVIOUS_RUN",),
            description=(
                "Propose a warm start from the final parameters of a previous run of the "
                "same realization. Exact-reference amplitudes are forbidden."
            ),
        ),
        AllowedRequestPatchContract(
            patch_rule_id="advisor.patch.jw_ansatz_layers.v1",
            field_path="/parameters/ansatz_layers",
            operation=PatchOperation.REPLACE,
            applies_to_variant_ids=(JW_GROUND_VARIANT,),
            applies_to_task_ids=common_tasks,
            value_type=PatchValueType.INTEGER,
            minimum=1,
            maximum=2,
            preconditions=(
                "mapping policy remains jordan_wigner.spin_orbital.v1",
                "ansatz family remains jw.ansatz.mapped_fermionic_swap_network.v1",
            ),
            reason_codes=("COMPARE_ACCEPTED_ANSATZ_DEPTH",),
            description=(
                "Propose one or two accepted WP11 ansatz layers. The new request must be "
                "resolved and rerun; the previous acceptance evidence is not reused as run evidence."
            ),
        ),
        AllowedRequestPatchContract(
            patch_rule_id="advisor.patch.mapping_analysis_candidates.v1",
            field_path="/task_parameters/mapping_ids",
            operation=PatchOperation.REPLACE,
            applies_to_variant_ids=ANALYSIS_VARIANTS,
            applies_to_task_ids=("mapping_analysis",),
            value_type=PatchValueType.VECTOR_TOKEN,
            allowed_values=("jordan_wigner.v1", "bravyi_kitaev.v1"),
            reason_codes=("COMPARE_MAPPING_RESOURCES",),
            description=(
                "Propose a non-empty subset of mappings already verified for mapping analysis. "
                "This is analysis-only and is not a ground-state execution recommendation."
            ),
        ),
    )


def public_allowed_request_patch_registry() -> dict[str, Any]:
    contracts = [item.to_dict() for item in build_allowed_request_patch_contracts()]
    payload: dict[str, Any] = {
        "schema_version": "qcol-allowed-request-patch-registry/1.0",
        "registry_id": PATCH_REGISTRY_ID,
        "registry_version": PATCH_REGISTRY_VERSION,
        "contracts": contracts,
        "forbidden_field_paths": list(FORBIDDEN_FIELD_PATHS),
        "guardrails": {
            "hypothesis_only": True,
            "user_approval_required": True,
            "same_pipeline_required": True,
            "resolver_rerun_required": True,
            "verification_retains_final_authority": True,
            "problem_artifact_mutation_allowed": False,
            "evidence_mutation_allowed": False,
            "verification_mutation_allowed": False,
            "exact_reference_parameter_leakage_allowed": False,
            "bk_ground_state_mapping_patch_allowed": False,
        },
    }
    payload["fingerprint"] = contract_fingerprint(payload)
    return json_contract_value(payload)


def allowed_request_patch_registry_fingerprint() -> str:
    return str(public_allowed_request_patch_registry()["fingerprint"])


def _report(
    candidate: RequestPatchCandidate,
    *,
    status: CheckStatus,
    decision: DecisionStatus,
    code: str,
    message: str,
    matched_rule: AllowedRequestPatchContract | None,
    evidence: Mapping[str, Any],
    suggested_action: str | None,
) -> RequestPatchValidationReport:
    report_seed = {
        "patch_id": candidate.patch_id,
        "field_path": candidate.field_path,
        "target_variant_id": candidate.target_variant_id,
        "code": code,
        "matched_rule_id": None if matched_rule is None else matched_rule.patch_rule_id,
    }
    return RequestPatchValidationReport(
        report_id=f"patch-report-{contract_fingerprint(report_seed)[:16]}",
        patch_id=candidate.patch_id,
        status=status,
        decision=decision,
        code=code,
        message=message,
        matched_rule_id=None if matched_rule is None else matched_rule.patch_rule_id,
        evidence=evidence,
        suggested_action=suggested_action,
        requires_user_approval=True if matched_rule is None else matched_rule.requires_user_approval,
        requires_resolver_rerun=True if matched_rule is None else matched_rule.requires_resolver_rerun,
        requires_pipeline_rerun=True if matched_rule is None else matched_rule.requires_pipeline_rerun,
        requires_new_evidence=True if matched_rule is None else matched_rule.requires_new_evidence,
        mutation_performed=False,
        hypothesis_only=True,
    )


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _validate_value(rule: AllowedRequestPatchContract, value: Any) -> tuple[bool, str | None]:
    if rule.value_type is PatchValueType.INTEGER:
        if not isinstance(value, int) or isinstance(value, bool):
            return False, "The proposed value must be an integer."
        numeric = value
    elif rule.value_type is PatchValueType.NUMBER:
        if not _is_number(value):
            return False, "The proposed value must be numeric."
        numeric = float(value)
    elif rule.value_type is PatchValueType.VECTOR_NUMBER:
        if not isinstance(value, (list, tuple)) or not value:
            return False, "The proposed value must be a non-empty numeric vector."
        if not all(_is_number(item) for item in value):
            return False, "Every initial-parameter value must be numeric."
        return True, None
    elif rule.value_type is PatchValueType.VECTOR_TOKEN:
        if not isinstance(value, (list, tuple)) or not value:
            return False, "The proposed value must be a non-empty token vector."
        if not all(isinstance(item, str) and item for item in value):
            return False, "Every proposed mapping ID must be a non-empty string."
        allowed = set(rule.allowed_values)
        if any(item not in allowed for item in value):
            return False, "The mapping-analysis patch contains an unverified mapping ID."
        if len(set(value)) != len(value):
            return False, "The mapping-analysis patch contains duplicate mapping IDs."
        return True, None
    else:  # pragma: no cover - future enum extension guard
        return False, "Unsupported patch value type."

    if rule.minimum is not None and numeric < rule.minimum:
        return False, f"The proposed value is below the declared minimum {rule.minimum}."
    if rule.maximum is not None and numeric > rule.maximum:
        return False, f"The proposed value exceeds the declared maximum {rule.maximum}."
    if rule.allowed_values and value not in rule.allowed_values:
        return False, "The proposed value is not in the declared allowlist."
    return True, None


def validate_advisor_request_patch(
    candidate: RequestPatchCandidate | Mapping[str, Any],
) -> RequestPatchValidationReport:
    if not isinstance(candidate, RequestPatchCandidate):
        candidate = RequestPatchCandidate(
            patch_id=str(candidate.get("patch_id", "advisor-patch")),
            target_variant_id=str(candidate["target_variant_id"]),
            task_id=str(candidate["task_id"]),
            field_path=str(candidate["field_path"]),
            operation=PatchOperation(str(candidate.get("operation", "replace"))),
            proposed_value=candidate.get("proposed_value"),
            source=str(candidate.get("source", "deterministic_advisor")),
            source_run_id=(
                None if candidate.get("source_run_id") is None else str(candidate["source_run_id"])
            ),
            same_variant_fingerprint=(
                None
                if candidate.get("same_variant_fingerprint") is None
                else bool(candidate["same_variant_fingerprint"])
            ),
        )

    if candidate.field_path in FORBIDDEN_FIELD_PATHS:
        return _report(
            candidate,
            status=CheckStatus.FAIL,
            decision=DecisionStatus.REJECT,
            code="ADVISOR_PATCH_FIELD_FORBIDDEN",
            message=(
                "The proposed field is part of scientific truth, verification, acceptance, "
                "or an unsupported mapping decision and cannot be patched by the Advisor."
            ),
            matched_rule=None,
            evidence={"field_path": candidate.field_path},
            suggested_action="Report the limitation; do not mutate the recorded scientific contract.",
        )

    rule = next(
        (
            item
            for item in build_allowed_request_patch_contracts()
            if item.field_path == candidate.field_path
            and item.operation is candidate.operation
        ),
        None,
    )
    if rule is None:
        return _report(
            candidate,
            status=CheckStatus.FAIL,
            decision=DecisionStatus.REJECT,
            code="ADVISOR_PATCH_NOT_ALLOWLISTED",
            message="No exact versioned request-patch rule allows this field and operation.",
            matched_rule=None,
            evidence={"field_path": candidate.field_path, "operation": candidate.operation.value},
            suggested_action="Use a published allow-listed field or return a no-patch recommendation.",
        )

    if (
        candidate.target_variant_id not in rule.applies_to_variant_ids
        or candidate.task_id not in rule.applies_to_task_ids
    ):
        return _report(
            candidate,
            status=CheckStatus.FAIL,
            decision=DecisionStatus.REJECT,
            code="ADVISOR_PATCH_TARGET_UNSUPPORTED",
            message="The patch rule does not apply to the declared realization variant and task.",
            matched_rule=rule,
            evidence={
                "target_variant_id": candidate.target_variant_id,
                "task_id": candidate.task_id,
                "allowed_variants": list(rule.applies_to_variant_ids),
                "allowed_tasks": list(rule.applies_to_task_ids),
            },
            suggested_action="Resolve a supported variant before proposing this patch.",
        )

    source_lower = candidate.source.lower()
    if any(item.lower() in source_lower for item in rule.forbidden_sources):
        return _report(
            candidate,
            status=CheckStatus.FAIL,
            decision=DecisionStatus.REJECT,
            code="ADVISOR_PATCH_SOURCE_FORBIDDEN",
            message="The proposed patch source is forbidden because it would contaminate verification.",
            matched_rule=rule,
            evidence={"source": candidate.source, "forbidden_sources": list(rule.forbidden_sources)},
            suggested_action="Use only a prior run of the same accepted realization as a warm-start source.",
        )

    if rule.patch_rule_id == "advisor.patch.warm_start.v1":
        if candidate.source != "previous_run.final_parameters":
            return _report(
                candidate,
                status=CheckStatus.FAIL,
                decision=DecisionStatus.REJECT,
                code="ADVISOR_PATCH_SOURCE_FORBIDDEN",
                message="Warm starts must come from previous_run.final_parameters.",
                matched_rule=rule,
                evidence={"source": candidate.source},
                suggested_action="Select a previous QCOL run of the same realization.",
            )
        if candidate.source_run_id is None or candidate.same_variant_fingerprint is not True:
            return _report(
                candidate,
                status=CheckStatus.FAIL,
                decision=DecisionStatus.REJECT,
                code="ADVISOR_PATCH_REQUIRES_SAME_VARIANT",
                message=(
                    "A warm-start patch requires a source run ID and an exact match of the "
                    "resolved realization fingerprint."
                ),
                matched_rule=rule,
                evidence={
                    "source_run_id": candidate.source_run_id,
                    "same_variant_fingerprint": candidate.same_variant_fingerprint,
                },
                suggested_action="Use parameters from a prior run with the same resolved variant fingerprint.",
            )

    value_valid, value_error = _validate_value(rule, candidate.proposed_value)
    if not value_valid:
        return _report(
            candidate,
            status=CheckStatus.FAIL,
            decision=DecisionStatus.REJECT,
            code="ADVISOR_PATCH_VALUE_INVALID",
            message=str(value_error),
            matched_rule=rule,
            evidence={"proposed_value": json_contract_value(candidate.proposed_value)},
            suggested_action="Choose a value inside the exact published patch rule.",
        )

    return _report(
        candidate,
        status=CheckStatus.PASS,
        decision=DecisionStatus.ACCEPT,
        code="ADVISOR_PATCH_ALLOWED",
        message=(
            "The patch is an allow-listed executable hypothesis. It remains unverified until "
            "the user approves it and the candidate is resolved and rerun through QCOL."
        ),
        matched_rule=rule,
        evidence={
            "field_path": candidate.field_path,
            "target_variant_id": candidate.target_variant_id,
            "task_id": candidate.task_id,
            "reason_codes": list(rule.reason_codes),
            "same_pipeline_required": True,
            "verification_final_authority": True,
        },
        suggested_action="Request user approval, then create a new run through the same pipeline.",
    )


def validate_allowed_request_patch_registry() -> dict[str, bool]:
    registry = public_allowed_request_patch_registry()
    rules = build_allowed_request_patch_contracts()
    fields = [item.field_path for item in rules]
    return {
        "registry_is_strict_json": json_contract_value(registry) == registry,
        "rule_ids_are_unique": len({item.patch_rule_id for item in rules}) == len(rules),
        "field_operation_pairs_are_unique": len({(item.field_path, item.operation.value) for item in rules}) == len(rules),
        "all_require_user_approval": all(item.requires_user_approval for item in rules),
        "all_require_resolver_rerun": all(item.requires_resolver_rerun for item in rules),
        "all_require_pipeline_rerun": all(item.requires_pipeline_rerun for item in rules),
        "no_truth_mutation": all(
            not item.may_mutate_problem_artifact
            and not item.may_mutate_evidence
            and not item.may_mutate_verification
            for item in rules
        ),
        "verification_fields_forbidden": all(path in FORBIDDEN_FIELD_PATHS for path in (
            "/acceptance_abs_floor",
            "/sector_leakage_floor",
            "/verification",
            "/evidence",
        )),
        "bk_ground_state_mapping_patch_not_allowed": "/mapping_id" not in fields,
        "warm_start_blocks_reference_leakage": any(
            item.patch_rule_id == "advisor.patch.warm_start.v1"
            and "exact_reference" in item.forbidden_sources
            for item in rules
        ),
        "mapping_analysis_patch_is_analysis_only": any(
            item.patch_rule_id == "advisor.patch.mapping_analysis_candidates.v1"
            and item.applies_to_task_ids == ("mapping_analysis",)
            for item in rules
        ),
    }


__all__ = [
    "PATCH_REGISTRY_ID",
    "PATCH_REGISTRY_VERSION",
    "FORBIDDEN_FIELD_PATHS",
    "JW_GROUND_VARIANT",
    "build_allowed_request_patch_contracts",
    "public_allowed_request_patch_registry",
    "allowed_request_patch_registry_fingerprint",
    "validate_advisor_request_patch",
    "validate_allowed_request_patch_registry",
]

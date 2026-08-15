"""Uncertainty-aware, evidence-preserving Phase C run comparison."""
from __future__ import annotations

import math
from typing import Any, Mapping, Optional

from qcol.realization_policies.base import contract_fingerprint, json_contract_value
from .contracts import ComparisonDecisionRecord, MetricComparison, RunComparison
from .enums import ComparisonKind, ComparisonOutcome, MetricDirection, MetricJudgment
from .policies import DECLARED_METRICS_POLICY_ID, MAPPING_RESOURCE_POLICY_ID, get_comparison_policy

PIPELINE_ENTRYPOINT = "qcol.orchestrator.run_pipeline"
DEFAULT_SIGMA = 3.0
DEFAULT_NUMERICAL_FLOOR = 1e-12


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _first(*values: Any, default: Any = None) -> Any:
    for value in values:
        if value is not None and value != "":
            return value
    return default


def _number(value: Any) -> Optional[float]:
    if isinstance(value, bool) or value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _get(payload: Mapping[str, Any], *path: str, default: Any = None) -> Any:
    current: Any = payload
    for key in path:
        if not isinstance(current, Mapping) or key not in current:
            return default
        current = current[key]
    return current


def _result(snapshot: Mapping[str, Any]) -> Mapping[str, Any]:
    return _mapping(snapshot.get("result"))


def _request(snapshot: Mapping[str, Any]) -> Mapping[str, Any]:
    return _mapping(snapshot.get("request"))


def _artifact(snapshot: Mapping[str, Any]) -> Mapping[str, Any]:
    return _mapping(snapshot.get("artifact"))


def _model_id(snapshot: Mapping[str, Any]) -> str:
    result, request, artifact = _result(snapshot), _request(snapshot), _artifact(snapshot)
    return str(_first(
        artifact.get("model_id"), request.get("model_id"),
        _get(result, "model_task_plan", "model_plan", "model_contract_id"),
        default="unknown.model",
    ))


def _task_id(snapshot: Mapping[str, Any]) -> str:
    result, request = _result(snapshot), _request(snapshot)
    return str(_first(result.get("task_id"), request.get("task_id"), default="ground_state_energy"))


def _evidence_schema(snapshot: Mapping[str, Any]) -> str:
    result = _result(snapshot)
    return str(_first(
        snapshot.get("evidence_schema"), result.get("evidence_schema"),
        _get(result, "evidence", "schema_version"),
        default="qcol-pipeline-evidence/1.0",
    ))


def _verification(snapshot: Mapping[str, Any]) -> Mapping[str, Any]:
    return _mapping(_result(snapshot).get("verification"))


def _verification_status(snapshot: Mapping[str, Any]) -> str:
    result = _result(snapshot)
    verification = _verification(snapshot)
    return str(_first(
        verification.get("scientific_status"), verification.get("status"),
        result.get("status"), snapshot.get("status"), default="unknown",
    )).upper()


def _sector_leakage(snapshot: Mapping[str, Any]) -> Optional[float]:
    verification = _verification(snapshot)
    return _number(_first(
        verification.get("sector_leakage"),
        _get(verification, "sector_diagnostics", "sector_leakage"),
        _result(snapshot).get("sector_leakage"),
    ))


def _sector_threshold(snapshot: Mapping[str, Any]) -> Optional[float]:
    verification, request = _verification(snapshot), _request(snapshot)
    return _number(_first(
        verification.get("sector_leakage_threshold"), request.get("sector_leakage_floor"),
        default=0.0,
    ))


def _evidence_complete(snapshot: Mapping[str, Any]) -> bool:
    result = _result(snapshot)
    value = _first(
        snapshot.get("evidence_available"), result.get("evidence_complete"),
        _get(result, "verification", "evidence_complete"), default=False,
    )
    return bool(value)


def _metric(snapshot: Mapping[str, Any], metric_id: str) -> Optional[float]:
    result, request, artifact, verification = _result(snapshot), _request(snapshot), _artifact(snapshot), _verification(snapshot)
    sources: dict[str, tuple[Any, ...]] = {
        "absolute_error": (verification.get("absolute_error"), result.get("absolute_error")),
        "standard_error": (result.get("standard_error"), verification.get("standard_error")),
        "reconstructed_energy": (result.get("reconstructed_energy"), result.get("energy")),
        "shots": (result.get("shots_per_group"), request.get("shots")),
        "qubits": (artifact.get("n_qubits"), result.get("n_qubits")),
        "circuit_depth": (result.get("circuit_depth"), _get(result, "resource_report", "circuit_depth")),
        "two_qubit_cost": (result.get("two_qubit_cost"), result.get("two_qubit_gate_count"), _get(result, "resource_report", "two_qubit_cost")),
        "runtime_seconds": (result.get("runtime_seconds"), result.get("wall_time_seconds")),
    }
    if metric_id == "optimizer_converged":
        value = result.get("optimizer_converged")
        return 1.0 if value is True else 0.0 if value is False else None
    for value in sources.get(metric_id, (result.get(metric_id),)):
        number = _number(value)
        if number is not None:
            return number
    return None


def _metric_comparison(
    metric_id: str,
    label: str,
    baseline_value: Optional[float],
    candidate_value: Optional[float],
    *,
    direction: MetricDirection,
    threshold: Optional[float],
    baseline_ref: str,
    candidate_ref: str,
) -> MetricComparison:
    if baseline_value is None or candidate_value is None:
        return MetricComparison(
            metric_id=metric_id, label=label,
            baseline_value=baseline_value, candidate_value=candidate_value, delta=None,
            direction=direction, judgment=MetricJudgment.MISSING,
            uncertainty_threshold=threshold,
            rationale="At least one run does not publish this metric; no preference is inferred.",
            evidence_refs=(baseline_ref, candidate_ref),
        )
    delta = candidate_value - baseline_value
    tol = max(0.0, float(threshold or 0.0))
    if abs(delta) <= tol:
        judgment = MetricJudgment.EQUIVALENT
        rationale = f"The observed delta {delta:.12g} is inside the declared comparison tolerance {tol:.12g}."
    elif direction is MetricDirection.LOWER_IS_BETTER:
        judgment = MetricJudgment.IMPROVED if delta < 0 else MetricJudgment.WORSENED
        rationale = "The candidate is lower on a lower-is-better metric." if delta < 0 else "The candidate is higher on a lower-is-better metric."
    elif direction is MetricDirection.HIGHER_IS_BETTER:
        judgment = MetricJudgment.IMPROVED if delta > 0 else MetricJudgment.WORSENED
        rationale = "The candidate is higher on a higher-is-better metric." if delta > 0 else "The candidate is lower on a higher-is-better metric."
    else:
        judgment = MetricJudgment.EQUIVALENT if delta == 0 else MetricJudgment.MIXED
        rationale = "The values are equal." if delta == 0 else "The values differ, but the policy does not rank them."
    return MetricComparison(
        metric_id=metric_id, label=label,
        baseline_value=baseline_value, candidate_value=candidate_value, delta=delta,
        direction=direction, judgment=judgment,
        uncertainty_threshold=tol,
        rationale=rationale,
        evidence_refs=(baseline_ref, candidate_ref),
    )


def _candidate_patch_path(candidate_snapshot: Mapping[str, Any]) -> str:
    phase_c = _mapping(candidate_snapshot.get("phase_c"))
    return str(_first(phase_c.get("patch_field"), candidate_snapshot.get("patch_field"), default=""))


def _comparison_identity(baseline: Mapping[str, Any], candidate: Mapping[str, Any]) -> tuple[bool, str, str]:
    baseline_cell = (_model_id(baseline), _task_id(baseline))
    candidate_cell = (_model_id(candidate), _task_id(candidate))
    return baseline_cell == candidate_cell, " × ".join(baseline_cell), " × ".join(candidate_cell)


def _execution_outcome(
    baseline: Mapping[str, Any], candidate: Mapping[str, Any], *, numerical_floor: float, sigma_multiplier: float
) -> tuple[ComparisonOutcome, str, list[MetricComparison], list[str], list[str]]:
    warnings: list[str] = []
    missing: list[str] = []
    metrics: list[MetricComparison] = []

    baseline_status = _verification_status(baseline)
    candidate_status = _verification_status(candidate)
    candidate_terminal = str(candidate.get("status", "")).lower()
    if candidate_terminal in {"failed", "cancelled"}:
        return ComparisonOutcome.REJECT, f"The candidate run ended as {candidate_terminal}; the baseline is retained.", metrics, warnings, missing
    if candidate_status not in {"PASS", "ACCEPTANCE_VERIFIED", "VERIFIED"}:
        return ComparisonOutcome.REJECT, f"The candidate did not pass its own declared verification ({candidate_status}).", metrics, warnings, missing
    if not _evidence_complete(candidate):
        return ComparisonOutcome.REJECT, "The candidate has no complete evidence archive; it cannot replace the baseline.", metrics, warnings, missing

    leakage = _sector_leakage(candidate)
    leakage_limit = _sector_threshold(candidate)
    if leakage is None:
        missing.append("sector_leakage")
    elif leakage_limit is not None and leakage > leakage_limit:
        return ComparisonOutcome.REJECT, f"Candidate sector leakage {leakage:.6g} exceeds its declared threshold {leakage_limit:.6g}.", metrics, warnings, missing

    b_se, c_se = _metric(baseline, "standard_error"), _metric(candidate, "standard_error")
    uncertainty_threshold = None
    if b_se is not None and c_se is not None:
        uncertainty_threshold = max(numerical_floor, sigma_multiplier * math.sqrt(b_se*b_se + c_se*c_se))
    patch_path = _candidate_patch_path(candidate)
    primary = "standard_error" if patch_path in {"/shots", "/final_shots"} else "absolute_error"
    primary_label = "Standard error" if primary == "standard_error" else "Absolute error against each run's declared reference"
    primary_threshold = numerical_floor if primary == "standard_error" else uncertainty_threshold
    primary_metric = _metric_comparison(
        primary, primary_label, _metric(baseline, primary), _metric(candidate, primary),
        direction=MetricDirection.LOWER_IS_BETTER, threshold=primary_threshold,
        baseline_ref=f"/runs/{baseline.get('run_id')}/result/{primary}",
        candidate_ref=f"/runs/{candidate.get('run_id')}/result/{primary}",
    )
    metrics.append(primary_metric)

    # Supporting metrics are always recorded but never override verification.
    for metric_id, label, direction in (
        ("standard_error", "Standard error", MetricDirection.LOWER_IS_BETTER),
        ("absolute_error", "Absolute error", MetricDirection.LOWER_IS_BETTER),
        ("shots", "Shots per group", MetricDirection.INFORMATION_ONLY),
        ("qubits", "Qubit count", MetricDirection.LOWER_IS_BETTER),
        ("circuit_depth", "Circuit depth", MetricDirection.LOWER_IS_BETTER),
        ("two_qubit_cost", "Two-qubit cost", MetricDirection.LOWER_IS_BETTER),
        ("runtime_seconds", "Runtime", MetricDirection.LOWER_IS_BETTER),
    ):
        if metric_id == primary:
            continue
        metrics.append(_metric_comparison(
            metric_id, label, _metric(baseline, metric_id), _metric(candidate, metric_id),
            direction=direction,
            threshold=uncertainty_threshold if metric_id == "absolute_error" else numerical_floor,
            baseline_ref=f"/runs/{baseline.get('run_id')}/result/{metric_id}",
            candidate_ref=f"/runs/{candidate.get('run_id')}/result/{metric_id}",
        ))

    if primary_metric.judgment is MetricJudgment.IMPROVED:
        return ComparisonOutcome.ADOPT, f"The candidate passed its own verification and improved the declared primary metric ({primary_label}) beyond the comparison threshold.", metrics, warnings, missing
    if primary_metric.judgment is MetricJudgment.WORSENED:
        return ComparisonOutcome.REJECT, f"The candidate passed verification but worsened the declared primary metric ({primary_label}) beyond the comparison threshold.", metrics, warnings, missing
    if primary_metric.judgment is MetricJudgment.MISSING:
        missing.append(primary)
        return ComparisonOutcome.INCONCLUSIVE, f"The candidate passed verification, but the declared primary metric ({primary_label}) is missing from one or both runs.", metrics, warnings, missing
    return ComparisonOutcome.INCONCLUSIVE, f"The candidate passed verification, but the observed change in {primary_label} is not distinguishable under the declared uncertainty policy.", metrics, warnings, missing


def _mapping_entries(snapshot: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    result = _result(snapshot)
    task_result = _mapping(result.get("task_result"))
    entries = task_result.get("entries")
    if isinstance(entries, list):
        return [item for item in entries if isinstance(item, Mapping)]
    direct = snapshot.get("mapping_resource")
    return [direct] if isinstance(direct, Mapping) else []


def _mapping_entry(snapshot: Mapping[str, Any]) -> Mapping[str, Any]:
    entries = _mapping_entries(snapshot)
    if not entries:
        return {}
    selected = _mapping(snapshot.get("phase_c")).get("selected_mapping_id")
    if selected:
        for entry in entries:
            if str(entry.get("mapping_id")) == str(selected):
                return entry
    return entries[0]


def _resource_number(entry: Mapping[str, Any], metric_id: str) -> Optional[float]:
    resource = _mapping(entry.get("resource_report"))
    aliases = {
        "qubits": ("n_qubits", "qubits"),
        "pauli_terms": ("pauli_term_count", "n_pauli_terms", "terms"),
        "maximum_pauli_weight": ("maximum_pauli_weight", "max_pauli_weight", "max_weight"),
        "mean_pauli_weight": ("coefficient_weighted_mean_pauli_weight", "mean_pauli_weight", "weighted_mean"),
        "grouping_estimate": ("qwc_group_estimate", "measurement_group_estimate", "qwc_groups"),
        "transformation_time": ("transformation_time_seconds", "transform_time_seconds"),
    }
    for key in aliases[metric_id]:
        value = _number(_first(resource.get(key), entry.get(key)))
        if value is not None:
            return value
    return None


def _transform_verified(snapshot: Mapping[str, Any]) -> bool:
    result = _result(snapshot)
    entry = _mapping_entry(snapshot)
    return bool(_first(
        entry.get("transform_verified"), entry.get("verified"),
        _get(result, "task_result", "all_transforms_verified"),
        default=False,
    ))


def _mapping_outcome(baseline: Mapping[str, Any], candidate: Mapping[str, Any]) -> tuple[ComparisonOutcome, str, list[MetricComparison], list[str], list[str]]:
    metrics: list[MetricComparison] = []
    warnings = ["Resource preference is not a physical-accuracy ranking; both transforms must represent the same operator under the declared assumptions."]
    missing: list[str] = []
    if not _transform_verified(baseline) or not _transform_verified(candidate):
        return ComparisonOutcome.REJECT, "At least one mapping-analysis run failed its own transformation/equivalence verification.", metrics, warnings, missing
    improved = worsened = 0
    for metric_id, label in (
        ("qubits", "Qubit count"),
        ("pauli_terms", "Pauli-term count"),
        ("maximum_pauli_weight", "Maximum Pauli weight"),
        ("mean_pauli_weight", "Coefficient-weighted mean Pauli weight"),
        ("grouping_estimate", "QWC grouping estimate"),
        ("transformation_time", "Transformation time"),
    ):
        metric = _metric_comparison(
            metric_id, label,
            _resource_number(_mapping_entry(baseline), metric_id),
            _resource_number(_mapping_entry(candidate), metric_id),
            direction=MetricDirection.LOWER_IS_BETTER, threshold=DEFAULT_NUMERICAL_FLOOR,
            baseline_ref=f"/runs/{baseline.get('run_id')}/result/task_result/entries/resource_report/{metric_id}",
            candidate_ref=f"/runs/{candidate.get('run_id')}/result/task_result/entries/resource_report/{metric_id}",
        )
        metrics.append(metric)
        if metric.judgment is MetricJudgment.IMPROVED:
            improved += 1
        elif metric.judgment is MetricJudgment.WORSENED:
            worsened += 1
        elif metric.judgment is MetricJudgment.MISSING:
            missing.append(metric_id)
    if missing:
        return ComparisonOutcome.INCONCLUSIVE, "Both mappings passed equivalence, but required resource metrics are missing; no preference is inferred.", metrics, warnings, missing
    if improved and not worsened:
        return ComparisonOutcome.ADOPT, "The candidate mapping passes equivalence and is no worse on every declared resource metric, with at least one strict improvement.", metrics, warnings, missing
    if worsened and not improved:
        return ComparisonOutcome.REJECT, "The candidate mapping passes equivalence but is no better on any declared resource metric and is worse on at least one.", metrics, warnings, missing
    return ComparisonOutcome.INCONCLUSIVE, "Both mappings pass equivalence, but the resource trade-off is mixed or equivalent under the declared policy.", metrics, warnings, missing


def compare_runs(
    *,
    baseline: Mapping[str, Any],
    candidate: Mapping[str, Any],
    policy: str = DECLARED_METRICS_POLICY_ID,
    explicit_user_approval: bool,
    numerical_floor: float = DEFAULT_NUMERICAL_FLOOR,
    sigma_multiplier: float = DEFAULT_SIGMA,
) -> RunComparison:
    """Compare two terminal public run snapshots under one declared policy."""
    if not explicit_user_approval:
        raise ValueError("Phase C requires explicit user approval before candidate execution and comparison.")
    policy_contract = get_comparison_policy(policy)
    same_cell, baseline_cell, candidate_cell = _comparison_identity(baseline, candidate)
    if not same_cell:
        raise ValueError(f"Run comparison requires the same Model × Task cell; got {baseline_cell!r} and {candidate_cell!r}.")
    baseline_schema = _evidence_schema(baseline)
    candidate_schema = _evidence_schema(candidate)
    if baseline_schema != candidate_schema:
        outcome = ComparisonOutcome.INCONCLUSIVE
        rationale = f"Evidence schemas differ ({baseline_schema} vs {candidate_schema}); the runs are not directly comparable."
        metrics: list[MetricComparison] = []
        warnings = [rationale]
        missing = ["same_evidence_schema"]
    elif policy_contract.comparison_kind is ComparisonKind.MAPPING_ANALYSIS:
        outcome, rationale, metrics, warnings, missing = _mapping_outcome(baseline, candidate)
    else:
        outcome, rationale, metrics, warnings, missing = _execution_outcome(
            baseline, candidate, numerical_floor=numerical_floor, sigma_multiplier=sigma_multiplier,
        )
    baseline_id = str(baseline.get("run_id", "baseline-run"))
    candidate_id = str(candidate.get("run_id", "candidate-run"))
    baseline_request = json_contract_value(dict(_request(baseline)))
    candidate_request = json_contract_value(dict(_request(candidate)))
    seed = {
        "baseline": baseline_id,
        "candidate": candidate_id,
        "policy": policy,
        "outcome": outcome.value,
        "metrics": [item.to_dict() for item in metrics],
    }
    comparison_id = f"comparison-{contract_fingerprint(seed)[:16]}"
    return RunComparison(
        comparison_id=comparison_id,
        comparison_kind=policy_contract.comparison_kind,
        policy_id=policy_contract.policy_id,
        policy_version=policy_contract.policy_version,
        baseline_run_id=baseline_id,
        candidate_run_id=candidate_id,
        baseline_request_fingerprint=contract_fingerprint(baseline_request),
        candidate_request_fingerprint=contract_fingerprint(candidate_request),
        baseline_evidence_schema=baseline_schema,
        candidate_evidence_schema=candidate_schema,
        same_pipeline_entrypoint=PIPELINE_ENTRYPOINT,
        same_model_task_cell=same_cell,
        explicit_user_approval=True,
        metrics=tuple(metrics),
        outcome=outcome,
        rationale=rationale,
        warnings=tuple(warnings),
        missing_metrics=tuple(sorted(set(missing))),
        baseline_verification_status=_verification_status(baseline),
        candidate_verification_status=_verification_status(candidate),
        physical_accuracy_ranking_claimed=False,
        automatic_replacement_performed=False,
        evidence_refs=(
            f"/runs/{baseline_id}/evidence",
            f"/runs/{candidate_id}/evidence",
        ),
    )


def build_decision_record(comparison: RunComparison) -> ComparisonDecisionRecord:
    seed = {"comparison": comparison.comparison_id, "outcome": comparison.outcome.value}
    return ComparisonDecisionRecord(
        decision_id=f"decision-{contract_fingerprint(seed)[:16]}",
        comparison_id=comparison.comparison_id,
        baseline_run_id=comparison.baseline_run_id,
        candidate_run_id=comparison.candidate_run_id,
        outcome=comparison.outcome,
        rationale=comparison.rationale,
        policy_id=comparison.policy_id,
        user_approved_candidate=True,
        automatic_replacement_performed=False,
        recorded_with_both_run_ids=True,
        verification_retains_final_authority=True,
        evidence_refs=comparison.evidence_refs,
    )


__all__ = ["compare_runs", "build_decision_record", "PIPELINE_ENTRYPOINT"]

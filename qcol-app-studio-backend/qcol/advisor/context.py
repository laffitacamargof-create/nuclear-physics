"""Sanitized, frozen Advisor contexts built from public QCOL run payloads.

The context deliberately reads only bounded public views.  Exact eigenvectors,
exact amplitudes, reference-derived parameters, credentials, callables, and
opaque scientific objects are rejected before any rule is evaluated.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable, Mapping, Optional

from qcol.governance.patches import (
    PATCH_REGISTRY_ID,
    allowed_request_patch_registry_fingerprint,
)
from qcol.realization_policies.base import contract_fingerprint, json_contract_value
from qcol.realization_variants import (
    get_model_task_realization_view,
    get_public_realization_variant,
)

from .contracts import AdvisorContext, PreviousRunSummary


FORBIDDEN_CONTEXT_KEYS = {
    "target_state_amplitudes",
    "eigenvectors",
    "eigenvector",
    "reference_state",
    "reference_amplitudes",
    "exact_parameters",
    "exact_theta",
    "exact_eigenvector",
    "classical_ground_state_vector",
    "backend_credentials",
    "api_key",
    "token",
    "password",
    "secret",
    "callable",
    "callable_payload",
    "hamiltonian_payload",
    "ansatz_template",
}


class AdvisorContextError(ValueError):
    pass


def _plain(value: Any) -> Any:
    """Strict public-data copy without scientific objects or MappingProxyType."""
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return _plain(value.to_dict())
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if isinstance(value, (set, frozenset)):
        # Public Advisor payloads should normally be strict JSON already.  If a
        # boundary caller supplies a set, normalize it deterministically rather
        # than inheriting hash-order nondeterminism into fingerprints.
        normalized = [_plain(item) for item in value]
        return sorted(normalized, key=lambda item: repr(item))
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value
    if hasattr(value, "item"):
        try:
            return _plain(value.item())
        except (TypeError, ValueError):
            pass
    if hasattr(value, "tolist"):
        try:
            return _plain(value.tolist())
        except (TypeError, ValueError):
            pass
    raise AdvisorContextError(
        f"Advisor context contains unsupported object {type(value).__module__}.{type(value).__name__}."
    )


def _assert_sanitized(value: Any, *, path: str = "$") -> None:
    if callable(value):
        raise AdvisorContextError(f"Advisor context contains a callable at {path}.")
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key)
            normalized_key = key_text.lower().replace("-", "_").replace(" ", "_")
            forbidden_fragment = any(
                fragment in normalized_key
                for fragment in (
                    "eigenvector",
                    "reference_amplitude",
                    "target_state_amplitude",
                    "reference_derived_parameter",
                    "exact_parameter",
                    "exact_theta",
                    "backend_credential",
                    "api_key",
                    "password",
                    "secret",
                    "callable_payload",
                )
            )
            safe_disclosure_flag = normalized_key in {
                "callable_payload_withheld",
                "credentials_withheld",
            } and isinstance(item, bool) and item is True
            if not safe_disclosure_flag and (normalized_key in FORBIDDEN_CONTEXT_KEYS or forbidden_fragment):
                raise AdvisorContextError(f"Forbidden Advisor field {key_text!r} found at {path}.")
            _assert_sanitized(item, path=f"{path}.{key_text}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _assert_sanitized(item, path=f"{path}[{index}]")


def _get(payload: Mapping[str, Any], *path: str, default: Any = None) -> Any:
    current: Any = payload
    for key in path:
        if not isinstance(current, Mapping) or key not in current:
            return default
        current = current[key]
    return current


def _first(*values: Any, default: Any = None) -> Any:
    for value in values:
        if value is not None and value != "":
            return value
    return default


def _model_id(request: Mapping[str, Any], artifact: Mapping[str, Any], result: Mapping[str, Any]) -> str:
    return str(_first(
        artifact.get("model_id"),
        request.get("model_id"),
        _get(result, "model_task_plan", "model_plan", "model_contract_id"),
        _get(result, "model_task_plan", "model_contract", "model_id"),
        default="unknown.model",
    ))


def _task_id(request: Mapping[str, Any], result: Mapping[str, Any]) -> str:
    return str(_first(result.get("task_id"), request.get("task_id"), default="ground_state_energy"))


def _variant_for(model_id: str, task_id: str, request: Mapping[str, Any]) -> Any:
    explicit = request.get("resolved_variant_id") or request.get("variant_id")
    if explicit:
        return get_public_realization_variant(str(explicit))
    cell = get_model_task_realization_view(model_id, task_id)
    if cell.default_variant_id is None:
        # A non-runnable cell may have no default; use the first public variant for explanation.
        if not cell.variants:
            raise AdvisorContextError(f"No realization variant exists for {model_id} × {task_id}.")
        return cell.variants[0]
    return get_public_realization_variant(cell.default_variant_id)


def _compatibility_report(
    result: Mapping[str, Any],
    variant: Any,
) -> dict[str, Any]:
    plan = result.get("model_task_plan") if isinstance(result.get("model_task_plan"), Mapping) else {}
    capability = {}
    if isinstance(plan, Mapping):
        capability = plan.get("capability_report") or _get(plan, "model_plan", "capability_report", default={}) or {}
    checks = capability.get("checks", []) if isinstance(capability, Mapping) else []
    diagnostics: list[dict[str, Any]] = []
    for item in checks if isinstance(checks, list) else []:
        if not isinstance(item, Mapping):
            continue
        diagnostics.append({
            "check_id": str(item.get("key", item.get("check_id", "unnamed_check"))),
            "status": str(item.get("status", "not_run")),
            "message": str(item.get("message", "")),
            "failure_code": item.get("failure_code") or item.get("code"),
            "details": _plain(item.get("details", {})),
        })
    if variant.failure_code:
        diagnostics.append({
            "check_id": "public_realization_variant",
            "status": "fail" if variant.composition_status == "failed" else "blocked",
            "message": variant.failure_message or "The public realization variant is not executable.",
            "failure_code": variant.failure_code,
            "details": {"variant_id": variant.variant_id},
        })
    return {
        "schema_version": "qcol-advisor-compatibility-view/1.0",
        "overall_status": str(capability.get("overall_status", variant.cell_status)) if isinstance(capability, Mapping) else variant.cell_status,
        "may_enter_runtime": bool(capability.get("may_enter_runtime", variant.runnable)) if isinstance(capability, Mapping) else variant.runnable,
        "status_triplet": {
            "mapper": variant.mapper_status,
            "composition": variant.composition_status,
            "cell": variant.cell_status,
        },
        "diagnostics": diagnostics,
        "source_variant_id": variant.variant_id,
    }


def _sector_leakage(verification: Mapping[str, Any]) -> Any:
    direct = verification.get("sector_leakage")
    if direct is not None:
        return direct
    diagnostics = verification.get("sector_diagnostics")
    if isinstance(diagnostics, Mapping):
        return diagnostics.get("sector_leakage")
    return None


def _resource_report(
    request: Mapping[str, Any],
    artifact: Mapping[str, Any],
    result: Mapping[str, Any],
) -> dict[str, Any]:
    task_result = result.get("task_result") if isinstance(result.get("task_result"), Mapping) else {}
    mapping_entries = task_result.get("entries", []) if isinstance(task_result, Mapping) else []
    mapping_resources = []
    for entry in mapping_entries if isinstance(mapping_entries, list) else []:
        if not isinstance(entry, Mapping):
            continue
        resource = entry.get("resource_report", {})
        mapping_resources.append({
            "mapping_id": entry.get("mapping_id"),
            "resource_report": _plain(resource if isinstance(resource, Mapping) else {}),
        })
    scientific = artifact.get("scientific_context") if isinstance(artifact.get("scientific_context"), Mapping) else {}
    measurement_groups = _first(
        artifact.get("measurement_groups"),
        scientific.get("measurement_groups") if isinstance(scientific, Mapping) else None,
        default=None,
    )
    return {
        "schema_version": "qcol-advisor-resource-view/1.0",
        "n_qubits": artifact.get("n_qubits"),
        "pauli_term_count": _first(artifact.get("pauli_terms"), artifact.get("hamiltonian_term_count")),
        "measurement_group_count": measurement_groups,
        "shots_per_group": result.get("shots_per_group", request.get("shots")),
        "optimizer_evaluations": result.get("optimizer_evaluations"),
        "mapping_resources": mapping_resources,
        "declared_backend": result.get("target_backend", request.get("target_backend")),
        "hardware_submission_performed": bool(result.get("hardware_submission_performed", False)),
    }


def _telemetry(
    request: Mapping[str, Any],
    artifact: Mapping[str, Any],
    result: Mapping[str, Any],
    variant: Any,
) -> dict[str, Any]:
    verification = result.get("verification") if isinstance(result.get("verification"), Mapping) else {}
    parameters = request.get("parameters") if isinstance(request.get("parameters"), Mapping) else {}
    task_parameters = request.get("task_parameters") if isinstance(request.get("task_parameters"), Mapping) else {}
    optimizer_message = str(result.get("optimizer_message", ""))
    current_max = _first(request.get("max_evaluations"), request.get("maximum_evaluations"), default=None)
    mapping_ids = task_parameters.get("mapping_ids")
    if mapping_ids is None:
        mapping_ids = request.get("mapping_ids")
    if mapping_ids is None and result.get("task_id") == "mapping_analysis":
        mapping_ids = [entry.get("mapping_id") for entry in (result.get("task_result", {}).get("entries", []) if isinstance(result.get("task_result"), Mapping) else []) if isinstance(entry, Mapping)]
    telemetry = {
        "result_status": result.get("status"),
        "run_mode": result.get("run_mode"),
        "execution_mode": result.get("execution_mode"),
        "shots_per_group": result.get("shots_per_group", request.get("shots")),
        "final_shots": request.get("final_shots"),
        "seed": result.get("seed", request.get("seed")),
        "optimizer_name": result.get("optimizer_name"),
        "optimizer_converged": result.get("optimizer_converged"),
        "optimizer_message": optimizer_message,
        "optimizer_evaluations": result.get("optimizer_evaluations"),
        "max_evaluations": current_max,
        "optimizer_tolerance": result.get("optimizer_tolerance", request.get("energy_tolerance")),
        "reconstructed_energy": result.get("reconstructed_energy"),
        "standard_error": result.get("standard_error"),
        "absolute_error": verification.get("absolute_error"),
        "acceptance_threshold": verification.get("acceptance_threshold"),
        "sector_leakage": _sector_leakage(verification),
        "sector_leakage_threshold": _first(verification.get("sector_leakage_threshold"), request.get("sector_leakage_floor")),
        "qasm_semantic_fidelity": _get(result, "translation_check", "semantic_check", "unitary_process_fidelity_up_to_global_phase"),
        "ansatz_layers": parameters.get("ansatz_layers"),
        "mapping_ids": mapping_ids or [],
        "parameter_source": result.get("parameter_source"),
        "final_parameters_available": bool(result.get("final_parameters")),
        "variant_runnable": variant.runnable,
        "variant_selectable": variant.selectable,
        "runtime_path": variant.runtime_path,
        "convergence_history_length": len(result.get("convergence_history", [])) if isinstance(result.get("convergence_history"), list) else 0,
        "artifact_n_qubits": artifact.get("n_qubits"),
    }
    return telemetry


def _failure_codes(
    snapshot: Mapping[str, Any],
    compatibility: Mapping[str, Any],
    variant: Any,
) -> tuple[str, ...]:
    codes: set[str] = set()
    if variant.failure_code:
        codes.add(str(variant.failure_code))
    failure = snapshot.get("failure")
    if isinstance(failure, Mapping):
        code = failure.get("error_code") or failure.get("failure_code") or failure.get("code")
        if code:
            codes.add(str(code))
    for item in compatibility.get("diagnostics", []) if isinstance(compatibility, Mapping) else []:
        if isinstance(item, Mapping) and item.get("failure_code"):
            codes.add(str(item["failure_code"]))
    return tuple(sorted(codes))


def _previous_run_summary(previous_snapshot: Mapping[str, Any] | None, target_variant: Any) -> Optional[PreviousRunSummary]:
    if not isinstance(previous_snapshot, Mapping):
        return None
    result = previous_snapshot.get("result") if isinstance(previous_snapshot.get("result"), Mapping) else {}
    request = previous_snapshot.get("request") if isinstance(previous_snapshot.get("request"), Mapping) else {}
    artifact = previous_snapshot.get("artifact") if isinstance(previous_snapshot.get("artifact"), Mapping) else {}
    if not result:
        return None
    source = str(result.get("parameter_source", ""))
    if any(token in source.lower() for token in ("exact", "fixture", "reference")):
        return None
    values = result.get("final_parameters")
    if not isinstance(values, list) or not values or not all(isinstance(item, (int, float)) for item in values):
        return None
    model_id = _model_id(request, artifact, result)
    task_id = _task_id(request, result)
    try:
        previous_variant = _variant_for(model_id, task_id, request)
    except (KeyError, AdvisorContextError):
        return None
    if previous_variant.variant_id != target_variant.variant_id:
        return None
    previous_fp = previous_variant.evidence_fingerprint or previous_variant.variant_id
    target_fp = target_variant.evidence_fingerprint or target_variant.variant_id
    if previous_fp != target_fp:
        return None
    return PreviousRunSummary(
        run_id=str(previous_snapshot.get("run_id", result.get("run_id", "previous-run"))),
        variant_id=previous_variant.variant_id,
        variant_fingerprint=str(previous_fp),
        final_parameters=tuple(float(item) for item in values),
        status=str(result.get("status", previous_snapshot.get("status", "unknown"))),
        parameter_source=source or "previous_run.final_parameters",
    )


def build_advisor_context_from_run_payload(
    snapshot: Mapping[str, Any],
    *,
    previous_snapshot: Mapping[str, Any] | None = None,
) -> AdvisorContext:
    """Build one immutable AdvisorContext from a public run snapshot."""
    raw = _plain(snapshot)
    _assert_sanitized(raw)
    request = raw.get("request") if isinstance(raw.get("request"), Mapping) else {}
    artifact = raw.get("artifact") if isinstance(raw.get("artifact"), Mapping) else {}
    result = raw.get("result") if isinstance(raw.get("result"), Mapping) else {}
    run_id = str(_first(raw.get("run_id"), result.get("run_id"), default="advisor-fixture-run"))
    model_id = _model_id(request, artifact, result)
    task_id = _task_id(request, result)
    variant = _variant_for(model_id, task_id, request)
    compatibility = _compatibility_report(result, variant)
    resource = _resource_report(request, artifact, result)
    telemetry = _telemetry(request, artifact, result, variant)
    evidence_fingerprint = variant.evidence_fingerprint or variant.variant_id
    result_status = str(result.get("status", raw.get("status", "unknown")))
    if variant.cell_status == "acceptance_verified" and result_status in {"PASS", "pass", "completed"}:
        freshness = "current"
    elif "ACCEPTANCE_EVIDENCE_STALE" in _failure_codes(raw, compatibility, variant):
        freshness = "stale"
    elif variant.evidence_fingerprint:
        freshness = "unknown"
    else:
        freshness = "not_applicable" if task_id == "mapping_analysis" else "missing"
    acceptance = {
        "schema_version": "qcol-advisor-acceptance-evidence-view/1.0",
        "freshness": freshness,
        "fingerprint": evidence_fingerprint,
        "cell_status": variant.cell_status,
        "evidence_archive_available": bool(raw.get("evidence_available", False)),
        "evidence_url": raw.get("evidence_url"),
    }
    request_view = deepcopy(dict(request))
    # Parameters derived from exact acceptance fixtures are not visible to the Advisor.
    parameter_source = str(result.get("parameter_source", ""))
    if any(token in parameter_source.lower() for token in ("exact", "fixture", "reference")):
        request_view.pop("initial_parameters", None)
    source_seed = {
        "run_id": run_id,
        "request": request_view,
        "artifact": artifact,
        "result": result,
        "variant_id": variant.variant_id,
    }
    source_fingerprint = contract_fingerprint(json_contract_value(source_seed))
    variant_fingerprint = str(variant.evidence_fingerprint or contract_fingerprint(variant.to_dict()))
    context_seed = {
        "run_id": run_id,
        "variant_id": variant.variant_id,
        "source_snapshot_fingerprint": source_fingerprint,
    }
    context_id = f"advisor-context-{contract_fingerprint(context_seed)[:16]}"
    previous = _previous_run_summary(previous_snapshot, variant)
    context = AdvisorContext(
        context_id=context_id,
        run_id=run_id,
        model_id=model_id,
        task_id=task_id,
        variant_id=variant.variant_id,
        variant_fingerprint=variant_fingerprint,
        status_triplet={
            "mapper": variant.mapper_status,
            "composition": variant.composition_status,
            "cell": variant.cell_status,
        },
        compatibility_report=compatibility,
        acceptance_evidence=acceptance,
        resource_report=resource,
        telemetry=telemetry,
        request_view=request_view,
        stable_failure_codes=_failure_codes(raw, compatibility, variant),
        allowed_patch_registry_id=PATCH_REGISTRY_ID,
        allowed_patch_registry_fingerprint=allowed_request_patch_registry_fingerprint(),
        source_snapshot_fingerprint=source_fingerprint,
        previous_run=previous,
    )
    _assert_sanitized(context.to_dict())
    return context


def _scenario_snapshot(name: str) -> tuple[dict[str, Any], Optional[dict[str, Any]]]:
    """Dependency-light deterministic scenarios used by catalogs and tests."""
    base_request = {
        "model_id": "fermion.general_spin_orbital",
        "task_id": "ground_state_energy",
        "run_mode": "external_vqe",
        "shots": 1024,
        "final_shots": 4096,
        "max_evaluations": 24,
        "energy_tolerance": 0.002,
        "seed": 42,
        "parameters": {"ansatz_layers": 1},
    }
    base_result = {
        "run_id": f"run-{name}",
        "status": "PASS",
        "task_id": "ground_state_energy",
        "run_mode": "external_vqe",
        "shots_per_group": 1024,
        "seed": 42,
        "optimizer_name": "COBYLA",
        "optimizer_converged": True,
        "optimizer_message": "Optimization terminated successfully.",
        "optimizer_evaluations": 18,
        "optimizer_tolerance": 0.002,
        "parameter_source": "declared_initialization",
        "final_parameters": [0.1, -0.2, 0.3, -0.4],
        "convergence_history": [{"evaluation": 1, "energy": 0.4}, {"evaluation": 18, "energy": 0.25}],
        "reconstructed_energy": 0.2501,
        "standard_error": 0.003,
        "verification": {
            "status": "PASS",
            "absolute_error": 0.002,
            "acceptance_threshold": 0.02,
            "sector_diagnostics": {"applicable": True, "sector_leakage": 0.0},
        },
        "translation_check": {"semantic_check": {"unitary_process_fidelity_up_to_global_phase": 1.0}},
        "model_task_plan": {
            "capability_report": {
                "overall_status": "verified",
                "may_enter_runtime": True,
                "checks": [
                    {"key": "model_mapping.domain", "status": "pass", "message": "Model and mapping domain agree."},
                    {"key": "mapping_ansatz.generator_semantics", "status": "pass", "message": "Mapped-generator equivalence passed."},
                ],
            }
        },
    }
    snapshot = {
        "run_id": f"run-{name}",
        "status": "completed",
        "request": deepcopy(base_request),
        "artifact": {
            "model_id": "fermion.general_spin_orbital",
            "n_qubits": 4,
            "pauli_terms": 15,
            "measurement_groups": 5,
            "units": {"energy": "MeV"},
        },
        "result": deepcopy(base_result),
        "evidence_available": True,
        "evidence_url": f"/runs/run-{name}/evidence",
    }
    previous = None
    if name == "accepted_jw_high_uncertainty":
        snapshot["result"]["standard_error"] = 0.012
        snapshot["result"]["verification"]["absolute_error"] = 0.018
    elif name == "optimizer_budget_exhausted":
        snapshot["result"]["status"] = "REVIEW"
        snapshot["result"]["optimizer_converged"] = False
        snapshot["result"]["optimizer_message"] = "Maximum number of function evaluations has been exceeded."
        snapshot["result"]["optimizer_evaluations"] = 24
    elif name == "historical_jw":
        snapshot["request"]["resolved_variant_id"] = "realization.general_spin_orbital.ground_state.jw.bare_exchange.historical.v1"
        snapshot["result"]["status"] = "FAIL"
    elif name == "bk_ground_state":
        snapshot["request"]["resolved_variant_id"] = "realization.general_spin_orbital.ground_state.bk.default.v1"
        snapshot["result"]["status"] = "REVIEW"
    elif name == "pair_mapping":
        snapshot["request"] = {
            "model_id": "nuclear.reduced_pairing.one_pair",
            "task_id": "ground_state_energy",
            "shots": 1024,
            "max_evaluations": 24,
            "seed": 42,
        }
        snapshot["artifact"]["model_id"] = "nuclear.reduced_pairing.one_pair"
    elif name == "mapping_analysis_single_mapping":
        snapshot["request"] = {
            "model_id": "fermion.general_spin_orbital",
            "task_id": "mapping_analysis",
            "task_parameters": {"mapping_ids": ["jordan_wigner.v1"]},
        }
        snapshot["result"].update({
            "status": "PASS",
            "task_id": "mapping_analysis",
            "run_mode": "mapping_analysis",
            "shots_per_group": 0,
            "optimizer_name": None,
            "optimizer_converged": True,
            "optimizer_evaluations": 1,
            "task_result": {
                "all_transforms_verified": True,
                "entries": [{
                    "mapping_id": "jordan_wigner.v1",
                    "resource_report": {"n_qubits": 4, "pauli_term_count": 15, "maximum_pauli_weight": 3},
                }],
            },
        })
    elif name == "stale_evidence":
        snapshot["failure"] = {"error_code": "ACCEPTANCE_EVIDENCE_STALE"}
        snapshot["result"]["status"] = "REVIEW"
    elif name == "sector_leakage":
        snapshot["result"]["status"] = "REVIEW"
        snapshot["result"]["verification"]["sector_diagnostics"]["sector_leakage"] = 0.06
        snapshot["result"]["verification"]["sector_leakage_threshold"] = 1e-8
    elif name == "warm_start":
        snapshot["result"]["status"] = "REVIEW"
        snapshot["result"]["optimizer_converged"] = False
        previous = deepcopy(snapshot)
        previous["run_id"] = "run-prior-compatible"
        previous["result"]["run_id"] = "run-prior-compatible"
        previous["result"]["status"] = "PASS"
        previous["result"]["parameter_source"] = "declared_initialization"
        previous["result"]["final_parameters"] = [0.2, -0.1, 0.25, -0.35]
    elif name == "clean_pass":
        pass
    else:
        raise KeyError(name)
    return snapshot, previous


SCENARIO_IDS = (
    "accepted_jw_high_uncertainty",
    "optimizer_budget_exhausted",
    "historical_jw",
    "bk_ground_state",
    "pair_mapping",
    "mapping_analysis_single_mapping",
    "stale_evidence",
    "sector_leakage",
    "warm_start",
    "clean_pass",
)


def build_advisor_context_fixture(name: str) -> AdvisorContext:
    snapshot, previous = _scenario_snapshot(name)
    return build_advisor_context_from_run_payload(snapshot, previous_snapshot=previous)


__all__ = [
    "FORBIDDEN_CONTEXT_KEYS",
    "AdvisorContextError",
    "SCENARIO_IDS",
    "build_advisor_context_from_run_payload",
    "build_advisor_context_fixture",
]

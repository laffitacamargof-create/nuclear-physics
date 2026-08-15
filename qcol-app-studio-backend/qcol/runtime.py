"""One green-column energy evaluation and the gray verification branch."""
from __future__ import annotations

import json
import math
from typing import Any, Dict, List, Mapping, Optional, Sequence

import cirq
from cirq.contrib.qasm_import import circuit_from_qasm
import numpy as np

from .config import REFERENCE_POLICY
from .control import CancellationToken
from .contracts import ProblemArtifact
from .events import EventCallback, PipelineEvent
from .measurement import (
    circuit_metrics,
    format_pauli_term,
    reconstruct_group,
)
from .execution import get_execution_adapter
from .modeling import bind_parameters
from .translation import (
    add_measurement_basis_and_readout,
    compare_circuit_semantics,
    export_openqasm2,
    ordered_imported_qubits,
    translate_measurement_free_circuit,
    validate_and_unroll_openqasm2,
)


def _emit(
    callback: Optional[EventCallback],
    *,
    run_id: str,
    stage: str,
    status: str,
    message: str,
    iteration: Optional[int] = None,
    progress_current: Optional[int] = None,
    progress_total: Optional[int] = None,
    metrics: Optional[Dict[str, Any]] = None,
    artifact_refs: Optional[List[str]] = None,
) -> None:
    if callback is None:
        return
    callback(PipelineEvent(
        run_id=run_id,
        stage=stage,
        status=status,  # type: ignore[arg-type]
        message=message,
        iteration=iteration,
        progress_current=progress_current,
        progress_total=progress_total,
        metrics={} if metrics is None else metrics,
        artifact_refs=[] if artifact_refs is None else artifact_refs,
    ))


def _ideal_particle_sector_diagnostics(
    artifact: ProblemArtifact,
    bound_circuit: cirq.Circuit,
    ordered_qubits: Sequence[cirq.Qid],
    execution_adapter: Any,
) -> Dict[str, Any]:
    """Inspect fixed-particle support without pretending it is sampled evidence.

    The diagnostic is available only for mappings whose public metadata states
    that computational-basis popcount is the physical particle number.  It is
    calculated from the ideal local statevector and is therefore labelled as a
    deterministic integrity diagnostic, not a hardware measurement.
    """
    realization = dict(artifact.provenance.get("quantum_realization", {}))
    mapping_metadata = dict(realization.get("mapping_metadata", {}))
    target = artifact.target_sector.get("particle_number")
    if not mapping_metadata.get("raw_popcount_is_particle_number", False):
        return {
            "applicable": False,
            "reason": "The selected mapping does not equate raw qubit popcount with particle number.",
            "source": "not_computed",
        }
    if target is None:
        return {
            "applicable": False,
            "reason": "No target particle-number sector was declared.",
            "source": "not_computed",
        }

    state = execution_adapter.simulate_statevector(
        bound_circuit,
        qubit_order=tuple(ordered_qubits),
    )
    probabilities = np.abs(np.asarray(state, dtype=np.complex128)) ** 2
    target = int(target)
    in_sector_probability = float(sum(
        probability
        for basis_index, probability in enumerate(probabilities)
        if int(basis_index).bit_count() == target
    ))
    in_sector_probability = min(1.0, max(0.0, in_sector_probability))
    leakage = max(0.0, 1.0 - in_sector_probability)
    return {
        "applicable": True,
        "target_particle_number": target,
        "in_sector_probability": in_sector_probability,
        "sector_leakage": leakage,
        "source": "ideal_local_statevector_integrity_diagnostic",
        "measured_on_backend": False,
        "mapping_id": mapping_metadata.get("mapping_plugin_id", artifact.mapping),
        "raw_popcount_is_particle_number": True,
        "claim_boundary": (
            "This checks the ideal bound circuit against the declared JW particle-number "
            "sector. It is not a sampled hardware observable and is not state fidelity."
        ),
    }




def _problem_artifact(realization_or_artifact):
    """Return the executable compatibility projection carried by the IR."""
    if hasattr(realization_or_artifact, "problem_artifact"):
        return realization_or_artifact.problem_artifact
    return realization_or_artifact


def execute_artifact_parameter_point(
    realization_or_artifact,
    parameter_values: Sequence[float],
    *,
    shots: int,
    seed: int,
    strict_semantic_checks: bool,
    retain_artifacts: bool,
    run_id: str = "standalone",
    iteration: Optional[int] = None,
    evaluation_role: str = "energy_evaluation",
    event_callback: Optional[EventCallback] = None,
    cancellation_token: Optional[CancellationToken] = None,
    execution_adapter_id: str = "execution.local_cirq.v1",
) -> Dict[str, Any]:
    """Run one complete green-column energy evaluation for one theta vector.

    The returned object is UI-neutral.  Live UI updates are emitted separately as
    PipelineEvent objects, so the deterministic scientific path remains reusable
    from tests, notebooks, and future backend adapters.
    """
    artifact = _problem_artifact(realization_or_artifact)

    def check_cancel(location: str) -> None:
        if cancellation_token is not None:
            cancellation_token.raise_if_cancelled(location=location)

    check_cancel("before_energy_evaluation")
    artifact.validate()
    if shots <= 0:
        raise ValueError("shots must be positive.")
    execution_adapter = get_execution_adapter(execution_adapter_id)
    values = np.asarray(parameter_values, dtype=float)
    if values.shape != (len(artifact.parameter_symbols),):
        raise ValueError(
            f"Expected {len(artifact.parameter_symbols)} parameters, got {values.shape}."
        )
    if not np.all(np.isfinite(values)):
        raise ValueError("The parameter vector contains non-finite values.")

    _emit(
        event_callback,
        run_id=run_id,
        stage="bind",
        status="running",
        message="Binding the optimizer parameter vector to the ansatz template.",
        iteration=iteration,
        metrics={"role": evaluation_role, "parameter_count": int(values.size)},
    )
    ordered_qubits = tuple(cirq.LineQubit.range(artifact.n_qubits))
    bound = bind_parameters(
        artifact.ansatz_template,
        artifact.parameter_symbols,
        values,
    )
    check_cancel("after_parameter_binding")
    _emit(
        event_callback,
        run_id=run_id,
        stage="bind",
        status="completed",
        message=f"Bound {values.size} parameter(s) numerically.",
        iteration=iteration,
        metrics={
            "role": evaluation_role,
            "parameter_count": int(values.size),
            "theta_preview": [float(value) for value in values[:6]],
        },
        artifact_refs=["bound_ansatz"],
    )

    _emit(
        event_callback,
        run_id=run_id,
        stage="translation",
        status="running",
        message="Checking the measurement-free OpenQASM 2 round trip.",
        iteration=iteration,
        metrics={"role": evaluation_role},
    )
    check_cancel("before_measurement_free_translation")
    translation_check = translate_measurement_free_circuit(
        bound,
        ordered_qubits,
        strict_semantic_check=strict_semantic_checks,
    )
    if strict_semantic_checks and not translation_check["passed"]:
        raise AssertionError(
            f"{artifact.method}/{artifact.problem}: measurement-free QASM2 "
            "semantic equivalence failed. Diagnostics: "
            + json.dumps(
                {
                    "raw": translation_check["raw_roundtrip"],
                    "unrolled": translation_check["unrolled_roundtrip"],
                    "imported_qubit_order": translation_check["imported_qubit_order"],
                },
                indent=2,
            )
        )

    check_cancel("after_measurement_free_translation")
    groups = list(artifact.measurement_plan["groups"])
    n_groups = len(groups)
    _emit(
        event_callback,
        run_id=run_id,
        stage="measurement",
        status="running",
        message=f"Preparing {n_groups} Pauli measurement group(s).",
        iteration=iteration,
        progress_current=0,
        progress_total=max(1, n_groups),
        metrics={
            "role": evaluation_role,
            "group_count": n_groups,
            "pauli_term_count": sum(len(group["terms"]) for group in groups),
        },
    )

    total_energy = float(artifact.measurement_plan["identity_coefficient"])
    total_variance_of_mean = 0.0
    term_expectations: Dict[str, float] = {}
    records: List[Dict[str, Any]] = []
    iteration_summaries: List[Dict[str, Any]] = []

    if n_groups == 0:
        _emit(
            event_callback,
            run_id=run_id,
            stage="execute",
            status="completed",
            message="No sampled measurement circuit is required for an identity-only Hamiltonian.",
            iteration=iteration,
            progress_current=1,
            progress_total=1,
            metrics={"role": evaluation_role, "shots_per_group": 0, "total_shots": 0},
        )
        _emit(
            event_callback,
            run_id=run_id,
            stage="evidence",
            status="completed",
            message="The identity coefficient is retained directly; no count record was produced.",
            iteration=iteration,
            progress_current=1,
            progress_total=1,
            metrics={"role": evaluation_role, "group_count": 0, "total_shots": 0, "full_artifacts_retained": bool(retain_artifacts)},
            artifact_refs=["identity_coefficient"],
        )

    for offset, group in enumerate(groups):
        current = offset + 1
        check_cancel(f"before_measurement_group_{current}")
        logical_circuit = add_measurement_basis_and_readout(
            bound, group, ordered_qubits
        )
        _emit(
            event_callback,
            run_id=run_id,
            stage="measurement",
            status="running",
            message=f"Built measurement group {current}/{n_groups}.",
            iteration=iteration,
            progress_current=current,
            progress_total=max(1, n_groups),
            metrics={
                "role": evaluation_role,
                "group_id": int(group["group_id"]),
                "basis": {str(k): v for k, v in sorted(group["basis"].items())},
                "terms_in_group": len(group["terms"]),
            },
        )

        raw_qasm2 = export_openqasm2(logical_circuit, ordered_qubits)
        validation = validate_and_unroll_openqasm2(raw_qasm2)
        if validation["num_qubits"] != artifact.n_qubits:
            raise AssertionError(
                "QASM2 translation changed the declared qubit-register size."
            )
        _emit(
            event_callback,
            run_id=run_id,
            stage="translation",
            status="running",
            message=f"Validated and unrolled QASM2 group {current}/{n_groups}.",
            iteration=iteration,
            progress_current=current,
            progress_total=max(1, n_groups),
            metrics={
                "role": evaluation_role,
                "group_id": int(group["group_id"]),
                "validated": bool(validation["validated"]),
                "depth_before_unroll": validation["depth_before_unroll"],
                "depth_after_unroll": validation["depth_after_unroll"],
            },
        )

        raw_imported = circuit_from_qasm(raw_qasm2)
        executable_circuit = circuit_from_qasm(validation["unrolled_qasm"])
        raw_order = ordered_imported_qubits(raw_imported, artifact.n_qubits)
        executable_order = ordered_imported_qubits(
            executable_circuit, artifact.n_qubits
        )

        if strict_semantic_checks:
            raw_semantics = compare_circuit_semantics(
                logical_circuit,
                raw_imported,
                ordered_qubits,
                raw_order,
                ignore_terminal_measurements=True,
            )
            unrolled_semantics = compare_circuit_semantics(
                logical_circuit,
                executable_circuit,
                ordered_qubits,
                executable_order,
                ignore_terminal_measurements=True,
            )
            performed = bool(
                raw_semantics.get("performed") and unrolled_semantics.get("performed")
            )
            semantic_passed = (
                bool(raw_semantics.get("passed") and unrolled_semantics.get("passed"))
                if performed
                else True
            )
        else:
            raw_semantics = {
                "performed": False,
                "passed": None,
                "reason": "intermediate optimizer evaluation: exact unitary check deferred",
            }
            unrolled_semantics = dict(raw_semantics)
            semantic_passed = True

        if not semantic_passed:
            raise AssertionError(
                f"{artifact.method}/{artifact.problem}, measurement group "
                f"{group['group_id']}: QASM2 semantic equivalence failed."
            )

        _emit(
            event_callback,
            run_id=run_id,
            stage="execute",
            status="running",
            message=f"Executing measurement group {current}/{n_groups} on the local simulator.",
            iteration=iteration,
            progress_current=current - 1,
            progress_total=max(1, n_groups),
            metrics={
                "role": evaluation_role,
                "group_id": int(group["group_id"]),
                "shots_per_group": int(shots),
                "execution_mode": "local_simulator",
            },
        )
        check_cancel(f"before_simulator_group_{current}")
        adapter_result = execution_adapter.run_measurement(
            executable_circuit,
            repetitions=shots,
            seed=seed + offset,
        )
        check_cancel(f"after_simulator_group_{current}")
        bits = adapter_result.measurement_bits
        imported_order = adapter_result.imported_qubit_order
        group_counts = dict(adapter_result.counts)
        reconstructed = reconstruct_group(group, bits)

        total_energy += reconstructed["energy_contribution"]
        total_variance_of_mean += reconstructed["variance_of_mean"]
        term_expectations.update(reconstructed["term_expectations"])

        top_counts = sorted(
            group_counts.items(), key=lambda item: (-int(item[1]), item[0])
        )[:4]
        compact_summary = {
            "group_id": int(group["group_id"]),
            "shots": int(shots),
            "distinct_outcomes": len(group_counts),
            "top_counts": [{"bitstring": key, "count": int(value)} for key, value in top_counts],
            "energy_contribution": float(reconstructed["energy_contribution"]),
            "variance_of_mean": float(reconstructed["variance_of_mean"]),
            "pyqasm_validated": bool(validation["validated"]),
        }
        iteration_summaries.append(compact_summary)

        record: Dict[str, Any] = {
            "group_id": int(group["group_id"]),
            "basis": {
                str(index): pauli
                for index, pauli in sorted(group["basis"].items())
            },
            "pauli_terms": [
                {
                    "term": format_pauli_term(tuple(item["term"])),
                    "coefficient": float(item["coefficient"]),
                }
                for item in group["terms"]
            ],
            "pyqasm_validated": bool(validation["validated"]),
            "pyqasm_depth_before_unroll": validation["depth_before_unroll"],
            "pyqasm_depth_after_unroll": validation["depth_after_unroll"],
            "logical_metrics": circuit_metrics(logical_circuit),
            "roundtrip_metrics": circuit_metrics(executable_circuit),
            "imported_qubit_order": list(imported_order),
            "execution_adapter": adapter_result.adapter.to_dict(),
            "canonical_execution_result": adapter_result.public_dict(
                include_counts=retain_artifacts
            ),
            "qasm_semantic_check": {
                "performed": strict_semantic_checks,
                "passed": semantic_passed,
                "raw_roundtrip": raw_semantics,
                "unrolled_roundtrip": unrolled_semantics,
            },
            "term_expectations": reconstructed["term_expectations"],
            "energy_contribution": reconstructed["energy_contribution"],
            "variance_of_mean": reconstructed["variance_of_mean"],
            "evidence_summary": compact_summary,
        }
        if retain_artifacts:
            record.update({
                "raw_qasm2": raw_qasm2,
                "unrolled_qasm2": validation["unrolled_qasm"],
                "counts": group_counts,
            })
        records.append(record)

        _emit(
            event_callback,
            run_id=run_id,
            stage="execute",
            status="running" if current < n_groups else "completed",
            message=(
                f"Executed group {current}/{n_groups}; {shots} shots returned."
                if current < n_groups
                else f"All {n_groups} measurement groups executed."
            ),
            iteration=iteration,
            progress_current=current,
            progress_total=max(1, n_groups),
            metrics={
                "role": evaluation_role,
                "group_id": int(group["group_id"]),
                "shots_per_group": int(shots),
                "total_shots_so_far": int(current * shots),
                "top_counts": compact_summary["top_counts"],
            },
        )
        _emit(
            event_callback,
            run_id=run_id,
            stage="evidence",
            status="running" if current < n_groups else "completed",
            message=(
                f"Preserved a compact evidence summary for group {current}/{n_groups}."
                if current < n_groups
                else "Iteration evidence summary completed. Full artifacts are retained for the best/final point."
            ),
            iteration=iteration,
            progress_current=current,
            progress_total=max(1, n_groups),
            metrics={
                "role": evaluation_role,
                "groups_summarized": current,
                "group_count": n_groups,
                "full_artifacts_retained": bool(retain_artifacts),
                "total_shots": int(current * shots),
            },
            artifact_refs=(
                ["raw_qasm2", "unrolled_qasm2", "counts"]
                if retain_artifacts
                else ["iteration_summary"]
            ),
        )

    _emit(
        event_callback,
        run_id=run_id,
        stage="measurement",
        status="completed",
        message=f"Measurement plan completed across {n_groups} group(s).",
        iteration=iteration,
        progress_current=max(1, n_groups),
        progress_total=max(1, n_groups),
        metrics={"role": evaluation_role, "group_count": n_groups},
    )
    _emit(
        event_callback,
        run_id=run_id,
        stage="translation",
        status="completed",
        message="All bound measurement circuits passed OpenQASM 2 / PyQASM processing.",
        iteration=iteration,
        progress_current=max(1, n_groups),
        progress_total=max(1, n_groups),
        metrics={
            "role": evaluation_role,
            "validated_groups": n_groups,
            "semantic_check_performed": bool(strict_semantic_checks),
        },
        artifact_refs=["qasm2_bound_measurement_circuits"],
    )

    clean_translation = {
        key: value
        for key, value in translation_check.items()
        if key not in {"executable_circuit", "executable_qubit_order"}
    }
    if not retain_artifacts:
        clean_translation.pop("raw_qasm2", None)
        clean_translation.pop("unrolled_qasm2", None)

    check_cancel("before_energy_reconstruction")
    standard_error = float(math.sqrt(total_variance_of_mean))
    sector_diagnostics = _ideal_particle_sector_diagnostics(
        artifact, bound, ordered_qubits, execution_adapter
    )
    evidence_summary = {
        "iteration": iteration,
        "role": evaluation_role,
        "group_count": n_groups,
        "shots_per_group": int(shots),
        "total_shots": int(n_groups * shots),
        "validated_groups": sum(bool(item["pyqasm_validated"]) for item in records),
        "full_artifacts_retained": bool(retain_artifacts),
        "groups": iteration_summaries,
        "sector_diagnostics": sector_diagnostics,
        "execution_adapter": execution_adapter.descriptor.to_dict(),
    }
    _emit(
        event_callback,
        run_id=run_id,
        stage="reconstruct",
        status="completed",
        message="Reconstructed the Hamiltonian expectation from retained measurement records.",
        iteration=iteration,
        metrics={
            "role": evaluation_role,
            "energy": float(total_energy),
            "standard_error": standard_error,
            "term_expectation_count": len(term_expectations),
            "sector_leakage": sector_diagnostics.get("sector_leakage"),
            "sector_diagnostic_source": sector_diagnostics.get("source"),
        },
        artifact_refs=["term_expectations", "energy_estimate"],
    )

    return {
        "parameter_values": [float(value) for value in values],
        "shots_per_group": int(shots),
        "seed": int(seed),
        "translation_check": clean_translation,
        "term_expectations": term_expectations,
        "energy": float(total_energy),
        "standard_error": standard_error,
        "records": records,
        "evidence_summary": evidence_summary,
        "sector_diagnostics": sector_diagnostics,
        "execution_adapter": execution_adapter.descriptor.to_dict(),
    }


def verify_reconstructed_result(
    artifact: ProblemArtifact,
    execution: Mapping[str, Any],
    request: Mapping[str, Any],
) -> Dict[str, Any]:
    """Gray branch: compare the final reconstructed value to the declared reference."""
    reference = artifact.exact_reference
    translation = execution["translation_check"]
    structural_checks = {
        **{name: bool(value) for name, value in artifact.validation_checks.items()},
        "artifact_contract_valid": True,
        "measurement_free_qasm_validated": bool(translation["validated"]),
        "measurement_free_semantic_check": bool(translation.get("passed", False)),
        "all_qasm_groups_validated": all(
            bool(record["pyqasm_validated"]) for record in execution["records"]
        ),
        "all_final_measurement_semantic_checks": all(
            bool(record.get("qasm_semantic_check", {}).get("passed"))
            for record in execution["records"]
        ),
    }
    sector_diagnostics = dict(execution.get("sector_diagnostics", {}))
    sector_leakage_threshold = float(request.get("sector_leakage_floor", 1e-10))
    if sector_diagnostics.get("applicable", False):
        structural_checks["particle_sector_preserved"] = (
            float(sector_diagnostics.get("sector_leakage", 1.0))
            <= sector_leakage_threshold
        )

    if reference is None:
        return {
            "status": "NOT_RUN",
            "reference_policy": REFERENCE_POLICY,
            "structural_checks": structural_checks,
            "reason": (
                "No classical reference was declared for this artifact. The mentor "
                "decision on the production reference policy is still pending."
            ),
            "sector_diagnostics": sector_diagnostics,
            "sector_leakage_threshold": sector_leakage_threshold,
        }

    reference_energy = float(reference["reference_energy"])
    reconstructed_energy = float(execution["energy"])
    standard_error = float(execution["standard_error"])
    absolute_error = abs(reconstructed_energy - reference_energy)
    floor = float(
        request.get(
            "acceptance_abs_floor",
            reference.get("acceptance_abs_floor", 0.05),
        )
    )
    threshold = max(3 * standard_error, floor)
    accepted = all(structural_checks.values()) and absolute_error <= threshold

    return {
        "status": "PASS" if accepted else "REVIEW",
        "reference_policy": REFERENCE_POLICY,
        "structural_checks": structural_checks,
        "reference_kind": reference["kind"],
        "reference_scope": reference["reference_scope"],
        "reference_energy": reference_energy,
        "reconstructed_energy": reconstructed_energy,
        "standard_error": standard_error,
        "absolute_error": absolute_error,
        "acceptance_threshold": threshold,
        "accepted": accepted,
        "sector_diagnostics": sector_diagnostics,
        "sector_leakage_threshold": sector_leakage_threshold,
    }

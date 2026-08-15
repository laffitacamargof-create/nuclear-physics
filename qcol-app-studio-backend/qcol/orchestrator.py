"""Public QCOL pipeline entry points: blocking and live-streaming."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from queue import Queue
from threading import Thread
import traceback
from typing import Any, Callable, Iterator, Mapping, Optional, Tuple
from uuid import uuid4

from .realization import resolve_request_to_quantum_realization
from .config import REFERENCE_POLICY, VERSIONS
from .control import CancellationToken, RunCancelled
from .contracts import ProblemArtifact, RunResult, json_safe
from .events import EventCallback, JourneyState, PipelineEvent, PipelineStreamUpdate
from .failures import (
    PipelineFailure,
    PipelineStageContext,
    build_pipeline_failure,
    format_technical_error_log,
)
from .request_validation import normalize_run_request


@dataclass
class _WorkerArtifact:
    artifact: ProblemArtifact


@dataclass
class _WorkerResult:
    artifact: ProblemArtifact
    result: RunResult


@dataclass
class _WorkerError:
    failure: PipelineFailure
    traceback_text: str

    @property
    def text(self) -> str:
        return format_technical_error_log(self.failure, self.traceback_text)


@dataclass
class _WorkerCancelled:
    message: str
    location: Optional[str] = None


def _run_pipeline_impl(
    request: Mapping[str, Any],
    *,
    run_id: str,
    event_callback: Optional[EventCallback] = None,
    artifact_callback: Optional[Callable[[ProblemArtifact], None]] = None,
    cancellation_token: Optional[CancellationToken] = None,
) -> Tuple[ProblemArtifact, RunResult]:
    """Run one resolved Model × Task cell through the shared services."""
    started = datetime.now(timezone.utc)
    event_log: list[dict[str, Any]] = []

    def check_cancel(location: str) -> None:
        if cancellation_token is not None:
            cancellation_token.raise_if_cancelled(location=location)

    def emit(event: PipelineEvent) -> None:
        event_log.append(event.to_dict())
        if event_callback is not None:
            event_callback(event)

    check_cancel("before_request_validation")
    request = normalize_run_request(request)
    method = str(request.get("method", request.get("model_id", "")))
    task_id = str(request.get("task_id", "ground_state_energy"))

    # Record the user request now, but enforce the backend boundary only after
    # the Model × Task plan is resolved. Analysis-only tasks deliberately have
    # no circuit, shots, simulator, or provider invocation.
    requested_execution_mode = str(request.get("execution_mode", "local_simulator"))
    requested_target_backend = str(request.get("target_backend", "google")).lower()
    execution_mode = requested_execution_mode
    target_backend = requested_target_backend

    emit(PipelineEvent(
        run_id=run_id,
        stage="entrance",
        status="completed",
        message="Captured the declared model route, task, parameters, and execution boundary.",
        metrics={
            "method": method,
            "problem": request.get("problem"),
            "task_id": task_id,
            "declared_execution_mode": requested_execution_mode,
            "declared_target_backend": requested_target_backend,
        },
        artifact_refs=["normalized_request"],
    ))

    emit(PipelineEvent(
        run_id=run_id,
        stage="model",
        status="running",
        message="Resolving the declared physical model and scientific task.",
        metrics={
            "method": method,
            "model_id": request.get("model_id"),
            "task_id": task_id,
            "problem": request.get("problem"),
            "target_backend": requested_target_backend,
            "execution_mode": requested_execution_mode,
        },
    ))
    # Compatibility-safe named boundary retained for Phase A.2 cancellation tests.
    check_cancel("before_model_build")
    check_cancel("before_model_task_resolution")
    realization = resolve_request_to_quantum_realization(request)
    # After this composition-root boundary, downstream code consumes only the
    # canonical QuantumRealizationArtifact.  The original request is never read
    # again and no scientific component is re-selected.
    artifact = realization.problem_artifact
    task_plan = realization.task_plan
    realization.validate_bridge()
    requested_execution_mode = str(
        realization.run_controls.get("execution_mode", requested_execution_mode)
    )
    requested_target_backend = str(
        realization.run_controls.get("target_backend", requested_target_backend)
    ).lower()

    backend_required = realization.backend_execution_required
    if backend_required:
        execution_mode = requested_execution_mode
        target_backend = requested_target_backend
        if execution_mode != "local_simulator":
            raise NotImplementedError(
                "The current release executes circuit tasks on the local Cirq simulator. "
                "IBM/Google/AWS adapters remain the execution seam."
            )
        if target_backend not in {"ibm", "google", "aws"}:
            raise ValueError("target_backend must be ibm, google, or aws for backend-executed tasks.")
    else:
        # Mapping analysis is a deterministic operator task. Normalize its
        # transport metadata instead of pretending that a simulator/backend ran.
        execution_mode = "analysis_only"
        target_backend = "none"

    artifact.validate()
    check_cancel("after_model_task_resolution")
    if artifact_callback is not None:
        artifact_callback(artifact)

    emit(PipelineEvent(
        run_id=run_id,
        stage="model",
        status="completed",
        message="Model and Hamiltonian constructed under the declared contract.",
        metrics={
            "model_id": artifact.model_id,
            "task_id": task_plan.task_contract.task_id,
            "energy_unit": artifact.units.get("energy", "unspecified"),
        },
        artifact_refs=["hamiltonian_payload"],
    ))
    emit(PipelineEvent(
        run_id=run_id,
        stage="artifact",
        status="completed",
        message="QuantumRealizationArtifact and task execution plan validated.",
        metrics={
            "artifact_id": artifact.artifact_id,
            "model_contract_id": task_plan.model_plan.model_contract_id,
            "task_contract_id": task_plan.task_contract.task_id,
            "model_task_cell_status": task_plan.capability_report.cell_status,
            "model_task_capability_status": task_plan.capability_report.overall_status,
            "model_task_plan_id": task_plan.plan_id,
            "controller_policy": task_plan.task_contract.controller_policy_id,
            "controller_structure": task_plan.task_execution_plan.controller_structure,
            "n_qubits": artifact.n_qubits,
            "pauli_terms": len(artifact.hamiltonian_payload.terms),
            "mapping": artifact.mapping,
            "mapping_policy_id": realization.mapping_policy_id,
            "encoding_context_id": realization.encoding_context_id,
            "scientific_fingerprint": realization.scientific_fingerprint,
            "mapping_selection": "automatic_by_model_contract_and_capability_resolver",
            "encoding": artifact.encoding,
            "target_sector": artifact.target_sector,
            "parameter_count": len(artifact.parameter_symbols),
            "measurement_groups": len(artifact.measurement_plan.get("groups", [])),
            "backend_required": backend_required,
            "shots_required": bool(
                task_plan.cell_snapshot.get("resource_envelope", {}).get(
                    "shots_required", backend_required
                )
            ),
            "execution_mode": execution_mode,
        },
        artifact_refs=[
            "hamiltonian_payload",
            "ansatz_template",
            "measurement_plan",
            "model_task_plan",
        ],
    ))
    emit(PipelineEvent(
        run_id=run_id,
        stage="task",
        status="completed",
        message=(
            f"Resolved task {task_plan.task_contract.label!r} with "
            f"{task_plan.task_execution_plan.controller_structure} control."
        ),
        metrics={
            "task_id": task_plan.task_contract.task_id,
            "objective": task_plan.task_contract.objective,
            "execution_plan": task_plan.task_execution_plan.to_dict(),
        },
        artifact_refs=["task_contract", "task_execution_plan"],
    ))

    reference = artifact.exact_reference
    reference_metrics: dict[str, Any] = {
        "task_reference_policy": task_plan.task_contract.reference_policy_id,
        "available": reference is not None,
    }
    if reference is not None:
        reference_metrics.update({
            "reference_kind": reference.get("kind"),
            "reference_scope": reference.get("reference_scope"),
            "reference_energy": reference.get("reference_energy"),
            "observable_reference_available": bool(reference.get("target_state_amplitudes")),
            "full_spectrum_size": len(reference.get("full_spectrum", [])),
            "target_sector_spectrum_size": len(reference.get("target_sector_spectrum", [])),
        })
    emit(PipelineEvent(
        run_id=run_id,
        stage="exact_reference",
        status="completed" if reference is not None else "review",
        message=(
            "Model-specific reference prepared for the selected task."
            if reference is not None
            else "No task-compatible reference is available; verification will be limited."
        ),
        metrics=reference_metrics,
        artifact_refs=["exact_reference"] if reference is not None else [],
    ))

    controller_structure = realization.task_execution.controller_structure
    controller_stage = realization.task_execution.controller_stage
    controller_message = realization.task_execution.controller_message
    emit(PipelineEvent(
        run_id=run_id,
        stage=controller_stage,
        status="running",
        message=controller_message,
        metrics={
            "task_id": task_plan.task_contract.task_id,
            "controller_policy": task_plan.task_contract.controller_policy_id,
        },
        artifact_refs=["task_execution_plan"],
    ))
    check_cancel("before_task_controller")
    outcome = realization.controller(
        realization,
        run_id=run_id,
        event_callback=emit,
        cancellation_token=cancellation_token,
    )
    check_cancel("after_task_controller")
    final_execution = outcome.final_execution

    # Verification remains a distinct post-reconstruction boundary.
    emit(PipelineEvent(
        run_id=run_id,
        stage="verification",
        status="running",
        message="Applying the task-specific reference and acceptance metric.",
        metrics={
            "task_id": task_plan.task_contract.task_id,
            "verification_metric": task_plan.task_contract.verification_metric,
        },
        artifact_refs=["task_verification_policy"],
    ))
    check_cancel("before_verification")
    check_cancel("before_task_verification")
    verification = dict(
        realization.verification_handler(realization, outcome)
    )
    check_cancel("after_task_verification")
    verification_status = str(verification.get("status", "REVIEW"))
    emit(PipelineEvent(
        run_id=run_id,
        stage="verification",
        status="completed" if verification_status == "PASS" else "review",
        message=(
            "The model × task cell satisfies its declared acceptance rule."
            if verification_status == "PASS"
            else "The model × task result remains limited or requires review."
        ),
        metrics={
            "task_id": task_plan.task_contract.task_id,
            "verification_status": verification_status,
            "verification_metric": task_plan.task_contract.verification_metric,
            "reference_energy": verification.get("reference_energy"),
            "reconstructed_energy": verification.get("reconstructed_energy", final_execution.get("energy")),
            "absolute_error": verification.get("absolute_error"),
            "maximum_observable_error": verification.get("maximum_absolute_error"),
            "sector_leakage": verification.get("sector_leakage"),
            "acceptance_threshold": verification.get("acceptance_threshold"),
        },
        artifact_refs=["task_verification_report"],
    ))

    emit(PipelineEvent(
        run_id=run_id,
        stage="meaning",
        status="running",
        message="Returning the verified task result to model-specific physical language.",
        metrics={"task_id": task_plan.task_contract.task_id},
        artifact_refs=["interpretation_policy"],
    ))
    meaning = dict(
        realization.interpretation_handler(realization, outcome, verification)
    )
    if outcome.run_mode == "mapping_analysis":
        automatic_limitations = [
            "operator-level mapping analysis only",
            "no circuit, QASM2, simulator, shots, provider adapter, or hardware submission",
            "resource ranking is not a ground-state execution recommendation",
            "no claim of quantum advantage",
        ]
    else:
        automatic_limitations = [
            "ideal local Cirq simulator",
            "the selected provider is a target label only",
            "no IBM/Google/AWS provider adapter invoked",
            "no real-hardware submission",
            "no claim of quantum advantage",
        ]
    if outcome.run_mode == "single_evaluation":
        automatic_limitations.append("one validated theta evaluation is not VQE convergence")
    if outcome.run_mode == "observable_single_pass":
        automatic_limitations.append("single-pass observable estimation has no optimizer-convergence claim")
    if outcome.controller_name and not outcome.controller_converged:
        automatic_limitations.append("the selected controller stopped without satisfying its convergence flag")
    meaning["limitations"] = list(dict.fromkeys(list(meaning.get("limitations", [])) + automatic_limitations))

    emit(PipelineEvent(
        run_id=run_id,
        stage="meaning",
        status="completed" if verification_status == "PASS" else "review",
        message="Returned the task result to model-specific physical language.",
        metrics={
            "task_id": task_plan.task_contract.task_id,
            "scientific_quantity": meaning.get("scientific_quantity"),
            "supported_statement": meaning.get("supported_statement"),
            "unit": meaning.get("unit"),
            "limitations": meaning.get("limitations"),
        },
        artifact_refs=["task_meaning"],
    ))
    emit(PipelineEvent(
        run_id=run_id,
        stage="feedback",
        status="completed",
        message="Sanitized post-run telemetry is sealed for the deterministic Phase B Advisor.",
        metrics={
            "enabled": True,
            "evaluation_timing": "post_run_only",
            "automatic_execution": False,
            "task_id": task_plan.task_contract.task_id,
            "telemetry_available": (
                ["mapping_capability_reports", "mapping_resource_reports", "mapping_equivalence_checks"]
                if outcome.run_mode == "mapping_analysis"
                else [
                    "controller_history",
                    "task_verification",
                    "statistical_uncertainty",
                    "circuit_and_measurement_metadata",
                ]
            ),
        },
    ))

    completed = datetime.now(timezone.utc)
    result = RunResult(
        run_id=run_id,
        artifact_id=artifact.artifact_id,
        method=artifact.method,
        problem=artifact.problem,
        status=verification_status,
        run_mode=outcome.run_mode,
        execution_mode=execution_mode,
        target_backend=target_backend,
        adapter_status=(
            "not applicable; deterministic operator mapping analysis, no backend invoked"
            if outcome.run_mode == "mapping_analysis"
            else "target recorded; local QASM2/PyQASM/Cirq path executed; provider adapter not invoked"
        ),
        hardware_submission_performed=False,
        shots_per_group=int(
            final_execution.get(
                "shots_per_group", realization.run_controls.get("shots", 0)
            )
        ),
        seed=int(realization.run_controls.get("seed", 42)),
        optimizer_name=outcome.controller_name,
        optimizer_converged=bool(outcome.controller_converged),
        optimizer_message=str(outcome.controller_message),
        optimizer_evaluations=int(outcome.controller_evaluations),
        optimizer_tolerance=float(outcome.controller_tolerance),
        parameter_source=str(outcome.parameter_source),
        optimizer_diagnostics=json_safe(outcome.controller_diagnostics),
        initial_parameters=[float(value) for value in outcome.initial_parameters],
        final_parameters=[float(value) for value in outcome.final_parameters],
        convergence_history=json_safe(outcome.history),
        request_summary=json_safe(dict(realization.request_summary)),
        translation_check=json_safe(final_execution["translation_check"]),
        raw_records=json_safe(final_execution["records"]),
        term_expectations=json_safe(final_execution["term_expectations"]),
        reconstructed_energy=(
            None if final_execution.get("energy") is None
            else float(final_execution["energy"])
        ),
        standard_error=(
            None if final_execution.get("standard_error") is None
            else float(final_execution["standard_error"])
        ),
        verification=verification,
        meaning=meaning,
        environment=json_safe(VERSIONS),
        timestamps={"started_utc": started.isoformat(), "completed_utc": completed.isoformat()},
        journey_events=json_safe(event_log),
        reference_policy=task_plan.task_contract.reference_policy_id,
        task_id=task_plan.task_contract.task_id,
        controller_id=outcome.controller_id,
        model_task_cell_id=str(task_plan.cell_snapshot.get("cell_id")),
        task_result=json_safe(outcome.task_result),
        task_verification=json_safe(verification),
        task_meaning=json_safe(meaning),
        model_task_plan=task_plan.to_dict(),
    )
    return artifact, result


def run_pipeline_controlled(
    request: Mapping[str, Any],
    *,
    run_id: Optional[str] = None,
    cancellation_token: Optional[CancellationToken] = None,
) -> Tuple[ProblemArtifact, RunResult]:
    """Blocking API with an optional externally supplied run ID and cancel token."""
    effective_run_id = run_id or f"run-{uuid4().hex[:12]}"
    return _run_pipeline_impl(
        request,
        run_id=effective_run_id,
        cancellation_token=cancellation_token,
    )


def run_pipeline(request: Mapping[str, Any]) -> Tuple[ProblemArtifact, RunResult]:
    """Blocking API used by tests and notebooks. Existing callers remain valid."""
    return run_pipeline_controlled(request)


def run_pipeline_stream(
    request: Mapping[str, Any],
    *,
    run_id: Optional[str] = None,
    cancellation_token: Optional[CancellationToken] = None,
) -> Iterator[PipelineStreamUpdate]:
    """Yield live JourneyState snapshots while the canonical pipeline runs.

    SciPy COBYLA is blocking, so the scientific path runs in a worker thread and
    emits structured events through a queue.  The same function is consumed by
    Gradio today and by the FastAPI run manager/SSE service.
    """
    effective_run_id = run_id or f"run-{uuid4().hex[:12]}"
    token = cancellation_token or CancellationToken()
    state = JourneyState.initial(effective_run_id, reference_policy=REFERENCE_POLICY)
    queue: Queue[Any] = Queue()
    stage_context = PipelineStageContext(stage="model")

    def callback(event: PipelineEvent) -> None:
        stage_context.observe(event)
        queue.put(event)

    def worker() -> None:
        try:
            artifact, result = _run_pipeline_impl(
                request,
                run_id=effective_run_id,
                event_callback=callback,
                artifact_callback=lambda value: queue.put(_WorkerArtifact(value)),
                cancellation_token=token,
            )
            queue.put(_WorkerResult(artifact=artifact, result=result))
        except RunCancelled as exc:
            queue.put(_WorkerCancelled(message=str(exc), location=exc.location))
        except Exception as exc:
            traceback_text = traceback.format_exc()
            failure = build_pipeline_failure(
                exc,
                run_id=effective_run_id,
                stage=stage_context.stage,
                iteration=stage_context.iteration,
                artifact_refs=stage_context.artifact_refs,
            )
            queue.put(_WorkerError(failure=failure, traceback_text=traceback_text))

    thread = Thread(
        target=worker,
        name=f"qcol-{effective_run_id}",
        daemon=True,
    )
    thread.start()
    yield PipelineStreamUpdate(state=state.snapshot(), done=False)

    while True:
        item = queue.get()
        if isinstance(item, PipelineEvent):
            state.apply(item)
            yield PipelineStreamUpdate(
                state=state.snapshot(),
                event=item,
                done=False,
            )
            continue
        if isinstance(item, _WorkerArtifact):
            yield PipelineStreamUpdate(
                state=state.snapshot(),
                artifact=item.artifact,
                done=False,
            )
            continue
        if isinstance(item, _WorkerResult):
            state.completed = True
            yield PipelineStreamUpdate(
                state=state.snapshot(),
                artifact=item.artifact,
                result=item.result,
                done=True,
            )
            return
        if isinstance(item, _WorkerCancelled):
            state.mark_cancelled(message="Run cancelled at a safe runtime boundary.")
            yield PipelineStreamUpdate(
                state=state.snapshot(),
                error=None,
                done=True,
                cancelled=True,
            )
            return
        if isinstance(item, _WorkerError):
            failed_event = state.mark_failed(item.failure)
            yield PipelineStreamUpdate(
                state=state.snapshot(),
                event=failed_event,
                error=item.text,
                failure=item.failure,
                done=True,
            )
            return
        raise RuntimeError(f"Unexpected stream item: {type(item).__name__}")

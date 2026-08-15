"""Structured, station-local failure contracts for QCOL.

The scientific runtime raises ordinary Python exceptions.  This module turns a
caught exception into a small, UI-safe failure record without changing the
exception itself, the scientific result, or the verification decision.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Optional, Sequence


_STAGE_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "model": {
        "code": "model_or_parameter_validation_failed",
        "message": "The declared model or physical parameters could not be validated.",
        "action": "Review the model contract, units, level count, particle/pair count, and required parameters.",
        "recoverable": True,
    },
    "artifact": {
        "code": "quantum_realization_build_failed",
        "message": "QCOL could not build or validate the quantum realization for this model.",
        "action": "Inspect the mapping, target sector, initial state, ansatz, resource report, and ProblemArtifact contract.",
        "recoverable": False,
    },
    "task": {
        "code": "model_task_resolution_failed",
        "message": "The selected model and task could not be resolved into a supported executable cell.",
        "action": "Choose a runnable Model × Task cell or inspect the missing capability reported by the resolver.",
        "recoverable": True,
    },
    "optimizer": {
        "code": "controller_failed",
        "message": "The classical controller stopped before completing the requested task.",
        "action": "Inspect the controller settings, initial parameters, evaluation budget, and optimizer diagnostics.",
        "recoverable": True,
    },
    "bind": {
        "code": "parameter_binding_failed",
        "message": "The parameter vector could not be bound to the declared circuit.",
        "action": "Check the parameter count, ordering, values, and the selected state-preparation circuit.",
        "recoverable": True,
    },
    "measurement": {
        "code": "measurement_plan_failed",
        "message": "QCOL could not build a complete measurement plan for the selected task.",
        "action": "Inspect the requested observable, Pauli terms, basis changes, grouping policy, and shot settings.",
        "recoverable": False,
    },
    "translation": {
        "code": "qasm_translation_or_validation_failed",
        "message": "The circuit did not pass the OpenQASM 2 / PyQASM translation checks.",
        "action": "Inspect the raw and unrolled QASM, qubit ordering, supported gates, and semantic round-trip diagnostics.",
        "recoverable": False,
    },
    "execute": {
        "code": "execution_failed",
        "message": "The selected simulator or backend did not return valid execution records.",
        "action": "Inspect the execution target, shot count, circuit compatibility, and backend/simulator diagnostics.",
        "recoverable": True,
    },
    "evidence": {
        "code": "evidence_preservation_failed",
        "message": "The run could not preserve the required evidence artifacts.",
        "action": "Check write permissions, available disk space, evidence paths, and manifest generation.",
        "recoverable": True,
    },
    "reconstruct": {
        "code": "result_reconstruction_failed",
        "message": "The retained records could not be reconstructed into the requested result.",
        "action": "Inspect bit order, counts, estimator inputs, measurement metadata, and reconstruction policy.",
        "recoverable": False,
    },
    "convergence": {
        "code": "termination_check_failed",
        "message": "The task controller could not evaluate its declared termination rule.",
        "action": "Inspect the controller history, tolerance, patience, and termination-policy inputs.",
        "recoverable": True,
    },
    "exact_reference": {
        "code": "reference_solver_failed",
        "message": "The model-specific reference could not be prepared.",
        "action": "Inspect the reference validity regime, target sector, model size, and classical solver inputs.",
        "recoverable": True,
    },
    "verification": {
        "code": "verification_process_failed",
        "message": "The reconstructed result could not be checked against the declared verification policy.",
        "action": "Inspect the reference, uncertainty, acceptance metric, and evidence-consistency checks.",
        "recoverable": False,
    },
    "meaning": {
        "code": "physical_interpretation_failed",
        "message": "The verified result could not be translated into bounded physical meaning.",
        "action": "Inspect the model-specific interpretation policy, units, assumptions, and declared limitations.",
        "recoverable": False,
    },
    "feedback": {
        "code": "feedback_rendering_failed",
        "message": "The optional design-feedback layer could not be produced.",
        "action": "Continue using the verified run result; inspect the feedback-layer technical log separately.",
        "recoverable": True,
    },
}


_COMPATIBILITY_FAILURE_SURFACE: Dict[str, Dict[str, Any]] = {
    "ANSATZ_GENERATOR_MAPPING_MISMATCH": {
        "stage": "artifact",
        "message": (
            "The selected ansatz does not implement the mapped fermionic generator "
            "required by this realization."
        ),
        "action": (
            "Use an accepted mapping-aware ansatz or inspect the realization variant's "
            "generator-equivalence evidence."
        ),
        "recoverable": True,
    },
    "INITIAL_STATE_ENCODING_MISMATCH": {
        "stage": "artifact",
        "message": "The initial state is not encoded under the selected mapping convention and sector.",
        "action": "Use the state-preparation policy resolved for this exact mapping and EncodingContext.",
        "recoverable": True,
    },
    "SECTOR_REPRESENTATION_UNAVAILABLE": {
        "stage": "artifact",
        "message": "The selected realization has no accepted representation or diagnostic for the target sector.",
        "action": "Choose a realization with an accepted SectorEncodingProfile or complete the missing sector evidence.",
        "recoverable": True,
    },
    "MODE_ORDER_CONTEXT_MISMATCH": {
        "stage": "artifact",
        "message": "The model, mapping, state, ansatz, or reference use different mode-ordering contexts.",
        "action": "Use one shared EncodingContext fingerprint across every component of the realization.",
        "recoverable": True,
    },
    "TASK_OPERATOR_NOT_MAPPABLE": {
        "stage": "task",
        "message": "At least one operator required by the selected task cannot be transformed by this mapping policy.",
        "action": "Choose a compatible mapping or add accepted transformation evidence for every required task operator.",
        "recoverable": True,
    },
    "REFERENCE_SECTOR_MISMATCH": {
        "stage": "exact_reference",
        "message": "The reference does not describe the same source problem, ordering, sector, quantity, or scale.",
        "action": "Use an independent reference with matching source and sector fingerprints.",
        "recoverable": True,
    },
    "ACCEPTANCE_EVIDENCE_STALE": {
        "stage": "verification",
        "message": "The acceptance evidence does not match the exact resolved realization and declared scale.",
        "action": "Re-run the applicable acceptance gates and archive evidence with the current fingerprint.",
        "recoverable": True,
    },
    "BINDING_DECLARED_NOT_EXECUTABLE": {
        "stage": "task",
        "message": "This realization is recognized, but a required accepted implementation binding is unavailable.",
        "action": "Choose a runnable realization variant or complete and accept the missing implementation binding.",
        "recoverable": True,
    },
}


def _compatibility_failure_from_exception(exc: BaseException) -> Optional[tuple[str, str, str, str, bool]]:
    text = str(exc)
    for code, declaration in _COMPATIBILITY_FAILURE_SURFACE.items():
        if code in text:
            return (
                code,
                str(declaration["stage"]),
                str(declaration["message"]),
                str(declaration["action"]),
                bool(declaration["recoverable"]),
            )
    if "recognized_not_executable" in text.lower():
        declaration = _COMPATIBILITY_FAILURE_SURFACE["BINDING_DECLARED_NOT_EXECUTABLE"]
        return (
            "BINDING_DECLARED_NOT_EXECUTABLE",
            str(declaration["stage"]),
            str(declaration["message"]),
            str(declaration["action"]),
            bool(declaration["recoverable"]),
        )
    return None




def _failure_category_for_stage(stage: str, error_code: str) -> str:
    if error_code.startswith("resource_") or "resource" in error_code:
        return "resource"
    if stage in {"model", "artifact", "task", "exact_reference", "verification"}:
        return "resolution"
    if stage == "translation":
        return "translation"
    if stage == "execute":
        return "execution"
    if stage == "evidence":
        return "evidence"
    if stage in {"optimizer", "bind", "measurement", "reconstruct", "convergence", "meaning", "feedback"}:
        return "state"
    return "state"


def _namespaced_failure_code(category: str, error_code: str) -> str:
    prefix = category.upper()
    normalized = "".join(ch if ch.isalnum() else "_" for ch in str(error_code)).upper().strip("_")
    return f"{prefix}_{normalized}"

@dataclass(frozen=True)
class PipelineFailure:
    """One structured failure attached to the station where execution stopped."""

    run_id: str
    stage: str
    error_code: str
    user_message: str
    technical_message: str
    exception_type: str
    recoverable: bool
    suggested_action: Optional[str] = None
    iteration: Optional[int] = None
    artifact_refs: tuple[str, ...] = ()
    traceback_ref: Optional[str] = "technical_error.json"
    timestamp_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        category = _failure_category_for_stage(self.stage, self.error_code)
        severity = "error" if self.recoverable else "fatal"
        return {
            "schema_version": "qcol-failure-record/1.0",
            "run_id": self.run_id,
            "station": self.stage,
            "stage": self.stage,
            "code": _namespaced_failure_code(category, self.error_code),
            "category": category,
            "severity": severity,
            "error_code": self.error_code,
            "user_message": self.user_message,
            "technical_message": self.technical_message,
            "exception_type": self.exception_type,
            "recoverable": self.recoverable,
            "suggested_action": self.suggested_action,
            "iteration": self.iteration,
            "artifact_refs": list(self.artifact_refs),
            "evidence_context": {
                "artifact_refs": list(self.artifact_refs),
                "iteration": self.iteration,
                "traceback_ref": self.traceback_ref,
            },
            "traceback_ref": self.traceback_ref,
            "timestamp_utc": self.timestamp_utc,
        }


@dataclass
class PipelineStageContext:
    """Mutable worker-local pointer used only to locate an uncaught exception."""

    stage: str = "model"
    iteration: Optional[int] = None
    artifact_refs: tuple[str, ...] = ()

    def observe(self, event: Any) -> None:
        self.stage = str(getattr(event, "stage", self.stage))
        self.iteration = getattr(event, "iteration", self.iteration)
        refs = getattr(event, "artifact_refs", None)
        if refs:
            self.artifact_refs = tuple(str(value) for value in refs)

    def activate(
        self,
        stage: str,
        *,
        iteration: Optional[int] = None,
        artifact_refs: Sequence[str] = (),
    ) -> None:
        self.stage = stage
        if iteration is not None:
            self.iteration = iteration
        if artifact_refs:
            self.artifact_refs = tuple(str(value) for value in artifact_refs)


def _message_contains(message: str, *needles: str) -> bool:
    lower = message.lower()
    return any(needle.lower() in lower for needle in needles)


def _refine_stage(stage: str, exc: BaseException) -> str:
    """Use the exception text only to correct obvious boundary misclassification."""
    message = str(exc)
    name = type(exc).__name__.lower()

    compatibility = _compatibility_failure_from_exception(exc)
    if compatibility is not None:
        return compatibility[1]

    if _message_contains(message, "epsilon", "n_pairs", "n_levels", "n_particles", "seniority", "energy unit"):
        return "model"
    if _message_contains(message, "model × task", "model x task", "task contract", "task policy", "unsupported task"):
        return "task"
    if _message_contains(message, "qasm", "pyqasm", "semantic equivalence", "round trip", "round-trip"):
        return "translation"
    if _message_contains(message, "measurement plan", "pauli basis", "measurement group", "observable"):
        return "measurement"
    if _message_contains(message, "simulator", "backend", "repetitions", "execution") and stage not in {"model", "task"}:
        return "execute"
    if _message_contains(message, "reference energy", "exact reference", "reference solver"):
        return "exact_reference"
    if _message_contains(message, "optimizer", "cobyla", "max_evaluations", "rhobeg", "convergence_patience"):
        return "optimizer"
    if "policyregistry" in name or "taskpolicyregistry" in name:
        return "task"
    return stage


def _known_input_message(exc: BaseException) -> Optional[tuple[str, str, str]]:
    """Return a more concrete user-facing message for common contract errors."""
    text = str(exc)
    lower = text.lower()
    if "n_pairs must satisfy" in lower or ("n_pairs" in lower and "n_levels" in lower):
        return (
            "invalid_pair_sector",
            "The declared pair number is incompatible with the number of levels.",
            "Choose a positive n_pairs strictly smaller than n_levels.",
        )
    if "epsilon" in lower and ("exactly" in lower or "contain" in lower or "length" in lower):
        return (
            "epsilon_length_mismatch",
            "The number of single-particle energies does not match the declared number of levels.",
            "Provide exactly one finite ε value for each declared level.",
        )
    if "shots" in lower and "positive" in lower:
        return (
            "invalid_shot_count",
            "The shot count must be a positive integer.",
            "Choose a positive shot count before running the task.",
        )
    if "parameter" in lower and ("expected" in lower or "shape" in lower or "symbols" in lower):
        return (
            "parameter_vector_mismatch",
            "The supplied parameter vector is incompatible with the resolved circuit.",
            "Use the parameter count and ordering declared by the ProblemArtifact.",
        )
    if "custom matrix must be hermitian" in lower or ("hermitian" in lower and "matrix" in lower):
        return (
            "non_hermitian_custom_matrix",
            "The custom Hamiltonian matrix must be Hermitian.",
            "Correct the matrix so H equals its conjugate transpose.",
        )
    return None


def build_pipeline_failure(
    exc: BaseException,
    *,
    run_id: str,
    stage: str,
    iteration: Optional[int] = None,
    artifact_refs: Sequence[str] = (),
    traceback_ref: Optional[str] = "technical_error.json",
) -> PipelineFailure:
    """Classify an exception without changing the scientific control flow."""
    stage = _refine_stage(stage if stage in _STAGE_DEFAULTS else "model", exc)
    defaults = _STAGE_DEFAULTS[stage]
    compatibility = _compatibility_failure_from_exception(exc)
    known = _known_input_message(exc)
    recoverable_override: Optional[bool] = None
    if compatibility is not None:
        error_code, _, user_message, suggested_action, recoverable_override = compatibility
    elif known is None:
        error_code = str(defaults["code"])
        user_message = str(defaults["message"])
        suggested_action = str(defaults["action"])
    else:
        error_code, user_message, suggested_action = known

    if isinstance(exc, NotImplementedError) and compatibility is None:
        error_code = "capability_not_implemented"
        user_message = "This model, task, or execution route is recognized but not implemented in the current release."
        suggested_action = "Select a runnable cell shown by the Model × Task matrix or inspect the missing capability."

    technical = f"{type(exc).__name__}: {exc}"
    return PipelineFailure(
        run_id=run_id,
        stage=stage,
        error_code=error_code,
        user_message=user_message,
        technical_message=technical,
        exception_type=type(exc).__name__,
        recoverable=(bool(defaults["recoverable"]) if recoverable_override is None else recoverable_override),
        suggested_action=suggested_action,
        iteration=iteration,
        artifact_refs=tuple(str(value) for value in artifact_refs),
        traceback_ref=traceback_ref,
    )


def format_technical_error_log(
    failure: PipelineFailure,
    traceback_text: str,
) -> str:
    """Human-readable log for Gradio and the local technical-error endpoint."""
    lines = [
        f"run_id: {failure.run_id}",
        f"stage: {failure.stage}",
        f"error_code: {failure.error_code}",
        f"exception_type: {failure.exception_type}",
        f"recoverable: {failure.recoverable}",
        f"user_message: {failure.user_message}",
        f"suggested_action: {failure.suggested_action or '—'}",
        "",
        "technical traceback:",
        traceback_text.rstrip(),
    ]
    return "\n".join(lines)

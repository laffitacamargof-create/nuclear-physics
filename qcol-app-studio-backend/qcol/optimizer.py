"""The external amber VQE loop. The scientific module itself remains optimizer-free."""
from __future__ import annotations

import hashlib
from typing import Any, Dict, Mapping, Optional, Sequence

import numpy as np
from scipy.optimize import minimize

from .config import (
    DEFAULT_ENERGY_TOLERANCE,
    DEFAULT_MAX_EVALUATIONS,
    DEFAULT_RHOBEG,
)
from .contracts import ProblemArtifact
from .control import CancellationToken
from .events import EventCallback, PipelineEvent
from .runtime import execute_artifact_parameter_point


def _emit(
    callback: Optional[EventCallback],
    *,
    run_id: str,
    stage: str,
    status: str,
    message: str,
    iteration: Optional[int] = None,
    metrics: Optional[Dict[str, Any]] = None,
) -> None:
    if callback is None:
        return
    callback(PipelineEvent(
        run_id=run_id,
        stage=stage,
        status=status,  # type: ignore[arg-type]
        message=message,
        iteration=iteration,
        metrics={} if metrics is None else metrics,
    ))


def _wrap_angles(values: Sequence[float]) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    return (array + np.pi) % (2 * np.pi) - np.pi


def _deterministic_seed(base_seed: int, values: Sequence[float]) -> int:
    rounded = np.round(np.asarray(values, dtype=np.float64), 10)
    digest = hashlib.blake2b(rounded.tobytes(), digest_size=4).digest()
    offset = int.from_bytes(digest, byteorder="little", signed=False)
    return int((base_seed + offset) % (2**31 - 1))


def _initial_vector(artifact: ProblemArtifact, request: Mapping[str, Any]) -> np.ndarray:
    supplied = request.get("initial_parameters")
    values = artifact.initial_parameters if supplied is None else supplied
    array = np.asarray(values, dtype=float)
    expected = (len(artifact.parameter_symbols),)
    if array.shape != expected:
        raise ValueError(
            f"Expected {expected[0]} initial parameters, received shape {array.shape}."
        )
    if not np.all(np.isfinite(array)):
        raise ValueError("Initial parameters contain non-finite values.")
    return _wrap_angles(array)


def run_variational_runtime(
    realization_or_artifact,
    request: Optional[Mapping[str, Any]] = None,
    *,
    run_id: str = "standalone",
    event_callback: Optional[EventCallback] = None,
    cancellation_token: Optional[CancellationToken] = None,
) -> Dict[str, Any]:
    """Run one validated theta point or the full external COBYLA loop.

    The canonical pipeline supplies a ``QuantumRealizationArtifact``.  The
    historical ``ProblemArtifact + request`` form remains a compatibility path
    for focused scientific tests and notebooks.
    """
    if hasattr(realization_or_artifact, "problem_artifact"):
        artifact = realization_or_artifact.problem_artifact
        runtime_input = realization_or_artifact
        controls = dict(realization_or_artifact.run_controls)
    else:
        artifact = realization_or_artifact
        runtime_input = realization_or_artifact
        if request is None:
            raise ValueError("Legacy optimizer invocation requires request controls.")
        controls = dict(request)
    request = controls

    def check_cancel(location: str) -> None:
        if cancellation_token is not None:
            cancellation_token.raise_if_cancelled(location=location)

    check_cancel("before_variational_runtime")
    run_mode = str(request.get("run_mode", "vqe")).lower()
    shots = int(request.get("shots", 2048))
    final_shots = int(request.get("final_shots", shots))
    seed = int(request.get("seed", 42))
    if shots <= 0 or final_shots <= 0:
        raise ValueError("shots and final_shots must be positive.")

    if run_mode == "single_evaluation":
        supplied = request.get("initial_parameters")
        if supplied is not None:
            values = np.asarray(supplied, dtype=float)
            source = "user_supplied_single_evaluation"
        elif artifact.parameter_fixture is not None:
            values = np.asarray(artifact.parameter_fixture["values"], dtype=float)
            source = str(artifact.parameter_fixture["source"])
        else:
            values = np.asarray(artifact.initial_parameters, dtype=float)
            source = "builder_initial_parameters"
        values = _wrap_angles(values)
        _emit(
            event_callback,
            run_id=run_id,
            stage="optimizer",
            status="completed",
            message="Single validated θ evaluation selected; optimizer not invoked.",
            iteration=1,
            metrics={"optimizer": None, "run_mode": "single_evaluation"},
        )
        final_execution = execute_artifact_parameter_point(
            runtime_input,
            values,
            shots=final_shots,
            seed=seed,
            strict_semantic_checks=True,
            retain_artifacts=True,
            run_id=run_id,
            iteration=1,
            evaluation_role="single_evaluation",
            event_callback=event_callback,
            cancellation_token=cancellation_token,
        )
        history = [{
            "evaluation": 1,
            "theta": [float(v) for v in values],
            "energy": float(final_execution["energy"]),
            "standard_error": float(final_execution["standard_error"]),
            "best_energy": float(final_execution["energy"]),
            "delta_energy": None,
            "role": "single_evaluation",
            "evidence_summary": final_execution["evidence_summary"],
        }]
        _emit(
            event_callback,
            run_id=run_id,
            stage="convergence",
            status="completed",
            message="One energy evaluation completed; no convergence claim is made.",
            iteration=1,
            metrics={
                "converged": False,
                "run_mode": "single_evaluation",
                "energy": float(final_execution["energy"]),
            },
        )
        return {
            "run_mode": "single_evaluation",
            "optimizer_name": None,
            "optimizer_converged": False,
            "optimizer_message": "One validated theta evaluation; optimizer not invoked.",
            "optimizer_evaluations": 1,
            "optimizer_tolerance": float(request.get("energy_tolerance", 0.0)),
            "parameter_source": source,
            "initial_parameters": [float(v) for v in values],
            "final_parameters": [float(v) for v in values],
            "history": history,
            "final_execution": final_execution,
            "best_execution": final_execution,
            "best_and_final_are_same_point": True,
        }

    if run_mode != "vqe":
        raise ValueError("run_mode must be 'vqe' or 'single_evaluation'.")

    x0 = _initial_vector(artifact, request)
    if x0.size == 0:
        _emit(
            event_callback,
            run_id=run_id,
            stage="optimizer",
            status="completed",
            message="Parameter-free ansatz; no numerical optimization was required.",
            iteration=1,
            metrics={"optimizer": "COBYLA", "parameter_count": 0},
        )
        final_execution = execute_artifact_parameter_point(
            runtime_input,
            x0,
            shots=final_shots,
            seed=seed,
            strict_semantic_checks=True,
            retain_artifacts=True,
            run_id=run_id,
            iteration=1,
            evaluation_role="parameter_free_final",
            event_callback=event_callback,
            cancellation_token=cancellation_token,
        )
        history = [{
            "evaluation": 1,
            "theta": [],
            "energy": float(final_execution["energy"]),
            "standard_error": float(final_execution["standard_error"]),
            "best_energy": float(final_execution["energy"]),
            "delta_energy": None,
            "role": "final",
            "evidence_summary": final_execution["evidence_summary"],
        }]
        _emit(
            event_callback,
            run_id=run_id,
            stage="convergence",
            status="completed",
            message="Parameter-free ansatz completed.",
            iteration=1,
            metrics={"converged": True, "energy": float(final_execution["energy"])},
        )
        return {
            "run_mode": "vqe",
            "optimizer_name": "COBYLA",
            "optimizer_converged": True,
            "optimizer_message": "Parameter-free ansatz; no optimization was required.",
            "optimizer_evaluations": 1,
            "optimizer_tolerance": float(request.get("energy_tolerance", 0.0)),
            "parameter_source": "parameter_free_ansatz",
            "initial_parameters": [],
            "final_parameters": [],
            "history": history,
            "final_execution": final_execution,
            "best_execution": final_execution,
            "best_and_final_are_same_point": True,
        }

    max_evaluations = int(request.get("max_evaluations", DEFAULT_MAX_EVALUATIONS))
    energy_tolerance = float(
        request.get("energy_tolerance", DEFAULT_ENERGY_TOLERANCE)
    )
    rhobeg = float(request.get("rhobeg", DEFAULT_RHOBEG))
    patience = int(request.get("convergence_patience", 4))
    if not 4 <= max_evaluations <= 200:
        raise ValueError("max_evaluations must be between 4 and 200.")
    if energy_tolerance <= 0:
        raise ValueError("energy_tolerance must be positive.")
    if rhobeg <= 0:
        raise ValueError("rhobeg must be positive.")
    if patience < 2:
        raise ValueError("convergence_patience must be at least 2.")

    history: list[dict[str, Any]] = []
    cache: dict[tuple[float, ...], float] = {}
    best_energy = float("inf")

    _emit(
        event_callback,
        run_id=run_id,
        stage="optimizer",
        status="running",
        message="COBYLA initialized outside the scientific problem builder.",
        iteration=1,
        metrics={
            "optimizer": "COBYLA",
            "max_evaluations": max_evaluations,
            "energy_tolerance": energy_tolerance,
            "parameter_count": int(x0.size),
        },
    )

    def objective(raw_theta: np.ndarray) -> float:
        nonlocal best_energy
        check_cancel("before_optimizer_evaluation")
        theta = _wrap_angles(raw_theta)
        key = tuple(float(v) for v in np.round(theta, 10))
        cached = cache.get(key)
        if cached is not None:
            return cached

        iteration = len(history) + 1
        _emit(
            event_callback,
            run_id=run_id,
            stage="optimizer",
            status="running",
            message=f"COBYLA proposed θ for energy evaluation {iteration}.",
            iteration=iteration,
            metrics={
                "optimizer": "COBYLA",
                "evaluation": iteration,
                "theta_preview": [float(value) for value in theta[:6]],
            },
        )
        eval_seed = _deterministic_seed(seed, theta)
        execution = execute_artifact_parameter_point(
            runtime_input,
            theta,
            shots=shots,
            seed=eval_seed,
            strict_semantic_checks=(len(history) == 0),
            retain_artifacts=False,
            run_id=run_id,
            iteration=iteration,
            evaluation_role="optimizer_evaluation",
            event_callback=event_callback,
            cancellation_token=cancellation_token,
        )
        check_cancel("after_optimizer_evaluation")
        energy = float(execution["energy"])
        standard_error = float(execution["standard_error"])
        previous_energy = history[-1]["energy"] if history else None
        best_energy = min(best_energy, energy)
        entry = {
            "evaluation": iteration,
            "theta": [float(v) for v in theta],
            "energy": energy,
            "standard_error": standard_error,
            "best_energy": best_energy,
            "delta_energy": (
                None if previous_energy is None else abs(energy - float(previous_energy))
            ),
            "seed": eval_seed,
            "role": "optimizer_evaluation",
            "evidence_summary": execution["evidence_summary"],
        }
        history.append(entry)
        _emit(
            event_callback,
            run_id=run_id,
            stage="optimizer",
            status="running",
            message=(
                f"Evaluation {iteration}: ⟨H⟩={energy:.8g}; "
                f"best={best_energy:.8g}."
            ),
            iteration=iteration,
            metrics={
                "optimizer": "COBYLA",
                "evaluation": iteration,
                "energy": energy,
                "standard_error": standard_error,
                "best_energy": best_energy,
                "delta_energy": entry["delta_energy"],
            },
        )
        cache[key] = energy
        return energy

    check_cancel("before_cobyla")
    scipy_result = minimize(
        objective,
        x0,
        method="COBYLA",
        options={
            "maxiter": max_evaluations,
            "tol": energy_tolerance,
            "rhobeg": rhobeg,
            "catol": 1e-8,
            "disp": False,
        },
    )

    check_cancel("after_cobyla")

    if not history:
        raise RuntimeError("The optimizer returned without evaluating the objective.")

    best_entry = min(history, key=lambda item: float(item["energy"]))
    final_theta = np.asarray(best_entry["theta"], dtype=float)
    final_iteration = len(history) + 1
    _emit(
        event_callback,
        run_id=run_id,
        stage="optimizer",
        status="running",
        message="Re-evaluating the best θ with strict semantic checks and full evidence retention.",
        iteration=final_iteration,
        metrics={
            "optimizer": "COBYLA",
            "best_optimizer_evaluation": int(best_entry["evaluation"]),
            "best_optimizer_energy": float(best_entry["energy"]),
        },
    )
    check_cancel("before_final_strict_evaluation")
    final_execution = execute_artifact_parameter_point(
        runtime_input,
        final_theta,
        shots=final_shots,
        seed=_deterministic_seed(seed + 1000003, final_theta),
        strict_semantic_checks=True,
        retain_artifacts=True,
        run_id=run_id,
        iteration=final_iteration,
        evaluation_role="best_and_final_strict_evaluation",
        event_callback=event_callback,
        cancellation_token=cancellation_token,
    )
    final_energy = float(final_execution["energy"])
    history.append({
        "evaluation": final_iteration,
        "theta": [float(v) for v in final_theta],
        "energy": final_energy,
        "standard_error": float(final_execution["standard_error"]),
        "best_energy": min(best_energy, final_energy),
        "delta_energy": abs(final_energy - float(best_entry["energy"])),
        "seed": int(final_execution["seed"]),
        "role": "best_and_final_strict_evaluation",
        "evidence_summary": final_execution["evidence_summary"],
    })

    optimizer_energies = [
        float(item["energy"])
        for item in history
        if item["role"] == "optimizer_evaluation"
    ]
    best_trace = np.minimum.accumulate(np.asarray(optimizer_energies, dtype=float))
    stagnation_converged = False
    rolling_improvement = None
    if len(best_trace) > patience:
        rolling_improvement = float(best_trace[-patience - 1] - best_trace[-1])
        stagnation_converged = rolling_improvement <= energy_tolerance
    converged = bool(scipy_result.success or stagnation_converged)
    message = str(scipy_result.message)
    if rolling_improvement is not None:
        message += (
            f" Best-energy improvement over the last {patience} evaluations: "
            f"{rolling_improvement:.6g}."
        )

    _emit(
        event_callback,
        run_id=run_id,
        stage="convergence",
        status="completed" if converged else "review",
        message=(
            "The external loop met its convergence condition."
            if converged
            else "The loop stopped without satisfying the declared convergence condition."
        ),
        iteration=final_iteration,
        metrics={
            "converged": converged,
            "optimizer_success": bool(scipy_result.success),
            "energy_tolerance": energy_tolerance,
            "optimizer_evaluations": len(optimizer_energies),
            "rolling_improvement": rolling_improvement,
            "final_energy": final_energy,
        },
    )
    _emit(
        event_callback,
        run_id=run_id,
        stage="optimizer",
        status="completed" if converged else "review",
        message=message,
        iteration=final_iteration,
        metrics={
            "optimizer": "COBYLA",
            "converged": converged,
            "evaluations": len(optimizer_energies),
            "best_energy": min(best_energy, final_energy),
        },
    )

    return {
        "run_mode": "vqe",
        "optimizer_name": "COBYLA",
        "optimizer_converged": converged,
        "optimizer_message": message,
        "optimizer_evaluations": len(optimizer_energies),
        "optimizer_tolerance": energy_tolerance,
        "parameter_source": "external_cobyla_optimizer",
        "initial_parameters": [float(v) for v in x0],
        "final_parameters": [float(v) for v in final_theta],
        "history": history,
        "final_execution": final_execution,
        "best_execution": final_execution,
        "best_and_final_are_same_point": True,
        "scipy_result": {
            "success": bool(scipy_result.success),
            "status": int(scipy_result.status),
            "message": str(scipy_result.message),
            "nfev": int(getattr(scipy_result, "nfev", len(optimizer_energies))),
            "fun": float(scipy_result.fun),
        },
    }

"""Live journey event contracts for the interactive QCOL interface.

The scientific runtime remains deterministic.  This module only exposes its
progress as structured, reproducible events that a UI, notebook, or logger can
consume without moving physics into the presentation layer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Literal, Mapping, Optional

from .contracts import json_safe
from .failures import PipelineFailure

StageStatus = Literal["waiting", "running", "completed", "review", "failed", "blocked"]
EventCallback = Callable[["PipelineEvent"], None]


STAGE_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "entrance": {
        "title": "Physics modelling entrance",
        "lenses": ["Physics", "Math", "Evidence"],
        "order": 5,
    },
    "model": {
        "title": "Model & Hamiltonian",
        "lenses": ["Physics", "Math"],
        "order": 10,
    },
    "artifact": {
        "title": "ProblemArtifact",
        "lenses": ["Physics", "Math", "Quantum"],
        "order": 20,
    },
    "task": {
        "title": "Task Contract & Controller",
        "lenses": ["Physics", "Math", "Quantum", "Evidence"],
        "order": 25,
    },
    "optimizer": {
        "title": "Classical optimizer",
        "lenses": ["Evidence"],
        "order": 30,
    },
    "mapping_analysis": {
        "title": "Mapping Explorer — JW ↔ BK",
        "lenses": ["Math", "Quantum", "Evidence"],
        "order": 35,
    },
    "bind": {
        "title": "Bind θ",
        "lenses": ["Quantum"],
        "order": 40,
    },
    "measurement": {
        "title": "Measurement circuits",
        "lenses": ["Physics", "Quantum", "Hardware"],
        "order": 50,
    },
    "translation": {
        "title": "OpenQASM 2 → PyQASM",
        "lenses": ["Quantum", "Evidence", "Hardware"],
        "order": 60,
    },
    "execute": {
        "title": "Execute → counts",
        "lenses": ["Hardware", "Evidence"],
        "order": 70,
    },
    "evidence": {
        "title": "Evidence",
        "lenses": ["Evidence", "Hardware"],
        "order": 80,
    },
    "reconstruct": {
        "title": "Reconstruct ⟨H⟩",
        "lenses": ["Physics", "Math", "Evidence"],
        "order": 90,
    },
    "convergence": {
        "title": "Converged?",
        "lenses": ["Evidence"],
        "order": 100,
    },
    "exact_reference": {
        "title": "Exact reference",
        "lenses": ["Math", "Evidence"],
        "order": 110,
    },
    "verification": {
        "title": "Verification",
        "lenses": ["Physics", "Math", "Quantum", "Evidence", "Hardware"],
        "order": 120,
    },
    "meaning": {
        "title": "Physical meaning",
        "lenses": ["Physics", "Evidence"],
        "order": 130,
    },
    "feedback": {
        "title": "Design feedback",
        "lenses": ["Physics", "Math", "Quantum", "Evidence", "Hardware"],
        "order": 140,
    },
}

RUNTIME_STAGES = (
    "bind",
    "measurement",
    "translation",
    "execute",
    "evidence",
    "reconstruct",
)


# Explicit graph rather than a numeric order: the exact-reference branch is
# parallel to the runtime, while verification and meaning depend on both.
DOWNSTREAM_STAGES: Dict[str, tuple[str, ...]] = {
    "entrance": ("model", "artifact", "task", "optimizer", "mapping_analysis", "bind", "measurement", "translation", "execute", "evidence", "reconstruct", "convergence", "exact_reference", "verification", "meaning", "feedback"),
    "model": ("artifact", "task", "optimizer", "mapping_analysis", "bind", "measurement", "translation", "execute", "evidence", "reconstruct", "convergence", "exact_reference", "verification", "meaning", "feedback"),
    "artifact": ("task", "optimizer", "mapping_analysis", "bind", "measurement", "translation", "execute", "evidence", "reconstruct", "convergence", "exact_reference", "verification", "meaning", "feedback"),
    "task": ("optimizer", "mapping_analysis", "bind", "measurement", "translation", "execute", "evidence", "reconstruct", "convergence", "exact_reference", "verification", "meaning", "feedback"),
    "optimizer": ("bind", "measurement", "translation", "execute", "evidence", "reconstruct", "convergence", "verification", "meaning", "feedback"),
    "mapping_analysis": ("evidence", "reconstruct", "verification", "meaning", "feedback"),
    "bind": ("measurement", "translation", "execute", "evidence", "reconstruct", "convergence", "verification", "meaning", "feedback"),
    "measurement": ("translation", "execute", "evidence", "reconstruct", "convergence", "verification", "meaning", "feedback"),
    "translation": ("execute", "evidence", "reconstruct", "convergence", "verification", "meaning", "feedback"),
    "execute": ("evidence", "reconstruct", "convergence", "verification", "meaning", "feedback"),
    "evidence": ("reconstruct", "convergence", "verification", "meaning", "feedback"),
    "reconstruct": ("convergence", "verification", "meaning", "feedback"),
    "convergence": ("verification", "meaning", "feedback"),
    "exact_reference": ("verification", "meaning", "feedback"),
    "verification": ("meaning", "feedback"),
    "meaning": ("feedback",),
    "feedback": (),
}


@dataclass(frozen=True)
class PipelineEvent:
    """One immutable progress message emitted by the canonical runtime."""

    run_id: str
    stage: str
    status: StageStatus
    message: str
    timestamp_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    iteration: Optional[int] = None
    progress_current: Optional[int] = None
    progress_total: Optional[int] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    artifact_refs: List[str] = field(default_factory=list)
    failure: Optional[PipelineFailure] = None

    def __post_init__(self) -> None:
        if self.stage not in STAGE_DEFINITIONS:
            raise ValueError(f"Unknown journey stage: {self.stage!r}")
        if self.status not in {"waiting", "running", "completed", "review", "failed", "blocked"}:
            raise ValueError(f"Unknown journey status: {self.status!r}")
        if self.progress_current is not None and self.progress_current < 0:
            raise ValueError("progress_current must be non-negative.")
        if self.progress_total is not None and self.progress_total <= 0:
            raise ValueError("progress_total must be positive.")

    def to_dict(self) -> Dict[str, Any]:
        return json_safe({
            "run_id": self.run_id,
            "stage": self.stage,
            "title": STAGE_DEFINITIONS[self.stage]["title"],
            "status": self.status,
            "message": self.message,
            "timestamp_utc": self.timestamp_utc,
            "iteration": self.iteration,
            "progress_current": self.progress_current,
            "progress_total": self.progress_total,
            "metrics": self.metrics,
            "artifact_refs": self.artifact_refs,
            "failure": None if self.failure is None else self.failure.to_dict(),
        })


@dataclass
class JourneyCardState:
    """Latest visible state of one journey station."""

    stage: str
    title: str
    status: StageStatus = "waiting"
    message: str = "Waiting"
    iteration: Optional[int] = None
    progress_current: Optional[int] = None
    progress_total: Optional[int] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    artifact_refs: List[str] = field(default_factory=list)
    lenses: List[str] = field(default_factory=list)
    updated_utc: Optional[str] = None
    failure: Optional[Dict[str, Any]] = None
    blocked_by: Optional[str] = None

    @property
    def progress_fraction(self) -> Optional[float]:
        if self.progress_current is None or self.progress_total is None:
            return None
        return max(0.0, min(1.0, self.progress_current / self.progress_total))

    def to_dict(self) -> Dict[str, Any]:
        return json_safe({
            "stage": self.stage,
            "title": self.title,
            "status": self.status,
            "message": self.message,
            "iteration": self.iteration,
            "progress_current": self.progress_current,
            "progress_total": self.progress_total,
            "progress_fraction": self.progress_fraction,
            "metrics": self.metrics,
            "artifact_refs": self.artifact_refs,
            "lenses": self.lenses,
            "updated_utc": self.updated_utc,
            "failure": self.failure,
            "blocked_by": self.blocked_by,
        })


@dataclass
class JourneyState:
    """UI-neutral snapshot assembled from the stream of PipelineEvent objects."""

    run_id: str
    reference_policy: str
    cards: Dict[str, JourneyCardState]
    current_iteration: int = 0
    energy_history: List[Dict[str, Any]] = field(default_factory=list)
    best_energy: Optional[float] = None
    exact_reference_energy: Optional[float] = None
    verification_status: str = "waiting"
    physical_summary: Dict[str, Any] = field(default_factory=dict)
    event_log: List[Dict[str, Any]] = field(default_factory=list)
    failure: Optional[PipelineFailure] = None
    global_summary: Optional[str] = None
    failed: bool = False
    cancelled: bool = False
    completed: bool = False

    @classmethod
    def initial(cls, run_id: str, *, reference_policy: str) -> "JourneyState":
        cards = {
            stage: JourneyCardState(
                stage=stage,
                title=definition["title"],
                lenses=list(definition["lenses"]),
            )
            for stage, definition in STAGE_DEFINITIONS.items()
        }
        cards["feedback"].message = "Waiting for a terminal run. Deterministic feedback is available post-run; Phase C candidates require explicit approval."
        return cls(
            run_id=run_id,
            reference_policy=reference_policy,
            cards=cards,
        )

    def apply(self, event: PipelineEvent) -> None:
        """Apply one event and update only presentation state."""
        if event.run_id != self.run_id:
            raise ValueError(
                f"Event run_id {event.run_id!r} does not match state {self.run_id!r}."
            )

        if event.stage == "optimizer" and event.iteration:
            if event.iteration > self.current_iteration:
                self.current_iteration = event.iteration
                for stage in RUNTIME_STAGES:
                    card = self.cards[stage]
                    card.status = "waiting"
                    card.message = f"Waiting for iteration {event.iteration}"
                    card.iteration = event.iteration
                    card.progress_current = None
                    card.progress_total = None
                    card.metrics = {}
                    card.artifact_refs = []

        card = self.cards[event.stage]
        card.status = event.status
        card.message = event.message
        card.iteration = event.iteration
        card.progress_current = event.progress_current
        card.progress_total = event.progress_total
        safe_metrics = json_safe(event.metrics)
        card.metrics = safe_metrics if isinstance(safe_metrics, dict) else {"value": safe_metrics}
        card.artifact_refs = list(event.artifact_refs)
        card.updated_utc = event.timestamp_utc
        card.failure = None if event.failure is None else event.failure.to_dict()
        card.blocked_by = None

        if event.iteration is not None:
            self.current_iteration = max(self.current_iteration, event.iteration)

        if event.stage == "reconstruct" and "energy" in event.metrics:
            energy_record = {
                "iteration": event.iteration,
                "energy": float(event.metrics["energy"]),
                "standard_error": event.metrics.get("standard_error"),
                "best_energy": event.metrics.get("best_energy"),
                "role": event.metrics.get("role"),
            }
            # One reconstruct event per iteration/role. Replace duplicates rather
            # than letting UI retries duplicate the history.
            key = (energy_record["iteration"], energy_record["role"])
            self.energy_history = [
                item
                for item in self.energy_history
                if (item.get("iteration"), item.get("role")) != key
            ]
            self.energy_history.append(energy_record)
            self.energy_history.sort(
                key=lambda item: (
                    int(item.get("iteration") or 0),
                    str(item.get("role") or ""),
                )
            )
            finite = [
                float(item["energy"])
                for item in self.energy_history
                if item.get("energy") is not None
            ]
            self.best_energy = min(finite) if finite else None

        if event.stage == "exact_reference":
            value = event.metrics.get("reference_energy")
            if value is not None:
                self.exact_reference_energy = float(value)

        if event.stage == "verification":
            self.verification_status = str(
                event.metrics.get("verification_status", event.status)
            )

        if event.stage == "meaning":
            safe_summary = json_safe(event.metrics)
            self.physical_summary = safe_summary if isinstance(safe_summary, dict) else {"value": safe_summary}

        if event.status == "failed":
            self.failed = True
            if event.failure is not None:
                self.failure = event.failure
                self.global_summary = (
                    f"Run stopped at: {self.cards[event.stage].title}. "
                    "Open the failed station for the user-facing explanation or the technical log for the traceback."
                )
            self._block_downstream(event.stage)
        self.event_log.append(event.to_dict())

    def _block_downstream(self, failed_stage: str) -> None:
        """Mark only not-yet-reached dependent stations as blocked."""
        failed_title = self.cards[failed_stage].title
        for stage in DOWNSTREAM_STAGES.get(failed_stage, ()):
            card = self.cards[stage]
            if card.status in {"waiting", "running"}:
                card.status = "blocked"
                card.message = f"Not reached because {failed_title} failed."
                card.blocked_by = failed_stage
                card.progress_current = None
                card.progress_total = None
                card.metrics = {}
                card.artifact_refs = []
                card.failure = None

    def mark_failed(self, failure: PipelineFailure) -> PipelineEvent:
        """Attach a structured failure to its station and block dependants."""
        event = PipelineEvent(
            run_id=self.run_id,
            stage=failure.stage,
            status="failed",
            message=failure.user_message,
            iteration=failure.iteration,
            metrics={
                "error_code": failure.error_code,
                "recoverable": failure.recoverable,
                "suggested_action": failure.suggested_action,
                "technical_log_available": bool(failure.traceback_ref),
            },
            artifact_refs=list(failure.artifact_refs),
            failure=failure,
        )
        self.apply(event)
        return event


    def mark_cancelled(self, *, message: str = "Run cancelled at a safe boundary.") -> None:
        """Mark the journey terminal without mislabelling it as verified or failed."""
        self.cancelled = True
        self.completed = True
        for card in self.cards.values():
            if card.status == "running":
                card.status = "review"
                card.message = message
            elif card.status == "waiting":
                card.status = "blocked"
                card.message = "Not reached because the run was cancelled."
                card.blocked_by = "cancellation"
        feedback = self.cards.get("feedback")
        if feedback is not None:
            feedback.status = "review"
            feedback.message = "Run cancelled; no verified final result was produced."

    def snapshot(self) -> "JourneyState":
        # Journey metrics may originate in frozen scientific contracts.  Build a
        # fresh UI-neutral snapshot from JSON-safe values instead of deepcopy,
        # which cannot copy MappingProxyType objects.
        cards = {
            stage: JourneyCardState(
                stage=card.stage,
                title=card.title,
                status=card.status,
                message=card.message,
                iteration=card.iteration,
                progress_current=card.progress_current,
                progress_total=card.progress_total,
                metrics=(json_safe(card.metrics) if isinstance(json_safe(card.metrics), dict) else {}),
                artifact_refs=list(card.artifact_refs),
                lenses=list(card.lenses),
                updated_utc=card.updated_utc,
                failure=(json_safe(card.failure) if card.failure is not None else None),
                blocked_by=card.blocked_by,
            )
            for stage, card in self.cards.items()
        }
        safe_history = json_safe(self.energy_history)
        safe_summary = json_safe(self.physical_summary)
        safe_events = json_safe(self.event_log)
        return JourneyState(
            run_id=self.run_id,
            reference_policy=self.reference_policy,
            cards=cards,
            current_iteration=self.current_iteration,
            energy_history=safe_history if isinstance(safe_history, list) else [],
            best_energy=self.best_energy,
            exact_reference_energy=self.exact_reference_energy,
            verification_status=self.verification_status,
            physical_summary=safe_summary if isinstance(safe_summary, dict) else {},
            event_log=safe_events if isinstance(safe_events, list) else [],
            failure=self.failure,
            global_summary=self.global_summary,
            failed=self.failed,
            cancelled=self.cancelled,
            completed=self.completed,
        )

    def to_dict(self) -> Dict[str, Any]:
        return json_safe({
            "run_id": self.run_id,
            "reference_policy": self.reference_policy,
            "cards": {stage: card.to_dict() for stage, card in self.cards.items()},
            "current_iteration": self.current_iteration,
            "energy_history": self.energy_history,
            "best_energy": self.best_energy,
            "exact_reference_energy": self.exact_reference_energy,
            "verification_status": self.verification_status,
            "physical_summary": self.physical_summary,
            "event_log": self.event_log,
            "failure": None if self.failure is None else self.failure.to_dict(),
            "global_summary": self.global_summary,
            "failed": self.failed,
            "cancelled": self.cancelled,
            "completed": self.completed,
        })


@dataclass
class PipelineStreamUpdate:
    """One item yielded by run_pipeline_stream."""

    state: JourneyState
    event: Optional[PipelineEvent] = None
    artifact: Any = None
    result: Any = None
    error: Optional[str] = None
    failure: Optional[PipelineFailure] = None
    done: bool = False
    cancelled: bool = False

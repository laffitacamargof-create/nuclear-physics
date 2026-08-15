"""Thread-safe run registry shared by FastAPI, SSE clients, and future frontends.

The manager deliberately knows nothing about Cirq/OpenFermion at import time.
It loads ``run_pipeline_stream`` only when a run starts, stores replayable JSON
messages, and exposes a compact public view that withholds exact-state data and
large evidence payloads.
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields as dataclass_fields, is_dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import traceback
from threading import Condition, RLock, Thread
from typing import Any, Callable, Dict, Iterable, Iterator, Mapping, Optional
from uuid import uuid4

from .control import CancellationToken
from .public_views import build_dashboard_view
from .request_validation import normalize_run_request
from .state import InMemoryStateRepository, StateRepository

TERMINAL_STATUSES = {"completed", "cancelled", "failed"}
StreamFactory = Callable[..., Iterable[Any]]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def service_json_safe(value: Any) -> Any:
    """Convert service payloads to strict JSON without importing NumPy eagerly."""
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return service_json_safe(value.to_dict())
    if is_dataclass(value):
        return {field.name: service_json_safe(getattr(value, field.name)) for field in dataclass_fields(value)}
    if isinstance(value, Mapping):
        return {str(key): service_json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [service_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, float):
        if math.isnan(value):
            return "NaN"
        if math.isinf(value):
            return "Infinity" if value > 0 else "-Infinity"
        return value
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    # NumPy scalar/array support without importing NumPy at module import time.
    if hasattr(value, "item"):
        try:
            return service_json_safe(value.item())
        except (TypeError, ValueError):
            pass
    if hasattr(value, "tolist"):
        try:
            return service_json_safe(value.tolist())
        except (TypeError, ValueError):
            pass
    return str(value)


def _public_state(state: Any) -> Optional[Dict[str, Any]]:
    if state is None:
        return None
    payload = service_json_safe(state)
    if not isinstance(payload, dict):
        return {"value": payload}
    events = payload.pop("event_log", [])
    payload["event_count"] = len(events) if isinstance(events, list) else 0
    return payload


def _active_stage_from_public_state(state: Optional[Dict[str, Any]]) -> str:
    cards = state.get("cards") if isinstance(state, dict) else None
    if isinstance(cards, dict):
        for stage, card in cards.items():
            if isinstance(card, dict) and card.get("status") == "running":
                return str(stage)
    return "model"


def _apply_failure_to_public_state(
    state: Optional[Dict[str, Any]],
    failure: Optional[Dict[str, Any]],
) -> None:
    """Mutate a serialized JourneyState when a service-boundary failure occurs."""
    if not isinstance(state, dict) or not isinstance(failure, dict):
        return
    stage = str(failure.get("stage") or "model")
    cards = state.get("cards")
    if not isinstance(cards, dict):
        return
    card = cards.get(stage)
    if isinstance(card, dict):
        card.update({
            "status": "failed",
            "message": failure.get("user_message") or "The run stopped.",
            "failure": failure,
            "blocked_by": None,
            "metrics": {
                "error_code": failure.get("error_code"),
                "recoverable": failure.get("recoverable"),
                "suggested_action": failure.get("suggested_action"),
                "technical_log_available": True,
            },
        })
    downstream = {
        "entrance": ("model", "artifact", "task", "optimizer", "mapping_analysis", "bind", "measurement", "translation", "execute", "evidence", "reconstruct", "convergence", "exact_reference", "verification", "meaning", "feedback"),
        "model": ("artifact", "task", "optimizer", "mapping_analysis", "bind", "measurement", "translation", "execute", "evidence", "reconstruct", "convergence", "exact_reference", "verification", "meaning", "feedback"),
        "artifact": ("task", "optimizer", "mapping_analysis", "bind", "measurement", "translation", "execute", "evidence", "reconstruct", "convergence", "exact_reference", "verification", "meaning", "feedback"),
        "task": ("optimizer", "mapping_analysis", "bind", "measurement", "translation", "execute", "evidence", "reconstruct", "convergence", "exact_reference", "verification", "meaning", "feedback"),
        "optimizer": ("bind", "measurement", "translation", "execute", "evidence", "reconstruct", "convergence", "verification", "meaning", "feedback"),
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
    }
    title = card.get("title", stage) if isinstance(card, dict) else stage
    for dependent in downstream.get(stage, ()):
        target = cards.get(dependent)
        if isinstance(target, dict) and target.get("status") in {"waiting", "running"}:
            target.update({
                "status": "blocked",
                "message": f"Not reached because {title} failed.",
                "blocked_by": stage,
                "failure": None,
                "metrics": {},
            })
    state["failed"] = True
    state["failure"] = failure
    state["global_summary"] = (
        f"Run stopped at: {title}. Open the failed station or technical log."
    )


def _remove_keys_recursively(value: Any, forbidden: set[str]) -> Any:
    if isinstance(value, dict):
        return {
            key: _remove_keys_recursively(item, forbidden)
            for key, item in value.items()
            if key not in forbidden
        }
    if isinstance(value, list):
        return [_remove_keys_recursively(item, forbidden) for item in value]
    return value


_EXACT_STATE_KEYS = {
    "target_state_amplitudes",
    "eigenvectors",
    "eigenvector",
    "reference_state",
    "reference_amplitudes",
    "exact_parameters",
    "exact_theta",
}


def public_artifact_view(artifact: Any) -> Optional[Dict[str, Any]]:
    """Expose the declared contract while withholding exact-state training data."""
    if artifact is None:
        return None
    metadata = artifact.metadata() if hasattr(artifact, "metadata") else artifact
    payload = service_json_safe(metadata)
    if not isinstance(payload, dict):
        return {"value": payload}
    payload = _remove_keys_recursively(payload, _EXACT_STATE_KEYS)

    exact_reference = payload.get("exact_reference")
    if isinstance(exact_reference, dict):
        exact_reference["exact_state_withheld_from_service_view"] = True

    fixture = payload.get("parameter_fixture")
    if isinstance(fixture, dict):
        fixture.pop("values", None)
        fixture["values_withheld_from_service_view"] = True
    return payload


def compact_result_view(result: Any) -> Optional[Dict[str, Any]]:
    """Return status-friendly output; full records remain inside the evidence ZIP."""
    if result is None:
        return None
    payload = (
        result.to_dict(include_artifacts=False)
        if hasattr(result, "to_dict")
        else service_json_safe(result)
    )
    payload = service_json_safe(payload)
    if not isinstance(payload, dict):
        return {"value": payload}

    raw_records = payload.pop("raw_records", [])
    journey_events = payload.pop("journey_events", [])
    term_expectations = payload.pop("term_expectations", {})
    payload["payload_summary"] = {
        "measurement_record_count": len(raw_records) if isinstance(raw_records, list) else 0,
        "journey_event_count": len(journey_events) if isinstance(journey_events, list) else 0,
        "term_expectation_count": len(term_expectations) if isinstance(term_expectations, dict) else 0,
        "full_payload_location": "evidence ZIP",
    }

    source = str(payload.get("parameter_source", ""))
    if "exact" in source.lower() or "fixture" in source.lower():
        payload["initial_parameters"] = {
            "withheld": True,
            "reason": "exact-derived acceptance fixture",
        }
        payload["final_parameters"] = {
            "withheld": True,
            "reason": "exact-derived acceptance fixture",
        }
    return payload


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class StoredEvent:
    id: int
    event: str
    data: Dict[str, Any]
    created_utc: str = field(default_factory=utc_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "event": self.event,
            "data": service_json_safe(self.data),
            "created_utc": self.created_utc,
        }


@dataclass
class RunRecord:
    run_id: str
    request: Dict[str, Any]
    cancellation_token: CancellationToken
    status: str = "queued"
    created_utc: str = field(default_factory=utc_now)
    started_utc: Optional[str] = None
    completed_utc: Optional[str] = None
    latest_state: Optional[Dict[str, Any]] = None
    artifact: Optional[Any] = field(default=None, repr=False)
    public_artifact: Optional[Dict[str, Any]] = None
    result: Optional[Any] = field(default=None, repr=False)
    public_result: Optional[Dict[str, Any]] = None
    advisor_context: Optional[Dict[str, Any]] = None
    advisor_report: Optional[Dict[str, Any]] = None
    advisor_error: Optional[str] = None
    parent_run_id: Optional[str] = None
    comparison_role: Optional[str] = None
    comparison_ids: list[str] = field(default_factory=list)
    phase_c: Optional[Dict[str, Any]] = None
    evidence_archive: Optional[Path] = None
    technical_error: Optional[str] = None
    failure: Optional[Dict[str, Any]] = None
    cancellation_location: Optional[str] = None
    events: list[StoredEvent] = field(default_factory=list)
    _next_event_id: int = 1
    _condition: Condition = field(default_factory=lambda: Condition(RLock()), repr=False)

    def append_event(self, event: str, data: Mapping[str, Any]) -> StoredEvent:
        with self._condition:
            created_utc = utc_now()
            payload = service_json_safe(dict(data))
            if not isinstance(payload, dict):
                payload = {"value": payload}
            nested_event = payload.get("event") if isinstance(payload.get("event"), dict) else {}
            journey = payload.get("journey_state") if isinstance(payload.get("journey_state"), dict) else {}
            failure = payload.get("failure") if isinstance(payload.get("failure"), dict) else {}
            station = (
                nested_event.get("stage")
                or failure.get("station")
                or failure.get("stage")
                or _active_stage_from_public_state(journey)
                or "service"
            )
            payload.setdefault("run_id", self.run_id)
            payload.setdefault("station", str(station))
            payload.setdefault("status", self.status)
            payload.setdefault("timestamp_utc", created_utc)
            if failure.get("code") or failure.get("error_code"):
                payload.setdefault("failure_code", failure.get("code") or failure.get("error_code"))
            item = StoredEvent(
                id=self._next_event_id,
                event=str(event),
                data=payload,
                created_utc=created_utc,
            )
            self._next_event_id += 1
            self.events.append(item)
            self._condition.notify_all()
            return item

    def snapshot(self) -> Dict[str, Any]:
        with self._condition:
            evidence_available = bool(
                self.evidence_archive and self.evidence_archive.exists()
            )
            journey_state = service_json_safe(self.latest_state)
            artifact = service_json_safe(self.public_artifact)
            result = service_json_safe(self.public_result)
            display = build_dashboard_view(
                run_id=self.run_id,
                status=self.status,
                artifact=artifact,
                result=result,
                journey_state=journey_state,
                evidence_available=evidence_available,
            )
            return {
                "run_id": self.run_id,
                "status": self.status,
                "created_utc": self.created_utc,
                "started_utc": self.started_utc,
                "completed_utc": self.completed_utc,
                "request": service_json_safe(self.request),
                "journey_state": journey_state,
                "artifact": artifact,
                "result": result,
                "advisor": service_json_safe(self.advisor_report),
                "advisor_context_available": self.advisor_context is not None,
                "advisor_error": self.advisor_error,
                "parent_run_id": self.parent_run_id,
                "comparison_role": self.comparison_role,
                "comparison_ids": list(self.comparison_ids),
                "phase_c": service_json_safe(self.phase_c),
                "display": display,
                "evidence_available": evidence_available,
                "evidence_url": (
                    f"/runs/{self.run_id}/evidence"
                    if evidence_available
                    else None
                ),
                "cancel_requested": self.cancellation_token.cancelled,
                "cancellation": self.cancellation_token.to_dict(),
                "cancellation_location": self.cancellation_location,
                "technical_error_available": self.technical_error is not None,
                "failure": service_json_safe(self.failure),
                "technical_error_url": (
                    f"/runs/{self.run_id}/technical-error"
                    if self.technical_error is not None
                    else None
                ),
                "last_event_id": self.events[-1].id if self.events else 0,
            }

    @property
    def terminal(self) -> bool:
        return self.status in TERMINAL_STATUSES

    def wait_for_events(
        self,
        *,
        after: int,
        timeout: float,
    ) -> tuple[list[StoredEvent], bool]:
        with self._condition:
            available = [event for event in self.events if event.id > after]
            if not available and not self.terminal:
                self._condition.wait(timeout=timeout)
                available = [event for event in self.events if event.id > after]
            terminal_and_drained = self.terminal and not any(
                event.id > after for event in self.events
            )
            return available, terminal_and_drained


@dataclass
class ComparisonSessionRecord:
    session_id: str
    baseline_run_id: str
    candidate_run_id: str
    advisor_card_id: str
    candidate_plan_id: str
    policy_id: str
    status: str = "waiting_for_candidate"
    created_utc: str = field(default_factory=utc_now)
    completed_utc: Optional[str] = None
    comparison: Optional[Dict[str, Any]] = None
    decision_record: Optional[Dict[str, Any]] = None
    evidence_archive: Optional[Path] = None
    error: Optional[str] = None
    _lock: RLock = field(default_factory=RLock, repr=False)

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            available = bool(self.evidence_archive and self.evidence_archive.exists())
            return {
                "schema_version": "qcol-try-compare-session/1.0",
                "session_id": self.session_id,
                "baseline_run_id": self.baseline_run_id,
                "candidate_run_id": self.candidate_run_id,
                "advisor_card_id": self.advisor_card_id,
                "candidate_plan_id": self.candidate_plan_id,
                "policy_id": self.policy_id,
                "status": self.status,
                "created_utc": self.created_utc,
                "completed_utc": self.completed_utc,
                "comparison": service_json_safe(self.comparison),
                "decision_record": service_json_safe(self.decision_record),
                "error": self.error,
                "explicit_user_approval": True,
                "same_pipeline_entrypoint": "qcol.orchestrator.run_pipeline",
                "automatic_replacement_performed": False,
                "evidence_available": available,
                "evidence_url": f"/comparisons/{self.session_id}/evidence" if available else None,
            }


class RunManager:
    """In-memory, single-process run service for the interactive QCOL runtime."""

    def __init__(
        self,
        *,
        evidence_root: Path | str = "qcol_api_evidence",
        stream_factory: Optional[StreamFactory] = None,
        state_repository: StateRepository | None = None,
    ) -> None:
        self.evidence_root = Path(evidence_root)
        self.evidence_root.mkdir(parents=True, exist_ok=True)
        self._stream_factory = stream_factory
        self._state_repository: StateRepository = state_repository or InMemoryStateRepository()
        # Backward-compatible in-memory views; the repository port is the
        # authoritative seam.  Future SQLite support replaces the adapter, not
        # the pipeline or RunManager API.
        self._records = getattr(self._state_repository, "_runs", {})
        self._comparisons = getattr(self._state_repository, "_comparisons", {})
        self._lock = RLock()

    @property
    def state_repository(self) -> StateRepository:
        return self._state_repository

    def state_boundary_contract(self) -> Dict[str, Any]:
        return {
            "schema_version": "qcol-state-boundary/1.0",
            "port": "StateRepository",
            "adapter": type(self._state_repository).__name__,
            "durable": False,
            "sqlite_implementation_deferred": True,
            "pipeline_changed": False,
        }

    def _default_stream_factory(self) -> StreamFactory:
        from .orchestrator import run_pipeline_stream

        return run_pipeline_stream

    @property
    def stream_factory(self) -> StreamFactory:
        return self._stream_factory or self._default_stream_factory()

    def create_run(self, request: Mapping[str, Any]) -> RunRecord:
        normalized_request = normalize_run_request(request)
        payload = service_json_safe(normalized_request)
        if not isinstance(payload, dict):
            raise TypeError("Run request must serialize to a JSON object.")
        run_id = f"run-{uuid4().hex[:12]}"
        record = RunRecord(
            run_id=run_id,
            request=payload,
            cancellation_token=CancellationToken(),
        )
        with self._lock:
            self._state_repository.put_run(run_id, record)
        record.append_event("run_created", record.snapshot())
        thread = Thread(
            target=self._worker,
            args=(record,),
            name=f"qcol-api-{run_id}",
            daemon=True,
        )
        thread.start()
        return record

    def _worker(self, record: RunRecord) -> None:
        record.status = "running"
        record.started_utc = utc_now()
        record.append_event("run_status", record.snapshot())
        try:
            for update in self.stream_factory(
                record.request,
                run_id=record.run_id,
                cancellation_token=record.cancellation_token,
            ):
                record.latest_state = _public_state(update.state)
                if update.artifact is not None:
                    record.artifact = update.artifact
                    record.public_artifact = public_artifact_view(update.artifact)
                    record.append_event(
                        "artifact_ready",
                        {
                            "run_id": record.run_id,
                            "artifact": record.public_artifact,
                        },
                    )
                if update.event is not None:
                    record.append_event(
                        "pipeline_event",
                        {
                            "run_id": record.run_id,
                            "event": service_json_safe(update.event),
                            "journey_state": record.latest_state,
                        },
                    )
                elif not update.done:
                    record.append_event(
                        "journey_state",
                        {
                            "run_id": record.run_id,
                            "journey_state": record.latest_state,
                        },
                    )

                if update.cancelled:
                    # Do not publish a terminal lifecycle state until the interrupted
                    # evidence archive exists.  This prevents a status/evidence race
                    # for clients that poll immediately after cancellation.
                    record.cancellation_location = "cooperative_runtime_boundary"
                    record.completed_utc = utc_now()
                    record.evidence_archive = self._write_interrupted_evidence(
                        record,
                        kind="cancelled",
                    )
                    record.status = "cancelled"
                    record.append_event("cancelled", record.snapshot())
                    return

                if update.error:
                    record.technical_error = str(update.error)
                    record.failure = service_json_safe(update.failure) if update.failure is not None else None
                    record.completed_utc = utc_now()
                    record.evidence_archive = self._write_interrupted_evidence(
                        record,
                        kind="failed",
                    )
                    record.status = "failed"
                    record.append_event("failed", record.snapshot())
                    return

                if update.done and update.result is not None:
                    record.result = update.result
                    record.public_result = compact_result_view(update.result)
                    record.completed_utc = utc_now()
                    self._evaluate_advisor_for_record(record)
                    if record.advisor_report is not None:
                        record.append_event(
                            "advisor_ready",
                            {
                                "run_id": record.run_id,
                                "advisor": record.advisor_report,
                            },
                        )
                    try:
                        record.evidence_archive = self._write_completed_evidence(record)
                    except Exception as exc:
                        from .failures import build_pipeline_failure, format_technical_error_log
                        failure = build_pipeline_failure(
                            exc,
                            run_id=record.run_id,
                            stage="evidence",
                            iteration=(record.latest_state or {}).get("current_iteration"),
                            artifact_refs=("evidence_archive",),
                        )
                        record.failure = failure.to_dict()
                        record.technical_error = format_technical_error_log(
                            failure, traceback.format_exc()
                        )
                        _apply_failure_to_public_state(record.latest_state, record.failure)
                        record.evidence_archive = self._write_interrupted_evidence(
                            record, kind="failed"
                        )
                        record.status = "failed"
                        record.append_event("failed", record.snapshot())
                        return
                    record.status = "completed"
                    record.append_event("completed", record.snapshot())
                    return

            # A stream must always end with a terminal update.
            from .failures import build_pipeline_failure, format_technical_error_log
            exc = RuntimeError("Pipeline stream ended without a terminal update.")
            failure = build_pipeline_failure(
                exc,
                run_id=record.run_id,
                stage=_active_stage_from_public_state(record.latest_state),
                iteration=(record.latest_state or {}).get("current_iteration"),
            )
            record.failure = failure.to_dict()
            record.technical_error = format_technical_error_log(failure, str(exc))
            _apply_failure_to_public_state(record.latest_state, record.failure)
            record.completed_utc = utc_now()
            record.evidence_archive = self._write_interrupted_evidence(
                record,
                kind="failed",
            )
            record.status = "failed"
            record.append_event("failed", record.snapshot())
        except Exception as exc:  # service boundary; preserve technical details in evidence
            from .failures import build_pipeline_failure, format_technical_error_log
            failure = build_pipeline_failure(
                exc,
                run_id=record.run_id,
                stage=_active_stage_from_public_state(record.latest_state),
                iteration=(record.latest_state or {}).get("current_iteration"),
            )
            record.failure = failure.to_dict()
            record.technical_error = format_technical_error_log(
                failure, traceback.format_exc()
            )
            _apply_failure_to_public_state(record.latest_state, record.failure)
            record.completed_utc = utc_now()
            record.evidence_archive = self._write_interrupted_evidence(
                record,
                kind="failed",
            )
            record.status = "failed"
            record.append_event("failed", record.snapshot())

    @staticmethod
    def advisor_enabled() -> bool:
        value = os.getenv("QCOL_ADVISOR_ENABLED", "1").strip().lower()
        return value not in {"0", "false", "off", "no", "disabled"}

    def _evaluate_advisor_for_record(
        self,
        record: RunRecord,
        *,
        previous_snapshot: Mapping[str, Any] | None = None,
    ) -> Optional[Dict[str, Any]]:
        """Build a post-run, read-only deterministic Advisor report.

        Advisor failures never change the scientific run status.  They are
        recorded separately so QCOL remains fully functional when the optional
        layer is disabled or unavailable.
        """
        try:
            from .advisor import advise_run_payload
            snapshot = record.snapshot()
            context, report = advise_run_payload(
                snapshot,
                previous_snapshot=previous_snapshot,
                enabled=self.advisor_enabled(),
            )
            record.advisor_context = service_json_safe(context.to_dict())
            record.advisor_report = service_json_safe(report.to_dict())
            record.advisor_error = None
            return record.advisor_report
        except Exception as exc:
            record.advisor_context = None
            record.advisor_report = None
            record.advisor_error = f"{type(exc).__name__}: {exc}"
            return None

    def evaluate_advisor(
        self,
        run_id: str,
        *,
        previous_run_id: str | None = None,
    ) -> Dict[str, Any]:
        record = self.get(run_id)
        if record.status != "completed" or record.public_result is None:
            raise RuntimeError("The deterministic Advisor requires a completed public run snapshot.")
        previous = None
        if previous_run_id is not None:
            previous = self.get(previous_run_id).snapshot()
        report = self._evaluate_advisor_for_record(record, previous_snapshot=previous)
        if report is None:
            raise RuntimeError(record.advisor_error or "Advisor evaluation failed.")
        record.append_event("advisor_ready", {"run_id": run_id, "advisor": report})
        return report

    def _write_completed_evidence(self, record: RunRecord) -> Optional[Path]:
        if record.artifact is None or record.result is None:
            return self._write_interrupted_evidence(record, kind="failed")
        from .evidence import save_and_archive_pipeline_evidence

        _, archive = save_and_archive_pipeline_evidence(
            record.artifact,
            record.result,
            root=self.evidence_root,
            advisor_context=record.advisor_context,
            advisor_report=record.advisor_report,
        )
        return archive

    def _write_interrupted_evidence(self, record: RunRecord, *, kind: str) -> Path:
        run_path = self.evidence_root / record.run_id
        if run_path.exists():
            shutil.rmtree(run_path)
        run_path.mkdir(parents=True)

        payloads: Dict[str, Any] = {
            "request.json": record.request,
            "journey_state.json": record.latest_state or {},
            "lifecycle.json": {
                "run_id": record.run_id,
                "status": kind,
                "created_utc": record.created_utc,
                "started_utc": record.started_utc,
                "completed_utc": record.completed_utc,
                "cancellation": record.cancellation_token.to_dict(),
                "note": "No verified RunResult exists for this interrupted run.",
            },
        }
        if record.public_artifact is not None:
            payloads["partial_problem_artifact.json"] = record.public_artifact
        if record.technical_error is not None:
            payloads["technical_error.json"] = {
                "available": True,
                "failure": record.failure,
                "error": record.technical_error,
            }

        for filename, payload in payloads.items():
            (run_path / filename).write_text(
                json.dumps(service_json_safe(payload), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        files = sorted(path for path in run_path.rglob("*") if path.is_file())
        manifest = {
            "run_id": record.run_id,
            "status": kind,
            "verified_result_available": False,
            "files": [
                {"path": str(path.relative_to(run_path)), "sha256": _sha256(path)}
                for path in files
            ],
        }
        (run_path / "manifest.json").write_text(
            json.dumps(manifest, indent=2),
            encoding="utf-8",
        )
        return Path(
            shutil.make_archive(
                str(run_path),
                "zip",
                root_dir=run_path.parent,
                base_dir=run_path.name,
            )
        )

    def start_try_compare(
        self,
        baseline_run_id: str,
        *,
        card_id: str,
        approved: bool,
        previous_run_id: str | None = None,
        policy_id: str | None = None,
    ) -> ComparisonSessionRecord:
        """Execute one explicitly approved Phase B patch through the same pipeline."""
        if approved is not True:
            raise ValueError("Phase C requires explicit user approval before candidate execution.")
        baseline = self.get(baseline_run_id)
        if baseline.status != "completed" or baseline.public_result is None:
            raise RuntimeError("Phase C requires a completed baseline run with a verified public result.")
        previous_snapshot = self.get(previous_run_id).snapshot() if previous_run_id else None
        from .advisor import advise_run_payload, prepare_candidate_request_plan
        context, report = advise_run_payload(
            baseline.snapshot(), previous_snapshot=previous_snapshot, enabled=True,
        )
        try:
            card = next(item for item in report.cards if item.card_id == card_id)
        except StopIteration as exc:
            raise KeyError(f"Advisor card {card_id!r} does not belong to this baseline run.") from exc
        plan = prepare_candidate_request_plan(baseline.request, card, approved=True)
        if plan.candidate_request is None:
            raise RuntimeError("The approved Advisor card did not produce a candidate request.")
        task_id = str((baseline.public_result or {}).get("task_id") or baseline.request.get("task_id") or "ground_state_energy")
        if policy_id is None:
            policy_id = (
                "mapping_resources_and_equivalence.v1"
                if task_id == "mapping_analysis"
                else "declared_metrics_and_uncertainty.v1"
            )
        candidate = self.create_run(plan.candidate_request)
        session_id = f"try-compare-{uuid4().hex[:12]}"
        patch_path = card.proposed_patch.field_path if card.proposed_patch is not None else ""
        candidate.parent_run_id = baseline_run_id
        candidate.comparison_role = "candidate"
        candidate.phase_c = {
            "session_id": session_id,
            "baseline_run_id": baseline_run_id,
            "advisor_card_id": card_id,
            "candidate_plan_id": plan.plan_id,
            "patch_field": patch_path,
            "patch_id": card.proposed_patch.patch_id if card.proposed_patch is not None else None,
            "explicit_user_approval": True,
            "policy_id": policy_id,
        }
        baseline.comparison_role = baseline.comparison_role or "baseline"
        baseline.phase_c = baseline.phase_c or {}
        baseline.phase_c.update({"latest_session_id": session_id})
        session = ComparisonSessionRecord(
            session_id=session_id,
            baseline_run_id=baseline_run_id,
            candidate_run_id=candidate.run_id,
            advisor_card_id=card_id,
            candidate_plan_id=plan.plan_id,
            policy_id=policy_id,
        )
        with self._lock:
            self._state_repository.put_comparison(session_id, session)
            baseline.comparison_ids.append(session_id)
            candidate.comparison_ids.append(session_id)
        baseline.append_event("comparison_started", session.snapshot())
        candidate.append_event("comparison_candidate", session.snapshot())
        Thread(
            target=self._comparison_monitor,
            args=(session_id,),
            name=f"qcol-compare-{session_id}",
            daemon=True,
        ).start()
        return session

    def _comparison_monitor(self, session_id: str) -> None:
        try:
            with self._lock:
                session = self._state_repository.get_comparison(session_id)
            if session is None:
                return
            candidate = self.get(session.candidate_run_id)
            cursor = 0
            while not candidate.terminal:
                events, _ = candidate.wait_for_events(after=cursor, timeout=0.2)
                if events:
                    cursor = events[-1].id
            self._finalize_comparison(session_id)
        except Exception as exc:
            with self._lock:
                session = self._state_repository.get_comparison(session_id)
            if session is None:
                return
            with session._lock:
                session.status = "failed"
                session.error = f"{type(exc).__name__}: {exc}"
                session.completed_utc = utc_now()

    def _finalize_comparison(self, session_id: str) -> ComparisonSessionRecord:
        with self._lock:
            session = self._state_repository.get_comparison(session_id)
        if session is None:
            raise KeyError(session_id)
        with session._lock:
            if session.status == "completed":
                return session
            if session.status == "comparing":
                return session
            session.status = "comparing"
        baseline = self.get(session.baseline_run_id)
        candidate = self.get(session.candidate_run_id)
        from .comparison import compare_runs, build_decision_record
        from .comparison.evidence import export_run_comparison_evidence
        comparison = compare_runs(
            baseline=baseline.snapshot(),
            candidate=candidate.snapshot(),
            policy=session.policy_id,
            explicit_user_approval=True,
        )
        decision = build_decision_record(comparison)
        exported = export_run_comparison_evidence(
            self.evidence_root / "comparisons",
            comparison=comparison,
            decision=decision,
            baseline_snapshot=baseline.snapshot(),
            candidate_snapshot=candidate.snapshot(),
        )
        with session._lock:
            session.comparison = comparison.to_dict()
            session.decision_record = decision.to_dict()
            session.evidence_archive = exported.archive_path
            session.status = "completed"
            session.completed_utc = utc_now()
        baseline.append_event("comparison_completed", session.snapshot())
        candidate.append_event("comparison_completed", session.snapshot())
        return session

    def get_comparison_record(self, session_id: str) -> ComparisonSessionRecord:
        with self._lock:
            session = self._state_repository.get_comparison(session_id)
        if session is None:
            raise KeyError(session_id)
        if session.status == "waiting_for_candidate":
            candidate = self.get(session.candidate_run_id)
            if candidate.terminal:
                return self._finalize_comparison(session_id)
        return session

    def get_comparison(self, session_id: str) -> Dict[str, Any]:
        return self.get_comparison_record(session_id).snapshot()

    def list_comparisons(self, *, run_id: str | None = None) -> list[Dict[str, Any]]:
        with self._lock:
            sessions = list(self._state_repository.list_comparisons())
        if run_id is not None:
            sessions = [item for item in sessions if run_id in {item.baseline_run_id, item.candidate_run_id}]
        sessions.sort(key=lambda item: item.created_utc, reverse=True)
        return [self.get_comparison(item.session_id) for item in sessions]

    def comparison_evidence_file(self, session_id: str) -> Path:
        session = self.get_comparison_record(session_id)
        if session.status != "completed":
            candidate = self.get(session.candidate_run_id)
            if candidate.terminal:
                session = self._finalize_comparison(session_id)
        archive = session.evidence_archive
        if archive is None or not archive.exists():
            raise FileNotFoundError(session_id)
        return archive

    def technical_error_info(self, run_id: str) -> Dict[str, Any]:
        record = self.get(run_id)
        if record.technical_error is None:
            raise FileNotFoundError(run_id)
        return {
            "run_id": run_id,
            "available": True,
            "failure": service_json_safe(record.failure),
            "technical_error": record.technical_error,
        }

    def get(self, run_id: str) -> RunRecord:
        with self._lock:
            record = self._state_repository.get_run(run_id)
        if record is None:
            raise KeyError(run_id)
        return record

    def list_runs(self) -> list[Dict[str, Any]]:
        with self._lock:
            records = list(self._state_repository.list_runs())
        records.sort(key=lambda record: record.created_utc, reverse=True)
        return [record.snapshot() for record in records]

    def cancel(self, run_id: str, *, reason: str = "user_requested") -> RunRecord:
        record = self.get(run_id)
        if record.terminal:
            return record
        first = record.cancellation_token.cancel(reason)
        if first:
            record.status = "cancelling"
            record.append_event("cancel_requested", record.snapshot())
        return record

    def evidence_file(self, run_id: str) -> Path:
        record = self.get(run_id)
        archive = record.evidence_archive
        if archive is None or not archive.exists():
            raise FileNotFoundError(run_id)
        return archive

    def iter_events(
        self,
        run_id: str,
        *,
        after: int = 0,
        heartbeat_seconds: float = 12.0,
    ) -> Iterator[Optional[StoredEvent]]:
        record = self.get(run_id)
        cursor = max(0, int(after))
        while True:
            events, terminal_and_drained = record.wait_for_events(
                after=cursor,
                timeout=heartbeat_seconds,
            )
            if events:
                for event in events:
                    cursor = event.id
                    yield event
                continue
            if terminal_and_drained:
                return
            yield None  # heartbeat

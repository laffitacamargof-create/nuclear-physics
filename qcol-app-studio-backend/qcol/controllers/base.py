"""Task-controller interface and neutral outcome."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Protocol


@dataclass
class ControllerOutcome:
    controller_id: str
    task_id: str
    run_mode: str
    final_execution: Mapping[str, Any]
    task_result: Dict[str, Any]
    parameter_source: str
    initial_parameters: List[float]
    final_parameters: List[float]
    history: List[Dict[str, Any]] = field(default_factory=list)
    controller_converged: bool = True
    controller_message: str = "completed"
    controller_evaluations: int = 1
    controller_tolerance: float = 0.0
    controller_name: Optional[str] = None
    controller_diagnostics: Dict[str, Any] = field(default_factory=dict)


class TaskController(Protocol):
    """Controller seam after resolution.

    The controller receives the canonical ``QuantumRealizationArtifact`` only;
    task plan and run controls are carried by that artifact.
    """

    def __call__(
        self,
        realization,
        *,
        run_id: str,
        event_callback=None,
        cancellation_token=None,
    ) -> ControllerOutcome:
        ...

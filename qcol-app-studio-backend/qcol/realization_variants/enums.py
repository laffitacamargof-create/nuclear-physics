"""WP5 resolver vocabulary for explicit realization and runtime-entry decisions."""
from __future__ import annotations

from enum import StrEnum


class RealizationTaskMode(StrEnum):
    """Whether a resolved task enters circuit execution or an analysis-only path."""

    EXECUTABLE_CIRCUIT = "executable_circuit"
    ANALYSIS_ONLY = "analysis_only"


class ResolutionStatus(StrEnum):
    """Bounded outcome of realization resolution before any scientific runtime."""

    RESOLVED = "resolved"
    RESOLVED_WITH_REVIEW = "resolved_with_review"
    REJECTED = "rejected"
    RECOGNIZED_NOT_EXECUTABLE = "recognized_not_executable"
    DEFERRED = "deferred"


class RuntimeEntryStatus(StrEnum):
    """Explicit runtime disposition; never infer it from a hidden Boolean."""

    EXECUTION_ALLOWED = "execution_allowed"
    EXECUTION_ALLOWED_WITH_REVIEW = "execution_allowed_with_review"
    ANALYSIS_ONLY_ALLOWED = "analysis_only_allowed"
    ANALYSIS_ONLY_ALLOWED_WITH_REVIEW = "analysis_only_allowed_with_review"
    BLOCKED_SCIENTIFIC = "blocked_scientific"
    RECOGNIZED_NOT_EXECUTABLE = "recognized_not_executable"
    DEFERRED = "deferred"


class RuntimePath(StrEnum):
    """Which existing QCOL service path may be invoked after resolution."""

    NONE = "none"
    ANALYSIS_CONTROLLER = "analysis_controller"
    SHARED_EXECUTION_PIPELINE = "shared_execution_pipeline"


__all__ = [
    "RealizationTaskMode",
    "ResolutionStatus",
    "RuntimeEntryStatus",
    "RuntimePath",
]

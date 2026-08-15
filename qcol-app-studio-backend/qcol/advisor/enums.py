"""Deterministic Advisor vocabulary.

The Advisor is a bounded proposer.  It reads sanitized, immutable telemetry and
never mutates scientific truth.  Only cards with an allow-listed RequestPatch
are executable hypotheses; facts and limitations carry no patch.
"""
from __future__ import annotations

from enum import StrEnum


class AdvisorStatus(StrEnum):
    READY = "ready"
    DISABLED = "disabled"
    UNAVAILABLE = "unavailable"


class RecommendationKind(StrEnum):
    VERIFIED_FACT = "verified_fact"
    PATCH_HYPOTHESIS = "patch_hypothesis"
    LIMITATION = "limitation"
    NO_ACTION = "no_action"


class RecommendationEpistemicStatus(StrEnum):
    GROUNDED = "grounded"
    HYPOTHESIS = "hypothesis"
    VERIFIED_LIMITATION = "verified_limitation"
    NO_ACTION = "no_action"


class AdvisorRulePhase(StrEnum):
    SUPPORT_BOUNDARY = "support_boundary"
    SCIENTIFIC_DIAGNOSTIC = "scientific_diagnostic"
    EXECUTION_DIAGNOSTIC = "execution_diagnostic"
    RESOURCE_DIAGNOSTIC = "resource_diagnostic"
    FALLBACK = "fallback"


class AdvisorDecision(StrEnum):
    EMIT = "emit"
    SKIP = "skip"
    BLOCKED = "blocked"


__all__ = [
    "AdvisorStatus",
    "RecommendationKind",
    "RecommendationEpistemicStatus",
    "AdvisorRulePhase",
    "AdvisorDecision",
]

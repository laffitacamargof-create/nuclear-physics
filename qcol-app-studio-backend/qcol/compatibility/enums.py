"""WP4 vocabulary for versioned compatibility rules.

These enums classify where a rule runs and whether its result belongs to a
component-to-component relation or to an invariant over the complete resolved
tuple.  They do not replace the shared WP1 status vocabulary.
"""
from __future__ import annotations

from enum import StrEnum


class CompatibilityRulePhase(StrEnum):
    """Evaluation phase for a compatibility rule."""

    PAIRWISE = "pairwise"
    GLOBAL_INVARIANT = "global_invariant"


class CompatibilityParticipant(StrEnum):
    """Named participants that may appear in a relation rule."""

    MODEL = "model"
    TASK = "task"
    MAPPING = "mapping"
    ORDERING = "ordering"
    SECTOR = "sector"
    STATE_PREPARATION = "state_preparation"
    ANSATZ = "ansatz"
    MEASUREMENT = "measurement"
    REFERENCE = "reference"
    RESOURCES = "resources"
    ACCEPTANCE_EVIDENCE = "acceptance_evidence"
    COMPLETE_TUPLE = "complete_tuple"


__all__ = ["CompatibilityRulePhase", "CompatibilityParticipant"]

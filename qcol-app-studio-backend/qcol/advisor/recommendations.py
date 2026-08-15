"""Recommendation-card helpers for Phase B.

Cards are produced by the deterministic rule engine.  This module exposes the
public contracts without introducing a second construction path.
"""
from .contracts import EvidenceReference, RecommendationCard

__all__ = ["EvidenceReference", "RecommendationCard"]

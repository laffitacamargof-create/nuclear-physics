"""Deterministic Advisor fixtures used by tests, API examples, and notebooks."""
from .context import SCENARIO_IDS, build_advisor_context_fixture
from .engine import evaluate_advisor_context


def build_advisor_report_fixture(name: str):
    context = build_advisor_context_fixture(name)
    return evaluate_advisor_context(context, enabled=True)


__all__ = ["SCENARIO_IDS", "build_advisor_context_fixture", "build_advisor_report_fixture"]

"""Certified one-pair reduced-pairing model plugin.

The package remains importable without Cirq/OpenFermion.  Runtime-heavy
builders are imported lazily when execution is requested.
"""
from .acceptance import (
    EXPECTED_FOUR_LEVEL_REFERENCE_ENERGY,
    acceptance_request,
    assess_one_pair_regression,
    assert_one_pair_regression,
)
from .bindings import (
    ONE_PAIR_POLICY_BINDINGS,
    build_one_pair_quantum_realization,
    declared_capability_report,
    declared_resolved_plan,
    model_instance_from_request,
)
from .contract import (
    FOUR_LEVEL_ACCEPTANCE_PRESET,
    GENERAL_ONE_PAIR_PRESET,
    MODEL_ID,
    MODEL_VERSION,
    ONE_PAIR_MODEL_CONTRACT,
    SUPPORTED_TASK,
)


def build_one_pair_problem_artifact(request):
    from .builder import build_one_pair_problem_artifact as _builder
    return _builder(request)


__all__ = [
    "EXPECTED_FOUR_LEVEL_REFERENCE_ENERGY",
    "FOUR_LEVEL_ACCEPTANCE_PRESET",
    "GENERAL_ONE_PAIR_PRESET",
    "MODEL_ID",
    "MODEL_VERSION",
    "ONE_PAIR_MODEL_CONTRACT",
    "ONE_PAIR_POLICY_BINDINGS",
    "SUPPORTED_TASK",
    "acceptance_request",
    "assess_one_pair_regression",
    "assert_one_pair_regression",
    "build_one_pair_problem_artifact",
    "build_one_pair_quantum_realization",
    "declared_capability_report",
    "declared_resolved_plan",
    "model_instance_from_request",
]

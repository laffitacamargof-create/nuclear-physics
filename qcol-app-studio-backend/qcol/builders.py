"""Compatibility problem builders delegated to the model registry and resolver."""
from __future__ import annotations

from typing import Any, Callable, Dict, Mapping

from .contracts import ProblemArtifact

ProblemBuilder = Callable[[Mapping[str, Any]], ProblemArtifact]
PROBLEM_BUILDERS: Dict[str, ProblemBuilder] = {}


def register_problem_builder(method: str):
    def decorator(builder: ProblemBuilder) -> ProblemBuilder:
        if method in PROBLEM_BUILDERS:
            raise KeyError(f"A builder is already registered for {method!r}.")
        PROBLEM_BUILDERS[method] = builder
        return builder
    return decorator


def _resolved_artifact(request: Mapping[str, Any]) -> ProblemArtifact:
    from .realization import resolve_request_to_quantum_realization
    return resolve_request_to_quantum_realization(request).runtime_artifact


@register_problem_builder("fermion_pairing")
def build_fermion_pairing_artifact(request: Mapping[str, Any]) -> ProblemArtifact:
    return _resolved_artifact(request)


@register_problem_builder("oscillator")
def build_oscillator_artifact(request: Mapping[str, Any]) -> ProblemArtifact:
    return _resolved_artifact(request)


@register_problem_builder("custom")
def build_custom_artifact(request: Mapping[str, Any]) -> ProblemArtifact:
    return _resolved_artifact(request)

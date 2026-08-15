"""Acceptance checks for the independent multi-pair plugin.

This suite promotes structural execution readiness.  It does not silently claim
that Bathri's first Givens ansatz reaches every exact multi-pair ground state.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import comb
from typing import Any, Dict


@dataclass(frozen=True)
class MultiPairAcceptanceReport:
    passed: bool
    checks: Dict[str, bool]
    model_id: str
    artifact_id: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "checks": dict(self.checks),
            "model_id": self.model_id,
            "artifact_id": self.artifact_id,
        }


def assess_multi_pair_artifact(artifact: Any) -> MultiPairAcceptanceReport:
    p = artifact.parameters
    n_levels = int(p["n_levels"])
    n_pairs = int(p["n_pairs"])
    context = artifact.scientific_context
    checks = {
        "canonical_model_id": artifact.model_id == "nuclear.reduced_pairing.multi_pair",
        "pair_mapping": artifact.mapping == "pair_mapping",
        "particle_pair_relation": int(p["n_particles"]) == 2 * n_pairs,
        "seniority_zero": int(p["seniority"]) == 0,
        "multi_pair_not_one_pair": n_pairs >= 2,
        "sector_dimension_recorded": int(
            artifact.provenance["quantum_realization"]["resource_report"]
            ["estimated_sector_dimension"]
        ) == comb(n_levels, n_pairs),
        "bathri_ansatz_recorded": "bathri_multi_pair" in str(
            context.get("model_contract", {}).get("policies", {}).get("ansatz", "")
        ),
        "measurement_plan_complete": bool(artifact.measurement_plan.get("groups")),
        "exact_reference_available": artifact.exact_reference is not None,
        "builder_validation_pass": all(bool(v) for v in artifact.validation_checks.values()),
    }
    return MultiPairAcceptanceReport(
        passed=all(checks.values()),
        checks=checks,
        model_id=artifact.model_id,
        artifact_id=str(artifact.artifact_id),
    )

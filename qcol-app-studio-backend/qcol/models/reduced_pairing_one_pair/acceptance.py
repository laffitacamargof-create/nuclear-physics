"""Regression anchor and promotion gate for the one-pair plugin."""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Dict, Mapping

from .contract import FOUR_LEVEL_ACCEPTANCE_PRESET, MODEL_ID, MODEL_VERSION


EXPECTED_FOUR_LEVEL_REFERENCE_ENERGY = -0.7791638468751889
REGRESSION_ENERGY_ATOL = 1e-10


@dataclass(frozen=True)
class OnePairRegressionReport:
    passed: bool
    checks: Dict[str, bool]
    observed_reference_energy: float
    expected_reference_energy: float
    artifact_id: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": bool(self.passed),
            "checks": dict(self.checks),
            "observed_reference_energy": self.observed_reference_energy,
            "expected_reference_energy": self.expected_reference_energy,
            "artifact_id": self.artifact_id,
        }


def assess_one_pair_regression(artifact: Any) -> OnePairRegressionReport:
    reference_energy = float(artifact.exact_reference["reference_energy"])
    contract_snapshot: Mapping[str, Any] = artifact.scientific_context.get("model_contract", {})
    checks = {
        "canonical_model_id": artifact.model_id == MODEL_ID,
        "canonical_model_contract_attached": (
            contract_snapshot.get("model_id") == MODEL_ID
            and contract_snapshot.get("model_version") == MODEL_VERSION
        ),
        "problem_is_four_level_acceptance": artifact.problem == "four_level_one_pair",
        "qubit_count_is_four": int(artifact.n_qubits) == 4,
        "mapping_is_pair_mapping": artifact.mapping == "pair_mapping",
        "sector_is_one_pair_seniority_zero": artifact.target_sector == {
            "particle_number": 2,
            "pair_number": 1,
            "seniority": 0,
        },
        "reference_energy_unchanged": math.isclose(
            reference_energy,
            EXPECTED_FOUR_LEVEL_REFERENCE_ENERGY,
            rel_tol=0.0,
            abs_tol=REGRESSION_ENERGY_ATOL,
        ),
        "builder_checks_pass": all(bool(v) for v in artifact.validation_checks.values()),
        "measurement_plan_present": bool(artifact.measurement_plan.get("groups")),
        "ansatz_parameter_count_unchanged": len(artifact.parameter_symbols) == 3,
    }
    return OnePairRegressionReport(
        passed=all(checks.values()),
        checks=checks,
        observed_reference_energy=reference_energy,
        expected_reference_energy=EXPECTED_FOUR_LEVEL_REFERENCE_ENERGY,
        artifact_id=str(artifact.artifact_id),
    )


def assert_one_pair_regression(artifact: Any) -> OnePairRegressionReport:
    report = assess_one_pair_regression(artifact)
    if not report.passed:
        failed = [key for key, value in report.checks.items() if not value]
        raise AssertionError(
            "One-pair regression anchor changed during plugin migration: "
            + ", ".join(failed)
        )
    return report


def acceptance_request() -> Dict[str, Any]:
    preset = FOUR_LEVEL_ACCEPTANCE_PRESET
    return {
        "method": "fermion_pairing",
        "problem": "four_level_one_pair",
        "parameters": dict(preset["parameters"]),
        "target_backend": "google",
        "execution_mode": "local_simulator",
        "run_mode": "single_evaluation",
        "shots": 512,
        "final_shots": 512,
        "seed": 42,
        "acceptance_abs_floor": 0.05,
    }

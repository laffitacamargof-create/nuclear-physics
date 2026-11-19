from __future__ import annotations

import os
import sys
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT))

from qcol.energy_bounds import check_minimum_energy_bound
from qcol.public_views import build_verification_judgments
from qcol.runtime import _ideal_statevector_energy, verify_reconstructed_result
import cirq


class MinimumEnergyBoundTests(unittest.TestCase):
    def test_roundoff_at_reference_is_accepted(self):
        result = check_minimum_energy_bound(2.4 - 1e-15, 2.4, 0.0)
        self.assertEqual(result["classification"], "ABOVE_MINIMUM")

    def test_one_sigma_sampling_dip_is_review_not_pass(self):
        result = check_minimum_energy_bound(10.0 - 0.1, 10.0, 0.1)
        self.assertEqual(result["classification"], "REVIEW_SAMPLING_BELOW_REFERENCE")
        self.assertAlmostEqual(result["z_below"], 1.0)

    def test_five_sigma_dip_is_invalid(self):
        result = check_minimum_energy_bound(10.0 - 0.5, 10.0, 0.1)
        self.assertEqual(result["classification"], "INVALID_BELOW_MINIMUM")
        self.assertAlmostEqual(result["z_below"], 5.0)

    def test_public_statistical_card_never_passes_below_reference(self):
        result = {
            "task_id": "ground_state_energy",
            "run_mode": "vqe",
            "optimizer_converged": True,
            "status": "REVIEW",
            "verification": {
                "reference_energy": 10.0,
                "absolute_error": 0.1,
                "acceptance_threshold": 1.0,
                "energy_minus_reference": -0.1,
                "minimum_energy_tolerance": 1e-9,
                "physical_bound": {
                    "classification": "REVIEW_SAMPLING_BELOW_REFERENCE"
                },
                "structural_checks": {"artifact_contract_valid": True},
            },
        }
        judgments = build_verification_judgments(result)
        self.assertNotEqual(judgments["statistical_consistency"]["status"], "PASS")
        self.assertEqual(judgments["variational_bound"]["status"], "REVIEW")

    def test_public_statistical_card_fails_significant_violation(self):
        result = {
            "task_id": "ground_state_energy",
            "run_mode": "vqe",
            "optimizer_converged": True,
            "status": "INVALID_BELOW_MINIMUM",
            "verification": {
                "reference_energy": 10.0,
                "absolute_error": 0.5,
                "acceptance_threshold": 1.0,
                "energy_minus_reference": -0.5,
                "minimum_energy_tolerance": 1e-9,
                "physical_bound": {
                    "classification": "INVALID_BELOW_MINIMUM"
                },
                "structural_checks": {"artifact_contract_valid": True},
            },
        }
        judgments = build_verification_judgments(result)
        self.assertEqual(judgments["statistical_consistency"]["status"], "FAIL")
        self.assertEqual(judgments["variational_bound"]["status"], "FAIL")


class UiRegressionTests(unittest.TestCase):
    def test_ground_state_restores_vqe_after_one_pass_task(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn('state.userRunMode || "vqe"', html)
        self.assertIn('state.taskId === "mapping_analysis"', html)

    def test_scientific_core_objects_are_rendered_as_json_not_object_string(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn('JSON.stringify(item)', html)


class RuntimeEnergyRegressionTests(unittest.TestCase):
    def test_statevector_energy_matches_pauli_expectation(self):
        qubit = cirq.LineQubit(0)
        circuit = cirq.Circuit(cirq.X(qubit))

        class LocalAdapter:
            def simulate_statevector(self, circuit, qubit_order):
                return cirq.Simulator().simulate(
                    circuit, qubit_order=qubit_order
                ).final_state_vector

        artifact = SimpleNamespace(measurement_plan={
            "identity_coefficient": 0.25,
            "groups": [{
                "terms": [{
                    "term": ((0, "Z"),),
                    "coefficient": 2.0,
                }]
            }],
        })
        energy = _ideal_statevector_energy(
            artifact, circuit, (qubit,), LocalAdapter()
        )
        self.assertAlmostEqual(energy, -1.75, places=10)

    def test_exact_statevector_violation_blocks_acceptance(self):
        artifact = SimpleNamespace(
            exact_reference={
                "reference_energy": 2.4,
                "kind": "test_reference",
                "reference_scope": "one-qubit test",
                "acceptance_abs_floor": 0.05,
            },
            validation_checks={"test_contract": True},
        )
        result = verify_reconstructed_result(
            artifact,
            {
                "translation_check": {"validated": True, "passed": True},
                "records": [],
                "energy": 2.41,
                "standard_error": 0.001,
                "ideal_statevector_energy": 2.4 - 1e-6,
            },
            {},
        )
        self.assertEqual(result["status"], "INVALID_BELOW_MINIMUM")
        self.assertEqual(
            result["physical_bound"]["classification"],
            "INVALID_BELOW_MINIMUM",
        )
        self.assertNotIn(
            "energy_not_below_declared_minimum",
            result["structural_checks"],
        )

    def test_sampling_dip_is_review_when_exact_energy_respects_bound(self):
        artifact = SimpleNamespace(
            exact_reference={
                "reference_energy": 2.4,
                "kind": "test_reference",
                "reference_scope": "one-qubit test",
                "acceptance_abs_floor": 0.05,
            },
            validation_checks={"test_contract": True},
        )
        result = verify_reconstructed_result(
            artifact,
            {
                "translation_check": {"validated": True, "passed": True},
                "records": [],
                "energy": 2.39,
                "standard_error": 0.02,
                "ideal_statevector_energy": 2.41,
            },
            {},
        )
        self.assertEqual(result["status"], "REVIEW")
        self.assertEqual(
            result["physical_bound"]["classification"],
            "REVIEW_SAMPLING_BELOW_REFERENCE",
        )
        self.assertFalse(result["accepted"])


class ConnectorContractTests(unittest.TestCase):
    def test_connector_exposes_all_ui_routes(self):
        import qcol_app_studio_connector as connector

        routes = {
            (method, route.path)
            for route in connector.app.routes
            for method in getattr(route, "methods", set())
        }
        required = {
            ("GET", "/catalog/model-task-realizations"),
            ("GET", "/runs"),
            ("POST", "/runs/{run_id}/cancel"),
            ("GET", "/runs/{run_id}/technical-error"),
            ("POST", "/runs/{run_id}/advisor/prepare-candidate"),
            ("POST", "/runs/{baseline_run_id}/try-compare"),
            ("GET", "/comparisons/{session_id}"),
        }
        self.assertTrue(required.issubset(routes), sorted(required - routes))

    def test_custom_cors_does_not_drop_github_pages(self):
        from qcol.api import _cors_origins

        with patch.dict(os.environ, {"QCOL_CORS_ORIGINS": "https://example.test"}):
            origins = _cors_origins()
        self.assertIn("https://laffitacamargof-create.github.io", origins)
        self.assertIn("https://example.test", origins)


if __name__ == "__main__":
    unittest.main()

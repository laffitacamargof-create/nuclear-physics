"""Deterministic WP4 fixtures for positive and negative rule evaluation."""
from __future__ import annotations

import copy
from typing import Any, Mapping

from .rule_contracts import RuleEvaluationContext


_SHARED_CONTEXT = "encoding-context-jw-four-modes-v1"
_SECTOR_FINGERPRINT = "sector-neutron-number-2-v1"
_PROBLEM_FINGERPRINT = "problem-general-spin-orbital-4m-2n-v1"
_ACCEPTANCE_FINGERPRINT = "accepted-tuple-general-spin-orbital-jw-v1"


def _base_payload() -> dict[str, Any]:
    component_contexts = {
        "model": _SHARED_CONTEXT,
        "task": _SHARED_CONTEXT,
        "mapping": _SHARED_CONTEXT,
        "sector": _SHARED_CONTEXT,
        "state_preparation": _SHARED_CONTEXT,
        "ansatz": _SHARED_CONTEXT,
        "measurement": _SHARED_CONTEXT,
        "reference": _SHARED_CONTEXT,
        "resources": _SHARED_CONTEXT,
    }
    return {
        "context_id": "wp4.valid-execution-tuple.v1",
        "context_version": "1.0.0",
        "model": {
            "model_id": "fermion.general_spin_orbital",
            "operator_type": "FermionOperator",
            "physical_domain": "general_spin_orbital",
            "metadata": {
                "n_modes": 4,
                "mode_ordering_id": "spin-orbital-order.4m.v1",
                "particle_numbers": {"neutron": 2},
            },
            "hermitian": True,
            "declared_symmetries": ["particle_number"],
            "verified_symmetries": ["particle_number"],
            "source_problem_fingerprint": _PROBLEM_FINGERPRINT,
            "units": "MeV",
            "declared_scale": {"n_modes": 4, "n_particles": 2},
            "encoding_context_fingerprint": _SHARED_CONTEXT,
        },
        "task": {
            "task_id": "ground_state_energy",
            "required_operator_kinds": ["hamiltonian", "particle_number"],
            "required_conserved_quantities": ["particle_number"],
            "requires_state_preparation": True,
            "requires_ansatz": True,
            "requires_measurement": True,
            "target_quantity": "ground_state_energy",
            "units": "MeV",
            "encoding_context_fingerprint": _SHARED_CONTEXT,
        },
        "mapping": {
            "policy_id": "jordan_wigner.policy.fixture.v1",
            "mapping_id": "jordan_wigner.v1",
            "family": "jordan_wigner",
            "mapping_scope": "full_fermionic_fock_space",
            "algebra_scope": "canonical_anticommutation_relations",
            "convention_id": "openfermion.jw.little_endian.v1",
            "accepted_operator_types": ["FermionOperator"],
            "allowed_physical_domains": ["general_spin_orbital"],
            "required_model_metadata": [
                "n_modes",
                "mode_ordering_id",
                "particle_numbers",
            ],
            "requires_hermitian_hamiltonian": True,
            "required_symmetries": ["particle_number"],
            "encoding_context_fingerprint": _SHARED_CONTEXT,
            "sector_profiles": [
                {
                    "quantity_id": "particle_number",
                    "representation_kind": "direct_popcount",
                    "diagnostic_policy_id": "jw.particle-number-diagnostic.v1",
                    "support_status": "verified",
                }
            ],
            "raw_popcount_is_particle_number": True,
            "requires_state_capabilities": [
                "mapping_aware_basis_encoding",
                "target_sector_preparation",
                "mode_order_aware",
            ],
            "requires_ansatz_capabilities": [
                "mapped_generator_semantics",
                "particle_number_preserving",
                "mode_order_aware",
            ],
            "transformable_operator_kinds": [
                "hamiltonian",
                "particle_number",
                "occupation",
                "single_excitation",
            ],
        },
        "ordering": {
            "ordering_id": "spin-orbital-order.4m.v1",
            "encoding_context_fingerprint": _SHARED_CONTEXT,
            "required_components": list(component_contexts),
            "component_context_fingerprints": component_contexts,
        },
        "sector": {
            "sector_fingerprint": _SECTOR_FINGERPRINT,
            "required_quantities": ["particle_number"],
            "target": {"particle_number": 2},
            "encoding_context_fingerprint": _SHARED_CONTEXT,
        },
        "state_preparation": {
            "policy_id": "jw.occupation-determinant-state.v1",
            "mapping_policy_id": "jordan_wigner.policy.fixture.v1",
            "mapping_convention_id": "openfermion.jw.little_endian.v1",
            "encoding_context_fingerprint": _SHARED_CONTEXT,
            "provided_capabilities": [
                "mapping_aware_basis_encoding",
                "target_sector_preparation",
                "mode_order_aware",
            ],
            "encoded_state_in_code_space": True,
            "target_sector_match": True,
        },
        "ansatz": {
            "policy_id": "jw.mapped-fermionic-single-excitation.v1",
            "semantic_class": "mapped_fermionic_generator",
            "mapping_policy_id": "jordan_wigner.policy.fixture.v1",
            "mapping_convention_id": "openfermion.jw.little_endian.v1",
            "encoding_context_fingerprint": _SHARED_CONTEXT,
            "provided_capabilities": [
                "mapped_generator_semantics",
                "particle_number_preserving",
                "mode_order_aware",
            ],
            "particle_number_preserving": True,
            "hamming_weight_preserving": True,
            "declared_invariants_preserved": True,
            "nonadjacent_sign_test_passed": True,
            "generator_equivalence_evidence": {
                "passed": True,
                "freshness_status": "current",
                "fingerprint": "jw-generator-equivalence-fixture-v1",
            },
        },
        "measurement": {
            "policy_id": "pauli-energy-qwc.v1",
            "supported_operator_kinds": ["hamiltonian", "particle_number"],
            "encoding_context_fingerprint": _SHARED_CONTEXT,
        },
        "reference": {
            "policy_id": "small-exact-fixed-particle-reference.v1",
            "source_problem_fingerprint": _PROBLEM_FINGERPRINT,
            "task_id": "ground_state_energy",
            "quantity_id": "ground_state_energy",
            "units": "MeV",
            "encoding_context_fingerprint": _SHARED_CONTEXT,
            "sector_fingerprint": _SECTOR_FINGERPRINT,
            "constant_shift": 0.0,
            "independent": True,
            "constructed_from_tested_mapping": False,
            "validity_envelope": {"max_n_modes": 6},
        },
        "resources": {
            "encoding_context_fingerprint": _SHARED_CONTEXT,
            "within_declared_envelope": True,
            "estimate": {
                "n_qubits": 4,
                "parameter_count": 16,
                "pauli_term_count": 15,
            },
            "envelope": {
                "max_n_qubits": 8,
                "max_parameter_count": 64,
                "max_pauli_term_count": 256,
            },
            "exceeded_dimensions": [],
        },
        "acceptance_evidence": {
            "resolved_variant_fingerprint": _ACCEPTANCE_FINGERPRINT,
            "evidence_fingerprint": _ACCEPTANCE_FINGERPRINT,
            "freshness_status": "current",
            "policy_versions_match": True,
            "declared_scale_matches": True,
        },
        "complete_tuple": {
            "model_id": "fermion.general_spin_orbital",
            "task_id": "ground_state_energy",
            "mapping_policy_id": "jordan_wigner.policy.fixture.v1",
            "encoding_context_fingerprint": _SHARED_CONTEXT,
            "sector_fingerprint": _SECTOR_FINGERPRINT,
            "resolved_variant_fingerprint": _ACCEPTANCE_FINGERPRINT,
        },
    }


def build_valid_execution_context() -> RuleEvaluationContext:
    return RuleEvaluationContext(**_base_payload())


def build_mapping_analysis_context() -> RuleEvaluationContext:
    payload = _base_payload()
    payload["context_id"] = "wp4.mapping-analysis-tuple.v1"
    payload["task"].update(
        {
            "task_id": "mapping_analysis",
            "required_operator_kinds": ["hamiltonian", "particle_number"],
            "requires_state_preparation": False,
            "requires_ansatz": False,
            "requires_measurement": False,
            "target_quantity": "mapping_equivalence",
        }
    )
    payload["reference"].update(
        {
            "task_id": "mapping_analysis",
            "quantity_id": "mapping_equivalence",
        }
    )
    payload["state_preparation"] = {}
    payload["ansatz"] = {}
    payload["measurement"] = {}
    component_contexts = payload["ordering"]["component_context_fingerprints"]
    for key in ("state_preparation", "ansatz", "measurement"):
        component_contexts.pop(key, None)
    payload["ordering"]["required_components"] = list(component_contexts)
    payload["complete_tuple"]["task_id"] = "mapping_analysis"
    return RuleEvaluationContext(**payload)


def build_known_invalid_jw_context() -> RuleEvaluationContext:
    payload = _base_payload()
    payload["context_id"] = "wp4.known-invalid-jw-composition.v1"
    payload["ansatz"] = {
        "policy_id": "legacy.bare-qubit-exchange.v1",
        "semantic_class": "qubit_native",
        "mapping_policy_id": "jordan_wigner.policy.fixture.v1",
        "mapping_convention_id": "openfermion.jw.little_endian.v1",
        "encoding_context_fingerprint": _SHARED_CONTEXT,
        "provided_capabilities": [
            "particle_number_preserving",
            "mode_order_aware",
        ],
        "particle_number_preserving": True,
        "hamming_weight_preserving": True,
        "declared_invariants_preserved": True,
        "nonadjacent_sign_test_passed": False,
        "generator_equivalence_evidence": {
            "passed": False,
            "freshness_status": "current",
            "failure": "nonadjacent_fermionic_sign_mismatch",
        },
    }
    return RuleEvaluationContext(**payload)


def _mutated_context(
    context_id: str,
    mutator,
) -> RuleEvaluationContext:
    payload = copy.deepcopy(_base_payload())
    payload["context_id"] = context_id
    mutator(payload)
    return RuleEvaluationContext(**payload)


def build_negative_rule_contexts() -> Mapping[str, RuleEvaluationContext]:
    def domain(payload: dict[str, Any]) -> None:
        payload["model"]["physical_domain"] = "broken_pair_shell_model"

    def ordering(payload: dict[str, Any]) -> None:
        payload["ordering"]["component_context_fingerprints"]["ansatz"] = (
            "different-encoding-context-v1"
        )

    def sector(payload: dict[str, Any]) -> None:
        payload["mapping"]["sector_profiles"][0].update(
            {
                "representation_kind": "unsupported",
                "diagnostic_policy_id": "",
            }
        )

    def state(payload: dict[str, Any]) -> None:
        payload["state_preparation"]["mapping_convention_id"] = (
            "openfermion.bk.fenwick.v1"
        )

    def ansatz(payload: dict[str, Any]) -> None:
        invalid = build_known_invalid_jw_context().to_dict()["ansatz"]
        payload["ansatz"] = invalid

    def task(payload: dict[str, Any]) -> None:
        payload["task"]["required_operator_kinds"].append(
            "time_evolution_generator"
        )

    def reference(payload: dict[str, Any]) -> None:
        payload["reference"]["source_problem_fingerprint"] = (
            "different-source-problem-v1"
        )

    def resources(payload: dict[str, Any]) -> None:
        payload["resources"].update(
            {
                "within_declared_envelope": False,
                "estimate": {"n_qubits": 20, "parameter_count": 640},
                "exceeded_dimensions": ["n_qubits", "parameter_count"],
            }
        )

    def acceptance(payload: dict[str, Any]) -> None:
        payload["acceptance_evidence"].update(
            {
                "evidence_fingerprint": "stale-four-mode-evidence-v0",
                "freshness_status": "stale",
                "policy_versions_match": False,
                "declared_scale_matches": False,
            }
        )

    return {
        "model_mapping.domain.v1": _mutated_context(
            "wp4.negative.model-mapping-domain.v1", domain
        ),
        "ordering.same_context.v1": _mutated_context(
            "wp4.negative.ordering-context.v1", ordering
        ),
        "mapping_sector.representation.v1": _mutated_context(
            "wp4.negative.mapping-sector.v1", sector
        ),
        "mapping_state.encoder_match.v1": _mutated_context(
            "wp4.negative.mapping-state.v1", state
        ),
        "mapping_ansatz.generator_semantics.v1": build_known_invalid_jw_context(),
        "mapping_task.all_operators_mapped.v1": _mutated_context(
            "wp4.negative.mapping-task.v1", task
        ),
        "model_task_reference.same_problem.v1": _mutated_context(
            "wp4.negative.reference.v1", reference
        ),
        "composition.resource_envelope.v1": _mutated_context(
            "wp4.negative.resources.v1", resources
        ),
        "composition.acceptance_fingerprint.v1": _mutated_context(
            "wp4.negative.acceptance-fingerprint.v1", acceptance
        ),
    }


__all__ = [
    "build_valid_execution_context",
    "build_mapping_analysis_context",
    "build_known_invalid_jw_context",
    "build_negative_rule_contexts",
]

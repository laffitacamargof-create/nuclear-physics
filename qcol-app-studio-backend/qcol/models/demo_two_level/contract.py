"""Declarative contract for the Step-3 two-level extensibility drill.

This model is an internal architecture fitness fixture, not a published nuclear
model.  It deliberately reuses existing scientific policies so that Step 3
measures the extension seam rather than introducing another runtime path.
"""
from __future__ import annotations

from ...model_contracts import (
    MODEL_CONTRACT_SCHEMA_VERSION_1_3,
    ModelClassificationContract,
    ModelContract,
    ParameterSpec,
    ReferenceValidity,
    ResourceValidityEnvelope,
)
from ...resource_rules import ONE_EXCITATION_RULE_ID

MODEL_ID = "demo.two_level.v1"
MODEL_VERSION = "1.0.0"
TASK_ID = "ground_state_energy"
ENCODING_CONTEXT_ID = "demo_two_level_computational_basis.v1"
MAPPING_POLICY_ID = "identity_qubit_mapping.v1"

DEMO_TWO_LEVEL_MODEL_CONTRACT = ModelContract(
    model_id=MODEL_ID,
    model_version=MODEL_VERSION,
    label="Two-level extensibility drill",
    description=(
        "Internal two-mode, one-excitation model used only to prove that a new "
        "scientifically bounded model can enter QCOL through one plugin, one "
        "registration seam, the existing Capability Resolver, and the shared pipeline."
    ),
    domain="architecture_fitness",
    family="demo_two_level",
    problem_type="two_mode_one_excitation",
    supported_tasks=(TASK_ID,),
    parameter_schema=(
        ParameterSpec(
            "n_modes",
            "Number of computational modes",
            "integer",
            role="fixed",
            default=2,
            fixed_value=2,
            visible=False,
            order=10,
        ),
        ParameterSpec(
            "omega",
            "Mode energies",
            "vector_or_scalar",
            role="fixed",
            default=(1.0, 2.0),
            fixed_value=(1.0, 2.0),
            visible=False,
            order=20,
        ),
        ParameterSpec(
            "coupling",
            "Mode coupling",
            "matrix_or_scalar",
            role="fixed",
            default=0.0,
            fixed_value=0.0,
            visible=False,
            order=30,
        ),
        ParameterSpec(
            "kappa",
            "Diagonal mode shift",
            "vector_or_scalar",
            role="fixed",
            default=0.0,
            fixed_value=0.0,
            visible=False,
            order=40,
        ),
        ParameterSpec(
            "n_quanta",
            "Target excitation number",
            "integer",
            role="fixed",
            default=1,
            fixed_value=1,
            visible=False,
            order=50,
        ),
        ParameterSpec(
            "energy_unit",
            "Energy unit",
            "text",
            role="fixed",
            default="dimensionless",
            fixed_value="dimensionless",
            visible=False,
            order=60,
        ),
    ),
    units={
        "energy": "declared_by_instance",
        "omega": "same_as_energy",
        "coupling": "same_as_energy",
        "kappa": "same_as_energy",
    },
    conserved_quantities=("excitation_number",),
    sector_schema={"excitation_number": {"fixed": 1}},
    supported_observables=("sector_energy",),
    hamiltonian_policy_id="hard_core_oscillator_hamiltonian.v1",
    sector_policy_id="one_excitation_sector.v1",
    mapping_policy_id=MAPPING_POLICY_ID,
    state_preparation_policy_id="lowest_mode_state.v1",
    ansatz_policy_id="one_excitation_chain_givens.v1",
    measurement_policy_id="pauli_energy_qwc.v1",
    reference_policy_id="small_exact_one_excitation_sector.v1",
    resource_policy_id="bounded_direct_qubit.v2",
    runtime_policy_id="external_variational_energy.v1",
    interpretation_policy_id="hard_core_oscillator_energy.v1",
    reference_validity=ReferenceValidity(
        reference_kind="deterministic_two_by_two_exact_diagonalisation",
        validity_statement=(
            "Exact in the two-dimensional one-excitation sector of the fixed "
            "two-mode architecture fixture."
        ),
        exact_within_declared_model=True,
        maximum_dimension=2,
        maximum_qubits=2,
        parameter_conditions={"n_modes": 2, "n_quanta": 1},
        fallback_policy="no_fallback_architecture_fixture",
    ),
    resource_validity=ResourceValidityEnvelope(
        simulator_max_qubits=2,
        exact_semantic_check_max_qubits=2,
        maximum_parameter_count=1,
        notes=(
            "Architecture fitness fixture only; excluded from the production model menu.",
        ),
    ),
    resource_estimation_rule_id=ONE_EXCITATION_RULE_ID,
    representation_contract={
        "representation_kind": "two_mode_computational_basis",
        "basis_semantics": "one qubit per declared mode with one excitation",
        "encoding_policy_id": MAPPING_POLICY_ID,
        "encoding_context_id": ENCODING_CONTEXT_ID,
        "target_sector": {"excitation_number": 1},
        "production_feature": False,
    },
    classification=ModelClassificationContract(
        classification_id="classification.demo.two_level.v1",
        classification_version="1.0.0",
        ui_group_id="internal_architecture_test",
        ui_group_label="Internal architecture test",
        discovery_tags=("extension_drill", "two_level", "test_only"),
        notes=(
            "Not exposed in the production navigation surface.",
            "The classification is discovery metadata only.",
        ),
    ),
    physical_phenomena=("bounded_two_level_transition",),
    degrees_of_freedom=("two_hard_core_modes",),
    hamiltonian_components=("onsite_mode_energy",),
    compatible_mapping_ids=(MAPPING_POLICY_ID,),
    assumptions=(
        "two computational modes",
        "fixed one-excitation sector",
        "identity qubit encoding",
    ),
    limitations=(
        "architecture conformance fixture; not a supported nuclear model",
        "not shown in the production UI",
    ),
    support_status="registered",
    execution_status="execution_ready",
    scientific_owner="QCOL architecture fitness suite",
    scientific_review_status="test-only bounded exact fixture",
    acceptance_suite_id="acceptance.demo.two_level.extension_drill.v1",
    schema_version=MODEL_CONTRACT_SCHEMA_VERSION_1_3,
)

__all__ = [
    "MODEL_ID",
    "MODEL_VERSION",
    "TASK_ID",
    "ENCODING_CONTEXT_ID",
    "MAPPING_POLICY_ID",
    "DEMO_TWO_LEVEL_MODEL_CONTRACT",
]

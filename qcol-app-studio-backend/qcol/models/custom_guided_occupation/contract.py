"""Contract for the no-code custom occupation/coupling model."""
from __future__ import annotations

from ...model_contracts import (
    MODEL_CONTRACT_SCHEMA_VERSION_1_3,
    ModelClassificationContract,
    ModelContract,
    ParameterSpec,
    ReferenceValidity,
    ResourceValidityEnvelope,
)

MODEL_ID = "custom.occupation_coupling.one_excitation"
MODEL_VERSION = "1.0.0"
SUPPORTED_TASK = "sector_ground_state_energy"

CUSTOM_GUIDED_MODEL_CONTRACT = ModelContract(
    model_id=MODEL_ID,
    model_version=MODEL_VERSION,
    label="Custom guided occupation-coupling model",
    description=(
        "No-code bounded model H=E0+sum epsilon_i n_i - 1/2 sum G_ij(XX+YY), "
        "resolved in the fixed one-excitation sector."
    ),
    domain="custom_model",
    family="guided_occupation_coupling",
    problem_type="one_excitation_custom_model",
    supported_tasks=("ground_state_energy", "sector_ground_state_energy"),
    parameter_schema=(
        ParameterSpec("model_name", "Model name", "text", default="custom occupation-coupling model", order=5),
        ParameterSpec("n_modes", "Number of modes", "integer", default=4, minimum=2, maximum=6, step=1, order=10),
        ParameterSpec("onsite_energies", "Onsite energies", "vector", default=(0.0,1.0,2.0,3.0), length_from="n_modes", item_kind="number", unit_key="energy_unit", order=20),
        ParameterSpec("coupling_matrix", "Pairwise couplings", "matrix_or_scalar", default=0.2, unit_key="energy_unit", order=30),
        ParameterSpec("energy_offset", "Energy offset", "number", default=0.0, unit_key="energy_unit", order=40),
        ParameterSpec("n_excitations", "Target excitations", "integer", role="fixed", default=1, fixed_value=1, order=50),
        ParameterSpec("energy_unit", "Energy unit", "text", default="MeV", order=60),
    ),
    units={"energy":"declared_by_instance", "onsite_energies":"same_as_energy", "coupling_matrix":"same_as_energy"},
    conserved_quantities=("excitation_number",),
    sector_schema={"excitation_number":{"fixed":1}},
    supported_observables=("sector_energy", "mode_occupations_when_measured"),
    hamiltonian_policy_id="guided_occupation_hamiltonian.v1",
    sector_policy_id="one_excitation_sector.v1",
    mapping_policy_id="direct_guided_occupation_encoding.v1",
    state_preparation_policy_id="lowest_mode_state.v1",
    ansatz_policy_id="one_excitation_chain_givens.v1",
    measurement_policy_id="pauli_energy_qwc.v1",
    reference_policy_id="small_exact_one_excitation_sector.v1",
    resource_policy_id="bounded_direct_qubit.v1",
    runtime_policy_id="external_variational_energy.v1",
    interpretation_policy_id="guided_occupation_energy.v1",
    reference_validity=ReferenceValidity(
        reference_kind="exact_one_excitation_sector_diagonalisation",
        validity_statement="Exact for the bounded declared one-excitation custom model.",
        exact_within_declared_model=True,
        maximum_dimension=6,
        maximum_qubits=6,
        parameter_conditions={"n_excitations":1, "n_modes":{"minimum":2,"maximum":6}},
        fallback_policy="limited_verification_outside_declared_envelope",
    ),
    resource_validity=ResourceValidityEnvelope(
        simulator_max_qubits=6,
        exact_semantic_check_max_qubits=6,
        maximum_parameter_count=5,
        notes=("Bounded no-code technical route, not automatic ingestion of experimental data.",),
    ),
    representation_contract={
        "representation_kind": "hard_core_mode_occupation",
        "basis_semantics": "one binary occupation variable per declared mode",
        "encoding_policy_id": "direct_guided_occupation_encoding.v1",
    },
    classification=ModelClassificationContract(
        classification_id="classification.custom.occupation_coupling.one_excitation.v1",
        classification_version="1.0.0",
        ui_group_id="custom",
        ui_group_label="Custom",
        discovery_tags=('user_declared_occupation_coupling', 'hard_core_modes'),
        notes=("The UI group is navigation metadata only.",),
    ),
    physical_phenomena=('user_declared_occupation_coupling_model',),
    degrees_of_freedom=('hard_core_modes',),
    hamiltonian_components=('onsite_energy', 'xx_yy_coupling', 'constant_offset'),
    assumptions=("hard-core occupation variables", "one-excitation sector"),
    limitations=("not a general fermionic model", "not automatic Hamiltonian inference from raw experiments"),
    support_status="execution_ready",
    execution_status="execution_ready",
    scientific_owner="QCOL user-supplied model route",
    scientific_review_status="user-declared model; bounded technical validation",
    acceptance_suite_id="acceptance.custom.occupation_coupling.one_excitation.v1",
    schema_version=MODEL_CONTRACT_SCHEMA_VERSION_1_3,
)

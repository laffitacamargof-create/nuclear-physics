"""Model contract for the bounded hard-core oscillator integration route."""
from __future__ import annotations

from ...model_contracts import (
    MODEL_CONTRACT_SCHEMA_VERSION_1_3,
    ModelClassificationContract,
    ModelContract,
    ParameterSpec,
    ReferenceValidity,
    ResourceValidityEnvelope,
)

MODEL_ID = "nuclear.oscillator.hard_core.one_quantum"
MODEL_VERSION = "1.0.0"
SUPPORTED_TASK = "sector_ground_state_energy"

OSCILLATOR_MODEL_CONTRACT = ModelContract(
    model_id=MODEL_ID,
    model_version=MODEL_VERSION,
    label="Quantum oscillator — two-level hard-core modes",
    description=(
        "One qubit per oscillator mode with occupation n_k in {0,1}, bounded to "
        "the one-quantum sector in the current shared variational-energy runtime."
    ),
    domain="nuclear_collective",
    family="hard_core_oscillator",
    problem_type="coupled_modes_one_quantum",
    supported_tasks=("ground_state_energy", "sector_ground_state_energy"),
    parameter_schema=(
        ParameterSpec("n_modes", "Number of modes", "integer", default=4, minimum=2, maximum=6, step=1, order=10),
        ParameterSpec("omega", "Mode frequencies ω", "vector_or_scalar", default=1.0, unit_key="energy_unit", order=20),
        ParameterSpec("coupling", "Mode coupling G", "matrix_or_scalar", default=0.2, unit_key="energy_unit", order=30),
        ParameterSpec("kappa", "Mode shifts κ", "vector_or_scalar", default=0.0, unit_key="energy_unit", order=40),
        ParameterSpec("n_quanta", "Target quanta", "integer", role="fixed", default=1, fixed_value=1, order=50),
        ParameterSpec("energy_unit", "Energy unit", "text", default="MeV", order=60),
    ),
    units={"energy": "declared_by_instance", "omega": "same_as_energy", "coupling": "same_as_energy", "kappa": "same_as_energy"},
    conserved_quantities=("excitation_number",),
    sector_schema={"excitation_number": {"fixed": 1}},
    supported_observables=("sector_energy", "mode_occupations_when_measured"),
    hamiltonian_policy_id="hard_core_oscillator_hamiltonian.v1",
    sector_policy_id="one_excitation_sector.v1",
    mapping_policy_id="direct_hard_core_mode_encoding.v1",
    state_preparation_policy_id="lowest_mode_state.v1",
    ansatz_policy_id="one_excitation_chain_givens.v1",
    measurement_policy_id="pauli_energy_qwc.v1",
    reference_policy_id="small_exact_one_excitation_sector.v1",
    resource_policy_id="bounded_direct_qubit.v1",
    runtime_policy_id="external_variational_energy.v1",
    interpretation_policy_id="hard_core_oscillator_energy.v1",
    reference_validity=ReferenceValidity(
        reference_kind="exact_one_excitation_sector_diagonalisation",
        validity_statement="Exact within the declared hard-core one-quantum model and bounded mode count.",
        exact_within_declared_model=True,
        maximum_dimension=6,
        maximum_qubits=6,
        parameter_conditions={"n_quanta": 1, "n_modes": {"minimum": 2, "maximum": 6}},
        fallback_policy="limited_verification_outside_declared_envelope",
    ),
    resource_validity=ResourceValidityEnvelope(
        simulator_max_qubits=6,
        exact_semantic_check_max_qubits=6,
        maximum_parameter_count=5,
        notes=("Integration prototype; not a full bosonic Fock-space oscillator.",),
    ),
    representation_contract={
        "representation_kind": "hard_core_oscillator_occupation",
        "basis_semantics": "one qubit per mode with binary occupation",
        "encoding_policy_id": "direct_hard_core_mode_encoding.v1",
        "target_sector": {"excitation_number": 1},
    },
    classification=ModelClassificationContract(
        classification_id="classification.nuclear.oscillator.hard_core.one_quantum.v1",
        classification_version="1.0.0",
        ui_group_id="oscillators",
        ui_group_label="Oscillators",
        discovery_tags=('bounded_oscillator', 'hard_core_modes', 'binary_occupation'),
        notes=("Legacy compatibility route; the UI group is navigation metadata only.",),
    ),
    physical_phenomena=('bounded_oscillator_or_vibrational_model',),
    degrees_of_freedom=('hard_core_oscillator_modes',),
    hamiltonian_components=('onsite_mode_energy', 'xx_yy_coupling', 'diagonal_mode_shift'),
    assumptions=("two-level hard-core occupation per mode", "fixed one-quantum sector"),
    limitations=("not a full bosonic Fock-space oscillator", "scientific review remains with the oscillator module owner"),
    support_status="execution_ready",
    execution_status="experimental",
    scientific_owner="Deepak Chauhan",
    scientific_review_status="integration prototype; module-owner review pending",
    acceptance_suite_id="acceptance.nuclear.oscillator.hard_core.one_quantum.v1",
    schema_version=MODEL_CONTRACT_SCHEMA_VERSION_1_3,
)

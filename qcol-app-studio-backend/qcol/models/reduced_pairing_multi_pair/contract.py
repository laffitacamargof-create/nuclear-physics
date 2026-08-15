"""Neutral contract for the independent multi-pair seniority-zero plugin."""
from __future__ import annotations

from ...model_contracts import (
    MODEL_CONTRACT_SCHEMA_VERSION_1_3,
    ModelContract,
    ModelClassificationContract,
    ParameterSpec,
    ReferenceValidity,
    ResourceValidityEnvelope,
)

MODEL_ID = "nuclear.reduced_pairing.multi_pair"
MODEL_VERSION = "1.0.0"
SUPPORTED_TASK = "sector_ground_state_energy"

MULTI_PAIR_MODEL_CONTRACT = ModelContract(
    model_id=MODEL_ID,
    model_version=MODEL_VERSION,
    label="Reduced pairing — multi-pair seniority-zero",
    description=(
        "Two or more correlated fermion pairs distributed across a bounded set "
        "of single-particle levels under the reduced attractive pairing Hamiltonian."
    ),
    domain="nuclear_fermionic",
    family="reduced_pairing",
    problem_type="multi_pair_seniority_zero",
    supported_tasks=("ground_state_energy", "sector_ground_state_energy"),
    parameter_schema=(
        ParameterSpec(
            key="n_levels",
            label="Number of levels",
            kind="integer",
            role="editable",
            default=4,
            minimum=4,
            maximum=6,
            step=1,
            help_text="Bounded acceptance envelope for the first independent multi-pair plugin.",
            order=10,
        ),
        ParameterSpec(
            key="epsilon",
            label="Single-particle energies ε",
            kind="vector",
            role="editable",
            default=(0.0, 1.0, 2.0, 3.0),
            length_from="n_levels",
            item_kind="number",
            unit_key="energy_unit",
            help_text="Exactly one finite energy per declared level.",
            order=20,
        ),
        ParameterSpec(
            key="g",
            label="Pairing strength G",
            kind="number",
            role="editable",
            default=0.5,
            minimum=0.0,
            step=0.01,
            unit_key="energy_unit",
            help_text="Finite attractive pairing strength; G must be strictly positive.",
            order=30,
        ),
        ParameterSpec(
            key="n_pairs",
            label="Number of pairs",
            kind="integer",
            role="editable",
            default=2,
            minimum=2,
            maximum=3,
            step=1,
            help_text="Must satisfy 2 <= n_pairs < n_levels.",
            order=40,
        ),
        ParameterSpec(
            key="n_particles",
            label="Number of particles",
            kind="integer",
            role="derived",
            default=4,
            help_text="Derived as 2 × n_pairs.",
            order=50,
        ),
        ParameterSpec(
            key="seniority",
            label="Seniority",
            kind="integer",
            role="fixed",
            default=0,
            fixed_value=0,
            help_text="The first multi-pair route remains in the seniority-zero sector.",
            order=60,
        ),
        ParameterSpec(
            key="energy_unit",
            label="Energy unit",
            kind="text",
            role="editable",
            default="MeV",
            help_text="Applied consistently to ε, G, and reconstructed energy.",
            order=70,
        ),
    ),
    units={
        "energy": "declared_by_instance",
        "epsilon": "same_as_energy",
        "g": "same_as_energy",
    },
    conserved_quantities=("particle_number", "pair_number", "seniority"),
    sector_schema={
        "particle_number": {"derived_from": "2*n_pairs"},
        "pair_number": {"parameter": "n_pairs"},
        "seniority": {"fixed": 0},
    },
    supported_observables=(
        "sector_energy",
        "pair_occupations_when_measured",
        "sector_leakage_when_measured",
    ),
    hamiltonian_policy_id="reduced_pairing_hamiltonian.v1",
    sector_policy_id="reduced_pairing_multi_pair_sector.v1",
    mapping_policy_id="pair_mapping.seniority_zero.v1",
    state_preparation_policy_id="multi_pair_lowest_levels_state.v1",
    ansatz_policy_id="bathri_multi_pair_givens.v1",
    measurement_policy_id="pauli_energy_qwc.v1",
    reference_policy_id="small_exact_multi_pair_sector.v1",
    resource_policy_id="bounded_multi_pair_local.v1",
    runtime_policy_id="external_variational_energy.v1",
    interpretation_policy_id="multi_pair_sector_energy.v1",
    reference_validity=ReferenceValidity(
        reference_kind="exact_fixed_pair_sector_diagonalisation",
        validity_statement=(
            "Exact within the declared seniority-zero fixed-pair sector for the "
            "small acceptance envelope. Richardson–Gaudin is not yet bound in this release."
        ),
        exact_within_declared_model=True,
        maximum_dimension=20,
        maximum_qubits=6,
        parameter_conditions={
            "seniority": 0,
            "n_levels": {"minimum": 4, "maximum": 6},
            "n_pairs": {"minimum": 2, "maximum": 3},
        },
        fallback_policy="limited_verification_outside_small_exact_envelope",
    ),
    resource_validity=ResourceValidityEnvelope(
        simulator_max_qubits=6,
        exact_semantic_check_max_qubits=6,
        maximum_parameter_count=9,
        notes=(
            "One pair-occupation qubit per level.",
            "Bathri occupied-to-virtual Givens network is execution-ready experimental.",
            "Acceptance promotion requires the declared multi-pair test matrix.",
        ),
    ),
    representation_contract={
        "representation_kind": "seniority_zero_pair_occupation",
        "basis_semantics": "one pair-occupation qubit per declared level",
        "encoding_policy_id": "pair_mapping.seniority_zero.v1",
        "physical_subspace": "restricted_seniority_zero_subspace",
    },
    classification=ModelClassificationContract(
        classification_id="classification.nuclear.reduced_pairing.multi_pair.v1",
        classification_version="1.0.0",
        ui_group_id="fermions",
        ui_group_label="Fermions",
        discovery_tags=('reduced_nuclear_pairing', 'paired_fermionic_levels', 'seniority_zero_pair_occupation'),
        notes=("The UI group is navigation metadata only.",),
    ),
    physical_phenomena=('reduced_nuclear_pairing',),
    degrees_of_freedom=('paired_fermionic_levels',),
    hamiltonian_components=('single_particle_level_energy', 'pair_scattering'),
    assumptions=(
        "reduced attractive pairing Hamiltonian",
        "two or more intact correlated pairs",
        "seniority-zero pair-occupation encoding",
        "sector-ground-state energy task",
    ),
    limitations=(
        "not a broken-pair or general shell-model route",
        "Bathri Givens ansatz is not yet certified as exact-state expressive for all cases",
        "small exact-sector reference only in this release",
        "not a real-hardware validation",
    ),
    support_status="execution_ready",
    execution_status="experimental",
    scientific_owner="Bathri + QCOL fermion model team",
    scientific_review_status="implementation extracted; acceptance promotion pending",
    acceptance_suite_id="acceptance.nuclear.reduced_pairing.multi_pair.v1",
    schema_version=MODEL_CONTRACT_SCHEMA_VERSION_1_3,
)

MULTI_PAIR_ACCEPTANCE_PRESETS = (
    {
        "preset_id": "four_levels_two_pairs",
        "parameters": {
            "n_levels": 4,
            "epsilon": [0.0, 1.0, 2.0, 3.0],
            "g": 0.5,
            "n_pairs": 2,
            "n_particles": 4,
            "seniority": 0,
            "energy_unit": "MeV",
        },
    },
    {
        "preset_id": "five_levels_two_pairs",
        "parameters": {
            "n_levels": 5,
            "epsilon": [0.0, 0.8, 1.7, 2.9, 4.0],
            "g": 0.4,
            "n_pairs": 2,
            "n_particles": 4,
            "seniority": 0,
            "energy_unit": "MeV",
        },
    },
    {
        "preset_id": "six_levels_three_pairs",
        "parameters": {
            "n_levels": 6,
            "epsilon": [0.0, 0.7, 1.5, 2.4, 3.4, 4.5],
            "g": 0.35,
            "n_pairs": 3,
            "n_particles": 6,
            "seniority": 0,
            "energy_unit": "MeV",
        },
    },
)

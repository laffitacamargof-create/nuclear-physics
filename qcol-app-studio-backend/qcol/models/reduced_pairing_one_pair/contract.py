"""Neutral scientific contract for the verified one-pair reduced-pairing plugin."""
from __future__ import annotations

from typing import Any, Dict

from ...model_contracts import (
    MODEL_CONTRACT_SCHEMA_VERSION_1_3,
    ModelContract,
    ModelClassificationContract,
    ParameterSpec,
    ReferenceValidity,
    ResourceValidityEnvelope,
)


MODEL_ID = "nuclear.reduced_pairing.one_pair"
MODEL_VERSION = "1.0.0"
SUPPORTED_TASK = "sector_ground_state_energy"


ONE_PAIR_MODEL_CONTRACT = ModelContract(
    model_id=MODEL_ID,
    model_version=MODEL_VERSION,
    label="Reduced pairing — one-pair seniority-zero",
    description=(
        "One correlated fermion pair distributed across a bounded set of "
        "single-particle levels under the reduced attractive pairing Hamiltonian."
    ),
    domain="nuclear_fermionic",
    family="reduced_pairing",
    problem_type="one_pair_seniority_zero",
    supported_tasks=("ground_state_energy", "sector_ground_state_energy", "observable_estimation"),
    parameter_schema=(
        ParameterSpec(
            key="n_levels",
            label="Number of levels",
            kind="integer",
            role="editable",
            default=4,
            minimum=2,
            maximum=6,
            step=1,
            help_text=(
                "Bounded to 2–6 levels in the verified local-simulator route. "
                "The four-level benchmark is an acceptance preset."
            ),
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
            key="n_particles",
            label="Number of particles",
            kind="integer",
            role="fixed",
            default=2,
            fixed_value=2,
            help_text="One pair contains exactly two fermions.",
            order=40,
        ),
        ParameterSpec(
            key="n_pairs",
            label="Number of pairs",
            kind="integer",
            role="fixed",
            default=1,
            fixed_value=1,
            help_text="This is a one-pair contract; multi-pair is a separate plugin.",
            order=50,
        ),
        ParameterSpec(
            key="seniority",
            label="Seniority",
            kind="integer",
            role="fixed",
            default=0,
            fixed_value=0,
            help_text="The certified route is restricted to the seniority-zero sector.",
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
        "particle_number": {"fixed": 2},
        "pair_number": {"fixed": 1},
        "seniority": {"fixed": 0},
    },
    supported_observables=(
        "sector_energy",
        "pair_occupations_when_measured",
        "pair_occupations",
    ),
    hamiltonian_policy_id="reduced_pairing_hamiltonian.v1",
    sector_policy_id="reduced_pairing_one_pair_sector.v1",
    mapping_policy_id="pair_mapping.seniority_zero.v1",
    state_preparation_policy_id="one_pair_lowest_level_state.v1",
    ansatz_policy_id="one_pair_chain_givens.v1",
    measurement_policy_id="pauli_energy_qwc.v1",
    reference_policy_id="small_exact_one_pair_sector.v1",
    resource_policy_id="bounded_local_exact_qasm_check.v1",
    runtime_policy_id="external_variational_energy.v1",
    interpretation_policy_id="one_pair_sector_energy.v1",
    reference_validity=ReferenceValidity(
        reference_kind="exact_sector_diagonalisation",
        validity_statement=(
            "Exact within the declared one-pair seniority-zero sector for the "
            "bounded local acceptance sizes."
        ),
        exact_within_declared_model=True,
        maximum_dimension=6,
        maximum_qubits=6,
        parameter_conditions={
            "n_pairs": 1,
            "seniority": 0,
            "n_levels": {"minimum": 2, "maximum": 6},
        },
        fallback_policy="do_not_promote_beyond_declared_envelope",
    ),
    resource_validity=ResourceValidityEnvelope(
        simulator_max_qubits=6,
        exact_semantic_check_max_qubits=6,
        maximum_parameter_count=5,
        notes=(
            "One pair maps to one qubit per level.",
            "This is a regression/acceptance envelope, not a hardware-capability claim.",
        ),
    ),
    representation_contract={
        "representation_kind": "seniority_zero_pair_occupation",
        "basis_semantics": "one pair-occupation qubit per declared level",
        "encoding_policy_id": "pair_mapping.seniority_zero.v1",
        "physical_subspace": "restricted_seniority_zero_subspace",
    },
    classification=ModelClassificationContract(
        classification_id="classification.nuclear.reduced_pairing.one_pair.v1",
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
        "one correlated pair",
        "seniority-zero pair-occupation encoding",
        "sector-ground-state energy task",
    ),
    limitations=(
        "not a multi-pair model",
        "not a general shell-model Hamiltonian",
        "not a real-hardware validation",
        "pair occupations require a dedicated diagnostic measurement",
    ),
    support_status="acceptance_verified",
    execution_status="acceptance_verified",
    scientific_owner="QCOL fermion model team",
    scientific_review_status="accepted as the registry regression anchor",
    acceptance_suite_id="acceptance.nuclear.reduced_pairing.one_pair.v1",
    schema_version=MODEL_CONTRACT_SCHEMA_VERSION_1_3,
)


FOUR_LEVEL_ACCEPTANCE_PRESET: Dict[str, Any] = {
    "preset_id": "four_level_one_pair",
    "label": "Four-level one-pair acceptance benchmark",
    "model_id": MODEL_ID,
    "model_version": MODEL_VERSION,
    "task_id": SUPPORTED_TASK,
    "parameters": {
        "n_levels": 4,
        "epsilon": [0.0, 1.0, 2.0, 3.0],
        "g": 0.5,
        "n_particles": 2,
        "n_pairs": 1,
        "seniority": 0,
        "energy_unit": "MeV",
    },
    "target_sector": {
        "particle_number": 2,
        "pair_number": 1,
        "seniority": 0,
    },
    "requested_observables": ["sector_energy"],
}


GENERAL_ONE_PAIR_PRESET: Dict[str, Any] = {
    "preset_id": "one_pair_pairing",
    "label": "Bounded configurable one-pair route",
    "model_id": MODEL_ID,
    "model_version": MODEL_VERSION,
    "task_id": SUPPORTED_TASK,
    "parameters": {
        "n_levels": 4,
        "epsilon": [0.0, 1.0, 2.0, 3.0],
        "g": 0.5,
        "n_particles": 2,
        "n_pairs": 1,
        "seniority": 0,
        "energy_unit": "MeV",
    },
    "target_sector": {
        "particle_number": 2,
        "pair_number": 1,
        "seniority": 0,
    },
    "requested_observables": ["sector_energy"],
}

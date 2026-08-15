"""Model contract for the reusable general spin-orbital fermionic representation.

The representation is an intermediate scientific contract.  Phase A.3.1
accepts deterministic JW/BK mapping analysis.  Phase A.3.2 adds the first
bounded circuit-executed cell:

    general spin-orbital × ground-state energy × Jordan–Wigner.

The contract still does not claim that a complete nuclear shell model has been
supplied.  Upstream nuclear-model plugins/adapters remain responsible for the
physical meaning of the modes, coefficients, symmetries, and observables.
"""
from __future__ import annotations

from ...model_contracts import (
    MODEL_CONTRACT_SCHEMA_VERSION_1_3,
    ModelContract,
    ModelClassificationContract,
    ParameterSpec,
    ReferenceValidity,
    ResourceValidityEnvelope,
)
from ...spin_orbital import GENERAL_SPIN_ORBITAL_REPRESENTATION

MODEL_ID = "fermion.general_spin_orbital"
MODEL_VERSION = "1.2.0"

DEFAULT_MODE_LABELS = (
    "neutron|a|m=+1/2",
    "neutron|a|m=-1/2",
    "neutron|b|m=+1/2",
    "neutron|b|m=-1/2",
)
DEFAULT_ONE_BODY_TERMS = (
    (0, 0, 0.0),
    (1, 1, 0.2),
    (2, 2, 1.0),
    (3, 3, 1.2),
    (0, 2, 0.15),
    (2, 0, 0.15),
    (1, 3, -0.10),
    (3, 1, -0.10),
)
# A finite Hermitian two-body input.  Each row multiplies
# a_p^ a_q^ a_s a_r under the explicit-operator convention.
DEFAULT_TWO_BODY_TERMS = (
    (0, 1, 0, 1, 0.08),
    (0, 2, 0, 2, 0.08),
    (0, 3, 0, 3, 0.08),
    (1, 2, 1, 2, 0.08),
    (1, 3, 1, 3, 0.08),
    (2, 3, 2, 3, 0.08),
)

GENERAL_SPIN_ORBITAL_MODEL_CONTRACT = ModelContract(
    model_id=MODEL_ID,
    model_version=MODEL_VERSION,
    label="General spin-orbital fermionic representation",
    description=(
        "A bounded finite spin-orbital input contract for sparse one- and "
        "two-body second-quantized Hamiltonians. Nuclear model plugins or "
        "external adapters must supply the physical meaning of modes and "
        "coefficients. The current release acceptance-verifies JW/BK mapping analysis "
        "and one bounded Jordan–Wigner fixed-particle ground-state composition."
    ),
    domain="general_fermionic",
    family="spin_orbital_representation",
    problem_type="sparse_one_two_body_second_quantization",
    supported_tasks=("mapping_analysis", "ground_state_energy"),
    parameter_schema=(
        ParameterSpec(
            "n_modes", "Number of spin-orbital modes", "integer",
            default=4, minimum=2, maximum=8, step=1, order=10,
            help_text=(
                "Finite spin-orbital Fock-space mode count. Mapping analysis "
                "accepts up to 8 modes; the Phase A.3.2 JW execution cell is "
                "bounded to 2–4 modes."
            ),
        ),
        ParameterSpec(
            "particle_species", "Particle species", "text",
            default="neutron", order=20,
            help_text=(
                "Comma-separated species labels. The first execution cell "
                "uses a declared total particle-number sector."
            ),
        ),
        ParameterSpec(
            "mode_labels", "Mode labels", "any",
            default=DEFAULT_MODE_LABELS, order=30,
            help_text="One line per mode: species|orbital|projection.",
        ),
        ParameterSpec(
            "one_body_terms", "One-body terms h[p,q]", "any",
            default=DEFAULT_ONE_BODY_TERMS, order=40,
            help_text="Rows p,q,coefficient; Hermitian conjugates must be declared.",
        ),
        ParameterSpec(
            "two_body_terms", "Two-body terms W[p,q,r,s]", "any",
            default=DEFAULT_TWO_BODY_TERMS, order=50,
            help_text="Rows p,q,r,s,coefficient multiplying a_p^ a_q^ a_s a_r.",
        ),
        ParameterSpec(
            "target_particle_number", "Target total particle number", "integer",
            default=2, minimum=0, maximum=8, step=1, order=60,
        ),
        ParameterSpec(
            "initial_occupied_modes", "Initial occupied modes", "any",
            default=tuple(), order=65,
            help_text=(
                "Optional comma-separated occupation determinant. Leave empty "
                "to occupy the lowest declared diagonal one-body levels. This "
                "policy never seeds the circuit from the exact many-body state."
            ),
        ),
        ParameterSpec(
            "ansatz_layers", "JW number-preserving ansatz layers", "integer",
            default=1, minimum=1, maximum=2, step=1, order=67,
            help_text=(
                "Used only by the bounded accepted JW ground-state composition. Each "
                "layer contains mapped fermionic single excitations routed by "
                "fermionic swaps, plus mapped diagonal number phases."
            ),
        ),
        ParameterSpec(
            "declared_symmetries", "Declared symmetries", "any",
            default=("particle_number",), order=70,
        ),
        ParameterSpec(
            "coefficient_convention", "Two-body coefficient convention", "text",
            default="explicit_operator_coefficient", order=80,
        ),
        ParameterSpec(
            "operator_ordering_convention", "Operator ordering convention", "text",
            role="fixed", default="a_p^ a_q^ a_s a_r",
            fixed_value="a_p^ a_q^ a_s a_r", order=90,
        ),
        ParameterSpec(
            "constant", "Constant energy offset", "number", default=0.0,
            unit_key="energy_unit", order=100,
        ),
        ParameterSpec(
            "energy_unit", "Energy unit", "text", default="MeV", order=110,
        ),
    ),
    units={
        "energy": "declared_by_instance",
        "one_body": "same_as_energy",
        "two_body": "same_as_energy",
    },
    conserved_quantities=("particle_number",),
    sector_schema={
        "particle_numbers": "declared_by_instance",
        "total_particle_number": "derived_from_particle_numbers",
    },
    supported_observables=(
        "fermionic_hamiltonian",
        "particle_number",
        "sector_energy",
        "ground_state_energy",
        "mapping_resources",
        "mapping_equivalence",
    ),
    hamiltonian_policy_id="general_spin_orbital_fermion_operator.v1",
    sector_policy_id="general_spin_orbital_particle_sector.v1",
    # The representation uses one inspectable primary mapping artifact. The
    # mapping-analysis controller still compares JW and BK independently; the
    # ground-state cell resolves only Jordan–Wigner.
    mapping_policy_id="general_spin_orbital_primary_jw.v1",
    state_preparation_policy_id="general_spin_orbital_state.v1",
    ansatz_policy_id="general_spin_orbital_ansatz.v1",
    measurement_policy_id="general_spin_orbital_measurement.v1",
    reference_policy_id="general_spin_orbital_reference.v1",
    resource_policy_id="general_spin_orbital_resource.v1",
    runtime_policy_id="general_spin_orbital_runtime.v1",
    interpretation_policy_id="general_spin_orbital_interpretation.v1",
    reference_validity=ReferenceValidity(
        reference_kind="exact_bounded_spin_orbital_fixed_particle_sector",
        validity_statement=(
            "Exact full-space and fixed-particle spectra for mapping analysis "
            "while n_modes <= 8; exact fixed-particle ground-state references "
            "for the JW execution cell while n_modes <= 4."
        ),
        exact_within_declared_model=True,
        maximum_qubits=8,
        maximum_dimension=256,
        parameter_conditions={
            "mapping_analysis": {"n_modes": {"minimum": 2, "maximum": 8}},
            "jw_ground_state": {
                "n_modes": {"minimum": 2, "maximum": 4},
                "ansatz_layers": {"minimum": 1, "maximum": 2},
            },
        },
        fallback_policy="mapping_diagnostics_or_limited_verification_outside_envelope",
    ),
    resource_validity=ResourceValidityEnvelope(
        simulator_max_qubits=4,
        exact_semantic_check_max_qubits=8,
        maximum_parameter_count=32,
        notes=(
            "Phase A.3.1 mapping analysis remains bounded to eight modes and uses no backend.",
            "WP11 acceptance-verifies Jordan–Wigner on a local simulator for 2–4 modes.",
            "The mapped-fermionic JW ansatz is bounded to one or two layers and at most 32 parameters.",
            "Bravyi–Kitaev remains transformation/analysis only in this release.",
        ),
    ),
    representation_contract=GENERAL_SPIN_ORBITAL_REPRESENTATION.to_dict(),
    classification=ModelClassificationContract(
        classification_id="classification.fermion.general_spin_orbital.v1",
        classification_version="1.0.0",
        ui_group_id="fermions",
        ui_group_label="Fermions",
        discovery_tags=('general_spin_orbital_many_body_model', 'individual_fermionic_modes', 'second_quantized_representation'),
        notes=(
            "The contract is a representation layer, not a complete shell-model physics claim.",
            "The UI group is navigation metadata only.",
        ),
    ),
    physical_phenomena=('general_spin_orbital_many_body_model',),
    degrees_of_freedom=('individual_fermionic_spin_orbital_modes',),
    hamiltonian_components=('one_body_terms', 'two_body_terms'),
    compatible_mapping_ids=("jordan_wigner.v1", "bravyi_kitaev.v1"),
    assumptions=(
        "finite spin-orbital basis with explicit ordering",
        "number-conserving one- and two-body input in the first release",
        "Hermitian coefficients under the declared convention",
        "the JW ground-state cell uses direct occupation-bit semantics",
        "the first JW execution cell is restricted to one declared particle species",
    ),
    limitations=(
        "an intermediate fermionic representation, not a complete nuclear model",
        "the accepted JW VQE cell is bounded to the declared small-scale composition and is not a universality claim",
        "the selected ansatz is not claimed universal for all strongly correlated Hamiltonians",
        "BK ground-state state preparation, sector diagnostics, and ansatz acceptance are not implemented",
        "species-resolved proton–neutron execution requires a later species-preserving ansatz and reference policy",
        "angular momentum, parity, or isospin semantics require an upstream nuclear-model adapter",
    ),
    # The model plugin has a verified mapping-analysis route. Cell-specific
    # ground-state honesty is carried by the Model × Task matrix.
    support_status="acceptance_verified",
    execution_status="acceptance_verified",
    scientific_owner="QCOL general fermionic representation layer",
    scientific_review_status="Phase A.3.1 mapping foundation + Phase A.3.2c WP11 accepted JW composition",
    acceptance_suite_id="acceptance.model.general_spin_orbital.a31_wp11.v1",
    schema_version=MODEL_CONTRACT_SCHEMA_VERSION_1_3,
)

"""Shared declarations for the four bounded nuclear QHO model contracts.

The four QHO models are independent :class:`ModelContract` records that reuse
one accepted hard-core oscillator realization family.  The contract factory is
purely declarative: it does not build Hamiltonians, branch the runtime, or
create a second execution path.
"""
from __future__ import annotations

from typing import Final

from ..model_contracts import (
    MODEL_CONTRACT_SCHEMA_VERSION_1_3,
    ModelContract,
    ModelClassificationContract,
    ParameterSpec,
    ReferenceValidity,
    ResourceValidityEnvelope,
)
from ..resource_rules import ONE_EXCITATION_RULE_ID

QHO_MODEL_IDS: Final[tuple[str, ...]] = (
    "nuclear.qho.free",
    "nuclear.qho.pairing",
    "nuclear.qho.spinorbit",
    "nuclear.qho.full",
)
QHO_FAMILY_ID: Final[str] = "nuclear_qho_hard_core"
QHO_MODEL_VERSION: Final[str] = "1.0.0"


def build_qho_contract(
    *,
    model_id: str,
    label: str,
    description: str,
    problem_type: str,
    coupling_enabled: bool,
    kappa_enabled: bool,
    assumptions: tuple[str, ...],
    limitations: tuple[str, ...],
) -> ModelContract:
    """Build one strict QHO contract with its interaction profile declared.

    ``coupling`` and ``kappa`` are fixed to zero when inactive.  UI clients can
    therefore render only editable/visible fields from ``parameter_schema``;
    they never need model-ID conditionals to know which interactions apply.
    """

    coupling_spec = (
        ParameterSpec(
            "coupling",
            "Mode coupling G",
            "matrix_or_scalar",
            default=0.2,
            minimum=0.0,
            unit_key="energy_unit",
            help_text=(
                "Non-negative pairing/hopping strength. The Hamiltonian applies "
                "the physical minus sign as −(G/2)(XX+YY)."
            ),
            order=30,
        )
        if coupling_enabled
        else ParameterSpec(
            "coupling",
            "Mode coupling G (fixed to zero)",
            "matrix_or_scalar",
            role="fixed",
            default=0.0,
            fixed_value=0.0,
            unit_key="energy_unit",
            visible=False,
            order=30,
        )
    )
    kappa_spec = (
        ParameterSpec(
            "kappa",
            "Spin-orbit shift κ",
            "vector_or_scalar",
            default=0.3,
            unit_key="energy_unit",
            help_text=(
                "Per-mode diagonal shell-splitting shift −κ·Z; this is not a "
                "full L·S interaction."
            ),
            order=40,
        )
        if kappa_enabled
        else ParameterSpec(
            "kappa",
            "Spin-orbit shift κ (fixed to zero)",
            "vector_or_scalar",
            role="fixed",
            default=0.0,
            fixed_value=0.0,
            unit_key="energy_unit",
            visible=False,
            order=40,
        )
    )

    return ModelContract(
        model_id=model_id,
        model_version=QHO_MODEL_VERSION,
        label=label,
        description=description,
        domain="nuclear_collective",
        family=QHO_FAMILY_ID,
        problem_type=problem_type,
        supported_tasks=("ground_state_energy", "sector_ground_state_energy"),
        parameter_schema=(
            ParameterSpec(
                "n_modes",
                "Number of modes",
                "integer",
                default=4,
                minimum=2,
                maximum=6,
                step=1,
                help_text="One qubit per hard-core oscillator mode.",
                order=10,
            ),
            ParameterSpec(
                "omega",
                "Mode frequencies ω",
                "vector_or_scalar",
                default=1.0,
                unit_key="energy_unit",
                help_text="A positive scalar or one frequency per declared mode.",
                order=20,
            ),
            coupling_spec,
            kappa_spec,
            ParameterSpec(
                "n_quanta",
                "Target quanta",
                "integer",
                role="fixed",
                default=1,
                fixed_value=1,
                visible=False,
                order=50,
            ),
            # QHO v1 is intentionally fixed to MeV in the guided interface.  The
            # unit remains part of the model identity and Evidence but is not an
            # interaction control shown to the user.
            ParameterSpec(
                "energy_unit",
                "Energy unit",
                "text",
                default="MeV",
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
        supported_observables=("sector_energy", "mode_occupations_when_measured"),
        hamiltonian_policy_id="hard_core_oscillator_hamiltonian.v1",
        sector_policy_id="one_excitation_sector.v1",
        mapping_policy_id="direct_hard_core_mode_encoding.v1",
        state_preparation_policy_id="lowest_mode_state.v1",
        ansatz_policy_id="one_excitation_chain_givens.v1",
        measurement_policy_id="pauli_energy_qwc.v1",
        reference_policy_id="small_exact_one_excitation_sector.v1",
        resource_policy_id="bounded_direct_qubit.v2",
        runtime_policy_id="external_variational_energy.v1",
        interpretation_policy_id="hard_core_oscillator_energy.v1",
        reference_validity=ReferenceValidity(
            reference_kind="exact_one_excitation_sector_diagonalisation",
            validity_statement=(
                "Exact within the declared hard-core one-quantum QHO model and "
                "bounded mode count."
            ),
            exact_within_declared_model=True,
            maximum_dimension=6,
            maximum_qubits=6,
            parameter_conditions={
                "n_quanta": 1,
                "n_modes": {"minimum": 2, "maximum": 6},
            },
            fallback_policy="limited_verification_outside_declared_envelope",
        ),
        resource_validity=ResourceValidityEnvelope(
            simulator_max_qubits=6,
            exact_semantic_check_max_qubits=6,
            maximum_parameter_count=5,
            notes=(
                "Bounded one-quantum hard-core QHO; not a full bosonic Fock space.",
            ),
        ),
        resource_estimation_rule_id=ONE_EXCITATION_RULE_ID,
        representation_contract={
            "representation": "hard_core_oscillator",
            "encoding": "one_qubit_per_mode",
            "occupation_values": [0, 1],
            "target_sector": {"excitation_number": 1},
            "interaction_profile": {
                "onsite_omega": True,
                "pairing_hopping": coupling_enabled,
                "spin_orbit_shift": kappa_enabled,
                "fixed_parameters": {
                    **({"coupling": 0.0} if not coupling_enabled else {}),
                    **({"kappa": 0.0} if not kappa_enabled else {}),
                },
            },
            "zero_point_convention": "omega_over_two_included",
        },
        classification=ModelClassificationContract(
            classification_id=f"classification.{model_id}.v2",
            classification_version="2.0.0",
            ui_group_id="oscillators",
            ui_group_label="Oscillators",
            discovery_tags=(
                "nuclear_oscillator",
                "hard_core_modes",
                "binary_mode_occupation",
                *(("pairing_or_hopping_like_interaction",) if coupling_enabled else ()),
                *(("diagonal_mode_shift",) if kappa_enabled else ()),
            ),
            notes=("Discovery metadata only; scientific facts are projected from ModelContract and resolved policies.",),
        ),
        physical_phenomena=("harmonic_oscillator_or_vibrational_model",),
        degrees_of_freedom=("hard_core_oscillator_modes",),
        hamiltonian_components=tuple(
            component
            for component, enabled in (
                ("onsite_zero_point_oscillator_energy", True),
                ("pairing_or_hopping_like_xx_yy_coupling", coupling_enabled),
                ("diagonal_mode_shift", kappa_enabled),
            )
            if enabled
        ),
        assumptions=assumptions,
        limitations=limitations,
        support_status="execution_ready",
        execution_status="experimental",
        scientific_owner=(
            "Q-Lab — QHO integration; interaction menu adapted from D. Chauhan's QHO module"
        ),
        scientific_review_status=(
            "structurally integrated; each Model × Task cell remains experimental "
            "until its own acceptance evidence is promoted"
        ),
        acceptance_suite_id=f"acceptance.{model_id}.ground_state.v1",
        schema_version=MODEL_CONTRACT_SCHEMA_VERSION_1_3,
    )

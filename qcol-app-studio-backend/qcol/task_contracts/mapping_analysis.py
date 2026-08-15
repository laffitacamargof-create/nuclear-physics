"""Task contract for analysis-only fermion-to-qubit mapping comparison."""
from __future__ import annotations

from .base import TaskContract, TaskParameterSpec

MAPPING_ANALYSIS_TASK_CONTRACT = TaskContract(
    task_id="mapping_analysis",
    task_version="1.0.0",
    label="Fermion-to-qubit Mapping Explorer",
    description=(
        "Transform the same standardized spin-orbital FermionOperator with all "
        "eligible mappings, verify semantic equivalence, and compare operator-level resources."
    ),
    task_family="mapping_and_resource_analysis",
    objective=(
        "Compare Jordan–Wigner and Bravyi–Kitaev on the same declared spin-orbital "
        "Hamiltonian without making a VQE or hardware-execution claim."
    ),
    required_model_capabilities=(
        "hamiltonian",
        "general_spin_orbital_representation",
        "mapping_plugins",
        "target_sector_or_full_space",
        "reference_or_limited_verification",
    ),
    required_model_observables=(
        "mapping_resources",
        "mapping_equivalence",
    ),
    parameter_schema=(
        TaskParameterSpec(
            "mapping_ids",
            "Mappings to compare",
            "vector",
            default=("jordan_wigner.v1", "bravyi_kitaev.v1"),
            required=True,
            allowed_values=("jordan_wigner.v1", "bravyi_kitaev.v1"),
            help_text="Both mappings are verified for transformation and analysis in Phase A.3.1.",
            order=10,
        ),
        TaskParameterSpec(
            "coefficient_threshold",
            "Coefficient threshold",
            "number",
            default=1e-12,
            minimum=0.0,
            maximum=1e-4,
            help_text="Terms below this magnitude are omitted only from resource counting.",
            order=20,
        ),
        TaskParameterSpec(
            "equivalence_tolerance",
            "Spectrum-equivalence tolerance",
            "number",
            default=1e-8,
            minimum=1e-12,
            maximum=1e-4,
            order=30,
        ),
    ),
    controller_policy_id="single_pass.mapping_analysis.v1",
    circuit_policy_id="mapping_analysis.no_circuit.v1",
    measurement_policy_id="mapping_analysis.no_measurement.v1",
    reconstruction_policy_id="mapping_comparison_report.v1",
    termination_policy_id="mapping_analysis_complete.v1",
    reference_policy_id="fermionic_fock_space_spectrum.v1",
    verification_policy_id="mapping_equivalence_and_resources.v1",
    interpretation_policy_id="mapping_analysis_bounded_meaning.v1",
    reference_type="full and fixed-particle Fermionic Fock-space spectra",
    verification_metric=(
        "full-spectrum, target-sector-spectrum, particle-number-spectrum, Hermiticity, and [H,N] checks"
    ),
    assumptions=(
        "all compared mappings receive exactly the same FermionOperator and mode ordering",
        "resource ranking is analysis-only and is not a VQE recommendation",
    ),
    limitations=(
        "no state-preparation, ansatz, optimizer, shots, backend, or hardware claim",
        "ground-state execution support is reported separately for each mapping",
    ),
    support_status="acceptance_verified",
    execution_status="acceptance_verified",
    acceptance_suite_id="acceptance.task.mapping_analysis.v1",
)

# Consistent public alias used by the existing task registry.
MAPPING_ANALYSIS_TASK = MAPPING_ANALYSIS_TASK_CONTRACT

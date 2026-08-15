"""Contract for bounded custom qubit Hamiltonians supplied as matrix or Pauli terms."""
from __future__ import annotations

from ...model_contracts import (
    MODEL_CONTRACT_SCHEMA_VERSION_1_3,
    ModelClassificationContract,
    ModelContract,
    ParameterSpec,
    ReferenceValidity,
    ResourceValidityEnvelope,
)

MODEL_ID="custom.qubit_hamiltonian"
MODEL_VERSION="1.0.0"
SUPPORTED_TASK="ground_state_energy"

CUSTOM_QUBIT_MODEL_CONTRACT=ModelContract(
    model_id=MODEL_ID,
    model_version=MODEL_VERSION,
    label="Custom qubit Hamiltonian — matrix or Pauli",
    description="Bounded technical route for a user-declared Hermitian qubit Hamiltonian.",
    domain="custom_model",
    family="custom_qubit_hamiltonian",
    problem_type="matrix_or_pauli_input",
    supported_tasks=(SUPPORTED_TASK,),
    parameter_schema=(
        ParameterSpec("input_route","Input route","text",default="matrix",order=10),
        ParameterSpec("matrix","Hermitian matrix","any",default="[[0,1],[1,0]]",order=20),
        ParameterSpec("pauli_terms","Pauli terms","any",default="X0: 1.0",order=30),
        ParameterSpec("n_qubits","Number of qubits","integer",default=1,minimum=1,maximum=6,step=1,order=40),
        ParameterSpec("ansatz_layers","Ansatz layers","integer",default=1,minimum=1,maximum=3,step=1,order=50),
        ParameterSpec("energy_unit","Energy unit","text",default="unspecified",order=60),
    ),
    units={"energy":"declared_by_instance"},
    conserved_quantities=tuple(),
    sector_schema={},
    supported_observables=("ground_state_energy",),
    hamiltonian_policy_id="custom_qubit_hamiltonian.v1",
    sector_policy_id="no_sector.v1",
    mapping_policy_id="direct_custom_qubit.v1",
    state_preparation_policy_id="computational_zero_state.v1",
    ansatz_policy_id="generic_ry_rz_linear_cnot.v1",
    measurement_policy_id="pauli_energy_qwc.v1",
    reference_policy_id="small_exact_full_space.v1",
    resource_policy_id="bounded_direct_qubit.v1",
    runtime_policy_id="external_variational_energy.v1",
    interpretation_policy_id="custom_qubit_energy.v1",
    reference_validity=ReferenceValidity(
        reference_kind="exact_full_space_diagonalisation",
        validity_statement="Exact while the declared qubit matrix fits the bounded local memory envelope.",
        exact_within_declared_model=True,
        maximum_qubits=6,
        parameter_conditions={"n_qubits":{"minimum":1,"maximum":6}},
        fallback_policy="diagnostics_only_when_exact_reference_unavailable",
    ),
    resource_validity=ResourceValidityEnvelope(
        simulator_max_qubits=6,
        exact_semantic_check_max_qubits=6,
        maximum_parameter_count=36,
        notes=("Technical input route; physical interpretation must be supplied by the user.",),
    ),
    representation_contract={
        "representation_kind": "qubit_native_operator_input",
        "basis_semantics": "user-declared computational qubit basis",
        "encoding_policy_id": "direct_custom_qubit.v1",
    },
    classification=ModelClassificationContract(
        classification_id="classification.custom.qubit_hamiltonian.v1",
        classification_version="1.0.0",
        ui_group_id="custom",
        ui_group_label="Custom",
        discovery_tags=('user_declared_qubit_hamiltonian', 'qubit_native'),
        notes=("The UI group is navigation metadata only.",),
    ),
    physical_phenomena=('user_declared_qubit_hamiltonian',),
    degrees_of_freedom=('qubit_native_degrees_of_freedom',),
    hamiltonian_components=('user_declared_qubit_terms',),
    assumptions=("user supplies a Hermitian qubit Hamiltonian",),
    limitations=("not automatically a nuclear model", "generic ansatz has no guaranteed symmetry preservation"),
    support_status="execution_ready",
    execution_status="execution_ready",
    scientific_owner="user supplied",
    scientific_review_status="technical validation only",
    acceptance_suite_id="acceptance.custom.qubit_hamiltonian.v1",
    schema_version=MODEL_CONTRACT_SCHEMA_VERSION_1_3,
)

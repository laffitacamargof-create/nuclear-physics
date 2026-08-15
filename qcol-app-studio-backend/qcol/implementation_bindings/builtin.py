"""WP3 schema-fixture contract and binding registrations.

The registrations prove the architecture without migrating the live Pair/JW/BK
policies.  All callable implementations are small deterministic fixtures and
are explicitly excluded from scientific runtime claims.
"""
from __future__ import annotations

from qcol.mapping_policies import PolicyStatus
from qcol.policy_contract_catalog import build_wp2_contract_examples

from .contract_index import DeclarativePolicyContractRegistry
from .contracts import BindingRequirement, ImplementationBindingContract
from .enums import BindingKind
from .registry import ImplementationBindingRegistry


WP3_BINDING_REGISTRY_ID = "qcol.mapping_realization.implementation_bindings.wp3"
WP3_BINDING_REGISTRY_VERSION = "1.0.0"
WP3_CONTRACT_REGISTRY_ID = "qcol.mapping_realization.declarative_contracts.wp3_examples"
WP3_CONTRACT_REGISTRY_VERSION = "1.0.0"
_FIXTURE_PROVIDER = "qcol.wp3_fixture"
_FIXTURE_REVISION = "wp3-fixture-2026-08-09"
_MAPPING_CONVENTION = "wp2.example.ordered_mode_encoding.v1"
_NOT_APPLICABLE_CONVENTION = "not_applicable.v1"


def _binding(
    binding_id: str,
    display_name: str,
    kind: BindingKind,
    import_attribute: str | None,
    expected_parameters: tuple[str, ...],
    *,
    convention_id: str = _NOT_APPLICABLE_CONVENTION,
    support_status: PolicyStatus = PolicyStatus.EXECUTION_READY,
    description: str,
) -> ImplementationBindingContract:
    return ImplementationBindingContract(
        binding_id=binding_id,
        binding_version="1.0.0",
        display_name=display_name,
        kind=kind,
        provider=_FIXTURE_PROVIDER,
        implementation_version="1.0.0",
        convention_id=convention_id,
        source_revision=_FIXTURE_REVISION,
        import_path=(
            None
            if import_attribute is None
            else f"qcol.implementation_bindings.fixtures:{import_attribute}"
        ),
        expected_parameters=expected_parameters,
        support_status=support_status,
        description=description,
        limitations=(
            "WP3 schema fixture only; not a migrated live mapping-realization policy.",
        ),
        provenance={
            "phase": "Phase A.3.2a",
            "work_package": "WP3",
            "fixture_only": True,
            "scientific_behavior_change": False,
            "live_policy_migration_performed": False,
        },
    )


def wp3_binding_contracts() -> tuple[ImplementationBindingContract, ...]:
    return (
        _binding(
            "wp2.binding.operator_mapper.v1",
            "WP3 fixture operator mapper",
            BindingKind.OPERATOR_TRANSFORM,
            "operator_mapper",
            ("operator",),
            convention_id=_MAPPING_CONVENTION,
            description="Lazy operator-transform fixture used to prove exact binding resolution.",
        ),
        _binding(
            "wp2.binding.occupation_encoder.v1",
            "WP3 fixture occupation encoder",
            BindingKind.BASIS_ENCODER,
            "occupation_encoder",
            ("occupations",),
            convention_id=_MAPPING_CONVENTION,
            description="Encodes a declared occupation vector for registry tests.",
        ),
        _binding(
            "wp2.binding.occupation_decoder.v1",
            "WP3 fixture occupation decoder",
            BindingKind.BASIS_DECODER,
            "occupation_decoder",
            ("bitstring",),
            convention_id=_MAPPING_CONVENTION,
            description="Decodes a declared occupation bitstring for registry tests.",
        ),
        _binding(
            "wp2.binding.full_fock_space.v1",
            "WP3 fixture full-Fock-space predicate",
            BindingKind.PHYSICAL_SUBSPACE,
            "full_fock_space",
            ("state",),
            convention_id=_MAPPING_CONVENTION,
            description="Checks the schema fixture's declared binary basis domain.",
        ),
        _binding(
            "wp2.binding.standard_mapping_resources.v1",
            "WP3 fixture mapping resource assessor",
            BindingKind.RESOURCE_ASSESSOR,
            "standard_mapping_resources",
            ("mapped_operator",),
            convention_id=_MAPPING_CONVENTION,
            description="Produces deterministic fixture-level resource metadata.",
        ),
        _binding(
            "wp2.binding.particle_popcount_diagnostic.v1",
            "WP3 fixture popcount diagnostic",
            BindingKind.SECTOR_DIAGNOSTIC,
            "particle_popcount_diagnostic",
            ("bitstring",),
            description="Demonstrates a direct-popcount sector diagnostic binding.",
        ),
        _binding(
            "wp2.binding.distributed_occupation_decoder.v1",
            "WP3 fixture distributed decoder",
            BindingKind.BASIS_DECODER,
            "distributed_occupation_decoder",
            ("encoded_bits",),
            description="Demonstrates a mapping-specific decoder binding without a BK runtime claim.",
        ),
        _binding(
            "wp2.binding.nonlocal_particle_operator.v1",
            "WP3 fixture non-local particle diagnostic",
            BindingKind.SECTOR_DIAGNOSTIC,
            "nonlocal_particle_operator",
            ("n_qubits",),
            description="Demonstrates a non-local mapped-sector diagnostic binding.",
        ),
        _binding(
            "wp2.binding.state_preparation.v1",
            "WP3 fixture state-preparation builder",
            BindingKind.STATE_PREPARATION,
            "state_preparation",
            ("occupations",),
            description="Builds a deterministic state-preparation declaration for registry tests.",
        ),
        _binding(
            "wp2.binding.mapped_generator_ansatz.v1",
            "WP3 fixture mapped-generator ansatz factory",
            BindingKind.ANSATZ_FACTORY,
            "mapped_generator_ansatz",
            ("generators", "parameters"),
            description="Proves callable binding mechanics; it is not an accepted JW composition.",
        ),
        _binding(
            "wp2.binding.real_parameter_vector.v1",
            "WP3 fixture real parameter vector",
            BindingKind.PARAMETERIZATION,
            "real_parameter_vector",
            ("values",),
            description="Normalizes real-valued fixture parameters.",
        ),
        _binding(
            "wp2.binding.measurement_builder.v1",
            "WP3 fixture measurement builder",
            BindingKind.MEASUREMENT_BUILDER,
            "measurement_builder",
            ("mapped_observables",),
            description="Builds a fixture measurement-plan declaration.",
        ),
        _binding(
            "wp2.binding.qwc_grouping.v1",
            "WP3 fixture QWC grouping",
            BindingKind.GROUPING,
            "qwc_grouping",
            ("pauli_terms",),
            description="Demonstrates a versioned grouping-policy binding.",
        ),
        _binding(
            "wp2.binding.term_expectation_reconstruction.v1",
            "WP3 fixture expectation reconstruction",
            BindingKind.RECONSTRUCTION,
            "term_expectation_reconstruction",
            ("expectations", "coefficients"),
            description="Demonstrates a versioned reconstruction binding.",
        ),
        _binding(
            "wp2.binding.source_domain_exact_solver.v1",
            "WP3 fixture independent source-domain solver",
            BindingKind.REFERENCE_SOLVER,
            "source_domain_exact_solver",
            ("matrix",),
            description="Demonstrates an independent-reference solver binding.",
        ),
        _binding(
            "wp2.binding.verification.v1",
            "WP3 fixture verification handler",
            BindingKind.VERIFICATION,
            "verification",
            ("result", "reference"),
            description="Demonstrates a verification implementation binding.",
        ),
        _binding(
            "wp3.binding.future_mapper.v1",
            "Recognized future mapper without implementation",
            BindingKind.OPERATOR_TRANSFORM,
            None,
            ("operator",),
            convention_id="wp3.future.mapping_convention.v1",
            support_status=PolicyStatus.RECOGNIZED_NOT_EXECUTABLE,
            description=(
                "A deliberate unavailable binding proving that known policies "
                "remain inspectable without raising ImportError."
            ),
        ),
    )


def build_wp3_example_registries() -> tuple[
    DeclarativePolicyContractRegistry,
    ImplementationBindingRegistry,
]:
    contract_registry = DeclarativePolicyContractRegistry(
        registry_id=WP3_CONTRACT_REGISTRY_ID,
        registry_version=WP3_CONTRACT_REGISTRY_VERSION,
    )
    for contract in build_wp2_contract_examples().values():
        contract_registry.register(contract)

    binding_registry = ImplementationBindingRegistry(
        registry_id=WP3_BINDING_REGISTRY_ID,
        registry_version=WP3_BINDING_REGISTRY_VERSION,
    )
    for contract in wp3_binding_contracts():
        binding_registry.register(contract)
    return contract_registry, binding_registry


def known_contract_missing_binding_requirement() -> BindingRequirement:
    return BindingRequirement(
        contract_id="wp3.fixture.known_contract_missing_binding.v1",
        contract_type="MappingPolicyContract",
        role="mapping.operator_transform",
        binding_id="wp3.binding.absent_mapper.v1",
        binding_kind=BindingKind.OPERATOR_TRANSFORM,
        required=True,
        expected_binding_version="1.0.0",
        expected_convention_id="wp3.absent.mapping_convention.v1",
    )


def recognized_not_executable_requirement() -> BindingRequirement:
    return BindingRequirement(
        contract_id="wp3.fixture.known_future_mapping.v1",
        contract_type="MappingPolicyContract",
        role="mapping.operator_transform",
        binding_id="wp3.binding.future_mapper.v1",
        binding_kind=BindingKind.OPERATOR_TRANSFORM,
        required=True,
        expected_binding_version="1.0.0",
        expected_convention_id="wp3.future.mapping_convention.v1",
    )


__all__ = [
    "WP3_BINDING_REGISTRY_ID",
    "WP3_BINDING_REGISTRY_VERSION",
    "WP3_CONTRACT_REGISTRY_ID",
    "WP3_CONTRACT_REGISTRY_VERSION",
    "wp3_binding_contracts",
    "build_wp3_example_registries",
    "known_contract_missing_binding_requirement",
    "recognized_not_executable_requirement",
]

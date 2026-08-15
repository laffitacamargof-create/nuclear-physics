"""Step-3 implementation of ``demo.two_level.v1``.

The module owns only extension-specific material: the model instance builder,
the identity-mapping binding, the plugin descriptor, and the test-only
Model × Task cell.  It does not create a runtime, resolver, evidence path, or
new public extension seam.
"""
from __future__ import annotations

from typing import Any, Mapping
from uuid import uuid4

from ...model_contracts import ModelInstance
from ...model_task_matrix import ModelTaskCell
from ...plugin_api import ModelPlugin
from ...plugin_identity import default_scientific_identity
from ...request_boundaries import copy_plain_data
from .contract import (
    DEMO_TWO_LEVEL_MODEL_CONTRACT,
    ENCODING_CONTEXT_ID,
    MAPPING_POLICY_ID,
    MODEL_ID,
    TASK_ID,
)


def _contract_parameters() -> dict[str, Any]:
    values: dict[str, Any] = {}
    for spec in DEMO_TWO_LEVEL_MODEL_CONTRACT.parameter_schema:
        if spec.role == "fixed":
            values[spec.key] = copy_plain_data(spec.fixed_value)
        elif spec.default is not None:
            values[spec.key] = copy_plain_data(spec.default)
    return values


def build_demo_two_level_instance(
    request: Mapping[str, Any],
    contract=DEMO_TWO_LEVEL_MODEL_CONTRACT,
) -> ModelInstance:
    """Build the fixed two-level architecture fixture without UI inference."""
    supplied = dict(request.get("parameters", {}))
    parameters = _contract_parameters()
    parameters.update(supplied)
    instance = ModelInstance(
        instance_id=f"instance-{uuid4().hex[:12]}",
        model_id=contract.model_id,
        model_version=contract.model_version,
        task_id=str(request.get("task_id") or TASK_ID),
        parameters=parameters,
        target_sector={"excitation_number": 1},
        requested_observables=("sector_energy",),
        units={
            "energy": "dimensionless",
            "omega": "dimensionless",
            "coupling": "dimensionless",
            "kappa": "dimensionless",
        },
        source_metadata={
            "source": "QCOL Step-3 extensibility drill",
            "production_feature": False,
            "legacy_problem": request.get("problem"),
        },
    )
    instance.validate_against(contract)
    return instance


def demo_two_level_encoding_context(*, instance, mapping, task_plan=None) -> str:
    del instance, mapping, task_plan
    return ENCODING_CONTEXT_ID


def identity_qubit_mapping_policy(context, hamiltonian, sector):
    """Exact identity encoding wrapper over the existing direct-qubit mapper.

    The executable implementation is reused; this wrapper publishes the exact
    mapping identity and encoding semantics required by the extension drill.
    """
    from ...model_execution_types import MappingResult
    from ..direct_qubit_common import direct_mapping_policy

    base = direct_mapping_policy(context, hamiltonian, sector)
    metadata = {
        **dict(base.mapping_metadata),
        "policy_id": MAPPING_POLICY_ID,
        "identity_mapping": True,
        "architecture_fixture": MODEL_ID,
    }
    return MappingResult(
        qubit_hamiltonian=base.qubit_hamiltonian,
        n_qubits=base.n_qubits,
        mapping_name="identity_qubit_mapping",
        encoding="demo_two_level_computational_basis",
        mapping_metadata=metadata,
        orbital_to_qubit_order=dict(base.orbital_to_qubit_order),
        preserved_symmetries=tuple(base.preserved_symmetries),
        crosscheck_payloads=dict(base.crosscheck_payloads),
        validation_checks={
            **dict(base.validation_checks),
            "identity_mapping_declared": True,
        },
    )


def _register_mapping_binding() -> None:
    from ...policy_registries import MAPPING_REGISTRY

    if MAPPING_REGISTRY.has(MAPPING_POLICY_ID):
        return
    MAPPING_REGISTRY.declare(
        MAPPING_POLICY_ID,
        "qcol.models.demo_two_level.plugin:identity_qubit_mapping_policy",
        "Identity qubit mapping for the Step-3 two-level extension drill.",
        provenance={
            "owner": "demo.two_level.v1",
            "scope": "internal architecture fitness fixture",
            "production_feature": False,
        },
    )


def _register_model_task_cell() -> None:
    # ``model_task_matrix`` may be partially initialized when its first static
    # cell triggers the plugin registry.  Its registration function is already
    # defined at that point, whereas its public lookup functions are not.
    # Registering through that one existing data surface avoids a second cell
    # registry and remains deterministic in either import order.
    from ... import model_task_matrix as matrix
    from ...model_contracts import ModelContractError

    try:
        matrix.register_model_task_cell(
            ModelTaskCell(
            model_id=MODEL_ID,
            task_id=TASK_ID,
            status="execution_ready",
            label="Step-3 two-level extensibility drill",
            resolved_policy_intent={
                "mapping": MAPPING_POLICY_ID,
                "encoding_context": ENCODING_CONTEXT_ID,
                "state_preparation": "lowest_mode_state.v1",
                "ansatz": "one_excitation_chain_givens.v1",
                "controller": "external_variational_energy.v1",
                "reference": "small_exact_one_excitation_sector.v1",
            },
            reference_validity={
                "kind": "deterministic two-by-two exact diagonalisation",
                "declared_scale": "two modes; one excitation",
                "production_claim": False,
            },
            resource_envelope={
                "simulator_max_qubits": 2,
                "maximum_parameter_count": 1,
            },
            acceptance_suite_id="acceptance.demo.two_level.extension_drill.v1",
            notes=(
                "Architecture fitness fixture only; excluded from production navigation.",
                "The cell proves the extension seam and does not promote a nuclear-model claim.",
            ),
            )
        )
    except ModelContractError as exc:
        if "already registered" not in str(exc):
            raise


def register_demo_two_level_extension(registry, capability_deriver) -> None:
    """Register the demo through the single Step-2 registration authority."""
    _register_mapping_binding()
    registry.register_model(
        ModelPlugin(
            plugin_id=MODEL_ID,
            plugin_version=DEMO_TWO_LEVEL_MODEL_CONTRACT.model_version,
            contract=DEMO_TWO_LEVEL_MODEL_CONTRACT,
            instance_factory=build_demo_two_level_instance,
            encoding_context_factory=demo_two_level_encoding_context,
            scientific_identity_factory=default_scientific_identity,
            capabilities=capability_deriver(DEMO_TWO_LEVEL_MODEL_CONTRACT),
            mapping_acceptance_modes=((TASK_ID, "full"),),
        )
    )
    _register_model_task_cell()


__all__ = [
    "build_demo_two_level_instance",
    "demo_two_level_encoding_context",
    "identity_qubit_mapping_policy",
    "register_demo_two_level_extension",
]

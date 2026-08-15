"""Built-in QCOL descriptors registered through the single Step-2 seam.

This is the only in-repository registration location.  Package entry-point
discovery is deliberately deferred until external plugins are a real need.
"""
from __future__ import annotations

from .plugin_api import ModelPlugin, TaskPlugin


def _model_capabilities(contract) -> tuple[str, ...]:
    """Derive the ModelPlugin capability projection from its ModelContract.

    ``ModelContract`` remains the OWNER of model science.  This helper is only a
    DERIVER: it projects the contract's existing policy and representation facts
    into the capability vocabulary consumed by ``TaskContract``.  Keeping this
    derivation here prevents the plugin descriptor from becoming a second,
    manually maintained scientific authority.

    The semantic capability names intentionally preserve the pre-Step-2
    resolver contract.  Generic ``task:``, ``observable:``, and ``mapping:`` tags
    remain available for discovery/reporting, but they are not substitutes for
    the task-admission vocabulary.
    """
    values = {
        "model_contract",
        "model_instance",
    }

    if str(contract.hamiltonian_policy_id).strip():
        values.add("hamiltonian")
    if str(contract.sector_policy_id).strip():
        values.update(("target_sector", "target_sector_or_full_space"))
    if str(contract.state_preparation_policy_id).strip():
        values.update((
            "state_preparation_policy",
            "initial_state",
            "parameterized_or_fixed_state",
        ))
    if str(contract.ansatz_policy_id).strip():
        values.update((
            "ansatz_policy",
            "parameterized_state_family",
            "parameterized_or_fixed_state",
        ))
    if str(contract.measurement_policy_id).strip():
        values.update((
            "measurement_policy",
            "energy_measurement",
            "observable_measurement",
        ))
    if str(contract.reference_policy_id).strip():
        values.update((
            "reference_policy",
            "reference_or_limited_verification",
            "observable_reference_for_acceptance",
        ))
    if str(contract.mapping_policy_id).strip():
        values.add("mapping_policy")
    if str(contract.resource_policy_id).strip():
        values.add("resource_policy")
    if contract.supported_observables:
        values.add("declared_observables")

    representation_id = str(
        contract.representation_contract.get("representation_id", "")
    ).strip()
    if representation_id == "general_spin_orbital_fermion.v1":
        values.update(("general_spin_orbital_representation", "fermion_operator"))
    if contract.compatible_mapping_ids:
        values.add("mapping_plugins")

    values.update(f"task:{value}" for value in contract.supported_tasks)
    values.update(f"observable:{value}" for value in contract.supported_observables)
    values.update(f"mapping:{value}" for value in contract.compatible_mapping_ids)
    return tuple(sorted(values))


def register_builtin_plugins(registry) -> None:
    # Local imports keep the dependency-light public package import intact.
    from .model_instance_adapters import (
        custom_qubit_instance,
        general_spin_orbital_instance,
        guided_instance,
        multi_pair_instance,
        one_pair_instance,
        oscillator_instance,
        qho_instance,
    )
    from .models.custom_guided_occupation.contract import CUSTOM_GUIDED_MODEL_CONTRACT
    from .models.custom_qubit_hamiltonian.contract import CUSTOM_QUBIT_MODEL_CONTRACT
    from .models.general_spin_orbital.contract import GENERAL_SPIN_ORBITAL_MODEL_CONTRACT
    from .models.oscillator_hard_core.contract import OSCILLATOR_MODEL_CONTRACT
    from .models.qho_free.contract import QHO_FREE_MODEL_CONTRACT
    from .models.qho_full.contract import QHO_FULL_MODEL_CONTRACT
    from .models.qho_pairing.contract import QHO_PAIRING_MODEL_CONTRACT
    from .models.qho_spinorbit.contract import QHO_SPINORBIT_MODEL_CONTRACT
    from .models.reduced_pairing_multi_pair.contract import MULTI_PAIR_MODEL_CONTRACT
    from .models.reduced_pairing_one_pair.contract import ONE_PAIR_MODEL_CONTRACT
    from .plugin_identity import (
        custom_qubit_encoding_context,
        default_scientific_identity,
        guided_encoding_context,
        hard_core_encoding_context,
        pair_encoding_context,
        spin_orbital_encoding_context,
        spin_orbital_scientific_identity,
    )

    model_rows = (
        (
            ONE_PAIR_MODEL_CONTRACT,
            one_pair_instance,
            pair_encoding_context,
            default_scientific_identity,
            (("ground_state_energy", "full"), ("observable_estimation", "full")),
        ),
        (
            MULTI_PAIR_MODEL_CONTRACT,
            multi_pair_instance,
            pair_encoding_context,
            default_scientific_identity,
            (("ground_state_energy", "full"),),
        ),
        (OSCILLATOR_MODEL_CONTRACT, oscillator_instance, hard_core_encoding_context, default_scientific_identity, ()),
        (CUSTOM_GUIDED_MODEL_CONTRACT, guided_instance, guided_encoding_context, default_scientific_identity, ()),
        (CUSTOM_QUBIT_MODEL_CONTRACT, custom_qubit_instance, custom_qubit_encoding_context, default_scientific_identity, ()),
        (
            GENERAL_SPIN_ORBITAL_MODEL_CONTRACT,
            general_spin_orbital_instance,
            spin_orbital_encoding_context,
            spin_orbital_scientific_identity,
            (("ground_state_energy", "full"), ("mapping_analysis", "analysis_only")),
        ),
        (QHO_FREE_MODEL_CONTRACT, qho_instance, hard_core_encoding_context, default_scientific_identity, ()),
        (QHO_PAIRING_MODEL_CONTRACT, qho_instance, hard_core_encoding_context, default_scientific_identity, ()),
        (QHO_SPINORBIT_MODEL_CONTRACT, qho_instance, hard_core_encoding_context, default_scientific_identity, ()),
        (QHO_FULL_MODEL_CONTRACT, qho_instance, hard_core_encoding_context, default_scientific_identity, ()),
    )
    for contract, factory, context_factory, identity_factory, mapping_modes in model_rows:
        registry.register_model(
            ModelPlugin(
                plugin_id=contract.model_id,
                plugin_version=contract.model_version,
                contract=contract,
                instance_factory=factory,
                encoding_context_factory=context_factory,
                scientific_identity_factory=identity_factory,
                capabilities=_model_capabilities(contract),
                mapping_acceptance_modes=mapping_modes,
            )
        )

    from .task_contracts.future import (
        EIGENPHASE_TASK,
        EXCITED_STATE_TASK,
        TIME_EVOLUTION_TASK,
    )
    from .task_contracts.ground_state import GROUND_STATE_TASK
    from .task_contracts.mapping_analysis import MAPPING_ANALYSIS_TASK
    from .task_contracts.observable import OBSERVABLE_TASK
    from .task_instance_adapters import (
        future_task_instance,
        ground_state_task_instance,
        mapping_analysis_task_instance,
        observable_task_instance,
    )

    task_rows = (
        TaskPlugin(
            plugin_id=GROUND_STATE_TASK.task_id,
            plugin_version=GROUND_STATE_TASK.task_version,
            contract=GROUND_STATE_TASK,
            instance_factory=ground_state_task_instance,
            controller_structure="optimizer_loop",
            controller_stage="optimizer",
            controller_message="Starting the resolved external optimizer controller.",
            observable_match_mode="any_of",
            observable_any_of=("sector_energy", "ground_state_energy"),
        ),
        TaskPlugin(
            plugin_id=OBSERVABLE_TASK.task_id,
            plugin_version=OBSERVABLE_TASK.task_version,
            contract=OBSERVABLE_TASK,
            instance_factory=observable_task_instance,
            controller_structure="single_pass",
            controller_stage="bind",
            controller_message="Starting the resolved single-pass task controller.",
            observable_match_mode="requested_all",
            observable_aliases=(("pair_occupations", "pair_occupations_when_measured"),),
        ),
        TaskPlugin(
            plugin_id=MAPPING_ANALYSIS_TASK.task_id,
            plugin_version=MAPPING_ANALYSIS_TASK.task_version,
            contract=MAPPING_ANALYSIS_TASK,
            instance_factory=mapping_analysis_task_instance,
            controller_structure="mapping_analysis",
            controller_stage="mapping_analysis",
            controller_message="Starting deterministic mapping transformation and resource analysis.",
            observable_match_mode="required_all",
        ),
        TaskPlugin(
            plugin_id=EXCITED_STATE_TASK.task_id,
            plugin_version=EXCITED_STATE_TASK.task_version,
            contract=EXCITED_STATE_TASK,
            instance_factory=future_task_instance,
            controller_structure="unresolved",
            controller_stage="task",
            controller_message="Future task is registered but not executable.",
            observable_match_mode="none",
        ),
        TaskPlugin(
            plugin_id=TIME_EVOLUTION_TASK.task_id,
            plugin_version=TIME_EVOLUTION_TASK.task_version,
            contract=TIME_EVOLUTION_TASK,
            instance_factory=future_task_instance,
            controller_structure="unresolved",
            controller_stage="task",
            controller_message="Future task is registered but not executable.",
            observable_match_mode="none",
        ),
        TaskPlugin(
            plugin_id=EIGENPHASE_TASK.task_id,
            plugin_version=EIGENPHASE_TASK.task_version,
            contract=EIGENPHASE_TASK,
            instance_factory=future_task_instance,
            controller_structure="unresolved",
            controller_stage="task",
            controller_message="Future task is registered but not executable.",
            observable_match_mode="none",
        ),
    )
    for descriptor in task_rows:
        registry.register_task(descriptor)

    from .execution.descriptors import LOCAL_AER_DESCRIPTOR, LOCAL_CIRQ_DESCRIPTOR

    registry.register_execution(
        LOCAL_CIRQ_DESCRIPTOR,
        import_path="qcol.execution.local_cirq:LOCAL_CIRQ_ADAPTER",
        implementation_status="implemented",
    )

    # Post-freeze Execution Realization E1: one adapter registration only.
    registry.register_execution(
        LOCAL_AER_DESCRIPTOR,
        import_path="qcol.execution.local_aer:LOCAL_AER_ADAPTER",
        implementation_status="implemented",
    )

    # Step 3 architecture-fitness extension: one registration edit only.
    # The demo remains internal/test-only and enters through the same resolver,
    # canonical IR, and shared pipeline as every other model.
    from .models.demo_two_level.plugin import register_demo_two_level_extension

    register_demo_two_level_extension(registry, _model_capabilities)


__all__ = ["register_builtin_plugins"]

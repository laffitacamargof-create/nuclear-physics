"""Compatibility projection over the Step-2 ModelPlugin registry.

Model registration authority now lives in :mod:`qcol.plugin_registry`.  This
module retains the historical public contract APIs without storing a second
registry.
"""
from __future__ import annotations

from typing import Tuple

from .model_contracts import ModelContract, ModelContractError
from .plugin_api import ModelPlugin
from .plugin_registry import REGISTRY, get_model_plugin, list_model_plugins

MODEL_CONTRACT_REGISTRY_VERSION = "qcol-model-registry/3.1-qho-family"


def register_model_contract(contract: ModelContract, *, replace: bool = False) -> None:
    """Compatibility registration helper.

    A new contract alone is not executable.  Replacing an existing contract
    preserves its single registered instance factory; new extensions should
    register a complete ``ModelPlugin`` instead.
    """
    try:
        existing = get_model_plugin(contract.model_id)
    except Exception as exc:
        raise ModelContractError(
            "Register a complete ModelPlugin for a new model; a bare "
            "ModelContract is not an executable extension seam."
        ) from exc
    REGISTRY.register_model(
        ModelPlugin(
            plugin_id=contract.model_id,
            plugin_version=contract.model_version,
            contract=contract,
            instance_factory=existing.instance_factory,
            encoding_context_factory=existing.encoding_context_factory,
            scientific_identity_factory=existing.scientific_identity_factory,
            capabilities=existing.capabilities,
            mapping_acceptance_modes=existing.mapping_acceptance_modes,
        ),
        replace=replace,
    )


def get_model_contract(model_id: str) -> ModelContract:
    try:
        return get_model_plugin(model_id).contract
    except Exception as exc:
        raise ModelContractError(str(exc)) from exc


def list_model_contracts() -> Tuple[ModelContract, ...]:
    return tuple(plugin.contract for plugin in list_model_plugins())


def public_model_registry():
    return {
        "registry_version": MODEL_CONTRACT_REGISTRY_VERSION,
        "contracts": [contract.to_dict() for contract in list_model_contracts()],
    }


def validate_model_registry():
    contracts = list_model_contracts()
    ids = [contract.model_id for contract in contracts]
    by_id = {contract.model_id: contract for contract in contracts}
    return {
        "registry_not_empty": bool(contracts),
        "model_ids_unique": len(ids) == len(set(ids)),
        "single_registration_authority": True,
        "generated_from_plugins": True,
        "one_pair_is_regression_anchor": (
            by_id["nuclear.reduced_pairing.one_pair"].execution_status
            == "acceptance_verified"
        ),
        "multi_pair_is_independent_contract": (
            "nuclear.reduced_pairing.multi_pair" in by_id
        ),
        "current_domains_migrated": all(
            model_id in by_id
            for model_id in (
                "nuclear.oscillator.hard_core.one_quantum",
                "custom.occupation_coupling.one_excitation",
                "custom.qubit_hamiltonian",
            )
        ),
        "general_spin_orbital_registered": "fermion.general_spin_orbital" in by_id,
        "qho_family_registered": all(
            model_id in by_id
            for model_id in (
                "nuclear.qho.free",
                "nuclear.qho.pairing",
                "nuclear.qho.spinorbit",
                "nuclear.qho.full",
            )
        ),
        "all_contracts_serializable": all(
            isinstance(contract.to_dict(), dict) for contract in contracts
        ),
    }

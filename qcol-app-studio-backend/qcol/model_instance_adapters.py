"""Request-to-ModelInstance adapters.

The shared runtime never branches on model IDs.  This boundary converts legacy
Phase-4 requests and new registry-native requests into explicit model instances.
"""
from __future__ import annotations

from collections.abc import Iterator, Mapping as MappingABC
from typing import Any, Dict, Mapping
from uuid import uuid4

from .model_contracts import ModelContract, ModelContractError, ModelInstance
from .task_registry import canonical_task_id
from .request_boundaries import RUN_CONTROL_KEYS, copy_plain_data
from .models.qho_common import QHO_MODEL_IDS

class _InstanceAdapterCompatibilityView(MappingABC[str, object]):
    """Generated compatibility view over the single plugin registry.

    Older structural tests imported ``INSTANCE_ADAPTERS`` directly.  The view
    remains read-only but stores no independent registrations.
    """

    def __getitem__(self, model_id: str):
        from .plugin_registry import get_model_plugin
        return get_model_plugin(model_id).instance_factory

    def __iter__(self) -> Iterator[str]:
        from .plugin_registry import list_model_plugins
        return iter(tuple(row.plugin_id for row in list_model_plugins()))

    def __len__(self) -> int:
        from .plugin_registry import list_model_plugins
        return len(list_model_plugins())


INSTANCE_ADAPTERS = _InstanceAdapterCompatibilityView()


def _default_parameters(contract: ModelContract) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for spec in contract.parameter_schema:
        if spec.role == "fixed":
            result[spec.key] = copy_plain_data(spec.fixed_value)
        elif spec.default is not None:
            result[spec.key] = copy_plain_data(spec.default)
    return result


def _base_instance(
    contract: ModelContract,
    parameters: Mapping[str, Any],
    target_sector: Mapping[str, Any],
    *,
    source_metadata: Mapping[str, Any],
    task_id: str | None = None,
    observables: tuple[str, ...] | None = None,
) -> ModelInstance:
    parameters = {
        key: value
        for key, value in parameters.items()
        if key not in RUN_CONTROL_KEYS
    }
    units = {
        "energy": str(parameters.get("energy_unit", "unspecified")),
    }
    # Units are declared by the contract.  A navigation/family label must not
    # decide scientific semantics at the instance boundary.
    for quantity, declaration in contract.units.items():
        if str(quantity) == "energy":
            continue
        if str(declaration) in {
            "same_as_energy",
            "declared_by_instance",
        }:
            units[str(quantity)] = units["energy"]
    instance = ModelInstance(
        instance_id=f"instance-{uuid4().hex[:12]}",
        model_id=contract.model_id,
        model_version=contract.model_version,
        task_id=task_id or contract.supported_tasks[0],
        parameters=dict(parameters),
        target_sector=dict(target_sector),
        requested_observables=observables or (contract.supported_observables[0],),
        units=units,
        source_metadata=dict(source_metadata),
    )
    instance.validate_against(contract)
    return instance


LEGACY_REQUEST_MODEL_ALIASES: Dict[tuple[str, str], str] = {
    ("fermion_pairing", "four_level_one_pair"): "nuclear.reduced_pairing.one_pair",
    ("fermion_pairing", "one_pair_pairing"): "nuclear.reduced_pairing.one_pair",
    ("fermion_pairing", "multi_pair_seniority_zero"): "nuclear.reduced_pairing.multi_pair",
    ("fermion_pairing", "multi_pair_pairing"): "nuclear.reduced_pairing.multi_pair",
    ("general_spin_orbital", "mapping_explorer"): "fermion.general_spin_orbital",
    ("general_spin_orbital", "jw_ground_state"): "fermion.general_spin_orbital",
    ("oscillator", "hard_core_modes_one_quantum"): "nuclear.oscillator.hard_core.one_quantum",
    ("custom", "guided_occupation_model"): "custom.occupation_coupling.one_excitation",
    ("custom", "pauli_input"): "custom.qubit_hamiltonian",
    ("custom", "matrix_input"): "custom.qubit_hamiltonian",
    ("custom", "advanced_matrix_or_pauli"): "custom.qubit_hamiltonian",
    **{("oscillator", model_id): model_id for model_id in QHO_MODEL_IDS},
}


def infer_model_id(request: Mapping[str, Any]) -> str:
    """Resolve legacy route aliases to one exact ModelContract ID.

    The authoritative path is an explicit ``model_id``.  Legacy ``method`` and
    ``problem`` fields are accepted only through this exact alias table; no
    particle count, family label, or other scientific value silently switches
    the model contract.
    """
    if request.get("model_id"):
        return str(request["model_id"])
    method = str(request.get("method", "")).strip()
    problem = str(request.get("problem", "")).strip()
    try:
        return LEGACY_REQUEST_MODEL_ALIASES[(method, problem)]
    except KeyError as exc:
        raise ModelContractError(
            "Could not resolve an exact model contract from the legacy route "
            f"(method={method!r}, problem={problem!r}). Supply model_id explicitly; "
            "QCOL does not infer a scientific model from a family label or parameter values."
        ) from exc


def instance_from_request(request: Mapping[str, Any]) -> ModelInstance:
    from .plugin_registry import get_model_plugin

    model_id = infer_model_id(request)
    plugin = get_model_plugin(model_id)
    return plugin.build_instance(request)


def one_pair_instance(request: Mapping[str, Any], contract: ModelContract) -> ModelInstance:
    p = _default_parameters(contract)
    p.update(dict(request.get("parameters", {})))
    p.pop("mapping", None)  # UI-inspectable policy, not a physical parameter.
    p["n_levels"] = int(p.get("n_levels", len(p.get("epsilon", [])) or 4))
    p["epsilon"] = [float(v) for v in p.get("epsilon", [0, 1, 2, 3])]
    p["g"] = float(p.get("g", 0.5))
    p["n_particles"] = 2
    p["n_pairs"] = 1
    p["seniority"] = 0
    p["energy_unit"] = str(p.get("energy_unit", "MeV"))
    task_id = canonical_task_id(request.get("task_id"))
    observables = ("pair_occupations",) if task_id == "observable_estimation" else ("sector_energy",)
    return _base_instance(
        contract,
        p,
        {"particle_number": 2, "pair_number": 1, "seniority": 0},
        source_metadata={"source": "QCOL request", "legacy_problem": request.get("problem")},
        task_id=task_id,
        observables=observables,
    )


def multi_pair_instance(request: Mapping[str, Any], contract: ModelContract) -> ModelInstance:
    p = _default_parameters(contract)
    p.update(dict(request.get("parameters", {})))
    p.pop("mapping", None)  # Resolver owns the mapping policy.
    p["n_levels"] = int(p.get("n_levels", len(p.get("epsilon", [])) or 4))
    p["epsilon"] = [float(v) for v in p.get("epsilon", [0, 1, 2, 3])]
    p["g"] = float(p.get("g", 0.5))
    p["n_pairs"] = int(p.get("n_pairs", max(int(p.get("n_particles", 4)) // 2, 2)))
    p["n_particles"] = 2 * p["n_pairs"]
    p["seniority"] = 0
    p["energy_unit"] = str(p.get("energy_unit", "MeV"))
    return _base_instance(
        contract,
        p,
        {"particle_number": p["n_particles"], "pair_number": p["n_pairs"], "seniority": 0},
        source_metadata={
            "source": "QCOL request",
            "implementation_origin": "Bathri qcol_platform multi-pair-capable route",
            "legacy_problem": request.get("problem"),
        },
        task_id=canonical_task_id(request.get("task_id")),
        observables=("sector_energy",),
    )


def oscillator_instance(request: Mapping[str, Any], contract: ModelContract) -> ModelInstance:
    p = _default_parameters(contract)
    p.update(dict(request.get("parameters", {})))
    p["n_modes"] = int(p.get("n_modes", 4))
    p["n_quanta"] = 1
    p["energy_unit"] = str(p.get("energy_unit", "MeV"))
    return _base_instance(
        contract,
        p,
        {"excitation_number": 1},
        source_metadata={"source":"QCOL request", "legacy_problem":request.get("problem")},
        task_id=canonical_task_id(request.get("task_id")),
        observables=("sector_energy",),
    )


def qho_instance(request: Mapping[str, Any], contract: ModelContract) -> ModelInstance:
    """Build any registered QHO ModelInstance from its declarative schema.

    The four model IDs share this adapter and all downstream policies.  Fixed
    interaction values are injected by ``_default_parameters`` and validated by
    the selected contract; the runtime never branches on the QHO subtype.
    """
    p = _default_parameters(contract)
    p.update(dict(request.get("parameters", {})))
    p["n_modes"] = int(p.get("n_modes", 4))
    p["n_quanta"] = 1
    p["energy_unit"] = str(p.get("energy_unit", "MeV"))
    profile = contract.to_dict().get("representation_contract", {}).get(
        "interaction_profile", {}
    )
    return _base_instance(
        contract,
        p,
        {"excitation_number": 1},
        source_metadata={
            "source": "QCOL schema-driven QHO request",
            "interaction_profile": profile,
            "legacy_problem": request.get("problem"),
        },
        task_id=canonical_task_id(request.get("task_id")),
        observables=("sector_energy",),
    )




def guided_instance(request: Mapping[str, Any], contract: ModelContract) -> ModelInstance:
    p = _default_parameters(contract)
    p.update(dict(request.get("parameters", {})))
    # Legacy UI used 'coupling_matrix'; keep scalar/matrix values as supplied.
    p["n_modes"] = int(p.get("n_modes", len(p.get("onsite_energies", [])) or 4))
    p["onsite_energies"] = [float(v) for v in p.get("onsite_energies", [0,1,2,3])]
    p["n_excitations"] = 1
    p["energy_unit"] = str(p.get("energy_unit", "MeV"))
    return _base_instance(
        contract,
        p,
        {"excitation_number":1},
        source_metadata={
            "source": "QCOL guided custom request",
            # Compatibility/provenance only. Scientific identity continues to
            # come from the canonical ModelContract and resolved policies.
            "legacy_problem": request.get("problem"),
        },
        task_id=canonical_task_id(request.get("task_id")),
        observables=("sector_energy",),
    )


def custom_qubit_instance(request: Mapping[str, Any], contract: ModelContract) -> ModelInstance:
    p = _default_parameters(contract)
    source = dict(request.get("parameters", {}))
    problem = str(request.get("problem", source.get("input_route", "matrix_input")))
    route = "pauli" if "pauli" in problem else "matrix"
    p["input_route"] = route
    if route == "matrix":
        p["matrix"] = source.get("matrix", source.get("matrix_str", p["matrix"]))
    else:
        p["pauli_terms"] = source.get("pauli_terms", p["pauli_terms"])
        p["n_qubits"] = int(source.get("n_qubits", p["n_qubits"]))
    p["ansatz_layers"] = int(source.get("ansatz_layers", p["ansatz_layers"]))
    p["energy_unit"] = str(source.get("energy_unit", "unspecified"))
    return _base_instance(
        contract,
        p,
        {},
        source_metadata={"source":"QCOL custom qubit request", "input_route":route},
        task_id=canonical_task_id(request.get("task_id")),
        observables=("ground_state_energy",),
    )


def general_spin_orbital_instance(request: Mapping[str, Any], contract: ModelContract) -> ModelInstance:
    p = _default_parameters(contract)
    p.update(dict(request.get("parameters", {})))
    task_id = canonical_task_id(request.get("task_id", "mapping_analysis"))

    p["n_modes"] = int(p.get("n_modes", 4))
    p["target_particle_number"] = int(
        p.get("target_particle_number", min(2, p["n_modes"]))
    )
    p["particle_species"] = p.get("particle_species", "neutron")
    p["energy_unit"] = str(p.get("energy_unit", "MeV"))
    p["coefficient_convention"] = str(
        p.get("coefficient_convention", "explicit_operator_coefficient")
    )
    p["operator_ordering_convention"] = "a_p^ a_q^ a_s a_r"

    symmetries = p.get("declared_symmetries", ("particle_number",))
    if isinstance(symmetries, str):
        symmetries = tuple(
            item.strip() for item in symmetries.split(",") if item.strip()
        )
    p["declared_symmetries"] = tuple(symmetries)

    initial_modes = p.get("initial_occupied_modes", ())
    if initial_modes is None:
        initial_modes = tuple()
    elif isinstance(initial_modes, str):
        initial_modes = tuple(
            int(item.strip())
            for item in initial_modes.split(",")
            if item.strip()
        )
    else:
        initial_modes = tuple(int(item) for item in initial_modes)
    p["initial_occupied_modes"] = initial_modes
    p["ansatz_layers"] = int(p.get("ansatz_layers", 1))

    species = p.get("particle_species", "neutron")
    first_species = str(species).split(",")[0].strip() or "fermion"
    if task_id == "mapping_analysis":
        observables = ("mapping_resources", "mapping_equivalence")
        legacy_problem = request.get("problem", "mapping_explorer")
    else:
        observables = ("sector_energy", "particle_number")
        legacy_problem = request.get("problem", "jw_ground_state")

    return _base_instance(
        contract,
        p,
        {
            "particle_number": p["target_particle_number"],
            "particle_numbers": {first_species: p["target_particle_number"]},
        },
        source_metadata={
            "source": "QCOL general spin-orbital request",
            "representation": "spin_orbital_occupation",
            "legacy_problem": legacy_problem,
            "resolved_mapping_intent": (
                "jordan_wigner.v1 + bravyi_kitaev.v1"
                if task_id == "mapping_analysis"
                else "jordan_wigner.v1"
            ),
        },
        task_id=task_id,
        observables=observables,
    )

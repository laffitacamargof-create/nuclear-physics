"""Gate-0 minimal public reading contract for QCOL.

Only :class:`ScientificRealizationView` is frozen.  It is a read-only boundary
projection for external consumers, not an internal communication bus.  The
projector reads already-resolved identities and makes no new scientific choice.
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Optional

from .runtime_integrity import scientific_identity_fingerprint

SCIENTIFIC_REALIZATION_VIEW_SCHEMA = "qcol-scientific-realization-view/1.0"
SCIENTIFIC_FINGERPRINT_INPUT_FIELDS = (
    "model_id", "task_id", "target_sector", "encoding_context_id",
    "mapping_policy_id", "state_preparation_policy_id", "ansatz_policy_id",
    "measurement_policy_id", "reference_policy_id",
)


def _plain(value: Any) -> Any:
    if is_dataclass(value):
        return {item.name: _plain(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_plain(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if hasattr(value, "to_public_dict") and callable(value.to_public_dict):
        return _plain(value.to_public_dict())
    if hasattr(value, "metadata") and callable(value.metadata):
        return _plain(value.metadata())
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return _plain(value.to_dict())
    return str(value)


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple, set, frozenset)):
        return tuple(_freeze(item) for item in value)
    return value


def _mapping(value: Any) -> Mapping[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return value
    if hasattr(value, "to_public_dict") and callable(value.to_public_dict):
        result = value.to_public_dict(); return result if isinstance(result, Mapping) else {}
    if hasattr(value, "metadata") and callable(value.metadata):
        result = value.metadata(); return result if isinstance(result, Mapping) else {}
    if hasattr(value, "to_dict") and callable(value.to_dict):
        result = value.to_dict(); return result if isinstance(result, Mapping) else {}
    return {}


def _attribute_or_key(source: Any, key: str, default: Any = None) -> Any:
    if isinstance(source, Mapping):
        return source.get(key, default)
    return getattr(source, key, default)


def _first_nonempty(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", (), [], {}):
            return value
    return None


def _require_text(name: str, value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} must be a non-empty public identifier.")
    return text


def scientific_view_fingerprint(*, model_id: str, task_id: str,
    target_sector: Mapping[str, Any], encoding_context_id: str,
    mapping_policy_id: str, state_preparation_policy_id: Optional[str],
    ansatz_policy_id: Optional[str], measurement_policy_id: Optional[str],
    reference_policy_id: Optional[str]) -> str:
    return scientific_identity_fingerprint(
        model_id=model_id, task_id=task_id, target_sector=_plain(target_sector),
        encoding_context_id=encoding_context_id, mapping_policy_id=mapping_policy_id,
        state_preparation_policy_id=state_preparation_policy_id,
        ansatz_policy_id=ansatz_policy_id,
        measurement_policy_id=measurement_policy_id,
        reference_policy_id=reference_policy_id,
    )


@dataclass(frozen=True)
class ScientificRealizationView:
    schema_version: str = field(default=SCIENTIFIC_REALIZATION_VIEW_SCHEMA, init=False)
    model_id: str = ""
    task_id: str = ""
    target_sector: Mapping[str, Any] = field(default_factory=dict)
    encoding_context_id: str = ""
    mapping_policy_id: str = ""
    state_preparation_policy_id: Optional[str] = None
    ansatz_policy_id: Optional[str] = None
    measurement_policy_id: Optional[str] = None
    reference_policy_id: Optional[str] = None
    controller_id: str = ""
    scientific_fingerprint: str = field(default="", init=False)

    def __post_init__(self) -> None:
        for name in ("model_id", "task_id", "encoding_context_id", "mapping_policy_id", "controller_id"):
            object.__setattr__(self, name, _require_text(name, getattr(self, name)))
        object.__setattr__(self, "target_sector", _freeze(_plain(self.target_sector)))
        for name in ("state_preparation_policy_id", "ansatz_policy_id", "measurement_policy_id", "reference_policy_id"):
            value = getattr(self, name)
            object.__setattr__(self, name, None if value in (None, "") else str(value))
        object.__setattr__(self, "scientific_fingerprint", scientific_view_fingerprint(
            model_id=self.model_id, task_id=self.task_id, target_sector=self.target_sector,
            encoding_context_id=self.encoding_context_id, mapping_policy_id=self.mapping_policy_id,
            state_preparation_policy_id=self.state_preparation_policy_id,
            ansatz_policy_id=self.ansatz_policy_id,
            measurement_policy_id=self.measurement_policy_id,
            reference_policy_id=self.reference_policy_id,
        ))

    def to_dict(self) -> dict[str, Any]:
        return _plain(self)


def _runtime_public(realization: Any, public: Mapping[str, Any]) -> Mapping[str, Any]:
    runtime = _attribute_or_key(realization, "runtime_artifact")
    if runtime is not None:
        mapped = _mapping(runtime)
        if mapped:
            return mapped
    if isinstance(public.get("scientific_context"), Mapping):
        return public
    return {}


def _derive_encoding_context(model_id: str, task_id: str, parameters: Mapping[str, Any],
                             target_sector: Mapping[str, Any], n_qubits: Any) -> Optional[str]:
    if model_id.startswith("nuclear.reduced_pairing."):
        n_levels = parameters.get("n_levels", n_qubits)
        n_pairs = target_sector.get("pair_number", parameters.get("n_pairs"))
        if n_levels is not None and n_pairs is not None:
            return f"pair.encoding-context.{int(n_levels)}levels.{int(n_pairs)}pairs.v1"
    if model_id.startswith("nuclear.qho.") or model_id == "nuclear.oscillator.hard_core.one_quantum":
        n_modes = parameters.get("n_modes", n_qubits)
        number = target_sector.get("excitation_number", parameters.get("n_quanta", 1))
        if n_modes is not None:
            return f"hard_core_mode.encoding-context.{int(n_modes)}modes.N{int(number)}.v1"
    if model_id == "custom.occupation_coupling.one_excitation":
        n_modes = parameters.get("n_modes", n_qubits)
        number = target_sector.get("excitation_number", parameters.get("n_excitations", 1))
        if n_modes is not None:
            return f"guided_occupation.encoding-context.{int(n_modes)}modes.N{int(number)}.v1"
    if model_id == "custom.qubit_hamiltonian" and n_qubits is not None:
        return f"custom_qubit.encoding-context.{int(n_qubits)}qubits.v1"
    if model_id == "fermion.general_spin_orbital":
        n_modes = parameters.get("n_modes", n_qubits)
        if n_modes is not None:
            if task_id == "mapping_analysis":
                return f"spin_orbital.mode_order.{int(n_modes)}.v1"
            particle_number = target_sector.get("particle_number", parameters.get("target_particle_number"))
            if particle_number is not None:
                return f"jw.encoding-context.{int(n_modes)}modes.N{int(particle_number)}.v1"
    return None


def scientific_realization_view(realization: Any, *, encoding_context_id: Optional[str] = None,
                                policy_overrides: Optional[Mapping[str, Any]] = None) -> ScientificRealizationView:
    """Project the frozen public view from one already-resolved realization.

    Step-2 ``QuantumRealizationArtifact`` instances carry all public identities
    directly.  The compatibility projection below is retained only for frozen
    Gate-0/Step-1 fixture dictionaries and never runs for a canonical artifact.
    """
    public = _mapping(realization)

    direct = {
        name: _attribute_or_key(realization, name, public.get(name))
        for name in (
            "model_id", "task_id", "target_sector", "encoding_context_id",
            "mapping_policy_id", "state_preparation_policy_id",
            "ansatz_policy_id", "measurement_policy_id",
            "reference_policy_id", "controller_id", "scientific_fingerprint",
        )
    }
    if all(
        direct.get(name) not in (None, "")
        for name in (
            "model_id", "task_id", "target_sector", "encoding_context_id",
            "mapping_policy_id", "controller_id",
        )
    ):
        view = ScientificRealizationView(
            model_id=str(direct["model_id"]),
            task_id=str(direct["task_id"]),
            target_sector=_mapping(direct["target_sector"]),
            encoding_context_id=str(direct["encoding_context_id"]),
            mapping_policy_id=str(direct["mapping_policy_id"]),
            state_preparation_policy_id=direct["state_preparation_policy_id"],
            ansatz_policy_id=direct["ansatz_policy_id"],
            measurement_policy_id=direct["measurement_policy_id"],
            reference_policy_id=direct["reference_policy_id"],
            controller_id=str(direct["controller_id"]),
        )
        supplied = str(direct.get("scientific_fingerprint") or "").strip()
        if supplied and supplied != view.scientific_fingerprint:
            raise ValueError(
                "Canonical realization scientific_fingerprint does not match "
                "the frozen Gate-0 identity vocabulary."
            )
        return view

    # Compatibility-only path for pre-Step-2 fixture dictionaries.
    runtime = _runtime_public(realization, public)
    scientific_context = _mapping(runtime.get("scientific_context"))
    provenance = _mapping(runtime.get("provenance"))
    quantum_provenance = _mapping(provenance.get("quantum_realization"))

    contract = _mapping(_first_nonempty(
        _attribute_or_key(realization, "contract_snapshot"), public.get("contract_snapshot"),
        scientific_context.get("model_contract"),
    ))
    resolved = _mapping(_first_nonempty(
        _attribute_or_key(realization, "resolved_plan_snapshot"), public.get("resolved_plan_snapshot"),
        scientific_context.get("resolved_model_plan"),
    ))
    policy_bindings = _mapping(_first_nonempty(resolved.get("policy_bindings"), contract.get("policies")))
    contract_policies = _mapping(contract.get("policies"))
    task_contract = _mapping(_first_nonempty(
        _attribute_or_key(realization, "task_contract_snapshot"), public.get("task_contract_snapshot"),
        scientific_context.get("task_contract"),
    ))
    task_plan = _mapping(_first_nonempty(
        _attribute_or_key(realization, "task_execution_plan"), public.get("task_execution_plan"),
        scientific_context.get("task_execution_plan"),
    ))
    mapping_metadata = _mapping(_first_nonempty(
        _attribute_or_key(realization, "mapping_metadata"), public.get("mapping_metadata"),
        quantum_provenance.get("mapping_metadata"),
    ))
    parameter_schema = _mapping(_first_nonempty(
        _attribute_or_key(realization, "parameter_schema"), public.get("parameter_schema"),
        quantum_provenance.get("parameter_schema"),
    ))
    parameter_metadata = _mapping(parameter_schema.get("metadata"))
    initial_state = _mapping(_first_nonempty(
        _attribute_or_key(realization, "initial_state"), public.get("initial_state"),
        quantum_provenance.get("initial_state"),
    ))
    instance = _mapping(_first_nonempty(
        _attribute_or_key(realization, "instance_snapshot"), public.get("instance_snapshot"),
    ))
    parameters = _mapping(_first_nonempty(instance.get("parameters"), runtime.get("parameters")))
    overrides = _mapping(policy_overrides)

    model_id = str(_first_nonempty(_attribute_or_key(realization, "model_id"), public.get("model_id"), runtime.get("model_id")))
    task_id = str(_first_nonempty(_attribute_or_key(realization, "task_id"), public.get("task_id"), task_contract.get("task_id")))
    target_sector = _mapping(_first_nonempty(_attribute_or_key(realization, "target_sector"), public.get("target_sector"), runtime.get("target_sector")))
    n_qubits = _first_nonempty(public.get("n_qubits"), runtime.get("n_qubits"))

    def policy(name: str, *fallbacks: Any) -> Optional[str]:
        value = _first_nonempty(overrides.get(name), *fallbacks)
        return None if value is None else str(value)

    context_id = _first_nonempty(
        encoding_context_id, mapping_metadata.get("encoding_context_id"), mapping_metadata.get("context_id"),
        _derive_encoding_context(model_id, task_id, parameters, target_sector, n_qubits),
    )
    mapping_policy = policy("mapping_policy_id", mapping_metadata.get("policy_id"), policy_bindings.get("mapping"), contract.get("mapping_policy_id"), contract_policies.get("mapping"))
    state_policy = policy("state_preparation_policy_id", policy_bindings.get("state_preparation"), contract.get("state_preparation_policy_id"), contract_policies.get("state_preparation"))
    ansatz_policy = policy("ansatz_policy_id", parameter_metadata.get("policy_id"), policy_bindings.get("ansatz"), contract.get("ansatz_policy_id"), contract_policies.get("ansatz"))

    # Task contracts own controller/measurement/reference semantics for analysis
    # and observable tasks. Ground-state measurement/reference remain model-owned.
    controller = policy("controller_id", task_plan.get("controller_policy_id"), task_contract.get("controller_policy_id"), _attribute_or_key(realization, "runtime_policy_id"), public.get("runtime_policy_id"), policy_bindings.get("runtime"), contract_policies.get("runtime"))
    if task_id in {"mapping_analysis", "observable_estimation"}:
        measurement = policy("measurement_policy_id", task_plan.get("measurement_policy_id"), task_contract.get("measurement_policy_id"), policy_bindings.get("measurement"), contract_policies.get("measurement"))
        reference = policy("reference_policy_id", task_plan.get("reference_policy_id"), task_contract.get("reference_policy_id"), policy_bindings.get("reference"), contract_policies.get("reference"))
    else:
        measurement = policy("measurement_policy_id", policy_bindings.get("measurement"), contract.get("measurement_policy_id"), contract_policies.get("measurement"), task_plan.get("measurement_policy_id"))
        reference = policy("reference_policy_id", policy_bindings.get("reference"), contract.get("reference_policy_id"), contract_policies.get("reference"), task_plan.get("reference_policy_id"))

    # Existing Phase-C artifacts encode task-aware implementation identity in
    # their resolved metadata but not yet as top-level policy IDs. This boundary
    # projects those exact identities; no scientific alternative is selected.
    if task_id == "mapping_analysis" and model_id == "fermion.general_spin_orbital":
        state_policy = "analysis_only_state.v1"
        ansatz_policy = "analysis_only_ansatz.v1"
    if model_id == "fermion.general_spin_orbital" and task_id == "ground_state_energy" and (
        ansatz_policy == "jw.ansatz.mapped_fermionic_swap_network.v1"
        or parameter_metadata.get("family") == "jw_mapped_fermionic_swap_network"
        or parameter_schema.get("family") == "jw_mapped_fermionic_swap_network"
    ):
        mapping_policy = "jordan_wigner.spin_orbital.v1"
        state_policy = "jw.state.occupation_determinant.v1"
        ansatz_policy = "jw.ansatz.mapped_fermionic_swap_network.v1"
        measurement = "jw.measurement.pauli_energy_qwc.v1"
        reference = "jw.reference.fixed_particle_sector.v1"

    return ScientificRealizationView(
        model_id=model_id, task_id=task_id, target_sector=target_sector,
        encoding_context_id=_require_text("encoding_context_id", context_id),
        mapping_policy_id=_require_text("mapping_policy_id", mapping_policy),
        state_preparation_policy_id=state_policy, ansatz_policy_id=ansatz_policy,
        measurement_policy_id=measurement, reference_policy_id=reference,
        controller_id=_require_text("controller_id", controller),
    )


FROZEN_PUBLIC_VIEW_VOCABULARY = {
    "scientific_realization": {
        "schema_version": SCIENTIFIC_REALIZATION_VIEW_SCHEMA,
        "fields": [item.name for item in fields(ScientificRealizationView)],
        "fingerprint_input_fields": list(SCIENTIFIC_FINGERPRINT_INPUT_FIELDS),
    }
}
DEFERRED_PUBLIC_VIEW_SPECIFICATIONS = {
    "request": {"status": "specified_not_frozen", "fields": ["request_schema_version", "model_request", "task_request", "user_parameters", "requested_backend", "requested_scale"]},
    "resource": {"status": "specified_not_frozen", "fields": ["resource_profile_id", "estimated_qubits", "estimated_parameters", "estimated_measurements", "resource_envelope_status"]},
    "execution": {"status": "specified_not_frozen", "fields": ["execution_adapter", "target_backend", "shots", "seed", "execution_fingerprint"]},
    "evidence": {"status": "specified_not_frozen", "fields": ["scientific_fingerprint", "execution_fingerprint", "verification_decision", "acceptance_certificate", "evidence_freshness", "provenance"], "note": "Acceptance and provenance remain lightweight nested records when this view is demanded."},
}

__all__ = [
    "SCIENTIFIC_REALIZATION_VIEW_SCHEMA", "SCIENTIFIC_FINGERPRINT_INPUT_FIELDS",
    "ScientificRealizationView", "scientific_view_fingerprint",
    "scientific_realization_view", "FROZEN_PUBLIC_VIEW_VOCABULARY",
    "DEFERRED_PUBLIC_VIEW_SPECIFICATIONS",
]

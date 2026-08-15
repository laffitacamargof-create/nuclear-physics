"""Domain-specific contracts for a general spin-orbital fermionic representation.

This layer is deliberately not a claim that a complete nuclear model has been
supplied.  It standardizes a second-quantized Hamiltonian, mode semantics,
particle-number sector, coefficient convention, and provenance so that mapping
plugins can transform and analyze the same physical input without ambiguity.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import math
from types import MappingProxyType
from typing import Any, Dict, Iterable, Mapping, Sequence, Tuple

from ..model_contracts import ModelContractError, ModelInstance

SPIN_ORBITAL_CONTRACT_SCHEMA = "qcol-general-spin-orbital-contract/1.0"
SPIN_ORBITAL_INSTANCE_SCHEMA = "qcol-spin-orbital-instance/1.0"
SUPPORTED_COEFFICIENT_CONVENTIONS = {
    "explicit_operator_coefficient",
    "antisymmetrized_v_with_quarter_prefactor",
}
SUPPORTED_OPERATOR_ORDERING_CONVENTIONS = {
    "a_p^ a_q^ a_s a_r",
}


def _freeze_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType({str(k): v for k, v in dict(value).items()})


def _complex_to_dict(value: complex) -> Dict[str, float]:
    return {"real": float(value.real), "imag": float(value.imag)}


def _parse_complex(value: Any) -> complex:
    if isinstance(value, complex):
        result = value
    elif isinstance(value, (int, float)):
        result = complex(float(value), 0.0)
    elif isinstance(value, Mapping):
        result = complex(float(value.get("real", 0.0)), float(value.get("imag", 0.0)))
    else:
        text = str(value).strip().replace("i", "j")
        result = complex(text)
    if not (math.isfinite(result.real) and math.isfinite(result.imag)):
        raise ModelContractError(f"Non-finite complex coefficient: {value!r}")
    return result


@dataclass(frozen=True)
class ModeLabel:
    index: int
    species: str
    orbital: str
    projection: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if int(self.index) < 0:
            raise ModelContractError("Mode index must be non-negative.")
        if not str(self.species).strip():
            raise ModelContractError("Mode species must be declared.")
        if not str(self.orbital).strip():
            raise ModelContractError("Mode orbital label must be declared.")
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))

    @classmethod
    def from_any(cls, value: Any, *, default_index: int) -> "ModeLabel":
        if isinstance(value, cls):
            return value
        if isinstance(value, Mapping):
            return cls(
                index=int(value.get("index", default_index)),
                species=str(value.get("species", "fermion")),
                orbital=str(value.get("orbital", value.get("label", f"mode_{default_index}"))),
                projection=str(value.get("projection", "")),
                metadata=dict(value.get("metadata", {})),
            )
        text = str(value).strip()
        parts = [part.strip() for part in text.split("|")]
        if len(parts) == 1:
            return cls(default_index, "fermion", parts[0] or f"mode_{default_index}")
        if len(parts) == 2:
            return cls(default_index, parts[0] or "fermion", parts[1] or f"mode_{default_index}")
        return cls(default_index, parts[0] or "fermion", parts[1] or f"mode_{default_index}", parts[2])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": int(self.index),
            "species": self.species,
            "orbital": self.orbital,
            "projection": self.projection,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class OneBodyTerm:
    p: int
    q: int
    coefficient: complex

    def __post_init__(self) -> None:
        object.__setattr__(self, "p", int(self.p))
        object.__setattr__(self, "q", int(self.q))
        object.__setattr__(self, "coefficient", _parse_complex(self.coefficient))

    @classmethod
    def from_any(cls, value: Any) -> "OneBodyTerm":
        if isinstance(value, cls):
            return value
        if isinstance(value, Mapping):
            return cls(value["p"], value["q"], value.get("coefficient", value.get("value", 0.0)))
        seq = list(value)
        if len(seq) == 3:
            return cls(seq[0], seq[1], seq[2])
        if len(seq) == 4:
            return cls(seq[0], seq[1], complex(float(seq[2]), float(seq[3])))
        raise ModelContractError(f"One-body term requires p,q,coefficient: {value!r}")

    def to_dict(self) -> Dict[str, Any]:
        return {"p": self.p, "q": self.q, "coefficient": _complex_to_dict(self.coefficient)}


@dataclass(frozen=True)
class TwoBodyTerm:
    p: int
    q: int
    r: int
    s: int
    coefficient: complex

    def __post_init__(self) -> None:
        for name in ("p", "q", "r", "s"):
            object.__setattr__(self, name, int(getattr(self, name)))
        object.__setattr__(self, "coefficient", _parse_complex(self.coefficient))

    @classmethod
    def from_any(cls, value: Any) -> "TwoBodyTerm":
        if isinstance(value, cls):
            return value
        if isinstance(value, Mapping):
            return cls(
                value["p"], value["q"], value["r"], value["s"],
                value.get("coefficient", value.get("value", 0.0)),
            )
        seq = list(value)
        if len(seq) == 5:
            return cls(seq[0], seq[1], seq[2], seq[3], seq[4])
        if len(seq) == 6:
            return cls(seq[0], seq[1], seq[2], seq[3], complex(float(seq[4]), float(seq[5])))
        raise ModelContractError(f"Two-body term requires p,q,r,s,coefficient: {value!r}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "p": self.p, "q": self.q, "r": self.r, "s": self.s,
            "coefficient": _complex_to_dict(self.coefficient),
        }


@dataclass(frozen=True)
class GeneralSpinOrbitalModelContract:
    """Representation-level contract reusable by nuclear and benchmark plugins."""

    representation_id: str = "general_spin_orbital_fermion.v1"
    representation_version: str = "1.0.0"
    label: str = "General spin-orbital fermionic representation"
    hamiltonian_form: str = (
        "H = c I + sum_pq h_pq a_p^† a_q + "
        "sum_pqrs W_pqrs a_p^† a_q^† a_s a_r"
    )
    supported_coefficient_conventions: Tuple[str, ...] = tuple(sorted(SUPPORTED_COEFFICIENT_CONVENTIONS))
    required_metadata: Tuple[str, ...] = (
        "n_modes", "mode_labels", "particle_species", "target_particle_numbers",
        "coefficient_convention", "operator_ordering_convention", "units", "source_provenance",
    )
    compatible_mapping_ids: Tuple[str, ...] = ("jordan_wigner.v1", "bravyi_kitaev.v1")
    assumptions: Tuple[str, ...] = (
        "finite spin-orbital Fock space",
        "number-conserving one- and two-body Hamiltonian in the first release",
        "explicit mode ordering",
    )
    limitations: Tuple[str, ...] = (
        "this is an intermediate representation, not a complete nuclear model",
        "angular momentum, parity, and isospin are only available when supplied by an upstream model plugin",
        "mapping analysis does not imply a verified VQE path",
    )
    schema_version: str = SPIN_ORBITAL_CONTRACT_SCHEMA

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "representation_id": self.representation_id,
            "representation_version": self.representation_version,
            "label": self.label,
            "hamiltonian_form": self.hamiltonian_form,
            "supported_coefficient_conventions": list(self.supported_coefficient_conventions),
            "required_metadata": list(self.required_metadata),
            "compatible_mapping_ids": list(self.compatible_mapping_ids),
            "assumptions": list(self.assumptions),
            "limitations": list(self.limitations),
        }


GENERAL_SPIN_ORBITAL_REPRESENTATION = GeneralSpinOrbitalModelContract()


@dataclass(frozen=True)
class SpinOrbitalInstance:
    n_modes: int
    particle_species: Tuple[str, ...]
    mode_labels: Tuple[ModeLabel, ...]
    one_body_terms: Tuple[OneBodyTerm, ...]
    two_body_terms: Tuple[TwoBodyTerm, ...]
    target_particle_numbers: Mapping[str, int]
    declared_symmetries: Tuple[str, ...]
    units: str
    coefficient_convention: str = "explicit_operator_coefficient"
    operator_ordering_convention: str = "a_p^ a_q^ a_s a_r"
    constant: complex = 0.0
    source_provenance: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = SPIN_ORBITAL_INSTANCE_SCHEMA

    def __post_init__(self) -> None:
        n_modes = int(self.n_modes)
        if n_modes < 1:
            raise ModelContractError("n_modes must be positive.")
        object.__setattr__(self, "n_modes", n_modes)
        object.__setattr__(self, "particle_species", tuple(str(v) for v in self.particle_species))
        object.__setattr__(self, "mode_labels", tuple(ModeLabel.from_any(v, default_index=i) for i, v in enumerate(self.mode_labels)))
        object.__setattr__(self, "one_body_terms", tuple(OneBodyTerm.from_any(v) for v in self.one_body_terms))
        object.__setattr__(self, "two_body_terms", tuple(TwoBodyTerm.from_any(v) for v in self.two_body_terms))
        object.__setattr__(self, "target_particle_numbers", MappingProxyType({str(k): int(v) for k, v in self.target_particle_numbers.items()}))
        object.__setattr__(self, "declared_symmetries", tuple(str(v) for v in self.declared_symmetries))
        object.__setattr__(self, "constant", _parse_complex(self.constant))
        object.__setattr__(self, "source_provenance", _freeze_mapping(self.source_provenance))
        self.validate()

    def validate(self) -> None:
        if self.coefficient_convention not in SUPPORTED_COEFFICIENT_CONVENTIONS:
            raise ModelContractError(
                f"Unsupported coefficient convention {self.coefficient_convention!r}."
            )
        if self.operator_ordering_convention not in SUPPORTED_OPERATOR_ORDERING_CONVENTIONS:
            raise ModelContractError(
                f"Unsupported operator ordering convention {self.operator_ordering_convention!r}."
            )
        if len(self.mode_labels) != self.n_modes:
            raise ModelContractError("mode_labels must contain exactly n_modes entries.")
        indices = [mode.index for mode in self.mode_labels]
        if indices != list(range(self.n_modes)):
            raise ModelContractError(
                "Mode indices must be complete and ordered as 0..n_modes-1."
            )
        if not self.particle_species:
            raise ModelContractError("At least one particle species must be declared.")
        declared_species = set(self.particle_species)
        mode_species = [mode.species for mode in self.mode_labels]
        unknown_mode_species = sorted(set(mode_species) - declared_species)
        if unknown_mode_species:
            raise ModelContractError(
                "Mode labels use undeclared particle species: "
                f"{unknown_mode_species}."
            )
        unknown_target_species = sorted(set(self.target_particle_numbers) - declared_species)
        if unknown_target_species:
            raise ModelContractError(
                "Target particle numbers use undeclared species: "
                f"{unknown_target_species}."
            )
        for species, number in self.target_particle_numbers.items():
            available_modes = sum(label == species for label in mode_species)
            if number < 0 or number > available_modes:
                raise ModelContractError(
                    f"Target particle number for {species!r} is outside "
                    f"[0, {available_modes}] for the declared mode labels."
                )
        if self.total_target_particles > self.n_modes:
            raise ModelContractError("Total target particle number exceeds n_modes.")
        for term in (*self.one_body_terms, *self.two_body_terms):
            for index in (term.p, term.q, *(() if isinstance(term, OneBodyTerm) else (term.r, term.s))):
                if index < 0 or index >= self.n_modes:
                    raise ModelContractError(
                        f"Operator index {index} is outside [0, {self.n_modes - 1}]."
                    )
        if not str(self.units).strip():
            raise ModelContractError("Energy units must be declared.")

    @property
    def total_target_particles(self) -> int:
        return int(sum(self.target_particle_numbers.values()))

    @classmethod
    def from_model_instance(cls, instance: ModelInstance) -> "SpinOrbitalInstance":
        p = dict(instance.parameters)
        n_modes = int(p["n_modes"])
        raw_labels = p.get("mode_labels") or [f"fermion|mode_{i}" for i in range(n_modes)]
        if isinstance(raw_labels, str):
            raw_labels = [line.strip() for line in raw_labels.splitlines() if line.strip()]
        raw_one = _load_terms(p.get("one_body_terms", []))
        raw_two = _load_terms(p.get("two_body_terms", []))
        species = p.get("particle_species", "fermion")
        if isinstance(species, str):
            particle_species = tuple(item.strip() for item in species.split(",") if item.strip())
        else:
            particle_species = tuple(str(item) for item in species)
        target = dict(instance.target_sector.get("particle_numbers", {}))
        if not target:
            target = {particle_species[0]: int(p.get("target_particle_number", 0))}
        return cls(
            n_modes=n_modes,
            particle_species=particle_species,
            mode_labels=tuple(raw_labels),
            one_body_terms=tuple(raw_one),
            two_body_terms=tuple(raw_two),
            target_particle_numbers=target,
            declared_symmetries=tuple(p.get("declared_symmetries", ("particle_number",))),
            units=str(p.get("energy_unit", instance.units.get("energy", "unspecified"))),
            coefficient_convention=str(p.get("coefficient_convention", "explicit_operator_coefficient")),
            operator_ordering_convention=str(p.get("operator_ordering_convention", "a_p^ a_q^ a_s a_r")),
            constant=p.get("constant", 0.0),
            source_provenance={**dict(instance.source_metadata), "model_instance_id": instance.instance_id},
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "n_modes": self.n_modes,
            "particle_species": list(self.particle_species),
            "mode_labels": [item.to_dict() for item in self.mode_labels],
            "one_body_terms": [item.to_dict() for item in self.one_body_terms],
            "two_body_terms": [item.to_dict() for item in self.two_body_terms],
            "target_particle_numbers": dict(self.target_particle_numbers),
            "total_target_particles": self.total_target_particles,
            "declared_symmetries": list(self.declared_symmetries),
            "units": self.units,
            "coefficient_convention": self.coefficient_convention,
            "operator_ordering_convention": self.operator_ordering_convention,
            "constant": _complex_to_dict(self.constant),
            "source_provenance": dict(self.source_provenance),
        }


def _load_terms(value: Any) -> Sequence[Any]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if text.startswith("[") or text.startswith("{"):
            loaded = json.loads(text)
            if isinstance(loaded, Mapping):
                loaded = loaded.get("terms", [])
            return list(loaded)
        rows = []
        for line in text.splitlines():
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            rows.append([item.strip() for item in line.split(",")])
        return rows
    if isinstance(value, Mapping):
        return list(value.get("terms", []))
    return list(value)

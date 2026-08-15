"""Versioned numerical and statistical tolerance declarations for WP2."""
from __future__ import annotations

from dataclasses import dataclass, field

from qcol.realization_policies.base import DeclarativeContract, PolicyContractError, require_text, require_token


TOLERANCE_PROFILE_SCHEMA_VERSION = "qcol-tolerance-profile/1.0"


@dataclass(frozen=True)
class ToleranceProfile(DeclarativeContract):
    profile_id: str
    profile_version: str
    label: str
    algebra_operator_norm: float
    basis_overlap: float
    matrix_relative_frobenius: float
    eigenvalue_absolute: float
    generator_unitary: float
    sector_leakage: float
    qasm_semantic: float
    statistical_sigma_multiplier: float
    absolute_numerical_floor: float
    minimum_sampled_seeds: int
    minimum_random_parameter_points: int
    units_policy: str = "task_declared_units"
    scope_statement: str = "small ideal deterministic fixtures unless overridden"
    notes: tuple[str, ...] = field(default_factory=tuple)
    schema_version: str = TOLERANCE_PROFILE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in ("profile_id", "profile_version", "units_policy"):
            require_token(name, getattr(self, name))
        require_text("label", self.label)
        require_text("scope_statement", self.scope_statement)
        for name in (
            "algebra_operator_norm", "basis_overlap", "matrix_relative_frobenius",
            "eigenvalue_absolute", "generator_unitary", "sector_leakage",
            "qasm_semantic", "absolute_numerical_floor",
        ):
            value = float(getattr(self, name))
            if value < 0:
                raise PolicyContractError(f"{name} must be non-negative.")
            object.__setattr__(self, name, value)
        sigma = float(self.statistical_sigma_multiplier)
        if sigma <= 0:
            raise PolicyContractError("statistical_sigma_multiplier must be positive.")
        object.__setattr__(self, "statistical_sigma_multiplier", sigma)
        if int(self.minimum_sampled_seeds) <= 0:
            raise PolicyContractError("minimum_sampled_seeds must be positive.")
        if int(self.minimum_random_parameter_points) <= 0:
            raise PolicyContractError("minimum_random_parameter_points must be positive.")
        object.__setattr__(self, "minimum_sampled_seeds", int(self.minimum_sampled_seeds))
        object.__setattr__(self, "minimum_random_parameter_points", int(self.minimum_random_parameter_points))
        object.__setattr__(self, "notes", tuple(require_text("notes", str(v)) for v in self.notes))


__all__ = ["TOLERANCE_PROFILE_SCHEMA_VERSION", "ToleranceProfile"]

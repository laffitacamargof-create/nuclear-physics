"""Build and validate OpenFermion objects from a spin-orbital instance."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from .contracts import SpinOrbitalInstance
from ..model_contracts import ModelContractError


@dataclass(frozen=True)
class FermionOperatorBuildResult:
    instance: SpinOrbitalInstance
    fermion_operator: Any
    particle_number_operator: Any
    validation_checks: Dict[str, bool]
    metadata: Dict[str, Any]


def build_fermion_operator(instance: SpinOrbitalInstance, *, hermiticity_tolerance: float = 1e-10) -> FermionOperatorBuildResult:
    try:
        from openfermion import FermionOperator, hermitian_conjugated, normal_ordered
    except ImportError as exc:  # pragma: no cover - scientific environment
        raise RuntimeError("OpenFermion is required to build a spin-orbital FermionOperator.") from exc

    operator = FermionOperator((), instance.constant)
    for term in instance.one_body_terms:
        operator += FermionOperator(((term.p, 1), (term.q, 0)), term.coefficient)
    prefactor = 0.25 if instance.coefficient_convention == "antisymmetrized_v_with_quarter_prefactor" else 1.0
    for term in instance.two_body_terms:
        # Contract convention: V[p,q,r,s] multiplies a_p^ a_q^ a_s a_r.
        operator += FermionOperator(
            ((term.p, 1), (term.q, 1), (term.s, 0), (term.r, 0)),
            prefactor * term.coefficient,
        )
    operator = normal_ordered(operator)
    operator.compress(abs_tol=hermiticity_tolerance)

    delta = normal_ordered(operator - hermitian_conjugated(operator))
    delta.compress(abs_tol=hermiticity_tolerance)
    hermitian = not delta.terms
    if not hermitian:
        preview = list(delta.terms.items())[:5]
        raise ModelContractError(
            "The declared spin-orbital Hamiltonian is not Hermitian under the "
            f"selected coefficient convention. Residual terms: {preview!r}"
        )

    number_operator = FermionOperator()
    for mode in range(instance.n_modes):
        number_operator += FermionOperator(((mode, 1), (mode, 0)), 1.0)
    number_operator.compress()

    return FermionOperatorBuildResult(
        instance=instance,
        fermion_operator=operator,
        particle_number_operator=number_operator,
        validation_checks={
            "indices_in_range": True,
            "coefficients_finite": True,
            "mode_order_complete": True,
            "particle_number_feasible": instance.total_target_particles <= instance.n_modes,
            "hermitian": hermitian,
            "coefficient_convention_declared": True,
        },
        metadata={
            "representation": "spin_orbital_occupation",
            "n_modes": instance.n_modes,
            "one_body_term_count": len(instance.one_body_terms),
            "two_body_term_count": len(instance.two_body_terms),
            "coefficient_convention": instance.coefficient_convention,
            "operator_ordering_convention": instance.operator_ordering_convention,
            "mode_labels": [item.to_dict() for item in instance.mode_labels],
            "target_particle_numbers": dict(instance.target_particle_numbers),
        },
    )

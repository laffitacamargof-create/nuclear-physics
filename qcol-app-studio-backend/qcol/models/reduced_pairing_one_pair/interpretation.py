"""Bounded physical interpretation supplied by the one-pair model plugin."""
from __future__ import annotations

from typing import Any, Dict


def build_one_pair_scientific_context(
    *,
    problem_contract: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "scientific_quantity": "lowest energy in the declared one-pair sector",
        "supported_statement": (
            "The sampled OpenQASM 2 workflow reconstructs the energy of the "
            "declared reduced pairing Hamiltonian in its one-pair "
            "seniority-zero sector."
        ),
        "limitations": [
            "small reduced pairing model",
            "one-pair seniority-zero sector",
            "not a full nuclear-structure prediction",
            "not a multi-pair or general fermionic route",
        ],
        "problem_contract": problem_contract,
    }

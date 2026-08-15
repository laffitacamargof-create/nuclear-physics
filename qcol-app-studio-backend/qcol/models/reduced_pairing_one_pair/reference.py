"""Trusted small-sector reference for the one-pair reduced-pairing plugin."""
from __future__ import annotations

from typing import Any, Dict, Sequence

import numpy as np

from ...modeling import exact_reference_from_matrix


def build_one_pair_sector_matrix(
    level_energies: Sequence[float],
    pairing_strength: float,
) -> np.ndarray:
    """Return the reduced pairing Hamiltonian in the one-pair sector."""
    epsilon = np.asarray(level_energies, dtype=float)
    if epsilon.ndim != 1 or epsilon.size < 2:
        raise ValueError("At least two one-pair levels are required.")
    if not np.all(np.isfinite(epsilon)):
        raise ValueError("One-pair energies must be finite.")
    g = float(pairing_strength)
    if not np.isfinite(g) or g <= 0:
        raise ValueError("The attractive one-pair reference requires finite G > 0.")

    matrix = np.full((epsilon.size, epsilon.size), -g, dtype=float)
    np.fill_diagonal(matrix, 2.0 * epsilon - g)
    return matrix


def solve_one_pair_reference(
    level_energies: Sequence[float],
    pairing_strength: float,
    *,
    acceptance_abs_floor: float = 0.05,
) -> Dict[str, Any]:
    """Build the exact reference used by the certified acceptance route."""
    matrix = build_one_pair_sector_matrix(level_energies, pairing_strength)
    return exact_reference_from_matrix(
        matrix,
        reference_scope="one-pair seniority-zero sector",
        acceptance_abs_floor=float(acceptance_abs_floor),
        target_state_labels=[
            f"pair_in_level_{level}" for level in range(matrix.shape[0])
        ],
    )

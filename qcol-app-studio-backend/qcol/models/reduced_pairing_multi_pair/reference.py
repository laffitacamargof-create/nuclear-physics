"""Independent fixed-pair-sector reference for reduced pairing models.

This module is deliberately independent of the qubit mapping.  It constructs
Hamiltonian matrix elements directly in the seniority-zero pair-occupation
basis, providing an acceptance reference that can detect mapping errors rather
than merely repeating them.
"""
from __future__ import annotations

from itertools import combinations
from typing import Iterable, Sequence, Tuple

import numpy as np


def build_reduced_pairing_sector_matrix(
    epsilon: Sequence[float],
    g: float,
    n_pairs: int,
) -> tuple[np.ndarray, tuple[tuple[int, ...], ...]]:
    energies = np.asarray(epsilon, dtype=float)
    n_levels = int(energies.size)
    n_pairs = int(n_pairs)
    g = float(g)
    if energies.ndim != 1 or n_levels < 1:
        raise ValueError('epsilon must be a non-empty one-dimensional sequence.')
    if not np.all(np.isfinite(energies)) or not np.isfinite(g) or g <= 0:
        raise ValueError('Reference construction requires finite epsilon and G > 0.')
    if not 0 < n_pairs < n_levels:
        raise ValueError('n_pairs must satisfy 0 < n_pairs < n_levels.')

    basis = tuple(combinations(range(n_levels), n_pairs))
    index = {state: i for i, state in enumerate(basis)}
    matrix = np.zeros((len(basis), len(basis)), dtype=complex)

    for row, occupied in enumerate(basis):
        occupied_set = set(occupied)
        matrix[row, row] = sum(2.0 * energies[p] - g for p in occupied)
        for source in occupied:
            for target in range(n_levels):
                if target in occupied_set:
                    continue
                moved = tuple(sorted((occupied_set - {source}) | {target}))
                col = index[moved]
                matrix[row, col] += -g

    if not np.allclose(matrix, matrix.conj().T, atol=1e-12):
        raise AssertionError('Direct fixed-pair-sector reference is not Hermitian.')
    return matrix, basis


def sector_ground_energy(epsilon: Sequence[float], g: float, n_pairs: int) -> float:
    matrix, _ = build_reduced_pairing_sector_matrix(epsilon, g, n_pairs)
    return float(np.linalg.eigvalsh(matrix)[0])

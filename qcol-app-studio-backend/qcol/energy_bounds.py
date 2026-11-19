"""Shared signed checks for a declared minimum-energy reference."""
from __future__ import annotations

import math
from typing import Any

DEFAULT_MINIMUM_ENERGY_TOLERANCE = 1e-9
DEFAULT_BELOW_REFERENCE_SIGMA_LIMIT = 3.0


def check_minimum_energy_bound(
    energy: float,
    reference_energy: float,
    standard_error: float = 0.0,
    *,
    tolerance: float | None = None,
    sigma_limit: float = DEFAULT_BELOW_REFERENCE_SIGMA_LIMIT,
) -> dict[str, Any]:
    """Classify an energy estimate without allowing a below-bound PASS.

    A finite-shot estimate below the bound by at most sigma_limit standard
    errors is a sampling review, never an acceptance. A statistically
    significant violation is invalid. Tiny floating-point deviations are
    absorbed by a scale-aware numerical tolerance.
    """
    value = float(energy)
    reference = float(reference_energy)
    sigma = max(0.0, float(standard_error))
    tol = (
        max(DEFAULT_MINIMUM_ENERGY_TOLERANCE,
            DEFAULT_MINIMUM_ENERGY_TOLERANCE * abs(reference))
        if tolerance is None else max(0.0, float(tolerance))
    )
    delta = value - reference
    z_below = (
        max(0.0, -delta) / sigma if sigma > 0.0
        else (math.inf if delta < -tol else 0.0)
    )
    if delta >= -tol:
        classification = "ABOVE_MINIMUM"
    elif sigma > 0.0 and z_below <= float(sigma_limit):
        classification = "REVIEW_SAMPLING_BELOW_REFERENCE"
    else:
        classification = "INVALID_BELOW_MINIMUM"
    return {
        "minimum_energy_bound": reference,
        "energy": value,
        "energy_minus_reference": delta,
        "standard_error": sigma,
        "z_below": z_below,
        "tolerance": tol,
        "classification": classification,
    }

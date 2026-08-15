"""Free bounded nuclear QHO contract."""
from __future__ import annotations

from ..qho_common import build_qho_contract

MODEL_ID = "nuclear.qho.free"
MODEL_VERSION = "1.0.0"

QHO_FREE_MODEL_CONTRACT = build_qho_contract(
    model_id=MODEL_ID,
    label="Free QHO",
    description=(
        "Uncoupled hard-core oscillator modes with on-site energy ω(n+1/2) "
        "only, including the zero-point contribution, in the one-quantum sector."
    ),
    problem_type="free_modes_one_quantum",
    coupling_enabled=False,
    kappa_enabled=False,
    assumptions=(
        "two-level hard-core occupation per mode",
        "fixed one-quantum sector",
        "zero-point ω/2 included",
    ),
    limitations=(
        "on-site term only; coupling and κ are fixed to zero",
        "not a full bosonic Fock-space oscillator",
    ),
)

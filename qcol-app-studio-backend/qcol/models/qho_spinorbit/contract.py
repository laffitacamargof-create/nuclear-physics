"""Diagonal spin-orbit-shift bounded nuclear QHO contract."""
from __future__ import annotations

from ..qho_common import build_qho_contract

MODEL_ID = "nuclear.qho.spinorbit"
MODEL_VERSION = "1.0.0"

QHO_SPINORBIT_MODEL_CONTRACT = build_qho_contract(
    model_id=MODEL_ID,
    label="Spin-orbit-shift QHO",
    description=(
        "Hard-core oscillator modes with on-site energy ω(n+1/2) and a "
        "per-mode diagonal shift −κ·Z, with coupling fixed to zero, in the "
        "one-quantum sector."
    ),
    problem_type="spinorbit_modes_one_quantum",
    coupling_enabled=False,
    kappa_enabled=True,
    assumptions=(
        "two-level hard-core occupation per mode",
        "fixed one-quantum sector",
        "κ denotes a diagonal shell shift, not a full L·S interaction",
    ),
    limitations=(
        "coupling is fixed to zero",
        "κ is a diagonal shift only",
        "not a full bosonic Fock-space oscillator",
    ),
)

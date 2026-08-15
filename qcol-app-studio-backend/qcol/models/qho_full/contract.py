"""Full bounded nuclear QHO contract with both interaction layers."""
from __future__ import annotations

from ..qho_common import build_qho_contract

MODEL_ID = "nuclear.qho.full"
MODEL_VERSION = "1.0.0"

QHO_FULL_MODEL_CONTRACT = build_qho_contract(
    model_id=MODEL_ID,
    label="Full QHO",
    description=(
        "Hard-core oscillator modes with on-site energy ω(n+1/2), "
        "pairing/hopping −(G/2)(XX+YY), and diagonal shell shift −κ·Z, "
        "in the one-quantum sector."
    ),
    problem_type="full_modes_one_quantum",
    coupling_enabled=True,
    kappa_enabled=True,
    assumptions=(
        "two-level hard-core occupation per mode",
        "fixed one-quantum sector",
        "pairing/hopping and diagonal shift compose in one declared Hamiltonian",
    ),
    limitations=(
        "κ is a diagonal shift, not a full L·S interaction",
        "not a full bosonic Fock-space oscillator",
    ),
)

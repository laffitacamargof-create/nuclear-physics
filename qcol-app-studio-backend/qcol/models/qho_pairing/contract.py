"""Pairing/hopping bounded nuclear QHO contract."""
from __future__ import annotations

from ..qho_common import build_qho_contract

MODEL_ID = "nuclear.qho.pairing"
MODEL_VERSION = "1.0.0"

QHO_PAIRING_MODEL_CONTRACT = build_qho_contract(
    model_id=MODEL_ID,
    label="Pairing QHO",
    description=(
        "Hard-core oscillator modes with on-site energy ω(n+1/2) and "
        "pairing/hopping −(G/2)(XX+YY), with κ fixed to zero, in the "
        "one-quantum sector."
    ),
    problem_type="pairing_modes_one_quantum",
    coupling_enabled=True,
    kappa_enabled=False,
    assumptions=(
        "two-level hard-core occupation per mode",
        "fixed one-quantum sector",
        "G is non-negative; the Hamiltonian applies the physical minus sign",
    ),
    limitations=(
        "κ is fixed to zero",
        "not a full bosonic Fock-space oscillator",
    ),
)

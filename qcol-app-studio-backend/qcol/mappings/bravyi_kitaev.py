"""Bravyi–Kitaev mapping plugin with analysis-ready support boundaries."""
from __future__ import annotations

from typing import Sequence, Tuple

from .base import FermionToQubitMappingPlugin, MappingCapabilityReport, MappingCompatibilityReport


def _encoder_matrix(n_modes: int):
    import numpy as np
    from openfermion import bravyi_kitaev_code

    code = bravyi_kitaev_code(int(n_modes))
    matrix = code.encoder
    if hasattr(matrix, "toarray"):
        matrix = matrix.toarray()
    return np.asarray(matrix, dtype=int) % 2


def _gf2_inverse(matrix):
    """Invert a square binary matrix over GF(2) without relying on decoder APIs."""
    import numpy as np

    a = np.asarray(matrix, dtype=int) % 2
    n = a.shape[0]
    if a.shape != (n, n):
        raise ValueError("BK encoder matrix must be square.")
    aug = np.concatenate([a.copy(), np.eye(n, dtype=int)], axis=1)
    for col in range(n):
        pivots = np.where(aug[col:, col] == 1)[0]
        if pivots.size == 0:
            raise ValueError("BK encoder matrix is singular over GF(2).")
        pivot = col + int(pivots[0])
        if pivot != col:
            aug[[col, pivot]] = aug[[pivot, col]]
        for row in range(n):
            if row != col and aug[row, col] == 1:
                aug[row] ^= aug[col]
    return aug[:, n:] % 2


class BKMappingPlugin(FermionToQubitMappingPlugin):
    mapping_id = "bravyi_kitaev.v1"
    mapping_version = "1.0.0"
    label = "Bravyi–Kitaev"
    support_by_task = {
        "mapping_analysis": "acceptance_verified",
        "ground_state_energy": "recognized_not_executable",
    }
    execution_boundary = (
        "Transformation, observable mapping, and occupation-code round trips are analysis-ready; "
        "BK state-preparation, sector diagnostics, and a compatible ansatz are not acceptance-verified."
    )

    def check_compatibility(self, spin_instance, *, task_id: str) -> MappingCompatibilityReport:
        checks = {
            "spin_orbital_representation": getattr(spin_instance, "n_modes", 0) > 0,
            "mode_order_declared": len(getattr(spin_instance, "mode_labels", ())) == getattr(spin_instance, "n_modes", 0),
            "number_conserving_first_release": "particle_number" in getattr(spin_instance, "declared_symmetries", ()),
            "task_supported": task_id in {"mapping_analysis", "ground_state_energy"},
        }
        reasons = tuple(key for key, passed in checks.items() if not passed)
        model_ok = (
            checks["spin_orbital_representation"]
            and checks["mode_order_declared"]
            and checks["number_conserving_first_release"]
        )
        return MappingCompatibilityReport(
            self.mapping_id,
            model_ok,
            checks["task_supported"],
            all(checks.values()),
            checks,
            reasons,
        )

    def transform_hamiltonian(self, fermion_operator, *, n_modes: int):
        from openfermion import bravyi_kitaev

        result = bravyi_kitaev(fermion_operator, n_qubits=int(n_modes))
        result.compress()
        return result

    def transform_observable(self, fermion_operator, *, n_modes: int):
        return self.transform_hamiltonian(fermion_operator, n_modes=n_modes)

    def encode_occupation_state(self, occupations: Sequence[int]) -> Tuple[int, ...]:
        # This encoder is verified as a representation-level transformation in
        # Phase A.3.1.  No BK state-preparation circuit is promoted yet.
        import numpy as np

        vector = np.asarray([int(value) & 1 for value in occupations], dtype=int)
        encoded = (_encoder_matrix(len(vector)) @ vector) % 2
        return tuple(int(value) for value in encoded.reshape(-1))

    def decode_basis_bitstring(self, bitstring: Sequence[int]) -> Tuple[int, ...]:
        import numpy as np

        bits = np.asarray([int(value) & 1 for value in bitstring], dtype=int)
        decoded = (_gf2_inverse(_encoder_matrix(len(bits))) @ bits) % 2
        return tuple(int(value) for value in decoded.reshape(-1))

    def occupation_encoding_metadata(self, n_modes: int):
        matrix = _encoder_matrix(int(n_modes))
        return {
            "encoding_family": "bravyi_kitaev_linear_gf2_code",
            "direct_mode_to_qubit": False,
            "encoder_matrix_gf2": matrix.astype(int).tolist(),
            "raw_popcount_is_particle_number": False,
            "particle_number_interpretation": "use the mapped particle-number observable or decode the BK code; never use raw qubit popcount",
            "basis_state_preparation_claim": "occupation-code transform implemented for analysis; a BK state-preparation circuit is not acceptance-verified",
        }

    def capability_report(self, spin_instance) -> MappingCapabilityReport:
        compatibility = self.check_compatibility(spin_instance, task_id="mapping_analysis")
        return MappingCapabilityReport(
            mapping_id=self.mapping_id,
            mapping_version=self.mapping_version,
            model_compatible=compatibility.model_compatible,
            transform_available=True,
            transform_verified=True,
            observable_transform_ready=True,
            analysis_ready=True,
            occupation_encoding_ready=True,
            particle_number_observable_ready=True,
            sector_verification_ready=False,
            ground_state_execution_ready=False,
            support_by_task=self.support_by_task,
            missing_capabilities=(
                "bk_state_preparation_circuit_acceptance",
                "bk_particle_number_sector_diagnostic_acceptance",
                "bk_compatible_ansatz_acceptance",
            ),
            overall_status="analysis_verified_full_execution_not_verified",
        )

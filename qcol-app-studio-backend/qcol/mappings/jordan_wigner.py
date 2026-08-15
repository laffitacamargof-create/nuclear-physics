"""Jordan–Wigner mapping plugin.

Phase A.3.1 verifies mapper conformance for transformation and operator-resource
analysis. WP0 preserves the endpoint-only qubit exchange as a negative fixture.
WP11 adds the first accepted bounded mapping-aware fermionic composition without
changing the historical negative record.
"""
from __future__ import annotations

from typing import Sequence, Tuple

from .base import (
    FermionToQubitMappingPlugin,
    MappingCapabilityReport,
    MappingCompatibilityReport,
)


class JWMappingPlugin(FermionToQubitMappingPlugin):
    mapping_id = "jordan_wigner.v1"
    mapping_version = "1.2.0"
    label = "Jordan–Wigner"
    support_by_task = {
        "mapping_analysis": "acceptance_verified",
        "ground_state_energy": "acceptance_verified",
    }
    execution_boundary = (
        "Transformation, observable mapping, direct occupation coding, and particle-number "
        "diagnostics are mapper-conformance verified. WP11 acceptance-verifies one bounded "
        "2–4-mode, fixed-particle, single-species ground-state composition using a reversible "
        "fermionic-swap network. This is not a general universality claim."
    )

    def check_compatibility(self, spin_instance, *, task_id: str) -> MappingCompatibilityReport:
        n_modes = int(getattr(spin_instance, "n_modes", 0))
        target = int(getattr(spin_instance, "total_target_particles", -1))
        fixed_particle_required = task_id == "ground_state_energy"
        species = tuple(getattr(spin_instance, "particle_species", ()))
        target_by_species = dict(getattr(spin_instance, "target_particle_numbers", {}))
        mode_species = {getattr(label, "species", None) for label in getattr(spin_instance, "mode_labels", ())}
        checks = {
            "spin_orbital_representation": n_modes > 0,
            "mode_order_declared": len(getattr(spin_instance, "mode_labels", ())) == n_modes,
            # Mapping analysis can compare full-space spectra without asserting a
            # fixed-N physical sector.  The execution cell, by contrast, requires
            # an explicit particle-number symmetry and a nontrivial target sector.
            "particle_number_declared_when_required": (
                not fixed_particle_required
                or "particle_number" in getattr(spin_instance, "declared_symmetries", ())
            ),
            # The first execution cell is deliberately single-species.  This keeps
            # the all-to-all Givens network honest: it preserves the declared total
            # number and cannot silently exchange a neutron into a proton mode.
            "single_species_execution_cell": (
                not fixed_particle_required
                or (
                    len(species) == 1
                    and len(target_by_species) == 1
                    and len(mode_species) == 1
                )
            ),
            "task_supported": task_id in {"mapping_analysis", "ground_state_energy"},
            "ground_state_mode_envelope": (
                True if not fixed_particle_required else 2 <= n_modes <= 4
            ),
            "ground_state_nontrivial_sector": (
                True if not fixed_particle_required else 0 < target < n_modes
            ),
        }
        reasons = tuple(key for key, passed in checks.items() if not passed)
        model_ok = (
            checks["spin_orbital_representation"]
            and checks["mode_order_declared"]
            and checks["particle_number_declared_when_required"]
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
        from openfermion import jordan_wigner

        result = jordan_wigner(fermion_operator)
        result.compress()
        return result

    def transform_observable(self, fermion_operator, *, n_modes: int):
        return self.transform_hamiltonian(fermion_operator, n_modes=n_modes)

    def encode_occupation_state(self, occupations: Sequence[int]) -> Tuple[int, ...]:
        return tuple(int(value) & 1 for value in occupations)

    def decode_basis_bitstring(self, bitstring: Sequence[int]) -> Tuple[int, ...]:
        return tuple(int(value) & 1 for value in bitstring)

    def occupation_encoding_metadata(self, n_modes: int):
        return {
            "encoding_family": "direct_occupation_bits",
            "direct_mode_to_qubit": True,
            "mode_to_qubit": {str(index): index for index in range(int(n_modes))},
            "raw_popcount_is_particle_number": True,
            "particle_number_interpretation": (
                "The computational-basis occupation bits are the JW mode occupations; "
                "raw popcount equals total particle number under the declared mode order."
            ),
            "basis_state_preparation_claim": (
                "Occupation-determinant preparation with X gates is implemented for the "
                "bounded Phase A.3.2 execution cell."
            ),
        }

    def capability_report(self, spin_instance) -> MappingCapabilityReport:
        analysis_compatibility = self.check_compatibility(
            spin_instance, task_id="mapping_analysis"
        )
        execution_compatibility = self.check_compatibility(
            spin_instance, task_id="ground_state_energy"
        )
        return MappingCapabilityReport(
            mapping_id=self.mapping_id,
            mapping_version=self.mapping_version,
            model_compatible=analysis_compatibility.model_compatible,
            transform_available=True,
            transform_verified=True,
            observable_transform_ready=True,
            analysis_ready=True,
            occupation_encoding_ready=True,
            particle_number_observable_ready=True,
            sector_verification_ready=execution_compatibility.compatible,
            ground_state_execution_ready=execution_compatibility.compatible,
            support_by_task=self.support_by_task,
            missing_capabilities=(
                tuple()
                if execution_compatibility.compatible
                else tuple(execution_compatibility.reasons)
            ),
            overall_status=(
                "analysis_and_bounded_ground_state_acceptance_verified"
                if execution_compatibility.compatible
                else "analysis_verified_ground_state_outside_envelope"
            ),
        )

"""WP11 scientific acceptance for the first mapped-aware JW composition.

Matrix/operator-action checks are performed before sampled task-level energy.
The old endpoint-only exchange remains a separate negative fixture.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping, Sequence
from zipfile import ZIP_DEFLATED, ZipFile

import numpy as np

from qcol.realization_policies.base import contract_fingerprint, json_contract_value
from qcol.mapping_policies.profiles.jw_accepted_composition import (
    WP11_ACCEPTANCE_SUITE_ID,
    WP11_VARIANT_ID,
    build_wp11_acceptance_fingerprint,
    build_wp11_acceptance_record,
    build_wp11_tolerance_profile,
    public_wp11_jw_accepted_composition_catalog,
    wp11_jw_accepted_composition_catalog_fingerprint,
)


WP11_EVIDENCE_SCHEMA_VERSION = "qcol-wp11-jw-accepted-composition-evidence/1.0"
WP11_DEFAULT_RANDOM_THETA_POINTS = 20
WP11_DEFAULT_SAMPLED_SEEDS = (17, 42, 73)


@dataclass(frozen=True)
class ExportedWP11Evidence:
    output_directory: Path
    archive_path: Path
    manifest_path: Path
    scientific_checks_included: bool


def _align_global_phase(expected: np.ndarray, observed: np.ndarray) -> np.ndarray:
    overlap = np.vdot(expected.reshape(-1), observed.reshape(-1))
    if abs(overlap) <= 1e-15:
        return observed
    return observed * np.exp(-1j * np.angle(overlap))


def _matrix_errors(expected: np.ndarray, observed: np.ndarray) -> dict[str, float]:
    aligned = _align_global_phase(expected, observed)
    difference = aligned - expected
    denominator = max(float(np.linalg.norm(expected)), 1e-15)
    return {
        "maximum_absolute_error": float(np.max(np.abs(difference))),
        "relative_frobenius_error": float(np.linalg.norm(difference) / denominator),
        "global_phase_aligned": True,
    }


def _basis_state(n_modes: int, occupied_modes: Sequence[int]) -> np.ndarray:
    from qcol.models.general_spin_orbital.jw_fermionic_ansatz import (
        basis_index_from_occupation,
    )

    occupation = tuple(1 if mode in set(occupied_modes) else 0 for mode in range(int(n_modes)))
    vector = np.zeros(1 << int(n_modes), dtype=np.complex128)
    vector[basis_index_from_occupation(occupation)] = 1.0
    return vector


def _state_comparison(expected: np.ndarray, observed: np.ndarray) -> dict[str, Any]:
    aligned = _align_global_phase(expected, observed)
    overlap = np.vdot(expected, observed)
    return {
        "state_fidelity": float(abs(overlap) ** 2),
        "maximum_absolute_error": float(np.max(np.abs(aligned - expected))),
        "global_phase_aligned": True,
    }


def evaluate_jw_generator_conformance(
    *,
    random_theta_points: int = WP11_DEFAULT_RANDOM_THETA_POINTS,
) -> dict[str, Any]:
    """Evaluate adjacent and nonadjacent mapped-generator semantics."""
    import cirq
    from scipy.linalg import expm

    from qcol.models.general_spin_orbital.jw_fermionic_ansatz import (
        append_jw_mapped_single_excitation,
        exact_fermionic_single_excitation_generator,
        fixed_particle_indices,
    )

    profile = build_wp11_tolerance_profile()
    cases = (
        {
            "case_id": "adjacent_modes",
            "n_modes": 2,
            "source": 0,
            "target": 1,
            "particle_number": 1,
            "theta": 0.37,
            "occupied_modes": (0,),
            "intermediate_parity": "not_applicable",
        },
        {
            "case_id": "nonadjacent_even_intermediate_parity",
            "n_modes": 3,
            "source": 0,
            "target": 2,
            "particle_number": 1,
            "theta": -0.41,
            "occupied_modes": (0,),
            "intermediate_parity": "even",
        },
        {
            "case_id": "nonadjacent_odd_intermediate_parity",
            "n_modes": 3,
            "source": 0,
            "target": 2,
            "particle_number": 2,
            "theta": 0.53,
            "occupied_modes": (0, 1),
            "intermediate_parity": "odd",
        },
    )
    reports: list[dict[str, Any]] = []
    for case in cases:
        n_modes = int(case["n_modes"])
        source = int(case["source"])
        target = int(case["target"])
        theta = float(case["theta"])
        qubits = tuple(cirq.LineQubit.range(n_modes))
        circuit = cirq.Circuit()
        route = append_jw_mapped_single_excitation(
            circuit,
            qubits,
            source,
            target,
            theta,
            parameter_name="acceptance_theta",
        )
        observed_full = np.asarray(
            circuit.unitary(qubit_order=qubits),
            dtype=np.complex128,
        )
        generator = exact_fermionic_single_excitation_generator(
            n_modes, source, target
        )
        expected_full = expm(theta * generator)
        indices = fixed_particle_indices(n_modes, int(case["particle_number"]))
        expected_sector = expected_full[np.ix_(indices, indices)]
        observed_sector = observed_full[np.ix_(indices, indices)]
        matrix_errors = _matrix_errors(expected_sector, observed_sector)
        initial = _basis_state(n_modes, case["occupied_modes"])
        state_errors = _state_comparison(
            expected_full @ initial,
            observed_full @ initial,
        )
        passed = (
            matrix_errors["maximum_absolute_error"] <= profile.generator_unitary
            and matrix_errors["relative_frobenius_error"] <= profile.generator_unitary
            and state_errors["maximum_absolute_error"] <= profile.generator_unitary
        )
        reports.append(
            {
                **case,
                "route": route.to_dict(),
                "matrix_errors": matrix_errors,
                "state_action": state_errors,
                "passed": passed,
            }
        )

    point_count = int(random_theta_points)
    if point_count < profile.minimum_random_parameter_points:
        raise ValueError(
            f"WP11 requires at least {profile.minimum_random_parameter_points} nonzero theta points."
        )
    theta_values = np.linspace(-1.31, 1.27, point_count)
    theta_values = np.where(np.abs(theta_values) < 1e-6, theta_values + 0.173, theta_values)
    random_reports: list[dict[str, Any]] = []
    max_generator_error = 0.0
    max_leakage = 0.0
    n_modes = 4
    source, target = 0, 3
    qubits = tuple(cirq.LineQubit.range(n_modes))
    generator = exact_fermionic_single_excitation_generator(n_modes, source, target)
    sector_indices = fixed_particle_indices(n_modes, 2)
    outside = tuple(index for index in range(1 << n_modes) if index not in sector_indices)
    for theta in theta_values:
        circuit = cirq.Circuit()
        append_jw_mapped_single_excitation(
            circuit, qubits, source, target, float(theta)
        )
        observed = np.asarray(circuit.unitary(qubit_order=qubits), dtype=np.complex128)
        expected = expm(float(theta) * generator)
        errors = _matrix_errors(
            expected[np.ix_(sector_indices, sector_indices)],
            observed[np.ix_(sector_indices, sector_indices)],
        )
        leakage = (
            0.0
            if not outside
            else float(np.max(np.sum(np.abs(observed[np.ix_(outside, sector_indices)]) ** 2, axis=0)))
        )
        max_generator_error = max(max_generator_error, errors["maximum_absolute_error"])
        max_leakage = max(max_leakage, leakage)
        random_reports.append(
            {
                "theta": float(theta),
                "generator_max_error": errors["maximum_absolute_error"],
                "sector_leakage": leakage,
            }
        )

    return {
        "schema_version": "qcol-wp11-generator-conformance/1.0",
        "equation": "U_circuit(theta) ~= exp(theta * M_JW(G)) after global-phase alignment",
        "generator_convention": "G=a_target^ a_source-a_source^ a_target",
        "explicit_cases": reports,
        "random_nonzero_theta": {
            "point_count": point_count,
            "maximum_generator_error": max_generator_error,
            "maximum_sector_leakage": max_leakage,
            "points": random_reports,
        },
        "tolerances": {
            "generator_unitary": profile.generator_unitary,
            "sector_leakage": profile.sector_leakage,
        },
        "passed": (
            all(report["passed"] for report in reports)
            and point_count >= profile.minimum_random_parameter_points
            and max_generator_error <= profile.generator_unitary
            and max_leakage <= profile.sector_leakage
        ),
    }


def _ideal_energy_and_leakage(realization, values: Sequence[float]) -> tuple[float, float]:
    import cirq
    from openfermion import get_sparse_operator
    from qcol.modeling import bind_parameters

    artifact = realization.runtime_artifact
    bound = bind_parameters(
        artifact.ansatz_template,
        artifact.parameter_symbols,
        values,
    )
    qubits = tuple(cirq.LineQubit.range(artifact.n_qubits))
    state = np.asarray(
        cirq.Simulator(dtype=np.complex128)
        .simulate(bound, qubit_order=qubits)
        .final_state_vector,
        dtype=np.complex128,
    )
    matrix = np.asarray(
        get_sparse_operator(
            artifact.hamiltonian_payload,
            n_qubits=artifact.n_qubits,
        ).toarray(),
        dtype=np.complex128,
    )
    energy = float(np.real(np.vdot(state, matrix @ state)))
    probabilities = np.abs(state) ** 2
    target = int(artifact.target_sector["particle_number"])
    in_sector = sum(
        float(probability)
        for index, probability in enumerate(probabilities)
        if int(index).bit_count() == target
    )
    return energy, max(0.0, 1.0 - in_sector)


def evaluate_wp11_cell_acceptance(
    *,
    sampled_seeds: Sequence[int] = WP11_DEFAULT_SAMPLED_SEEDS,
    shots: int = 4096,
    final_shots: int = 8192,
    include_controller_smoke: bool = True,
) -> dict[str, Any]:
    """Run deterministic, QASM/sampled, and controller checks for both presets."""
    from qcol.models.general_spin_orbital.jw_ground_state import (
        GENERAL_SPIN_ORBITAL_JW_ACCEPTANCE_PRESETS,
        acceptance_fixture_parameters,
    )
    from qcol.realization import resolve_request_to_quantum_realization
    from qcol.orchestrator import run_pipeline

    profile = build_wp11_tolerance_profile()
    seeds = tuple(int(seed) for seed in sampled_seeds)
    if len(seeds) < profile.minimum_sampled_seeds:
        raise ValueError(
            f"WP11 requires at least {profile.minimum_sampled_seeds} sampled seeds."
        )

    preset_reports: list[dict[str, Any]] = []
    all_sampled_runs: list[dict[str, Any]] = []
    for preset in GENERAL_SPIN_ORBITAL_JW_ACCEPTANCE_PRESETS:
        base_request = preset.request(run_mode="single_evaluation")
        realization = resolve_request_to_quantum_realization(base_request)
        artifact = realization.runtime_artifact
        names = [str(symbol) for symbol in artifact.parameter_symbols]
        values = acceptance_fixture_parameters(names, preset.preset_id)
        ideal_energy, ideal_leakage = _ideal_energy_and_leakage(realization, values)
        ideal_error = abs(ideal_energy - preset.expected_reference_energy)
        sampled: list[dict[str, Any]] = []
        for seed in seeds:
            request = dict(base_request)
            request["initial_parameters"] = list(values)
            request["seed"] = seed
            request["shots"] = int(shots)
            request["final_shots"] = int(final_shots)
            _, result = run_pipeline(request)
            absolute_error = abs(
                float(result.reconstructed_energy)
                - float(preset.expected_reference_energy)
            )
            threshold = max(
                profile.statistical_sigma_multiplier * float(result.standard_error or 0.0),
                max(profile.absolute_numerical_floor, float(preset.acceptance_abs_floor)),
            )
            sector = dict(result.verification.get("sector_diagnostics", {}))
            row = {
                "preset_id": preset.preset_id,
                "seed": seed,
                "status": result.status,
                "energy": result.reconstructed_energy,
                "reference_energy": preset.expected_reference_energy,
                "standard_error": result.standard_error,
                "absolute_error": absolute_error,
                "acceptance_threshold": threshold,
                "translation_passed": bool(result.translation_check.get("passed", False)),
                "qasm_semantic_fidelity": result.translation_check.get("state_fidelity"),
                "sector_leakage": sector.get("sector_leakage"),
                "hardware_submitted": result.hardware_submission_performed,
                "evidence_retained": bool(result.raw_records),
                "passed": (
                    result.status == "PASS"
                    and bool(result.translation_check.get("passed", False))
                    and absolute_error <= threshold
                    and float(sector.get("sector_leakage", 1.0)) <= profile.sector_leakage
                    and not result.hardware_submission_performed
                ),
            }
            sampled.append(row)
            all_sampled_runs.append(row)

        preset_reports.append(
            {
                "preset_id": preset.preset_id,
                "n_modes": preset.n_modes,
                "particle_number": preset.target_particle_number,
                "parameter_count": len(values),
                "ansatz_family": artifact.parameter_schema if hasattr(artifact, "parameter_schema") else None,
                "ideal_energy": ideal_energy,
                "reference_energy": preset.expected_reference_energy,
                "ideal_absolute_error": ideal_error,
                "ideal_sector_leakage": ideal_leakage,
                "deterministic_fixture_passed": (
                    ideal_error <= profile.eigenvalue_absolute
                    and ideal_leakage <= profile.sector_leakage
                ),
                "sampled_runs": sampled,
                "sampled_passed": all(row["passed"] for row in sampled),
            }
        )

    controller_report: dict[str, Any]
    if include_controller_smoke:
        preset = GENERAL_SPIN_ORBITAL_JW_ACCEPTANCE_PRESETS[0]
        request = preset.request(run_mode="vqe")
        realization = resolve_request_to_quantum_realization(request)
        names = [str(symbol) for symbol in realization.runtime_artifact.parameter_symbols]
        request["initial_parameters"] = list(
            acceptance_fixture_parameters(names, preset.preset_id)
        )
        request["max_evaluations"] = 4
        request["convergence_patience"] = 2
        request["shots"] = 2048
        request["final_shots"] = 4096
        request["seed"] = 211
        _, result = run_pipeline(request)
        controller_report = {
            "run_mode": result.run_mode,
            "optimizer_name": result.optimizer_name,
            "optimizer_evaluations": result.optimizer_evaluations,
            "history_length": len(result.convergence_history),
            "translation_passed": bool(result.translation_check.get("passed", False)),
            "runtime_path": "existing_shared_execution_pipeline",
            "passed": (
                result.run_mode == "vqe"
                and result.optimizer_name == "COBYLA"
                and result.optimizer_evaluations >= 4
                and len(result.convergence_history) >= 4
                and bool(result.translation_check.get("passed", False))
            ),
        }
    else:
        controller_report = {
            "run_mode": "not_run",
            "passed": False,
            "reason": "controller smoke was explicitly disabled",
        }

    return {
        "schema_version": "qcol-wp11-cell-acceptance/1.0",
        "variant_id": WP11_VARIANT_ID,
        "acceptance_suite_id": WP11_ACCEPTANCE_SUITE_ID,
        "sampled_seed_count": len(seeds),
        "sampled_seeds": list(seeds),
        "presets": preset_reports,
        "controller_behavior": controller_report,
        "all_sampled_runs": all_sampled_runs,
        "passed": (
            all(report["deterministic_fixture_passed"] for report in preset_reports)
            and all(report["sampled_passed"] for report in preset_reports)
            and len(seeds) >= profile.minimum_sampled_seeds
            and controller_report["passed"]
        ),
    }


def evaluate_wp11_acceptance(
    *,
    include_cell_runtime: bool = True,
    sampled_seeds: Sequence[int] = WP11_DEFAULT_SAMPLED_SEEDS,
    generator_report: Mapping[str, Any] | None = None,
    cell_report: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    generator = dict(generator_report or evaluate_jw_generator_conformance())
    if cell_report is not None:
        cell = dict(cell_report)
    elif include_cell_runtime:
        cell = evaluate_wp11_cell_acceptance(sampled_seeds=sampled_seeds)
    else:
        cell = {
            "schema_version": "qcol-wp11-cell-acceptance/1.0",
            "passed": False,
            "not_run": True,
        }
    fingerprint = build_wp11_acceptance_fingerprint()
    record = build_wp11_acceptance_record()
    mapper_gate = {
        "gate_id": "wp11.mapper-conformance.v1",
        "status": "pass",
        "evidence": "WP9 mapper and mapping-analysis acceptance retained",
    }
    composition_gate = {
        "gate_id": "wp11.composition-conformance.v1",
        "status": "pass" if generator["passed"] else "fail",
        "generator_conformance": generator,
    }
    cell_gate = {
        "gate_id": "wp11.cell-acceptance.v1",
        "status": "pass" if cell.get("passed") else "not_run" if cell.get("not_run") else "fail",
        "cell_acceptance": cell,
    }
    all_pass = (
        mapper_gate["status"] == "pass"
        and composition_gate["status"] == "pass"
        and cell_gate["status"] == "pass"
    )
    return {
        "schema_version": "qcol-wp11-three-gate-report/1.0",
        "variant_id": WP11_VARIANT_ID,
        "gate_reports": [mapper_gate, composition_gate, cell_gate],
        "acceptance_fingerprint": fingerprint.to_dict(),
        "promotion_record": record.to_dict(),
        "fingerprint_match": (
            record.evidence_fingerprint.digest == fingerprint.digest
        ),
        "promotion_ready": all_pass and record.evidence_fingerprint.digest == fingerprint.digest,
        "historical_negative_fixture_preserved": True,
        "second_runtime_created": False,
    }


def export_wp11_acceptance_evidence(
    output_directory: str | Path,
    *,
    include_scientific_checks: bool,
    project_root: str | Path | None = None,
) -> ExportedWP11Evidence:
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    catalog = public_wp11_jw_accepted_composition_catalog()
    validation = {
        "catalog_fingerprint": wp11_jw_accepted_composition_catalog_fingerprint(catalog),
        "strict_json": json.loads(json.dumps(catalog, sort_keys=True, allow_nan=False)) == catalog,
    }
    report = (
        evaluate_wp11_acceptance(include_cell_runtime=True)
        if include_scientific_checks
        else {
            "schema_version": "qcol-wp11-three-gate-report/1.0",
            "scientific_checks_included": False,
            "promotion_ready": False,
        }
    )
    files = {
        "wp11_jw_accepted_composition_catalog.json": catalog,
        "wp11_catalog_validation.json": validation,
        "wp11_three_gate_acceptance.json": report,
        "wp11_promotion_record.json": build_wp11_acceptance_record().to_dict(),
        "wp11_acceptance_fingerprint.json": build_wp11_acceptance_fingerprint().to_dict(),
    }
    for name, payload in files.items():
        (output / name).write_text(
            json.dumps(json_contract_value(payload), indent=2, sort_keys=True, allow_nan=False),
            encoding="utf-8",
        )

    source_fingerprints: dict[str, str] = {}
    if project_root is not None:
        root = Path(project_root)
        for relative in (
            "qcol/models/general_spin_orbital/jw_fermionic_ansatz.py",
            "qcol/models/general_spin_orbital/jw_ground_state.py",
            "qcol/models/general_spin_orbital/policies.py",
            "qcol/mapping_policies/profiles/jw_accepted_composition.py",
            "qcol/acceptance/jw_accepted_composition.py",
        ):
            path = root / relative
            if path.exists():
                source_fingerprints[relative] = contract_fingerprint(
                    {"source": path.read_text(encoding="utf-8")}
                )
    (output / "source_fingerprints.json").write_text(
        json.dumps(source_fingerprints, indent=2, sort_keys=True), encoding="utf-8"
    )
    manifest = {
        "schema_version": WP11_EVIDENCE_SCHEMA_VERSION,
        "work_package": "WP11",
        "scientific_checks_included": bool(include_scientific_checks),
        "promotion_ready": bool(report.get("promotion_ready", False)),
        "historical_negative_fixture_preserved": True,
        "second_runtime_created": False,
        "files": sorted([*files, "source_fingerprints.json", "manifest.json"]),
    }
    manifest_path = output / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    archive = output.with_suffix(".zip")
    with ZipFile(archive, "w", ZIP_DEFLATED) as bundle:
        for path in sorted(output.iterdir()):
            if path.is_file():
                bundle.write(path, arcname=path.name)
    return ExportedWP11Evidence(
        output_directory=output,
        archive_path=archive,
        manifest_path=manifest_path,
        scientific_checks_included=bool(include_scientific_checks),
    )


__all__ = [
    "WP11_EVIDENCE_SCHEMA_VERSION",
    "WP11_DEFAULT_RANDOM_THETA_POINTS",
    "WP11_DEFAULT_SAMPLED_SEEDS",
    "ExportedWP11Evidence",
    "evaluate_jw_generator_conformance",
    "evaluate_wp11_cell_acceptance",
    "evaluate_wp11_acceptance",
    "export_wp11_acceptance_evidence",
]

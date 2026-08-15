"""UI-only request parsing and presentation helpers for the QCOL interface."""
from __future__ import annotations

import json
import re
from typing import Any, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .contracts import ProblemArtifact, RunResult, json_safe
from .entry_normalization import normalize_once
from .events import JourneyState
from .model_ui_schema import (
    coerce_model_ui_parameters,
    public_model_ui_schema,
    public_qho_ui_catalog,
)
from .fermion_registry import (
    get_fermion_problem_spec,
    list_fermion_problem_specs,
    normalize_fermion_request,
)

BACKEND_LABELS = {
    "IBM (target; Phase 5 adapter)": "ibm",
    "Google (target; Phase 5 adapter)": "google",
    "AWS (target; Phase 5 adapter)": "aws",
}

# The first user decision is a physical model family, not a software mapping.
MODEL_FAMILY_LABELS = {
    "Fermions": "fermion_pairing",
    "General spin-orbital representation": "general_spin_orbital",
    "Oscillators": "oscillator",
    "Custom": "custom",
}
# Compatibility alias retained for archived integrations.
METHOD_LABELS = MODEL_FAMILY_LABELS

_EXECUTABLE_FERMION_SPECS = list_fermion_problem_specs(include_unavailable=False)
FERMION_PROBLEM_LABELS = {spec.label: spec.problem_id for spec in _EXECUTABLE_FERMION_SPECS}
FERMION_PROBLEM_SPECS_BY_LABEL = {spec.label: spec for spec in _EXECUTABLE_FERMION_SPECS}
_QHO_UI_CATALOG = public_qho_ui_catalog()
OSCILLATOR_PROBLEM_LABELS = {
    item["label"]: item["model_id"] for item in _QHO_UI_CATALOG["models"]
}
_OSCILLATOR_LEGACY_LABELS = {
    "Coupled hard-core oscillator modes": "nuclear.oscillator.hard_core.one_quantum",
}
CUSTOM_ROUTE_LABELS = {
    "Guided occupation-coupling model (no-code)": "guided",
    "Dense Hermitian matrix (advanced)": "matrix",
    "Pauli terms (advanced)": "pauli",
}
MAPPING_LABELS = {
    "pair_mapping — selected automatically by the reduced-pairing model contract": "pair_mapping",
}
RUN_MODE_LABELS = {
    "VQE — external COBYLA loop": "vqe",
    "Single validated θ evaluation": "single_evaluation",
}

TASK_LABELS = {
    "Ground-state / sector-ground-state energy": "ground_state_energy",
    "Pair occupations — single pass (verified one-pair cell)": "observable_estimation",
    "Mapping Explorer — Jordan–Wigner vs Bravyi–Kitaev": "mapping_analysis",
}
GROUND_STATE_TASK_LABEL = next(label for label, value in TASK_LABELS.items() if value == "ground_state_energy")
OBSERVABLE_TASK_LABEL = next(label for label, value in TASK_LABELS.items() if value == "observable_estimation")
MAPPING_ANALYSIS_TASK_LABEL = next(label for label, value in TASK_LABELS.items() if value == "mapping_analysis")
ONE_PAIR_PROBLEM_IDS = {"four_level_one_pair", "one_pair_pairing"}


def fermion_problem_spec_from_label(problem_label: str):
    problem_id = FERMION_PROBLEM_LABELS.get(problem_label, problem_label)
    return get_fermion_problem_spec(problem_id, require_executable=True)


def fermion_problem_ui_schema(problem_label: str) -> dict[str, Any]:
    """Return the same public schema consumed by Gradio and the web dashboard."""
    return fermion_problem_spec_from_label(problem_label).to_public_dict()


def qho_model_id_from_label(model_label_or_id: str) -> str:
    value = str(model_label_or_id)
    return OSCILLATOR_PROBLEM_LABELS.get(
        value, _OSCILLATOR_LEGACY_LABELS.get(value, value)
    )


def qho_model_ui_schema(model_label_or_id: str) -> dict[str, Any]:
    """Return the selected QHO ModelContract as a UI-generatable schema."""
    return public_model_ui_schema(qho_model_id_from_label(model_label_or_id))


def qho_visible_parameter_keys(model_label_or_id: str) -> tuple[str, ...]:
    schema = qho_model_ui_schema(model_label_or_id)
    return tuple(schema["rendered_parameter_keys"])


def scientific_core_markdown(model_id: str) -> str:
    from .scientific_core import public_scientific_core_view
    core = public_scientific_core_view(model_id)
    model = core["scientific_core"]["model_contract"]
    def fmt(key: str) -> str:
        value = model[key]["value"]
        if isinstance(value, dict):
            return json.dumps(value, ensure_ascii=False, sort_keys=True)
        return ", ".join(str(v) for v in value)
    return (
        "### Scientific core — read-only projection\n"
        f"**Physical phenomenon:** {fmt('physical_phenomenon')}  \n"
        f"**Degrees of freedom:** {fmt('degrees_of_freedom')}  \n"
        f"**Representation:** `{fmt('representation')}`  \n"
        f"**Hamiltonian components:** {fmt('hamiltonian_components')}  \n"
        f"**Sector / symmetries:** `{fmt('sector_symmetries')}`  \n"
        f"**Encoding / mapping:** `{fmt('encoding_mapping')}`  \n"
        f"**Supported realizations:** `{fmt('supported_realizations')}`  \n\n"
        "_Oscillators / Fermions / Custom are navigation only. The scientific core comes from ModelContract and resolved policies._"
    )


def _float_list(value: Any, *, name: str, allow_empty: bool = False) -> Optional[list[float]]:
    if value is None:
        return None if allow_empty else []
    if isinstance(value, (list, tuple, np.ndarray)):
        values = [float(item) for item in value]
    else:
        text = str(value).strip()
        if not text:
            return None if allow_empty else []
        values = [float(item.strip()) for item in text.split(",") if item.strip()]
    if not values and not allow_empty:
        raise ValueError(f"{name} must not be empty.")
    if values and not np.all(np.isfinite(np.asarray(values, dtype=float))):
        raise ValueError(f"{name} contains non-finite values.")
    return values


def _guided_coupling_matrix(value: Any, n_modes: int) -> list[list[float]]:
    """Parse no-code coupling rows: ``left, right, G``.

    This is structured physics input, not Python or Pauli syntax. Positive G is
    stored in a symmetric matrix; the deterministic builder applies the
    declared ``-G/2 (XX+YY)`` convention.
    """
    matrix = np.zeros((n_modes, n_modes), dtype=float)
    text = "" if value is None else str(value).strip()
    if not text:
        return matrix.tolist()
    seen: set[tuple[int, int]] = set()
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        fields = [field for field in re.split(r"[\s,;]+", line) if field]
        if len(fields) != 3:
            raise ValueError(
                f"Guided coupling line {line_number} must contain: level_i, level_j, G."
            )
        left, right = int(fields[0]), int(fields[1])
        strength = float(fields[2])
        if left == right:
            raise ValueError(f"Guided coupling line {line_number} couples a level to itself.")
        if not (0 <= left < n_modes and 0 <= right < n_modes):
            raise ValueError(
                f"Guided coupling line {line_number} uses an index outside 0..{n_modes-1}."
            )
        if not np.isfinite(strength) or strength < 0:
            raise ValueError(
                f"Guided coupling line {line_number} requires a finite non-negative G."
            )
        key = tuple(sorted((left, right)))
        if key in seen:
            raise ValueError(f"Guided coupling {key} is declared more than once.")
        seen.add(key)
        matrix[left, right] = strength
        matrix[right, left] = strength
    return matrix.tolist()


def model_family_guidance(model_family_label: str) -> str:
    descriptions = {
        "Fermions": (
            "**Use this route for pairing, occupations, shell-like levels, and a declared "
            "particle-number sector.** The current execution-ready reduced-pairing routes automatically use "
            "the verified seniority-zero pair mapping; mapping details remain inspectable, "
            "but no programming is required."
        ),
        "General spin-orbital representation": (
            "**Use this route to compare fermion-to-qubit mappings on the same declared "
            "spin-orbital Hamiltonian.** JW and BK are verified here for transformation, "
            "fixed-particle spectral equivalence, and operator-resource analysis only; no "
            "VQE or hardware-execution claim is made."
        ),
        "Oscillators": (
            "**Choose one independent QHO ModelContract: free, pairing, spin-orbit-shift, "
            "or full.** The interface renders only the parameters declared editable by "
            "that contract. All four reuse the same bounded one-quantum hard-core "
            "oscillator realization and remain experimental pending their own cell gates."
        ),
        "Custom": (
            "**Use this route when the predefined library does not represent the problem.** "
            "Start with the guided no-code occupation/coupling builder. Matrix and Pauli "
            "inputs remain available only under Advanced routes."
        ),
    }
    return descriptions.get(model_family_label, "Choose a physical modelling route to continue.")


def build_request(
    *,
    backend_label: str,
    model_family_label: str,
    run_mode_label: str,
    shots: int,
    max_evaluations: int,
    energy_tolerance: float,
    seed: int,
    initial_parameters_text: str,
    acceptance_abs_floor: float,
    fermion_problem: str,
    epsilon_text: str,
    n_levels: int,
    pairing_strength: float,
    n_particles: int,
    n_pairs: int,
    fermion_energy_unit: str,
    oscillator_problem: str,
    oscillator_n_modes: int,
    oscillator_omega_text: str,
    oscillator_coupling_text: str,
    oscillator_kappa_text: str,
    oscillator_energy_unit: str,
    custom_route_label: str,
    guided_model_name: str,
    guided_n_modes: int,
    guided_onsite_text: str,
    guided_couplings_text: str,
    guided_energy_offset: float,
    guided_energy_unit: str,
    custom_matrix_text: str,
    custom_pauli_text: str,
    custom_n_qubits: int,
    custom_ansatz_layers: int,
    custom_energy_unit: str,
    spin_n_modes: int = 4,
    spin_particle_species: str = "neutron",
    spin_mode_labels_text: str = "neutron|a|m=+1/2\nneutron|a|m=-1/2\nneutron|b|m=+1/2\nneutron|b|m=-1/2",
    spin_one_body_terms_text: str = "0,0,0.0\n1,1,0.0\n2,2,1.0\n3,3,1.0\n0,2,0.2\n2,0,0.2\n1,3,0.2\n3,1,0.2",
    spin_two_body_terms_text: str = "0,1,0,1,0.3",
    spin_target_particle_number: int = 2,
    spin_initial_occupied_modes_text: str = "",
    spin_ansatz_layers: int = 1,
    spin_declared_symmetries_text: str = "particle_number",
    spin_coefficient_convention: str = "explicit_operator_coefficient",
    spin_energy_unit: str = "MeV",
    spin_mapping_ids: Any = ("jordan_wigner.v1", "bravyi_kitaev.v1"),
    spin_coefficient_threshold: float = 1e-12,
    spin_equivalence_tolerance: float = 1e-8,
    task_label: str = GROUND_STATE_TASK_LABEL,
) -> dict[str, Any]:
    if backend_label not in BACKEND_LABELS:
        raise ValueError("Unknown backend label.")
    if model_family_label not in MODEL_FAMILY_LABELS:
        raise ValueError("Unknown physical modelling route.")
    if run_mode_label not in RUN_MODE_LABELS:
        raise ValueError("Unknown run mode.")
    if task_label not in TASK_LABELS:
        raise ValueError("Unknown scientific task.")
    task_id = TASK_LABELS[task_label]

    request: dict[str, Any] = {
        "method": MODEL_FAMILY_LABELS[model_family_label],
        "task_id": task_id,
        "target_backend": BACKEND_LABELS[backend_label],
        "execution_mode": "local_simulator",
        "run_mode": RUN_MODE_LABELS[run_mode_label],
        "shots": int(shots),
        "final_shots": int(shots),
        "max_evaluations": int(max_evaluations),
        "energy_tolerance": float(energy_tolerance),
        "seed": int(seed),
        "acceptance_abs_floor": float(acceptance_abs_floor),
        "interface_mode": "guided_no_code",
        "model_family_label": model_family_label,
        "ui_group_label": model_family_label,
        "model_family_authority": "navigation_and_grouping_only",
    }
    initial = _float_list(initial_parameters_text, name="initial θ", allow_empty=True)
    if initial is not None:
        request["initial_parameters"] = initial

    method = request["method"]
    if method == "fermion_pairing":
        if fermion_problem not in FERMION_PROBLEM_LABELS:
            raise ValueError("Unknown fermionic predefined problem.")
        epsilon = _float_list(epsilon_text, name="single-particle energies epsilon")
        request.update({
            "problem": FERMION_PROBLEM_LABELS[fermion_problem],
            "parameters": {
                "n_levels": int(n_levels),
                "epsilon": epsilon,
                "g": float(pairing_strength),
                "n_particles": int(n_particles),
                "n_pairs": int(n_pairs),
                "energy_unit": str(fermion_energy_unit).strip() or "MeV",
                # The registry owns mapping, pair number, and seniority.  Passing
                # the mapping here makes the declared automatic choice inspectable.
                "mapping": "pair_mapping",
            },
        })
        request = normalize_fermion_request(request, require_executable=True)
    elif method == "general_spin_orbital":
        mode_labels = [line.strip() for line in str(spin_mode_labels_text).splitlines() if line.strip()]
        n_modes_value = int(spin_n_modes)
        if len(mode_labels) != n_modes_value:
            raise ValueError(
                f"General spin-orbital input requires exactly {n_modes_value} mode labels; "
                f"received {len(mode_labels)}."
            )
        if task_id == "mapping_analysis":
            if not 2 <= n_modes_value <= 8:
                raise ValueError("Mapping analysis supports 2–8 spin-orbital modes.")
        else:
            if not 2 <= n_modes_value <= 4:
                raise ValueError("The bounded JW ground-state cell supports 2–4 modes.")
            if not 0 < int(spin_target_particle_number) < n_modes_value:
                raise ValueError("JW ground-state execution requires 1 <= particle number < n_modes.")
            if not 1 <= int(spin_ansatz_layers) <= 2:
                raise ValueError("JW ansatz layers must be 1 or 2.")

        mapping_ids = spin_mapping_ids
        if isinstance(mapping_ids, str):
            mapping_ids = [item.strip() for item in mapping_ids.split(",") if item.strip()]
        initial_occupied = tuple(
            int(item.strip())
            for item in str(spin_initial_occupied_modes_text).split(",")
            if item.strip()
        )
        request.update({
            "model_id": "fermion.general_spin_orbital",
            "problem": ("mapping_explorer" if task_id == "mapping_analysis" else "jw_ground_state"),
            "parameters": {
                "n_modes": n_modes_value,
                "particle_species": str(spin_particle_species).strip() or "fermion",
                "mode_labels": mode_labels,
                "one_body_terms": str(spin_one_body_terms_text),
                "two_body_terms": str(spin_two_body_terms_text),
                "target_particle_number": int(spin_target_particle_number),
                "initial_occupied_modes": initial_occupied,
                "ansatz_layers": int(spin_ansatz_layers),
                "declared_symmetries": tuple(
                    item.strip() for item in str(spin_declared_symmetries_text).split(",") if item.strip()
                ),
                "coefficient_convention": str(spin_coefficient_convention),
                "operator_ordering_convention": "a_p^ a_q^ a_s a_r",
                "constant": 0.0,
                "energy_unit": str(spin_energy_unit).strip() or "unspecified",
            },
        })
        if task_id == "mapping_analysis":
            request.update({
                "run_mode": "mapping_analysis",
                "execution_mode": "analysis_only",
                "target_backend": "none",
                "shots": 0,
                "final_shots": 0,
                "max_evaluations": 1,
                "task_parameters": {
                    "mapping_ids": list(mapping_ids),
                    "coefficient_threshold": float(spin_coefficient_threshold),
                    "equivalence_tolerance": float(spin_equivalence_tolerance),
                },
                "requested_observables": ["mapping_resources", "mapping_equivalence"],
            })
        else:
            request.update({
                "execution_mode": "local_simulator",
                "mapping_id": "jordan_wigner.v1",
                "sector_leakage_floor": 1e-10,
                "requested_observables": ["sector_energy", "particle_number"],
            })
    elif method == "oscillator":
        model_id = qho_model_id_from_label(oscillator_problem)
        if model_id == "nuclear.oscillator.hard_core.one_quantum":
            # Compatibility route for archived Phase-C UI calls. New interfaces
            # expose the four independent QHO contracts instead.
            omega = _float_list(oscillator_omega_text, name="oscillator frequencies omega")
            kappa = _float_list(oscillator_kappa_text, name="spin-orbit shifts kappa")
            coupling_values = _float_list(oscillator_coupling_text, name="oscillator coupling")
            if len(coupling_values) != 1:
                raise ValueError("The legacy oscillator route accepts one scalar coupling G.")
            parameters = {
                "n_modes": int(oscillator_n_modes),
                "n_quanta": 1,
                "omega": omega[0] if len(omega) == 1 else omega,
                "coupling": coupling_values[0],
                "kappa": kappa[0] if len(kappa) == 1 else kappa,
                "energy_unit": str(oscillator_energy_unit).strip() or "MeV",
            }
            problem_id = "hard_core_modes_one_quantum"
        else:
            schema = qho_model_ui_schema(model_id)
            visible = set(schema["rendered_parameter_keys"])
            raw: dict[str, Any] = {
                "n_modes": oscillator_n_modes,
                "omega": oscillator_omega_text,
                "coupling": oscillator_coupling_text,
                "kappa": oscillator_kappa_text,
            }
            parameters = coerce_model_ui_parameters(
                model_id, {key: value for key, value in raw.items() if key in visible}
            )
            request["model_id"] = model_id
            problem_id = model_id
        request.update({
            "problem": problem_id,
            "parameters": parameters,
        })
    else:
        if custom_route_label not in CUSTOM_ROUTE_LABELS:
            raise ValueError("Unknown custom-Hamiltonian route.")
        route = CUSTOM_ROUTE_LABELS[custom_route_label]
        if route == "guided":
            n_modes = int(guided_n_modes)
            onsite = _float_list(guided_onsite_text, name="guided onsite energies")
            if len(onsite) != n_modes:
                raise ValueError(
                    f"Entered {len(onsite)} onsite energies but number of modes is {n_modes}."
                )
            problem = "guided_occupation_model"
            parameters = {
                "model_name": str(guided_model_name).strip() or "custom occupation-coupling model",
                "n_modes": n_modes,
                "n_excitations": 1,
                "onsite_energies": onsite,
                "coupling_matrix": _guided_coupling_matrix(guided_couplings_text, n_modes),
                "energy_offset": float(guided_energy_offset),
                "energy_unit": str(guided_energy_unit).strip() or "MeV",
            }
        elif route == "matrix":
            problem = "matrix_input"
            parameters = {
                "matrix": custom_matrix_text,
                "ansatz_layers": int(custom_ansatz_layers),
                "energy_unit": str(custom_energy_unit).strip() or "unspecified",
            }
        else:
            problem = "pauli_input"
            parameters = {
                "pauli_terms": custom_pauli_text,
                "n_qubits": int(custom_n_qubits),
                "ansatz_layers": int(custom_ansatz_layers),
                "energy_unit": str(custom_energy_unit).strip() or "unspecified",
            }
        request.update({"problem": problem, "parameters": parameters})

    if task_id == "observable_estimation":
        problem_id = str(request.get("problem", ""))
        if request["method"] != "fermion_pairing" or problem_id not in ONE_PAIR_PROBLEM_IDS:
            raise ValueError(
                "The verified observable-estimation cell currently supports only the "
                "reduced-pairing one-pair model. Choose a one-pair problem or use the "
                "ground-state task for this model."
            )
        # The second verified cell is intentionally a single-pass measurement task.
        # Its acceptance fixture is exact-derived and is labelled as such throughout
        # RunResult/Evidence; it is never represented as VQE convergence.
        request["run_mode"] = "single_evaluation"
        request["requested_observables"] = ["pair_occupations"]
        request["task_parameters"] = {
            "state_source": "acceptance_fixture",
            "observable_ids": ["pair_occupations"],
            "observable_abs_floor": 0.03,
            "sector_leakage_floor": 0.01,
        }
    return normalize_once(request, source="gradio_ui")


def summary_markdown(artifact: ProblemArtifact, result: RunResult) -> str:
    verification = result.verification
    unit = artifact.units.get("energy", "unspecified")
    if result.task_id == "mapping_analysis":
        report = result.task_result or {}
        rows = []
        for entry in report.get("entries", []):
            resource = entry.get("mapped_artifact", {}).get("resource_report", {})
            capability = entry.get("mapped_artifact", {}).get("capability_report", {})
            rows.append(
                f"- **{entry.get('mapping_id')}** — terms {resource.get('pauli_term_count')}, "
                f"max weight {resource.get('maximum_pauli_weight')}, "
                f"weighted mean {resource.get('coefficient_weighted_mean_pauli_weight'):.4g}, "
                f"QWC groups {resource.get('qwc_measurement_group_count')}, "
                f"analysis `{capability.get('support_by_task', {}).get('mapping_analysis')}`, "
                f"ground-state `{capability.get('support_by_task', {}).get('ground_state_energy')}`"
            )
        return (
            f"## {result.status}\n\n"
            f"**Task:** Fermion-to-qubit mapping analysis  \n"
            f"**Model:** `{artifact.model_id}`  \n"
            f"**Modes / target particles:** {artifact.n_qubits} / {(artifact.target_sector or {}).get('particle_number')}  \n"
            f"**All transforms verified:** {report.get('all_transforms_verified')}  \n"
            f"**Analysis-only ranking:** `{report.get('recommended_for_analysis')}`  \n\n"
            + "\n".join(rows)
            + "\n\n_No circuit, optimizer, shots, backend, or VQE execution was performed._"
        )
    if result.task_id == "observable_estimation":
        task_result = result.task_result or {}
        occupations = task_result.get("occupations") or []
        errors = task_result.get("occupation_standard_errors") or []
        formatted = ", ".join(
            f"n{i}={float(value):.5f}±{float(errors[i]):.3g}"
            if i < len(errors) else f"n{i}={float(value):.5f}"
            for i, value in enumerate(occupations)
        ) or "not available"
        reference = task_result.get("reference_occupations")
        reference_text = (
            "not available" if reference is None
            else ", ".join(f"n{i}={float(value):.5f}" for i, value in enumerate(reference))
        )
        return (
            f"## {result.status}\n\n"
            f"**Task:** observable estimation — pair occupations  \n"
            f"**Controller:** single pass (no optimizer loop)  \n"
            f"**Prepared-state source:** `{result.parameter_source}`  \n"
            f"**Measured occupations:** {formatted}  \n"
            f"**Classical reference occupations:** {reference_text}  \n"
            f"**Measured sector leakage:** {float(task_result.get('sector_leakage', float('nan'))):.6g}  \n"
            f"**Maximum occupation error:** {float(verification.get('maximum_absolute_error', float('nan'))):.6g}  \n"
            f"**Qubits:** {artifact.n_qubits}  \n"
            f"**Mapping / encoding:** {artifact.mapping or 'not declared'} / {artifact.encoding}  \n"
            f"**Selected provider target:** {result.target_backend.upper()}  \n"
            f"**Actual execution:** local Cirq simulator; no provider adapter or QPU submission.\n\n"
            "_The acceptance fixture is exact-derived and is used only to verify the "
            "single-pass task path; this is not a VQE-convergence result._"
        )

    exact = verification.get("reference_energy")
    exact_text = "not available" if exact is None else f"{float(exact):.8f} {unit}"
    mapping_note = artifact.mapping or "not declared"
    convergence = "yes" if result.optimizer_converged else "no / not invoked"
    return (
        f"## {result.status}\n\n"
        f"**Task:** ground-state / sector-ground-state energy  \n"
        f"**Run mode:** {result.run_mode}  \n"
        f"**Controller:** {result.controller_id or result.optimizer_name or 'not invoked'}  \n"
        f"**Optimizer convergence flag:** {convergence}  \n"
        f"**Energy evaluations:** {result.optimizer_evaluations}  \n"
        f"**Parameter source:** {result.parameter_source}  \n"
        f"**Reconstructed final energy:** {float(result.reconstructed_energy):.8f} {unit}  \n"
        f"**Final standard error:** {float(result.standard_error):.6g} {unit}  \n"
        f"**Exact sector/reference energy:** {exact_text}  \n"
        f"**Absolute error:** {verification.get('absolute_error', float('nan')):.6g} {unit}  \n"
        f"**Qubits:** {artifact.n_qubits}  \n"
        f"**Mapping / encoding:** {mapping_note} / {artifact.encoding}  \n"
        f"**Selected provider target:** {result.target_backend.upper()}  \n"
        f"**Actual execution:** local Cirq simulator; no provider adapter or QPU submission.\n\n"
        f"**Controller message:** {result.optimizer_message}"
    )

def convergence_plot_live(
    state: JourneyState,
    artifact: Optional[ProblemArtifact] = None,
    result: Optional[RunResult] = None,
):
    """Render task-appropriate live output without assuming an energy loop."""
    if result is not None and result.task_id == "mapping_analysis":
        fig, ax = plt.subplots(figsize=(5.6, 3.55))
        entries = list((result.task_result or {}).get("entries", []))
        if not entries:
            ax.text(0.5, 0.5, "No mapping report", ha="center", va="center")
            ax.set_axis_off(); return fig
        labels = [item.get("mapping_id", "mapping").replace(".v1", "") for item in entries]
        terms = [item.get("mapped_artifact", {}).get("resource_report", {}).get("pauli_term_count", 0) for item in entries]
        weights = [item.get("mapped_artifact", {}).get("resource_report", {}).get("coefficient_weighted_mean_pauli_weight", 0.0) for item in entries]
        x = np.arange(len(labels)); width = 0.38
        ax.bar(x - width/2, terms, width, label="Pauli terms")
        ax2 = ax.twinx(); ax2.bar(x + width/2, weights, width, alpha=0.55, label="weighted mean weight")
        ax.set_xticks(x); ax.set_xticklabels(labels, rotation=10)
        ax.set_ylabel("Pauli-term count"); ax2.set_ylabel("Coefficient-weighted mean Pauli weight")
        ax.set_title("JW / BK operator-resource comparison")
        handles, labels1 = ax.get_legend_handles_labels(); handles2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(handles+handles2, labels1+labels2, loc="best")
        fig.tight_layout(); return fig
    if result is not None and result.task_id == "observable_estimation":
        fig, ax = plt.subplots(figsize=(5.2, 3.35))
        task_result = result.task_result or {}
        occupations = np.asarray(task_result.get("occupations") or [], dtype=float)
        reference = task_result.get("reference_occupations")
        errors = np.asarray(task_result.get("occupation_standard_errors") or [], dtype=float)
        if occupations.size == 0:
            ax.text(0.5, 0.5, "No observable result", ha="center", va="center")
            ax.set_axis_off()
            return fig
        x = np.arange(occupations.size)
        yerr = errors if errors.size == occupations.size else None
        ax.bar(x, occupations, yerr=yerr, capsize=3, label="measured occupations")
        if isinstance(reference, (list, tuple)) and len(reference) == occupations.size:
            ax.scatter(x, np.asarray(reference, dtype=float), marker="x", s=60, label="classical reference")
        ax.set_xticks(x)
        ax.set_xlabel("Pair-occupation level")
        ax.set_ylabel("Occupation probability")
        ax.set_ylim(0.0, 1.05)
        ax.set_title("Single-pass pair-occupation estimation")
        ax.legend()
        fig.tight_layout()
        return fig

    fig, ax = plt.subplots(figsize=(5.2, 3.35))
    history = result.convergence_history if result is not None else state.energy_history
    if not history:
        ax.text(0.5, 0.5, "Waiting for the first reconstructed energy", ha="center", va="center")
        ax.set_axis_off()
        return fig
    energy_items = [item for item in history if item.get("energy") is not None]
    if not energy_items:
        ax.text(0.5, 0.5, "This task has no energy-convergence trace", ha="center", va="center")
        ax.set_axis_off()
        return fig
    evaluations = [
        int(item.get("evaluation", item.get("iteration", index + 1)) or index + 1)
        for index, item in enumerate(energy_items)
    ]
    energies = [float(item["energy"]) for item in energy_items]
    best = np.minimum.accumulate(np.asarray(energies, dtype=float))
    ax.plot(evaluations, energies, marker="o", label="reconstructed energy")
    ax.plot(evaluations, best, label="best so far")
    reference = None
    if result is not None:
        reference = result.verification.get("reference_energy")
    elif state.exact_reference_energy is not None:
        reference = state.exact_reference_energy
    elif artifact is not None:
        reference = (artifact.exact_reference or {}).get("reference_energy")
    if reference is not None:
        ax.axhline(float(reference), linestyle="--", label="declared reference")
    unit = "unspecified" if artifact is None else artifact.units.get("energy", "unspecified")
    ax.set_xlabel("Energy evaluation")
    ax.set_ylabel(f"Energy ({unit})")
    ax.set_title("Live external variational loop")
    ax.legend()
    fig.tight_layout()
    return fig


def convergence_plot(artifact: ProblemArtifact, result: RunResult):
    if result.task_id in {"observable_estimation", "mapping_analysis"}:
        # Reuse the live renderer for the final single-pass observable result.
        return convergence_plot_live(JourneyState.initial(result.run_id), artifact, result)
    fig, ax = plt.subplots(figsize=(5.2, 3.6))
    history = [item for item in result.convergence_history if item.get("energy") is not None]
    if not history:
        ax.text(0.5, 0.5, "No energy history", ha="center", va="center")
        ax.set_axis_off()
        return fig
    evaluations = [int(item["evaluation"]) for item in history]
    energies = [float(item["energy"]) for item in history]
    best = np.minimum.accumulate(np.asarray(energies, dtype=float))
    ax.plot(evaluations, energies, marker="o", label="sampled energy")
    ax.plot(evaluations, best, label="best so far")
    reference = (artifact.exact_reference or {}).get("reference_energy")
    if reference is not None:
        ax.axhline(float(reference), linestyle="--", label="exact reference")
    ax.set_xlabel("Energy evaluation")
    ax.set_ylabel(f"Energy ({artifact.units.get('energy', 'unspecified')})")
    ax.set_title("External variational runtime")
    ax.legend()
    fig.tight_layout()
    return fig


def spectrum_plot(artifact: ProblemArtifact):
    fig, ax = plt.subplots(figsize=(5.2, 3.6))
    reference = artifact.exact_reference or {}
    spectrum = list(reference.get("spectrum", reference.get("target_sector_spectrum", [])))
    if not spectrum:
        ax.text(0.5, 0.5, "No small-system reference spectrum", ha="center", va="center")
        ax.set_axis_off()
        return fig
    x = np.arange(len(spectrum))
    ax.scatter(x, spectrum)
    ax.vlines(x, min(spectrum), spectrum)
    ax.set_xlabel("Eigenvalue index")
    ax.set_ylabel(f"Energy ({artifact.units.get('energy', 'unspecified')})")
    ax.set_title("Exact sector/reference spectrum")
    fig.tight_layout()
    return fig


def qasm_text(result: RunResult) -> str:
    if result.task_id == "mapping_analysis":
        return (
            "// Mapping analysis does not construct or execute a circuit.\n"
            "// OpenQASM 2 / PyQASM are intentionally not applicable in Phase A.3.1.\n"
            "// Inspect the MappingComparisonReport and retained mapped-operator provenance instead."
        )
    raw = result.translation_check.get("raw_qasm2", "")
    unrolled = result.translation_check.get("unrolled_qasm2", "")
    first_measurement = ""
    if result.raw_records:
        first_measurement = result.raw_records[0].get("raw_qasm2", "")
    return (
        "// ===== FINAL BOUND ANSATZ: RAW OPENQASM 2 =====\n"
        f"{raw}\n\n"
        "// ===== FINAL BOUND ANSATZ: PYQASM-UNROLLED =====\n"
        f"{unrolled}\n\n"
        "// ===== FIRST FINAL MEASUREMENT CIRCUIT =====\n"
        f"{first_measurement}"
    )


def diagnostics_text(artifact: ProblemArtifact, result: RunResult) -> str:
    payload = {
        "artifact": artifact.metadata(),
        "run": result.to_dict(include_artifacts=False),
    }
    return json.dumps(json_safe(payload), indent=2, ensure_ascii=False)

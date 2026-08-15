"""QCOL model-registry modelling entrance + live journey.

The default experience is no-code and physicist-first:

    physical model family -> supported problem -> physics parameters
    -> request -> run_pipeline_stream(request) -> inspectable journey.

The Gradio layer never constructs Hamiltonians, circuits, or verification
results.  Advanced matrix/Pauli inputs are deliberately separated from the
guided entrance.
"""
from __future__ import annotations

import os
from pathlib import Path
import traceback
from typing import Any, Iterator, Optional

import gradio as gr

from .config import REFERENCE_POLICY
from .contracts import ProblemArtifact, RunResult
from .evidence import save_and_archive_pipeline_evidence
from .events import JourneyState
from .failures import build_pipeline_failure, format_technical_error_log
from .journey import (
    GUIDED_VIEW_CSS,
    backend_status_markdown,
    boundary_contract_markdown,
    qasm_semantic_fidelity,
    render_evidence_html,
    render_feedback_html,
    render_journey_html,
    render_physical_return_html,
)
from .orchestrator import run_pipeline_stream
from .run_manager import compact_result_view, public_artifact_view
from .model_task_matrix import public_model_task_matrix
from .model_registry import public_model_registry
from .task_registry import public_task_registry
from .realization_variants import public_model_task_realization_catalog
from .ui_service import (
    BACKEND_LABELS,
    CUSTOM_ROUTE_LABELS,
    FERMION_PROBLEM_LABELS,
    MODEL_FAMILY_LABELS,
    OSCILLATOR_PROBLEM_LABELS,
    RUN_MODE_LABELS,
    TASK_LABELS,
    GROUND_STATE_TASK_LABEL,
    OBSERVABLE_TASK_LABEL,
    MAPPING_ANALYSIS_TASK_LABEL,
    build_request,
    convergence_plot_live,
    diagnostics_text,
    fermion_problem_ui_schema,
    model_family_guidance,
    qho_model_ui_schema,
    qasm_text,
    spectrum_plot,
    summary_markdown,
    scientific_core_markdown,
)

BACKENDS = list(BACKEND_LABELS)
MODEL_FAMILIES = ["Oscillators", "Fermions", "Custom"]
FERMION_ROUTES = ["Reduced-pairing model contracts", "General spin-orbital — Mapping Explorer / JW ground state"]
RUN_MODES = list(RUN_MODE_LABELS)
TASKS = list(TASK_LABELS)
FERMION_PROBLEMS = list(FERMION_PROBLEM_LABELS)
OSCILLATOR_PROBLEMS = list(OSCILLATOR_PROBLEM_LABELS)
CUSTOM_ROUTES = list(CUSTOM_ROUTE_LABELS)
EVIDENCE_ROOT = Path(os.getenv("QCOL_EVIDENCE_ROOT", "qcol_phase_a2_evidence"))



WP12_SURFACE_CSS = r"""
.qcol-capability-surface{border:1px solid #2b3b50;border-radius:14px;background:#0d1621;padding:14px;margin:10px 0 16px}
.qcol-capability-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;margin-bottom:10px}
.qcol-capability-head strong{font-size:15px;color:#e5edf7}.qcol-capability-head small{display:block;color:#9aa8b9;margin-top:3px}
.qcol-axis-badge{border:1px solid #6658aa;color:#c4baff;background:#1c1835;border-radius:999px;padding:4px 9px;font-size:10px;font-weight:800;white-space:nowrap}
.qcol-matrix-scroll{overflow:auto;border:1px solid #26364a;border-radius:10px}
.qcol-matrix{border-collapse:collapse;width:100%;min-width:940px;font-size:10px}
.qcol-matrix th,.qcol-matrix td{border-right:1px solid #26364a;border-bottom:1px solid #26364a;padding:7px;vertical-align:top}.qcol-matrix th{background:#132033;color:#cbd8e8;text-align:left}.qcol-matrix .rowhead{background:#101a27;font-weight:700;min-width:190px}
.qcol-cell{border:1px solid #34455e;border-radius:8px;padding:6px;background:#111c2a;min-height:45px}.qcol-cell.acceptance_verified{border-color:#287459;background:#0f2821}.qcol-cell.experimental{border-color:#88611f;background:#2b1e0a}.qcol-cell.execution_ready{border-color:#376b9e;background:#102239}.qcol-cell.selected{box-shadow:0 0 0 2px rgba(155,135,245,.33)}
.qcol-cell b{display:block;font-size:9px}.qcol-cell span{display:block;color:#93a3b7;font-size:8px;margin-top:3px}
.qcol-variant-drawer{margin-top:12px;border:1px solid #3c4e68;border-radius:11px;padding:12px;background:#0b141f}.qcol-variant-drawer h4{margin:0 0 4px;color:#e5edf7}.qcol-variant-drawer>p{margin:0 0 10px;color:#9aa8b9;font-size:11px}
.qcol-variant-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px}.qcol-variant{border:1px solid #33455e;border-radius:10px;padding:10px;background:#101925}.qcol-variant.run{border-color:#287459;background:#0f2821}.qcol-variant.fail{border-color:#8e4542;background:#291517}.qcol-variant.blocked{border-color:#6253a8;background:#1d1938}.qcol-variant.review{border-color:#88611f;background:#2b1e0a}
.qcol-variant h5{margin:0 0 7px;font-size:11px;color:#e5edf7}.qcol-triplet{display:grid;grid-template-columns:repeat(3,1fr);gap:4px}.qcol-triplet div{border:1px solid rgba(150,170,190,.18);border-radius:6px;padding:5px}.qcol-triplet span{display:block;color:#91a0b2;font-size:7px;text-transform:uppercase}.qcol-triplet b{font-size:8px;overflow-wrap:anywhere}.qcol-variant code{display:block;margin-top:8px;color:#ff9b96;font-size:8px;overflow-wrap:anywhere}.qcol-variant p{font-size:9px;color:#a9b6c6;line-height:1.4}.qcol-route{display:inline-block;margin-top:7px;border:1px solid currentColor;border-radius:999px;padding:2px 6px;font-size:7px;text-transform:uppercase;color:#93a3b7}
@media(max-width:900px){.qcol-variant-grid{grid-template-columns:1fr}.qcol-capability-head{flex-direction:column}.qcol-axis-badge{align-self:flex-start}}
"""


def _html_escape(value: Any) -> str:
    import html
    return html.escape(str(value if value is not None else "—"))


def _surface_model_id(
    model_family: str,
    fermion_route_label: str,
    fermion_problem_label: str,
    oscillator_problem_label: str,
    custom_route_label: str,
) -> str:
    if model_family == "Fermions":
        if fermion_route_label == FERMION_ROUTES[1]:
            return "fermion.general_spin_orbital"
        problem_id = FERMION_PROBLEM_LABELS.get(fermion_problem_label, fermion_problem_label)
        return (
            "nuclear.reduced_pairing.one_pair"
            if problem_id in {"four_level_one_pair", "one_pair_pairing"}
            else "nuclear.reduced_pairing.multi_pair"
        )
    if model_family == "Oscillators":
        return OSCILLATOR_PROBLEM_LABELS.get(
            oscillator_problem_label, oscillator_problem_label
        )
    route = CUSTOM_ROUTE_LABELS.get(custom_route_label, custom_route_label)
    return (
        "custom.occupation_coupling.one_excitation"
        if route == "guided"
        else "custom.qubit_hamiltonian"
    )


def render_model_task_realization_surface_html(
    model_family: str = MODEL_FAMILIES[0],
    fermion_route_label: str = FERMION_ROUTES[0],
    fermion_problem_label: str = FERMION_PROBLEMS[0],
    oscillator_problem_label: str = OSCILLATOR_PROBLEMS[0],
    custom_route_label: str = CUSTOM_ROUTES[0],
    task_label: str = GROUND_STATE_TASK_LABEL,
) -> str:
    """Render a two-axis Model × Task map and one internal variant drawer."""
    matrix = public_model_task_matrix()
    catalog = public_model_task_realization_catalog()
    model_id = _surface_model_id(
        model_family,
        fermion_route_label,
        fermion_problem_label,
        oscillator_problem_label,
        custom_route_label,
    )
    task_id = TASK_LABELS.get(task_label, task_label)
    cell_id = f"{model_id}::{task_id}"
    cell_map = {item["cell_id"]: item for item in matrix["cells"]}
    realization_map = {item["cell_id"]: item for item in catalog["cells"]}
    model_labels = {
        item["model_id"]: item.get("label", item["model_id"])
        for item in public_model_registry()["contracts"]
    }
    task_labels = {
        item["task_id"]: item.get("label", item["task_id"])
        for item in public_task_registry()["tasks"]
    }
    header = "".join(
        f"<th>{_html_escape(task_labels.get(task, task))}</th>"
        for task in matrix["columns"]
    )
    rows = []
    for row_model in matrix["rows"]:
        cells = []
        for task in matrix["columns"]:
            entry = cell_map.get(f"{row_model}::{task}")
            if entry is None:
                cells.append("<td>—</td>")
                continue
            variants = entry.get("realization_variants", {})
            selected = " selected" if entry["cell_id"] == cell_id else ""
            cells.append(
                f'<td><div class="qcol-cell {_html_escape(entry["status"])}{selected}">'
                f'<b>{_html_escape(entry["status"].replace("_", " "))}</b>'
                f'<span>{_html_escape(variants.get("variant_count", 0))} variants · '
                f'{_html_escape(variants.get("runnable_variant_count", 0))} runnable</span></div></td>'
            )
        rows.append(
            f'<tr><td class="rowhead">{_html_escape(model_labels.get(row_model, row_model))}</td>{"".join(cells)}</tr>'
        )
    selected_cell = realization_map.get(cell_id)
    if selected_cell is None:
        selected_cell = realization_map.get(next((key for key in realization_map if key.startswith(model_id + "::")), ""))
    cards = []
    if selected_cell:
        for variant in selected_cell["variants"]:
            css = (
                "fail" if variant["composition_status"] == "failed"
                else "blocked" if not variant["runnable"] and variant["composition_status"] == "unresolved"
                else "review" if variant["composition_status"] == "review" or variant["cell_status"] == "experimental"
                else "run" if variant["runnable"] else "blocked"
            )
            failure = (
                f'<code>{_html_escape(variant.get("failure_code"))}</code>'
                f'<p>{_html_escape(variant.get("failure_message"))}</p>'
                if variant.get("failure_code") else ""
            )
            cards.append(
                f'<article class="qcol-variant {css}"><h5>{_html_escape(variant["label"])}</h5>'
                '<div class="qcol-triplet">'
                f'<div><span>mapper</span><b>{_html_escape(variant["mapper_status"])}</b></div>'
                f'<div><span>composition</span><b>{_html_escape(variant["composition_status"])}</b></div>'
                f'<div><span>cell</span><b>{_html_escape(variant["cell_status"])}</b></div>'
                f'</div><p>{_html_escape(variant["support_scope"])}</p>{failure}'
                f'<span class="qcol-route">{"runnable through shared runtime" if variant["runnable"] else "not offered as runnable"}</span></article>'
            )
    selected_title = (
        f'{model_labels.get(selected_cell["model_id"], selected_cell["model_id"])} × '
        f'{task_labels.get(selected_cell["task_id"], selected_cell["task_id"])}'
        if selected_cell else "No registered cell"
    )
    return (
        '<section class="qcol-capability-surface">'
        '<div class="qcol-capability-head"><div><strong>Model × Task capability map</strong>'
        '<small>The public surface stays two-dimensional; mapping, state, ansatz, reference, and evidence are internal realization records.</small></div>'
        '<span class="qcol-axis-badge">2 axes only</span></div>'
        f'<div class="qcol-matrix-scroll"><table class="qcol-matrix"><thead><tr><th>Model × Task</th>{header}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
        f'<div class="qcol-variant-drawer"><h4>{_html_escape(selected_title)}</h4>'
        '<p>Internal RealizationVariants — inspectable scientific decisions, not extra user-facing matrix axes.</p>'
        f'<div class="qcol-variant-grid">{"".join(cards) if cards else "No variants registered."}</div></div></section>'
    )


def update_model_task_realization_surface(
    model_family: str,
    fermion_route_label: str,
    fermion_problem_label: str,
    oscillator_problem_label: str,
    custom_route_label: str,
    task_label: str,
) -> str:
    return render_model_task_realization_surface_html(
        model_family,
        fermion_route_label,
        fermion_problem_label,
        oscillator_problem_label,
        custom_route_label,
        task_label,
    )

def update_scientific_core_inspector(
    model_family: str,
    fermion_route_label: str,
    fermion_problem_label: str,
    oscillator_problem_label: str,
    custom_route_label: str,
) -> str:
    model_id = _surface_model_id(
        model_family,
        fermion_route_label,
        fermion_problem_label,
        oscillator_problem_label,
        custom_route_label,
    )
    return scientific_core_markdown(model_id)


def update_model_family(model_family: str):
    fermionic = model_family == "Fermions"
    return (
        gr.update(visible=fermionic),
        gr.update(visible=fermionic),
        gr.update(visible=False),
        gr.update(visible=model_family == "Oscillators"),
        gr.update(visible=model_family == "Custom"),
        model_family_guidance(model_family),
    )


def update_fermion_route(route_label: str):
    mapping_route = route_label == FERMION_ROUTES[1]
    return (
        gr.update(visible=not mapping_route),
        gr.update(visible=mapping_route),
        gr.update(
            choices=([MAPPING_ANALYSIS_TASK_LABEL, GROUND_STATE_TASK_LABEL] if mapping_route else [GROUND_STATE_TASK_LABEL, OBSERVABLE_TASK_LABEL]),
            value=(MAPPING_ANALYSIS_TASK_LABEL if mapping_route else GROUND_STATE_TASK_LABEL),
        ),
        (
            "**General spin-orbital route:** choose verified JW/BK mapping analysis or the "
            "bounded JW-only fixed-particle ground-state execution cell. BK full execution is not enabled."
            if mapping_route else
            "**Reduced-pairing route:** choose a problem-specific one-pair or multi-pair contract."
        ),
    )


def update_task_availability(model_family: str, fermion_route_label: str, fermion_problem_label: str):
    """Expose only verified/runnable cells for the currently selected model route."""
    if model_family == "Fermions" and fermion_route_label == FERMION_ROUTES[1]:
        return gr.update(choices=[MAPPING_ANALYSIS_TASK_LABEL, GROUND_STATE_TASK_LABEL], value=MAPPING_ANALYSIS_TASK_LABEL)
    choices = [GROUND_STATE_TASK_LABEL]
    problem_id = FERMION_PROBLEM_LABELS.get(fermion_problem_label, fermion_problem_label)
    if model_family == "Fermions" and problem_id in {"four_level_one_pair", "one_pair_pairing"}:
        choices.append(OBSERVABLE_TASK_LABEL)
    return gr.update(choices=choices, value=choices[0])


def update_task_controls(task_label: str):
    task_id = TASK_LABELS.get(task_label)
    observable = task_id == "observable_estimation"
    mapping_analysis = task_id == "mapping_analysis"
    if mapping_analysis:
        note = (
            "**Mapping-analysis task:** transforms the same FermionOperator with JW and BK, "
            "verifies full and fixed-particle spectra, and compares operator resources. "
            "No optimizer, QASM, shots, simulator, or hardware run is invoked."
        )
    elif observable:
        note = (
            "**Single-pass task:** measures pair occupations and sector leakage on the "
            "verified one-pair cell. No optimizer loop is invoked. The acceptance fixture "
            "is exact-derived and labelled acceptance-only, not VQE convergence."
        )
    else:
        note = (
            "**Ground-state task:** the external COBYLA controller repeatedly calls the "
            "shared energy evaluator until its stopping rule is met."
        )
    fixed_single = observable or mapping_analysis
    return (
        gr.update(value=("Single validated θ evaluation" if fixed_single else RUN_MODES[0]), interactive=not fixed_single),
        gr.update(interactive=not fixed_single),
        gr.update(interactive=not fixed_single),
        note,
    )


def update_spin_orbital_task_controls(task_label: str):
    task_id = TASK_LABELS.get(task_label)
    analysis = task_id == "mapping_analysis"
    return (
        gr.update(
            value=(
                ["jordan_wigner.v1", "bravyi_kitaev.v1"]
                if analysis else ["jordan_wigner.v1"]
            ),
            interactive=analysis,
            label=(
                "Mapping plugins to compare"
                if analysis else "Execution mapping — fixed by accepted cell"
            ),
        ),
        gr.update(interactive=analysis),
        gr.update(interactive=analysis),
        gr.update(interactive=not analysis),
        gr.update(interactive=not analysis),
        (
            "**Analysis boundary:** JW and BK transformation/resource analysis; no circuit, shots, or backend."
            if analysis else
            "**Execution boundary:** JW only · 2–4 modes · fixed particle number · occupation determinant · mapping-aware fermionic swap-network ansatz · exact bounded reference. Cell status: acceptance verified."
        ),
    )


def _qho_contract_markdown(schema: dict[str, Any]) -> str:
    rendered = ", ".join(schema["rendered_parameter_keys"])
    fixed = schema.get("fixed_parameters", {})
    fixed_text = ", ".join(f"{key}={value}" for key, value in fixed.items()) or "none"
    policies = schema.get("policies", {})
    return (
        f"### {schema['label']}  \n"
        f"{schema['description']}  \n\n"
        f"**Generated controls:** `{rendered}`  \n"
        f"**Fixed by contract:** `{fixed_text}`  \n"
        f"**Encoding / ansatz:** `{policies.get('mapping')}` / `{policies.get('ansatz')}`  \n"
        f"**Cell status:** `{schema['execution_status']}` — each QHO model remains experimental until its own acceptance promotion."
    )


def update_oscillator_schema(model_label: str):
    """Drive the QHO controls entirely from the selected ModelContract."""
    schema = qho_model_ui_schema(model_label)
    fields = {item["key"]: item for item in schema["parameter_fields"]}

    def update_for(key: str, *, numeric: bool = False):
        spec = fields[key]
        show = bool(spec["render"])
        value = spec.get("default")
        if spec.get("role") == "fixed":
            value = spec.get("fixed_value")
        kwargs = {
            "visible": show,
            "interactive": show,
            "value": value,
            "label": spec.get("label", key),
        }
        if numeric:
            kwargs.update({
                "minimum": spec.get("minimum"),
                "maximum": spec.get("maximum"),
                "step": spec.get("step"),
            })
        return gr.update(**kwargs)

    return (
        _qho_contract_markdown(schema),
        update_for("n_modes", numeric=True),
        update_for("omega"),
        update_for("coupling"),
        update_for("kappa"),
        gr.update(visible=False, value=str(fields["energy_unit"].get("default") or "MeV")),
    )


def update_custom_route(route_label: str):
    route = CUSTOM_ROUTE_LABELS.get(route_label)
    return (
        gr.update(visible=route == "guided"),
        gr.update(visible=route == "matrix"),
        gr.update(visible=route == "pauli"),
        gr.update(visible=route in {"matrix", "pauli"}),
    )


MAX_FERMION_LEVELS = 6


def _schema_field_map(schema: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item["key"]): item
        for item in schema.get("parameter_schema", {}).get("fields", [])
    }


def _pair_choices(fields: dict[str, dict[str, Any]], n_levels: int) -> list[int]:
    spec = fields["n_pairs"]
    if spec.get("role") == "fixed":
        return [int(spec.get("fixed_value"))]
    minimum = int(spec.get("minimum") or spec.get("default") or 1)
    declared_maximum = int(spec.get("maximum") or minimum)
    maximum = min(declared_maximum, max(int(n_levels) - 1, minimum))
    return list(range(minimum, maximum + 1))


def _fermion_contract_markdown(schema: dict[str, Any]) -> str:
    fields = _schema_field_map(schema)
    fixed = [
        f"`{item['label']} = {item.get('fixed_value')}`"
        for item in fields.values()
        if item.get("role") == "fixed" and item.get("visible", True)
    ]
    return (
        f"#### {schema['label']}  \n"
        f"**Support:** `{schema['support_status']}` · **Execution:** `{schema['execution_status']}`  \n"
        f"{schema['description']}  \n"
        f"**Declared contract:** {', '.join(fixed)}  \n"
        f"**Mapping / encoding:** `{fields['mapping'].get('fixed_value', schema['mapping_policy'])}` "
        f"(automatic via ModelContract + Capability Resolver) · `{schema['encoding']}`  \n"
        "**Resolved policies:** shown after Build & Run through `ScientificRealizationView v1`."
    )


def update_fermion_problem(problem_label: str):
    schema = fermion_problem_ui_schema(problem_label)
    fields = _schema_field_map(schema)
    n_field = fields["n_levels"]
    n_levels = int(n_field.get("fixed_value") if n_field.get("role") == "fixed" else n_field.get("default", 4))
    epsilon_default = list(fields["epsilon"].get("default") or [])
    if len(epsilon_default) != n_levels:
        epsilon_default = [float(index) for index in range(n_levels)]
    epsilon_updates = [
        gr.update(
            value=(epsilon_default[index] if index < len(epsilon_default) else float(index)),
            visible=index < n_levels,
            interactive=True,
            label=f"ε{index}",
        )
        for index in range(MAX_FERMION_LEVELS)
    ]
    return (
        _fermion_contract_markdown(schema),
        gr.update(value=n_levels, interactive=n_field.get("role") == "editable"),
        gr.update(
            value=(fields["n_particles"].get("fixed_value") if fields["n_particles"].get("role") == "fixed" else fields["n_particles"].get("default")),
            interactive=False,
        ),
        gr.update(
            choices=_pair_choices(fields, n_levels),
            value=(fields["n_pairs"].get("fixed_value") if fields["n_pairs"].get("role") == "fixed" else fields["n_pairs"].get("default")),
            interactive=fields["n_pairs"].get("role") == "editable",
        ),
        gr.update(value=fields["seniority"].get("fixed_value"), interactive=False),
        gr.update(value=fields["mapping"].get("fixed_value"), interactive=False),
        gr.update(value=fields["g"].get("default", 0.5), interactive=True),
        gr.update(value=fields["energy_unit"].get("default", "MeV"), interactive=True),
        *epsilon_updates,
    )


def update_fermion_level_count(
    problem_label: str,
    n_levels_value: Any,
    n_pairs_value: Any,
    *epsilon_values: Any,
):
    schema = fermion_problem_ui_schema(problem_label)
    fields = _schema_field_map(schema)
    n_field = fields["n_levels"]
    if n_field.get("role") == "fixed":
        n_levels = int(n_field.get("fixed_value"))
    else:
        try:
            n_levels = int(n_levels_value)
        except (TypeError, ValueError):
            n_levels = int(n_field.get("default", 4))
        minimum = int(n_field.get("minimum") or 2)
        maximum = int(n_field.get("maximum") or MAX_FERMION_LEVELS)
        n_levels = max(minimum, min(maximum, n_levels))

    pair_choices = _pair_choices(fields, n_levels)
    try:
        selected_pairs = int(n_pairs_value)
    except (TypeError, ValueError):
        selected_pairs = pair_choices[0]
    if selected_pairs not in pair_choices:
        selected_pairs = pair_choices[0]

    defaults = list(fields["epsilon"].get("default") or [])
    updates = []
    for index in range(MAX_FERMION_LEVELS):
        current = epsilon_values[index] if index < len(epsilon_values) else None
        if current is None:
            current = defaults[index] if index < len(defaults) else float(index)
        updates.append(gr.update(value=current, visible=index < n_levels, label=f"ε{index}"))
    return (
        gr.update(value=n_levels),
        gr.update(choices=pair_choices, value=selected_pairs),
        gr.update(value=2 * selected_pairs),
        *updates,
    )


def update_particle_count(n_pairs_value: Any):
    try:
        pairs = int(n_pairs_value)
    except (TypeError, ValueError):
        pairs = 1
    return gr.update(value=2 * pairs)


def _live_summary(state: JourneyState, artifact: Optional[ProblemArtifact]) -> str:
    unit = "unspecified" if artifact is None else artifact.units.get("energy", "unspecified")
    latest = state.energy_history[-1] if state.energy_history else None
    energy = "—" if latest is None else f"{float(latest['energy']):.8g} {unit}"
    best = "—" if state.best_energy is None else f"{state.best_energy:.8g} {unit}"
    return (
        "### Live run summary\n\n"
        f"**Run ID:** `{state.run_id}`  \n"
        f"**Current iteration:** {state.current_iteration or '—'}  \n"
        f"**Latest reconstructed energy:** {energy}  \n"
        f"**Best energy so far:** {best}  \n"
        f"**Verification:** {state.verification_status}  \n"
        f"**Reference policy:** `{state.reference_policy}`"
    )


def _backend_live(state: JourneyState, backend_label: str) -> str:
    target = BACKEND_LABELS.get(backend_label, "unknown").upper()
    execute = state.cards["execute"]
    return (
        f"**Execution:** local simulator · **Target:** {target} · "
        f"**Hardware submission:** not performed  \n"
        f"_Execute status: {execute.status}. IBM/Google/AWS adapters remain the Phase 5 seam._"
    )


def on_run_stream(
    model_family, task_label, backend, run_mode, shots, max_evaluations, energy_tolerance,
    seed, initial_parameters, acceptance_floor,
    fermion_route, fermion_problem, g, n_levels, n_particles, n_pairs, seniority, mapping_value,
    fermion_unit, epsilon_0, epsilon_1, epsilon_2, epsilon_3, epsilon_4, epsilon_5,
    spin_n_modes, spin_particle_species, spin_mode_labels, spin_one_body_terms,
    spin_two_body_terms, spin_target_particles, spin_initial_occupied_modes,
    spin_ansatz_layers, spin_symmetries,
    spin_coefficient_convention, spin_unit, spin_mapping_ids,
    spin_coefficient_threshold, spin_equivalence_tolerance,
    oscillator_problem, omega, coupling, kappa, n_modes, oscillator_unit,
    custom_route, guided_model_name, guided_n_modes, guided_onsite,
    guided_couplings, guided_offset, guided_unit, matrix_str, pauli_str,
    custom_n_qubits, custom_layers, custom_unit,
) -> Iterator[tuple[Any, ...]]:
    """Gradio generator: one no-code request enters the shared live pipeline."""
    artifact: Optional[ProblemArtifact] = None
    result: Optional[RunResult] = None
    evidence_zip: Optional[str] = None
    advisor_context_payload = None
    advisor_report_payload = None
    error_text = ""
    try:
        effective_model_family = (
            "General spin-orbital representation"
            if model_family == "Fermions" and fermion_route == FERMION_ROUTES[1]
            else model_family
        )
        request = build_request(
            backend_label=backend,
            model_family_label=effective_model_family,
            run_mode_label=run_mode,
            shots=int(shots),
            max_evaluations=int(max_evaluations),
            energy_tolerance=float(energy_tolerance),
            seed=int(seed),
            initial_parameters_text=initial_parameters,
            acceptance_abs_floor=float(acceptance_floor),
            fermion_problem=fermion_problem,
            epsilon_text=", ".join(
                str(value) for value in
                [epsilon_0, epsilon_1, epsilon_2, epsilon_3, epsilon_4, epsilon_5][: int(n_levels)]
            ),
            n_levels=int(n_levels),
            pairing_strength=float(g),
            n_particles=int(n_particles),
            n_pairs=int(n_pairs),
            fermion_energy_unit=fermion_unit,
            oscillator_problem=oscillator_problem,
            oscillator_n_modes=int(n_modes),
            oscillator_omega_text=omega,
            oscillator_coupling_text=coupling,
            oscillator_kappa_text=kappa,
            oscillator_energy_unit=oscillator_unit,
            custom_route_label=custom_route,
            guided_model_name=guided_model_name,
            guided_n_modes=int(guided_n_modes),
            guided_onsite_text=guided_onsite,
            guided_couplings_text=guided_couplings,
            guided_energy_offset=float(guided_offset),
            guided_energy_unit=guided_unit,
            custom_matrix_text=matrix_str,
            custom_pauli_text=pauli_str,
            custom_n_qubits=int(custom_n_qubits),
            custom_ansatz_layers=int(custom_layers),
            custom_energy_unit=custom_unit,
            spin_n_modes=int(spin_n_modes),
            spin_particle_species=spin_particle_species,
            spin_mode_labels_text=spin_mode_labels,
            spin_one_body_terms_text=spin_one_body_terms,
            spin_two_body_terms_text=spin_two_body_terms,
            spin_target_particle_number=int(spin_target_particles),
            spin_initial_occupied_modes_text=spin_initial_occupied_modes,
            spin_ansatz_layers=int(spin_ansatz_layers),
            spin_declared_symmetries_text=spin_symmetries,
            spin_coefficient_convention=spin_coefficient_convention,
            spin_energy_unit=spin_unit,
            spin_mapping_ids=spin_mapping_ids,
            spin_coefficient_threshold=float(spin_coefficient_threshold),
            spin_equivalence_tolerance=float(spin_equivalence_tolerance),
            task_label=task_label,
        )

        for update in run_pipeline_stream(request):
            if update.artifact is not None:
                artifact = update.artifact
            if update.result is not None:
                result = update.result
            if update.error:
                error_text = update.error

            if result is not None and evidence_zip is None:
                # The Advisor is optional and post-run.  Its unavailability may
                # not turn a verified scientific run into an evidence failure.
                try:
                    from .advisor import advise_run_payload
                    enabled = os.getenv("QCOL_ADVISOR_ENABLED", "1").strip().lower() not in {
                        "0", "false", "off", "no", "disabled"
                    }
                    advisor_context, advisor_report = advise_run_payload(
                        {
                            "run_id": result.run_id,
                            "status": "completed",
                            "request": request,
                            "artifact": public_artifact_view(artifact) or {},
                            "result": compact_result_view(result) or {},
                            "evidence_available": False,
                        },
                        enabled=enabled,
                    )
                    advisor_context_payload = advisor_context.to_dict()
                    advisor_report_payload = advisor_report.to_dict()
                except Exception:
                    advisor_context_payload = None
                    advisor_report_payload = None

                try:
                    _, archive = save_and_archive_pipeline_evidence(
                        artifact,
                        result,
                        EVIDENCE_ROOT,  # type: ignore[arg-type]
                        advisor_context=advisor_context_payload,
                        advisor_report=advisor_report_payload,
                    )
                    evidence_zip = str(archive)
                except Exception as evidence_error:
                    traceback_text = traceback.format_exc()
                    failure = build_pipeline_failure(
                        evidence_error,
                        run_id=update.state.run_id,
                        stage="evidence",
                        iteration=update.state.current_iteration or None,
                        artifact_refs=("evidence_archive",),
                    )
                    failed_state = update.state.snapshot()
                    failed_state.mark_failed(failure)
                    error_text = format_technical_error_log(failure, traceback_text)
                    yield (
                        render_journey_html(failed_state),
                        render_physical_return_html(failed_state, artifact, result),
                        render_evidence_html(failed_state, result),
                        render_feedback_html(failed_state),
                        convergence_plot_live(failed_state, artifact, result),
                        spectrum_plot(artifact),
                        boundary_contract_markdown(artifact),
                        summary_markdown(artifact, result),
                        qasm_text(result),
                        diagnostics_text(artifact, result),
                        None,
                        backend_status_markdown(result),
                        error_text,
                    )
                    return

            plot_update: Any = gr.update()
            if (
                update.done
                or update.event is None
                or update.event.stage in {"reconstruct", "exact_reference", "convergence"}
            ):
                plot_update = convergence_plot_live(update.state, artifact, result)

            spectrum_update: Any = gr.update()
            boundary_update: Any = gr.update()
            if update.artifact is not None:
                spectrum_update = spectrum_plot(artifact)  # type: ignore[arg-type]
                boundary_update = boundary_contract_markdown(artifact)

            final_summary = (
                summary_markdown(artifact, result)  # type: ignore[arg-type]
                if result is not None
                else _live_summary(update.state, artifact)
            )
            final_qasm = qasm_text(result) if result is not None else ""
            final_diag = diagnostics_text(artifact, result) if result is not None else ""
            if result is not None:
                fidelity = qasm_semantic_fidelity(result)
                final_diag += (
                    "\n\nQASM semantic fidelity (translation check; not state fidelity): "
                    + ("not available" if fidelity is None else f"{fidelity:.12f}")
                )

            yield (
                render_journey_html(update.state),
                render_physical_return_html(update.state, artifact, result),
                render_evidence_html(update.state, result),
                render_feedback_html(update.state, advisor_report_payload),
                plot_update,
                spectrum_update,
                boundary_update,
                final_summary,
                final_qasm,
                final_diag,
                evidence_zip,
                (
                    backend_status_markdown(result)
                    if result is not None
                    else _backend_live(update.state, backend)
                ),
                error_text,
            )
    except Exception as error:
        traceback_text = traceback.format_exc()
        state = JourneyState.initial("request-error", reference_policy=REFERENCE_POLICY)
        failure = build_pipeline_failure(
            error,
            run_id=state.run_id,
            stage="model",
        )
        state.mark_failed(failure)
        yield (
            render_journey_html(state),
            render_physical_return_html(state),
            render_evidence_html(state),
            render_feedback_html(state),
            None,
            None,
            boundary_contract_markdown(None),
            "## Request stopped at Model & Hamiltonian\n\n"
            + failure.user_message
            + ("\n\n**Suggested correction:** " + failure.suggested_action if failure.suggested_action else ""),
            "",
            "",
            None,
            "",
            format_technical_error_log(failure, traceback_text),
        )


_INITIAL_STATE = JourneyState.initial("preview", reference_policy=REFERENCE_POLICY)

with gr.Blocks(
    title="QCOL — Model × Task Modelling Journey",
    css=GUIDED_VIEW_CSS + WP12_SURFACE_CSS,
) as demo:
    gr.Markdown("# QCOL — Model × Task Modelling Journey")
    gr.Markdown(
        "**No-code by default, inspectable by choice.** Nuclear researchers start "
        "with a physical model and its parameters; QCOL builds the Hamiltonian and "
        "quantum workflow internally. Users who want deeper engagement can inspect "
        "every artifact, measurement, and verification step."
    )

    with gr.Group(elem_id="physics-modelling-entrance"):
        gr.HTML(
            '<div class="qcol-section-heading"><span>A</span><div><strong>Physics Modelling Entrance</strong>'
            '<small>Choose the physical system first. The interactive quantum journey begins after the model is declared.</small></div></div>'
        )
        model_family = gr.Radio(
            MODEL_FAMILIES,
            value=MODEL_FAMILIES[0],
            label="1. Choose a physical modelling route (navigation only)",
            elem_id="model-family-cards",  # legacy DOM id; grouping only
        )
        model_guidance = gr.Markdown(model_family_guidance(MODEL_FAMILIES[0]))
        with gr.Accordion("Scientific core — contract and resolved-policy projection", open=True):
            scientific_core_view = gr.Markdown(
                scientific_core_markdown("nuclear.qho.free")
            )
        gr.HTML(
            '<div class="qcol-no-code-note"><strong>No programming required:</strong> '
            'you do not write Python, OpenFermion objects, Cirq circuits, QASM2, or measurement code. '
            'The selected mapping/encoding is recorded and exposed later in the ProblemArtifact inspector.</div>'
        )
        task_label = gr.Dropdown(
            TASKS,
            value=GROUND_STATE_TASK_LABEL,
            label="2. What scientific task do you want to run?",
        )
        task_guidance = gr.Markdown(
            "**Ground-state task:** the external COBYLA controller repeatedly calls the shared energy evaluator."
        )

        fermion_route = gr.Dropdown(
            FERMION_ROUTES,
            value=FERMION_ROUTES[0],
            label="3. Choose the fermionic route",
            visible=True,
        )
        fermion_route_guidance = gr.Markdown(
            "**Reduced-pairing route:** choose a problem-specific one-pair or multi-pair contract."
        )

        with gr.Group(visible=False) as fermion_group:
            gr.Markdown("### 4. Choose a supported reduced-pairing problem")
            fermion_problem = gr.Dropdown(
                FERMION_PROBLEMS,
                value=FERMION_PROBLEMS[0],
                label="Problem library",
            )
            fermion_contract = gr.Markdown(
                _fermion_contract_markdown(fermion_problem_ui_schema(FERMION_PROBLEMS[0]))
            )
            gr.Markdown(
                "**Problem-first model layer:** changing the number of particles is not "
                "treated as a parameter tweak. Each registered problem owns its sector, "
                "mapping, state preparation, ansatz, constraints, and reference policy."
            )
            gr.Markdown("### 5. Enter the parameters allowed by this problem contract")
            with gr.Row():
                n_levels = gr.Number(value=4, precision=0, label="Number of levels", interactive=False)
                n_particles = gr.Number(value=2, precision=0, label="Number of particles", interactive=False)
                n_pairs = gr.Dropdown(choices=[1], value=1, label="Number of pairs", interactive=False)
                seniority = gr.Number(value=0, precision=0, label="Seniority", interactive=False)
            gr.Markdown("**Single-particle energies — one field per declared level**")
            with gr.Row():
                epsilon_0 = gr.Number(value=0.0, label="ε0")
                epsilon_1 = gr.Number(value=1.0, label="ε1")
                epsilon_2 = gr.Number(value=2.0, label="ε2")
            with gr.Row():
                epsilon_3 = gr.Number(value=3.0, label="ε3")
                epsilon_4 = gr.Number(value=4.0, label="ε4", visible=False)
                epsilon_5 = gr.Number(value=5.0, label="ε5", visible=False)
            with gr.Row():
                g = gr.Number(value=0.5, label="Pairing strength G")
                fermion_unit = gr.Textbox(value="MeV", label="Energy unit")
                mapping_value = gr.Textbox(value="pair_mapping", label="Mapping (automatic — contract/resolver selected)", interactive=False)

        with gr.Group(visible=False) as spin_orbital_group:
            gr.Markdown("### 4. Declare a general spin-orbital FermionOperator input")
            gr.Markdown(
                "This is an intermediate fermionic representation, not a complete nuclear model. "
                "The same declared modes and coefficients are transformed by both JW and BK. "
                "Phase A.3.1 verifies transformation and mapping resources. Phase A.3.2 adds the first bounded execution cell: general spin-orbital × ground-state × Jordan–Wigner."
            )
            with gr.Row():
                spin_n_modes = gr.Number(value=4, precision=0, label="Number of spin-orbital modes")
                spin_particle_species = gr.Textbox(value="neutron", label="Particle species")
                spin_target_particles = gr.Number(value=2, precision=0, label="Target total particle number")
                spin_unit = gr.Textbox(value="MeV", label="Energy unit")
            with gr.Row():
                spin_initial_occupied_modes = gr.Textbox(
                    value="0,1",
                    label="Initial occupied modes (optional; JW execution)",
                    interactive=False,
                )
                spin_ansatz_layers = gr.Number(
                    value=1,
                    precision=0,
                    label="JW mapped-fermionic ansatz layers",
                    interactive=False,
                )
            spin_mode_labels = gr.Textbox(
                value="neutron|a|m=+1/2\nneutron|a|m=-1/2\nneutron|b|m=+1/2\nneutron|b|m=-1/2",
                lines=5, label="Mode labels — one line: species|orbital|projection",
            )
            with gr.Row():
                spin_one_body_terms = gr.Textbox(
                    value="0,0,0.0\n1,1,0.0\n2,2,1.0\n3,3,1.0\n0,2,0.2\n2,0,0.2\n1,3,0.2\n3,1,0.2",
                    lines=9, label="One-body terms — p,q,coefficient",
                )
                spin_two_body_terms = gr.Textbox(
                    value="0,1,0,1,0.08\n0,2,0,2,0.08\n0,3,0,3,0.08\n1,2,1,2,0.08\n1,3,1,3,0.08\n2,3,2,3,0.08",
                    lines=9, label="Two-body terms — p,q,r,s,coefficient",
                )
            with gr.Row():
                spin_symmetries = gr.Textbox(value="particle_number", label="Declared symmetries")
                spin_coefficient_convention = gr.Dropdown(
                    ["explicit_operator_coefficient", "antisymmetrized_v_with_quarter_prefactor"],
                    value="explicit_operator_coefficient",
                    label="Coefficient convention",
                )
            with gr.Row():
                spin_mapping_ids = gr.CheckboxGroup(
                    ["jordan_wigner.v1", "bravyi_kitaev.v1"],
                    value=["jordan_wigner.v1", "bravyi_kitaev.v1"],
                    label="Mapping plugins to compare",
                )
                spin_coefficient_threshold = gr.Number(value=1e-12, label="Resource coefficient threshold")
                spin_equivalence_tolerance = gr.Number(value=1e-8, label="Equivalence tolerance")
            spin_execution_boundary = gr.Markdown(
                "**Analysis boundary:** JW and BK transformation/resource analysis; no circuit, shots, or backend."
            )

        with gr.Group(visible=True) as oscillator_group:
            gr.Markdown("### 3. Choose a physical QHO model")
            oscillator_problem = gr.Dropdown(
                OSCILLATOR_PROBLEMS,
                value=OSCILLATOR_PROBLEMS[0],
                label="Physical model",
            )
            oscillator_contract = gr.Markdown(
                _qho_contract_markdown(qho_model_ui_schema(OSCILLATOR_PROBLEMS[0]))
            )
            gr.Markdown("### 4. Enter contract-declared parameters")
            with gr.Row():
                n_modes = gr.Number(value=4, precision=0, label="Number of modes")
                omega = gr.Textbox(value="1.0", label="Mode frequencies ω")
            with gr.Row():
                coupling = gr.Textbox(value="0.0", label="Mode coupling G", visible=False)
                kappa = gr.Textbox(value="0.0", label="Spin-orbit shift κ", visible=False)
                oscillator_unit = gr.Textbox(value="MeV", label="Energy unit", visible=False)

        with gr.Group(visible=False) as custom_group:
            gr.Markdown("### 3. Choose how to declare the custom model")
            custom_route = gr.Radio(
                CUSTOM_ROUTES,
                value=CUSTOM_ROUTES[0],
                label="Custom route",
            )

            with gr.Group(visible=True) as guided_custom_group:
                gr.Markdown("### 4. Guided occupation/coupling model — no code")
                gr.Markdown(
                    "Declare a bounded model of levels or modes with onsite energies "
                    "and pairwise couplings. QCOL constructs  "
                    "$H=E_0I+\\sum_i\\epsilon_i n_i-\\tfrac12\\sum_{i<j}G_{ij}(X_iX_j+Y_iY_j)$ "
                    "in the one-excitation sector."
                )
                guided_model_name = gr.Textbox(
                    value="custom coupled-level model",
                    label="Model name",
                )
                with gr.Row():
                    guided_n_modes = gr.Number(value=4, precision=0, label="Number of levels / modes")
                    guided_onsite = gr.Textbox(
                        value="0.0, 1.0, 2.0, 3.0",
                        label="Onsite energies ε",
                    )
                    guided_offset = gr.Number(value=0.0, label="Energy offset E₀")
                guided_couplings = gr.Textbox(
                    value="0, 1, 0.20\n1, 2, 0.15\n2, 3, 0.10",
                    lines=5,
                    label="Pairwise couplings — one row: level_i, level_j, G",
                )
                guided_unit = gr.Textbox(value="MeV", label="Energy unit")
                gr.Markdown(
                    "_Current boundary: two to six modes and one excitation. This is "
                    "a guided Hamiltonian builder, not automatic inference from raw experimental data._"
                )

            with gr.Group(visible=False) as custom_matrix_group:
                gr.Markdown("### 4. Dense Hermitian matrix — advanced")
                matrix_str = gr.Textbox(
                    value="[[0, 1], [1, 0]]",
                    lines=6,
                    label="Matrix (2^n × 2^n)",
                )

            with gr.Group(visible=False) as custom_pauli_group:
                gr.Markdown("### 4. Pauli terms — advanced")
                pauli_str = gr.Textbox(
                    value="X0: 1.0",
                    lines=6,
                    label="One term per line: term: coefficient",
                )
                custom_n_qubits = gr.Number(value=1, precision=0, label="Number of qubits")

            with gr.Group(visible=False) as custom_advanced_settings:
                with gr.Row():
                    custom_layers = gr.Number(value=1, precision=0, label="Ansatz layers")
                    custom_unit = gr.Textbox(value="dimensionless", label="Energy unit")
                gr.Markdown(
                    "_Advanced routes assume the user already knows the matrix or Pauli representation._"
                )

        gr.Markdown("### 5. Select the execution target")
        backend = gr.Dropdown(
            BACKENDS,
            value=BACKENDS[0],
            label="Quantum backend target",
        )
        gr.Markdown(
            "The target is recorded now; the current release executes locally. Provider adapters "
            "and real-hardware submission remain the Phase 5 boundary."
        )

        with gr.Accordion("Optional runtime settings", open=False):
            run_mode = gr.Radio(RUN_MODES, value=RUN_MODES[0], label="Run mode")
            with gr.Row():
                shots = gr.Dropdown(
                    [512, 1024, 2048, 4096, 8192],
                    value=2048,
                    label="Shots per measurement group",
                )
                max_evaluations = gr.Slider(
                    4, 80, value=24, step=1, label="Maximum COBYLA energy evaluations"
                )
                energy_tolerance = gr.Number(value=0.01, label="Convergence tolerance ΔE")
            with gr.Row():
                seed = gr.Number(value=42, precision=0, label="Seed")
                acceptance_floor = gr.Number(
                    value=0.05,
                    label="Verification absolute-error floor",
                )
            initial_parameters = gr.Textbox(
                value="",
                label="Optional initial θ (comma-separated)",
            )

    run_btn = gr.Button("Build / analyze", variant="primary")

    gr.HTML(
        '<div class="qcol-section-heading journey"><span>B</span><div><strong>Results</strong>'
        '<small>The compact physical return is available without opening the full live journey.</small></div></div>'
    )
    physical_out = gr.HTML(render_physical_return_html(_INITIAL_STATE))
    with gr.Accordion("Model × Task capability map — internal realization variants", open=True):
        realization_surface_out = gr.HTML(
            render_model_task_realization_surface_html()
        )
    with gr.Accordion("Full live modelling journey — architectural station map", open=False):
        journey_out = gr.HTML(render_journey_html(_INITIAL_STATE))
        feedback_out = gr.HTML(render_feedback_html(_INITIAL_STATE))
        evidence_station_out = gr.HTML(render_evidence_html(_INITIAL_STATE))

    with gr.Row():
        convergence_out = gr.Plot(label="Live variational energy")
        spectrum_out = gr.Plot(label="Declared exact/sector reference")

    with gr.Accordion("Inspect details — ProblemArtifact, QASM, evidence, and provenance", open=False):
        boundary_out = gr.Markdown(boundary_contract_markdown(None))
        backend_out = gr.Markdown(
            "**Execution:** local simulator · **Hardware submission:** not performed"
        )
        with gr.Accordion("Full run summary", open=False):
            summary_out = gr.Markdown()
        with gr.Accordion("OpenQASM 2 / PyQASM — best/final θ", open=False):
            qasm_out = gr.Textbox(label="QASM2", lines=22)
        with gr.Accordion("Diagnostics and evidence metadata", open=False):
            diag_out = gr.Textbox(label="Diagnostics", lines=22)
            evidence_out = gr.File(label="Download evidence bundle")
        with gr.Accordion("Technical error log", open=False):
            error_out = gr.Textbox(label="Traceback", lines=14)

    scientific_core_inputs = [
        model_family,
        fermion_route,
        fermion_problem,
        oscillator_problem,
        custom_route,
    ]
    for component in scientific_core_inputs:
        component.change(
            update_scientific_core_inspector,
            inputs=scientific_core_inputs,
            outputs=scientific_core_view,
        )

    model_family.change(
        update_model_family,
        inputs=model_family,
        outputs=[fermion_route, fermion_group, spin_orbital_group, oscillator_group, custom_group, model_guidance],
    )
    fermion_route.change(
        update_fermion_route,
        inputs=fermion_route,
        outputs=[fermion_group, spin_orbital_group, task_label, fermion_route_guidance],
    )
    model_family.change(
        update_task_availability,
        inputs=[model_family, fermion_route, fermion_problem],
        outputs=task_label,
    )
    fermion_problem.change(
        update_task_availability,
        inputs=[model_family, fermion_route, fermion_problem],
        outputs=task_label,
    )
    task_label.change(
        update_task_controls,
        inputs=task_label,
        outputs=[run_mode, max_evaluations, energy_tolerance, task_guidance],
    )
    task_label.change(
        update_spin_orbital_task_controls,
        inputs=task_label,
        outputs=[
            spin_mapping_ids,
            spin_coefficient_threshold,
            spin_equivalence_tolerance,
            spin_initial_occupied_modes,
            spin_ansatz_layers,
            spin_execution_boundary,
        ],
    )
    fermion_problem.change(
        update_fermion_problem,
        inputs=fermion_problem,
        outputs=[
            fermion_contract, n_levels, n_particles, n_pairs, seniority,
            mapping_value, g, fermion_unit, epsilon_0, epsilon_1, epsilon_2,
            epsilon_3, epsilon_4, epsilon_5,
        ],
    )
    n_levels.change(
        update_fermion_level_count,
        inputs=[
            fermion_problem, n_levels, n_pairs, epsilon_0, epsilon_1, epsilon_2,
            epsilon_3, epsilon_4, epsilon_5,
        ],
        outputs=[
            n_levels, n_pairs, n_particles, epsilon_0, epsilon_1, epsilon_2,
            epsilon_3, epsilon_4, epsilon_5,
        ],
    )
    n_pairs.change(
        update_particle_count,
        inputs=n_pairs,
        outputs=n_particles,
    )
    oscillator_problem.change(
        update_oscillator_schema,
        inputs=oscillator_problem,
        outputs=[oscillator_contract, n_modes, omega, coupling, kappa, oscillator_unit],
    )
    custom_route.change(
        update_custom_route,
        inputs=custom_route,
        outputs=[
            guided_custom_group,
            custom_matrix_group,
            custom_pauli_group,
            custom_advanced_settings,
        ],
    )

    for _surface_trigger in [model_family, fermion_route, fermion_problem, oscillator_problem, custom_route, task_label]:
        _surface_trigger.change(
            update_model_task_realization_surface,
            inputs=[model_family, fermion_route, fermion_problem, oscillator_problem, custom_route, task_label],
            outputs=realization_surface_out,
        )

    run_btn.click(
        on_run_stream,
        inputs=[
            model_family, task_label, backend, run_mode, shots, max_evaluations,
            energy_tolerance, seed, initial_parameters, acceptance_floor,
            fermion_route, fermion_problem, g, n_levels, n_particles, n_pairs, seniority, mapping_value,
            fermion_unit, epsilon_0, epsilon_1, epsilon_2, epsilon_3, epsilon_4, epsilon_5,
            spin_n_modes, spin_particle_species, spin_mode_labels, spin_one_body_terms,
            spin_two_body_terms, spin_target_particles, spin_initial_occupied_modes,
            spin_ansatz_layers, spin_symmetries,
            spin_coefficient_convention, spin_unit, spin_mapping_ids,
            spin_coefficient_threshold, spin_equivalence_tolerance,
            oscillator_problem, omega, coupling, kappa, n_modes, oscillator_unit,
            custom_route, guided_model_name, guided_n_modes, guided_onsite,
            guided_couplings, guided_offset, guided_unit, matrix_str, pauli_str,
            custom_n_qubits, custom_layers, custom_unit,
        ],
        outputs=[
            journey_out,
            physical_out,
            evidence_station_out,
            feedback_out,
            convergence_out,
            spectrum_out,
            boundary_out,
            summary_out,
            qasm_out,
            diag_out,
            evidence_out,
            backend_out,
            error_out,
        ],
    )

# Generator-based live updates require the queue. The app remains local-only.
demo.queue(concurrency_count=1, max_size=8)

if __name__ == "__main__":
    demo.launch(
        server_name="127.0.0.1",
        server_port=7860,
        share=False,
        inbrowser=True,
    )

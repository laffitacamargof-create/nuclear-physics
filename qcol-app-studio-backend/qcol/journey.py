"""Physicist-first renderers for the QCOL Variational Modelling Journey.

The renderers consume JourneyState / ProblemArtifact / RunResult.  They do not
construct Hamiltonians, run circuits, or make verification decisions.
"""
from __future__ import annotations

from html import escape
import json
from typing import Any, Iterable, Mapping, Optional

from .config import REFERENCE_POLICY
from .contracts import ProblemArtifact, RunResult
from .events import JourneyCardState, JourneyState
from .public_contract_views import scientific_realization_view

GUIDED_VIEW_CSS = r"""
:root {
  --qcol-bg: #f7f8fb;
  --qcol-card: #ffffff;
  --qcol-ink: #17233c;
  --qcol-muted: #667085;
  --qcol-line: #d9e0ea;
  --qcol-purple: #6547c8;
  --qcol-teal: #087f72;
  --qcol-amber: #b96b00;
  --qcol-blue: #2767b5;
  --qcol-gray: #667085;
  --qcol-green: #14804a;
  --qcol-red: #b42318;
}
.gradio-container {max-width: 1480px !important;}
.qcol-guided-shell {font-family: Inter, ui-sans-serif, system-ui, sans-serif; color: var(--qcol-ink);}
.qcol-guided-heading {display:flex; align-items:flex-end; justify-content:space-between; gap:16px; margin:2px 0 14px;}
.qcol-guided-heading h2 {margin:0; font-size:1.35rem;}
.qcol-guided-heading p {margin:3px 0 0; color:var(--qcol-muted);}
.qcol-guided-label {font-size:.75rem; letter-spacing:.06em; text-transform:uppercase; font-weight:700; color:var(--qcol-blue);}
.qcol-flow {display:grid; grid-template-columns:minmax(190px,.85fr) 34px minmax(230px,1fr) 42px minmax(560px,2.6fr) 42px minmax(225px,1fr); gap:8px; align-items:stretch;}
.qcol-arrow {display:flex; align-items:center; justify-content:center; color:#8a94a6; font-size:1.5rem; font-weight:700;}
.qcol-card, .qcol-runtime, .qcol-branch {background:var(--qcol-card); border:1px solid var(--qcol-line); border-radius:14px; box-shadow:0 4px 14px rgba(16,24,40,.05);}
.qcol-card {padding:13px 14px; min-height:118px; position:relative; overflow:hidden;}
.qcol-card::before {content:""; position:absolute; left:0; top:0; bottom:0; width:4px; background:#b5bdca;}
.qcol-card.stage-artifact::before {background:var(--qcol-purple);}
.qcol-card.stage-task::before {background:#4263b8;}
.qcol-stage-stack {display:grid; gap:8px;}
.qcol-card.stage-model::before, .qcol-card.stage-meaning::before {background:var(--qcol-blue);}
.qcol-card.stage-optimizer::before, .qcol-card.stage-convergence::before {background:var(--qcol-amber);}
.qcol-card.stage-mapping_analysis::before {background:linear-gradient(180deg,var(--qcol-purple),var(--qcol-teal));}
.qcol-card.stage-bind::before, .qcol-card.stage-measurement::before, .qcol-card.stage-translation::before, .qcol-card.stage-execute::before, .qcol-card.stage-reconstruct::before {background:var(--qcol-teal);}
.qcol-card.stage-evidence::before {background:#d39200;}
.qcol-card.stage-exact_reference::before, .qcol-card.stage-verification::before {background:var(--qcol-gray);}
.qcol-card.stage-feedback::before {background:#4d7dc4;}
.qcol-entrance-strip {margin-bottom:10px;}
.qcol-entrance-strip .qcol-card {min-height:auto;}
.qcol-card.stage-entrance::before {background:linear-gradient(180deg,var(--qcol-purple),var(--qcol-blue));}
.qcol-card.status-running {border-color:#63b7ad; box-shadow:0 0 0 2px rgba(8,127,114,.10);}
.qcol-card.status-completed {border-color:#a6d8bd;}
.qcol-card.status-review {border-color:#e8bd72; background:#fffaf1;}
.qcol-card.status-failed {border-color:#f0a7a0; background:#fff5f4;}
.qcol-card.status-blocked {border-color:#d7dce5; background:#f5f6f8; opacity:.78;}
.qcol-card-header {display:flex; align-items:center; justify-content:space-between; gap:8px; margin-bottom:8px;}
.qcol-card-title {font-weight:750; font-size:.94rem;}
.qcol-status {font-size:.68rem; font-weight:750; border-radius:999px; padding:3px 8px; text-transform:uppercase; letter-spacing:.04em; background:#eef1f5; color:#596579; white-space:nowrap;}
.status-running .qcol-status {background:#e1f5f1; color:#087f72;}
.status-completed .qcol-status {background:#e9f7ef; color:#14804a;}
.status-review .qcol-status {background:#fff0cc; color:#985900;}
.status-failed .qcol-status {background:#fee4e2; color:#b42318;}
.status-blocked .qcol-status {background:#e8ebf0; color:#667085;}
.qcol-message {font-size:.82rem; line-height:1.42; color:#344054; min-height:35px;}
.qcol-metrics {margin-top:8px; font-size:.74rem; color:#5d6677; display:grid; gap:3px;}
.qcol-metric {display:flex; justify-content:space-between; gap:8px; border-top:1px dashed #e3e7ee; padding-top:3px;}
.qcol-metric strong {color:#27364e; text-align:right; font-weight:650; overflow-wrap:anywhere;}
.qcol-lenses {display:flex; flex-wrap:wrap; gap:4px; margin-top:9px;}
.qcol-lens {font-size:.62rem; border:1px solid #d6ddea; border-radius:999px; padding:2px 6px; color:#526079; background:#f8fafc;}
.qcol-progress {height:5px; border-radius:999px; background:#e8edf3; overflow:hidden; margin-top:8px;}
.qcol-progress > span {display:block; height:100%; background:linear-gradient(90deg,#168c7e,#58c0a7);}
.qcol-failure-summary {border:1px solid #f0a7a0; border-left:5px solid var(--qcol-red); background:#fff5f4; color:#7a271a; border-radius:11px; padding:10px 12px; margin:0 0 12px; font-size:.8rem; line-height:1.45;}
.qcol-failure-detail {margin-top:9px; border-top:1px solid #f2cbc7; padding-top:8px; display:grid; gap:5px;}
.qcol-failure-code {font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:.68rem; color:#912018;}
.qcol-failure-action {font-size:.75rem; color:#7a271a; background:#fff; border:1px solid #f1d3cf; border-radius:8px; padding:6px 8px;}
.qcol-technical-note {font-size:.68rem; color:#8d3b34;}
.qcol-runtime {padding:12px; border-color:#a7d8cf; background:linear-gradient(180deg,#f9fffd,#ffffff);}
.qcol-runtime-title {display:flex; justify-content:space-between; align-items:center; margin-bottom:9px; font-weight:750; color:#07695f;}
.qcol-runtime-grid {display:grid; grid-template-columns:repeat(3,minmax(150px,1fr)); gap:8px;}
.qcol-runtime .qcol-card {min-height:122px; box-shadow:none;}
.qcol-runtime-footer {display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-top:8px;}
.qcol-mapping-shell {padding:12px; border:1px solid #9fcfc5; border-radius:14px; background:linear-gradient(135deg,#f8fffd,#faf8ff); box-shadow:0 4px 14px rgba(16,24,40,.05);}
.qcol-mapping-grid {display:grid; grid-template-columns:minmax(250px,1fr) minmax(250px,1fr); gap:10px;}
.qcol-mapping-note {margin-top:9px; border:1px solid #d7d0f1; background:#f7f5ff; border-radius:9px; padding:8px 10px; color:#544587; font-size:.74rem;}
.qcol-branch {display:grid; gap:10px; padding:10px; background:#fbfcfe;}
.qcol-branch .qcol-card {min-height:104px; box-shadow:none;}
.qcol-evidence-panel, .qcol-return-panel, .qcol-feedback-panel {background:#fff; border:1px solid var(--qcol-line); border-radius:14px; padding:14px; box-shadow:0 4px 14px rgba(16,24,40,.05);}
.qcol-panel-title {display:flex; align-items:center; justify-content:space-between; gap:10px; margin-bottom:10px; font-weight:750;}
.qcol-panel-sub {font-size:.79rem; color:var(--qcol-muted); margin-top:-5px; margin-bottom:10px;}
.qcol-kpis {display:grid; grid-template-columns:repeat(2,minmax(120px,1fr)); gap:8px;}
.qcol-kpi {border:1px solid #e1e6ee; border-radius:10px; padding:10px; background:#fbfcfe;}
.qcol-kpi small {display:block; color:#667085; font-size:.68rem; margin-bottom:3px;}
.qcol-kpi strong {font-size:1rem; color:#24344f;}
.qcol-table {width:100%; border-collapse:collapse; font-size:.76rem;}
.qcol-table th, .qcol-table td {border-bottom:1px solid #e5e9f0; padding:6px 7px; text-align:left;}
.qcol-table th {color:#546176; font-weight:650; background:#fafbfc;}
.qcol-feedback-panel {border-color:#c8d8ef; background:#f8fbff;}
.qcol-feedback-indicator {display:inline-flex; align-items:center; gap:6px; border-radius:999px; padding:4px 9px; background:#eaf2ff; color:#2767b5; font-size:.72rem; font-weight:700;}
.qcol-advisor-grid {display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:10px;margin-top:10px;}
.qcol-advisor-card {background:#fff;border:1px solid #c8d8ef;border-radius:12px;padding:12px;}
.qcol-advisor-card p,.qcol-advisor-card li {font-size:.78rem;color:#53657a;}
.qcol-advisor-patch {white-space:pre-wrap;background:#eef5ff;border:1px solid #c8d8ef;padding:8px;border-radius:8px;font-size:.72rem;}
.qcol-telemetry {display:flex; flex-wrap:wrap; gap:6px; margin-top:9px;}
.qcol-telemetry span {font-size:.7rem; border-radius:7px; padding:4px 7px; background:#fff; border:1px solid #d7e3f4; color:#426084;}
.qcol-policy {font-size:.7rem; color:#7b5b22; background:#fff8e8; border:1px solid #f0d9a2; border-radius:8px; padding:6px 8px; margin-top:8px;}
.qcol-empty {color:#7b8494; font-size:.82rem; font-style:italic;}
.qcol-section-heading {display:flex; align-items:center; gap:12px; margin:6px 0 14px; padding:12px 14px; border:1px solid #cfd8e6; border-radius:13px; background:linear-gradient(90deg,#f4f7fc,#ffffff); color:#203250;}
.qcol-section-heading > span {display:grid; place-items:center; width:34px; height:34px; border-radius:10px; color:white; background:var(--qcol-purple); font-size:1rem; font-weight:800; flex:0 0 auto;}
.qcol-section-heading.journey > span {background:var(--qcol-teal);}
.qcol-section-heading strong {display:block; font-size:1.03rem;}
.qcol-section-heading small {display:block; color:var(--qcol-muted); margin-top:2px; line-height:1.35;}
.qcol-no-code-note {border-left:4px solid var(--qcol-blue); background:#f3f8ff; color:#344e73; padding:10px 12px; border-radius:0 10px 10px 0; margin:8px 0 14px; font-size:.84rem;}
#physics-modelling-entrance {border:1px solid #d6dfeb; border-radius:16px; padding:14px !important; background:linear-gradient(180deg,#fbfcff,#ffffff); box-shadow:0 5px 18px rgba(16,24,40,.05);}
#model-family-cards .wrap {display:grid !important; grid-template-columns:repeat(3,minmax(0,1fr)); gap:10px !important;}
#model-family-cards label {min-height:76px; border:1px solid #d6deea !important; border-radius:12px !important; padding:13px 14px !important; background:#ffffff !important; align-items:flex-start !important; box-shadow:0 2px 8px rgba(16,24,40,.04); transition:.18s ease;}
#model-family-cards label:hover {border-color:#9cb3d4 !important; transform:translateY(-1px); box-shadow:0 5px 14px rgba(16,24,40,.08);}
#model-family-cards label:has(input:checked) {border-color:var(--qcol-purple) !important; background:#f5f2ff !important; box-shadow:0 0 0 2px rgba(101,71,200,.10);}
#model-family-cards label span {font-weight:700 !important; color:#24344f !important; line-height:1.3 !important;}
@media (max-width:1200px) {
  #model-family-cards .wrap {grid-template-columns:repeat(2,minmax(0,1fr)) !important;}
  .qcol-flow {grid-template-columns:1fr;}
  .qcol-arrow {transform:rotate(90deg); min-height:24px;}
  .qcol-runtime-grid {grid-template-columns:repeat(2,minmax(150px,1fr));}
}
@media (max-width:700px) {
  .qcol-runtime-grid, .qcol-runtime-footer, .qcol-kpis {grid-template-columns:1fr;}
  #model-family-cards .wrap {grid-template-columns:1fr !important;}
}
.qcol-card {cursor:pointer; transition:transform .16s ease, box-shadow .16s ease;}
.qcol-card:hover {transform:translateY(-1px); box-shadow:0 7px 18px rgba(16,24,40,.09);}

/* UI R5 — independent architectural rectangles instead of nested dashboard boxes. */
.qcol-architectural-sequence {display:flex; align-items:stretch; gap:8px; overflow-x:auto; padding:2px 1px 8px;}
.qcol-architectural-sequence > .qcol-card {flex:1 0 205px; min-height:116px;}
.qcol-connector {display:grid; place-items:center; color:#8a94a6; font-size:1.25rem; flex:0 0 24px;}
.qcol-map-label {display:flex; justify-content:space-between; align-items:baseline; gap:12px; border-bottom:1px solid #dfe5ee; padding-bottom:6px; margin:4px 0 8px;}
.qcol-map-label strong {font-size:.77rem; text-transform:uppercase; letter-spacing:.05em; color:var(--qcol-purple);}
.qcol-map-label small {color:var(--qcol-muted); text-align:right;}
.qcol-task-map {display:grid; grid-template-columns:minmax(0,1fr) minmax(230px,.28fr); gap:14px; align-items:start; margin-top:12px;}
.qcol-vqe-loop-map {position:relative; border:1px solid #e5c181; background:#fffdf8; border-radius:16px; padding:42px 18px 54px 52px;}
.qcol-vqe-loop-map::before {content:""; position:absolute; left:17px; top:31px; right:8px; bottom:27px; border:2px solid rgba(185,107,0,.62); border-right:0; border-radius:22px 0 0 22px;}
.qcol-loop-caption {position:absolute; top:8px; left:10px; color:var(--qcol-amber); border:1px solid #e2bd77; background:#fff8e8; border-radius:999px; padding:3px 8px; font-size:.66rem; font-weight:750; text-transform:uppercase;}
.qcol-loop-return {position:absolute; left:2px; bottom:16px; color:var(--qcol-amber); font-size:.68rem;}
.qcol-loop-exit {position:absolute; right:10px; bottom:7px; color:#896527; font-size:.66rem;}
.qcol-optimizer-row, .qcol-convergence-row {display:flex; justify-content:center;}
.qcol-optimizer-row > .qcol-card, .qcol-convergence-row > .qcol-card {width:min(390px,100%);}
.qcol-down {height:26px; display:grid; place-items:center; color:#8a94a6;}
.qcol-verification-lane {position:relative; display:grid; gap:9px; padding-left:25px;}
.qcol-verification-lane::before {content:""; position:absolute; left:6px; top:42px; bottom:18px; width:2px; background:linear-gradient(#7c8591,#c0c5cc);}
.qcol-branch-head {border:1px solid #bbc2cb; background:#f4f5f7; border-radius:10px; padding:8px 9px; color:#5d6673; font-size:.72rem;}
.qcol-branch-arrow {height:16px; display:grid; place-items:center; color:#7b8491;}
.qcol-verification-lane .qcol-card {background:#f8f9fb; border-color:#b7bec8;}
.qcol-mapping-map {border:1px solid #b6d9d1; background:linear-gradient(145deg,#fbfffe,#fbf9ff); border-radius:16px; padding:14px;}
.qcol-mapping-lanes {display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px; margin:9px 0;}
.qcol-mapping-lane {border:1px solid #d5dde8; border-radius:12px; padding:11px; min-height:118px;}
.qcol-mapping-lane.jw {background:#eefbf7; border-color:#8bc8b8;}
.qcol-mapping-lane.bk {background:#f5f2ff; border-color:#b6a9ed;}
.qcol-mapping-lane strong {display:block; margin-bottom:6px;}
.qcol-mapping-lane p {color:var(--qcol-muted); font-size:.75rem; line-height:1.4;}
.qcol-split-label, .qcol-merge-label {text-align:center; color:#667085; font-size:.68rem; margin:7px 0;}
.qcol-analysis-boundary {margin-top:9px; border:1px solid #e2bd77; background:#fff8e8; border-radius:9px; padding:8px 10px; color:#7b5b22; font-size:.72rem;}
.qcol-card-details {margin-top:auto; border-top:1px dashed #e0e5ed; padding-top:6px;}
.qcol-card-details summary {cursor:pointer; color:#617087; font-size:.68rem; font-weight:700;}
.qcol-card-details[open] summary {margin-bottom:5px;}
@media (max-width:1200px) {
  .qcol-task-map {grid-template-columns:1fr;}
  .qcol-verification-lane {grid-template-columns:repeat(3,minmax(0,1fr)); padding:20px 0 0;}
  .qcol-verification-lane::before {left:8%; right:8%; top:7px; bottom:auto; width:auto; height:2px;}
  .qcol-branch-head {grid-column:1/-1;}
  .qcol-branch-arrow {display:none;}
}
@media (max-width:700px) {
  .qcol-architectural-sequence {flex-direction:column; overflow:visible;}
  .qcol-connector {transform:rotate(90deg); min-height:22px;}
  .qcol-mapping-lanes {grid-template-columns:1fr;}
  .qcol-verification-lane {grid-template-columns:1fr;}
  .qcol-verification-lane::before {left:6px; top:42px; bottom:8px; width:2px; height:auto;}
  .qcol-branch-head {grid-column:auto;}
  .qcol-branch-arrow {display:grid;}
}
"""


def _fmt(value: Any, *, max_len: int = 80) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.7g}"
    if isinstance(value, (dict, list, tuple)):
        text = json.dumps(value, ensure_ascii=False, default=str)
    else:
        text = str(value)
    if len(text) > max_len:
        text = text[: max_len - 1] + "…"
    return text


def _status_label(status: str) -> str:
    return {
        "waiting": "waiting",
        "running": "running",
        "completed": "completed",
        "review": "review",
        "failed": "failed",
        "blocked": "not reached",
    }.get(status, status)


def _metric_items(card: JourneyCardState) -> Iterable[tuple[str, Any]]:
    preferred = {
        "model": ("method", "problem", "energy_unit"),
        "artifact": ("n_qubits", "pauli_terms", "mapping", "mapping_policy_id", "measurement_groups"),
        "task": ("task_id", "controller_structure", "controller_policy", "objective"),
        "optimizer": ("evaluation", "energy", "best_energy", "evaluations"),
        "bind": ("parameter_count", "role"),
        "measurement": ("group_count", "terms_in_group", "basis"),
        "translation": ("validated", "depth_after_unroll", "validated_groups"),
        "execute": ("shots_per_group", "total_shots_so_far", "execution_mode"),
        "evidence": ("groups_summarized", "total_shots", "full_artifacts_retained"),
        "reconstruct": ("energy", "standard_error", "term_expectation_count"),
        "convergence": ("converged", "energy_tolerance", "optimizer_evaluations"),
        "exact_reference": ("reference_energy", "reference_scope", "reference_policy"),
        "verification": ("verification_status", "absolute_error", "acceptance_threshold"),
        "meaning": ("energy", "standard_error", "unit"),
        "feedback": ("enabled", "phase"),
    }.get(card.stage, ())
    yielded = set()
    for key in preferred:
        if key in card.metrics:
            yielded.add(key)
            yield key.replace("_", " "), card.metrics[key]
    for key, value in card.metrics.items():
        if key in yielded or key in {"theta_preview", "top_counts", "limitations", "telemetry_available"}:
            continue
        yield key.replace("_", " "), value
        if len(yielded) >= 4:
            break


def _card_html(card: JourneyCardState) -> str:
    metric_rows = "".join(
        f'<div class="qcol-metric"><span>{escape(label)}</span><strong>{escape(_fmt(value))}</strong></div>'
        for label, value in list(_metric_items(card))[:4]
    )
    lenses = "".join(
        f'<span class="qcol-lens">{escape(lens)}</span>' for lens in card.lenses
    )
    progress = ""
    if card.progress_fraction is not None:
        percent = round(card.progress_fraction * 100, 1)
        progress = f'<div class="qcol-progress" title="{percent}%"><span style="width:{percent}%"></span></div>'
    iteration = f" · iter {card.iteration}" if card.iteration else ""
    failure_html = ""
    if card.failure:
        failure = card.failure
        action = failure.get("suggested_action")
        failure_html = (
            '<div class="qcol-failure-detail">'
            f'<div class="qcol-failure-code">{escape(str(failure.get("error_code", "pipeline_failure")))}</div>'
            + (f'<div class="qcol-failure-action"><strong>Suggested correction:</strong> {escape(str(action))}</div>' if action else "")
            + '<div class="qcol-technical-note">Technical details are retained in the error log and interrupted evidence bundle.</div>'
            + '</div>'
        )
    details = ""
    if metric_rows or lenses or progress:
        details = (
            '<details class="qcol-card-details"><summary>Inspect details</summary>'
            f'{progress}<div class="qcol-metrics">{metric_rows}</div><div class="qcol-lenses">{lenses}</div>'
            '</details>'
        )
    return f"""
    <div class="qcol-card stage-{escape(card.stage)} status-{escape(card.status)}">
      <div class="qcol-card-header">
        <span class="qcol-card-title">{escape(card.title)}{iteration}</span>
        <span class="qcol-status">{escape(_status_label(card.status))}</span>
      </div>
      <div class="qcol-message">{escape(card.message)}</div>
      {failure_html}
      {details}
    </div>
    """


def _is_mapping_analysis(state: JourneyState) -> bool:
    task_metrics = state.cards.get("task").metrics if state.cards.get("task") else {}
    return str(task_metrics.get("task_id", "")) == "mapping_analysis"


def _render_mapping_journey_html(state: JourneyState, failure_summary: str) -> str:
    c = state.cards
    foundation = '<div class="qcol-connector">→</div>'.join(
        _card_html(c[stage]) for stage in ("entrance", "model", "artifact", "task")
    )
    mapping_outputs = '<div class="qcol-connector">→</div>'.join(
        _card_html(c[stage]) for stage in ("evidence", "reconstruct")
    )
    return f"""
    <div class="qcol-guided-shell">
      <div class="qcol-guided-heading">
        <div><div class="qcol-guided-label">Physicist-first Guided View · analysis only</div><h2>QCOL Fermion-to-Qubit Mapping Explorer</h2><p>One declared FermionOperator splits through JW and BK, then recombines as a verified MappingComparisonReport.</p></div>
        <div class="qcol-status">run {escape(state.run_id)}</div>
      </div>
      {failure_summary}
      <div class="qcol-map-label"><strong>Declared model and task</strong><small>Every handoff is an independent, inspectable station.</small></div>
      <div class="qcol-architectural-sequence">{foundation}</div>
      <div class="qcol-task-map">
        <div class="qcol-mapping-map">
          <div class="qcol-map-label"><strong>Analysis-only transformation path</strong><small>same operator · same ordering · same particle sector</small></div>
          {_card_html(c['mapping_analysis'])}
          <div class="qcol-split-label">↓ split into eligible mapping plugins ↓</div>
          <div class="qcol-mapping-lanes">
            <article class="qcol-mapping-lane jw"><strong>Jordan–Wigner</strong><p>Direct mode-to-qubit occupation semantics. Transformation, particle-number interpretation, spectra, and operator resources are verified for analysis.</p></article>
            <article class="qcol-mapping-lane bk"><strong>Bravyi–Kitaev</strong><p>GF(2) occupation code. Transformation, decoding semantics, spectra, and operator resources are verified for analysis.</p></article>
          </div>
          <div class="qcol-merge-label">↑ recombine as one MappingComparisonReport ↑</div>
          <div class="qcol-architectural-sequence">{mapping_outputs}</div>
          <div class="qcol-analysis-boundary">No circuit, optimizer, shots, QASM circuit execution, simulator, hardware submission, or VQE claim occurs in this task.</div>
        </div>
        <aside class="qcol-verification-lane">
          <div class="qcol-branch-head">Independent gray branch · exact Fermionic full-space and fixed-particle spectra</div>
          {_card_html(c['exact_reference'])}<div class="qcol-branch-arrow">↓</div>{_card_html(c['verification'])}<div class="qcol-branch-arrow">↓</div>{_card_html(c['meaning'])}
        </aside>
      </div>
    </div>
    """


def render_journey_html(state: JourneyState) -> str:
    """Render the task-aware journey as an architectural map of independent stations."""
    c = state.cards
    failure_summary = ""
    if state.failure is not None:
        action = state.failure.suggested_action or ""
        failure_summary = (
            '<div class="qcol-failure-summary">'
            f'<strong>{escape(state.global_summary or "Run stopped.")}</strong><br>{escape(state.failure.user_message)}'
            + (f'<br><span>{escape(action)}</span>' if action else "") + '</div>'
        )
    if _is_mapping_analysis(state):
        return _render_mapping_journey_html(state, failure_summary)
    foundation = '<div class="qcol-connector">→</div>'.join(
        _card_html(c[stage]) for stage in ("entrance", "model", "artifact", "task")
    )
    runtime = '<div class="qcol-connector">→</div>'.join(
        _card_html(c[stage]) for stage in ("bind", "measurement", "translation", "execute", "evidence", "reconstruct")
    )
    return f"""
    <div class="qcol-guided-shell">
      <div class="qcol-guided-heading">
        <div><div class="qcol-guided-label">Physicist-first Guided View</div><h2>QCOL Scientific Modelling Journey</h2><p>Read the workflow as connected handoffs: declaration, quantum execution, retained evidence, independent verification, and bounded meaning.</p></div>
        <div class="qcol-status">run {escape(state.run_id)}</div>
      </div>
      {failure_summary}
      <div class="qcol-map-label"><strong>Declared model and task</strong><small>One source enters the workflow; each transition is inspectable.</small></div>
      <div class="qcol-architectural-sequence">{foundation}</div>
      <div class="qcol-task-map">
        <div>
          <div class="qcol-map-label"><strong>External variational runtime</strong><small>current iteration {state.current_iteration or '—'}</small></div>
          <div class="qcol-vqe-loop-map">
            <div class="qcol-loop-caption">classical controller loop</div>
            <div class="qcol-optimizer-row">{_card_html(c['optimizer'])}</div>
            <div class="qcol-down">↓</div>
            <div class="qcol-architectural-sequence">{runtime}</div>
            <div class="qcol-down">↓</div>
            <div class="qcol-convergence-row">{_card_html(c['convergence'])}</div>
            <div class="qcol-loop-return">no · new θ ↺</div>
            <div class="qcol-loop-exit">yes · best/final estimate → verification</div>
          </div>
        </div>
        <aside class="qcol-verification-lane">
          <div class="qcol-branch-head">Independent gray branch · reference, verification, and physical meaning remain distinct from reconstruction.</div>
          {_card_html(c['exact_reference'])}<div class="qcol-branch-arrow">↓</div>{_card_html(c['verification'])}<div class="qcol-branch-arrow">↓</div>{_card_html(c['meaning'])}
          <div class="qcol-policy">Exact-reference production policy: <strong>{escape(state.reference_policy.replace('_',' '))}</strong>.</div>
        </aside>
      </div>
    </div>
    """


def _latest_energy(state: JourneyState) -> tuple[Optional[float], Optional[float]]:
    if not state.energy_history:
        return None, None
    item = state.energy_history[-1]
    energy = item.get("energy")
    error = item.get("standard_error")
    return (
        None if energy is None else float(energy),
        None if error is None else float(error),
    )


def render_physical_return_html(
    state: JourneyState,
    artifact: Optional[ProblemArtifact] = None,
    result: Optional[RunResult] = None,
) -> str:
    """Render the task result without assuming that every task returns energy."""
    unit = "unspecified" if artifact is None else artifact.units.get("energy", "unspecified")
    verification = state.cards["verification"].metrics
    status = str(verification.get("verification_status", state.verification_status))
    meaning = state.physical_summary

    if result is not None:
        verification = result.verification
        status = result.status
        meaning = result.meaning

    statement = (
        meaning.get("supported_statement")
        or meaning.get("scientific_quantity")
        or "The physical statement appears after verification."
    )

    if result is not None and result.task_id == "mapping_analysis":
        task_result = result.task_result or {}
        entries = list(task_result.get("entries", []))
        rows = []
        for item in entries:
            mapped = item.get("mapped_artifact", {})
            resources = mapped.get("resource_report", {})
            capability = mapped.get("capability_report", {})
            mapping_label = str(item.get("mapping_id", "mapping")).replace(".v1", "")
            rows.append(
                "<tr>"
                f"<td><strong>{escape(mapping_label)}</strong></td>"
                f"<td>{escape(_fmt(resources.get('n_qubits')))}</td>"
                f"<td>{escape(_fmt(resources.get('pauli_term_count')))}</td>"
                f"<td>{escape(_fmt(resources.get('maximum_pauli_weight')))}</td>"
                f"<td>{escape(_fmt(resources.get('coefficient_weighted_mean_pauli_weight')))}</td>"
                f"<td>{escape(_fmt(resources.get('qwc_measurement_group_count')))}</td>"
                f"<td>{escape(_fmt(capability.get('support_by_task', {}).get('ground_state_energy')))}</td>"
                "</tr>"
            )
        table = (
            '<table class="qcol-table"><thead><tr><th>Mapping</th><th>Qubits</th><th>Pauli terms</th><th>Max weight</th><th>Weighted mean</th><th>QWC groups</th><th>Ground-state support</th></tr></thead><tbody>'
            + "".join(rows) + "</tbody></table>"
            if rows else '<div class="qcol-empty">No mapping comparison is available yet.</div>'
        )
        recommended = task_result.get("recommended_for_analysis")
        all_verified = task_result.get("all_transforms_verified")
        return f"""
        <div class="qcol-return-panel">
          <div class="qcol-panel-title"><span>Mapping comparison return</span><span class="qcol-status">{escape(str(status))}</span></div>
          <div class="qcol-panel-sub">The same FermionOperator and mode ordering were transformed through Jordan–Wigner and Bravyi–Kitaev. This is an operator-analysis result, not a VQE recommendation.</div>
          {table}
          <div class="qcol-kpis" style="margin-top:10px">
            <div class="qcol-kpi"><small>All transforms verified</small><strong>{escape(_fmt(all_verified))}</strong></div>
            <div class="qcol-kpi"><small>Analysis-only resource ranking</small><strong>{escape(_fmt(recommended))}</strong></div>
          </div>
          <div style="margin-top:12px"><strong>Bounded meaning</strong><div class="qcol-message" style="margin-top:5px">{escape(str(statement))}</div></div>
          <div class="qcol-policy">JW and BK are acceptance-verified here for transformation, spectra, particle-number semantics, and operator-resource analysis only. Full ground-state execution remains a separate Model × Task × Mapping acceptance claim.</div>
        </div>
        """

    if result is not None and result.task_id == "observable_estimation":
        task_result = result.task_result or {}
        occupations = list(task_result.get("occupations") or [])
        errors = list(task_result.get("occupation_standard_errors") or [])
        reference = task_result.get("reference_occupations")
        maximum_error = verification.get("maximum_absolute_error")
        threshold = verification.get("observable_acceptance_threshold", verification.get("acceptance_threshold"))
        leakage = task_result.get("sector_leakage")
        leakage_error = task_result.get("sector_leakage_standard_error")
        leakage_threshold = verification.get("sector_leakage_threshold")

        rows = []
        for index, value in enumerate(occupations):
            stderr = errors[index] if index < len(errors) else None
            ref = reference[index] if isinstance(reference, (list, tuple)) and index < len(reference) else None
            rows.append(
                "<tr>"
                f"<td>level {index}</td>"
                f"<td>{escape(_fmt(value))}</td>"
                f"<td>{escape(_fmt(stderr))}</td>"
                f"<td>{escape(_fmt(ref))}</td>"
                "</tr>"
            )
        table = (
            '<table class="qcol-table"><thead><tr><th>Pair occupation</th><th>Measured</th><th>Std. error</th><th>Classical reference</th></tr></thead><tbody>'
            + "".join(rows)
            + "</tbody></table>"
            if rows
            else '<div class="qcol-empty">No observable result is available yet.</div>'
        )
        leakage_text = "—" if leakage is None else _fmt(leakage)
        if leakage_error is not None:
            leakage_text += f" ± {_fmt(leakage_error)}"
        return f"""
        <div class="qcol-return-panel">
          <div class="qcol-panel-title"><span>Physical return — pair occupations</span><span class="qcol-status">{escape(str(status))}</span></div>
          <div class="qcol-panel-sub">A single-pass task returns measured pair occupations and sector diagnostics; no optimizer-convergence claim applies.</div>
          {table}
          <div class="qcol-kpis" style="margin-top:10px">
            <div class="qcol-kpi"><small>Maximum occupation error</small><strong>{escape(_fmt(maximum_error))}</strong></div>
            <div class="qcol-kpi"><small>Occupation threshold</small><strong>{escape(_fmt(threshold))}</strong></div>
            <div class="qcol-kpi"><small>Measured sector leakage</small><strong>{escape(leakage_text)}</strong></div>
            <div class="qcol-kpi"><small>Leakage threshold</small><strong>{escape(_fmt(leakage_threshold))}</strong></div>
          </div>
          <div style="margin-top:12px"><strong>Bounded physical meaning</strong><div class="qcol-message" style="margin-top:5px">{escape(str(statement))}</div></div>
          <div class="qcol-policy">The acceptance fixture may be exact-derived and is labelled in the evidence. Reference occupations are classical; measured occupations come from this run's counts.</div>
        </div>
        """

    energy, standard_error = _latest_energy(state)
    reference = state.exact_reference_energy
    if result is not None:
        energy = result.reconstructed_energy
        standard_error = result.standard_error
        reference = result.verification.get("reference_energy")
    estimate_text = "—" if energy is None else f"{energy:.7g} {escape(unit)}"
    uncertainty_text = "—" if standard_error is None else f"± {standard_error:.3g} {escape(unit)}"
    ref_text = "unavailable" if reference is None else f"{float(reference):.7g} {escape(unit)}"
    error = verification.get("absolute_error")
    threshold = verification.get("acceptance_threshold")
    return f"""
    <div class="qcol-return-panel">
      <div class="qcol-panel-title"><span>Physical return — energy</span><span class="qcol-status">{escape(str(status))}</span></div>
      <div class="qcol-panel-sub">The quantum workflow returns an estimate, evidence conditions, and a bounded statement—not only a number.</div>
      <div class="qcol-kpis">
        <div class="qcol-kpi"><small>Reconstructed estimate</small><strong>{estimate_text}</strong><div>{uncertainty_text}</div></div>
        <div class="qcol-kpi"><small>Exact / sector reference</small><strong>{ref_text}</strong></div>
        <div class="qcol-kpi"><small>Absolute error</small><strong>{escape(_fmt(error))}</strong></div>
        <div class="qcol-kpi"><small>Acceptance threshold</small><strong>{escape(_fmt(threshold))}</strong></div>
      </div>
      <div style="margin-top:12px"><strong>Bounded physical meaning</strong><div class="qcol-message" style="margin-top:5px">{escape(str(statement))}</div></div>
      <div class="qcol-policy">Reference policy for larger production problems remains a mentor decision. Small acceptance cases continue to expose their declared reference when available.</div>
    </div>
    """


def render_evidence_html(state: JourneyState, result: Optional[RunResult] = None) -> str:
    if result is not None and result.task_id == "mapping_analysis":
        entries = list((result.task_result or {}).get("entries", []))
        rows = []
        for item in entries:
            resources = item.get("mapped_artifact", {}).get("resource_report", {})
            rows.append(
                "<tr>"
                f"<td>{escape(str(item.get('mapping_id', '—')))}</td>"
                f"<td>{escape(_fmt(item.get('transform_verified')))}</td>"
                f"<td>{escape(_fmt(item.get('full_spectrum_max_abs_error')))}</td>"
                f"<td>{escape(_fmt(item.get('target_sector_spectrum_max_abs_error')))}</td>"
                f"<td>{escape(_fmt(resources.get('pauli_term_count')))}</td>"
                "</tr>"
            )
        table = '<table class="qcol-table"><thead><tr><th>Mapping</th><th>Verified</th><th>Full-spectrum error</th><th>Sector error</th><th>Pauli terms</th></tr></thead><tbody>' + "".join(rows) + '</tbody></table>'
        evidence_card = state.cards["evidence"]
        return f"""
        <div class="qcol-evidence-panel">
          <div class="qcol-panel-title"><span>Mapping-analysis evidence</span><span class="qcol-status">{escape(evidence_card.status)}</span></div>
          <div class="qcol-panel-sub">The bundle retains the standardized spin-orbital contract, FermionOperator provenance, mapped JW/BK operators, compatibility/capability reports, exact spectra, and comparable resource metrics.</div>
          {table}
          <div class="qcol-telemetry"><span>backend: not invoked</span><span>shots: not applicable</span><span>QASM2: not applicable</span><span>provenance: retained</span></div>
        </div>
        """
    rows = []
    history = result.convergence_history if result is not None else state.energy_history
    for item in history[-10:]:
        rows.append(
            "<tr>"
            f"<td>{escape(_fmt(item.get('evaluation', item.get('iteration'))))}</td>"
            f"<td>{escape(_fmt(item.get('role')))}</td>"
            f"<td>{escape(_fmt(item.get('energy')))}</td>"
            f"<td>{escape(_fmt(item.get('standard_error')))}</td>"
            f"<td>{escape(_fmt(item.get('best_energy')))}</td>"
            "</tr>"
        )
    table = (
        '<table class="qcol-table"><thead><tr><th>Evaluation</th><th>Role</th><th>Energy</th><th>Std. error</th><th>Best</th></tr></thead><tbody>'
        + "".join(rows)
        + "</tbody></table>"
        if rows
        else '<div class="qcol-empty">Iteration evidence summaries will appear here during the run.</div>'
    )
    evidence_card = state.cards["evidence"]
    retained = evidence_card.metrics.get("full_artifacts_retained")
    return f"""
    <div class="qcol-evidence-panel">
      <div class="qcol-panel-title"><span>Evidence — visible station</span><span class="qcol-status">{escape(evidence_card.status)}</span></div>
      <div class="qcol-panel-sub">Compact summaries are retained for every iteration; full QASM2, counts, and translation artifacts are retained for the best/final point.</div>
      {table}
      <div class="qcol-telemetry">
        <span>groups: {escape(_fmt(evidence_card.metrics.get('group_count')))}</span>
        <span>shots: {escape(_fmt(evidence_card.metrics.get('total_shots')))}</span>
        <span>full artifacts now: {escape(_fmt(retained))}</span>
        <span>provenance: request · seeds · versions · events</span>
      </div>
    </div>
    """


def render_feedback_html(state: JourneyState, advisor_report: Optional[Mapping[str, Any]] = None) -> str:
    """Render Phase B cards without changing the scientific journey."""
    if not advisor_report:
        telemetry = state.cards["feedback"].metrics.get("telemetry_available", [])
        chips = "".join(f"<span>✓ {escape(str(item).replace('_',' '))}</span>" for item in telemetry)
        return f"""
        <div class="qcol-feedback-panel">
          <div class="qcol-panel-title"><span>Return arrow / deterministic design feedback</span><span class="qcol-feedback-indicator">↩ waiting</span></div>
          <div class="qcol-panel-sub">The deterministic Advisor runs only after a completed public run snapshot. QCOL remains fully functional when it is disabled.</div>
          <div class="qcol-telemetry">{chips or '<span>Telemetry appears after execution</span>'}</div>
        </div>
        """
    cards = advisor_report.get("cards", []) if isinstance(advisor_report, Mapping) else []
    rendered = []
    for card in cards:
        refs = card.get("evidence_refs", []) if isinstance(card, Mapping) else []
        ref_html = "".join(
            f"<li><code>{escape(str(ref.get('source')))} {escape(str(ref.get('path')))}</code> = {escape(_fmt(ref.get('observed_value')))}</li>"
            for ref in refs if isinstance(ref, Mapping)
        )
        patch = card.get("proposed_patch") if isinstance(card, Mapping) else None
        patch_html = (
            '<pre class="qcol-advisor-patch">' + escape(str(patch)) + '</pre>'
            '<div class="qcol-panel-sub">Hypothesis only · user approval · resolver rerun · same pipeline · new Evidence.</div>'
            if patch else ''
        )
        rendered.append(f"""
        <article class="qcol-advisor-card">
          <div class="qcol-panel-title"><span>{escape(str(card.get('title', 'Recommendation')))}</span><span class="qcol-feedback-indicator">{escape(str(card.get('epistemic_status', 'grounded')))}</span></div>
          <strong>{escape(str(card.get('summary', '')))}</strong>
          <p>{escape(str(card.get('explanation', '')))}</p>
          <ul>{ref_html}</ul>
          {patch_html}
        </article>
        """)
    return f"""
    <div class="qcol-feedback-panel">
      <div class="qcol-panel-title"><span>Return arrow / deterministic design feedback</span><span class="qcol-feedback-indicator">↩ {len(cards)} grounded card(s)</span></div>
      <div class="qcol-panel-sub">Rules read sanitized CompatibilityReport, acceptance fingerprint, ResourceReport, stable failure codes, and the governed patch allowlist. Verification remains final authority.</div>
      <div class="qcol-advisor-grid">{''.join(rendered)}</div>
    </div>
    """


def _sector_text(sector: Any) -> str:
    if not sector:
        return "No conserved sector declared"
    keys = ("particle_number", "pair_number", "seniority", "excitation_number")
    bits = [f"{key.replace('_',' ')} = {sector[key]}" for key in keys if key in sector]
    return " · ".join(bits) if bits else str(sector)


def boundary_contract_markdown(artifact: Optional[ProblemArtifact]) -> str:
    """Inspect the resolved contract through the frozen public view."""
    if artifact is None:
        return "_Build a problem to inspect its shared computational contract._"
    terms = sorted(artifact.hamiltonian_payload.terms.items(), key=lambda item: (len(item[0]), str(item[0])))
    shown = []
    for term, coefficient in terms[:12]:
        label = "I" if not term else " ".join(f"{pauli}{index}" for index, pauli in term)
        shown.append(f"  {float(complex(coefficient).real):+.6f}  {label}")
    more = "" if len(terms) <= 12 else f"\n  … {len(terms)-12} more terms"
    exact = "available" if artifact.exact_reference is not None else "not declared"
    view = scientific_realization_view(artifact).to_dict()
    entry_contract = artifact.scientific_context.get("problem_contract", {})
    entry_line = ""
    if isinstance(entry_contract, dict) and entry_contract:
        entry_line = (
            f"**Legacy entry contract (provenance only):** "
            f"`{entry_contract.get('problem_id', artifact.problem)}` "
            f"(`{entry_contract.get('schema_version', '—')}`)  \n"
        )
    body = (
        "### ProblemArtifact — shared computational contract\n\n"
        f"**Canonical model / task:** `{view['model_id']}` / `{view['task_id']}`  \n"
        f"{entry_line}"
        f"**Encoding context:** `{view['encoding_context_id']}`  \n"
        f"**Mapping policy:** `{view['mapping_policy_id']}`  \n"
        f"**State / ansatz:** `{view.get('state_preparation_policy_id') or '—'}` / `{view.get('ansatz_policy_id') or '—'}`  \n"
        f"**Measurement / reference:** `{view.get('measurement_policy_id') or '—'}` / `{view.get('reference_policy_id') or '—'}`  \n"
        f"**Controller:** `{view['controller_id']}`  \n"
        f"**Scientific fingerprint:** `{view['scientific_fingerprint']}`  \n"
        f"**Hamiltonian payload:** OpenFermion `QubitOperator`, {len(terms)} terms  \n"
        f"**Target sector:** {_sector_text(view['target_sector'])}  \n"
        f"**Symmetries:** {', '.join(artifact.symmetries) or 'none declared'}  \n"
        f"**Qubits:** {artifact.n_qubits}  \n"
        f"**Parameterized ansatz:** {len(artifact.parameter_symbols)} parameter(s)  \n"
        f"**Measurement groups:** {len(artifact.measurement_plan.get('groups', []))}  \n"
        f"**Exact-reference declaration:** {exact}\n\n"
        "```text\n" + "\n".join(shown) + more + "\n```"
    )
    return body



def qasm_semantic_fidelity(result: RunResult) -> Optional[float]:
    """Return translation fidelity, explicitly not physical-state fidelity."""
    check = result.translation_check or {}
    for branch in ("unrolled_roundtrip", "raw_roundtrip", "semantic_check"):
        item = check.get(branch, {})
        if isinstance(item, Mapping):
            value = item.get("unitary_process_fidelity_up_to_global_phase")
            if value is not None:
                return float(value)
    measurement_free = check.get("measurement_free")
    if isinstance(measurement_free, Mapping):
        for branch in ("unrolled_roundtrip", "raw_roundtrip"):
            item = measurement_free.get(branch, {})
            if isinstance(item, Mapping):
                value = item.get("unitary_process_fidelity_up_to_global_phase")
                if value is not None:
                    return float(value)
    return None


def backend_status_markdown(result: RunResult) -> str:
    submitted = "yes" if result.hardware_submission_performed else "not performed"
    return (
        f"**Execution:** {result.execution_mode.replace('_', ' ')} · "
        f"**Target:** {result.target_backend.upper()} · "
        f"**Hardware submission:** {submitted}  \n"
        f"_{result.adapter_status}_"
    )


# Compatibility aliases for earlier Phase 4 integrations.
def stations_markdown(artifact: ProblemArtifact, result: RunResult) -> str:
    state = JourneyState.initial(result.run_id, reference_policy=result.reference_policy)
    for payload in result.journey_events:
        from .events import PipelineEvent
        state.apply(PipelineEvent(
            run_id=result.run_id,
            stage=str(payload["stage"]),
            status=str(payload["status"]),  # type: ignore[arg-type]
            message=str(payload["message"]),
            timestamp_utc=str(payload.get("timestamp_utc")),
            iteration=payload.get("iteration"),
            progress_current=payload.get("progress_current"),
            progress_total=payload.get("progress_total"),
            metrics=dict(payload.get("metrics", {})),
            artifact_refs=list(payload.get("artifact_refs", [])),
        ))
    return render_journey_html(state)


def interpretation_markdown(artifact: ProblemArtifact, result: RunResult) -> str:
    state = JourneyState.initial(result.run_id, reference_policy=result.reference_policy)
    return render_physical_return_html(state, artifact, result)

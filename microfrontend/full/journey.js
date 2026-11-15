function stageCard(stage) {
  return state.snapshot?.journey_state?.cards?.[stage] || {
    title: stage.replaceAll("_", " "), status: "waiting", message: "Waiting", metrics: {}, lenses: []
  };
}

const metricPreferences = {
  model: ["method", "problem", "energy_unit"],
  artifact: ["n_qubits", "pauli_terms", "mapping", "measurement_groups"],
  task: ["task_id", "controller_structure", "controller_policy", "objective"],
  optimizer: ["evaluation", "energy", "best_energy", "evaluations"],
  mapping_analysis: ["all_transforms_verified", "recommended_for_analysis", "resource_reports", "capability_reports"],
  bind: ["parameter_count", "role"],
  measurement: ["group_count", "current_group", "shots"],
  translation: ["validated_groups", "semantic_check_performed"],
  execute: ["current_group", "shots", "total_shots"],
  evidence: ["group_count", "total_shots", "full_artifacts_retained"],
  reconstruct: ["energy", "standard_error", "term_expectation_count"],
  convergence: ["converged", "delta_energy", "tolerance"],
  exact_reference: ["available", "reference_energy", "reference_scope"],
  verification: ["verification_status", "absolute_error", "acceptance_threshold"],
  meaning: ["scientific_quantity", "energy", "standard_error"],
};

function renderStage(stage) {
  const roots = [
    $(`stage-${stage}`),
    ...document.querySelectorAll(`[data-stage-alias="${stage}"]`),
  ].filter(Boolean);
  if (!roots.length) return;
  const card = stageCard(stage);
  const preferred = metricPreferences[stage] || Object.keys(card.metrics || {}).slice(0,3);
  const metrics = preferred.filter(key => card.metrics && card.metrics[key] !== undefined).slice(0,4);
  const metricsHtml = metrics.map(key => `<div class="card-metric"><span>${esc(key.replaceAll("_", " "))}</span><b>${esc(list(card.metrics[key]))}</b></div>`).join("");
  const lenses = (card.lenses || []).map(item => `<span class="lens">${esc(item)}</span>`).join("");
  const fraction = card.progress_fraction ?? ((card.progress_current && card.progress_total) ? card.progress_current / card.progress_total : null);
  const progress = fraction === null || fraction === undefined ? "" : `<div class="progress"><span style="width:${Math.max(0,Math.min(100,fraction*100))}%"></span></div>`;
  const failure = card.failure || null;
  const failureHtml = failure ? `
    <div class="station-failure">
      <code>${esc(failure.error_code || "pipeline_failure")}</code>
      ${failure.suggested_action ? `<div class="station-action"><strong>Suggested correction:</strong> ${esc(failure.suggested_action)}</div>` : ""}
      <div class="station-technical-note">Technical details are retained separately.</div>
    </div>` : "";
  const details = (metricsHtml || lenses || progress) ? `
    <details class="station-details">
      <summary>Inspect details</summary>
      <div class="card-metrics">${metricsHtml}</div>${progress}<div class="lens-row">${lenses}</div>
    </details>` : "";
  const markup = `
    <div class="card-title-line"><strong>${esc(card.title || stage)}</strong><span class="card-status">${esc(card.status === "blocked" ? "not reached" : (card.status || "waiting"))}</span></div>
    <div class="card-message">${esc(card.message || "Waiting")}</div>
    ${failureHtml}${details}`;
  roots.forEach(root => {
    root.classList.remove("status-waiting", "status-running", "status-completed", "status-review", "status-failed", "status-blocked");
    root.classList.add(`status-${card.status || "waiting"}`);
    root.innerHTML = markup;
  });
}

function renderArtifact(artifact, journey, display) {
  if (!artifact) {
    $("artifactInspector").innerHTML = `<div class="empty-state">Build a problem to inspect the shared computational contract.</div>`;
    return;
  }
  const artifactMetrics = journey?.cards?.artifact?.metrics || {};
  const scientific = display?.scientific_realization || null;
  const fields = [
    ["Artifact ID", artifact.artifact_id],
    ["Canonical model", scientific?.model_id || "—"],
    ["Canonical task", scientific?.task_id || "—"],
    ["Legacy entry", `${artifact.method || "—"} / ${artifact.problem || "—"} (provenance only)`],
    ["Encoding context", scientific?.encoding_context_id || "—"],
    ["Mapping policy", scientific?.mapping_policy_id || "—"],
    ["State preparation", scientific?.state_preparation_policy_id || "—"],
    ["Ansatz policy", scientific?.ansatz_policy_id || "—"],
    ["Measurement policy", scientific?.measurement_policy_id || "—"],
    ["Reference policy", scientific?.reference_policy_id || "—"],
    ["Controller", scientific?.controller_id || "—"],
    ["Scientific fingerprint", scientific?.scientific_fingerprint || "—"],
    ["Qubits", artifact.n_qubits ?? artifactMetrics.n_qubits],
    ["Target sector", list(scientific?.target_sector || artifact.target_sector)],
    ["Symmetries", list(artifact.symmetries)],
    ["Parameter count", artifact.parameter_names?.length ?? artifactMetrics.parameter_count],
    ["Pauli terms", artifactMetrics.pauli_terms],
    ["Measurement groups", artifact.measurement_plan?.groups?.length ?? artifactMetrics.measurement_groups],
    ["Exact reference", artifact.exact_reference ? "declared; exact state withheld from service view" : "not declared"],
  ];
  $("artifactInspector").innerHTML = `<div class="inspector-grid">${fields.map(([k,v]) => `<div class="inspector-row"><span>${esc(k)}</span><strong>${esc(list(v))}</strong></div>`).join("")}</div>`;
}


function renderJudgments(display) {
  const judgments = display?.epistemic_status || {};
  const order = ["pipeline_integrity", "qasm_semantic_preservation", "statistical_consistency", "optimizer_convergence", "scientific_acceptance"];
  $("judgmentList").innerHTML = order.map(key => {
    const item = judgments[key] || { status: "WAITING", label: key, detail: "Waiting" };
    const css = `judge-${String(item.status).toLowerCase()}`;
    return `<div class="judgment"><div class="judgment-line"><strong>${esc(item.label)}</strong><span class="${css}">${esc(item.status)}</span></div><p>${esc(item.detail)}</p></div>`;
  }).join("");
}

function renderEnergyHistory(snapshot) {
  const result = snapshot?.result || null;
  if (result?.task_id === "mapping_analysis") {
    const entries = result?.task_result?.entries || [];
    if (!entries.length) { $("energyHistory").innerHTML = `<div class="empty-state">Mapping resources will appear here.</div>`; return; }
    $("energyHistory").innerHTML = `<div class="mapping-resource-cards">${entries.map(item => {
      const r = item.mapped_artifact?.resource_report || {};
      return `<article><strong>${esc(item.mapping_id)}</strong><span>Pauli terms: ${esc(r.pauli_term_count ?? "—")}</span><span>max weight: ${esc(r.maximum_pauli_weight ?? "—")}</span><span>weighted mean: ${esc(number(r.coefficient_weighted_mean_pauli_weight,6))}</span><span>QWC groups: ${esc(r.qwc_measurement_group_count ?? "—")}</span></article>`;
    }).join("")}</div>`;
    return;
  }
  const history = result?.convergence_history || snapshot?.journey_state?.energy_history || [];
  if (!history.length) {
    $("energyHistory").innerHTML = `<div class="empty-state">Energy evaluations will appear here.</div>`;
    return;
  }
  const values = history.map(item => Number(item.energy)).filter(Number.isFinite);
  const min = Math.min(...values), max = Math.max(...values);
  const span = Math.max(1e-12, max - min);
  const bars = history.map((item,index) => {
    const energy = Number(item.energy);
    const height = Number.isFinite(energy) ? 18 + ((max - energy) / span) * 88 : 10;
    const evaluation = item.evaluation ?? item.iteration ?? index + 1;
    return `<div class="chart-bar" style="height:${height}px" data-tip="eval ${esc(evaluation)} · E=${esc(number(energy,8))}"></div>`;
  }).join("");
  $("energyHistory").innerHTML = `<div class="chart-bars">${bars}</div>`;
}

function renderLedger(display) {
  const rows = display?.source_ledger || [];
  if (!rows.length) {
    $("sourceLedger").innerHTML = `<div class="empty-state">The source ledger appears after a run is created.</div>`;
    return;
  }
  $("sourceLedger").innerHTML = rows.map(row => `<div class="ledger-row"><strong>${esc(row.label)} · ${esc(row.classification)}</strong><span>${esc(row.source)}</span><span>run_id: ${esc(row.run_id)} · value: ${esc(list(row.value))}</span>${row.note ? `<span>${esc(row.note)}</span>` : ""}</div>`).join("");
}

function renderFailureSummary(snapshot, journey) {
  const failure = journey?.failure || snapshot?.failure || null;
  const box = $("runFailureSummary");
  const panel = $("technicalErrorPanel");
  if (!failure) {
    box.classList.add("hidden");
    box.innerHTML = "";
    panel.classList.add("hidden");
    $("technicalErrorLog").textContent = "No technical error has been loaded.";
    return;
  }
  const stage = journey?.cards?.[failure.stage];
  const title = stage?.title || failure.stage || "unknown station";
  box.innerHTML = `<strong>Run stopped at: ${esc(title)}</strong>${esc(failure.user_message || "The run stopped.")}${failure.suggested_action ? `<br><span>${esc(failure.suggested_action)}</span>` : ""}`;
  box.classList.remove("hidden");
  panel.classList.toggle("hidden", !snapshot?.technical_error_available);
}

async function loadTechnicalError() {
  if (!state.runId) return;
  try {
    const payload = await apiJson(`/runs/${encodeURIComponent(state.runId)}/technical-error`);
    const failure = payload.failure || {};
    $("technicalErrorLog").textContent = [
      `run_id: ${payload.run_id}`,
      `stage: ${failure.stage || "—"}`,
      `error_code: ${failure.error_code || "—"}`,
      `exception_type: ${failure.exception_type || "—"}`,
      `recoverable: ${failure.recoverable ?? "—"}`,
      `user_message: ${failure.user_message || "—"}`,
      `suggested_action: ${failure.suggested_action || "—"}`,
      "",
      payload.technical_error || "No traceback is available.",
    ].join("\n");
  } catch (error) {
    $("technicalErrorLog").textContent = String(error.message || error);
  }
}

function renderMappingComparison(result) {
  const panel = $("mappingComparisonPanel");
  if (!result || result.task_id !== "mapping_analysis") { panel.classList.add("hidden"); panel.innerHTML = ""; return; }
  const report = result.task_result || {};
  const rows = (report.entries || []).map(item => {
    const r = item.mapped_artifact?.resource_report || {};
    const c = item.mapped_artifact?.capability_report || {};
    return `<tr><td><strong>${esc(item.mapping_id)}</strong></td><td>${esc(item.transform_verified)}</td><td>${esc(r.n_qubits ?? "—")}</td><td>${esc(r.pauli_term_count ?? "—")}</td><td>${esc(r.maximum_pauli_weight ?? "—")}</td><td>${esc(number(r.coefficient_weighted_mean_pauli_weight,6))}</td><td>${esc(r.qwc_measurement_group_count ?? "—")}</td><td>${esc(c.support_by_task?.ground_state_energy ?? "—")}</td></tr>`;
  }).join("");
  panel.innerHTML = `<div class="mapping-results-head"><h3>JW / BK Mapping Explorer</h3><span class="truth-badge verified">ANALYSIS VERIFIED</span></div><p>The same FermionOperator, mode ordering, and particle sector are used for both transforms. The ranking is analysis-only.</p><div class="mapping-table-wrap"><table><thead><tr><th>Mapping</th><th>Transform</th><th>Qubits</th><th>Terms</th><th>Max weight</th><th>Weighted mean</th><th>QWC groups</th><th>Ground-state support</th></tr></thead><tbody>${rows}</tbody></table></div><div class="mapping-result-note">Analysis-only ranking: <strong>${esc(report.recommended_for_analysis || "—")}</strong>. ${esc(report.recommendation_basis || "")}</div>`;
  panel.classList.remove("hidden");
}


function renderMappingJourneyLanes(result) {
  const defaults = {
    mappingLaneJW: ["Jordan–Wigner", "Direct occupation semantics. Resource and equivalence metrics appear after the live run."],
    mappingLaneBK: ["Bravyi–Kitaev", "GF(2) occupation code. Resource and equivalence metrics appear after the live run."],
  };
  if (!result || result.task_id !== "mapping_analysis") {
    for (const [id, [label, text]] of Object.entries(defaults)) {
      const node = $(id); if (!node) continue;
      node.innerHTML = `<div class="mapping-live-head"><strong>${esc(label)}</strong><span>waiting</span></div><p>${esc(text)}</p>`;
    }
    return;
  }
  const entries = result.task_result?.entries || [];
  const map = Object.fromEntries(entries.map(item => [String(item.mapping_id || ""), item]));
  const fill = (id, keys, label) => {
    const node = $(id); if (!node) return;
    const item = keys.map(key => map[key]).find(Boolean);
    if (!item) { node.innerHTML = `<div class="mapping-live-head"><strong>${esc(label)}</strong><span>not returned</span></div>`; return; }
    const r = item.mapped_artifact?.resource_report || {};
    const c = item.mapped_artifact?.capability_report || {};
    node.innerHTML = `<div class="mapping-live-head"><strong>${esc(label)}</strong><span>${item.transform_verified ? "verified" : "review"}</span></div>
      <div class="mapping-live-metrics">
        <div><span>qubits</span><b>${esc(r.n_qubits ?? "—")}</b></div>
        <div><span>Pauli terms</span><b>${esc(r.pauli_term_count ?? "—")}</b></div>
        <div><span>maximum weight</span><b>${esc(r.maximum_pauli_weight ?? "—")}</b></div>
        <div><span>weighted mean</span><b>${esc(number(r.coefficient_weighted_mean_pauli_weight,6))}</b></div>
        <div><span>QWC groups</span><b>${esc(r.qwc_measurement_group_count ?? "—")}</b></div>
        <div><span>ground-state support</span><b>${esc(c.support_by_task?.ground_state_energy ?? "—")}</b></div>
      </div>`;
  };
  fill("mappingLaneJW", ["jordan_wigner.v1", "jordan_wigner"], "Jordan–Wigner");
  fill("mappingLaneBK", ["bravyi_kitaev.v1", "bravyi_kitaev"], "Bravyi–Kitaev");
}

function renderCompactSummary(snapshot, journey, result, artifact, display) {
  const status = snapshot?.status || "waiting";
  const badge = $("compactRunStatus");
  badge.textContent = result?.status || status;
  badge.className = `status-badge ${status}`;
  $("compactRunId").textContent = snapshot?.run_id || "—";
  $("compactModel").textContent = artifact?.model_id || snapshot?.request?.model_id || snapshot?.request?.problem || "—";
  $("compactTask").textContent = result?.task_id || snapshot?.request?.task_id || "—";
  if (!result) {
    $("compactPrimaryValue").textContent = status === "running" ? "running…" : "—";
    $("compactReference").textContent = journey?.exact_reference_energy ?? "—";
    $("compactError").textContent = journey?.failure?.error_code || "—";
    return;
  }
  if (result.task_id === "mapping_analysis") {
    const report = result.task_result || {};
    const entries = report.entries || [];
    const errors = entries.flatMap(item => [Number(item.full_spectrum_max_abs_error || 0), Number(item.target_sector_spectrum_max_abs_error || 0)]);
    $("compactPrimaryValue").textContent = `${entries.length} mappings · ${report.all_transforms_verified ? "verified" : "review"}`;
    $("compactReference").textContent = "exact Fock-space spectra";
    $("compactError").textContent = errors.length ? `max Δ=${number(Math.max(...errors),6)}` : "—";
  } else if (result.task_id === "observable_estimation") {
    const occupations = result.task_result?.occupations || [];
    $("compactPrimaryValue").textContent = occupations.length ? `[${occupations.map(v => number(v,5)).join(", ")}]` : "—";
    $("compactReference").textContent = result.task_result?.reference_occupations ? "classical occupations" : "unavailable";
    $("compactError").textContent = result.verification?.maximum_absolute_error !== undefined ? number(result.verification.maximum_absolute_error,6) : result.status;
  } else {
    const unit = artifact?.units?.energy || result.meaning?.unit || "";
    $("compactPrimaryValue").textContent = result.reconstructed_energy !== null && result.reconstructed_energy !== undefined ? `${number(result.reconstructed_energy,9)} ${unit}` : "—";
    $("compactReference").textContent = result.verification?.reference_energy !== null && result.verification?.reference_energy !== undefined ? `${number(result.verification.reference_energy,9)} ${unit}` : "unavailable";
    $("compactError").textContent = result.verification?.absolute_error !== null && result.verification?.absolute_error !== undefined ? `${number(result.verification.absolute_error,6)} ${unit}` : result.status;
  }
}


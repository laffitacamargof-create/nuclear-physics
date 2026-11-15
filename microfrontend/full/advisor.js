function advisorClass(kind) {
  if (kind === "patch_hypothesis") return "hypothesis";
  if (kind === "limitation") return "limitation";
  if (kind === "verified_fact") return "fact";
  return "no-action";
}

function renderPhaseC(comparison) {
  const badge = $("phaseCBadge");
  const status = $("phaseCStatus");
  const result = $("phaseCResult");
  const evidence = $("phaseCEvidence");
  if (!comparison) {
    badge.textContent = "WAITING";
    status.innerHTML = `<strong>No candidate experiment yet</strong><p>Approve one allow-listed Advisor hypothesis to execute a candidate through the same pipeline.</p>`;
    result.classList.add("hidden");
    result.innerHTML = "";
    evidence.classList.add("disabled"); evidence.setAttribute("aria-disabled", "true"); evidence.href = "#";
    return;
  }
  badge.textContent = String(comparison.status || "waiting").toUpperCase();
  status.innerHTML = `<strong>Baseline ${esc(comparison.baseline_run_id)} ⇄ candidate ${esc(comparison.candidate_run_id)}</strong><p>Explicit approval recorded · same run_pipeline · no automatic replacement.</p>`;
  if (comparison.comparison) {
    const data = comparison.comparison;
    const metrics = (data.metrics || []).map(item => `<div class="phase-c-metric"><span>${esc(item.label)}</span><strong>${esc(item.judgment)}</strong><small>${esc(list(item.baseline_value))} → ${esc(list(item.candidate_value))}</small></div>`).join("");
    result.innerHTML = `<div class="phase-c-outcome outcome-${String(data.outcome || "").toLowerCase()}"><span>Decision</span><strong>${esc(data.outcome)}</strong></div><p>${esc(data.rationale)}</p><div class="phase-c-metrics">${metrics}</div><small>Verification remains final authority · decision stored with both run IDs.</small>`;
    result.classList.remove("hidden");
  } else {
    result.innerHTML = `<p>Candidate status: ${esc(comparison.status)}. The comparison will appear after the candidate reaches a terminal state and its Evidence is available.</p>`;
    result.classList.remove("hidden");
  }
  if (comparison.evidence_available && comparison.evidence_url) {
    evidence.classList.remove("disabled"); evidence.removeAttribute("aria-disabled"); evidence.href = apiUrl(comparison.evidence_url);
  }
}

async function pollPhaseC(sessionId) {
  if (state.comparisonPollTimer) window.clearTimeout(state.comparisonPollTimer);
  try {
    const payload = await apiJson(`/comparisons/${encodeURIComponent(sessionId)}`);
    state.comparison = payload;
    renderPhaseC(payload);
    if (!["completed", "failed"].includes(payload.status)) {
      state.comparisonPollTimer = window.setTimeout(() => pollPhaseC(sessionId), 900);
    }
  } catch (error) {
    $("phaseCStatus").innerHTML = `<strong>Comparison unavailable</strong><p>${esc(error.message || error)}</p>`;
  }
}

function renderAdvisor(report) {
  const badge = $("advisorBadge");
  const status = $("advisorStatus");
  const cardsRoot = $("advisorCards");
  const candidate = $("advisorCandidatePlan");
  candidate.classList.add("hidden");
  candidate.textContent = "";
  if (!report) {
    badge.textContent = ["completed","failed","cancelled"].includes(state.snapshot?.status) ? "DETERMINISTIC · UNAVAILABLE" : "DETERMINISTIC · WAITING";
    status.innerHTML = `<span class="feedback-icon">↩</span><div><strong>${["completed","failed","cancelled"].includes(state.snapshot?.status) ? "No Advisor report is available" : "Waiting for a terminal run"}</strong><p>The scientific run remains valid without Advisor output. No truth is mutated.</p></div>`;
    cardsRoot.innerHTML = "";
    return;
  }
  const cards = report.cards || [];
  badge.textContent = report.status === "disabled" ? "ADVISOR DISABLED" : `DETERMINISTIC · ${cards.length} CARD${cards.length === 1 ? "" : "S"}`;
  status.innerHTML = `<span class="feedback-icon">↩</span><div><strong>Grounded post-run feedback ready</strong><p>${report.deterministic ? "Deterministic rules only" : "Unknown mode"} · no artifact, result, evidence, or verification mutation · verification retains final authority.</p></div>`;
  cardsRoot.innerHTML = cards.map(card => {
    const refs = (card.evidence_refs || []).map(ref => `<li>${esc(ref.source)} ${esc(ref.path)} = ${esc(list(ref.observed_value))}</li>`).join("");
    const patch = card.proposed_patch ? `<div class="advisor-patch">${esc(JSON.stringify(card.proposed_patch, null, 2))}</div>` : "";
    const action = card.proposed_patch ? `<div class="advisor-action"><button class="button secondary advisor-prepare" data-card-id="${esc(card.card_id)}">Inspect candidate</button><button class="button amber advisor-try-compare" data-card-id="${esc(card.card_id)}">Approve · run · compare</button><small>Phase C executes only after explicit confirmation</small></div>` : "";
    return `<article class="advisor-card ${advisorClass(card.kind)}"><div class="advisor-card-head"><h3>${esc(card.title)}</h3><span class="advisor-kind">${esc(card.epistemic_status)}</span></div><p><strong>${esc(card.summary)}</strong></p><p>${esc(card.explanation)}</p><ul class="advisor-evidence">${refs}</ul>${patch}${action}<p><em>Expected:</em> ${esc(card.expected_effect)}</p></article>`;
  }).join("");
  cardsRoot.querySelectorAll(".advisor-prepare").forEach(button => button.addEventListener("click", async () => {
    if (!state.runId) return;
    button.disabled = true;
    try {
      const approved = window.confirm(
        "Prepare this candidate request? This does not execute it. The app will validate the patch, preserve the baseline, and return a candidate for a new POST /runs submission."
      );
      if (!approved) return;
      const payload = await apiJson(`/runs/${encodeURIComponent(state.runId)}/advisor/prepare-candidate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ card_id: button.dataset.cardId, approved: true }),
      });
      candidate.textContent = JSON.stringify({
        candidate_plan: payload.candidate_plan,
        next_entrypoint: payload.next_entrypoint,
        canonical_pipeline_entrypoint: payload.canonical_pipeline_entrypoint,
        execution_performed_by_advisor: payload.execution_performed_by_advisor,
        phase_c_comparison_performed: payload.phase_c_comparison_performed,
      }, null, 2);
      candidate.classList.remove("hidden");
    } catch (error) {
      candidate.textContent = String(error.message || error);
      candidate.classList.remove("hidden");
    } finally { button.disabled = false; }
  }));
  cardsRoot.querySelectorAll(".advisor-try-compare").forEach(button => button.addEventListener("click", async () => {
    if (!state.runId) return;
    button.disabled = true;
    try {
      const approved = window.confirm(
        "Run this candidate through the same pipeline and compare its Evidence with the baseline? The outcome may be ADOPT, REJECT, or INCONCLUSIVE; nothing is replaced automatically."
      );
      if (!approved) return;
      const payload = await apiJson(`/runs/${encodeURIComponent(state.runId)}/try-compare`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ card_id: button.dataset.cardId, approved: true }),
      });
      state.comparison = payload;
      renderPhaseC(payload);
      pollPhaseC(payload.session_id);
    } catch (error) {
      $("phaseCStatus").innerHTML = `<strong>Try / Compare did not start</strong><p>${esc(error.message || error)}</p>`;
    } finally { button.disabled = false; }
  }));
}

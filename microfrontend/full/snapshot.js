function renderSnapshot() {
  const snapshot = state.snapshot || {};
  const journey = snapshot.journey_state || {};
  const result = snapshot.result || null;
  const artifact = snapshot.artifact || null;
  const display = snapshot.display || null;
  state.advisor = snapshot.advisor || state.advisor;
  renderAdvisor(state.advisor);
  renderPhaseC(state.comparison);
  $("runIdLabel").textContent = snapshot.run_id ? `run_id: ${snapshot.run_id}` : "No active run";
  const lifecycle = $("lifecycleBadge");
  lifecycle.textContent = snapshot.status || "waiting";
  lifecycle.className = `status-badge ${snapshot.status || "waiting"}`;
  $("iterationLabel").textContent = `iteration ${journey.current_iteration || "—"}`;
  $("cancelButton").disabled = !snapshot.run_id || ["completed","cancelled","failed"].includes(snapshot.status);
  renderFailureSummary(snapshot, journey);
  for (const stage of STAGES) renderStage(stage);
  renderArtifact(artifact, journey, display);
  const mappingTask = (result?.task_id || state.taskId) === "mapping_analysis";
  setHidden("mappingRuntime", !mappingTask);
  setHidden("variationalRuntimeBody", mappingTask);
  $("runtimeTitleText").textContent = mappingTask ? "Deterministic mapping analysis" : "External variational runtime";
  renderMappingComparison(result);
  renderMappingJourneyLanes(result);
  renderCompactSummary(snapshot, journey, result, artifact, display);
  renderActiveRealization(display, artifact, result, snapshot);

  const unit = artifact?.units?.energy || result?.meaning?.unit || "";
  const history = journey.energy_history || [];
  const latest = history.length ? history[history.length - 1] : null;
  $("latestEnergy").textContent = latest ? `${number(latest.energy,8)} ${unit}` : "—";
  $("bestEnergy").textContent = journey.best_energy !== null && journey.best_energy !== undefined ? `${number(journey.best_energy,8)} ${unit}` : "—";
  $("referenceEnergy").textContent = journey.exact_reference_energy !== null && journey.exact_reference_energy !== undefined ? `${number(journey.exact_reference_energy,8)} ${unit}` : "—";
  $("eventCount").textContent = journey.event_count ?? snapshot.last_event_id ?? 0;

  const verification = result?.verification || {};
  const mappingTaskResult = result?.task_id === "mapping_analysis";
  const observableTask = result?.task_id === "observable_estimation";
  if (mappingTaskResult) {
    const report = result?.task_result || {};
    const entries = report.entries || [];
    const maxFull = Math.max(...entries.map(item => Number(item.full_spectrum_max_abs_error || 0)));
    const maxSector = Math.max(...entries.map(item => Number(item.target_sector_spectrum_max_abs_error || 0)));
    $("resultEnergy").textContent = `${entries.length} mappings`;
    $("resultUncertainty").textContent = "deterministic operator transforms · no shots";
    $("resultReference").textContent = "exact Fermionic spectra";
    $("referenceScope").textContent = "full Fock space + fixed-particle sector within the bounded acceptance envelope";
    $("resultError").textContent = number(Math.max(maxFull, maxSector), 6);
    $("resultThreshold").textContent = number(result.optimizer_tolerance, 6);
    $("sectorLeakage").textContent = "not applicable";
    $("sectorLeakageNote").textContent = "particle-number operator spectra and [H,N] are verified instead";
  } else if (observableTask) {
    const taskResult = result?.task_result || {};
    const occupations = taskResult.occupations || [];
    const referenceOccupations = taskResult.reference_occupations || verification.reference_occupations || [];
    $("resultEnergy").textContent = occupations.length ? `[${occupations.map(v => number(v,6)).join(", ")}]` : "—";
    $("resultUncertainty").textContent = "pair occupations · measured from one Z-basis diagnostic circuit";
    $("resultReference").textContent = referenceOccupations.length ? `[${referenceOccupations.map(v => number(v,6)).join(", ")}]` : "unavailable";
    $("referenceScope").textContent = "exact-state occupations for the acceptance fixture; not a VQE-convergence claim";
    $("resultError").textContent = verification.maximum_absolute_error !== null && verification.maximum_absolute_error !== undefined ? number(verification.maximum_absolute_error,6) : "—";
    $("resultThreshold").textContent = verification.observable_acceptance_threshold !== null && verification.observable_acceptance_threshold !== undefined ? number(verification.observable_acceptance_threshold,6) : "—";
    $("sectorLeakage").textContent = taskResult.sector_leakage !== null && taskResult.sector_leakage !== undefined ? number(taskResult.sector_leakage,8) : "—";
    $("sectorLeakageNote").textContent = "MEASURED / DERIVED from the same run's bitstrings";
  } else {
    $("resultEnergy").textContent = result ? `${number(result.reconstructed_energy,9)} ${unit}` : "—";
    $("resultUncertainty").textContent = result ? `± ${number(result.standard_error,5)} ${unit} · reconstructed from counts` : "from measurement counts";
    $("resultReference").textContent = verification.reference_energy !== null && verification.reference_energy !== undefined ? `${number(verification.reference_energy,9)} ${unit}` : "unavailable";
    $("referenceScope").textContent = verification.reference_scope || (artifact?.exact_reference ? "declared small-system / sector reference" : "exact reference unavailable · verification level limited");
    $("resultError").textContent = verification.absolute_error !== null && verification.absolute_error !== undefined ? `${number(verification.absolute_error,6)} ${unit}` : "—";
    $("resultThreshold").textContent = verification.acceptance_threshold !== null && verification.acceptance_threshold !== undefined ? `${number(verification.acceptance_threshold,6)} ${unit}` : "—";
    const sectorDiagnostics = verification.sector_diagnostics || result?.meaning?.result?.sector_diagnostics || {};
    if (sectorDiagnostics.applicable) {
      $("sectorLeakage").textContent = number(sectorDiagnostics.sector_leakage, 10);
      $("sectorLeakageNote").textContent = sectorDiagnostics.measured_on_backend
        ? "MEASURED / DERIVED from backend records"
        : "ideal local logical-sector diagnostic · not a backend measurement or state fidelity";
    } else {
      $("sectorLeakage").textContent = "not measured";
      $("sectorLeakageNote").textContent = sectorDiagnostics.reason || "requires a mapping-aware sector diagnostic";
    }
  }
  $("qasmFidelity").textContent = mappingTaskResult ? "not applicable" : (display?.qasm_semantic_fidelity !== null && display?.qasm_semantic_fidelity !== undefined ? number(display.qasm_semantic_fidelity,12) : "—");
  renderJudgments(display);

  const meaning = result?.meaning || journey.physical_summary || {};
  $("physicalStatement").textContent = meaning.supported_statement || meaning.scientific_quantity || "A physical statement will appear after reconstruction and verification.";
  const limits = meaning.limitations || [];
  $("limitationList").innerHTML = limits.length ? limits.map(item => `<li>${esc(item)}</li>`).join("") : "<li>No final limitation list is available yet.</li>";
  $("executionLabel").textContent = mappingTaskResult ? "Execution: deterministic operator analysis" : `Execution: ${(result?.execution_mode || snapshot.request?.execution_mode || "local_simulator").replaceAll("_", " ")}`;
  $("backendLabel").textContent = mappingTaskResult ? "backend: not invoked" : `provider target: ${(result?.target_backend || snapshot.request?.target_backend || "—").toUpperCase()}`;

  renderEnergyHistory(snapshot);
  const summary = result?.payload_summary || {};
  $("evidenceMeta").innerHTML = [
    `measurement records: ${summary.measurement_record_count ?? "—"}`,
    `term expectations: ${summary.term_expectation_count ?? "—"}`,
    `journey events: ${summary.journey_event_count ?? snapshot.last_event_id ?? "—"}`,
    `full payload: ${summary.full_payload_location || "evidence ZIP"}`,
  ].map(item => `<span>${esc(item)}</span>`).join("");

  const evidence = $("evidenceDownload");
  if (snapshot.evidence_available && snapshot.evidence_url) {
    evidence.href = apiUrl(snapshot.evidence_url);
    evidence.classList.remove("disabled");
    evidence.setAttribute("aria-disabled", "false");
  } else {
    evidence.href = "#";
    evidence.classList.add("disabled");
    evidence.setAttribute("aria-disabled", "true");
  }
  renderLedger(display);
}

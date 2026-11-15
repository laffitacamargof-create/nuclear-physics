async function refreshRunHistory() {
  try {
    const payload = await apiJson("/runs");
    const select = $("runHistorySelect");
    const current = select.value;
    select.innerHTML = `<option value="">${payload.count ? "Choose a run" : "No saved runs"}</option>` + payload.runs.map(run => `<option value="${esc(run.run_id)}">${esc(run.run_id)} · ${esc(run.status)} · ${esc(run.request?.model_id || "canonical identity pending")}</option>`).join("");
    if ([...select.options].some(option => option.value === current)) select.value = current;
  } catch (_) { /* API health will show the issue */ }
}

function setApiHealth(text, status) {
  const node = $("apiHealth");
  node.textContent = text;
  node.className = `health-badge ${status}`;
}

async function checkHealth() {
  try {
    const health = await apiJson("/health");
    setApiHealth(`Engine ready`, "ok");
  } catch (error) {
    setApiHealth("Engine unavailable", "waiting");
  }
}

function resetDashboard() {
  closeStream();
  state.runId = null;
  state.lastEventId = 0;
  state.snapshot = null;
  state.advisor = null;
  state.comparison = null;
  if (state.comparisonPollTimer) window.clearTimeout(state.comparisonPollTimer);
  state.comparisonPollTimer = null;
  storageRemove("qcol_last_run_id");
  $("cancelButton").disabled = true;
  renderSnapshot();
  showFormError(null);
  $("technicalErrorPanel").classList.add("hidden");
  $("technicalErrorLog").textContent = "No technical error has been loaded.";
}

async function bootstrap() {
  try {
    state.catalog = await apiJson("/catalog");
    state.realizationCatalog = await apiJson("/catalog/model-task-realizations");
    renderModelCards();
    renderForms();
    renderCapabilityMatrix();
    $("taskId").addEventListener("change", event => {
      state.taskId = event.target.value;
      renderTaskOptions();
    });
    selectModel(state.modelFamily);
    selectFermionRoute(state.fermionRoute);
    selectCustomRoute("guided");
    renderScientificCoreInspector();
    syncMatrixSelection();
    await checkHealth();
    await refreshRunHistory();
    const previous = storageGet("qcol_last_run_id");
    if (previous) {
      try {
        await recoverRun(previous);
        if (!["completed", "cancelled", "failed"].includes(state.snapshot?.status)) connectStream();
      } catch (_) {
        storageRemove("qcol_last_run_id");
      }
    }
  } catch (error) {
    showFormError(error);
  }
  renderSnapshot();
}

$("runForm").addEventListener("submit", submitRun);
$("cancelButton").addEventListener("click", cancelRun);
$("newRunButton").addEventListener("click", resetDashboard);
$("refreshRunsButton").addEventListener("click", refreshRunHistory);
$("loadTechnicalErrorButton").addEventListener("click", loadTechnicalError);
$("loadRunButton").addEventListener("click", async () => {
  const runId = value("runHistorySelect");
  if (!runId) return;
  closeStream();
  await recoverRun(runId);
  if (!["completed", "cancelled", "failed"].includes(state.snapshot?.status)) connectStream();
});
window.addEventListener("beforeunload", closeStream);
bootstrap();
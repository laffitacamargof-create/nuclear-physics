function showFormError(error) {
  const box = $("formError");
  if (!error) {
    box.textContent = "";
    box.classList.add("hidden");
  } else {
    box.textContent = String(error.message || error);
    box.classList.remove("hidden");
  }
}

async function submitRun(event) {
  event.preventDefault();
  showFormError(null);
  try {
    const request = buildRequest();
    const created = await apiJson("/runs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    });
    state.runId = created.run_id;
    state.lastEventId = 0;
    state.snapshot = null;
    storageSet("qcol_last_run_id", state.runId);
    storageSet(`qcol_last_event_${state.runId}`, "0");
    $("cancelButton").disabled = false;
    await recoverRun(state.runId, true);
    connectStream();
    refreshRunHistory();
  } catch (error) {
    showFormError(error);
  }
}

function handleSseEvent(event) {
  const id = Number(event.lastEventId || 0);
  if (id > 0) {
    state.lastEventId = id;
    storageSet(`qcol_last_event_${state.runId}`, String(id));
  }
  let data = {};
  try { data = JSON.parse(event.data); } catch (_) { return; }
  if (["run_created", "run_status", "cancel_requested", "completed", "cancelled", "failed"].includes(event.type)) {
    state.snapshot = data;
  } else if (event.type === "advisor_ready") {
    state.snapshot ||= { run_id: state.runId, status: "running" };
    state.snapshot.advisor = data.advisor;
    state.advisor = data.advisor;
  } else {
    state.snapshot ||= { run_id: state.runId, status: "running" };
    if (data.journey_state) state.snapshot.journey_state = data.journey_state;
    if (data.artifact) state.snapshot.artifact = data.artifact;
    state.snapshot.last_event_id = id;
  }
  renderSnapshot();
  if (["completed", "cancelled", "failed"].includes(state.snapshot?.status)) {
    closeStream();
    refreshRunHistory();
  }
}

async function recoverRun(runId, resetEventCursor = false) {
  if (!runId) return;
  const snapshot = await apiJson(`/runs/${encodeURIComponent(runId)}`);
  state.runId = runId;
  state.snapshot = snapshot;
  state.lastEventId = resetEventCursor ? 0 : Number(storageGet(`qcol_last_event_${runId}`) || snapshot.last_event_id || 0);
  storageSet("qcol_last_run_id", runId);
  renderSnapshot();
  if (!["completed", "cancelled", "failed"].includes(snapshot.status)) {
    $("cancelButton").disabled = false;
  }
}

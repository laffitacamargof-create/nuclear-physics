/* Quantum app nuclear physics · virtual transport.
   Replaces fetch/EventSource of the original interface by pyCall -> qapi() (backend inside the compiler). */
const V = { runs: {}, alias: {}, pending: {}, cmp: {}, evBlob: {}, abort: false };
const QN = window.QNP;
const clean = (x) => JSON.parse(JSON.stringify(x).replace(/QCOL/g, "Quantum app"));
const b64u8 = (s) => Uint8Array.from(atob(s), (c) => c.charCodeAt(0));
async function inflate(b64) {
  const ds = new Blob([b64u8(b64)]).stream().pipeThrough(new DecompressionStream("deflate"));
  return JSON.parse(await new Response(ds).text());
}
async function pyq(method, path, body, ctx) {
  const zip = typeof DecompressionStream === "function";
  const out = await QN.py("qapi", JSON.stringify({ m: method, p: path, b: body || {}, c: Object.assign({ z: zip ? 1 : 0 }, ctx || {}) }));
  const r = out && out.z ? await inflate(out.z) : out;
  if (!r || r.status >= 400) {
    const d = r && r.detail;
    throw new Error(typeof d === "string" ? d : d && typeof d === "object" ? `${d.message || "Request contract failed"}${d.field ? ` [${d.field}]` : ""}` : "Engine error");
  }
  return r.json;
}
const rid = (a) => V.alias[a] || a;
function blobUrl(b64) { return b64 ? URL.createObjectURL(new Blob([b64u8(b64)], { type: "application/zip" })) : null; }
async function staticJson(name, fallbackPath) {
  try { return JSON.parse(await QN.getSrc(name)); } catch (_) { return pyq("GET", fallbackPath); }
}
function remember(id, rec) {
  V.runs[id] = rec;
  try {
    const keep = Object.values(V.runs).sort((a, b) => String(b.snapshot.created_utc).localeCompare(String(a.snapshot.created_utc))).slice(0, 6);
    localStorage.setItem("qnp_runs", JSON.stringify(keep.map((r) => ({ snapshot: Object.assign({}, r.snapshot, { evidence_available: false, evidence_url: null }), technical: r.technical, exp: r.exp }))));
  } catch (_) {}
}
try { (JSON.parse(localStorage.getItem("qnp_runs") || "[]")).forEach((r) => { V.runs[r.snapshot.run_id] = { snapshot: r.snapshot, technical: r.technical, exp: r.exp }; }); } catch (_) {}

function apiUrl(path) {
  let m = /^\/runs\/([^/]+)\/evidence/.exec(path);
  if (m) return (V.runs[rid(m[1])] || {}).evUrl || "#";
  m = /^\/comparisons\/([^/]+)\/evidence/.exec(path);
  if (m) return (V.cmp[rid(m[1])] || {}).evUrl || "#";
  return path;
}
function provisional(id, request) {
  return { run_id: id, status: "running", created_utc: new Date().toISOString(), started_utc: null, completed_utc: null, request, journey_state: null, artifact: null, result: null, advisor: null, display: null, evidence_available: false, last_event_id: 0 };
}

async function apiJson(url, options = {}) {
  const method = (options.method || "GET").toUpperCase();
  const body = options.body ? JSON.parse(options.body) : {};
  let m;
  if (url === "/health") return { status: "ok", active_run_count: Object.keys(V.pending).length };
  if (url === "/catalog") return staticJson("catalog.json", "/catalog");
  if (url === "/catalog/model-task-realizations") return staticJson("realizations.json", "/catalog/model-task-realizations");
  if (method === "GET" && url === "/runs") {
    const runs = Object.values(V.runs).map((r) => r.snapshot).sort((a, b) => String(b.created_utc).localeCompare(String(a.created_utc)));
    return { count: runs.length, runs };
  }
  if (method === "POST" && url === "/runs") {
    const tmp = "run-" + Math.random().toString(16).slice(2, 14);
    const t0 = performance.now();
    V.pending[tmp] = { prov: provisional(tmp, body), t0, job: pyq("POST", "/runs", body).then((d) => ({ d })).catch((e) => ({ e })) };
    return { run_id: tmp };
  }
  if ((m = /^\/runs\/([^/]+)\/(cancel|technical-error|advisor\/prepare-candidate|try-compare)$/.exec(url))) {
    const id = rid(decodeURIComponent(m[1]));
    if (m[2] === "technical-error") {
      const t = (V.runs[id] || {}).technical;
      if (!t) throw new Error("No technical error is available for this run.");
      return t;
    }
    if (m[2] === "cancel") return (V.runs[id] && V.runs[id].snapshot) || V.pending[decodeURIComponent(m[1])].prov;
    const rec = V.runs[id];
    if (!rec) throw new Error("The run is no longer available. Run it again.");
    const ctx = { run_id: id, request: rec.snapshot.request };
    if (m[2] === "advisor/prepare-candidate") return pyq("POST", `/runs/${id}/advisor/prepare-candidate`, body, ctx);
    if (!body.card_id) throw new Error("card_id is required.");
    if (body.approved !== true) throw new Error("Phase C will not execute a candidate until approved=true is supplied.");
    const sid = "try-compare-" + Math.random().toString(16).slice(2, 14);
    const prov = { session_id: sid, status: "waiting_for_candidate", baseline_run_id: id, candidate_run_id: "running…", advisor_card_id: body.card_id, comparison: null, evidence_available: false };
    V.cmp[sid] = { snap: prov };
    pyq("POST", `/runs/${id}/try-compare`, body, ctx).then((d) => {
      const cid = d.run_id;
      remember(cid, { snapshot: clean(d.snapshot), technical: d.technical_error, exp: d.export, evUrl: blobUrl(d.evidence_b64) });
      if (d.time_limited) showFormError("The compiler time limit (35 s) stopped the candidate run; the comparison is not conclusive. Try again.");
      const s = clean(d.session);
      V.alias[sid] = d.session_id;
      V.cmp[sid] = { snap: Object.assign({}, s, { evidence_url: s.evidence_available ? `/comparisons/${sid}/evidence` : null }), evUrl: blobUrl(d.comparison_evidence_b64) };
      if (V.cmp[sid].evUrl) V.cmp[sid].snap.evidence_available = true, V.cmp[sid].snap.evidence_url = `/comparisons/${sid}/evidence`;
      refreshRunHistory();
    }).catch((e) => { V.cmp[sid] = { snap: Object.assign({}, prov, { status: "failed", error: e.message }) }; });
    return prov;
  }
  if ((m = /^\/runs\/([^/]+)$/.exec(url))) {
    const raw = decodeURIComponent(m[1]);
    if (V.pending[raw]) return V.pending[raw].prov;
    const r = V.runs[rid(raw)];
    if (!r) throw new Error("Run not found (it may belong to a previous session).");
    return r.snapshot;
  }
  if ((m = /^\/comparisons\/([^/]+)$/.exec(url))) {
    const c = V.cmp[decodeURIComponent(m[1])];
    if (!c) throw new Error("Comparison not found.");
    if (c.snap.status === "failed" && c.snap.error) throw new Error(c.snap.error);
    return c.snap;
  }
  throw new Error("Route not available: " + url);
}

function closeStream() { V.abort = true; }
const _renderSnapshot = renderSnapshot;
const draw = () => { _renderSnapshot(); (QN.hooks || []).forEach((f) => { try { f(); } catch (_) {} }); };
renderSnapshot = function () { if (V.replay) { V.dirty = true; return; } draw(); };
window.QNP.V = V;
function expandEvents(d) {
  const snap = clean(d.snapshot);
  let cards = {};
  const out = [];
  for (const e of d.events) {
    let data = e.data;
    if (data["@final"]) data = snap;
    else if (data.artifact === "@snapshot") data = Object.assign({}, data, { artifact: snap.artifact });
    else if (data.journey_state && data.journey_state["@delta"]) {
      const js = Object.assign({}, data.journey_state);
      delete js["@delta"];
      cards = Object.assign({}, cards, js.cards);
      js.cards = cards;
      data = Object.assign({}, data, { journey_state: js });
    }
    out.push({ id: e.id, type: e.event, data: clean(data), ts: (data.event && data.event.timestamp_utc) || null });
  }
  return { snap, events: out };
}
function connectStream() {
  const raw = state.runId;
  if (!raw) return;
  V.abort = false;
  const jd = $("journeyDisclosure"); if (jd) jd.open = true;
  const p = V.pending[raw];
  if (!p) return;
  (async () => {
    setApiHealth("running on the engine…", "waiting");
    const tick = setInterval(() => { $("lifecycleBadge").title = `elapsed ${((performance.now() - p.t0) / 1000).toFixed(0)} s`; }, 1000);
    const res = await p.job;
    clearInterval(tick);
    delete V.pending[raw];
    if (V.abort) { return; }
    if (res.e) {
      state.snapshot = Object.assign({}, p.prov, { status: "failed", failure: { message: res.e.message } });
      renderSnapshot(); showFormError(res.e); setApiHealth("engine error", "waiting"); return;
    }
    const d = res.d, { snap, events } = expandEvents(res.d);
    V.alias[raw] = d.run_id;
    state.runId = d.run_id;
    const ev = blobUrl(d.evidence_b64);
    remember(d.run_id, { snapshot: snap, technical: d.technical_error, exp: d.export, evUrl: ev });
    storageSet("qcol_last_run_id", d.run_id);
    setApiHealth("live replay of the recorded run", "ok");
    const ms = (t) => (t ? Date.parse(t) : NaN);
    const total = Math.min(9000, Math.max(2500, events.length * 25));
    const t0 = ms(events.find((e) => e.ts) ? events.find((e) => e.ts).ts : null);
    const t1 = ms([...events].reverse().find((e) => e.ts) ? [...events].reverse().find((e) => e.ts).ts : null);
    let prevT = t0;
    V.replay = true; let lastR = 0;
    for (const e of events) {
      if (V.abort) break;
      let w = total / events.length;
      if (e.ts && t1 > t0) { const cur = ms(e.ts); w = Math.max(6, ((cur - prevT) / (t1 - t0)) * total); prevT = cur; }
      handleSseEvent({ type: e.type, lastEventId: String(e.id), data: JSON.stringify(e.data) });
      if (performance.now() - lastR > 90) { V.replay = false; draw(); V.replay = true; lastR = performance.now(); await QN.sleep(Math.min(w, 200)); }
    }
    V.replay = false; V.dirty = false; draw();
    if (V.abort) { state.snapshot = snap; renderSnapshot(); }
    if (d.time_limited) showFormError("The compiler time limit (35 s) stopped this run before it converged. Use fewer evaluations or fewer shots, or run it again (the second attempt is usually faster).");
    setApiHealth(`engine ready · ${d.seconds}s`, "ok");
    refreshRunHistory();
  })();
}
async function cancelRun() {
  if (!state.runId) return;
  V.abort = true;
  const raw = state.runId, p = V.pending[raw];
  if (p) {
    delete V.pending[raw];
    state.snapshot = Object.assign({}, p.prov, { status: "cancelled" });
    showFormError("Stopped in the interface. The compiler finishes the call that was already sent, but its result is discarded.");
  } else if (V.runs[rid(raw)]) state.snapshot = V.runs[rid(raw)].snapshot;
  renderSnapshot();
}

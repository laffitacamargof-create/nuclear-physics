"use strict";

const state = {
  catalog: null,
  realizationCatalog: null,
  selectedCellId: null,
  modelFamily: "oscillator",
  fermionProblem: "four_level_one_pair",
  fermionRoute: "reduced_pairing",
  fermionValues: {},
  oscillatorModel: null,
  customRoute: "guided",
  taskId: "ground_state_energy",
  runId: null,
  lastEventId: 0,
  eventSource: null,
  snapshot: null,
  reconnectTimer: null,
  advisor: null,
  comparison: null,
  comparisonPollTimer: null,
};

const STAGES = [
  "entrance", "model", "artifact", "task", "optimizer", "mapping_analysis", "bind", "measurement", "translation",
  "execute", "evidence", "reconstruct", "convergence", "exact_reference",
  "verification", "meaning"
];

const $ = (id) => document.getElementById(id);
function storageGet(key) { try { return window.localStorage.getItem(key); } catch (_) { return null; } }
function storageSet(key, value) { try { window.localStorage.setItem(key, value); } catch (_) { /* storage is optional */ } }
function storageRemove(key) { try { window.localStorage.removeItem(key); } catch (_) { /* storage is optional */ } }
const esc = (value) => String(value ?? "—")
  .replaceAll("&", "&amp;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;")
  .replaceAll("'", "&#039;");

function number(value, digits = 6) {
  if (value === null || value === undefined || value === "NaN") return "—";
  const n = Number(value);
  if (!Number.isFinite(n)) return esc(value);
  return n.toLocaleString(undefined, { maximumSignificantDigits: digits });
}

function list(value) {
  if (!value) return "—";
  if (Array.isArray(value)) return value.join(", ");
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function setHidden(id, hidden) { $(id).classList.toggle("hidden", hidden); }
function value(id) { return $(id).value; }
function intValue(id) { return Number.parseInt(value(id), 10); }
function floatValue(id) { return Number.parseFloat(value(id)); }
function floatList(text, name, allowEmpty = false) {
  const clean = String(text ?? "").trim();
  if (!clean) {
    if (allowEmpty) return null;
    throw new Error(`${name} must not be empty.`);
  }
  const parts = clean.split(",").map(item => item.trim()).filter(Boolean);
  const values = parts.map(item => Number(item));
  if (!values.length && !allowEmpty) throw new Error(`${name} must not be empty.`);
  if (values.some(item => !Number.isFinite(item))) throw new Error(`${name} contains an invalid or non-finite value.`);
  return values;
}

function parseCouplingMatrix(text, nModes) {
  const matrix = Array.from({ length: nModes }, () => Array(nModes).fill(0));
  const seen = new Set();
  const lines = String(text ?? "").split(/\r?\n/);
  for (let lineIndex = 0; lineIndex < lines.length; lineIndex += 1) {
    const line = lines[lineIndex].trim();
    if (!line || line.startsWith("#")) continue;
    const fields = line.split(/[\s,;]+/).filter(Boolean);
    if (fields.length !== 3) throw new Error(`Coupling line ${lineIndex + 1} must be: level_i, level_j, G.`);
    const left = Number.parseInt(fields[0], 10);
    const right = Number.parseInt(fields[1], 10);
    const strength = Number(fields[2]);
    if (!Number.isInteger(left) || !Number.isInteger(right)) throw new Error(`Coupling line ${lineIndex + 1} requires integer indices.`);
    if (left === right) throw new Error(`Coupling line ${lineIndex + 1} couples a level to itself.`);
    if (left < 0 || right < 0 || left >= nModes || right >= nModes) throw new Error(`Coupling line ${lineIndex + 1} uses an index outside 0..${nModes - 1}.`);
    if (!Number.isFinite(strength) || strength < 0) throw new Error(`Coupling line ${lineIndex + 1} requires a finite non-negative G.`);
    const key = [left, right].sort((a,b) => a-b).join(":");
    if (seen.has(key)) throw new Error(`Coupling ${key} is declared more than once.`);
    seen.add(key);
    matrix[left][right] = strength;
    matrix[right][left] = strength;
  }
  return matrix;
}

function modelById(id) {
  return state.catalog?.model_families?.find(item => item.id === id);
}

function fermionProblemById(id) {
  return modelById("fermion_pairing")?.problems?.find(item => item.id === id);
}

function schemaFields(problem) {
  return Object.fromEntries((problem?.parameter_schema?.fields || []).map(item => [item.key, item]));
}

function defaultVector(length, declared) {
  const values = Array.isArray(declared) ? declared.map(Number) : [];
  if (values.length === length && values.every(Number.isFinite)) return values;
  return Array.from({ length }, (_, index) => Number(index));
}

function ensureFermionValues(problem) {
  const fields = schemaFields(problem);
  const current = state.fermionValues[problem.id] || {};
  const nField = fields.n_levels;
  const nLevels = nField.role === "fixed" ? Number(nField.fixed_value) : Number(current.n_levels ?? nField.default ?? 4);
  const epsilon = Array.isArray(current.epsilon) ? [...current.epsilon] : defaultVector(nLevels, fields.epsilon?.default);
  while (epsilon.length < nLevels) epsilon.push(epsilon.length);
  state.fermionValues[problem.id] = {
    n_levels: nLevels,
    epsilon: epsilon.slice(0, nLevels),
    g: Number(current.g ?? fields.g?.default ?? 0.5),
    energy_unit: String(current.energy_unit ?? fields.energy_unit?.default ?? "MeV"),
  };
  return state.fermionValues[problem.id];
}

function fermionContractHtml(problem) {
  const fields = schemaFields(problem);
  const fixed = Object.values(fields)
    .filter(item => item.role === "fixed" && item.visible !== false)
    .map(item => `<span><strong>${esc(item.label)}:</strong> ${esc(item.fixed_value)}</span>`)
    .join("");
  return `
    <div class="problem-contract">
      <div class="contract-heading"><strong>${esc(problem.label)}</strong><span>${esc(problem.support_status.replaceAll("_", " "))}</span></div>
      <p>${esc(problem.description)}</p>
      <div class="mapping-declaration">
        <strong>Mapping & encoding — selected by the model contract</strong>
        <span>${esc(fields.mapping?.fixed_value || problem.mapping_policy)} · ${esc(problem.encoding)}</span>
        <small>${esc(fields.mapping?.help_text || "The Capability Resolver applies the declared mapping policy; unsupported alternatives are not shown as runnable choices.")}</small>
      </div>
      <div class="contract-fixed">${fixed}</div>
      <small>Resolved ansatz and reference are shown after the resolver through ScientificRealizationView v1.</small>
    </div>`;
}

function renderFermionDynamicFields(problemId) {
  const problem = fermionProblemById(problemId);
  if (!problem) throw new Error(`Unknown fermion problem: ${problemId}`);
  state.fermionProblem = problemId;
  const fields = schemaFields(problem);
  const values = ensureFermionValues(problem);
  const nField = fields.n_levels;
  const nLevelsLocked = nField.role === "fixed";
  const epsilonInputs = Array.from({ length: values.n_levels }, (_, index) => `
    <label><span>ε${index}</span><input id="fermionEpsilon${index}" type="number" step="any" value="${esc(values.epsilon[index])}"></label>`).join("");
  const pairField = fields.n_pairs;
  const pairMinimum = Number(pairField.minimum ?? pairField.fixed_value ?? 1);
  const pairMaximumDeclared = Number(pairField.maximum ?? pairField.fixed_value ?? pairMinimum);
  const pairMaximum = Math.min(pairMaximumDeclared, Math.max(values.n_levels - 1, pairMinimum));
  const pairChoices = Array.from(
    { length: Math.max(pairMaximum - pairMinimum + 1, 1) },
    (_, offset) => pairMinimum + offset,
  );
  const selectedPairs = pairChoices.includes(Number(values.n_pairs))
    ? Number(values.n_pairs)
    : Number(pairField.fixed_value ?? pairField.default ?? pairChoices[0]);
  values.n_pairs = selectedPairs;
  const pairOptions = pairChoices
    .map(item => `<option value="${item}" ${item === selectedPairs ? "selected" : ""}>${item}</option>`)
    .join("");
  const future = (modelById("fermion_pairing")?.registered_future_problems || [])
    .map(item => `<li><strong>${esc(item.label)}</strong> — ${esc(item.execution_status.replaceAll("_", " "))}. ${esc(item.description)}</li>`).join("");
  $("fermionDynamicFields").innerHTML = `
    ${fermionContractHtml(problem)}
    <div class="form-grid four-columns">
      <label><span>Number of levels</span><input id="fermionLevels" type="number" min="${esc(nField.minimum ?? values.n_levels)}" max="${esc(nField.maximum ?? values.n_levels)}" value="${values.n_levels}" ${nLevelsLocked ? "disabled" : ""}></label>
      <label><span>Number of particles</span><input id="fermionParticles" value="${esc(fields.n_particles.fixed_value ?? (2 * Number(values.n_pairs ?? fields.n_pairs.default ?? 1)))}" disabled></label>
      <label><span>Number of pairs</span><select id="fermionPairs" ${pairField.role === "editable" ? "" : "disabled"}>${pairOptions}</select></label>
      <label><span>Seniority</span><input id="fermionSeniority" value="${esc(fields.seniority.fixed_value)}" disabled></label>
    </div>
    <div class="field-section-label">Single-particle energies — one field per declared level</div>
    <div class="form-grid epsilon-grid">${epsilonInputs}</div>
    <div class="form-grid three-columns">
      <label><span>Pairing strength G</span><input id="fermionG" type="number" step="${esc(fields.g.step ?? 0.01)}" value="${esc(values.g)}"></label>
      <label><span>Energy unit</span><input id="fermionUnit" value="${esc(values.energy_unit)}"></label>
      <label><span>Mapping (automatic)</span><input id="fermionMapping" value="${esc(fields.mapping.fixed_value)}" disabled><small>Chosen by ModelContract + Capability Resolver.</small></label>
    </div>
    ${future ? `<details class="future-problems"><summary>Registered future fermion problem contracts</summary><ul>${future}</ul></details>` : ""}`;
  $("fermionProblem").value = problemId;
  renderTaskOptions();
  renderScientificCoreInspector();
  if (!nLevelsLocked) {
    $("fermionLevels").addEventListener("change", event => {
      captureFermionValues();
      const minimum = Number(nField.minimum ?? 2);
      const maximum = Number(nField.maximum ?? 6);
      state.fermionValues[problem.id].n_levels = Math.max(minimum, Math.min(maximum, Number.parseInt(event.target.value, 10) || Number(nField.default || 4)));
      const existing = state.fermionValues[problem.id].epsilon;
      while (existing.length < state.fermionValues[problem.id].n_levels) existing.push(existing.length);
      state.fermionValues[problem.id].epsilon = existing.slice(0, state.fermionValues[problem.id].n_levels);
      renderFermionDynamicFields(problem.id);
    });
  }
  for (let index = 0; index < values.n_levels; index += 1) {
    $("fermionEpsilon" + index).addEventListener("input", captureFermionValues);
  }
  $("fermionG").addEventListener("input", captureFermionValues);
  if ($("fermionPairs") && !$("fermionPairs").disabled) {
    $("fermionPairs").addEventListener("change", event => {
      const pairs = Number.parseInt(event.target.value, 10) || 2;
      state.fermionValues[problem.id].n_pairs = pairs;
      $("fermionParticles").value = 2 * pairs;
    });
  }
  $("fermionUnit").addEventListener("input", captureFermionValues);
}

function captureFermionValues() {
  const problem = fermionProblemById(state.fermionProblem);
  if (!problem || !$("fermionLevels")) return;
  const nLevels = Number.parseInt($("fermionLevels").value, 10);
  const epsilon = Array.from({ length: nLevels }, (_, index) => Number($("fermionEpsilon" + index)?.value));
  state.fermionValues[problem.id] = {
    n_levels: nLevels, epsilon,
    g: Number($("fermionG")?.value),
    energy_unit: String($("fermionUnit")?.value || "MeV"),
    n_pairs: Number.parseInt($("fermionPairs")?.value, 10) || Number(problem.fields?.n_pairs?.fixed_value ?? 1),
  };
}

function renderModelCards() {
  const root = $("modelCards");
  root.innerHTML = "";
  for (const model of state.catalog.model_families.filter(item => item.top_level !== false)) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `model-card ${model.id === state.modelFamily ? "active" : ""}`;
    button.dataset.model = model.id;
    button.innerHTML = `<strong>${esc(model.label)}</strong><small>${esc(model.description)}</small><span class="support">${esc(model.support_status.replaceAll("_", " "))}</span>`;
    button.addEventListener("click", () => selectModel(model.id));
    root.appendChild(button);
  }
}

function selectModel(id) {
  state.modelFamily = id;
  renderModelCards();
  setHidden("fermionFields", id !== "fermion_pairing");
  setHidden("oscillatorFields", id !== "oscillator");
  setHidden("customFields", id !== "custom");
  const model = modelById(id);
  const review = model.review ? ` Owner: ${model.review.model_owner}; scientific review: ${model.review.scientific_review_status}.` : "";
  $("modelSupportNote").textContent = `${model.description}${review}`;
  renderTaskOptions();
  renderScientificCoreInspector();
  if (id === "fermion_pairing") {
    selectFermionRoute(state.fermionRoute);
  } else {
    if (id === "oscillator" && $("qhoDynamicFields")) renderQhoDynamicFields(state.oscillatorModel);
    $("buildRunButton").textContent = "Build & Run";
    $("buildRunButton").title = "Build the selected model and run its declared task through the shared pipeline.";
  }
}

function isSpinOrbitalRoute() {
  return state.modelFamily === "fermion_pairing" && ["general_spin_orbital", "mapping_explorer"].includes(state.fermionRoute);
}

function configureSpinTaskControls() {
  if (!isSpinOrbitalRoute() || !$("spinModes")) return;
  const analysis = state.taskId === "mapping_analysis";
  $("spinModes").max = analysis ? "8" : "4";
  $("spinTargetParticles").min = analysis ? "0" : "1";
  $("spinInitialOccupied").disabled = analysis;
  $("spinAnsatzLayers").disabled = analysis;
  $("spinCoefficientThreshold").disabled = !analysis;
  $("spinEquivalenceTolerance").disabled = !analysis;
  $("mappingJW").checked = true;
  $("mappingJW").disabled = !analysis;
  $("mappingBK").checked = analysis;
  $("mappingBK").disabled = !analysis;
  const boundary = $("spinExecutionBoundary");
  if (boundary) {
    boundary.innerHTML = analysis
      ? `<strong>Mapping analysis</strong><span>JW and BK transformation/resource analysis · no circuit, shots, or backend.</span>`
      : `<strong>JW ground-state execution · acceptance verified</strong><span>2–4 modes · fixed particle number · JW occupation determinant · mapped-fermionic swap-network ansatz · exact bounded reference. BK remains analysis only.</span>`;
  }
}

function currentModelContractId() {
  if (state.modelFamily === "fermion_pairing") {
    if (isSpinOrbitalRoute()) return "fermion.general_spin_orbital";
    return ["four_level_one_pair", "one_pair_pairing"].includes(state.fermionProblem)
      ? "nuclear.reduced_pairing.one_pair"
      : "nuclear.reduced_pairing.multi_pair";
  }
  if (state.modelFamily === "oscillator") {
    return state.oscillatorModel || modelById("oscillator")?.default_model_id || "nuclear.qho.free";
  }
  return state.customRoute === "guided"
    ? "custom.occupation_coupling.one_excitation"
    : "custom.qubit_hamiltonian";
}

function scientificCoreById(modelId) {
  const rows = state.catalog?.scientific_core?.models || [];
  return rows.find(item => item.model_id === modelId) || null;
}

function renderScientificCoreInspector() {
  const root = $("scientificCoreInspector");
  if (!root) return;
  const modelId = currentModelContractId();
  const view = scientificCoreById(modelId);
  if (!view) {
    root.innerHTML = `<div class="empty-state">Scientific core unavailable for ${esc(modelId)}.</div>`;
    return;
  }
  const core = view.scientific_core?.model_contract || {};
  const value = key => core[key]?.value;
  const format = item => {
    if (Array.isArray(item)) return item.map(esc).join(", ");
    if (item && typeof item === "object") return `<code>${esc(JSON.stringify(item))}</code>`;
    return esc(item ?? "—");
  };
  const rows = [
    ["Physical phenomenon", value("physical_phenomenon")],
    ["Degrees of freedom", value("degrees_of_freedom")],
    ["Representation", value("representation")],
    ["Hamiltonian components", value("hamiltonian_components")],
    ["Sector / symmetries", value("sector_symmetries")],
    ["Encoding / mapping", value("encoding_mapping")],
    ["Supported realizations", value("supported_realizations")],
  ];
  root.innerHTML = `
    <div class="semantic-boundary-note"><strong>${esc(view.user_view?.group_label || "Model")}</strong> is navigation only. The values below come from ModelContract and resolved-policy owners.</div>
    <div class="scientific-core-grid">${rows.map(([label,item]) => `<div><span>${esc(label)}</span><strong>${format(item)}</strong></div>`).join("")}</div>`;
}

function taskContracts() {
  return state.catalog?.task_contract_registry?.tasks || [];
}

function modelTaskCells() {
  return state.catalog?.model_task_matrix?.cells || [];
}


function realizationCells() {
  return state.realizationCatalog?.cells || [];
}

function modelLabel(modelId) {
  const contracts = state.catalog?.model_contract_registry?.contracts || [];
  return contracts.find(item => item.model_id === modelId)?.label || modelId;
}

function taskLabel(taskId) {
  return taskContracts().find(item => item.task_id === taskId)?.label || taskId;
}

function cellStatusClass(status) {
  return String(status || "waiting").toLowerCase().replaceAll(" ", "_");
}

function badgeStatusClass(status) {
  const value = cellStatusClass(status);
  if (["acceptance_verified", "verified", "execution_ready", "executable"].includes(value)) return "completed";
  if (["experimental", "review", "unresolved", "recognized_not_executable", "planned"].includes(value)) return "review";
  if (["failed", "rejected", "not_verified", "unsupported"].includes(value)) return "failed";
  return "waiting";
}

function variantVisualClass(variant) {
  if (variant.composition_status === "failed") return "failed";
  if (["unresolved", "recognized_not_executable"].includes(variant.composition_status) || variant.runtime_status === "recognized_not_executable") return "unresolved";
  if (["review", "experimental"].includes(variant.composition_status) || variant.cell_status === "experimental") return "review";
  if (variant.runnable) return "runnable";
  return "";
}

function variantCardHtml(variant) {
  const visual = variantVisualClass(variant);
  const routeLabel = variant.runnable
    ? (variant.runtime_path === "analysis_controller" ? "analysis only" : "runnable")
    : (variant.historical ? "historical rejection" : "not executable");
  const failure = variant.failure_code
    ? `<div class="variant-failure"><code>${esc(variant.failure_code)}</code>${esc(variant.failure_message || "The declared realization failed a scientific compatibility rule.")}</div>`
    : "";
  const action = variant.suggested_action
    ? `<div class="variant-action"><strong>Allowed next action:</strong> ${esc(variant.suggested_action)}</div>`
    : "";
  const limitations = (variant.limitations || []).length
    ? `<ul class="variant-limitations">${variant.limitations.map(item => `<li>${esc(item)}</li>`).join("")}</ul>`
    : "";
  const policyLine = [
    variant.mapping_id ? `mapping: ${variant.mapping_id}` : null,
    variant.ansatz_policy_id ? `ansatz: ${variant.ansatz_policy_id}` : null,
    variant.reference_policy_id ? `reference: ${variant.reference_policy_id}` : null,
  ].filter(Boolean).join(" · ");
  return `<article class="realization-variant-card ${visual}">
    <div class="variant-card-head"><strong>${esc(variant.label)}</strong><span class="variant-route-badge">${esc(routeLabel)}</span></div>
    <div class="variant-status-grid">
      <div><span>mapper</span><strong>${esc(variant.mapper_status)}</strong></div>
      <div><span>composition</span><strong>${esc(variant.composition_status)}</strong></div>
      <div><span>cell</span><strong>${esc(variant.cell_status)}</strong></div>
    </div>
    ${variant.default_for_cell ? '<div class="variant-default-note">Default realization for this Model × Task cell.</div>' : ''}
    ${policyLine ? `<div class="variant-policy-line">${esc(policyLine)}</div>` : ''}
    <div class="variant-scope"><strong>Declared scope:</strong> ${esc(variant.support_scope || "—")}</div>
    ${failure}${action}${limitations}
  </article>`;
}

function renderVariantDrawer(cell) {
  if (!cell) {
    $("selectedCellTitle").textContent = "Choose a Model × Task cell";
    $("selectedCellNote").textContent = "Mappings, state preparation, ansatz, reference, and acceptance remain internal realization records.";
    $("selectedCellStatus").textContent = "waiting";
    $("selectedCellStatus").className = "status-badge waiting";
    $("realizationVariantGrid").innerHTML = '<div class="empty-state">Select a cell in the matrix to inspect its realization variants.</div>';
    return;
  }
  $("selectedCellTitle").textContent = `${modelLabel(cell.model_id)} × ${taskLabel(cell.task_id)}`;
  $("selectedCellNote").textContent = `${cell.cell_label} · ${cell.variant_count} internal realization variant${cell.variant_count === 1 ? "" : "s"}.`;
  $("selectedCellStatus").textContent = cell.cell_status;
  $("selectedCellStatus").className = `status-badge ${badgeStatusClass(cell.cell_status)}`;
  $("realizationVariantGrid").innerHTML = (cell.variants || []).map(variantCardHtml).join("") || '<div class="empty-state">No realization variants are registered for this cell.</div>';
}

function selectMatrixCell(modelId, taskId) {
  const cellId = `${modelId}::${taskId}`;
  state.selectedCellId = cellId;
  document.querySelectorAll(".matrix-cell-button").forEach(node => {
    node.classList.toggle("selected", node.dataset.cellId === cellId);
  });
  renderVariantDrawer(realizationCells().find(item => item.cell_id === cellId));
}

function renderCapabilityMatrix() {
  const table = $("capabilityMatrix");
  if (!table || !state.catalog?.model_task_matrix) return;
  const matrix = state.catalog.model_task_matrix;
  const cells = Object.fromEntries((matrix.cells || []).map(item => [item.cell_id, item]));
  const columns = matrix.columns || [];
  const rows = matrix.rows || [];
  table.querySelector("thead").innerHTML = `<tr><th>Model \ Task</th>${columns.map(task => `<th>${esc(taskLabel(task))}</th>`).join("")}</tr>`;
  table.querySelector("tbody").innerHTML = rows.map(model => {
    const rowCells = columns.map(task => {
      const cell = cells[`${model}::${task}`];
      if (!cell) return '<td><span class="muted">—</span></td>';
      const variants = cell.realization_variants || {};
      return `<td><button type="button" class="matrix-cell-button ${cellStatusClass(cell.status)}" data-cell-id="${esc(cell.cell_id)}" data-model-id="${esc(model)}" data-task-id="${esc(task)}">
        <strong>${esc(cell.status.replaceAll("_", " "))}</strong>
        <span class="matrix-cell-meta"><span>${esc(variants.variant_count ?? 0)} variants</span><span>${esc(variants.runnable_variant_count ?? 0)} runnable</span></span>
      </button></td>`;
    }).join("");
    return `<tr><td class="row-label">${esc(modelLabel(model))}</td>${rowCells}</tr>`;
  }).join("");
  table.querySelectorAll(".matrix-cell-button").forEach(button => {
    button.addEventListener("click", () => selectMatrixCell(button.dataset.modelId, button.dataset.taskId));
  });
}

function syncMatrixSelection() {
  if (!state.realizationCatalog) return;
  const modelId = currentModelContractId();
  const taskId = state.taskId || "ground_state_energy";
  const exact = realizationCells().find(item => item.model_id === modelId && item.task_id === taskId);
  const fallback = exact || realizationCells().find(item => item.model_id === modelId) || realizationCells()[0];
  if (fallback) selectMatrixCell(fallback.model_id, fallback.task_id);
}

function renderActiveRealization(display, artifact, result, snapshot) {
  const node = $("activeRealizationStrip");
  if (!node) return;
  const publicView = display?.realization || null;
  const scientific = display?.scientific_realization || null;
  const modelId = scientific?.model_id || publicView?.model_id || null;
  const taskId = scientific?.task_id || publicView?.task_id || result?.task_id || null;
  const cell = realizationCells().find(item => item.model_id === modelId && item.task_id === taskId);
  const activeVariants = publicView?.active_variants || [];
  if (activeVariants.length > 1) {
    node.innerHTML = `<strong>${esc(activeVariants.map(item => item.mapping_label).join(" + "))}</strong><span>analysis-only realization variants</span><span>cell ${esc(publicView.cell_status || cell?.cell_status || "—")}</span>`;
    return;
  }
  const variantId = activeVariants[0]?.variant_id || publicView?.default_variant_id || cell?.default_variant_id;
  const variant = activeVariants[0] || (variantId ? state.realizationCatalog?.variant_index?.[variantId] : null);
  if (!cell || !variant) {
    node.innerHTML = '<strong>Resolved realization</strong><span>available after model/task resolution</span>';
    return;
  }
  node.innerHTML = `<strong>${esc(variant.mapping_label)} realization</strong><span>mapper ${esc(variant.mapper_status)}</span><span>composition ${esc(variant.composition_status)}</span><span>cell ${esc(variant.cell_status)}</span><span>${variant.runnable ? "shared runtime" : "not runnable"}</span>`;
}

function renderTaskOptions() {
  const select = $("taskId");
  if (!select) return;
  const modelId = currentModelContractId();
  const runnable = modelTaskCells().filter(cell => cell.model_id === modelId && cell.runnable);
  const contracts = taskContracts();
  const options = runnable.map(cell => {
    const contract = contracts.find(task => task.task_id === cell.task_id);
    return {
      id: cell.task_id,
      label: contract?.label || cell.task_id,
      status: cell.status,
      note: cell.label,
    };
  });
  if (!options.length) {
    select.innerHTML = `<option value="">No executable task for this model</option>`;
    state.taskId = "";
    $("taskSupportNote").textContent = "This model route is recognized but has no runnable task cell.";
    return;
  }
  if (!options.some(item => item.id === state.taskId)) state.taskId = options[0].id;
  select.innerHTML = options.map(item => `<option value="${esc(item.id)}">${esc(item.label)} · ${esc(item.status.replaceAll("_", " "))}</option>`).join("");
  select.value = state.taskId;
  const selected = options.find(item => item.id === state.taskId) || options[0];
  $("taskSupportNote").textContent = selected.note;
  const observable = state.taskId === "observable_estimation";
  const mappingAnalysis = state.taskId === "mapping_analysis";
  $("runMode").value = (observable || mappingAnalysis) ? "single_evaluation" : ($("runMode").value || "vqe");
  $("runMode").disabled = observable || mappingAnalysis;
  $("maxEvaluations").disabled = observable || mappingAnalysis;
  $("energyTolerance").disabled = observable || mappingAnalysis;
  $("acceptanceFloor").disabled = mappingAnalysis;
  $("shots").disabled = mappingAnalysis;
  $("seed").disabled = mappingAnalysis;
  $("initialParameters").disabled = mappingAnalysis;
  $("targetBackend").disabled = mappingAnalysis;
  $("buildRunButton").textContent = mappingAnalysis
    ? "Build & analyze JW / BK"
    : (isSpinOrbitalRoute() ? "Build & Run JW ground state" : "Build & Run");
  configureSpinTaskControls();
  syncMatrixSelection();
}


function qhoSchemaById(modelId) {
  const family = modelById("oscillator");
  return (family?.models || []).find(item => item.model_id === modelId) || null;
}

function qhoFieldId(key) {
  return `qhoParam-${String(key).replaceAll("_", "-")}`;
}

function qhoContractHtml(schema) {
  const fixed = Object.entries(schema.fixed_parameters || {})
    .map(([key, value]) => `<span><strong>${esc(key)}:</strong> ${esc(list(value))}</span>`)
    .join("");
  const policies = schema.policies || {};
  return `<div class="problem-contract qho-contract">
    <div class="contract-heading"><strong>${esc(schema.label)}</strong><span>${esc(String(schema.execution_status || "registered").replaceAll("_", " "))}</span></div>
    <p>${esc(schema.description)}</p>
    <div class="mapping-declaration">
      <strong>Shared realization family — selected by the ModelContract</strong>
      <span>${esc(policies.mapping)} · ${esc(policies.ansatz)}</span>
      <small>Fields below are generated from parameter_schema. Fixed interactions remain in the contract and are not editable.</small>
    </div>
    ${fixed ? `<div class="contract-fixed">${fixed}</div>` : ""}
    <small>Reference: ${esc(policies.reference)} · Cell status: ${esc(schema.execution_status)} · no separate runtime.</small>
  </div>`;
}

function qhoFieldHtml(spec) {
  if (!spec.render) return "";
  const id = qhoFieldId(spec.key);
  const attrs = [
    spec.minimum !== null && spec.minimum !== undefined ? `min="${esc(spec.minimum)}"` : "",
    spec.maximum !== null && spec.maximum !== undefined ? `max="${esc(spec.maximum)}"` : "",
    spec.step !== null && spec.step !== undefined ? `step="${esc(spec.step)}"` : "",
  ].filter(Boolean).join(" ");
  const inputType = ["integer", "number"].includes(spec.ui_input_kind) ? "number" : "text";
  const defaultValue = spec.default_display ?? spec.default ?? "";
  return `<label data-qho-field="${esc(spec.key)}"><span>${esc(spec.label)}</span><input id="${esc(id)}" data-qho-key="${esc(spec.key)}" data-qho-kind="${esc(spec.kind)}" type="${inputType}" ${attrs} value="${esc(defaultValue)}"><small>${esc(spec.help_text || "Declared by the selected ModelContract.")}</small></label>`;
}

function renderQhoDynamicFields(modelId) {
  const family = modelById("oscillator");
  const schema = qhoSchemaById(modelId || family?.default_model_id);
  if (!schema) throw new Error(`Unknown QHO ModelContract: ${modelId}`);
  state.oscillatorModel = schema.model_id;
  renderScientificCoreInspector();
  const select = $("oscillatorProblem");
  if (select) select.value = schema.model_id;
  const fields = (schema.parameter_fields || []).filter(item => item.render).map(qhoFieldHtml).join("");
  $("qhoDynamicFields").innerHTML = `${qhoContractHtml(schema)}<div class="form-grid two-columns">${fields}</div>`;
  renderTaskOptions();
  syncMatrixSelection();
}

function parseQhoField(spec) {
  const node = $(qhoFieldId(spec.key));
  if (!node) throw new Error(`Missing schema-generated QHO input: ${spec.key}`);
  const raw = String(node.value ?? "").trim();
  if (!raw) throw new Error(`${spec.label} must not be empty.`);
  if (spec.kind === "integer") {
    const value = Number.parseInt(raw, 10);
    if (!Number.isInteger(value)) throw new Error(`${spec.label} must be an integer.`);
    return value;
  }
  if (spec.kind === "number") {
    const value = Number(raw);
    if (!Number.isFinite(value)) throw new Error(`${spec.label} must be finite.`);
    return value;
  }
  if (spec.kind === "vector_or_scalar") {
    if (raw.startsWith("[")) {
      const decoded = JSON.parse(raw);
      if (!Array.isArray(decoded) || decoded.some(item => Array.isArray(item))) throw new Error(`${spec.label} must be a scalar or one-dimensional vector.`);
      const values = decoded.map(Number);
      if (!values.length || values.some(item => !Number.isFinite(item))) throw new Error(`${spec.label} contains an invalid value.`);
      return values.length === 1 ? values[0] : values;
    }
    const values = raw.split(",").map(item => item.trim()).filter(Boolean).map(Number);
    if (!values.length || values.some(item => !Number.isFinite(item))) throw new Error(`${spec.label} contains an invalid value.`);
    return values.length === 1 ? values[0] : values;
  }
  if (spec.kind === "matrix_or_scalar") {
    if (raw.startsWith("[")) {
      const decoded = JSON.parse(raw);
      if (typeof decoded === "number") return decoded;
      if (!Array.isArray(decoded) || decoded.some(row => !Array.isArray(row))) throw new Error(`${spec.label} must be a scalar or matrix.`);
      return decoded.map(row => row.map(Number));
    }
    const scalar = Number(raw);
    if (!Number.isFinite(scalar)) throw new Error(`${spec.label} must be a scalar or JSON matrix.`);
    return scalar;
  }
  return raw;
}

function collectQhoParameters() {
  const schema = qhoSchemaById(state.oscillatorModel);
  if (!schema) throw new Error("Choose a registered QHO ModelContract.");
  const parameters = {};
  for (const spec of schema.parameter_fields || []) {
    if (spec.render) parameters[spec.key] = parseQhoField(spec);
  }
  return parameters;
}

function renderForms() {
  const fermion = modelById("fermion_pairing");
  state.fermionProblem = fermion.default_problem || fermion.problems[0].id;
  const nestedRoutes = fermion.nested_routes || [
    {id:"reduced_pairing", label:"Reduced-pairing model contracts"},
    {id:"general_spin_orbital", label:"General spin-orbital — Mapping Explorer / JW ground state"},
  ];
  $("fermionFields").innerHTML = `
    <div class="form-grid">
      <label><span>Supported fermionic route</span><select id="fermionRoute">${nestedRoutes.map(route => `<option value="${esc(route.id)}">${esc(route.label)}</option>`).join("")}</select></label>
      <div id="pairingRouteFields">
        <label><span>Supported physical problem</span><select id="fermionProblem">${fermion.problems.map(p => `<option value="${esc(p.id)}">${esc(p.label)}</option>`).join("")}</select></label>
        <div id="fermionDynamicFields"></div>
      </div>
      <div id="spinFields" class="model-fields hidden"></div>
    </div>`;
  $("fermionRoute").addEventListener("change", event => selectFermionRoute(event.target.value));
  $("fermionProblem").addEventListener("change", event => {
    captureFermionValues();
    renderFermionDynamicFields(event.target.value);
  });
  renderFermionDynamicFields(state.fermionProblem);

  const spin = modelById("general_spin_orbital");
  $("spinFields").innerHTML = `
    <div class="problem-contract mapping-contract">
      <div class="contract-heading"><strong>${esc(spin.label)}</strong><span>analysis verified · JW execution experimental</span></div>
      <p>${esc(spin.description)}</p>
      <div class="mapping-declaration"><strong>Mapping and execution boundary</strong><span>Jordan–Wigner · Bravyi–Kitaev</span><small>Both are verified for transformation/analysis. The first bounded execution cell is JW-only; BK full execution is not enabled.</small></div>
      <div id="spinExecutionBoundary" class="mapping-declaration"></div>
    </div>
    <div class="form-grid two-columns">
      <label><span>Number of spin-orbital modes</span><input id="spinModes" type="number" min="2" max="8" value="${spin.defaults.n_modes}"></label>
      <label><span>Particle species</span><input id="spinSpecies" value="${esc(spin.defaults.particle_species)}"></label>
      <label><span>Target particle number</span><input id="spinTargetParticles" type="number" min="0" value="${spin.defaults.target_particle_number}"></label>
      <label><span>Energy unit</span><input id="spinUnit" value="${esc(spin.defaults.energy_unit)}"></label>
      <label><span>Initial occupied modes (optional)</span><input id="spinInitialOccupied" value="${esc(spin.defaults.initial_occupied_modes || "")}" placeholder="e.g. 0,1"></label>
      <label><span>JW ansatz layers</span><input id="spinAnsatzLayers" type="number" min="1" max="2" value="${spin.defaults.ansatz_layers || 1}"></label>
      <label style="grid-column:1/-1"><span>Mode labels — one per line: species | orbital | projection</span><textarea id="spinModeLabels">${esc(spin.defaults.mode_labels)}</textarea></label>
      <label style="grid-column:1/-1"><span>One-body terms — p, q, coefficient</span><textarea id="spinOneBody">${esc(spin.defaults.one_body_terms)}</textarea></label>
      <label style="grid-column:1/-1"><span>Two-body terms — p, q, r, s, coefficient</span><textarea id="spinTwoBody">${esc(spin.defaults.two_body_terms)}</textarea></label>
      <label><span>Declared symmetries</span><input id="spinSymmetries" value="${esc(spin.defaults.declared_symmetries)}"></label>
      <label><span>Coefficient convention</span><select id="spinConvention"><option value="explicit_operator_coefficient">Explicit operator coefficient</option><option value="antisymmetrized_v_with_quarter_prefactor">Antisymmetrized V with 1/4 prefactor</option></select></label>
    </div>
    <div class="mapping-choice-grid">
      <label><input id="mappingJW" type="checkbox" checked> <strong>Jordan–Wigner</strong><small>analysis verified · bounded ground-state execution: acceptance verified</small></label>
      <label><input id="mappingBK" type="checkbox" checked> <strong>Bravyi–Kitaev</strong><small>analysis verified · ground-state execution: not executable</small></label>
    </div>
    <div class="form-grid two-columns">
      <label><span>Resource coefficient threshold</span><input id="spinCoefficientThreshold" type="number" min="0" step="1e-12" value="1e-12"></label>
      <label><span>Equivalence tolerance</span><input id="spinEquivalenceTolerance" type="number" min="1e-12" step="1e-9" value="1e-8"></label>
    </div>`;

  const osc = modelById("oscillator");
  state.oscillatorModel = state.oscillatorModel || osc.default_model_id || osc.models?.[0]?.model_id;
  $("oscillatorFields").innerHTML = `
    <div class="form-grid">
      <label><span>Physical model</span><select id="oscillatorProblem">${(osc.models || []).map(item => `<option value="${esc(item.model_id)}">${esc(item.label)}</option>`).join("")}</select></label>
      <div id="qhoDynamicFields"></div>
    </div>`;
  $("oscillatorProblem").addEventListener("change", event => renderQhoDynamicFields(event.target.value));
  renderQhoDynamicFields(state.oscillatorModel);

  const custom = modelById("custom");
  $("customFields").innerHTML = `
    <div class="form-grid">
      <label><span>Custom route</span><select id="customRoute">${custom.routes.map(r => `<option value="${esc(r.id)}">${esc(r.label)}</option>`).join("")}</select></label>
      <div id="customGuided" class="form-grid two-columns">
        <label style="grid-column:1/-1"><span>Model name</span><input id="customModelName" value="${esc(custom.defaults.model_name)}"></label>
        <label><span>Number of modes / levels</span><input id="customModes" type="number" min="1" value="${custom.defaults.n_modes}"></label>
        <label><span>Energy offset</span><input id="customOffset" type="number" step="0.01" value="${custom.defaults.energy_offset}"></label>
        <label style="grid-column:1/-1"><span>Onsite energies</span><input id="customOnsite" value="${esc(custom.defaults.onsite_energies)}"></label>
        <label style="grid-column:1/-1"><span>Pairwise couplings — one line: i, j, G</span><textarea id="customCouplings">${esc(custom.defaults.couplings)}</textarea></label>
      </div>
      <div id="customMatrix" class="hidden"><label><span>Dense Hermitian matrix</span><textarea id="customMatrixText">${esc(custom.defaults.matrix)}</textarea></label></div>
      <div id="customPauli" class="hidden"><label><span>Pauli terms</span><textarea id="customPauliText">${esc(custom.defaults.pauli_terms)}</textarea></label></div>
      <div class="form-grid two-columns">
        <label><span>Number of qubits (Pauli route)</span><input id="customQubits" type="number" min="1" value="${custom.defaults.n_qubits}"></label>
        <label><span>Ansatz layers</span><input id="customLayers" type="number" min="1" value="${custom.defaults.ansatz_layers}"></label>
        <label><span>Energy unit</span><input id="customUnit" value="${esc(custom.defaults.energy_unit)}"></label>
      </div>
    </div>`;
  $("customRoute").addEventListener("change", event => selectCustomRoute(event.target.value));
}

function selectFermionRoute(route) {
  state.fermionRoute = route;
  renderScientificCoreInspector();
  const spinRoute = ["general_spin_orbital", "mapping_explorer"].includes(route);
  setHidden("pairingRouteFields", spinRoute);
  setHidden("spinFields", !spinRoute);
  const routeSelect = $("fermionRoute");
  if (routeSelect) routeSelect.value = route;
  state.taskId = spinRoute ? "mapping_analysis" : "ground_state_energy";
  renderTaskOptions();
  $("buildRunButton").textContent = spinRoute ? "Build & analyze JW / BK" : "Build & Run";
  $("buildRunButton").title = spinRoute
    ? "Choose mapping analysis or the bounded JW ground-state execution task."
    : "Build the selected reduced-pairing model and run its accepted task.";
  const fermion = modelById("fermion_pairing");
  const routeInfo = (fermion?.nested_routes || []).find(item => item.id === route);
  $("modelSupportNote").textContent = routeInfo?.description || fermion?.description || "";
}

function selectCustomRoute(route) {
  state.customRoute = route;
  renderScientificCoreInspector();
  setHidden("customGuided", route !== "guided");
  setHidden("customMatrix", route !== "matrix");
  setHidden("customPauli", route !== "pauli");
  renderTaskOptions();
  syncMatrixSelection();
}

function buildRequest() {
  const runMode = value("runMode");
  const shots = intValue("shots");
  const maxEvaluations = intValue("maxEvaluations");
  const energyTolerance = floatValue("energyTolerance");
  const acceptanceFloor = floatValue("acceptanceFloor");
  const seed = intValue("seed");
  const spinRoute = isSpinOrbitalRoute();
  const mappingAnalysis = spinRoute && state.taskId === "mapping_analysis";
  if (!mappingAnalysis && (!Number.isInteger(shots) || shots < 1)) throw new Error("Shots must be a positive integer.");
  if (!mappingAnalysis && (!Number.isInteger(maxEvaluations) || maxEvaluations < 1)) throw new Error("Maximum evaluations must be positive.");
  if (!state.taskId) throw new Error("No executable task is available for the selected model route.");
  const request = {
    method: spinRoute ? "general_spin_orbital" : state.modelFamily,
    task_id: state.taskId,
    target_backend: value("targetBackend"),
    execution_mode: "local_simulator",
    run_mode: runMode,
    shots,
    final_shots: shots,
    max_evaluations: maxEvaluations,
    energy_tolerance: energyTolerance,
    acceptance_abs_floor: acceptanceFloor,
    seed,
    interface_mode: "guided_no_code",
    model_family_label: spinRoute
      ? "Fermionic nuclear system · General spin-orbital representation"
      : modelById(state.modelFamily).label,
  };
  const initial = floatList(value("initialParameters"), "Initial θ", true);
  if (initial) request.initial_parameters = initial;
  if (state.taskId === "observable_estimation") {
    request.run_mode = "single_evaluation";
    request.requested_observables = ["pair_occupations"];
    request.task_parameters = {
      state_source: "acceptance_fixture",
      observable_ids: ["pair_occupations"],
      observable_abs_floor: 0.03,
      sector_leakage_floor: 0.01,
    };
  }

  if (state.modelFamily === "fermion_pairing" && !spinRoute) {
    captureFermionValues();
    const problem = fermionProblemById(state.fermionProblem);
    if (!problem) throw new Error("Choose a registered fermion problem.");
    const fields = schemaFields(problem);
    const values = state.fermionValues[problem.id];
    if (!values || values.epsilon.length !== values.n_levels) throw new Error("The problem schema requires one ε value per level.");
    if (values.epsilon.some(item => !Number.isFinite(item))) throw new Error("Every ε value must be finite.");
    request.problem = problem.id;
    request.parameters = {
      n_levels: values.n_levels,
      epsilon: values.epsilon,
      g: values.g,
      n_pairs: Number(values.n_pairs ?? fields.n_pairs.fixed_value ?? fields.n_pairs.default ?? 1),
      n_particles: 2 * Number(values.n_pairs ?? fields.n_pairs.fixed_value ?? fields.n_pairs.default ?? 1),
      seniority: Number(fields.seniority.fixed_value),
      mapping: String(fields.mapping.fixed_value),
      energy_unit: values.energy_unit.trim() || "MeV",
    };
    request.problem_contract = {
      problem_id: problem.id,
      schema_version: problem.schema_version,
      support_status: problem.support_status,
      execution_status: problem.execution_status,
    };
  } else if (spinRoute) {
    const nModes = intValue("spinModes");
    const targetParticles = intValue("spinTargetParticles");
    const maximumModes = mappingAnalysis ? 8 : 4;
    if (!Number.isInteger(nModes) || nModes < 2 || nModes > maximumModes) {
      throw new Error(`${mappingAnalysis ? "Mapping analysis" : "The JW execution cell"} supports 2–${maximumModes} spin-orbital modes.`);
    }
    const minimumParticles = mappingAnalysis ? 0 : 1;
    const maximumParticles = mappingAnalysis ? nModes : nModes - 1;
    if (!Number.isInteger(targetParticles) || targetParticles < minimumParticles || targetParticles > maximumParticles) {
      throw new Error(`Target particle number must lie between ${minimumParticles} and ${maximumParticles} for this task.`);
    }
    const labels = value("spinModeLabels").split(/\r?\n/).map(item => item.trim()).filter(Boolean);
    if (labels.length !== nModes) throw new Error(`Mode labels must contain exactly ${nModes} non-empty lines.`);
    request.parameters = {
      n_modes: nModes,
      particle_species: value("spinSpecies").trim() || "fermion",
      mode_labels: value("spinModeLabels"),
      one_body_terms: value("spinOneBody"),
      two_body_terms: value("spinTwoBody"),
      target_particle_number: targetParticles,
      initial_occupied_modes: value("spinInitialOccupied").trim(),
      ansatz_layers: intValue("spinAnsatzLayers"),
      declared_symmetries: value("spinSymmetries").split(",").map(item => item.trim()).filter(Boolean),
      coefficient_convention: value("spinConvention"),
      energy_unit: value("spinUnit").trim() || "unspecified",
    };
    if (mappingAnalysis) {
      const mappingIds = [];
      if ($("mappingJW")?.checked) mappingIds.push("jordan_wigner.v1");
      if ($("mappingBK")?.checked) mappingIds.push("bravyi_kitaev.v1");
      if (!mappingIds.length) throw new Error("Select at least one registered mapping plugin.");
      request.problem = "mapping_explorer";
      request.run_mode = "mapping_analysis";
      request.execution_mode = "analysis_only";
      request.target_backend = "none";
      request.shots = 0; request.final_shots = 0; request.max_evaluations = 1;
      request.task_parameters = {
        mapping_ids: mappingIds,
        coefficient_threshold: floatValue("spinCoefficientThreshold"),
        equivalence_tolerance: floatValue("spinEquivalenceTolerance"),
      };
      request.requested_observables = ["mapping_resources", "mapping_equivalence"];
    } else {
      if (intValue("spinAnsatzLayers") < 1 || intValue("spinAnsatzLayers") > 2) {
        throw new Error("The bounded JW execution cell supports one or two ansatz layers.");
      }
      request.problem = "jw_ground_state";
      request.execution_mode = "local_simulator";
      request.mapping_id = "jordan_wigner.v1";
      request.sector_leakage_floor = 1e-10;
      request.requested_observables = ["sector_energy", "particle_number"];
    }
  } else if (state.modelFamily === "oscillator") {
    const schema = qhoSchemaById(state.oscillatorModel);
    if (!schema) throw new Error("Choose a registered QHO ModelContract.");
    request.model_id = schema.model_id;
    request.problem = schema.model_id;
    request.parameters = collectQhoParameters();
    request.problem_contract = {
      model_id: schema.model_id,
      model_version: schema.model_version,
      schema_version: schema.schema_version,
      execution_status: schema.execution_status,
      rendered_parameter_keys: schema.rendered_parameter_keys,
    };
  } else {
    if (state.customRoute === "guided") {
      const nModes = intValue("customModes");
      const onsite = floatList(value("customOnsite"), "Onsite energies");
      if (onsite.length !== nModes) throw new Error(`Entered ${onsite.length} onsite energies but number of modes is ${nModes}.`);
      request.problem = "guided_occupation_model";
      request.parameters = {
        model_name: value("customModelName").trim() || "custom occupation-coupling model",
        n_modes: nModes,
        n_excitations: 1,
        onsite_energies: onsite,
        coupling_matrix: parseCouplingMatrix(value("customCouplings"), nModes),
        energy_offset: floatValue("customOffset"),
        energy_unit: value("customUnit").trim() || "MeV",
      };
    } else if (state.customRoute === "matrix") {
      request.problem = "matrix_input";
      request.parameters = {
        matrix: value("customMatrixText"),
        ansatz_layers: intValue("customLayers"),
        energy_unit: value("customUnit").trim() || "unspecified",
      };
    } else {
      request.problem = "pauli_input";
      request.parameters = {
        pauli_terms: value("customPauliText"),
        n_qubits: intValue("customQubits"),
        ansatz_layers: intValue("customLayers"),
        energy_unit: value("customUnit").trim() || "unspecified",
      };
    }
  }
  return request;
}

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

async function apiJson(url, options = {}) {
  const response = await fetch(url, options);
  let payload = null;
  try { payload = await response.json(); } catch (_) { /* no-op */ }
  if (!response.ok) {
    const detail = payload?.detail;
    let message;
    if (typeof detail === "string") message = detail;
    else if (detail && typeof detail === "object") {
      const field = detail.field ? ` [${detail.field}]` : "";
      message = `${detail.message || "Request contract failed"}${field}`;
    } else message = `${response.status} ${response.statusText}`;
    throw new Error(message);
  }
  return payload;
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

function closeStream() {
  if (state.eventSource) state.eventSource.close();
  state.eventSource = null;
  if (state.reconnectTimer) window.clearTimeout(state.reconnectTimer);
  state.reconnectTimer = null;
}

function connectStream() {
  closeStream();
  if (!state.runId) return;
  const saved = Number(storageGet(`qcol_last_event_${state.runId}`) || state.lastEventId || 0);
  state.lastEventId = saved;
  const source = new EventSource(`/runs/${encodeURIComponent(state.runId)}/stream?after=${saved}`);
  state.eventSource = source;
  const names = ["run_created", "run_status", "journey_state", "artifact_ready", "pipeline_event", "advisor_ready", "cancel_requested", "completed", "cancelled", "failed"];
  for (const name of names) source.addEventListener(name, handleSseEvent);
  source.onopen = () => setApiHealth("live stream connected", "ok");
  source.onerror = async () => {
    if (!state.runId) return;
    try {
      const snapshot = await apiJson(`/runs/${encodeURIComponent(state.runId)}`);
      state.snapshot = snapshot;
      renderSnapshot();
      if (["completed", "cancelled", "failed"].includes(snapshot.status)) {
        closeStream();
        return;
      }
    } catch (_) { /* retry below */ }
    closeStream();
    state.reconnectTimer = window.setTimeout(connectStream, 1800);
  };
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

async function cancelRun() {
  if (!state.runId) return;
  try {
    const snapshot = await apiJson(`/runs/${encodeURIComponent(state.runId)}/cancel`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason: "user_requested_from_phase4_dashboard" }),
    });
    state.snapshot = snapshot;
    renderSnapshot();
  } catch (error) {
    showFormError(error);
  }
}

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
    evidence.classList.remove("disabled"); evidence.removeAttribute("aria-disabled"); evidence.href = comparison.evidence_url;
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
        "Prepare this candidate request? This does not execute it. QCOL will validate the patch, preserve the baseline, and return a candidate for a new POST /runs submission."
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
        "Run this candidate through the same QCOL pipeline and compare its Evidence with the baseline? The outcome may be ADOPT, REJECT, or INCONCLUSIVE; nothing is replaced automatically."
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
    evidence.href = snapshot.evidence_url;
    evidence.classList.remove("disabled");
    evidence.setAttribute("aria-disabled", "false");
  } else {
    evidence.href = "#";
    evidence.classList.add("disabled");
    evidence.setAttribute("aria-disabled", "true");
  }
  renderLedger(display);
}

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
    setApiHealth(`API active · ${health.active_run_count} active`, "ok");
  } catch (error) {
    setApiHealth("API unavailable", "waiting");
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
window.addEventListener("DOMContentLoaded", bootstrap);

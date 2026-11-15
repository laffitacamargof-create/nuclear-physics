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

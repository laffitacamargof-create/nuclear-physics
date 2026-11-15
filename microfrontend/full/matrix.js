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

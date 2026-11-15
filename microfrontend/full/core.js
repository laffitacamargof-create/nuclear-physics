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

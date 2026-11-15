# Quantum app nuclear physics · micro-frontend

Light **connector** (`index.html`, ~33 KB) + heavy parts loaded on demand from this repo.

| File | Role |
|---|---|
| `index.html` | Connector: model/level/pairing selectors, run controls, Build & Run, history, minimal fallback result. Calls `pyCall` and injects the backend result into the modules. |
| `modules/flow.js` | 16-stage workflow (live + replay) |
| `modules/result.js` | Full result view (verdict, metrics, variational-bound banner, details) |
| `modules/chart.js` | Convergence chart + enlarge/zoom |
| `modules/codegen.js` | QASM2 → Qiskit / Cirq / Braket code (simulator or real hardware) |
| `modules/capmap.js` | Model × task capability map |
| `nuclear_logic.py` | Python bridge (only fetched if the compiler lacks `nuclear_run`) |
| `manifest.json` | SHA-256 of every file; the connector embeds the same hashes |

**Security:** the connector pins a commit SHA and verifies SHA-256 before running any module. A failed fetch or hash falls back to the built-in minimal result.
**Data contract:** modules receive the object returned by `nuclear_run` (schema v1) plus `Q` (`$`, `fmt`, `esc`, `cur`, `last`, `HIST`, `setTiles`).
**Update a module:** edit it, commit, then update `PIN` and `HASH` in `index.html`.
**Compiler requirement:** `openqasm3[parser]==1.0.1` (1.0.2 cannot parse OpenQASM 2.0, which breaks `pyqasm`).

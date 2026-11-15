# =============================================================================
#  Quantum app nuclear physics - Python logic
# -----------------------------------------------------------------------------
#  Paste this whole file in the "Python" field of the app.
#  El HTML lo invoca con  pyCall('nuclear_run', modelo, parametros, shots, semilla)
#
#  Que hace: descarga (una vez) el backend publico
#      github.com/laffitacamargof-create/nuclear-physics   (commit fijado)
#  y ejecuta SU pipeline real (OpenFermion -> Cirq -> OpenQASM2 -> PyQASM
#  -> simulador local). No reimplementa fisica: solo llama y resume el resultado.
#
#  Requisitos en el servidor compilador (ademas de numpy/cirq que ya tiene):
#      scipy==1.13.1  openfermion==1.6.1  pyqasm==1.0.4
#  Solo usa simulador local; no se envia nada a hardware cuantico real.
# =============================================================================
import sys, io, json, time, zipfile, tempfile, warnings, importlib.util
import urllib.request
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

BACKEND_REPO = "laffitacamargof-create/nuclear-physics"
BACKEND_COMMIT = "c173be521c786507c16d678498640cb03e6679c6"   # version fijada
BACKEND_PATH = ""      # opcional: ruta local a .../qcol-app-studio-backend
NEEDED = ("numpy", "scipy", "cirq", "openfermion", "pyqasm")
K_SIGMA = 3.0          # k de la prueba variacional unilateral


def _backend_dir():
    if BACKEND_PATH and (Path(BACKEND_PATH) / "qcol" / "__init__.py").exists():
        return Path(BACKEND_PATH)
    root = Path(tempfile.gettempdir()) / ("qcol_nuclear_" + BACKEND_COMMIT[:8])
    hits = list(root.glob("*/qcol-app-studio-backend/qcol/__init__.py"))
    if not hits:
        url = "https://codeload.github.com/%s/zip/%s" % (BACKEND_REPO, BACKEND_COMMIT)
        root.mkdir(parents=True, exist_ok=True)
        tmp_zip = root / "backend.zip"
        urllib.request.urlretrieve(url, str(tmp_zip))
        zipfile.ZipFile(str(tmp_zip)).extractall(str(root))
        hits = list(root.glob("*/qcol-app-studio-backend/qcol/__init__.py"))
    if not hits:
        raise RuntimeError("No se encontro qcol-app-studio-backend en el zip descargado")
    return hits[0].parent.parent


def _ensure_backend():
    missing = [m for m in NEEDED if importlib.util.find_spec(m) is None]
    if missing:
        raise RuntimeError(
            "Faltan librerias en el servidor compilador: " + ", ".join(missing)
            + ". Agregalas a requirements.txt (scipy==1.13.1 openfermion==1.6.1 pyqasm==1.0.4).")
    path = str(_backend_dir())
    if path not in sys.path:
        sys.path.insert(0, path)


def nuclear_warmup():
    """Descarga e importa el backend para que la primera ejecucion real sea rapida."""
    t0 = time.time()
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            warnings.filterwarnings("ignore")
            _ensure_backend()
            from qcol.request_validation import normalize_run_request  # noqa
            from qcol.orchestrator import run_pipeline  # noqa
        return {"success": True, "seconds": round(time.time() - t0, 1)}
    except Exception as e:
        return {"success": False, "error": str(e)[:400]}


def nuclear_run(model_id="nuclear.reduced_pairing.one_pair", params=None,
                shots=1024, seed=42, max_evaluations=60, backend="cirq", target="google"):
    """Corre una celda modelo->VQE->referencia y devuelve un resumen JSON."""
    t0 = time.time()
    buf = io.StringIO()
    try:
        with redirect_stdout(buf), redirect_stderr(io.StringIO()):
            warnings.filterwarnings("ignore")
            _ensure_backend()
            from qcol.request_validation import normalize_run_request
            from qcol.orchestrator import run_pipeline
            req = {"model_id": model_id, "task": "ground_state_energy",
                   "shots": int(shots), "seed": int(seed),
                   "max_evaluations": int(max_evaluations),
                   "target_backend": str(target or "google").lower(),
                   "parameters": dict(params or {})}
            if backend == "aer":
                if importlib.util.find_spec("qiskit_aer") is None:
                    return {"success": False, "error": "Qiskit Aer is not installed on the compiler server (pip install qiskit-aer). Use the Cirq simulator or export the code."}
                from qcol.execution import run_pipeline_with_execution_adapter
                _art, res = run_pipeline_with_execution_adapter(normalize_run_request(req), adapter_id="execution.local_aer.v1")
            else:
                _art, res = run_pipeline(normalize_run_request(req))
        v = dict(res.verification or {})
        E, sig = res.reconstructed_energy, res.standard_error
        ref = v.get("reference_energy")
        out = {
            "success": True, "model_id": model_id,
            "backend_status": v.get("status"),
            "energy": E, "sigma": sig, "reference": ref,
            "threshold": v.get("acceptance_threshold"),
            "abs_error": v.get("absolute_error"),
            "unit": (res.request_summary.get("parameters", {}) or {}).get("energy_unit", ""),
            "shots": int(shots), "seed": int(seed),
            "optimizer": {"name": res.optimizer_name, "evaluations": res.optimizer_evaluations,
                          "converged": bool(res.optimizer_converged)},
            "history": [h.get("energy") for h in res.convergence_history
                        if h.get("energy") is not None],
            "final_parameters": list(res.final_parameters or []),
            "reference_kind": v.get("reference_kind"),
            "sector_checked": bool((v.get("sector_diagnostics") or {}).get("applicable", False)),
            "hardware": bool(res.hardware_submission_performed),
        }
        if E is not None and ref is not None:
            d = float(E) - float(ref)
            s = float(sig or 0.0)
            out["delta_e"] = d
            out["variational_bound"] = {
                "rule": "E >= E_ref - %.0f*sigma" % K_SIGMA,
                "ok": bool(d >= -K_SIGMA * s - 1e-9),
                "below_reference": bool(d < 0),
                "delta_in_sigma": (d / s) if s > 0 else None}
        stages, order = {}, []
        for ev in (getattr(res, "journey_events", None) or []):
            st = ev.get("stage")
            if st not in stages:
                order.append(st)
            met = {}
            for k, v in (ev.get("metrics") or {}).items():
                if isinstance(v, (int, float, str, bool)) and len(met) < 8:
                    met[str(k)] = v if not isinstance(v, str) else v[:60]
            stages[st] = {"stage": st, "title": ev.get("title"), "status": ev.get("status"),
                          "message": str(ev.get("message") or "")[:260], "metrics": met,
                          "updates": stages.get(st, {}).get("updates", 0) + 1}
        out["stages"] = [stages[k] for k in order]
        tc = res.translation_check or {}
        out["circuit"] = {"mapping": str(getattr(_art, "mapping", "") or "")[:80],
                          "n_qubits": getattr(_art, "n_qubits", None),
                          "depth": tc.get("depth_after_unroll"),
                          "method": getattr(_art, "method", None),
                          "target_sector": str(getattr(_art, "target_sector", "") or "")[:80]}
        # datos para exportar el circuito final a otro SDK / hardware real
        groups, acc = [], 0.0
        for rec in (res.raw_records or []):
            terms = [[t.get("term"), t.get("coefficient")] for t in (rec.get("pauli_terms") or [])]
            exps = rec.get("term_expectations") or {}
            for t, c in terms:
                acc += float(c or 0.0) * float(exps.get(t, 0.0))
            qasm = "\n".join(l for l in str(rec.get("raw_qasm2", "")).splitlines() if l.strip() and not l.strip().startswith("//"))
            groups.append({"id": rec.get("group_id"), "qasm": qasm, "terms": terms})
        out["export"] = {"groups": groups, "constant": (float(E) - acc) if E is not None else 0.0}
        out["backend_used"] = backend
        out["target"] = str(target)
        out["seconds"] = round(time.time() - t0, 1)
        return out
    except Exception as e:
        return {"success": False, "error": (type(e).__name__ + ": " + str(e))[:600],
                "seconds": round(time.time() - t0, 1)}

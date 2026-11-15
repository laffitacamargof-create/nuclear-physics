# =============================================================================
#  Quantum app nuclear physics - Python connector
#  Paste this whole file in the "Python" field of the app. The HTML calls
#      pyCall('qapi', METHOD, PATH, BODY, CTX)
#  qapi() reproduces the REST routes the original interface used, but runs the
#  real backend (github.com/laffitacamargof-create/nuclear-physics, pinned
#  commit) INSIDE the compiler of the ecosystem. No external server is used.
#  Needs in the compiler: numpy scipy cirq-core openfermion pyqasm ply
#  (and openqasm3[parser]==1.0.1). Only the local simulator runs; nothing is
#  sent to real quantum hardware.
# =============================================================================
import sys, io, json, time, base64, zipfile, tempfile, warnings, importlib.util
import urllib.request
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

BACKEND_REPO = "laffitacamargof-create/nuclear-physics"
BACKEND_COMMIT = "c173be521c786507c16d678498640cb03e6679c6"
BACKEND_PATH = ""          # optional: local path of .../qcol-app-studio-backend
NEEDED = ("numpy", "scipy", "cirq", "openfermion", "pyqasm")
DEADLINE = 30.0            # the compiler allows ~35 s per call
_M = sys.modules.setdefault("_qnp_state", type(sys)("_qnp_state")).__dict__   # survives between calls if the compiler keeps its process


def _backend_dir():
    if BACKEND_PATH and (Path(BACKEND_PATH) / "qcol" / "__init__.py").exists():
        return Path(BACKEND_PATH)
    root = Path(tempfile.gettempdir()) / ("qcol_nuclear_" + BACKEND_COMMIT[:8])
    hits = list(root.glob("*/qcol-app-studio-backend/qcol/__init__.py"))
    if not hits:
        root.mkdir(parents=True, exist_ok=True)
        z = root / "backend.zip"
        urllib.request.urlretrieve("https://codeload.github.com/%s/zip/%s" % (BACKEND_REPO, BACKEND_COMMIT), str(z))
        zipfile.ZipFile(str(z)).extractall(str(root))
        hits = list(root.glob("*/qcol-app-studio-backend/qcol/__init__.py"))
    if not hits:
        raise RuntimeError("qcol-app-studio-backend not found in the downloaded zip")
    return hits[0].parent.parent


def _ensure():
    miss = [m for m in NEEDED if importlib.util.find_spec(m) is None]
    if miss:
        raise RuntimeError("Missing libraries in the compiler: " + ", ".join(miss))
    p = str(_backend_dir())
    if p not in sys.path:
        sys.path.insert(0, p)


def nuclear_warmup(deep=True):
    t0 = time.time()
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            warnings.filterwarnings("ignore")
            _ensure()
            import qcol.run_manager, qcol.catalog, qcol.orchestrator  # noqa
            if deep:
                _route("POST", "/runs", {"model_id": "nuclear.reduced_pairing.one_pair", "task": "ground_state_energy",
                       "shots": 64, "seed": 1, "max_evaluations": 4, "target_backend": "google",
                       "parameters": {"n_levels": 4, "epsilon": [0, 1, 2, 3], "g": 0.5}}, {}, t0)
        return {"success": True, "seconds": round(time.time() - t0, 1)}
    except Exception as e:
        return {"success": False, "error": str(e)[:400]}


def _mgr():
    if "m" not in _M:
        from qcol.run_manager import RunManager
        _M["m"] = RunManager(evidence_root=Path(tempfile.mkdtemp(prefix="qcol_ev_")))
    return _M["m"]


def _b64(p):
    try:
        p = Path(p)
        return base64.b64encode(p.read_bytes()).decode() if p and p.exists() else None
    except Exception:
        return None


def _export(rec):
    """QASM2 groups + constant to rebuild the final circuit in Qiskit/Cirq/Braket."""
    res = getattr(rec, "result", None)
    if res is None or res.reconstructed_energy is None:
        return None
    groups, acc = [], 0.0
    for r in (res.raw_records or []):
        terms = [[t.get("term"), t.get("coefficient")] for t in (r.get("pauli_terms") or [])]
        ex = r.get("term_expectations") or {}
        for t, c in terms:
            acc += float(c or 0.0) * float(ex.get(t, 0.0))
        q = "\n".join(l for l in str(r.get("raw_qasm2", "")).splitlines() if l.strip() and not l.strip().startswith("//"))
        groups.append({"id": r.get("group_id"), "qasm": q, "terms": terms})
    return {"groups": groups, "constant": float(res.reconstructed_energy) - acc}


def _wait(rec, limit):
    t0 = time.time()
    while not rec.terminal:
        if time.time() - t0 > limit and rec.public_result is None:
            rec.cancellation_token.cancel("compiler_time_limit")
            _M["tl"] = rec.run_id
            limit = 1e9
        time.sleep(0.05)
    while rec.status not in ("completed", "cancelled", "failed"):
        time.sleep(0.02)
    return round(time.time() - t0, 1)


def _compact(rec):
    """Drop repeated data: journey cards are sent as deltas, big payloads as markers."""
    out, prev = [], {}
    snap = rec.snapshot()
    for e in rec.events:
        d = e.to_dict()
        data, js = d["data"], None
        if e.event in ("completed", "cancelled", "failed"):
            d["data"] = {"@final": True}
        elif e.event == "artifact_ready":
            d["data"] = {"run_id": rec.run_id, "artifact": "@snapshot"}
        elif isinstance(data.get("journey_state"), dict):
            js = dict(data["journey_state"])
            cards = js.get("cards") or {}
            js["cards"] = {k: v for k, v in cards.items() if prev.get(k) != v}
            js["@delta"] = True
            prev = dict(cards)
            data = dict(data)
            data["journey_state"] = js
            d["data"] = data
        out.append(d)
    return out


def _pack(rec, mgr, secs):
    snap = rec.snapshot()
    d = {"run_id": rec.run_id, "events": _compact(rec), "snapshot": snap,
         "evidence_b64": _b64(rec.evidence_archive),
         "technical_error": (mgr.technical_error_info(rec.run_id) if rec.technical_error else None),
         "export": _export(rec), "seconds": secs, "time_limited": _M.get("tl") == rec.run_id}
    try:
        p = Path(tempfile.gettempdir()) / "qnp_runs"
        p.mkdir(exist_ok=True)
        (p / (rec.run_id + ".json")).write_text(json.dumps(snap, default=str))
    except Exception:
        pass
    return d


def _saved(run_id):
    try:
        return json.loads((Path(tempfile.gettempdir()) / "qnp_runs" / (str(run_id) + ".json")).read_text())
    except Exception:
        return None


def _snapshot_for(mgr, run_id, request, t0):
    """Snapshot of a finished run: from the compiler temp dir, else deterministic re-run."""
    snap = _saved(run_id)
    if snap:
        return snap
    if not request:
        raise ValueError("The run is no longer available in the compiler; run it again.")
    rec = mgr.create_run(request)
    _wait(rec, DEADLINE - (time.time() - t0))
    return rec.snapshot()


def _err(code, status, msg, **kw):
    d = {"code": code, "message": msg}
    d.update(kw)
    return {"status": status, "detail": d}


def _rebuild(mgr, snap):
    from qcol.run_manager import RunRecord
    from qcol.control import CancellationToken
    rec = RunRecord(run_id=snap["run_id"], request=snap["request"], cancellation_token=CancellationToken(),
                    status=snap.get("status", "completed"), created_utc=snap.get("created_utc"),
                    started_utc=snap.get("started_utc"), completed_utc=snap.get("completed_utc"),
                    latest_state=snap.get("journey_state"), public_artifact=snap.get("artifact"),
                    public_result=snap.get("result"), advisor_report=snap.get("advisor"),
                    parent_run_id=snap.get("parent_run_id"), comparison_role=snap.get("comparison_role"),
                    phase_c=snap.get("phase_c"))
    mgr.state_repository.put_run(rec.run_id, rec)
    return rec


def qapi(method="GET", path="/health", body=None, ctx=None):
    if str(method).startswith("{"):
        d = json.loads(method)
        method, path, body, ctx = d["m"], d.get("p", "/health"), d.get("b"), d.get("c")
    method = str(method).upper()
    body = body or {}
    ctx = ctx or {}
    t0 = time.time()
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            warnings.filterwarnings("ignore")
            _ensure()
            out = _route(method, str(path), body, ctx, t0)
        if ctx.get("z"):
            import zlib
            raw = json.dumps(out, default=str, separators=(",", ":")).encode()
            return {"z": base64.b64encode(zlib.compress(raw, 6)).decode(), "n": len(raw)}
        return out
    except Exception as e:
        return _err("backend_error", 500, (type(e).__name__ + ": " + str(e))[:600])


def _route(method, path, body, ctx, t0):
    if method == "GET" and path == "/health":
        return {"status": 200, "json": {"status": "ok", "registry": "in_memory_single_process", "active_run_count": 0}}
    if method == "GET" and path == "/catalog":
        from qcol.catalog import get_catalog
        return {"status": 200, "json": get_catalog()}
    if method == "GET" and path == "/catalog/model-task-realizations":
        from qcol.realization_variants import public_model_task_realization_catalog
        return {"status": 200, "json": public_model_task_realization_catalog()}
    from qcol.run_manager import service_json_safe
    mgr = _mgr()
    if method == "POST" and path == "/runs":
        from qcol.model_contracts import ModelContractError
        from qcol.fermion_registry import FermionProblemContractError
        try:
            rec = mgr.create_run(body)
        except FermionProblemContractError as e:
            return {"status": 422, "detail": e.to_dict()}
        except ModelContractError as e:
            return _err("model_contract_error", 422, str(e))
        except (TypeError, ValueError) as e:
            return _err("invalid_request", 422, str(e))
        secs = _wait(rec, DEADLINE - (time.time() - t0))
        return {"status": 200, "json": _pack(rec, mgr, secs)}
    parts = [p for p in path.split("/") if p]
    if method == "POST" and len(parts) == 4 and parts[0] == "runs" and parts[2:] == ["advisor", "prepare-candidate"]:
        from qcol.advisor import advise_run_payload, prepare_candidate_request_plan
        snap = _snapshot_for(mgr, parts[1], ctx.get("request"), t0)
        prev = _saved(ctx.get("prev_id")) if ctx.get("prev_id") else None
        cid = str(body.get("card_id", "")).strip()
        if not cid:
            return {"status": 422, "detail": "card_id is required."}
        context, report = advise_run_payload(snap, previous_snapshot=prev, enabled=True)
        card = next((c for c in report.cards if c.card_id == cid), None)
        if card is None:
            return _err("advisor_card_not_found", 404, "The card ID does not belong to the current deterministic Advisor report.")
        try:
            plan = prepare_candidate_request_plan(snap["request"], card, approved=body.get("approved") is True)
        except (KeyError, TypeError, ValueError) as e:
            return _err("candidate_request_not_preparable", 422, str(e))
        return {"status": 200, "json": {"schema_version": "qcol-advisor-candidate-response/1.0", "run_id": parts[1],
                "context_id": context.context_id, "report_id": report.report_id, "card": card.to_dict(),
                "candidate_plan": plan.to_dict(), "execution_performed_by_advisor": False,
                "next_entrypoint": "POST /runs", "phase_c_comparison_performed": False}}
    if method == "POST" and len(parts) == 3 and parts[0] == "runs" and parts[2] == "try-compare":
        cid = str(body.get("card_id", "")).strip()
        if not cid:
            return {"status": 422, "detail": "card_id is required."}
        if body.get("approved") is not True:
            return _err("explicit_user_approval_required", 409, "Phase C will not execute a candidate until approved=true is supplied.")
        bsnap = _snapshot_for(mgr, parts[1], ctx.get("request"), t0)
        base = _rebuild(mgr, bsnap)
        prev = _saved(ctx.get("prev_id")) if ctx.get("prev_id") else None
        if prev:
            _rebuild(mgr, prev)
        try:
            sess = mgr.start_try_compare(base.run_id, card_id=cid, approved=True,
                                         previous_run_id=(prev or {}).get("run_id"),
                                         policy_id=body.get("policy_id"))
        except KeyError as e:
            return {"status": 404, "detail": str(e)}
        except RuntimeError as e:
            return _err("try_compare_conflict", 409, str(e))
        except (TypeError, ValueError) as e:
            return _err("try_compare_not_startable", 422, str(e))
        cand = mgr.get(sess.candidate_run_id)
        secs = _wait(cand, DEADLINE - (time.time() - t0))
        t1 = time.time()
        while time.time() - t1 < 8:
            comp = mgr.get_comparison(sess.session_id)
            if comp.get("status") in ("completed", "failed"):
                break
            time.sleep(0.1)
        out = _pack(cand, mgr, secs)
        out["session"] = comp
        out["session_id"] = sess.session_id
        out["comparison_evidence_b64"] = None
        try:
            out["comparison_evidence_b64"] = _b64(mgr.comparison_evidence_file(sess.session_id))
        except Exception:
            pass
        out["baseline_events"] = [e.to_dict() for e in base.events if e.event.startswith("comparison")]
        out["baseline_snapshot"] = base.snapshot()
        return {"status": 200, "json": service_json_safe(out)}
    return _err("not_found", 404, "Route not available in the embedded transport: %s %s" % (method, path))

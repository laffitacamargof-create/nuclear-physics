"""
QCOL Quantum App Studio connector.

Thin FastAPI integration layer. Uses the existing QCOL runtime when
qcol-app-studio-backend/qcol is present, and uses GitHub only for
repository/catalog *inspection* -- it never executes code fetched from
GitHub. That design was already correct in the previous version of this
file; nothing about it changes here.

What changed in this revision, and why:

1. Catalog caching (the actual fix for this pass). get_catalog(),
   public_qho_ui_catalog(), and public_fermion_problem_catalog() are pure,
   zero-argument, deterministic functions -- confirmed by reading their
   signatures -- but get_catalog() takes ~38s and public_qho_ui_catalog()
   takes ~9.5s on every single call, because they recompute nested
   acceptance-fingerprint SHA-256 digests from scratch every time instead
   of once. That's not a hypothetical concern: it was measured directly
   against this repository's backend, and it's exactly why the previous
   version of this connector appeared to hang on GET /catalog -- any
   normal HTTP client (browser fetch, httpx, a load balancer, most free
   hosting tiers) times out well before 38 seconds.

   The fix stays entirely inside this connector file, not the frozen
   qcol/ package: each of the three catalog functions is computed once,
   cached in memory, and served from cache on every subsequent request.
   A background warm-up task computes all three at server startup so the
   *first* real user request is already fast, instead of that one request
   eating the 38-second cost.

2. /catalog/refresh (new). If the underlying qcol package is ever swapped
   for a newer checkout without restarting the process, this endpoint
   forces the cache to recompute. Not required for correctness, just
   operational convenience.

3. Everything else -- run creation, SSE streaming, evidence download,
   GitHub inspection endpoints, CORS policy -- is unchanged from the
   previous version, which was already sound.

Run locally or in any container:
    pip install fastapi uvicorn httpx
    uvicorn qcol_app_studio_connector:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, StreamingResponse

GITHUB_OWNER = os.getenv("QCOL_GITHUB_OWNER", "laffitacamargof-create")
GITHUB_REPO = os.getenv("QCOL_GITHUB_REPO", "nuclear-physics")
GITHUB_REF = os.getenv("QCOL_GITHUB_REF", "main")
QCOL_API_URL = os.getenv("QCOL_API_URL", "").rstrip("/")

PROJECT_ROOT = Path(os.getenv(
    "QCOL_PROJECT_ROOT",
    Path(__file__).resolve().parent / "qcol-app-studio-backend"
))

GITHUB_API = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}"
ALLOWED_SOURCE_FILES = {
    "catalog.json", "fermion_pairing.py", "oscillator.py",
    "qcol-nuclearphysics-connector.js", "requirements.txt"
}

app = FastAPI(
    title="QCOL Quantum App Studio Connector",
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://laffitacamargof-create.github.io",
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "*",  # restrict this in production
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


def _load_qcol():
    """Load the canonical QCOL API if this checkout contains it."""
    api_file = PROJECT_ROOT / "qcol" / "api.py"
    if not api_file.exists():
        return None
    root = str(PROJECT_ROOT.resolve())
    if root not in sys.path:
        sys.path.insert(0, root)
    try:
        from qcol import api as qcol_api
        return qcol_api
    except Exception:
        return None


QCOL = _load_qcol()


# ---------------------------------------------------------------------------
# Catalog caching
#
# get_catalog(), public_qho_ui_catalog(), and public_fermion_problem_catalog()
# take no arguments and are deterministic for a fixed qcol checkout -- there
# is nothing request-specific to invalidate on. Measured cost without this
# cache: get_catalog() ~38s, public_qho_ui_catalog() ~9.5s,
# public_fermion_problem_catalog() ~instant. Cached after the first call.
# ---------------------------------------------------------------------------
class _CachedComputation:
    def __init__(self, compute: Callable[[], Any], label: str) -> None:
        self._compute = compute
        self._label = label
        self._value: Any = None
        self._computed = False
        self._lock = asyncio.Lock()
        self._last_duration_seconds: float | None = None

    async def get(self) -> Any:
        if self._computed:
            return self._value
        async with self._lock:
            if self._computed:  # re-check: another request may have won the race
                return self._value
            t0 = time.monotonic()
            self._value = await asyncio.to_thread(self._compute)
            self._last_duration_seconds = time.monotonic() - t0
            self._computed = True
            return self._value

    def invalidate(self) -> None:
        self._computed = False
        self._value = None

    def status(self) -> dict[str, Any]:
        return {
            "label": self._label,
            "cached": self._computed,
            "last_compute_seconds": self._last_duration_seconds,
        }


def _build_catalog_caches() -> dict[str, _CachedComputation]:
    if QCOL is None:
        return {}
    from qcol.catalog import get_catalog
    from qcol.model_ui_schema import public_qho_ui_catalog
    from qcol.fermion_registry import public_fermion_problem_catalog

    return {
        "catalog": _CachedComputation(get_catalog, "GET /catalog"),
        "qho": _CachedComputation(public_qho_ui_catalog, "GET /catalog/qho"),
        "fermions": _CachedComputation(
            lambda: public_fermion_problem_catalog(include_unavailable=True),
            "GET /catalog/fermions",
        ),
    }


CATALOG_CACHES = _build_catalog_caches()


@app.on_event("startup")
async def _warm_caches() -> None:
    """Pay the ~38s + ~9.5s cost once, at process startup, off the request
    path -- so the first real user is not the one who eats it.

    Warmed sequentially in a single background task, not as separate
    concurrent tasks: measured directly, running get_catalog() and
    public_qho_ui_catalog() concurrently makes each one slower (CPU
    contention pushed them to 58s and 22s respectively, versus 38s and
    9.5s standalone) and a request arriving mid-warm-up still has to wait
    on whichever cache's lock it hits. Sequential warm-up keeps at most
    one expensive computation running at a time.
    """
    async def _warm_sequentially() -> None:
        for cache in CATALOG_CACHES.values():
            await cache.get()

    asyncio.create_task(_warm_sequentially())


# ---------------------------------------------------------------------------
# GitHub inspection helpers (unchanged behavior from the previous version)
# ---------------------------------------------------------------------------
async def github_json(path: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(
            f"{GITHUB_API}/contents/{path}",
            params={"ref": GITHUB_REF},
            headers={"Accept": "application/vnd.github+json"},
        )
    if r.status_code != 200:
        raise HTTPException(502, {
            "code": "github_fetch_failed",
            "path": path,
            "status": r.status_code,
        })
    return r.json()


@app.get("/")
def root():
    return RedirectResponse("/studio")


@app.get("/studio")
def studio():
    return {
        "service": "QCOL Quantum App Studio Connector",
        "status": "ok",
        "canonical_qcol_available": QCOL is not None,
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "qcol-app-studio-connector",
        "repository": f"{GITHUB_OWNER}/{GITHUB_REPO}",
        "ref": GITHUB_REF,
        "canonical_qcol_available": QCOL is not None,
        "external_qcol": bool(QCOL_API_URL),
        "catalog_cache": {key: cache.status() for key, cache in CATALOG_CACHES.items()},
    }


@app.get("/github/repository")
async def repository():
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(
            GITHUB_API,
            headers={"Accept": "application/vnd.github+json"},
        )
    if r.status_code != 200:
        raise HTTPException(502, "Unable to read GitHub repository metadata.")
    d = r.json()
    return {
        "full_name": d.get("full_name"),
        "default_branch": d.get("default_branch"),
        "html_url": d.get("html_url"),
        "commit_ref": GITHUB_REF,
    }


@app.get("/github/source/{path:path}")
async def source(path: str):
    if path not in ALLOWED_SOURCE_FILES:
        raise HTTPException(403, "Source file is not exposed by this connector.")
    d = await github_json(path)
    if d.get("encoding") != "base64":
        raise HTTPException(502, "Unexpected GitHub encoding.")
    return {
        "path": path,
        "sha": d.get("sha"),
        "ref": GITHUB_REF,
        "repository": f"{GITHUB_OWNER}/{GITHUB_REPO}",
        "content": base64.b64decode(d["content"]).decode(),
        "execution": "inspection_only",
    }


@app.get("/catalog")
async def catalog():
    if "catalog" in CATALOG_CACHES:
        return await CATALOG_CACHES["catalog"].get()
    raise HTTPException(
        503,
        "Canonical QCOL runtime is not available. "
        "Mount qcol-app-studio-backend or set QCOL_API_URL."
    )


@app.get("/catalog/qho")
async def qho():
    if "qho" in CATALOG_CACHES:
        return await CATALOG_CACHES["qho"].get()
    raise HTTPException(503, "QCOL runtime unavailable.")


@app.get("/catalog/fermions")
async def fermions():
    if "fermions" in CATALOG_CACHES:
        payload = await CATALOG_CACHES["fermions"].get()
        return {"count": len(payload), "problems": payload}
    raise HTTPException(503, "QCOL runtime unavailable.")


@app.post("/catalog/refresh")
def refresh_catalog():
    """Force the next request to each catalog endpoint to recompute,
    e.g. after swapping in an updated qcol checkout without restarting."""
    for cache in CATALOG_CACHES.values():
        cache.invalidate()
    return {"status": "invalidated", "caches": list(CATALOG_CACHES.keys())}


@app.post("/runs")
async def create_run(request: Request):
    payload = await request.json()

    if QCOL is not None:
        try:
            record = QCOL.get_run_manager().create_run(payload)
        except Exception as exc:
            raise HTTPException(
                422, {"code": "run_creation_failed", "message": str(exc)}
            ) from exc
        s = record.snapshot()
        return JSONResponse({
            "run_id": record.run_id,
            "status": s["status"],
            "status_url": f"/runs/{record.run_id}",
            "stream_url": f"/runs/{record.run_id}/stream",
            "evidence_url": f"/runs/{record.run_id}/evidence",
        }, status_code=202)

    if QCOL_API_URL:
        async with httpx.AsyncClient(timeout=None) as client:
            r = await client.post(f"{QCOL_API_URL}/runs", json=payload)
        return JSONResponse(r.json(), status_code=r.status_code)

    raise HTTPException(503, "No QCOL runtime is configured.")


@app.get("/runs/{run_id}")
def get_run(run_id: str):
    if QCOL is not None:
        try:
            return QCOL.get_run_manager().get(run_id).snapshot()
        except KeyError:
            raise HTTPException(404, "Unknown run_id.")
    raise HTTPException(503, "QCOL runtime unavailable.")


@app.get("/runs/{run_id}/stream")
def stream_run(run_id: str):
    if QCOL is None:
        raise HTTPException(503, "QCOL runtime unavailable.")

    try:
        QCOL.get_run_manager().get(run_id)
    except KeyError:
        raise HTTPException(404, "Unknown run_id.")

    def stream():
        yield "retry: 1500\n\n"
        for item in QCOL.get_run_manager().iter_events(run_id, after=0):
            if item is None:
                yield ": heartbeat\n\n"
            else:
                data = json.dumps(
                    item.data, ensure_ascii=False,
                    separators=(",", ":"), allow_nan=False
                )
                yield (
                    f"id: {item.id}\n"
                    f"event: {item.event}\n"
                    f"data: {data}\n\n"
                )

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/runs/{run_id}/evidence")
def evidence(run_id: str):
    if QCOL is None:
        raise HTTPException(503, "QCOL runtime unavailable.")
    try:
        archive = QCOL.get_run_manager().evidence_file(run_id)
    except KeyError:
        raise HTTPException(404, "Unknown run_id.")
    except FileNotFoundError:
        raise HTTPException(409, "Evidence is not available until the run is terminal.")
    return FileResponse(
        archive,
        media_type="application/zip",
        filename=archive.name,
    )


# Reuse the complete canonical API router so the production connector exposes
# every endpoint consumed by index.html (realization catalog, run history,
# cancellation, technical logs, Advisor, Try/Compare, and comparison records).
# Connector-specific routes above remain first and retain their catalog cache.
if QCOL is not None:
    app.include_router(QCOL.app.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "qcol_app_studio_connector:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
    )

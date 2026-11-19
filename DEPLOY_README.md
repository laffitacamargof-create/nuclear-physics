# QCOL Quantum App Studio — connector fix + free hosting

## What was broken, and what's fixed

Both source files you had were architecturally sound (no execution of
remote code, GitHub used for inspection only, canonical QCOL as the real
engine). Two bugs would have broken it in production regardless of where
it was hosted — found by actually running it, not by reading it:

1. **`GET /catalog` genuinely takes ~38 seconds** (and `/catalog/qho` takes
   ~9.5s), measured directly against your backend. Root cause: deeply
   nested acceptance-fingerprint SHA-256 digests get recomputed from
   scratch on every call, with no caching, even though the function takes
   no arguments and its output is deterministic. Any browser `fetch()`,
   most reverse proxies, and every free hosting tier's default timeout
   would kill this request before it finishes — this is why the Studio
   would appear to hang on load.

   **Fix:** each of the three catalog functions is now computed once,
   cached in memory, and served from cache afterward. A background task
   warms all three sequentially at server startup (not concurrently —
   measured that running them concurrently causes CPU contention that
   makes each one *slower*, 58s/22s instead of 38s/9.5s standalone), so
   the first real visitor doesn't pay the cost.

2. **Every successful run creation crashed with an HTTP 500.**
   `JSONResponse(202, {...})` has the arguments backwards — Starlette's
   signature is `JSONResponse(content, status_code)`, not the reverse. So
   even with the catalog fixed, clicking "Execute" would never have
   worked. Fixed in both places it occurred.

Verified after fixing: ran a real physics problem (one-pair pairing model)
through `POST /runs` → SSE event stream → `completed`, with the actual
QCOL orchestrator producing a real reconstructed energy — not mocked.

## Files in this delivery

```
qcol_app_studio_connector.py   the fixed connector (place at repo root)
quantum_app_studio.html         frontend, now supports ?api=<url> to point
                                 at your deployed connector without editing
                                 the file each time
Dockerfile                      builds and runs the connector (not the
                                 raw qcol/api.py — the connector adds the
                                 GitHub-inspection + catalog-cache endpoints
                                 the frontend actually calls)
render.yaml                     one-file Render deploy config
.github/workflows/keepalive.yml free keep-alive ping (see below)
```

## Deploy to Render (free)

1. Commit these 5 files into `laffitacamargof-create/nuclear-physics` at
   the repository root (alongside the existing `qcol-app-studio-backend/`
   folder — the Dockerfile expects that folder to stay where it is).
2. Go to https://dashboard.render.com → **New** → **Blueprint** → connect
   the `nuclear-physics` repository. Render reads `render.yaml`
   automatically; no manual service configuration needed.
3. Render builds the Dockerfile and gives you a stable URL, e.g.
   `https://qcol-quantum-app-studio-connector.onrender.com`.
4. Open your GitHub Pages site with `?api=` pointing at that URL once, e.g.:
   `https://laffitacamargof-create.github.io/quantum-computing-open-lab/?api=https://qcol-quantum-app-studio-connector.onrender.com`
   The page saves it in `localStorage`, so you only need the `?api=` link
   once per browser — after that, visiting the page normally remembers it.
   (Alternatively, just hardcode that URL into `FALLBACK_API_BASE` in the
   HTML once you know it, and skip the query-param step entirely.)

No Colab notebook to keep open, no ngrok tunnel that changes on every
restart — the URL is permanent as long as the Render service exists.

## Free tier's one real limitation, and how it's handled at zero cost

Render's free web services sleep after ~15 minutes with no traffic, and
the next request pays a cold-start cost. Two options, both free:

- **Do nothing.** The catalog cache now warms itself automatically on
  every cold start, so the delay is bounded and one-time per wake-up
  rather than compounding — acceptable if the Studio is used sporadically.
- **Use the included GitHub Actions workflow** (`.github/workflows/keepalive.yml`).
  It pings `/health` every 10 minutes using GitHub's own free scheduled-workflow
  runner — no third-party uptime service, no signup, no cost. After
  deploying to Render, set the `CONNECTOR_URL` repository variable
  (Settings → Secrets and variables → Actions → Variables) to your Render
  URL, and the service should never go to sleep at all.

## What wasn't changed

The overall design — GitHub for inspection only, canonical QCOL as the
real execution engine, no remote code execution, SSE for live run events,
the API-key prompt for remote backends being honestly labeled
"target-only" — was already correct and is untouched. This pass only fixed
what was actually broken and made hosting cheap and stable.

## Runtime API routing and CORS (November 2026)

The root production connector now reuses the canonical `qcol.api` router
when the backend package is present. This keeps the connector's cached
catalog and GitHub-inspection endpoints while also exposing the complete
API contract consumed by `index.html`, including model-task realizations,
run listing/cancellation, technical-error logs, Advisor, Try/Compare, and
comparison retrieval.

The canonical API keeps these origins enabled by default:

- `https://laffitacamargof-create.github.io`
- local development origins on ports 3000, 5173, and 7860

Set `QCOL_CORS_ORIGINS` to a comma-separated list of additional browser
origins, for example:

```text
QCOL_CORS_ORIGINS=https://staging.example.org,https://my-lab.example.org
```

Configured origins extend the built-in defaults; they do not replace the
GitHub Pages origin. Specify origins without a trailing slash.

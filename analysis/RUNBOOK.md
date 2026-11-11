# TerraTwin runbook: setup, operation, verification and deployment

All commands run from the repository root. Tested on Linux (Python 3.14.4, 12th-gen Intel i5-1235U, 15 GiB RAM) on 2026-11-12.

## 1. Requirements

| Resource | Needed for | Size / note |
|---|---|---|
| Python 3.12+ (verified 3.14.4) | Server, engine, tests | — |
| Git LFS objects for `prepared/0.2.0/*.parquet` | **Required** for search | 405 MB on disk (`git lfs pull`) |
| `frontend/ldem_64.tif` lunar DEM | Optional lunar point telemetry and lunar textures | 1.06 GB download |
| `frontend/tile_cache/` | Optional imagery cache, grows with browsing | ~25 MB per world for levels 0–4; 195 MB observed after testing |
| Memory | Server process | 200 MB idle; **1.18 GiB peak RSS** under the 10-concurrent benchmark; allow 2 GiB |
| Internet access (browser) | Globe library, Tailwind, Chart.js CDNs; Esri/NASA/USGS imagery tiles | Search, results, evidence and exports work without the globe; see §6 |

## 2. Setup

```bash
git lfs install && git lfs pull                       # real Parquet data, not pointers
python3 -m venv .venv
.venv/bin/pip install -r processing/requirements.txt -r frontend/requirements.txt -r requirements-dev.txt
# Optional lunar DEM (NASA SVS CGI Moon Kit, 64 px/deg):
curl -L -o frontend/ldem_64.tif https://svs.gsfc.nasa.gov/vis/a000000/a004700/a004720/ldem_64.tif
```

Large files, environments, caches and generated textures are git-ignored. `mars_viking.jpg` and the Gazetteer label files are committed.

## 3. Start

```bash
.venv/bin/uvicorn --app-dir frontend app:app --port 8000          # open http://localhost:8000
```

The working directory no longer matters; files resolve relative to `frontend/app.py`. Configuration is optional, through environment variables listed in [`.env.example`](../.env.example): `TERRATWIN_RELEASE_DIR`, `TERRATWIN_LDEM`, `TERRATWIN_TILE_CACHE`, `TERRATWIN_PREWARM`, `TERRATWIN_FETCH_LABELS`, `TERRATWIN_MAX_CONCURRENT_SEARCHES`.

On the first start with the DEM present, lunar textures are generated once. A background thread then prewarms imagery tiles for levels 0–4. During that warm-up, searches still work but can be slower. Browser round-trips of 0.9–3.9 s were observed in the first minutes, against 0.15–0.33 s afterwards. For demonstrations, start the server a few minutes early or set `TERRATWIN_PREWARM=0`.

**Readiness:** `GET /api/v1/health` returns 200 `{"status":"ready", "release":{"dataset_version":"0.2.0"}, "lunar_dem":{...}}` when the release is loaded. It returns 503 with a specific diagnostic when it is not, such as missing files or LFS pointers ("run `git lfs pull`"). Imagery and the lunar DEM are reported separately and never block search.

## 4. API (`/api/v1`)

| Route | Purpose |
|---|---|
| `GET /health` | Readiness, release version, lunar DEM availability |
| `GET /meta` | Release version, profiles (available and unavailable with missing evidence), score label/explanation, feature definitions, grids, examples, local studies |
| `GET /target?body=&lat=&lon=` | Containing native cell, its terrain, eligibility per profile |
| `POST /search` | `{body, lat, lon, profile, limit?, origin?{lat,lon}, radius_km?, weights?}`. Unknown fields rejected |
| `GET /cases`, `GET /cases/{id}` | Saved release fixtures, always marked `saved_fixture` |
| `GET /evidence/{study}/{file}` | Allowlisted Gobi/Jaflong/known-site files only |

Outcomes `ok`, `target_insufficient_evidence`, `no_candidates_under_filters` and `profile_unavailable` return HTTP 200 with that `status`. Invalid input returns 422 (field locations and messages only; values are never echoed). A missing release returns 503, and unexpected failures return 500 `service_error`. None of these can look like a scientific no-match. The server binds the release from `prepared/current_release.json`, so clients cannot supply paths, SQL or URLs. Public static files are an explicit allowlist (`index.html`, `terratwin.js`, `terratwin.css`, label JSON, Mars/lunar textures).

## 5. Verify

```bash
TERRATWIN_PREWARM=0 TERRATWIN_FETCH_LABELS=0 .venv/bin/python -m pytest processing frontend/test_api.py -q   # 59 tests
.venv/bin/python frontend/app.py                                  # self-check incl. a real search (needs DEM)
.venv/bin/python frontend/browser_check.py --shots analysis/screenshots   # 18 browser checks; server must be running
.venv/bin/python frontend/perf_check.py --server-pid <pid> --browser --output analysis/performance_<date>.json
```

`browser_check.py` and the browser part of `perf_check.py` use Playwright with the system Chrome (`--browser chromium` uses Playwright's bundled build after `playwright install chromium`).

**CI** (`.github/workflows/ci.yml`) runs without LFS objects. It covers the unit tests, the API tests (data-dependent ones skip with a stated reason), JavaScript syntax, and a server smoke test asserting that missing data yields 503 rather than results. The full data-dependent verification (fixture regression, HTTP-vs-engine parity, browser workflow, performance) runs locally after `git lfs pull` with the commands above. A clone made with `GIT_LFS_SKIP_SMUDGE=1` was used to confirm that behavior: 11 passed and 48 skipped with reasons, and the smoke test passed.

## 6. Degraded operation and demonstration fallback

| Failure | Behavior |
|---|---|
| Lunar DEM missing | Lunar telemetry panel says unavailable; search unaffected |
| Upstream imagery tile fails | Tile returns 502/404 (with CORS headers); the failure is remembered for 2 minutes; the globe shows the base image |
| Globe CDN or WebGL unavailable | Notice shown; coordinate entry, search, results, evidence, comparison and exports work in the panels |
| Tailwind CDN unavailable | `terratwin.css` keeps panels, inputs, focus and tables legible; layout is less polished |
| Release data missing | `/health` 503 with diagnostic; search 503 "Search data unavailable", never an empty result |
| No network for live demo | Local studies tab → **Saved examples**, which load the release fixtures with a "Saved example — not a newly executed query" banner and keep their original query/version |

## 7. Deployment

No hosting target or credentials were provided, so nothing has been deployed. Deployment is ready to proceed once a host is chosen.

- **Process:** `uvicorn --app-dir frontend app:app --host 0.0.0.0 --port 8000 --workers 1` behind a TLS reverse proxy. Use one worker per 2 GiB of memory. Concurrency inside a worker is bounded by `TERRATWIN_MAX_CONCURRENT_SEARCHES`.
- **Container:** a [`Dockerfile`](../Dockerfile) and [`.dockerignore`](../.dockerignore) are provided. The image contains the serving release, fixtures and local-study assets; the DEM and tile cache go on a `/data` volume. The build refuses to proceed if the Parquet files are LFS pointers. **The image has not been built or run in this environment.** Verify with `docker build -t terratwin . && docker run -p 8000:8000 -v terratwin-data:/data terratwin`, then `/api/v1/health`.
- **Privacy:** travel origins arrive only in POST bodies and are not logged by the application. The default uvicorn access log records paths and query strings: `/target` query strings carry planetary coordinates only.
- **External dependencies at runtime:** jsDelivr (globe.gl 2.46.1, Chart.js 4.5.1, three-globe night-sky image), cdn.tailwindcss.com, raw.githubusercontent.com (lunar base image), Esri ArcGIS Online (Earth imagery, CTX Mars tiles), NASA Trek (Kaguya, Viking tiles), USGS Gazetteer (one-time label download).

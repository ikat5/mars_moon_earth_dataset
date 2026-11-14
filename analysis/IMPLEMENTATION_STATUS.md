# TerraTwin implementation status

Updated 2026-11-12 on branch `feat/terratwin-search-integration`, against [MASTER_IMPLEMENTATION_PROMPT.md](MASTER_IMPLEMENTATION_PROMPT.md) as revised that day (with the Moon/Mars→Earth reveal). Every "verified" item below was executed in this environment on that date. Historical reports elsewhere in `analysis/` are not counted as fresh evidence.

## Requirements checklist

| Phase | Requirement | State | Evidence |
|---|---|---|---|
| A | Isolated environment; dependencies installed | Verified | `.venv` from `processing/` + `frontend/` + `requirements-dev.txt` |
| A | Parquet files are real data, not LFS pointers | Verified | Parquet magic checked; `has_release_data()` |
| A | Existing processing tests pass | Verified | 16/16 |
| A | Four release fixtures reproduce with the serving release | Verified | `processing/test_release_fixtures.py`: identical IDs, scores within 1e-9 |
| A | Startup independent of working directory; no work at import; clear missing-data diagnostics | Verified | `app.py` refactor; LFS-less clone gives 503 "run `git lfs pull`" |
| A | Search usable without imagery or lunar DEM | Verified | DEM optional; no-WebGL browser check |
| B | `/api/v1` health, meta, target, search, saved cases, allowlisted evidence | Verified | `frontend/test_api.py` (40 tests) |
| B | Release bound server-side; strict request contract; four outcomes distinct from 422/503/500 | Verified | Validation and outage tests |
| B | HTTP results equal direct engine results | Verified | Parity test for all four cases |
| B | Static files and evidence allowlisted | Verified | DEM, `.venv`, source, rasters and traversal all return 404 |
| B | Concurrency safe; blocking work off the event loop | Verified | Sync routes in a threadpool, bounded semaphore, 10-concurrent consistency test |
| C | Select target by globe click, coordinates or example; cell outlined; marker kept | Verified | Browser checks 1–2 |
| C | Terrain vs dry/barren screening explained; optional origin/radius; user-initiated geolocation; origin not persisted | Implemented; geolocation not browser-tested (needs a permission prompt) | Manual-entry path verified |
| C | Moon/Mars → Earth reveal of the returned top candidate; others then selectable | Verified | Camera, geometry and stage checks |
| C | Skip button, reduced motion and no-WebGL give the same final state | Verified | Browser checks |
| C | Stale requests and animations discarded on any change | Verified | Delayed-response, rapid-click and mid-reveal checks |
| C | Empty/error states with retry; no automatic relaxation | Verified | Sylhet, Shackleton, 503 and invalid-input checks |
| C | Laptop and mobile layouts, keyboard tabs, visible focus | Verified for 1440×900 and 390×844 | Screenshots in `analysis/screenshots/` |
| D | Evidence: values, units, differences, contributions, Earth-only context with epochs, provenance, limitations | Verified | Screenshot 02 |
| D | Two-candidate comparison explaining the ranking difference | Verified | Screenshot 03 |
| D | Gobi/Jaflong via approved routes; legend separates reference sites, candidates and local studies | Verified | Screenshot 09 |
| D | JSON, GeoJSON and printable brief traceable to the query; origin omitted by default | Verified | Export checks; screenshot 04 |
| E | API and browser checks, incl. poles, antimeridian, aliases, cell boundary, landing vs centre | Verified | 59 pytest tests + 18 browser checks, 0 console errors |
| E | Performance measured | Verified | [performance_2026-11-12.json](performance_2026-11-12.json) |
| F | Reproducible start, configuration example, runbook, CI | Done | [RUNBOOK.md](RUNBOOK.md), `.env.example`, `.github/workflows/ci.yml` |
| F | Container build | **Not verified** | `Dockerfile` written; build was not run here |
| F | Deployment | **Awaiting host and authorization** | — |
| G | `submission/` package | Drafted | Challenge-specific mapping is pending the official text (see blockers) |

## Decisions

- **Release binding.** `/api/v1` reads `prepared/current_release.json` (0.2.0) at startup. `processing/config.py` still defaults to 0.1.0 for the existing CLI and tests; this is intentional and left unchanged.
- **The scoring formula is unchanged.** No parameter was tuned.
- **Profile names.** Searches default to `dry_barren_terrain`, matching the release fixtures. `terrain_screening` is one click away, and the four unavailable profiles can be selected to return their missing-evidence explanation.
- **Display vs data geometry.** Engine and exports keep RFC 7946 polygons. The globe receives clockwise copies, because d3-geo otherwise fills each cell's complement.
- **The reveal follows only a completed live search with candidates.** Saved fixtures, empty results and unsupported results never animate.
- **Privacy of the travel origin.** It is sent only in the POST body and never echoed in errors. It is omitted from exports unless the user opts in; when omitted, distances are nulled too, since several distances could reveal the origin.
- **Validation errors never echo values.** FastAPI's default handler crashed when the rejected value was NaN, and it could leak an origin.

## Measured results (2026-11-12, i5-1235U, 12 threads, 15 GiB, Linux, Python 3.14.4)

| Workload | Median | p95 | Max | Errors |
|---|---:|---:|---:|---:|
| 40 random Moon/Mars HTTP searches, first request per query on a fresh server | 0.169 s | 0.360 s | 0.382 s | 0 |
| Same 40 repeated | 0.168 s | 0.359 s | 0.370 s | 0 |
| 80 searches from 10 concurrent clients (server admits 4 at a time) | 1.393 s | **1.810 s** | 2.207 s | 0 |

The ten-concurrent p95 meets the 2 s target on this machine with little margin; its maximum exceeded it. Throughput was 6.9 queries/s. The largest response was 29.6 KB. Server RSS was 198 MiB idle and **1.18 GiB at peak**. The OS page cache was not dropped, so "cold" means a fresh process, not a cold disk.

In the browser (headless Chrome, software WebGL), the panels were ready in 0.9–2.1 s. The in-page search round-trip was 150–330 ms at steady state, matching the server's compute time (Resource Timing showed ~0 ms browser queuing). During the first minutes after a cold start, background tile prewarming competes for CPU, and round-trips of 0.86 s and 3.9 s were observed. The reveal adds ~4.5 s of intentional animation (skippable). Imagery tile latency depends on external services and was not benchmarked.

## Defects found and fixed during this work

1. The whole `frontend/` directory was publicly served, including the 1 GB DEM, `.venv` and source code.
2. A NaN in a request crashed the validation-error response.
3. Globe polygons filled the entire planet except the cell (winding order).
4. Search errors were rendered on a hidden tab.
5. Tile error responses lacked CORS headers.
6. Failing upstream tiles were re-fetched on every request, each attempt holding a connection for up to 20 s.
7. Data-dependent tests failed instead of skipping in checkouts without LFS data.
8. Shutting down the self-check produced noisy prewarm thread errors.

## Remaining work and blockers

- **Official challenge text (blocker for final submission mapping).** `spaceappschallenge.org` failed TLS verification from this environment. Its chain ends at the legacy Comodo "AAA Certificate Services" root, which the local trust stores do not include, and verification was not bypassed. `submission/CHALLENGE_MAPPING.md` lists what must be filled in from the official page.
- **Container build and public deployment** are unverified/not performed. Deployment needs a chosen host and authorization.
- **Team details, portal submission and final narrated video** are external to this repository. A silent scripted recording exists locally (`submission/media/terratwin_demo.webm`, regenerate with `frontend/record_demo.py`).
- **Not built (outside the supported release):** geolocation browser test, common fixed physical footprints instead of native cells, relevance evaluation beyond the existing diagnostics, and additional scientific profiles.
- **Visual note.** Esri place-name tiles can appear as large blurred labels while higher zoom levels load. This is pre-existing imagery behavior.

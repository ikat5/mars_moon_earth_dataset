# Pre-existing assets and new work

Grounded in this repository's Git history (`git log`) as of 2026-11-12. Names are the Git author names recorded in the commits. Work outside the repository is not inferred, and nothing here verifies that history against the event's timeline rules (see [CHALLENGE_MAPPING.md](CHALLENGE_MAPPING.md)).

## Third-party data and software

All upstream datasets, imagery and libraries are listed in [ATTRIBUTION.md](ATTRIBUTION.md). None were created by the team. The integrated tables' metadata records upstream processing dates from 2026-11-01. The raw-to-integrated generation code is not in this repository.

## Repository history

| Date | Commit | Author | Contribution |
|---|---|---|---|
| 2026-11-06 | `2815994` | ikat | Integrated Moon and Mars datasets |
| 2026-11-06 | `ea927d3` | ikat | Teammate README |
| 2026-11-06 | `09f95df` | ikat | Integrated Earth dataset |
| 2026-11-06 | `2a53566` | Md Mashrafi | Verified preparation pipeline (`processing/`), releases 0.1.0–0.2.0, evaluations, Gobi/Jaflong studies, analysis documents |
| 2026-11-08 | `7fdb08b` | ikat | First globe frontend (React) and run instructions |
| 2026-11-11 | `27aba42` | ikat | Replaced with the FastAPI + globe.gl imagery/lunar-DEM explorer |
| 2026-11-11 | `7a25b54` | Md Mashrafi | Merged PR #1 |
| 2026-11-12 | `7b3c31f` → present | Md Mashrafi, with Claude Code (AI coding assistant; commits carry a `Co-Authored-By` trailer) | Branch `feat/terratwin-search-integration` (below) |

## New work on `feat/terratwin-search-integration` (2026-11-12)

- **Search API:** `frontend/terratwin_service.py`, the `/api/v1` adapter around the existing `processing.search.search`. It binds the release, enforces the request contract, keeps the four scientific outcomes distinct, bounds concurrency, and allowlists evidence routes.
- **Server hardening:** `frontend/app.py` gained module-relative paths, an optional DEM, lifespan startup, a static allowlist, tile-failure caching and CORS on tile errors.
- **Search workflow UI:** `frontend/terratwin.js`, `terratwin.css`, and a restructured `index.html`. Covers target selection, cell outline, screening modes, origin/radius, the Moon/Mars→Earth reveal, results, evidence, comparison, local studies, saved examples and exports. The existing globe, tile engines and label placement were kept.
- **Verification:** `processing/test_release_fixtures.py`, `processing/test_support.py`, `frontend/test_api.py`, `frontend/browser_check.py`, `frontend/perf_check.py`, `frontend/record_demo.py`, and CI.
- **Documentation:** `analysis/IMPLEMENTATION_STATUS.md`, `analysis/RUNBOOK.md`, `analysis/performance_2026-11-12.json`, `analysis/screenshots/`, this `submission/` folder, status notes in older documents, and deployment files (`Dockerfile`, `.dockerignore`, `.env.example`).
- **Unchanged:** the scoring formula, profiles, prepared releases and all original datasets.

`analysis/MASTER_IMPLEMENTATION_PROMPT.md` and `analysis/PROJECT_ANALYSIS.md` were team-authored guidance and review documents. They were committed on this branch as provided.

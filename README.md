# TerraTwin: planetary-to-Earth analog screening

Select a Moon or Mars region and retrieve Earth regions with explainable terrain resemblance. An optional historical dry/barren screen narrows the Earth candidate population. This workspace contains the analysis, reproducible data preparation, search callable and integration assets for the team's existing 3D globe.

The recommended first product is **regional terrain and navigation investigation**, with visible source footprints, environmental evidence and mismatches. Scores are experimental resemblance indices, not analog accuracy, base safety or predicted hardware performance.

## Start here

- [Master project blueprint](TERRATWIN_MASTER_BLUEPRINT.md): product decisions, innovations, scientific rules, architecture, priorities, validation and demonstration.
- [Measured preparation results](analysis/PREPARATION_RESULTS.md): what the current data actually supports.
- [App data handoff](analysis/APP_DATA_HANDOFF.md): callable, JSON/GeoJSON contract and globe integration requirements.
- [Data catalog](analysis/DATA_CATALOG.md): sources, epochs, resolution, integrity and attribution.
- [Reproduction instructions](processing/README.md): acquisition, processing and checks.

## Current data and examples

Use `prepared/0.2.0` for the current serving data and `prepared/app_0.2.0/cases.json` for the four integration fixtures. The original terrain-only release and intermediate investigations remain separately versioned. The full 2001–2017 vegetation series is processed and independently checked; it remains provisional, unscored context.

```bash
python -m processing.search --data-dir prepared/0.2.0 --profile dry_barren_terrain --body mars --lat 18.41 --lon 77.69 --output analysis/my_search.json
```

Install `processing/requirements.txt` first. This is a backend data query; a deployed API is not included in this workspace. The 3D globe frontend lives in [`frontend/`](frontend/) (see below).

## Run the frontend (TerraTwin globes)

The React + Vite 3D globe app is in `frontend/`. Requires Node.js 20.19+ (or 22.12+) and npm.

```bash
cd frontend
npm install
npm run dev        # starts the dev server, open the printed URL (default http://localhost:5173)
```

Production build:

```bash
npm run build      # outputs to frontend/dist
npm run preview    # serves the built app locally
```

## Clone and download

The original Earth/Mars tables and prepared Parquet tables use Git LFS. Install Git LFS, then clone and retrieve its objects:

```bash
git lfs install
git clone https://github.com/ikat5/mars_moon_earth_dataset.git
cd mars_moon_earth_dataset
git lfs pull
```

The original teammate guide is preserved in [ORIGINAL_DATASET_GUIDE.md](analysis/ORIGINAL_DATASET_GUIDE.md), including raw-table loading examples and grid definitions. The current preparation adds stricter comparison policies; shared names do not imply that every quantity can be compared across bodies.

Large source rasters are reacquired with the commands in `processing/README.md`; source catalogs, manifests and the prepared outputs are included. Failed builds and the superseded aridity output remain local only. Use `prepared/current_release.json` to identify the serving version.

The [Gobi candidate](analysis/GOBI_CANDIDATE_BRIEF.md) demonstrates global screening followed by finer inspection. The [Jaflong investigation](analysis/JAFLONG_LOCAL_PILOT.md) demonstrates why local exposed patches can be missed by regional cells. Neither is declared a newly discovered or field-verified analog. [Known-site review scope](analysis/KNOWN_ANALOG_REVIEW.md) is recorded separately.

Every successful match needs an explicit testing purpose. Missing terrain at Shackleton produces an insufficient-evidence response; the constrained Jezero search within 500 km of Sylhet produces no qualifying regional result. These are valid outcomes that the UI must preserve.

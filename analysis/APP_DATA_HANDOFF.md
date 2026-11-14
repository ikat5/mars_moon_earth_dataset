# TerraTwin data handoff for the existing globe

> **Status update 2026-11-12:** This handoff said the UI source was not present; the frontend now exists in `frontend/`. The globe is now connected to analog retrieval through `/api/v1` (`frontend/terratwin_service.py`, `frontend/terratwin.js`). See [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) for what is implemented and verified. The text below is preserved as written.

The prepared package supports **regional terrain resemblance** and an optional **historical dry/barren Earth screen**. The current serving release is `prepared/0.2.0`, including the complete 2001–2017 vegetation series as provisional, unscored context. This document concerns data integration, not an implemented web server or a replacement globe.

## What to load

Keep the three body Parquet tables on the backend. Do not send the complete tables to the browser. Load `prepared/app_0.2.0/cases.json` for the four reproducible demonstration cases, then load its referenced query and Earth GeoJSON files on demand. The entire app example folder contains **348,711 bytes**; this excludes optional dossier images/rasters and the backend data.

Two cases have ten Earth results each: Jezero's containing cell and an illustrative lunar coordinate at 0°N, 0°E. Two have intentionally empty results: the dry/barren Jezero search within 500 km of Sylhet and the unsupported Shackleton-center terrain query. Never replace those empty lists with unrelated preset results.

The index's Gobi and Jaflong investigation links point to sibling prepared directories. Serve those directories too if the UI uses these links. Their metadata, figures and GeoJSON files are small enough for on-demand loading; the source rasters are separate provenance inputs.

## Arbitrary selection

The same Python function serves arbitrary locations:

```python
from pathlib import Path
from processing.search import search

result = search(
    body="mars", lat=18.41, lon=77.69,
    data_dir=Path("prepared/0.2.0"),
    profile="dry_barren_terrain",
    limit=10,
    # Optional: origin=(24.89, 91.87), radius_km=500,
)
```

A service adapter should fix the prepared-data directory on the server, validate client inputs and call this function. Do not expose a client-controlled filesystem path or SQL expression. The current function supports `moon`/`mars`, finite latitude in [-90,90], east-positive longitude normalized to [-180,180), result limits 1–100, optional travel origin/radius, separation distance and overrides for the four documented terrain weights. Origins are calculation inputs; the processing function does not persist them.

`terrain_screening` omits environmental eligibility, while `dry_barren_terrain` requires the declared Earth land-cover/aridity conditions. Both use the same terrain formula. Other task profiles remain explicitly unavailable where their required evidence is missing.

## Interpret the response

| Field | UI meaning |
|---|---|
| `dataset_version`, `profile` | Display or retain for reproducibility |
| `target.geometry` | Selected native cell on the Moon/Mars globe, not an Earth geometry |
| `target.core_terrain` | Measurements of that regional cell, not the exact click point |
| `candidates[].geometry` | Earth candidate cell footprint |
| `observed_fit` | Uncalibrated terrain resemblance, 0–100; not probability or overall suitability |
| `comparisons` | Actual target/Earth values, differences and score contributions |
| `scored_feature_coverage` | Availability of the four score terms, not total scientific confidence |
| `earth_environment_context` | Earth-only historical conditions; not planetary similarity terms |
| `land_cover_screened`, `aridity_screened` | Whether those explicit Earth gates were applied |
| `vegetation_screened` | False; no definitive NDVI gate is enabled |
| `distance_from_origin_km` | Great-circle center distance, not travel time or access |
| `local_site_verified` | False for current candidates |
| `rank_stability` | Null for a live query unless a separate analysis was actually performed |

In exported GeoJSON, candidate fields live under each feature's `properties`, while its footprint remains the GeoJSON `geometry`. Exported scenario-retention diagnostics use the `sensitivity` object. The `supported_fit_lower`/`possible_fit_upper` values coincide for the complete scored feature set; they are **not** statistical confidence intervals.

Handle `ok`, `target_insufficient_evidence`, `no_candidates_under_filters` and `profile_unavailable` separately. An input error or service failure should not look like a scientific no-match conclusion. JSON missing values are null, never NaN or a fabricated zero.

## Make the selected footprint unmistakable

Highlight the entire native cell immediately after resolving the click. Keep the click marker visible but label the result as **“Regional cell containing this point.”** Show the cell's physical area and approximate data resolution. A named crater center is not a delta, crater rim, landing ellipse or base footprint.

This is essential because the current grid is discontinuous at cell boundaries. In measured tests, moving the click about **11.85 m** across a northern boundary near Jezero changed the compared regional cell and retained **0/10** top regions within 100 km. A lunar-equatorial pair separated by about **6.06 m** also retained **0/10**. Their entire regional terrain summaries changed; these are not terrain measurements varying over those few metres. [Boundary and geography checks](geography_validation_0.2.0.json).

Do not animate these scores as a smooth point-level suitability field. A future fixed-footprint/sliding-window method needs new preprocessing and validation; interpolation of the existing score would not supply the missing scientific evidence.

## Evidence panel and local investigations

For the Gobi case, show coarse resemblance alongside the finer WorldCover and DSM evidence. Keep the finer 30 m slopes separate from the four-term regional score. A mapped carbonate-sedimentary unit does not establish exposed materials or chemistry matching Jezero. Link [the dossier](GOBI_CANDIDATE_BRIEF.md).

For Jaflong, show the eight patch polygons as **local investigation candidates**, with no planetary score. Surface classification, source dates, clipped-component flags and potential water-editing effects must remain visible. Link [the local brief](JAFLONG_LOCAL_PILOT.md).

Known-site review belongs in a separate documentation panel. The current general portal feed is incomplete, and the 45-site PAAD catalog concerns dune fields. Neither supplies a global novelty verdict. Link [the review scope](KNOWN_ANALOG_REVIEW.md).

The globe's orientation, body-specific coordinate conversion, stale-response handling and deployed end-to-end interaction remain integration responsibilities. The UI source code is not present in this workspace, so those behaviors have not been verified here.

## Measured backend scope

The 0.2.0 callable plus compact JSON benchmark recorded p95 0.212 s for five sequential mixed queries and 0.792 s for twenty queries with ten workers. The largest response was about 29 KB, and process peak RSS was about 795 MiB. Warm caches and this small workload do not establish deployed HTTP/globe latency. See [benchmark conditions](benchmark_0.2.0.json).

The full vegetation series has 204 accepted processed months for 770,147 Earth cells and none for the other 643,546. The median gap-filled area/time fraction among supported cells is 57.9%; non-gap-filled source values are still smoothed. Show coverage, period and gap filling beside provisional NDVI. Do not equate a complete series with independent observed months, confirmed units or current seasonal suitability.

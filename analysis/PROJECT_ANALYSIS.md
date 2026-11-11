# TerraTwin project analysis

Reviewed 2026-11-12 against the current local checkout, including the frontend added after the original preparation reports. This is a repository analysis; it does not establish field suitability or confirm external source claims independently.

## Project purpose

TerraTwin aims to help planetary science students, rover teams and researchers choose Earth environments for a particular Moon or Mars investigation. The intended journey is to select a planetary region, choose a testing purpose, retrieve terrestrial candidates, inspect matching measurements and important differences, then investigate a finalist at finer resolution.

The implemented scientific capability is regional terrain resemblance, optionally restricted to historically dry, predominantly barren Earth cells. The broader blueprint also proposes material/geology profiles, cold/dry operations, cave reconnaissance, complementary two-site plans and brief exports. Those extensions are not implemented as supported search capabilities.

The current system has two substantial components: a reproducible data/search package and a three-world globe explorer. They are not yet connected into the intended selection-to-recommendation workflow.

## Repository map

| Location | Responsibility |
|---|---|
| `earth_integrated_dataset/` | Original Earth Parquet table, feature dictionary and source metadata |
| `moon_integrated_dataset/` | Original lunar table, definitions and source metadata |
| `mars_integrated_dataset/` | Original Martian table, definitions and source metadata |
| `sources/` | Pinned catalogs, download records, source snapshots and finer raster windows; many large downloads are local-only |
| `processing/` | Offline acquisition, quality checks, spherical aggregation, releases, retrieval, evaluations, evidence exports and tests |
| `prepared/` | Immutable versioned data, environment sidecars, UI fixtures and candidate dossiers |
| `analysis/` | Audits, evaluation outputs, interpretation, integration instructions and figures |
| `frontend/` | FastAPI imagery/DEM server and a single HTML/JavaScript globe page |
| `TERRATWIN_MASTER_BLUEPRINT.md` | Full product design and scientific policy; also contains roadmap items and some outdated frontend-status statements |

There is no current React application or Node build pipeline. The current browser application uses plain JavaScript, globe.gl, Chart.js and Tailwind loaded from CDNs. No CI workflow, container configuration or repository-wide Python package/build configuration was found in this checkout.

## Data and evidence

The integrated source tables contain 2,709,693 rows in total. These are regional grid cells, not independent observations or verified analog sites.

| Body | Rows | Native angular grid | Original feature definitions | Current definitions |
|---|---:|---:|---:|---:|
| Earth | 1,413,693 | 0.125°; retained land cells | 49 | 78 |
| Moon | 259,200 | 0.5°; full global grid | 87 | 87 |
| Mars | 1,036,800 | 0.25°; full global grid | 92 | 92 |

These grids have roughly 14–15 km equatorial cell dimensions, with width and physical area shrinking toward the poles. The original terrain inputs have nominal spacing around 463–474 m. Much finer imagery in the globe does not increase the resolution of the regional matching measurements.

The source dictionaries cover geology, terrain, environment, resources, surface processes, habitability, subsurface context and exploration. They explicitly distinguish measurements, models, catalogs, map interpretations and derived indices. Some features belong to multiple dimensions; dimension counts must not be summed as independent features.

Earth source families include NOAA ETOPO, lithology, MODIS temperature, ERA5 context, crater and cave inventories and dunes. Lunar sources include LOLA, Diviner, Lunar Prospector, GRAIL, geological maps, craters and pits. Mars sources include MOLA, TES, OMEGA, Odyssey, geological/crater/cave catalogs, SWIM and modeled climate. Their effective support, epochs and meanings differ. A shared column name does not establish comparability.

`prepared/current_release.json` selects **0.2.0**, whose serving data occupy about 424 MB including the planetary union table. There are 257 registered body-specific feature definitions. Terrain eligibility counts are 1,304,254 Earth cells, 257,760 Moon cells and 1,013,760 Mars cells. The stricter dry/barren terrain population contains 100,797 Earth cells before target-specific filtering.

Additional Earth evidence consists of:

- Strictly classified MODIS land-cover fractions for 2017, including separate quality/support fields.
- Global AI/ET0 aridity for the historical period 1970–2000. The corrected sidecar is `prepared/environment_0.1.0/aridity_0.1.1`; the older aridity output is superseded.
- All 204 monthly vegetation composites and 204 associated masks for 2001–2017. NDVI units remain provisional, and values are smoothed/gap-filled. NDVI is exported as context and has no effect on eligibility or rank.

The source terms are recorded per product. Land-cover derivative attribution/share-alike terms and conflicting aridity license statements are documented in `DATA_CATALOG.md`; the repository does not provide one verified blanket license for all upstream products.

## Preparation pipeline

`prepare.py` builds the terrain baseline from the supplied integrated tables. It preserves rows and finite measurements, converts nonfinite numerical values into explicit missing values, adds body-qualified IDs and native cell polygons, and computes quality/eligibility flags. It checks source schemas, coordinates, IDs, row counts, every source column and checksums before publishing a release.

The repository begins with integrated source tables. Their metadata describe upstream processing, but the complete original three-body raw-to-integrated generation code is not supplied here. Reproducibility is strongest from these supplied tables onward.

`acquire.py` and related acquisition modules use pinned catalogs and record source sizes and checksums. Completed files are reusable after verification; partial files are restarted rather than resumed by byte range. `aggregate.py` calculates spherical pixel-overlap weights rather than averaging latitude–longitude pixels equally. `environment.py` and `landcover.py` produce immutable sidecars with coverage separate from measurements.

`enriched_release.py` verifies sidecar manifests and independent verification reports before joining them to the baseline. It preserves planetary outputs and adds Earth-only environmental flags, definitions and the `dry_barren_terrain` profile. Failed staging directories are retained for inspection; published outputs refuse replacement.

`app_assets.py` exports compact case metadata and candidate GeoJSON. Other modules provide independent raster-window verification, known-site inventories, controls, geographic checks, score diagnostics, sensitivity evaluation, release comparisons and benchmarking. Gobi, Jaflong and polar modules create separate finer/contextual investigations.

## Retrieval behavior

The central callable is `processing.search.search`. It accepts a Moon/Mars body and coordinates, a prepared release, profile, result limit, optional Earth origin/radius, geographic separation and overrides for the four terrain weights.

The query sequence is:

1. Validate inputs and normalize longitude to [-180°, 180°).
2. Resolve the point to its containing native planetary cell.
3. Check profile availability and target terrain eligibility.
4. Read eligible Earth rows from Parquet through DuckDB, requiring an Earth/target cell-area ratio between 2/3 and 1.5.
5. Apply the optional great-circle radius constraint.
6. Calculate exact terrain scores using NumPy, sort deterministically and retain geographically separated results.
7. Return real cell polygons, physical values, differences, score contributions, historical environmental context and explicit review/validation flags.

This is a deterministic, explainable numerical retrieval method. There is no trained machine-learning model or learned embedding in the current matcher.

The four score terms are equally weighted by default:

| Term | Difference tolerance |
|---|---:|
| Median slope | 5° |
| 90th-percentile slope | 10° |
| Relief | 500 m |
| RMS roughness | 100 m |

For each term, `distance = min(abs(earth - target) / tolerance, 1)`. The score is `100 × (1 − weighted mean distance)`. The default cutoff is 50, default result count is 10 and default minimum separation is 100 km. These parameters are engineering assumptions, not calibrated analog-success criteria. TRI is required as a terrain-quality diagnostic but is not a fifth scoring term.

The dry/barren profile uses the same score after Earth-only gates: land-cover and aridity coverage at least 95%, barren-class fraction at least 80%, water at most 5%, built-up at most 1%, crops/mosaic at most 5%, and aridity index at most 0.20. No planetary NDVI or aridity value is fabricated to apply these gates.

Scientific outcomes include `ok`, `target_insufficient_evidence`, `no_candidates_under_filters` and `profile_unavailable`. Invalid inputs and service errors require distinct treatment in a future HTTP adapter. Fit is an uncalibrated resemblance index; its reported bounds are not confidence intervals. Live-query rank stability remains null unless separately evaluated.

## Current frontend

`frontend/app.py` serves three operational route families:

- `/tiles/{body}/{z}/{x}/{y}.jpg`: lunar/Martian tile proxy, stitching, visual processing and disk caching.
- `/api/sites`: hard-coded points of interest, with lunar telemetry added for Moon sites.
- `/api/query`: lunar DEM sampling at a coordinate.

Static files are served from the frontend working directory. The application requires starting inside `frontend/`, and opens `ldem_64.tif` during import. Texture generation, optional place-name acquisition and background tile prewarming also start during module initialization. These choices suit a local demo but couple startup, the working directory, raster availability and background work.

The Moon view combines Kaguya imagery with generated DEM textures and samples elevation, mean gradient slope, local elevation standard deviation and a 21-pixel west–east profile. Mars imagery combines CTX detail and Viking color. Earth uses Esri imagery/reference tiles. Mars and Earth clicks currently show imagery-only notices rather than integrated-table measurements.

The page includes body switching, labeled points, Gazetteer labels selected by visibility/overlap, surface toggles, fly-to controls and a telemetry chart. Sequence checks discard stale lunar query responses. Tiles and the DEM have separate purposes: filled lunar imagery gaps and synthetic Mars color/detail composites are presentation layers, not new scientific measurements.

**There is no call from this server/page to `processing.search.search`, no analog-search HTTP endpoint, and no candidate-results or evidence-panel workflow.** The Earth pins are a fixed list of known analog examples; they are not retrieved results. Prepared fixtures and dossiers outside the frontend folder are not exposed by its current static mount.

## Demonstration evidence

The current app fixture package contains four cases and twenty Earth candidate polygons:

| Case | Published outcome |
|---|---|
| Jezero crater-center cell | Ten screened Earth candidates |
| Moon at 0°N, 0°E | Ten screened Earth candidates |
| Jezero terrain within 500 km of Sylhet | No candidates under the selected filters |
| Shackleton crater center | Insufficient integrated target terrain |

The Gobi dossier investigates Earth cell 1090899 at 42.6875°N, 102.4375°E. Its archived Jezero terrain fit is about 99.72/100. Independent finer land-cover context is predominantly bare/sparse, while 30 m DSM slopes reveal variation hidden in the coarse summaries. Material equivalence, access, field suitability and novelty are not established.

The Jaflong dossier contains eight local classified patches of at least 0.5 ha. It demonstrates that a regional screen can miss small exposed patches. Seven have potential water-editing concerns in their DSM terrain context. These patches have no planetary match scores.

Independent lunar polar products supply contextual Shackleton measurements with different definitions. They do not fill the integrated target's missing fields or enable a supported match.

## Important integration and scientific findings

1. **The primary implementation gap is the complete search interaction.** The prepared callable, examples and explanation contract already exist, but the globe does not expose them.
2. **Jezero identity differs between components.** The viewer pin uses the Perseverance landing point (18.4447°, 77.4508°), resolving to `mars:412869`. The main fixtures use the crater center (18.41°, 77.69°), resolving to `mars:412870`. Their results must be queried independently and labeled accordingly.
3. **Viewer telemetry and matcher measurements differ.** The viewer's 5×5 lunar gradient mean and elevation standard deviation cannot silently replace the regional table's median/p90 slope and RMS roughness. Their footprints and definitions differ.
4. **Tiny click movements can switch whole regions.** Archived boundary experiments near Jezero and the lunar equator retained none of the top ten Earth regions after crossing a cell boundary by metres. A visible native target polygon is essential. Fixed-size physical-window comparisons require new preparation and evaluation.
5. **Current-release selection is not centralized in runtime defaults.** The release pointer selects 0.2.0, but `config.DEFAULT_OUTPUT`, the CLI and several tools still default to the 0.1.0 terrain baseline. A service should explicitly bind the intended release/profile.
6. **Document status is mixed.** The root README reflects the newer frontend. Older preparation/handoff/blueprint passages still say its code is absent; the code is now present, while analog integration remains absent. The processing README's temporary dependency directory is also absent in this session.
7. **Polar globe sampling has an approximation.** The viewer floors the longitude spacing factor at `cos(latitude) = 0.12` and clips raster rows at the poles. Its high-latitude slope/profile metrics need separate validation before use as scientific matching evidence.
8. **Operational validation is narrower than the product ambition.** There are sixteen existing unit/integration test methods and extensive archived diagnostic reports, but no automated full browser/search workflow or CI was found. The viewer depends on live CDN/imagery services and uses globe.gl scene internals for its custom tile engines.

## Verification performed during this review

- Parsed all processing Python modules and inspected the main preparation, aggregation, enrichment, retrieval, frontend, export and validation implementations.
- Recomputed file size and SHA-256 checks for **39 files across seven current manifests**: serving release, app fixtures, Gobi, Jaflong and three environmental sidecars. All matched.
- Checked all four exported case statuses/counts and all twenty candidates' contribution totals and scientific screening flags. All passed.
- Ran the two existing environmental-screening unit tests, covering missing evidence, independent exclusions and threshold boundaries. Both passed.
- Parsed the frontend inline JavaScript with Node. Syntax passed.
- Confirmed that the local lunar DEM, generated textures and tile-cache directory are present.

The full processing test suite, live search queries, fresh raster-window calculations, frontend self-check and browser interactions were not rerun. DuckDB, Rasterio, PyProj, FastAPI and Matplotlib are unavailable in the Python environments inspected for this session. Existing reports describe earlier successful checks and benchmark results; they are historical evidence, not fresh execution here. The published warm-cache benchmark records approximately 0.212 s sequential p95 and 0.792 s p95 with ten workers, excluding HTTP and browser rendering.

No application or dataset files were changed during this review. This analysis document is the sole new deliverable; pre-existing untracked frontend bytecode was left in place.

## Recommended next sequence

1. Bind a small HTTP search adapter to the intended version/profile, using the current callable and validating request inputs.
2. Connect globe selection to a visible planetary source-cell polygon and a search action. Keep the original selection and resulting Earth candidates distinct when switching bodies.
3. Render returned Earth footprints and a ranked list with actual values, units, score contributions, strongest mismatch, historical context and provenance.
4. Implement all scientific outcome states, loading/failure handling and stale-response protection for search.
5. Link the Gobi/Jaflong evidence assets and preserve their distinct investigation status.
6. Validate the full workflow with fixture and arbitrary targets, coordinate controls, rapid clicks/body switches, empty results and missing target evidence. Measure actual service/browser performance.
7. Update stale status documents and make environment setup/release selection reproducible. Then pursue common physical footprints, broader relevance evaluation and additional scientific profiles.

The present repository is an explainable regional analog-screening foundation with reproducible evidence and a separate globe explorer. Its clearest next milestone is one complete, inspectable planetary-selection-to-Earth-result workflow.

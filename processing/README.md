# TerraTwin data processing

Use `prepared/0.2.0` for the current terrain + historical dry/barren Earth screening capability. It preserves the three-body source measurements and adds explicit Earth-only land-cover/aridity gates. `prepared/0.1.0` remains the immutable terrain baseline. Full 2001–2017 NDVI is processed and independently checked; it remains provisional, unscored context. Outputs are regional screening assets, with finer remote-sensing investigations and predeclared reference checks; field validation remains outstanding.

## Reproduce

Use Python 3.12 or later and install `processing/requirements.txt` in an isolated environment. From the repository root:

```bash
python -m processing.prepare --output prepared/NEW_VERSION
python -m unittest processing.test_processing -v
python -m processing.search --body mars --lat 18.41 --lon 77.69 --output analysis/my_search.json
python -m processing.evaluate
```

`prepare` refuses to replace an existing release. The supplied default release identifier is 0.1.0; update `processing/config.py` when intentionally releasing a new version. A failed build leaves a `.building` directory for inspection. The tests/evaluation use the default release; `search` accepts `--data-dir` for other prepared versions.

The current session uses dependencies in `/tmp/terratwin-audit-deps`, invoked with `PYTHONPATH=/tmp/terratwin-audit-deps`. This is an execution environment, not an output dependency: install the requirements normally to reproduce elsewhere. CLI searches default to the original terrain release, so explicitly pass `--data-dir prepared/0.2.0 --profile dry_barren_terrain` for the enriched capability.

## Prepared outputs

- `earth_features.parquet`, `moon_features.parquet`, `mars_features.parquet`: source measurements with explicit eligibility and cell footprints.
- `planetary_features.parquet`: union of Moon and Mars, with body-specific applicability documented in the registry. Missing columns from the other body's schema are not fabricated observations.
- `feature_registry.json`: 257 body/feature definitions in 0.2.0 (228 in the original terrain release) and comparison policies.
- `profiles.json`: experimental terrain weights/tolerances and unavailable-profile requirements.
- `targets.json`: sourced named-feature centers for Jezero and Shackleton, distinguished from mission landing footprints.
- `provenance.json`, `manifest.json`, `validation.json`: checksums, source documentation and checks of every source column after finite-value normalization.
- `readiness.json`: completed steps and remaining work; not a declaration of full project completion.

## Quality and retrieval rules

Quality flags describe low DEM coverage, incomplete/invalid terrain, elevation ordering, unknown geology, missing temperature and suspect low Earth elevations. Every row remains in the output. See `processing/config.py` and the registry for the bit definitions.

Eligible terrain requires the five core fields, physically valid terrain, at least 95% DEM coverage, consistent elevations and no flagged deep-negative Earth elevation. Geology and temperature availability do not gate the terrain-only profile. The four scoring terms avoid adding TRI and derived hazard indices as extra evidence.

Native Earth and planetary cell areas must have a ratio between 2/3 and 1.5. This is an experimental support check, not proof of equivalent resolution. Scores use declared physical tolerances. Default results are at least 100 km apart; returned polygons are actual source cells, not mapped extent of an analog site. A 50-point cutoff is an engineering default, not a scientifically validated acceptance threshold. No result is labeled a verified analog, vegetation-screened or physically equivalent.

Examples:

```bash
python -m processing.search --body moon --lat -89.67 --lon 129.78
python -m processing.search --body mars --lat 18.41 --lon 77.69 --origin 24.89 91.87 --radius-km 500
```

The first correctly reports missing target terrain. The second is an illustrative radius query around Sylhet; it does not establish access, local dryness or equipment suitability.

## Enrichment acquisition

Public catalog snapshots are in `sources/catalogs`. The selected vegetation source is OpenGeoHub's MODIS/AVHRR-derived monthly 5 km product, with its auxiliary smoothed/gap-filled masks, for 2001–2017. Aridity uses the pinned Global AI/ET0 v3 annual archive with historical 1970–2000 climatology. The periods differ and must remain explicit in derived features.

```bash
python -m processing.acquire --plan-only
python -m processing.acquire --sample
python -m processing.acquire --workers 8
```

The full plan is approximately 4.09 GB in 410 files. Completed downloads are reused only after publisher MD5 and size checks; SHA-256 is recorded locally. Metadata inspection and scientific raster processing must precede incorporating them into a new prepared release. Auxiliary vegetation flags are necessary because the product includes smoothing and gap filling. Neither low NDVI nor climatic aridity alone establishes bare ground, absence of biology or a usable field site.

Process the verified inputs separately from the immutable terrain release:

```bash
python -m unittest processing.test_aggregate -v
python -m processing.environment ndvi --sample
python -m processing.environment aridity
python -m processing.environment ndvi
```

The January 2001 sample has been processed to `prepared/environment_0.1.0/ndvi_sample`. Full-series processing requires all expected input files; an incomplete download cannot silently become a complete release. Output folders are immutable. Aggregation uses exact spherical source/target pixel intersections, with missing area separated from measurements. Aridity processing reads the large rasters in bounded blocks.

**NDVI scale remains provisional.** The derivative's GeoTIFF scale is 1 and its catalog omits an explicit storage multiplier. The inferred factor 0.0001 matches the documented NOAA parent convention and the derivative's raw range, but this is not independent provider confirmation. Both raw and explicitly provisional values are exported. A definitive low-vegetation gate must wait for confirmation or a replacement product with documented units. The sample is one month, not a climatology.

Aridity's 0.0001 scale is documented by the provider. Its Figshare license metadata says CC BY 4.0, while its README and description specify non-commercial use. Both statements are recorded; this workflow does not infer commercial clearance. Corrected processing is published at `prepared/environment_0.1.0/aridity_0.1.1`: AI requires valid positive reference ET0 support because the AI raster alone has no nodata tag and uses zero for both dry land and ocean background. Seven independent window checks passed. The old `aridity` output is superseded and must not be used for screening.

The 2017 MODIS IGBP land-cover mosaic and its QC raster add a separate 166.7 MB acquisition. The derivative uses **CC BY-SA 4.0**; metadata is copied from its pinned catalog. QC=1 can label unclassified land as barren, so strict fractions admit only classified land/water codes 0 and 2. Corrected/backfilled fractions are reported separately. Fractions describe classified pixel area, not measured bare-rock percentage.

```bash
python -m processing.acquire_landcover
python -m unittest processing.test_landcover -v
python -m processing.landcover
python -m processing.finish_enrichment
```

`finish_enrichment` is a local worker for ongoing downloads. It processes each of land cover, aridity and full-series NDVI when its required files arrive, validates published manifests, and writes `analysis/enrichment_worker_status.json`. It stops on a processing error or after eight hours without all sources. It does not claim that derived data constitute scientific analog validation. The downloads run separately and can be resumed at the file level with their acquisition commands.

The land-cover stage is now published: 916,840 Earth cells meet 95% strict coverage, and 105,337 also have at least 80% barren-class area. Six independent source-window checks passed (`processing.verify_enrichment landcover`), including Yungay, Manaus forest, Cinder Lake, Garwood Valley and two terrain-search candidates. This is aggregation verification, not field validation of the classifications.

The complete land-cover and aridity inputs already support a separate screening release without NDVI:

```bash
python -m processing.enriched_release --screening-only
python -m processing.validate_controls --data-dir prepared/0.1.1
python -m processing.search --data-dir prepared/0.1.1 --profile dry_barren_terrain --body mars --lat 18.41 --lon 77.69
python -m processing.evaluate --data-dir prepared/0.1.1 --profile dry_barren_terrain --output-dir analysis/evaluation_0.1.1
```

Release 0.1.1 is published with 100,797 eligible dry/barren terrain cells. Predeclared Yungay, Manaus and Garwood checks passed, and Cinder Lake exposed the intended local-versus-regional scale limitation. The 500 km Sylhet case returns no qualifying regional cells. NDVI is explicitly omitted, with no effect on the terrain score or environmental thresholds.

After all three full enrichment sidecars exist, add the full vegetation series as **unscored provisional context**:

```bash
python -m processing.verify_enrichment landcover
python -m processing.verify_enrichment aridity
python -m processing.verify_enrichment ndvi
python -m processing.enriched_release
python -m processing.verify_release_upgrade
python -m processing.validate_controls --data-dir prepared/0.2.0
python -m processing.search --data-dir prepared/0.2.0 --profile dry_barren_terrain --body mars --lat 18.41 --lon 77.69
```

The builder requires the independent verification reports to pass and match each input manifest hash. The full NDVI check independently computes spatial overlap and temporal reductions for six windows across all 204 months. It does not confirm the derivative's undocumented scale or its model accuracy. `verify_release_upgrade` checks all prior Earth columns/gates, planetary file hashes and five real queries against 0.1.1: provisional NDVI must not change the results.

Release 0.2.0 is published. All 410 planned NDVI/aridity files completed verification; independent NDVI checks passed at six sites across all 204 months. The builder refuses incomplete or independently unverified inputs. The Earth-only environmental gates are separate from the unchanged four-term terrain score. Tests verify that missing values and cells violating the declared aridity/land-cover thresholds cannot pass, and that an Earth-only gate is not incorrectly required on a Mars target. The four reference sites and their primary sources are predeclared in `analysis/control_sites.json`; results for 0.1.1 are in `analysis/control_evaluation_0.1.1.json`.

## Local micro-analog investigation

`prepared/local_pilot_0.1.1` contains eight >=0.5 ha candidate patch polygons near Jaflong, 10 m WorldCover source context, 30 m DSM-derived context, metadata and a figure. The same-product comparison shows 1.97% bare/sparse class in the surrounding regional cell and 5.48% in the local window. No planetary score, field permission or material suitability is assigned. Seven patches are flagged for potential water-editing effects on DSM slopes. See [the local pilot report](../analysis/JAFLONG_LOCAL_PILOT.md).

```bash
python -m processing.acquire_local_pilot
python -m processing.acquire_local_pilot --regional
MPLCONFIGDIR=/tmp/terratwin-matplotlib python -m processing.local_pilot
```

These commands reproduce the pilot in a fresh workspace. Source and prepared folders refuse replacement. Version 0.1.0 is retained, but use 0.1.1 because it adds water-editing and clipped-component flags. Remote COG windows are locally hashed; remote whole-file checksums were not verified.

## Global candidate investigation

`prepared/gobi_candidate_0.1.0` characterizes Earth cell 1090899 with finer WorldCover and Copernicus DSM windows. It includes a GeoJSON footprint, per-source evidence, a figure and explicit material/novelty limitations. About 99.565% of the footprint is WorldCover bare/sparse class, but finer slopes reveal terrain variation hidden by the original regional summaries. See [the candidate brief](../analysis/GOBI_CANDIDATE_BRIEF.md).

```bash
python -m processing.global_candidate --download
MPLCONFIGDIR=/tmp/terratwin-matplotlib python -m processing.global_candidate
```

## Polar context and globe integration

```bash
python -m processing.polar --download
python -m processing.app_assets
MPLCONFIGDIR=/tmp/terratwin-matplotlib python -m processing.figures
```

Two NASA LOLA products provide independent Shackleton context using 400 m plane-fit baselines and 1 km raster spacing. Results are in `analysis/shackleton_polar_context.json`. They are not replacements for differently defined integrated terrain fields and do not enable a supported Shackleton match.

`prepared/app_0.2.0/cases.json` indexes four UI cases and 20 Earth footprints using the dry/barren profile. Jezero and the illustrative lunar equatorial coordinate have results; Sylhet and Shackleton correctly have none under the selected requirements. Evidence includes per-feature explanations, historical environmental context and scenario-retention diagnostics. Related Gobi and Jaflong investigations link to sibling prepared folders, which must also be served if those links are used. The earlier `app_0.1.0` remains a terrain-only baseline with 30 footprints. The CLI supports arbitrary coordinates; exported cases are integration fixtures, not deployed UI.

```bash
python -m processing.search --data-dir prepared/0.1.1 --profile dry_barren_terrain --body moon --lat -89.67 --lon 129.78 --output analysis/evaluation_0.1.1/queries/shackleton_coverage.json
python -m processing.app_assets --output prepared/app_0.1.1 --data-dir prepared/0.1.1 --query-dir analysis/evaluation_0.1.1/queries
```

The reproducible scientific overview is `analysis/figures/dataset_diagnostics.png` and its PDF counterpart. The PDF was rendered and visually inspected.

## Release diagnostics and serving fixtures

```bash
python -m processing.summarize_release --data-dir prepared/0.2.0
python -m processing.evaluate --data-dir prepared/0.2.0 --profile dry_barren_terrain --output-dir analysis/evaluation_0.2.0
python -m processing.validate_geography --data-dir prepared/0.2.0
python -m processing.score_diagnostics --data-dir prepared/0.2.0
python -m processing.benchmark --data-dir prepared/0.2.0
python -m processing.search --data-dir prepared/0.2.0 --profile dry_barren_terrain --body moon --lat -89.67 --lon 129.78 --output analysis/evaluation_0.2.0/queries/shackleton_coverage.json
python -m processing.app_assets --output prepared/app_0.2.0 --data-dir prepared/0.2.0 --query-dir analysis/evaluation_0.2.0/queries
MPLCONFIGDIR=/tmp/terratwin-matplotlib python -m processing.release_figures
python -m processing.verify_handoff
```

Run the benchmark after other heavy processing jobs finish. It measures the callable and compact JSON serialization in sequential and ten-worker workloads; HTTP/network/browser performance is excluded. Geography checks cover 24 arbitrary selections, longitude aliases and two boundary probes. Boundary sensitivity is reported, not hidden by interpolation.

The baseline figure under `analysis/figures` is retained. The complete-release figure uses the versioned `analysis/figures_0.2.0` folder. Integration details are in [APP_DATA_HANDOFF.md](../analysis/APP_DATA_HANDOFF.md).

The handoff verifier checks serving manifests, case counts, geometry/flags and related paths, then writes `prepared/current_release.json`. Its pointer selects 0.2.0; CLI defaults remain the original terrain fixture unless `--data-dir` is supplied. Do not serve superseded aridity or the preserved failed app-export folder.

## Known analog documentation

`processing.analog_inventory --download` acquires the public general portal feed discovered in its client script; `--import-paad FILE` snapshots an already downloaded PAAD GeoJSON. The default review and `--paad` review produce separate records. Their catalog coverage differs and is inadequate to certify global novelty. See [KNOWN_ANALOG_REVIEW.md](../analysis/KNOWN_ANALOG_REVIEW.md) for exact source URLs, acquisition limitations and candidate conclusions.

## Remaining work

Confirm NDVI scale or replace the product before enabling a vegetation gate, harmonize polar footprints, validate material comparisons, broaden external evaluation and conduct current local/field checks. The existing environment screening and candidate dossiers do not complete these remaining steps. For the larger product roadmap, use the master blueprint; do not interpret unavailable profiles as implemented capabilities.

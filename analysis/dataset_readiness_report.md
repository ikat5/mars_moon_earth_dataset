# Dataset readiness for the terrestrial analog challenge

Assessment date: 2026-11-06.

**Verdict:** The local Earth, Moon, and Mars datasets are sufficient for a useful regional analog discovery prototype, especially terrain and rover-mobility comparisons. They do not yet support equally strong conclusions about geology, polar environments, caves, biological analogs, or actual landing/base safety. The highest-value next work is to improve Earth selection criteria and feature comparability, rather than collect more planetary columns indiscriminately.

The challenge allows a location to be analogous in particular characteristics. A defensible submission should therefore identify *what a site is useful for testing*, report dimension-specific similarities, and explain physical differences. NASA describes this use of [planetary analogs](https://science.nasa.gov/solar-system/planetary-analogs/).

## What was inspected

All three local integrated Parquet tables were scanned, alongside their feature dictionaries and source/processing metadata. The audit checks schema, unique cell IDs, finite-value coverage, area-weighted coverage, numeric ranges, categorical distributions, and selected quality issues. It does not independently reprocess the raw source data, establish ground truth, or identify and validate new analog sites.

| Dataset | Actual rows | Total columns | Feature columns, excluding four spatial identifiers | Grid width at equator |
|---|---:|---:|---:|---:|
| Earth | 1,413,693 | 53 | 49 | 13.9 km |
| Moon | 259,200 | 91 | 87 | 15.16 km |
| Mars | 1,036,800 | 96 | 92 | 14.82 km |

Earth contains selected land-intersecting cells; Moon and Mars contain their complete configured latitude-longitude grids. All three have unique cell IDs within their respective table. IDs are not shared geographic identifiers between bodies.

Earth and Mars share **47 feature names**; Earth and Moon share **36**; **36** occur in all three. Shared names are not a count of independent, scientifically comparable measurements. Some are quality variables, redundant terrain statistics, derived indices, or body-specific categorical vocabularies.

## Readiness by challenge dimension

| Dimension | What the existing data supports | Main limitation | Assessment |
|---|---|---|---|
| Terrain and topography | Regional matching of slope distributions, relief, ruggedness and roughness | Roughly 470 m DEM sampling aggregated into approximately 15 km cells misses small hazards | Strongest current dimension |
| Geology and materials | Coarse volcanic, sedimentary and other context; richer planetary chemistry/mineralogy | Earth has broad lithology classes, no matching chemical abundance grids; volcanic does not necessarily mean basaltic | Useful screening; insufficient for detailed material analogy |
| Temperature and environment | Characterizing relative cold, heat and seasonality | Different sampling definitions; Mars climate is a coarse model; Earth Antarctic temperature omitted | Useful with explicit caveats |
| Water and ice | Snow/soil-water context on Earth; lunar thermal/neutron proxies and Mars SWIM/GRS context | Shared water scores use different inputs; no common measurement of accessible resources | Preliminary process context |
| Dust and aeolian processes | Earth/Mars dunes and modeled winds | Earth lacks dust opacity, grain size and transport/activity measurements; wind speed alone does not reproduce sediment transport | Partial |
| Biology and habitability | Limited physical context | No microbial observations, biological inventories or Earth biosignature measurements; vegetation and aridity layers absent | Insufficient for biological claims |
| Caves and subsurface | Finding areas near cataloged caves or candidate openings | Incomplete Earth catalog; most planetary cave interiors unknown; proximity is not evidence of a lava tube | Weak without site-specific validation |
| Exploration operations | Selecting regional terrain for rover or field-work trials | No boulder-scale hazard assessment, soil strength, bearing capacity or detailed construction information | Regional testing context only |

## Is there enough Earth data?

Yes for an initial global land search. Actual coverage is:

| Earth feature | Valid rows | Represented cell area with data |
|---|---:|---:|
| Median slope | 99.73% | 99.71% |
| Terrain roughness | 92.26% | 91.99% |
| Dominant lithology | 69.77% | 90.46% |
| Mean surface temperature | 71.89% | 91.40% |
| Distance to a cataloged cave | 100% | 100% |

Area percentages use the table's `area_km2` column and refer to the represented cells, not an independently measured land-only footprint inside coastal cells. Polar cells are smaller than equatorial cells, so row and area coverage differ substantially.

**891,305 Earth cells (63.05% of rows)** simultaneously have finite median slope, 90th-percentile slope, relief, roughness, TRI, mean temperature, and nonmissing lithology. This is a missing-data count, not a quality-approved candidate count. It is ample for screening, although neighboring cells and repeated coarse climate values are not independent observations.

The limiting issue is the kinds and quality of data, rather than row count:

1. **Antarctica is omitted from two key Earth layers.** All 393,244 Earth rows south of 62 degrees S lack mean temperature and lithology in this release. This is a limitation of the integrated products used here, not a statement that no Antarctic Earth-observation data exist. It removes an important class of cold, dry and polar analogs from combined rankings.
2. **No explicit desert or bare-ground selection.** There is no NDVI, land-cover class, precipitation, precipitation/PET aridity index, or exposed-ground fraction. A terrain-only search can select vegetated or otherwise unsuitable terrain.
3. **Broad lithology is not material characterization.** All four Earth geology features come from one generalized lithology product. Its fine raster spacing does not undo the generalization of the underlying map. Basaltic, silicic volcanic and pyroclastic environments should not automatically be treated as equivalent.
4. **Cave catalog completeness is not 100%.** The distance column has values everywhere because every cell can be assigned a nearest catalog point. The table counts 15,155 cave records in 5,787 cells, but metadata describes a crowd-sourced catalog containing mostly ordinary caves and only roughly 50 lava tubes. Large regions with `nearest_cave_setting=lava_tube` do not imply many tubes or verified caves at those locations.
5. **Some selected land cells need investigation.** There are 17,347 cells with `dem_valid_frac < 0.1` and 50,694 with it below 0.5. Four cells near latitude/longitude zero have mean elevation around -4,936 m and valid fractions about 0.0011. These are suspect land-selection or coastal/mask artifacts; the cause has not been established. Correct the mask or inspect the source data, and apply a documented minimum valid fraction before ranking.
6. **Detailed Earth source files are missing locally.** Metadata lists `earth_impact_craters.parquet` and `earth_vectors.gpkg`, but neither was published in the downloaded Earth directory. Aggregated features are present; catalog-level follow-up needs the source files or another verified catalog.

## Comparisons that need redesign

### The configured analog recipe cannot compare two of its six dimensions on Earth

The `processing_config.analog.features` section in the metadata requests:

- Geology: `feo_wt`, `sio2_wt`, `k_ppm`, `th_ppm` — **all absent on Earth**.
- Surface processes: `rock_abundance` — **absent on Earth**.
- Terrain: seven of eight configured columns exist; `crater_sfd_slope` is absent.
- Environment: all five configured names exist, but temperature definitions differ.
- Subsurface: only `cave_candidate_distance_km`.
- Exploration: only `landing_hazard_index`, itself derived from terrain.

Consequently the configured `min_dimensions=4` can, at most, be satisfied by terrain, environment, cave proximity, and a second terrain-derived score. It does not establish four independent scientific dimensions. This assessment concerns the stored recipe; no executable scoring implementation was supplied or evaluated.

### Same names can conceal different quantities

- **Temperature extrema:** Earth uses warmest/coldest monthly-median MODIS overpass temperatures; the Moon uses binned Diviner bolometric temperatures across the lunar day; Mars uses sampled modeled annual extremes. Earth `tsurf_min_k` ranges from 222.45 to 302.05 K, Mars from 141.35 to 194.46 K, and Moon from 19.39 to 131.98 K. These recorded ranges do not overlap. An algorithm will still return a nearest location, but that does not establish a close thermal match. Sampling differences and Antarctic omissions matter.
- **Water indicators:** Earth combines normalized soil moisture and snow; the Moon combines cold-trap/ice-stability and hydrogen proxies; Mars combines GRS, SWIM and ejecta context. Equal 0-1 scores do not mean equal water content, accessibility, or resource value. The Earth score is saturated at 1 in 438,349 cells.
- **Solar-power index:** Moon uses sunlit-time fraction; Earth and Mars use normalized surface irradiance. These are different quantities. Do not compare the shared index directly.
- **Geology and caves:** `geo_unit` and `nearest_cave_setting` use different vocabularies on each body. Build an explicit process/material crosswalk and retain unmatched categories.
- **Crater density:** Earth preservation and catalog completeness differ from planetary records. Earth `crater_density_d1` is exactly zero in over 99.7% of cells. Catalog availability and preservation must be considered; zero is not a good general surface-age analogy.
- **Absolute elevation:** Reference surfaces differ by body. Relative relief and local topographic form are usually more interpretable for terrain analog tasks.
- **Wind:** Equal speed does not imply equal aerodynamic force or sediment transport in different atmospheres. Pressure, air density, gravity and grain properties matter.

### Effective resolution is coarser than the output grid for several layers

The metadata describes Earth ERA5 climate at 0.25 degrees, Mars climate at roughly 5.625 by 3.8 degrees, lunar Prospector chemistry near 60 km, and Mars GRS chemistry near 450-600 km footprints. Mapping those values into approximately 15 km cells does not create local information. Report source resolution, group validation spatially, and do not present cell-level confidence as though all inputs were measured there.

Lunar polar layers and Mars SWIM coverage are regional by design. Low global coverage of such a layer is not automatically poor quality; assess completeness inside the target region.

## Highest-value additions

| Priority | Addition | Purpose and candidate source |
|---|---|---|
| 1 | Vegetation and bare-ground/land-cover filtering | Avoid selecting forests or developed terrain. NASA [MODIS vegetation indices](https://modis.gsfc.nasa.gov/data/dataprod/mod13.php) provide NDVI/EVI; add a land-cover layer with checked coverage. Low NDVI alone is not proof of sterility. |
| 1 | Precipitation and climatic aridity | Distinguish dry analogs from merely warm/cold terrain. [TerraClimate](https://www.climatologylab.org/terraclimate.html) provides precipitation and reference evapotranspiration; check product version, regional validity and temporal baseline. |
| 1 if polar analogs are a focus | Antarctic surface temperature and snow/ice context | Ingest appropriate source products with verified Antarctic coverage and QA, rather than filling missing values with global medians. NASA [MODIS snow products](https://nsidc.org/data/mod10a1/versions/61) support snow context but do not by themselves fill the temperature/geology gaps. |
| 2 | Material/process crosswalk and regional mineral evidence | Distinguish basalt, silicic volcanics, sediments, evaporites and alteration. [ASTER GED](https://data.nasa.gov/dataset/aster-global-emissivity-dataset-100-meter-hdf5-v003-ee2b0) offers emissivity context, not direct global FeO/SiO2 chemistry; combine with regional geology and validated spectral interpretation. |
| 2 if aeolian analogs are a focus | Dust activity, sediment availability and grain properties | NASA [MERRA-2](https://gmao.gsfc.nasa.gov/gmao-products/merra-2/) adds aerosol context, but is a coarse reanalysis; use local observations for testing claims. |
| 2 for finalist sites | Higher-resolution imagery, DEMs and verified cave/impact records | Characterize shortlisted valleys, lava flows, craters and openings. [Landsat Collection 2](https://www.usgs.gov/landsat-missions/landsat-collection-2-level-2-science-products) supplies surface reflectance/temperature imagery. Choose local DEM and catalog sources appropriate to each location. |

These are proposed additions, not downloaded or validated layers in this workspace. The challenge does not require filling all dimensions. Pick additions that support the chosen scientific or operational claim.

## Recommended submission scope and validation

Start with separate searches for **terrain/mobility**, **volcanic/material**, and **cold/dry-environment** analogs. Caves or ice can become dedicated profiles once better supporting data are integrated. Define each profile around a specific Moon/Mars target region or operational task.

For each profile:

1. Screen land/validity, vegetation, land cover and applicable environmental constraints; retain missing-data flags.
2. Compare harmonized physical measurements with declared scaling and tolerances. Use a few representative terrain measurements so correlated slope/roughness statistics do not dominate. Do not add derived terrain indices as independent evidence on top of their inputs.
3. Require the essential features for that profile; report observed coverage and source resolution. Do not allow missing geology or temperature to improve a candidate's similarity by silently dropping dimensions.
4. Report a score per dimension plus physical mismatches. Treat any combined score as a declared ranking rule, not a calibrated probability of analogy.
5. Merge nearby high-ranking cells into candidate regions, then inspect finalists using imagery, regional geology and finer terrain data. Vary weights, thresholds and missing-data rules to assess rank stability.
6. Use known analogs as sanity checks, and compare finalists against the [USGS known terrestrial analog sites dataset](https://www.usgs.gov/data/known-terrestrial-analog-sites-planetary-science) and the literature before calling a site new. A match to one famous site alone does not validate a method.
7. For each selected Earth location, show coordinates, target Moon/Mars region, measured similarities, uncertainty, analogy breakdowns, and the equipment or scientific method it could help test.

These data can support regional discovery and explainable comparison. Actual landing/base suitability requires separate, much finer engineering and site investigations. Earth gravity, atmosphere and radiation also prevent complete environmental equivalence.

## Reproduce the table audit

Install `duckdb` in an appropriate Python environment, then run `python3 analysis/audit_datasets.py` from this repository. This run used DuckDB 2.0.0, installed in `/tmp/terratwin-audit-deps`; its command was `PYTHONPATH=/tmp/terratwin-audit-deps python3 analysis/audit_datasets.py`.

Outputs: `dataset_audit.json` (counts, ranges, categories and recipe audit) and `feature_coverage.csv` (cell and area coverage for each of 228 feature entries). Input datasets were not modified by this analysis.

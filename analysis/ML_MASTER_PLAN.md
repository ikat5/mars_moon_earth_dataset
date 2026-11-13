# TerraTwin data and machine-learning master plan

Prepared: 2026-11-14. Audience: data, ML, science-review, and application teammates.

Revision: explicit distance/economic ranking and task-specific seasonal campaign planning added on 2026-11-14; see section 13.

**Handoff status:** implementation plan, not a claim that new datasets, models, labels, or scientific capabilities have been delivered. The serving release remains `0.2.0`. No cloud training is launched by this document.

## 1. Objective and recommended approach

Find Earth footprints useful for investigating a selected Moon or Mars footprint, explain the useful similarities by scientific dimension, and identify the physical and operational differences. Cover all eight challenge areas, enabling numerical comparison only when compatible evidence exists.

Use this progression:

1. Reproduce the existing physical terrain baseline and build independent evaluation data.
2. Acquire and harmonize additional measurements; improve footprint consistency.
3. Compare stronger physical baselines, clustering, and frozen pretrained representations.
4. Evaluate a small self-supervised terrain model if simpler methods leave measurable gaps.
5. Collect reviewed, purpose-specific relevance labels and train a supervised ranker when sufficient independent labels exist.
6. Integrate only methods that improve held-out results; retain dimension-level evidence and a physical fallback.

Self-supervision learns from unlabeled observations; unsupervised clustering groups observations; supervised ranking learns from relevance judgments. These are different tools. None automatically establishes analog suitability. More training cannot recover information absent from the input measurements.

This plan follows the user's requested hybrid direction and request for an ML handoff. Specific model choices and numerical targets below are experiment defaults, not validated conclusions. It supplements [the product blueprint](../TERRATWIN_MASTER_BLUEPRINT.md) and the local `Further_TODO.md` roadmap; this committed document is self-contained because that roadmap is not currently tracked.

### Working assumptions and unresolved inputs

| Item | Planning default / outstanding decision |
|---|---|
| Scope | Both Moon and Mars; all eight areas inventoried; terrain, thermal, and materials mature first. |
| Users | Researchers, students, rover teams, and exploration organizations; initially a small demonstration workload. |
| Runtime | Existing CPU server; proposed p95 search target <=2 s under a declared workload, measured again after integration. Precompute embeddings. |
| Reliability | Immutable local releases and fallback search; provider outages must not break prepared searches. |
| Privacy | Public scientific data; tokens outside Git; origin/budget inputs not retained by default. |
| Ownership | Data teammate owns acquisition/provenance; ML teammate owns experiments; science reviewer owns comparison/label review; app teammate owns serving. Names unassigned. |
| Compute | User reports 300 h of 2xT4 and up to 30 concurrent computes. Provider, quota units, accessible storage, and interconnect are unconfirmed. Budget conservatively in GPU-hours; see section 10. |
| Supervision | No reviewed cross-body analog-pair training set found. Expert/reviewer time must be arranged; supervised ranking is conditional on labels. |
| Schedule | Milestones are dependency ordered; no deadline or guaranteed download/training duration assumed. |
| Data volume | Inventory globally, acquire targeted windows first. Estimate storage, request limits, and egress before expanding. |

Do not wait for every portal to be accessible before beginning the local baseline. Record blocked sources explicitly. This handoff authorizes planning; cloud access and credentials still have to be provisioned by their owners.

## 2. What exists and what the ML teammate can use now

| Asset | Current role |
|---|---|
| `prepared/current_release.json` | Serving pointer, currently `0.2.0`. |
| `prepared/0.2.0/{earth,moon,mars}_features.parquet` | Regional measurements, QC, footprints, and context. Earth: 1,413,693 rows; Moon: 259,200; Mars: 1,036,800. |
| `prepared/0.2.0/feature_registry.json` | Definitions, sources, resolution, and allowed comparison policies. |
| `prepared/0.2.0/profiles.json` | Four-term terrain scoring and historical dry/barren eligibility rules. |
| `prepared/0.2.0/{manifest,provenance,validation}.json` | Integrity and transformation evidence. |
| `processing/search.py`, `processing/config.py` | Actual baseline implementation and comparison policies. |
| `analysis/control_sites.json` | Four sanity/scale controls, explicitly not a training dataset. |
| `analysis/evaluation_0.2.0/`, `analysis/control_evaluation_0.2.0.json` | Existing retrieval diagnostics and control results, not measured analog accuracy. |
| `sources/known_analogs/`, `sources/known_analogs_paad/` | Incomplete USGS analog inventories, useful for documentation/review. |
| `prepared/gobi_candidate_0.1.0/`, `prepared/local_pilot_0.1.1/` | Finer Gobi/Jaflong case studies; not labeled positives. |
| `frontend/terratwin_service.py`, `frontend/terratwin.js` | Existing API adapter and application integration. |

The source table dictionaries contain 49 Earth, 87 Moon, and 92 Mars scientific feature definitions. They are not 228 interchangeable predictors. Many describe different physical quantities, footprints, epochs, models, or correlated derivatives. Audit actual nulls, QC, and provenance before use.

LOLA and MOLA supply ranked planetary terrain. Earth regional terrain uses NOAA ETOPO 2022. Diviner temperature/rock/polar fields, Mars TES/OMEGA/geology/SWIM fields, and Earth MODIS temperature exist as unscored context. Mars surface-temperature fields originate from the Mars Climate Database, not directly from THEMIS measurements. Some imported cave/dune catalogs used THEMIS/CTX/HiRISE upstream; that is not direct imagery or DTM ingestion here.

Copernicus DEM and Sentinel-derived WorldCover are used in local studies. Direct Sentinel optical/SAR analysis, ASTER GED ingestion, and CF-based comparison are new work. Lunar pit catalog use is not equivalent to LROC DTM processing. Frontend `labels_*.json` are place names, not ML labels. NASA Trek/Esri display tiles are not automatically approved scientific training inputs.

Raw-to-integrated generation code is absent: preserve that provenance limitation rather than claiming raw reconstruction. Read [DATA_CATALOG.md](DATA_CATALOG.md), [ATTRIBUTION.md](../submission/ATTRIBUTION.md), and [KNOWN_LIMITATIONS.md](../submission/KNOWN_LIMITATIONS.md).

### Existing score, exactly

For feature j, target t, and Earth candidate x:

```text
d_j = min(abs(x_j - t_j) / tolerance_j, 1)
S_terrain = 100 * (1 - sum(weight_j * d_j) / sum(weight_j))
```

| Term | Weight | Tolerance |
|---|---:|---:|
| Median slope | 0.25 | 5 degrees |
| p90 slope | 0.25 | 10 degrees |
| Relief | 0.25 | 500 m |
| RMS roughness | 0.25 | 100 m |

Differences of 1 degree, 2 degrees, 100 m, and 20 m yield 80/100. This is an uncalibrated resemblance index, not 80% accuracy, confidence, or hardware success. Distances saturate at one, reducing discrimination among sufficiently different terrain; test alternatives rather than silently changing the baseline.

Required terrain includes TRI as a diagnostic/QC field, but TRI is not a fifth score term. Current defaults require >=95% DEM validity, Earth/target cell-area ratio 2/3 to 1.5, score >=50, and 100 km separation between returned candidates. Additional physical/QC checks apply in code. The optional historical screen requires >=80% barren class, aridity <=0.2, and coverage/water/built/crop thresholds declared in `profiles.json`. NDVI never gates or ranks release 0.2.0.

Existing cells are approximately 15 km across at the equator, summarizing roughly 460-475 m terrain rasters; footprints shrink with latitude. Globe imagery does not increase scoring resolution. Shackleton currently has insufficient integrated terrain, and separate polar context must not silently fill it.

## 3. Data register: all supplied portals and relevant products

Priorities: **P0** = local baseline/data contracts; **P1** = first comparable terrain/thermal/materials pilot; **P2** = deeper cases/other scientific dimensions; **P3** = optional independent source. "Existing" means documented in this repository, not independently verified upstream processing. Links are discovery/product pages unless explicitly labeled download; exact collection versions and asset IDs must be pinned in acquisition manifests.

### 3.1 Moon and Mars reference data

| ID / priority | Product and official data link | Existing -> planned use | Key constraint |
|---|---|---|---|
| M01 / P0-P1 | [LRO LOLA GDR/DEM](https://pds-geosciences.wustl.edu/missions/lro/lola.htm); [LDEM image archive](https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/cylindrical/img/); [NASA polar products](https://pgda.gsfc.nasa.gov/products/90) | Existing LDEM_64 terrain and separate polar context -> consistently derived regional/polar footprints. | DEM spacing, interpolation, slope baseline, polar projection, and actual track support differ. |
| M02 / P1 | [Diviner products](https://ode.rsl.wustl.edu/moon/pagehelp/Content/Missions_Instruments/LRO/DIVINER/Intro.htm); [L2 gridded records](https://ode.rsl.wustl.edu/moon/pagehelp/Content/Missions_Instruments/LRO/DIVINER/GDR_L2.htm) | Existing GCP temperature, rock abundance/regolith, and PRP context -> harmonized thermal descriptors and new L3 Christiansen Feature material evidence. | L2 day/night and L3 CF/rock/soil products are distinct. Pin actual product resolution, local-time bins, QC, and coverage; not every Diviner layer is 250 m. |
| M03 / P2 | [LROC mission/data entry](https://www.lroc.asu.edu/); [current PDS archive](https://pds.lroc.im-ldi.com/) | Existing pit catalog -> targeted NAC imagery and suitable terrain products for selected footprints. | Stereo terrain coverage is selective; pin product IDs and photometric/geometry metadata. |
| P01 / P0-P1 | [MOLA MEGDR](https://pds-geosciences.wustl.edu/missions/mgs/megdr.html) | Existing 128 pixels/degree terrain -> matched physical-support DEM patches. | About 463 m equatorial spacing for the existing product; polar products and effective resolution differ. |
| P02 / P1-P2 | [THEMIS PDS entry](https://pds-geosciences.wustl.edu/missions/odyssey/themis.html); [mission data/mosaics](https://themis.asu.edu/) | New targeted daytime/nighttime IR context and appropriate thermal products. | A visual mosaic DN is not automatically temperature or thermal inertia. Read calibration and mosaic metadata before quantitative use. |
| P03 / P2 | [HiRISE DTM catalog](https://hirise.lpl.arizona.edu/dtm/); [HiRISE data](https://hirise.lpl.arizona.edu/) | New local terrain/morphology investigations and high-resolution validation. | Sparse DTM footprints; do not upsample MOLA and claim HiRISE-level evidence. |
| P04 / P1 | [USGS Geologic Map of Mars, SIM 3292](https://pubs.usgs.gov/sim/3292/) | Existing Tanaka et al. map -> documented target-region classes/processes. | Mapped units and ages require a scientific crosswalk to Earth; numeric category subtraction is invalid. |
| P05 / P2 | [SWIM project/data discovery](https://swim.psi.edu/); [PDS Geosciences](https://pds-geosciences.wustl.edu/) | Existing SWIM/TES/GRS context -> purpose-specific ice/material descriptors after product-level review. | Ice consistency, hydrogen, water abundance, and accessible ice depth are different evidence types; preserve source-native definitions. |

Initial target profiles: lunar mare terrain; a specifically drawn south-polar rim footprint; Jezero delta/crater footprints kept distinct from the landing point; and a sourced Mars mid-latitude ice-interest footprint. Save target polygons and IDs before evaluation. The current 0 N, 0 E lunar fixture is a regression example, not automatically a scientifically defined mare profile. The south-polar profile remains unavailable until compatible terrain is prepared.

### 3.2 Earthdata / NASA Earth observations

| ID / priority | Product and data link | Existing -> planned use | Key constraint |
|---|---|---|---|
| E01 / P1 | [ASTER GED AG100.003, 100 m](https://www.earthdata.nasa.gov/data/catalog/lpcloud-ag100-003); [persistent DOI](https://doi.org/10.5067/Community/ASTER_GED/AG100.003); [JPL documentation](https://emissivity.jpl.nasa.gov/aster-ged) | New five-band thermal emissivity, mean/variability of LST, NDVI, elevation, and land/water support. | Static clear-sky 2000-2008 summary; observation count/QC needed. Spectral responses differ from Diviner CF; require validated material interpretation rather than raw numerical matching. |
| E02 / P1 | [MODIS LST product family](https://modis.gsfc.nasa.gov/data/dataprod/mod11.php); [MOD11 user guide](https://modis-land.gsfc.nasa.gov/pdf/MOD11_User_Guide_V61.pdf); [Earthdata Search](https://search.earthdata.nasa.gov/) | Existing historical OpenLandMap MOD11A2 derivative -> direct QA-controlled day/night Terra/Aqua products with explicit observation times. | MOD11A2/MYD11A2 are 8-day products. Overpass day-minus-night contrast is not measured full diurnal range. Pin collection, dates, QC bits, and cloud support. |
| E03 / P2 | [ECOSTRESS data access](https://ecostress.jpl.nasa.gov/data); [AppEEARS](https://appeears.earthdatacloud.nasa.gov/) | New local LST/emissivity evidence at selected sites. | Use current Collection 2 metadata; irregular sampling and orbit/coverage limits prevent treating it as a uniform global time series. |
| E04 / P2 | [NASADEM HGT v001](https://www.earthdata.nasa.gov/data/catalog/lpcloud-nasadem-hgt-001); [SRTM data access](https://www.usgs.gov/centers/eros/science/usgs-eros-archive-digital-elevation-shuttle-radar-topography-mission-srtm-1) | Optional finer Earth terrain alternative/cross-check. | Coverage limitations; do not assume polar availability. Compare with Copernicus rather than duplicate every DEM. |
| E05 / P2 | [MODIS aerosol family](https://modis.gsfc.nasa.gov/data/dataprod/mod04.php) | New aerosol occurrence/optical-depth context. | Aerosol optical depth is atmospheric column evidence, not measured surface dust thickness or grain size. Product QA and retrieval failure over bright deserts matter. |
| E06 / P1 | [MODIS vegetation products](https://modis.gsfc.nasa.gov/data/dataprod/mod13.php); [MCD12Q1 land cover](https://doi.org/10.5067/MODIS/MCD12Q1.061) | Replace/confirm provisional NDVI and update historical bare/vegetation context. | Preserve seasonal sampling and masks; low NDVI does not prove biological absence. |
| E07 / P2 | [NASA Worldview](https://worldview.earthdata.nasa.gov/); [GIBS documentation](https://nasa-gibs.github.io/gibs-api-docs/) | New scouting links, dated screenshots, and optional visualization layers. | Display/scouting layer; use underlying calibrated products for analysis. |

Earthdata discovery/API entry: [Earthdata Search](https://search.earthdata.nasa.gov/), [CMR documentation](https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html), [earthaccess](https://earthaccess.readthedocs.io/en/latest/). Many download services require Earthdata Login; verify each asset's actual authentication and subsetting behavior. Do not embed account tokens in notebooks or manifests.

### 3.3 Copernicus / ESA

| ID / priority | Product and data link | Planned contribution | Key constraint |
|---|---|---|---|
| C01 / P1 | [Copernicus DEM documentation](https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Data/DEM.html); [existing GLO-30 open-cloud access](https://copernicus-dem-30m.s3.amazonaws.com/readme.html) | Extend existing Gobi/Jaflong DSM terrain windows. | DSM includes surface objects and edited water; retain acquisition/source and editing flags. |
| C02 / P1 | [Sentinel-2](https://documentation.dataspace.copernicus.eu/Data/SentinelMissions/Sentinel2.html) | Cloud-masked L2A optical morphology, bare-surface/vegetation checks, documented spectral descriptors. | Bands have different sampling; reflectance/color across worlds is not a universal mineral classifier. |
| C03 / P2 | [Sentinel-1](https://documentation.dataspace.copernicus.eu/Data/SentinelMissions/Sentinel1.html) | Calibrated backscatter/polarization descriptors and change evidence at shortlisted sites. | Orbit, incidence angle, moisture, terrain, and speckle affect signal. SAR backscatter is not DEM roughness. Confirm actual polar acquisition coverage. |
| C04 / P2 | [Sentinel-3](https://documentation.dataspace.copernicus.eu/Data/SentinelMissions/Sentinel3.html) | SLSTR thermal cross-check where it fills a gap. | Different footprint and observation times; not an independent reason to duplicate the full MODIS stack. |
| C05 / P3 | [Sentinel-5P](https://documentation.dataspace.copernicus.eu/Data/SentinelMissions/Sentinel5P.html) | Investigate atmospheric context only if a specific experiment requires it. | Not a primary terrain, mineral, or surface-dust measurement; optional relevance must be demonstrated. |
| C06 / P2 | [ESA WorldCover](https://esa-worldcover.org/en/data-access) | Extend existing local 2021 10 m bare/sparse, water, and vegetation context. | Predicted land-cover class is not measured bare-rock fraction or local classification confidence. |
| C07 / P3 | [ESA Open Science Catalog](https://opensciencedata.esa.int/) | Discovery of additional geoscience products. | Discovery portal, not a single dataset. A specific collection, license, resolution, and use must be established before acquisition. |

Access: [CDSE documentation](https://documentation.dataspace.copernicus.eu/), [STAC](https://documentation.dataspace.copernicus.eu/APIs/STAC.html), [OData](https://documentation.dataspace.copernicus.eu/APIs/OData.html), [S3](https://documentation.dataspace.copernicus.eu/APIs/S3.html), and [openEO](https://documentation.dataspace.copernicus.eu/APIs/openEO.html). Authentication, quotas, processing credits, and service availability vary; inventory them before launching workers.

### 3.4 Canadian radar and JAXA

| ID / priority | Product / link | Planned use and access decision |
|---|---|---|
| R01 / P3 | [RCM access policy](https://www.asc-csa.gc.ca/eng/satellites/radarsat/access-to-data/about.asp); [EODMS](https://www.eodms-sgdot.nrcan-rncan.gc.ca/) | Selected mid-latitude SAR comparisons if accessible. Public account required; public products have geographic/resolution limits, including latitude limits varying with longitude. Do not make polar delivery depend on RCM. |
| R02 / P2-P3 | [RADARSAT-1 open release](https://www.canada.ca/en/space-agency/news/2019/03/open-data-over-36000-historical-radarsat-1-satellite-images-of-the-earth-now-available-to-the-public.html); [EODMS](https://www.eodms-sgdot.nrcan-rncan.gc.ca/) | Inspect actual archive footprints near Devon Island/Haughton. Historical Canada-focused coverage does not guarantee scenes over a chosen site. |
| R03 / P2 | [ESA SNAP toolbox](https://step.esa.int/main/toolboxes/snap/); [ASF SAR training](https://hyp3-docs.asf.alaska.edu/) | SAR processing references: calibration, terrain correction, masks, and product-specific interpretation. The brief's unnamed "SAR Python tutorial" has no URL; teammate must obtain the original link before claiming to follow it. |
| J01 / P3 | [JAXA G-Portal](https://www.gportal.jaxa.jp/?lang=en); [GCOM-C SGLI L2 LST](https://eolp.jaxa.jp/GCOM-C_SGLI_L2_LST.html) | Optional QA-controlled LST/emissivity evidence. JAXA's product page specifies registration for downloads; pin version and QA definition. |
| J02 / P3 | [JAXA ALOS PALSAR mosaics](https://www.eorc.jaxa.jp/ALOS/en/dataset/fnf_e.htm) | Optional L-band surface/subsurface-sensitive radar case study using actually available open products. This is an additional JAXA route, not proof that the same asset is downloadable from G-Portal. Do not assume high-resolution PALSAR-2/PRISM access or infer ice, penetration depth, or regolith thickness from brightness alone. |

All supplied portals are covered by the register; not all must become model inputs. For every optional source, record `integrated`, `pilot_only`, `blocked_access`, `not_applicable`, or `deferred`, with reasons and the gap it would fill. Do not bulk-download archives merely to increase the source count.

### 3.5 Retain existing complementary sources and field evidence

- Earth terrain: [NOAA ETOPO 2022](https://www.ncei.noaa.gov/products/etopo-global-relief-model).
- Existing land-cover derivative: [Zenodo 8367523](https://doi.org/10.5281/zenodo.8367523), CC BY-SA 4.0 as recorded locally.
- Existing aridity/ET0: [Figshare 7504448 v5](https://doi.org/10.6084/m9.figshare.7504448.v5), 1970-2000. Catalog and README licensing conflict; preserve both and resolve intended use.
- Existing provisional vegetation: [Zenodo 4305975](https://doi.org/10.5281/zenodo.4305975), selected 2001-2017, smoothed/gap-filled; storage scale remains unconfirmed.
- Known analog discovery: [USGS terrestrial analog portal](https://tadp.astrogeology.usgs.gov/), [USGS known sites](https://www.usgs.gov/data/known-terrestrial-analog-sites-planetary-science), and [PAAD](https://www.usgs.gov/data/paad-planetary-aeolian-analog-database).
- Biology/biosignatures: [NASA astrobiology field locations](https://astrobiology.nasa.gov/research-locations/) and site-specific primary field studies. These are discovery evidence, not a ready biological training raster.
- Caves/subsurface: [NASA cave analog data entry](https://ti.arc.nasa.gov/dataset/caves/) plus source-native LROC/Mars cave catalogs already recorded in metadata. Verify availability, actual contents, and licenses before adding assets.

Do not infer novelty from absence in USGS feeds. Do not tune the score until Atacama, Haughton, or Death Valley always ranks high: each is useful for particular processes, not every target.

### 3.6 Additional data for seasonal suitability and campaign planning

These supporting sources extend the supplied resource brief. Acquire bounded site/time windows for section 13 rather than treating the existing annual aridity and static ASTER climatology as monthly operating conditions.

| ID / priority | Data / official link | Planned use and limitation |
|---|---|---|
| T01 / P1 for planning | [ERA5-Land hourly data](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land?tab=overview) | Historical temperature, precipitation, soil/snow conditions, and appropriate wind fields after variable review. Reanalysis is modeled gridded evidence, not a local forecast or measured road condition. Pin extraction interval and variable definitions. |
| T02 / P2 | [NASA GPM IMERG](https://gpm.nasa.gov/data/imerg) | Precipitation seasonality and supported wet-day/event statistics. Inspect product version, coverage, run type, and error over snow, mountains, and arid terrain; rainfall alone does not establish flood/access safety. |
| T03 / P2 | [MODIS snow-cover products](https://modis.gsfc.nasa.gov/data/dataprod/mod10.php) | Snow-covered versus exposed-ground seasons and freeze/thaw context with other evidence. Cloud/QA gaps are unknown; visible snow absence does not establish an unfrozen subsurface. |
| T04 / P2 | [NASA POWER climatology API](https://power.larc.nasa.gov/docs/services/api/temporal/climatology/); [daily API](https://power.larc.nasa.gov/docs/services/api/temporal/daily/) | Lightweight meteorological/solar context and independent workflow checks where useful. Record underlying products, units, climatology period, and support; shared upstream sources are not independent validation. Monthly averages cannot establish consecutive usable days. |
| T05 / P1 for planning | Existing Sentinel-2/WorldCover, MODIS vegetation/LST, Sentinel-1, and relevant local stations/field studies | Seasonal exposed surface, vegetation, wetness, surface-temperature, and access evidence at the selected footprint. Keep observations, modeled estimates, and inferred accessibility separate. |
| T06 / P1 for planning | Official site operator, park/land manager, transport provider, local authority, station records, or dated user-supplied evidence | Access calendars, closures, permits, route availability, local support, and dated cost quotes. No universal satellite portal supplies these. Store exact per-site source URLs, verification dates, scope, and expiry. |

ERA5-Land, IMERG, and POWER documentation was accessible during this revision; the MODIS snow product entry returned a gateway error in the research client and needs an acquisition-time check. No seasonal product or local planning record is downloaded by this revision. No named site's suitable months have yet been established.

### Link-verification status

Official documentation/product pages were checked through web research on 2026-11-14 where accessible. LOLA, Diviner, MOLA, HiRISE, THEMIS, ECOSTRESS, CDSE, RCM, and JAXA LST supplied accessible documentation. Some Earthdata catalog, MODIS, USGS, and JPL pages returned 403/502/503 through the research client; retain canonical links but do not call their downloads tested. Discovery links, account flows, archive asset downloads, and every source's current terms require an acquisition-time check. The dataset manifest must record the actual resolution of the source used, not a resolution copied from this plan.

## 4. Acquisition and data contracts

### Separate measurement, comparison, and model assets

Keep `prepared/0.2.0` immutable. Add new raw-source manifests and sidecars, then publish a new release only after validation. Use versioned release IDs across features, patches, labels, and model artifacts. Do not change the current serving pointer during experiments.

Proposed output contracts, to be implemented by teammates:

| Artifact | Required contents |
|---|---|
| `sources/ml_<version>/catalog.json` | Provider, product/collection/version, asset ID, canonical and download URLs, terms, acquisition state, estimated bytes, date checked, and access failure reasons. |
| `sources/ml_<version>/manifest.json` | Download timestamps, footprint, CRS/body/datum, bands, units/scale/offset, nodata/QC definitions, temporal support, provider checksum if supplied, local SHA-256, and processing lineage. |
| `prepared/ml_<version>/samples.parquet` | `sample_id`, body, geometry, source IDs, footprint dimensions/area, observation dates, effective resolution/baseline, feature schema ID, QC/coverage, and missingness. |
| `prepared/ml_<version>/patches/` | Metric DEM/derivative arrays or calibrated sensor-native image arrays, validity masks, per-patch sidecars, and parent asset IDs; COG/Zarr or measured shard format. |
| `prepared/ml_<version>/splits.parquet` | Sample ID, regional/site group, split, target family, buffer decisions, and duplicate group; immutable hash. |
| `prepared/ml_<version>/judgments.parquet` | Label schema in section 8, label provenance/review and split ownership. |
| `analysis/ml_<version>/runs/<run_id>/` | Config, code commit, environment lock, data/split hashes, seed, training logs, hardware, GPU-time ledger, checkpoints, and validation metrics. |
| `prepared/ml_<version>/models/<model_id>/` | Selected checkpoint/reference, preprocessing, feature order/units, embedding dimensions, allowed domains, index/ID hashes, evaluation/model card, and attribution. |

Never put credentials, expiring signed URLs containing tokens, raw imagery dumps, or large checkpoints into ordinary Git commits. Use approved external artifact storage or deliberate Git LFS, with stable manifests. Review dataset and pretrained-weight terms independently.

Download one sample asset per source first; inspect values, georeferencing, masks, and temporal metadata. Only then create a bounded AOI/date plan. Use resumable idempotent workers, limited per-provider concurrency, backoff, checksums, and explicit partial/failure states. CPU workers handle discovery, I/O, reprojection, and QC; do not allocate GPUs to wait on downloads.

### Harmonize physical support before model input

1. Retain body-native radii, coordinate conventions, vertical datum, east-positive longitude, and appropriate local metric/polar projections. Do not apply Earth EPSG geometry to Mars/Moon coordinates.
2. Distinguish analysis-window size, raster spacing, effective resolution, and slope/roughness calculation baseline. Nominally equal pixel spacing does not imply equal resolved terrain.
3. Start a regional pilot near the current ~16 km support. An example is 32x32 samples at 500 m spacing, where source support permits; do not confuse this with a validated effective 500 m resolution. Resizing it to a network's input size creates no new information.
4. Treat the brief's approximately 1 km common grid as a candidate feature-summary grid. Do not turn coarse 15 km summaries into observed 1 km cells by interpolation. Test support choices on held-out regions.
5. Build a separate fine tier, for example 128x128 at 30 m spacing (~3.84 km), only for compatible source footprints. Aggregate high-resolution DTMs to this support; never substitute upsampled MOLA for actual fine terrain.
6. Compute derivatives after resampling/reprojection using declared physical baselines. Continuous physical layers need appropriate area/resolution-aware treatment; categories need categorical aggregation, not bilinear interpolation. Preserve QA fractions separately.
7. Retain invalid/cloud/shadow masks. Unknown is null, not zero. Required missing evidence makes a dimension unavailable. Train-only imputation may be tested for optional predictors but must retain masks and may not fabricate displayed observations.
8. Fit scaling, PCA, feature selection, and other learned preprocessing on training data only. Per-patch height normalization may aid shape learning but can erase relief; preserve metric amplitude in a separate audited branch.
9. Preserve native spectral responses and thermal observation times. No direct ASTER-band-versus-CF subtraction, arbitrary geology-code subtraction, or Earth day/night versus modeled Mars extreme subtraction.

## 5. Similarity by scientific dimension

| Dimension | Comparable evidence / candidate comparison | Required interpretation |
|---|---|---|
| Terrain/topography | Common-support slope distributions, relief, detrended roughness at declared baselines, curvature/landform descriptors, and learned DEM morphology. | Absolute elevation across planetary datums is not directly useful. Regional morphology is not wheel-scale traction or bearing strength. |
| Materials/geology | Reviewed broad material/process crosswalk, exposed-surface evidence, ASTER emissivity descriptors, Diviner CF, and source-native TES/OMEGA information. | Derive supported material classes/probabilities with uncertainty; compare only compatible classes/descriptors. Different instruments do not measure an identical vector. |
| Temperature/illumination | Explicit local-time and seasonal temperature descriptors, thermal contrast, frequency of supported extremes, illumination distributions. | Match absolute conditions only for tasks where meaningful; relative-shape resemblance must be labeled separately. Earth cycles cannot reproduce lunar day length or vacuum. |
| Water/ice/resources | State, seasonality, occurrence evidence, and depth/temperature only where measured or explicitly modeled. | SWIM consistency, neutron hydrogen, cold traps, moisture, and confirmed accessible ice are not interchangeable. Require substrate/depth evidence for drilling tasks. |
| Dust/wind/processes | Dune morphology, migration when dated repeat observations support it, substrate/sediment evidence, atmospheric context. | Dust AOD and surface sediment are separate. Equal wind speeds across different gravity/atmosphere do not establish equivalent sediment transport. |
| Biology/biosignatures | Reviewed field observations, environmental limits, and preservation settings linked to an explicit scientific hypothesis. | NDVI cannot establish sterility, microbial abundance, or extraterrestrial life. Initially evidence cards/site studies rather than a universal score. |
| Caves/subsurface | Sourced cave type, geometry, entrance, interior measurements where available, volcanic context. | Proximity to a cave point is not a cave inside the footprint. Radar anomalies do not certify a lava tube. |
| Exploration operations | Requirements derived from the declared navigation, sampling, drilling, construction, or other investigation. | Do not double count terrain-derived hazard indices or infer engineering safety from regional similarity. |

For continuous distributions, test a physical baseline using Wasserstein-1 distance in original units, divided by a documented dimension-specific tolerance. Compare this with robust normalized scalar distances; freeze choices using validation regions only. Tolerances must be declared before final testing and justified for the task. Do not compare independently quantile-normalized planets and interpret matching percentiles as equal conditions.

For embeddings, use L2-normalized vectors and cosine similarity as an experimental morphology signal. Cosine similarity is not a calibrated scientific probability. Keep separate terrain, optical, radar, and material representations until their compatibility is established.

Each dimension returns `status`, source IDs, support/coverage, observed values/distributions, comparison definition, score if supported, and mismatches. Keep evidence coverage distinct from similarity. Missing essential dimensions cause abstention for tasks requiring them; silently renormalizing a broad suitability score over whatever happens to be present is prohibited.

Overall ordering is task-specific: first apply essential requirements, then compare remaining dimension trade-offs or a reviewed ranker. Show strong alternatives and conflicts. A morphology embedding cannot compensate for absent required ice. Gravity, atmosphere/vacuum, radiation, and time-scale mismatches remain explicit even when surface observations match.

## 6. Candidate discovery and ML experiments

### Experiment ladder

| ID | Method | Purpose / promotion condition |
|---|---|---|
| B0 | Frozen current four-term formula | Regression reference on current regional assets. |
| B1 | Harmonized physical distributions and robust distance | Test whether better measurements/support solve the problem before adding neural models. |
| U1 | MiniBatchKMeans or another bounded clustering baseline on compatible terrain descriptors | Explore candidate diversity, stratify sampling, and detect recurring groups. Internal cluster metrics alone cannot justify deployment. |
| F1 | Frozen compact pretrained image encoder on standardized representations | Cheap representation benchmark; record checkpoint/weight license and Earth/planetary domain limitations. |
| S1 | Small DEM/derivative encoder with self-supervised contrastive learning | Conditional experiment to improve terrain retrieval; compare to B1 and F1 on identical footprints and splits. |
| S2 | Optional sensor-specific optical/SAR representation | Only after S1/data QA; do not force unrelated spectral channels into the same input meaning. |
| R1 | Regularized linear/pairwise ranker or boosted-tree ranker on reviewed pairs and physical/embedding features | Supervised stage after label audit; compare against simple calibrated physical weights. |
| R2 | Supervised contrastive encoder refinement | Optional, only if label diversity and independent evaluation support it; not the first training job. |

Start with compact CNN/ResNet-scale experiments. A DINO-style pretrained model is a candidate frozen benchmark, not a decision to pretrain a large foundation model. Pin the chosen checkpoint and software versions after a compatibility test. Literature starting points: [SimCLR](https://arxiv.org/abs/2002.05709), [DINO](https://arxiv.org/abs/2104.14294), and [supervised contrastive learning](https://arxiv.org/abs/2004.11362). Their published general-image results do not establish performance on this task.

### Self-supervised terrain experiment

- Pilot first on a stratified sample of 20,000-50,000 unique patches across bodies, latitude bands, terrain types, and source quality; this is a planning size to revise after throughput and independent-region counts are measured.
- Use metric elevation plus selected derivatives and masks; identify and ablate redundant channels. Optical images are a separate modality.
- Positives are appropriate alternative views of the same footprint. Do not manufacture cross-body positive pairs by assuming the old score is ground truth.
- Allowed transformations depend on the task. Rotations/flips may be appropriate for orientation-independent terrain shape; they are unsuitable when orientation, illumination, aspect, or directional processes are relevant. Avoid vertical scaling that changes metric relief, and arbitrary crops that silently change physical support.
- Use small physical-support-preserving perturbations. Inspect augmented samples. Mask padding/nodata so the network does not learn the instrument footprint instead of geology.
- Same-footprint multimodal pairs can support a later cross-modal experiment, but correspondence alone does not prove planetary analog relevance.
- Record batch size, effective batch size, learning rate, optimizer, temperature/loss, image/patch scale, augmentations, seeds, and early-stop rule. Gradient accumulation does not create the same simultaneous negative pool as a larger contrastive batch; implement a valid queue/gather method if needed.
- Train/compare one narrow family of configurations, terminate poor runs early, and reserve repeat seeds for finalists. Do not run an uncontrolled 30-job architecture sweep.

### Candidate retrieval

First build exact cosine search on the pilot, with an explicit embedding-to-sample ID mapping. For global scale, benchmark a CPU index before introducing GPU serving or approximate search. [FAISS](https://github.com/facebookresearch/faiss) is a candidate implementation. A 1.4-million-row, 256-component float32 embedding matrix is about 1.43 GB decimal before IDs/index overhead; measure actual memory and latency. If using approximate search, measure recall against exact search and oversample/filter until enough scientifically eligible candidates remain.

Never discard a physically strong candidate solely because one experimental embedding failed. For evaluation, compare physical-only, learned-only, and combined candidate pools and report retrieval coverage as well as final ranking. Candidate counts and fusion weights are validation-time settings, not hard-coded scientific truths.

## 7. Validation and protection against misleading results

Freeze splits before patch augmentation or training. Group by physical site/region, overlapping source footprints, duplicates, and shared observations. Use spatial buffers informed by footprint overlap and measured spatial correlation; a fixed universal distance is not enough. The same named site or target footprint must not appear in training and testing through different crops or sensors.

Use a development split with training/validation regions and a locked test set of independent regions and target families, subject to adequate counts. Report Earth geography generalization and planetary-target generalization separately. The primary inductive test excludes held-out regions from self-supervised fitting, preprocessing, and tuning. If a transductive experiment uses unlabeled test-region observations, report it separately rather than mixing results.

Reference: [spatial cross-validation research](https://arxiv.org/abs/2005.14263); [GroupKFold](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.GroupKFold.html) can enforce assigned groups but does not choose scientifically valid spatial buffers for us.

| Evaluation | Required report |
|---|---|
| Data correctness | Independent source-window checks, units/scales, nodata, QC, georeferencing, coverage, and transformation invariants. |
| Retrieval relevance | NDCG@10 for graded reviewed judgments; Precision@k/Recall@k only where the relevance denominator is sufficiently judged. Report unjudged candidates and pool coverage. |
| Essential requirements | Violation rate, availability/abstention rate, and correctness of explicit no-match outcomes. |
| Robustness | Held-out-region results, target-family results, perturbation/footprint sensitivity, missing-modality behavior, source/sensor holdouts, and repeat seeds. |
| Model contribution | B0/B1/F1/S1/R1 ablations on common eligible observations; physical-only versus learned-only versus combined. |
| Runtime/cost | Preprocessing and inference throughput, index recall, CPU search p50/p95 under declared concurrency, peak RAM/VRAM, GPU-hour ledger, and artifact sizes. |
| Domain bias | Body/sensor/latitude predictability probes, coverage-pattern artifacts, nearest-neighbor montages, and failure review. Domain indistinguishability alone is not success. |

Bootstrap uncertainty by independent query/site/region, not individual correlated crops. NDCG and other ranking metrics need task-specific relevance judgments; reconstruction loss, silhouette, and attractive montages are insufficient substitutes. Metric definition: [NDCG](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.ndcg_score.html).

Proposed promotion gate: a consistent improvement over the strongest eligible baseline on validation, followed by one locked test evaluation, with effect sizes/uncertainty reported and no essential-condition or missing-evidence regressions. Do not invent a required percentage improvement before learning label reliability and test-set power. If evidence is inconclusive, ship the physical baseline and label the model experimental.

Keep the current Jezero, lunar coordinate, Sylhet no-match, and Shackleton insufficient-evidence outcomes as regression fixtures until an intentionally versioned scientific change justifies different behavior. Final test judgments cannot be reused for model tuning.

## 8. Supervision and human review

The four current controls are Yungay/Atacama, Manaus forest, Cinder Lake, and Garwood Valley. They diagnose specific screens/scale gaps; they do not establish target-specific analog truth. Existing USGS general and PAAD feeds are incomplete. Candidate Gobi/Jaflong dossiers are not automatically positive labels.

Create a reviewed query-candidate dataset with:

```text
judgment_id, query_id, target_body, target_geometry_id, candidate_sample_id,
task_id, scientific_dimension, relevance_grade, essential_requirement_status,
evidence_status, source_references, reviewer_id, review_date,
review_confidence, disagreement/adjudication, label_version, split_group
```

Suggested relevance rubric: 0 = unsuitable for the declared investigation, 1 = limited resemblance/use, 2 = useful with named limitations, 3 = strong supported relevance. `unknown` is a separate state, never grade 0. Required-condition pass/fail/unknown is separate from relevance. Reviewer confidence is not model probability.

Start with a pilot of roughly 200-500 judged pairs across at least several independent target footprints and geographically distinct Earth regions; this is a workflow target, not sufficient sample-size proof. Review physical-baseline candidates, learned candidates, plausible hard negatives, and a random/stratified component. Hide model rank/source during judgment where practical. Arrange a second reviewer for an overlapping subset and adjudicate disagreements before expanding toward 1,000-3,000 pairs if time and independent-region diversity permit.

Group both query and candidate sites when splitting: repeating one target against hundreds of candidates does not create hundreds of independent target examples. Labels derived only from a landform map support landform supervision, not universal analog suitability. Algorithmic/pseudo labels must retain their origin and never enter the independent expert test set as ground truth.

For active review, prioritize disagreements between methods and gaps in task/region coverage. Apply active selection only within development data. Keep the final evaluation pool and review rubric frozen.

## 9. Team work packages and dependency order

| Package | Owner role | Concrete deliverables | Dependency / acceptance |
|---|---|---|---|
| WP0: reproduce and freeze | ML + data | Baseline output hashes, dependency lock, current asset/QC inventory, initial experiment config. | Can start now from local release; explicit `--data-dir` required. |
| WP1: acquisition pilot | Data | Register with every portal's state, sample download/QA per selected P1 source, AOI/date/bytes plan, provenance manifests. | Do not scale before sample/QC checks. |
| WP2: harmonized samples | Data + science | Metric footprints, terrain derivatives/distributions, native thermal/material descriptors, masks, source-window checks. | Common-support definitions reviewed; unsupported layers remain context. |
| WP3: evaluation and labels | Science + ML | Immutable spatial groups/splits, rubric, independent reviewed development/test pools, label audit. | Begins before training; test ownership and access separated from tuning. |
| WP4: cheap baselines | ML | B0/B1/U1/F1 comparison, retrieval montages, runtime, failure analysis. | Pilot data contract and development evaluation available. |
| WP5: bounded SSL | ML | S1 configs/checkpoints, seed comparisons, bias/missingness tests, compute ledger. | Only after WP4 and a throughput smoke test. |
| WP6: supervised refinement | ML + science | R1 baseline/ranker and optional R2, relevance/constraint/region metrics, model card. | Only after independent labels pass audit; otherwise retain self-supervised/physical experiments. |
| WP7: candidate science | Science + data | One or two independently checked dossiers, task fit, novelty-search scope, and where analogy breaks. | Candidate model cannot replace local observations/review. |
| WP8: integration | App + ML | Versioned dimensions/model/index contract, cached CPU inference, comparisons/export, fallback, performance report. | Promotion gate and provenance complete; existing API regressions pass. |
| WP9: distance, economic, and seasonal planning | App + science + data | Date/task-specific monthly suitability calendars, campaign windows, route/time/cost scenarios, and eligible-site rankings using section 13. | Preserve scientific requirements; dated access/seasonal evidence required; unknown cost, access, and weather support remain unknown. |

Hypothesis regions for diverse discovery: Puna/Altiplano salars, Tibesti, Arabian Harrat lava fields, Qaidam Basin, Siberian basalt plateaus. Known-site checks: appropriate footprints in Atacama, Haughton/Devon Island, and Death Valley plus unsuitable controls. Register actual AOIs and literature before assigning relevance; these names are hypotheses, not new discoveries or universal positive labels.

For the first milestone, finish WP0 and a bounded terrain pilot, not every global source. Thermal and material pilots follow while labels are reviewed. Biology, drilling, caves, and engineering claims initially rely on sourced site evidence where satellite products cannot answer the question.

## 10. T4 compute plan and cost controls

User resource statement: 300 h of 2xT4; up to 30 computes concurrently. Two possible meanings:

- 300 two-T4 instance-hours = 600 GPU-hours.
- 300 GPU-hours total = 150 two-T4 instance-hours.

Use **300 GPU-hours as the conservative total cap until the quota is confirmed**. The following is a proposed maximum allocation, not a promise that all work requires this much or that jobs finish within it. If 600 GPU-hours are confirmed, retain the other 300 as unallocated reserve until pilot evidence warrants use.

| Stage | GPU-hour cap | Equivalent hours if every job allocates two GPUs |
|---|---:|---:|
| Environment/throughput and correctness smoke tests | 15 | 7.5 |
| Frozen representation pilot and comparison | 45 | 22.5 |
| Small self-supervised terrain experiments | 75 | 37.5 |
| Label-dependent supervised refinement | 45 | 22.5 |
| Selected-model full-corpus encoding | 30 | 15 |
| Finalist repeat seeds / targeted ablations | 30 | 15 |
| Failure recovery / unresolved throughput reserve | 60 | 30 |
| **Total** | **300** | **150** |

The supervised allocation stays unspent if reviewed labels are unavailable; do not invent labels to consume compute. Prefer CPU for small tabular models and preprocessing. If the provider bills allocated devices, a two-GPU instance using one GPU still consumes both devices' allocation; use billing units in the ledger, not estimated utilization alone.

Thirty simultaneous two-T4 instances consume 60 GPU-hours per elapsed hour: 300 GPU-hours would last five hours, or 300 two-GPU instance-hours would last ten hours, before overhead. Thirty available workers are not a reason to exhaust the budget simultaneously. Start with one instance; use a small number of independent experiments after the data cache is ready. Use remaining worker capacity for bounded CPU ingestion if the platform supports that without GPU charges.

T4 has 16 GB per device; two devices do not form one transparent 32 GB tensor memory pool. Use FP16 mixed precision where numerically appropriate, conservative batch sizing, and measured data-loader throughput. Prefer independent single-GPU trials if allowed and efficient; use two-GPU DDP when a measured experiment benefits. Do not assume 30 instances have the network/shared storage needed for a single distributed job.

Before any longer job: check quota units, CUDA/PyTorch compatibility, storage persistence, checkpoint restore, per-step time, loader stalls, peak VRAM, estimated full-run cost, and stop behavior. Run a small representative benchmark and compute cost from observed throughput. Save checkpoints and logs to persistent storage; keep cached observations near compute to avoid repeated network downloads.

Maintain a shared ledger with run ID, allocated GPUs, start/stop, billable units, stage budget remaining, artifact URI, and outcome. Enforce a global cap in the eventual runner/scheduler; individual notebooks cannot safely coordinate the shared budget by themselves. No job starts if its allocation plus measured reserve exceeds the remaining cap.

References: [NVIDIA T4](https://www.nvidia.com/en-us/data-center/tesla-t4/), [PyTorch AMP](https://docs.pytorch.org/docs/stable/amp.html), [PyTorch DDP](https://docs.pytorch.org/docs/stable/generated/torch.nn.parallel.DistributedDataParallel.html). Pin a tested environment rather than assuming the documentation version equals the hosted runtime.

## 11. First tasks for the ML teammate

### Run the existing project

These commands refer to existing files/modules. They do not start cloud compute or implement the future experiment ladder.

```bash
git switch feat/terratwin-search-integration
git pull --ff-only
git lfs pull
python3 -m venv .venv
.venv/bin/pip install -r processing/requirements.txt -r frontend/requirements.txt -r requirements-dev.txt
.venv/bin/python -m processing.search --data-dir prepared/0.2.0 --profile dry_barren_terrain --body mars --lat 18.41 --lon 77.69
.venv/bin/python -m pytest processing frontend/test_api.py -q
```

Python 3.12+ is the repository's stated starting requirement; verify the pinned wheels support the chosen OS/Python and use a separately locked ML environment where needed. CLI defaults still point to the original terrain release, so never omit the explicit data directory for release-0.2.0 comparisons. LFS access and large downloads may be required. Tests are existing verification, not proof of analog accuracy.

### Start work without waiting for new imagery

1. Read `feature_registry.json`, `profiles.json`, and source metadata. Record scored versus context-only features and inspect actual missingness by body/region.
2. Save B0 outputs for the four existing fixtures and explicit data/code hashes. Do not modify them during model development.
3. Define independent evaluation sites/tasks and split groups with the science reviewer. Create a schema and label rubric before requesting relevance judgments.
4. Produce an initial training-only tabular terrain baseline and diversity/clustering exploration using compatible features; label results experimental.
5. Request a bounded set of metric DEM patches and masks from the data teammate; do not train image models on screenshots or interpolated regional summary tables.
6. Benchmark frozen representations before SSL; measure retrieval relevance, sensor artifacts, and cost. Run a small training smoke test only after the patch and split contracts are stable.
7. Deliver a reproducible run folder with configs, preprocessing state, split/data hashes, sample montages, metrics, failures, checkpoint reference, and compute ledger. A notebook alone is not the handoff.

Suggested future package structure (not currently implemented): `ml/data/`, `ml/features/`, `ml/models/`, `ml/retrieval/`, `ml/evaluation/`, `ml/configs/`, and `ml/README.md`. Keep optional ML dependencies out of the existing serving requirements until an integration decision is made. Proposed command names must not be documented as runnable until their implementations exist.

## 12. Serving and final product contract

Retain existing API outcomes and add versioned evidence/model fields through a reviewed adapter. A candidate should expose:

```text
candidate/sample ID, actual geometry, task ID,
dimension results [{name, status, score_definition, score_if_supported,
  observations, coverage, support, sources, mismatches}],
essential requirements [{name, pass/fail/unknown, evidence}],
model/index/data versions, ranking method, experimental status,
local verification and novelty-review states,
where the analogy breaks, recommended next observations,
optional campaign plan {origin_privacy_policy, requested_dates, task_id,
  seasonal_profile_version, month_statuses, suitable_windows, access_status,
  distance_method, distance_km, travel_time, cost_range_and_currency,
  usable_field_hours_estimate_and_method, ranking_mode, assumptions,
  evidence_dates, missing_inputs, uncertainty}
```

Do not replace current `observed_fit` with a learned score under the same semantics. Keep model similarity separate from physical evidence. Build the model/index offline; load prepared artifacts for CPU queries. Benchmark p95/RAM under declared concurrency; fall back to the supported physical method when model artifacts fail. Model failure and scientific no-match must remain different outcomes.

Interactive map: dimension toggles, target/candidate footprint and scale, source dates/coverage, missing-dimension explanations, candidate comparisons, downloadable evidence, and explicit physical mismatches. Fine inspection shows actual finer footprints rather than implying that all regional results have high-resolution data.

Operational scenario comparison follows scientific eligibility and the date-aware rules in section 13. Straight-line distance is not actual travel cost; a cheap location cannot satisfy an experiment with missing essential conditions. Leave unknown cost/access unknown and keep organization inputs private by default.

## 13. Distance, economic efficiency, and suitable time of year

**Explicit user requirements:** provide ranking options based on distance and economic efficiency, and show when during the year an Earth analog is suitable. This expands the earlier roadmap's campaign simulation requirement. It is planned functionality; the current origin/radius terrain search is not an implemented travel-cost or seasonal planner.

### 13.1 Define suitability for the experiment and the campaign

A site has no universal "best season." Its scientific usefulness and operating conditions may change differently. A frozen-substrate experiment may require a season unsuitable for exposed dry-ground rover testing. Compute suitability for `(candidate footprint, planetary target profile, experiment, proposed dates)`.

Keep three separate results: scientific relevance (including date-dependent surface conditions where relevant), campaign operating conditions, and access/logistical feasibility. Preserve stable terrain/material descriptors separately from changing snow, water, vegetation, thermal, or illumination evidence. Define task thresholds with the team/reviewer rather than hard-code a global comfortable-temperature or dry-season rule.

Inputs: optional team origin; experiment and mandatory scientific conditions; acceptable temperature/wind/precipitation/snow/soil conditions; required daylight; team size; equipment and transport; budget/currency; earliest/latest dates; duration and required usable field hours/days; flexibility; maximum travel time; and whether repeat campaigns are needed. If dates are omitted, show a January-December calendar. If origin or budget is absent, retain scientific/seasonal results and mark dependent planning ranks unavailable rather than inventing values.

### 13.2 Build a task-specific seasonal calendar

For each month or supported date window, report `supported`, `conditional`, `unsuitable`, or `insufficient_evidence`, with the conditions and sources behind the state. "Supported" means the declared historical evidence/requirements support planning that window; it is not guaranteed future weather or safe access.

| Evidence | Calendar output / condition to evaluate |
|---|---|
| Temperature and surface thermal data | Relevant quantiles/extremes and periods within the experiment's operating envelope; air temperature and surface LST remain separate. |
| Precipitation / surface wetness | Wet-day frequency, dry-spell evidence, and expected interference with dry-ground testing; flood susceptibility needs independent local evidence. |
| Snow, freeze/thaw, and ice | Exposed-ground availability or required frozen/snow/ice conditions, according to the experiment; snow cover is not subsurface ice depth. |
| Wind / dust | Exposure to task-specific wind limits and supported dust-event evidence; atmospheric AOD alone does not measure local visibility or equipment exposure. |
| Daylight / illumination | Usable daylight and relevant sun geometry for the actual coordinates, date, and task; polar conditions and local horizons need appropriate treatment. |
| Vegetation / water seasonality | Whether the target surface is exposed in the observation period and whether seasonal water/vegetation changes the scientific analogy. |
| Local access / support | Operator-confirmed open dates, permits, road/transport windows, infrastructure, and support availability; absent evidence remains unknown. |

Use a declared multi-year reference interval with enough temporal/QA coverage, chosen for available products and local relevance. Save year counts, missing days, sensor changes, trend/stationarity caveats, and source dates. Hemisphere-specific seasons emerge from site observations, never from globally fixed "summer" month labels. Month windows can cross the December/January boundary.

Monthly means support only a coarse climatological screen. Estimating usable hours, consecutive days, or campaign completion needs compatible hourly/daily observations or historical sequences. Evaluate the joint required conditions at each supported timestamp; multiplying independent marginal probabilities assumes independence and must not be used without validation. Never sum the full month's nominal field days for a campaign lasting only part of that month.

For window W and valid historical year y, a possible explicitly labeled historical estimate is:

```text
usable_hours_y(W) = sum over time bins in W of
  bin_duration_hours * I(all observed/model-supported task conditions pass)
```

Unknown essential conditions produce unknown support, not a passing indicator. Report valid coverage and per-year distributions, with exclusions. A consecutive-days requirement needs run-length evaluation, not just a total. Do not turn historical pass frequency into a calibrated future success probability. Use near-term forecasts, current site reports, and operator checks as a separately dated planning update when available; climatology is not a forecast.

### 13.3 Rank eligible campaign alternatives

First enforce mandatory scientific requirements, access/date conditions, and the user's budget/time constraints wherever evidence permits. Unknown essential requirements produce a conditional/unassessed alternative, not a fully eligible recommendation. Then expose these ranking modes:

| Mode | Ranking objective / display |
|---|---|
| Best scientific fit | Existing per-dimension relevance, with the selected season's scientific limitations visible. |
| Nearest eligible analog | Real route distance where supported; otherwise clearly labeled great-circle proximity. Keep road, air, and local approach legs distinct. |
| Shortest campaign travel time | Supported route/time estimates plus equipment-transfer and setup assumptions; distance alone cannot determine it. |
| Lowest estimated campaign cost | Total comparable campaign cost, with ranges and missing components shown. |
| Best economic efficiency | Estimated total cost per supported usable field hour/day for the declared experiment, only if both cost and usable-time estimates are supported. |
| Best window / practical trade-off | Suitable date windows and the non-dominated choices across scientific fit, cost, travel time, and usable field time. Explain trade-offs rather than hide them in one score. |

Campaign cost includes supported travel, equipment shipping, accommodation, local transport, access/permits, local support, setup, and declared contingency. Record quote dates, currency/base date, exchange-rate source when converting, team/equipment assumptions, and uncertainty. A single static price per site is insufficient; prices and transport/access may vary by requested dates.

```text
economic_efficiency_cost = estimated_total_campaign_cost
                          / estimated_usable_field_hours_within_campaign
```

This ratio is a planning estimate, not scientific similarity or expected hardware success. A missing numerator/denominator makes it unavailable; a supported zero usable-time denominator makes the campaign infeasible. Show cost/time ranges and scenario sensitivity rather than false precision. Repeated visits may change fixed setup/transport costs; state how shared costs are allocated.

Default to visible trade-offs/Pareto alternatives. If the user requests a combined practical score, expose weights, directions, normalization/reference ranges, constraint rules, and sensitivity. Keep the scientific dimensions visible and do not let affordability compensate for a failed essential experiment condition. Ranking thresholds and currency conversion must be versioned with the scenario.

### 13.4 Application output and comparison scenarios

Add a "Plan a field campaign" option after scientific retrieval: origin and travel constraints, budget/team/equipment, task, date window/duration, and ranking mode. Show a 12-month suitability strip per candidate, recommended supported windows, reasons for conditional/unsuitable months, historical support/uncertainty, travel distance/time, cost range, usable field time, and comparison with the strongest scientific match. Exports retain the same sources/assumptions while omitting private organization inputs unless explicitly included.

Support scenarios such as choosing another month, reducing the budget, moving the team origin, shortening the campaign, or planning repeat visits. Recompute seasonal evidence, eligible alternatives, and date-dependent costs. Explain which scientific differences the team accepts by choosing a nearer/cheaper site. If no supported plan qualifies, report the limiting conditions and possible user-controlled changes without silently relaxing requirements.

Illustrative behavior only: a distant candidate may provide stronger morphology, while a closer candidate offers lower campaign cost and more usable field time during the requested dates. The planner shows both and their scientific limitations. No named site's suitable months, actual routes, prices, or permissions are asserted by this example.

### 13.5 Planner implementation and validation handoff

Start with transparent CPU calculations over dated environmental summaries and user/provider planning inputs. This planner does not require a new GPU model. Seasonal ML is optional later, only with independent labels/observations and demonstrated value.

Data teammate: publish versioned site/month or site/window evidence with source dates, support/QA, reference period, and task-independent measurements. Science reviewer: approve task requirements and distinguish scientific-season fit from operating convenience. App/planner teammate: implement date/route/cost scenarios, ranking modes, privacy, explanations, and exports. ML teammate: expose stable versus date-dependent descriptors and retain the independent scientific score; do not learn economic desirability from geographic or wealth proxies.

Validate joint-condition/hour calculations against direct source sequences; compare seasonal recommendations with independent local station/field/operator evidence where available. Hold out years for temporal evaluation as a separate test from geographic/target generalization; fit any seasonal model using training periods only. Check missing data, clouds versus snow, unsupported routes/costs, currency/date changes, hemispheres, polar day/night, leap years, cross-year windows, campaign duration, consecutive-day requirements, closures, zero usable time, and ranking sensitivity. Record local-versus-grid resolution limitations.

Planner acceptance: every recommended window and practical rank has task/date-specific evidence and explicit uncertainty; unknown values cannot improve a rank; mandatory scientific conditions cannot be bought away; UI and exports reproduce the same scenario. Current forecasts/access reports may override a historical planning window when dated evidence supports it, with the change explained.

## 14. Decision log and release checklist

| Decision | Alternatives considered | Reason |
|---|---|---|
| Physical baseline + bounded self-supervised experiments, supervised ranker later | Immediate supervised end-to-end model; clustering alone | Current labels are inadequate; scientific traceability and measurable added value are required. |
| All portals inventoried, acquisition by relevance/coverage | Download every archive first | Access, storage, temporal support, and duplicated evidence otherwise consume the budget without proven benefit. |
| Common-support terrain first; optional modalities separately | Concatenate all existing columns or all sensor channels | Measurement incompatibility and missingness can overwhelm real resemblance. |
| Independent spatial/site/target evaluation | Random patch splits and score-generated test labels | Prevent leakage and circular claims. |
| Frozen/pretrained benchmark before new training | Spend all GPUs on pretraining | Establish whether added training is necessary and affordable. |
| Conservative 300 GPU-hour planning cap | Assume 600 GPU-hours immediately | Quota accounting remains unconfirmed. |
| No silent replacement of serving release | Experiment directly in `prepared/0.2.0` | Preserve reproducibility, rollback, and current application behavior. |
| Explicit distance/economic ranking and suitable-season planner | Static all-year site rank or distance-only affordability proxy | User requested practical efficiency and when in the year an analog is suitable; eligibility and recommendations depend on the experiment, dates, and supported logistics. |

Before promoting a new scientific/ML release:

- [ ] Every supplied portal has a documented acquisition/disposition state and canonical link.
- [ ] Selected assets are pinned, attributed, hashed, and independently inspected.
- [ ] Feature units, support, compatibility, QC, and missingness are documented.
- [ ] Immutable spatial/site/target splits and duplicate/buffer audit exist.
- [ ] Relevance judgments distinguish task, dimension, unknown evidence, and reviewer provenance.
- [ ] Physical and learned baselines, ablations, failures, uncertainty, and held-out results are reported.
- [ ] No learned score is presented as confidence, novelty, engineering safety, or field verification.
- [ ] Compute consumption and remaining quota reconcile with provider accounting.
- [ ] Model card, environment, index mapping, source terms, and reproduction instructions are complete.
- [ ] Existing regression checks and new meaningful data/API checks pass for the intended release.
- [ ] Runtime/fallback and source-outage behavior are measured before changing the serving pointer.
- [ ] Seasonal calendars/windows identify task, reference years, QA coverage, access status, and uncertainty; historical climatology is distinguished from current forecasts.
- [ ] Distance/time/cost/usable-field-time ranks are reproducible for the requested dates, preserve essential scientific conditions, and do not reward unknown inputs.

Success is a reproducible, independently evaluated improvement in finding useful, explainable candidates for declared investigations. A model that does not beat the physical baseline remains an experiment; source count, GPU consumption, and visually attractive results are not success criteria.

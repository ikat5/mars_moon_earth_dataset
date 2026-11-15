# TerraTwin data catalog and interpretation guide

The package combines regional source tables with Earth environmental screening and two finer investigations. These are different evidence levels. Original measurements, missingness, provider documentation, source hashes and transformation records remain available; a derived column is not an additional independent observation.

## Regional source tables

| Body | Original cells | Original feature definitions | Role |
|---|---:|---:|---|
| Earth | 1,413,693 | 49 | Candidate population and terrestrial context |
| Moon | 259,200 | 87 | Selected target's regional properties |
| Mars | 1,036,800 | 92 | Selected target's regional properties |

The source is the [team's integrated dataset repository](https://github.com/ikat5/mars_moon_earth_dataset). Its Earth table is now present locally under `earth_integrated_dataset`. These numbers exclude spatial/identifier fields. The original tables do not have a single verified repository-wide license granting rights over every contributing source. Preserve the per-source attribution and terms recorded in their metadata.

Earth terrain comes from NOAA ETOPO 2022 at 15 arc-seconds, aggregated into 0.125° cells. Earth lithology is a generalized OpenLandMap/USGS map interpretation; its nominal raster spacing does not equal geological mapping accuracy. Earth MODIS temperature and ERA5 context have their own sampling periods and footprints. NASA's contribution is visible in Earth MODIS-derived temperature and environmental inputs, lunar LOLA observations, and Mars mission observations documented in the original registry. The package also uses NOAA, ESA, ECMWF/Copernicus and other open sources; it is not exclusively NASA data.

Only four terrain summaries currently contribute to ranking: median slope, p90 slope, relief and RMS roughness. Shared column names across the bodies do not license comparing numerical geology codes, different water indices, or differently sampled temperature extrema. Full policies and original definitions are in each prepared release's `feature_registry.json` and `provenance.json`.

## Additional measurements and their intended use

| Product | Time and spatial support | Prepared use | Main constraint |
|---|---|---|---|
| [MODIS MCD12Q1 v061 IGBP mosaic and QC](https://doi.org/10.5281/zenodo.8367523) | 2017; inspected raster spacing about 1/240° | Classified barren, water, crops, built area and other fractions; strict coverage gate | Provider derivative is CC BY-SA 4.0; default/unclassified barren labels are excluded |
| [Global AI/ET0 v3 annual](https://doi.org/10.6084/m9.figshare.7504448.v5) | 1970–2000 climatology; 30 arc-seconds | Earth precipitation/reference-ET0 climate screen | Requires valid positive ET0 support; provider license statements conflict |
| [MODIS/AVHRR-derived monthly vegetation and masks](https://doi.org/10.5281/zenodo.4305975) | Selected 2001–2017, 204 months; approximately 5 km | Raw and provisional NDVI means, calendar-month extrema and QA diagnostics | Smoothed/gap-filled values; derivative scale not independently confirmed; excluded from gates and rank; CC BY 4.0 |
| [ESA WorldCover v200](https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/docs/WorldCover_PUM_V2.0.pdf) | 2021; nominal 10 m | Finer class fractions and exposed-patch candidates at Gobi/Jaflong | A class prediction is not bare-rock percentage or local confidence; CC BY 4.0 |
| [Copernicus DEM GLO-30](https://copernicus-dem-30m.s3.amazonaws.com/readme.html) | Primarily 2011–2015 acquisitions plus mosaic/edits; nominal 30 m | Finer DSM-derived terrain at Gobi/Jaflong | Includes surface objects and edited water; separate from the regional planetary score; Copernicus DEM license |
| [NASA lunar polar LOLA products](https://pgda.gsfc.nasa.gov/products/90) | 400 m plane-fit baseline, sampled at 1 km | Independent Shackleton context | Definitions differ from the integrated fields; does not repair the missing target or enable its ranking |
| [USGS analog portal](https://tadp.astrogeology.usgs.gov/) and [PAAD](https://www.usgs.gov/data/paad-planetary-aeolian-analog-database) | Retrieved 2026-11-06; four general-feed records and 45 dune-field points | Scoped known-site review | Incomplete inventories; absence never establishes novelty |

The aridity provider's catalog says CC BY 4.0 while its README/description restrict commercial use. Both statements are retained in metadata. No commercial permission is inferred. The local DSM attribution and license URL are recorded in the relevant source manifest.

## Integrity and support

All **410 files** in the NDVI/aridity acquisition plan completed with publisher size and MD5 checks and locally recorded SHA-256 hashes. This comprises 204 vegetation rasters, 204 QA rasters, the annual AI/ET0 archive and its README. Land-cover inputs were acquired and checked separately. Local WorldCover/DSM COG windows have local hashes and retained remote headers; full remote-object checksums were not verified. Portal snapshots have local hashes, not publisher checksums.

Earth environmental aggregation uses spherical source/target pixel intersections, keeping valid-area coverage separate from the measurement. A valid zero remains zero. Missing or inadequately supported values remain null. Independent direct source-window calculations check land cover and aridity; the complete vegetation release also requires independent spatial and temporal verification before publication.

Matching nominal DEM grid spacing is insufficient to match effective resolution. LOLA/MOLA track gaps and interpolation, Earth source composition, different cell shapes and different physical footprints remain relevant. Equal-sized, consistently derived terrain footprints are a documented next product-development step, especially for lunar poles.

## What the package does not measure

It does not measure wheel-scale boulders, soil cohesion, bearing capacity, exposed chemistry, subsurface ice accessibility, actual biological absence, current weather, site access or an approved base location. Earth locations also cannot reproduce reduced gravity, lunar vacuum or the complete Martian atmosphere/radiation environment. Candidate briefs specify the narrower investigation each location could support.

See the [README](README.md) for the folder layout and every source link, and [ATTRIBUTION.md](ATTRIBUTION.md) for citations and terms.

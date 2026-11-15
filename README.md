# Mars, Moon and Earth integrated terrain dataset

Regional surface datasets for the Moon, Mars and Earth, prepared for finding Earth terrain analogs of lunar and Martian sites. Used by the **GeoNexus** planetary rover simulator ([live app](https://ikat5-geonexus.hf.space), [code](https://github.com/ikat5/GeoNexus)) for NASA Space Apps Challenge 2026.

Large files (`.parquet`) are stored with Git LFS: run `git lfs pull` after cloning.

## What is in this repository

| Folder / file | Contents |
|---|---|
| `earth_integrated_dataset/` | Earth table: 1,413,693 cells, 49 features (terrain, climate, land cover, lithology, craters, dunes), plus `earth_feature_dictionary.json` and `earth_metadata.json` (sources, units, terms) |
| `moon_integrated_dataset/` | Moon table: 259,200 cells, 87 features (LOLA topography, Diviner temperature and rock abundance, GRAIL gravity, Lunar Prospector chemistry, craters, pits, illumination, geology) |
| `mars_integrated_dataset/` | Mars table: 1,036,800 cells, 92 features (MOLA topography, TES thermophysics, Odyssey GRS/NS, OMEGA, climate, craters, dunes, caves, geology) |
| `prepared/0.2.0/` | **Current release**: per-body feature tables (`earth_features.parquet`, `mars_features.parquet`, `moon_features.parquet`), `feature_registry.json` (every feature's definition), `provenance.json` (input files, hashes, processing), `profiles.json`, `targets.json`, `validation.json`, `manifest.json` |
| `prepared/current_release.json` | Which release is current |
| `prepared/0.1.0`, `0.1.1`, `environment_0.1.0`, `app_*`, `local_pilot_*`, `gobi_candidate_0.1.0` | Earlier releases and small local studies, kept for reproducibility |
| `prepared/ml_0.3.0/` | Metadata of the S1 terrain-embedding index (the `.npz` is a [release asset](https://github.com/ikat5/mars_moon_earth_dataset/releases/tag/ml-0.3.0)) |
| `sources/` | Download manifests and small source extracts: land cover, aridity, NDVI, known analog sites, lunar polar context |
| `DATA_CATALOG.md` | How each source was used, its resolution and period, and its limits |
| `ATTRIBUTION.md` | Citations and per-source terms |

Quick look (Python): `import duckdb; duckdb.sql("SELECT * FROM 'prepared/0.2.0/mars_features.parquet' LIMIT 5").show()`

## Data sources

### NASA data
| Source | Link |
|---|---|
| LRO LOLA gridded topography (Moon terrain) | https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/ |
| LRO Diviner derived products: temperature, rock abundance, polar products | https://pds-geosciences.wustl.edu/lro/urn-nasa-pds-lro_diviner_derived1/ |
| GRAIL lunar gravity field | https://pds-geosciences.wustl.edu/grail/grail-l-lgrs-5-rdr-v1/ |
| Lunar Prospector gamma-ray spectrometer elements | https://pds-geosciences.wustl.edu/lunar/lp-l-grs-5-elem-abundance-v1/ |
| Lunar Prospector neutron spectrometer | https://pds-geosciences.wustl.edu/missions/lunarp/ |
| LROC lunar pit locations | https://pds.lroc.im-ldi.com/data/LRO-L-LROC-5-RDR-V1.0/ |
| NASA GSFC PGDA lunar polar illumination | https://pgda.gsfc.nasa.gov/data/MoonIllumination/ |
| NASA GSFC PGDA lunar polar LOLA products | https://pgda.gsfc.nasa.gov/products/90 |
| MGS MOLA gridded topography, MEGDR (Mars terrain) | https://pds-geosciences.wustl.edu/mgs/mgs-m-mola-5-megdr-l3-v1/ |
| Mars Odyssey gamma-ray spectrometer element maps | https://pds-geosciences.wustl.edu/ody/ody-m-grs-5-elements-v1/ |
| Mars Odyssey neutron spectrometer | https://pds-geosciences.wustl.edu/ody/urn-nasa-pds-odyssey_grs_special/ |
| MGS TES thermophysics and minerals (via ASU JMARS map server) | https://jmars.asu.edu/ |
| Mars Global Cave Candidate Catalog | https://astrogeology.usgs.gov/ckan/dataset/c2960f77-ee20-4cc6-ac85-abbecc0fc7f6 |
| MODIS MCD12Q1 v061 land cover 2017 (via OpenLandMap) | https://doi.org/10.5281/zenodo.8367523 |
| MODIS MOD11A2 land surface temperature (via OpenLandMap) | https://doi.org/10.5281/zenodo.1420115 |
| NDVI from NASA MODIS MOD09GA and NOAA AVHRR (via OpenLandMap) | https://doi.org/10.5281/zenodo.4305975 |
| USGS Terrestrial Analog Data Portal (NASA-funded) | https://tadp.astrogeology.usgs.gov/ |

### Space agency partner and other data
| Source | Link |
|---|---|
| ESA Mars Express OMEGA albedo maps (via ASU JMARS) | https://jmars.asu.edu/ |
| Mars Climate Database (LMD / CNES / ESA) | https://www-mars.lmd.jussieu.fr/mcd_python/ |
| ECMWF / Copernicus ERA5 monthly climate (NCAR GDEX d633001) | https://gdex.ucar.edu/datasets/d633001/ |
| ESA WorldCover 2021 v200 (local studies) | https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/docs/WorldCover_PUM_V2.0.pdf |
| Copernicus DEM GLO-30 (local studies) | https://copernicus-dem-30m.s3.amazonaws.com/readme.html |
| NOAA ETOPO 2022 global relief (Earth terrain) | https://www.ncei.noaa.gov/products/etopo-global-relief-model |
| Natural Earth (lakes / land mask) | https://www.naturalearthdata.com/ |
| Global Aridity Index and ET0 v3 (Zomer et al.) | https://doi.org/10.6084/m9.figshare.7504448.v5 |
| USGS global lithology (via OpenLandMap) | https://doi.org/10.5281/zenodo.1464846 |
| USGS Geologic Map of Mars, SIM 3292 (Tanaka et al. 2014) | https://pubs.usgs.gov/sim/3292/ |
| USGS Unified Geologic Map of the Moon (Fortezzo et al. 2020) | https://asc-astropedia.s3.us-west-2.amazonaws.com/Moon/Geology/Unified_Geologic_Map_of_the_Moon_GIS_v2.zip |
| USGS Mars Global Digital Dune Database (2007) | https://pubs.usgs.gov/of/2007/1158/ |
| USGS Mars Global Digital Dune Database (2018) | https://pubs.usgs.gov/of/2018/1164/ |
| Robbins Mars crater database | https://craters.sjrdesign.net/ |
| Robbins lunar crater database | https://asc-astropedia.s3.us-west-2.amazonaws.com/Moon/Research/Craters/Ancillary/Catalog_Moon_Release_20180815_shapefile180.zip |
| USGS terrestrial analog sites data release | https://doi.org/10.5066/P9J72921 |
| USGS Planetary Aeolian Analog Database (PAAD) | https://doi.org/10.5066/P9IFVZEX |
| Dune World global dune mask (geomorphlab) | https://github.com/geomorphlab/dune-world |
| Wikidata (Earth impact craters and caves) | https://query.wikidata.org/ |

Exact file URLs, retrieval dates and checksums for every input are in each body's `*_metadata.json` and in `prepared/0.2.0/provenance.json`.

## License and use

This repository has **no single license**. Each source keeps its own terms (for example CC BY 4.0, CC BY-SA 4.0, public domain for NASA/USGS data); see `ATTRIBUTION.md` and the metadata files, and cite the original sources when you use the data. Scores derived from these tables are experimental terrain-resemblance indices, not validated analog, safety or hardware-performance measures.

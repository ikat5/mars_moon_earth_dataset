# Data, imagery and software attribution

Compiled from the integrated datasets' `*_metadata.json`, `prepared/0.2.0/feature_registry.json`, [DATA_CATALOG.md](../analysis/DATA_CATALOG.md) and the frontend source. Per-source terms recorded in metadata take precedence. **The repository has no single license, and none is asserted here.**

## Data that feeds the terrain resemblance score

| Body | Source | Citation | Contributor |
|---|---|---|---|
| Moon | LRO LOLA gridded topography (ldem_64) | Smith D.E. et al. (2010) GRL 37, L18204; Neumann G.A. (2010) LRO-L-LOLA-4-GDR-V1.0, NASA PDS | **NASA** |
| Mars | MGS MOLA MEGDR 128 px/deg | Smith D.E. et al. (2001) JGR 106, 23689; Smith D.E. et al. (2003) MGS-M-MOLA-5-MEGDR-L3-V1.0, NASA PDS | **NASA** |
| Earth | ETOPO 2022 15 arc-second relief | NOAA NCEI (2022), doi:10.25921/fd45-gt74; Natural Earth land mask | NOAA |

## Earth-only screening and context

| Source | Period | Use | Terms noted |
|---|---|---|---|
| MODIS MCD12Q1 v061 IGBP land cover (derivative, [doi:10.5281/zenodo.8367523](https://doi.org/10.5281/zenodo.8367523)) | 2017 | Barren/water/built/crop gates | Derivative CC BY-SA 4.0; MODIS is a **NASA** instrument/product |
| Global Aridity Index & ET0 v3 ([doi:10.6084/m9.figshare.7504448.v5](https://doi.org/10.6084/m9.figshare.7504448.v5)) | 1970–2000 | Aridity gate | **Conflicting:** catalog CC BY 4.0, README restricts commercial use |
| MODIS/AVHRR-derived monthly NDVI ([doi:10.5281/zenodo.4305975](https://doi.org/10.5281/zenodo.4305975)) | 2001–2017 | Context only, never scored | CC BY 4.0 |

## Other integrated-dataset sources (context; not scored)

- **Moon:** Diviner (Williams 2017; Paige 2010; Siegler 2016; Bandfield 2011), Lunar Prospector GRS/neutrons (Prettyman 2006; Feldman 2001; Maurice 2004), GRAIL gravity (Lemoine 2014; Zuber 2013), LROC pit atlas (Wagner & Robinson 2021), PGDA illumination (Mazarico 2011), all **NASA** missions. Also Robbins (2019) craters and USGS Unified Geologic Map (Fortezzo 2020).
- **Mars:** TES minerals and thermophysics (Bandfield 2002; Christensen 2001; Nowicki & Christensen 2007), Mars Odyssey GRS/NS (Boynton 2007; Feldman 2004), the Mars Global Cave Candidate Catalog (Cushing 2017, PDS) and SWIM ice (Morgan 2021), all **NASA** missions/programs. Also OMEGA (Ody 2012, ESA Mars Express), Mars Climate Database (Millour 2018; Forget 1999), Robbins & Hynek (2012) craters, USGS SIM 3292 geology (Tanaka 2014), and dunes (Hayward 2007/2014; Fenton 2018).
- **Earth:** MODIS LST (Wan 2015, **NASA** LP DAAC, via Hengl 2018), ERA5 (Hersbach 2020, ECMWF), lithology (Hengl 2018; Sayre 2014), Earth Impact Database (UNB), Wikidata caves (CC0), dunes (Nature Communications 2026).

## Local studies

ESA WorldCover 2021 v200 (CC BY 4.0, Copernicus Sentinel-1/2), Copernicus DEM GLO-30 (Copernicus DEM license), NASA lunar polar LOLA products (PGDA), USGS analog portal and PAAD, and BWDB station listing (Jaflong location evidence).

## Globe imagery and labels (display only; not used in matching)

| Layer | Credit |
|---|---|
| Moon tiles | JAXA/SELENE Kaguya Terrain Camera mosaic via **NASA Moon Trek** |
| Lunar textures, point telemetry | **NASA SVS** CGI Moon Kit `ldem_64.tif` (LOLA-derived) |
| Mars tiles | MRO CTX global mosaic (**NASA/JPL/MSSS**, Caltech Murray Lab) hosted by Esri; Viking colour mosaic (**NASA/USGS**) via **NASA Mars Trek** |
| Earth tiles | Esri World Imagery and Reference (© Esri, Maxar, Earthstar Geographics, GIS User Community) |
| Place names | USGS/IAU Gazetteer of Planetary Nomenclature |

## Software

globe.gl 2.46.1 and three-globe (MIT), Chart.js 4.5.1 (MIT), Tailwind CSS Play CDN (MIT), FastAPI, Uvicorn, DuckDB, NumPy, Rasterio/GDAL, Pillow, Matplotlib, PyProj, Playwright (testing).

## Open attribution and licensing questions

1. **Repository license:** none chosen. A license is needed before public release.
2. **Aridity data:** conflicting commercial-use statements. Non-commercial use is assumed, and no commercial permission is inferred.
3. **Land-cover derivative (CC BY-SA 4.0):** check whether share-alike applies to the released `prepared/` tables that contain derived fractions.
4. **Esri basemaps and CTX tiles on a public deployment:** confirm the applicable Esri terms of use and attribution display.
5. **Moon Trek / Kaguya tiles:** confirm the JAXA data policy for redistribution of the cached tiles (the cache is not committed).
6. **Integrated-table generation:** upstream processing is described in metadata, but the raw-to-integrated code is not in this repository.

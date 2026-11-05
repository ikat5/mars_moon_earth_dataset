# TerraTwin — Moon & Mars integrated datasets

The final merged datasets for the TerraTwin project. Each body has **one main file** (`*_integrated.parquet`).
It is a table where each row is one map cell, and its columns are all the features from 8 scientific dimensions
merged together.

## Download

`mars_integrated.parquet` is 109 MB, over GitHub's 100 MB limit, so it is stored with **Git LFS**. Install Git LFS
once before cloning:

```bash
sudo apt install git-lfs      # macOS: brew install git-lfs   Windows: included with Git for Windows
git lfs install
git clone https://github.com/ikat5/mars_moon_earth_dataset.git
```

If `mars_integrated.parquet` is only a few hundred bytes, the file is still a Git LFS pointer, so the data is
missing. Run `git lfs pull` inside the repo.

> "Download ZIP" on GitHub may not include the LFS file. Use `git clone`.

## Files

| File | What it is |
|---|---|
| `moon_integrated_dataset/moon_integrated.parquet` | **Main Moon dataset**: 259,200 cells × 91 columns |
| `mars_integrated_dataset/mars_integrated.parquet` | **Main Mars dataset**: 1,036,800 cells × 96 columns |
| `*_feature_dictionary.json` | Information about every column: units, description, source, measurement type, coverage, min/max/mean |
| `*_metadata.json` | Grid definition, data sources with citations, limitations, processing config |

For analysis, you only need the `.parquet` file. Use the feature dictionary when you need to know what a column means.

## Load the data

```python
import json
import pandas as pd

moon = pd.read_parquet("moon_integrated_dataset/moon_integrated.parquet")
mars = pd.read_parquet("mars_integrated_dataset/mars_integrated.parquet")

# what a column means
info = {f["name"]: f for f in json.load(open("mars_integrated_dataset/mars_feature_dictionary.json"))}
print(info["elev_mean_m"]["units"], "-", info["elev_mean_m"]["description"])

# example: flat, low-elevation cells on Mars
flat = mars[(mars.slope_mean_deg < 2) & (mars.elev_mean_m < -3000)]
```

Requires `pandas` and `pyarrow` (`pip install pandas pyarrow`).

## Grid

| | Moon | Mars |
|---|---|---|
| Cell size | 0.5° (~15.2 km at equator) | 0.25° (~14.8 km at equator) |
| Grid shape (lat × lon) | 360 × 720 | 720 × 1440 |
| CRS | IAU_2015:30100 | IAU_2015:49900 |
| Radius | 1737.4 km | 3396.19 km |

Every table starts with `cell_id`, `lat`, `lon` (cell centre, longitude −180…180 °E) and `area_km2`.
`cell_id = row * n_lon + col`, where row 0 is the northernmost row and col 0 starts at −180 °E.

## The 8 dimensions

Every feature belongs to one or more dimensions. The `dimensions` field in the feature dictionary lists them.

| Dimension | Moon | Mars | Examples |
|---|---|---|---|
| geology | 24 | 27 | oxide abundances, geologic unit, TES minerals |
| terrain | 18 | 18 | elevation, relief, slope, roughness |
| environment | 16 | 14 | surface temperature, thermal inertia, albedo |
| resources | 15 | 13 | cold traps, ice stability, water-equivalent hydrogen |
| surface_processes | 4 | 18 | rock abundance, crater size distribution, dunes |
| habitability | 11 | 17 | temperature range, hydrated minerals, ice |
| subsurface | 8 | 5 | GRAIL gravity (Moon), cave candidates |
| exploration | 19 | 20 | landing/mobility slope fractions, illumination, Earth visibility |

## Rules for using the data

* **Missing values are NaN, never 0.** Coverage differs by source. Check `coverage_area_frac` in the feature
  dictionary.
* The Moon has **no wind or atmosphere columns**. They are absent by physics, not missing.
* Each column has a `measurement_type`: `measurement`, `derived_measurement`, `model`, `catalog`,
  `map_interpretation` or `derived_index`. Proxies and indices are not direct observations.
* Cave and ice columns are **candidates/proxies**, not confirmed detections.

## Sources & citation

The data comes from NASA PDS, USGS, PGDA, instrument teams and the Mars Climate Database: LRO LOLA, Diviner,
Lunar Prospector, GRAIL, MGS MOLA, TES, OMEGA, Mars Odyssey GRS/NS, SWIM, the Robbins crater databases, USGS
geologic maps, and others. The full citation and the known limitations for every source are in
`*_metadata.json` → `sources`. Please cite the original sources when you use the data.

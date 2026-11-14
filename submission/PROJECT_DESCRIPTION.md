# TerraTwin — project description

## The problem

University rover teams, planetary-science students and researchers often need an Earth place to rehearse a Moon or Mars investigation. They might drive a rover over comparable slopes, practise navigation over similar relief, or test instruments on similar ground. Well-known analog sites are few, far away and chosen for many reasons. A team usually cannot see **why** a place resembles a particular planetary region, **how strongly**, or **what differs**.

## What TerraTwin does

TerraTwin answers a narrow, inspectable question:

> Which Earth regions have regional terrain resembling this Moon or Mars region, why, and what needs closer examination before using one?

1. **Choose a target** on the 3D Moon or Mars globe, by coordinates, or from examples. TerraTwin outlines the *regional cell containing the point* (~15 km, ~200 km²) and shows its measured terrain. It states plainly that a precise click does not create point-scale evidence.
2. **Choose a screening mode.** *Terrain screening* considers every eligible Earth land cell. *Historical dry/barren screening* applies the same score only to Earth cells that were ≥80% barren land cover in 2017 and arid (aridity index ≤0.20, 1970–2000). An Earth distance limit from an origin is optional.
3. **Search.** The real engine runs over 1.3 million Earth cells in about 0.2 s. It compares median slope, 90th-percentile slope, relief and RMS roughness against declared tolerances.
4. **See the best match emerge.** The view moves from Mars or the Moon to Earth and reveals the top candidate's actual footprint at its true location. Every other candidate is a selectable footprint and list entry.
5. **Inspect the evidence.** For each candidate TerraTwin shows target and Earth values, differences, tolerances, each term's points, the closest agreement and largest mismatch. Earth-only historical context (land cover, aridity, provisional vegetation) is shown separately with its dates, alongside sources and limitations.
6. **Compare** two candidates to see which measurement drives the ranking difference.
7. **Go finer.** Two prepared local studies show the next step. At Gobi, 30 m elevation and 10 m land cover reveal variation hidden in the regional cell. At Jaflong, small exposed patches near Sylhet are missed by a regional screen.
8. **Export** query/results JSON, candidate GeoJSON, and a printable investigation brief with purpose, footprints, comparisons, sources, dates, version, limitations and proposed next measurements.

TerraTwin is honest about weak and missing answers. "No region within 500 km of Sylhet meets these filters" and "Shackleton's integrated terrain is missing" are shown as valid results; filters are never relaxed silently and no other site is substituted.

## Intended benefit

Teams get a **reasoned shortlist** of Earth regions for a stated purpose in minutes. Each comes with the measurements that justify it, the mismatches to check, and a brief they can take into planning. The same workflow teaches how regional summaries, data epochs and footprints limit what a "match" means.

## Data and method

The search uses team-prepared integrated grids: Earth 0.125°, Moon 0.5°, Mars 0.25°, about 2.7 million cells in total. Terrain comes from NOAA ETOPO 2022 (Earth), LRO LOLA (Moon) and MGS MOLA (Mars). The Earth screens use MODIS land cover (2017) and Global Aridity Index (1970–2000). The method is a deterministic, explainable distance score (`100 × (1 − Σ wᵢ·min(|Δᵢ|/tolᵢ, 1))`), not a trained model. Its tolerances, 50-point cutoff and weights are declared engineering defaults.

## Present limitations (summary)

The score is an uncalibrated **terrain resemblance** index, not accuracy, probability, safety or hardware performance. It compares ~15 km regional summaries, not sites. Materials, boulders, mechanical strength, access and permissions are not assessed, and no candidate is field-verified or a claimed new discovery. Full list: [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md).

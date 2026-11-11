# Known limitations

## Scientific

- **The score is an uncalibrated terrain resemblance index.** Tolerances (5°, 10°, 500 m, 100 m), equal weights, the 50-point cutoff, the 2/3–1.5 area ratio and the 100 km separation are engineering defaults, not fitted or validated thresholds. The score is not accuracy, confidence, probability, safety or predicted hardware performance.
- **It compares regional cells, not sites.** Each value summarizes a ~15 km native cell (~140–210 km²) derived from ~460–475 m terrain models. Finer imagery on the globe does not add scoring resolution.
- **Results jump at cell boundaries.** Moving a click a few metres across a cell edge selects a different cell and can change every result (archived tests retained 0/10 top regions). The UI always outlines the compared cell.
- **Only four terrain terms are scored.** TRI is a diagnostic only. Materials, mineralogy, boulders, mechanical strength, traction, temperature, illumination, ice and access are not compared.
- **Earth screens are historical:** land cover from 2017 and climate from 1970–2000. NDVI (2001–2017) has a provisional scale, is smoothed and gap-filled, and never affects eligibility or rank.
- **No candidate is field-verified or a claimed new discovery.** Known-analog inventories consulted are incomplete, so novelty cannot be assessed.
- **Landing point ≠ crater centre ≠ base footprint.** For example, the Jezero landing point and crater centre resolve to different cells.
- **Missing target data is reported, not filled.** Shackleton's integrated terrain is missing, and separate polar LOLA context uses different definitions.
- **Rank stability is not evaluated for live queries** (`rank_stability: null`).

## Operational

- **External dependencies.** The globe relies on CDNs and external imagery services (Esri, NASA Trek). Without them the panels still work (verified), and saved examples support offline demonstration.
- **Warm-up slowdown.** For a few minutes after a cold start, background tile prewarming slows searches (up to 3.9 s observed versus ~0.2 s steady). Start early or set `TERRATWIN_PREWARM=0`.
- **Concurrency headroom is small.** Ten-concurrent p95 was 1.81 s, meeting the 2 s target narrowly on a laptop CPU; the maximum was 2.2 s. Peak memory was 1.18 GiB.
- **Imagery artifacts.** Esri place-name tiles may show large blurred labels while higher zoom levels load. Software-rendered screenshots are less smooth than real GPUs.
- **Not done:** the Docker image is not built and verified, there is no public deployment, geolocation is not browser-tested, and the repository has no license.
- **Lunar point telemetry near the poles** uses an approximate east–west spacing (floored at cos 83°). It is labeled and never used for matching.

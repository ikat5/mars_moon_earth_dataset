# Draft submission text

Form field names and length limits are **unverified** (see [CHALLENGE_MAPPING.md](CHALLENGE_MAPPING.md)), so each text block below comes in a short and a long version. Fields marked *Pending* need team input.

## Team

- Team name: *Pending*
- Members, roles, locations, eligibility: *Pending*
- Challenge: Permanent Moon Base Locations and Mars *(title from the page URL; confirm against the official page)*

## Project name

TerraTwin

## One-line summary (~140 characters)

Pick a spot on the Moon or Mars and TerraTwin finds Earth regions with resembling terrain — showing why, what differs, and what to check next.

## Short description (~500 characters)

TerraTwin helps rover teams and students choose Earth places to rehearse Moon or Mars investigations. Select a region on a 3D globe and TerraTwin searches 1.3 million Earth terrain cells, optionally limited to historically dry, barren land. It then reveals the best match at its real location on Earth, shows each measured similarity and mismatch, compares alternatives, and exports a brief. It says plainly when nothing qualifies or when data is missing.

## Long description (~1,500 characters)

Teams preparing Moon or Mars field exercises need Earth sites that resemble a *specific* planetary region, and they need to know why. TerraTwin turns team-prepared global grids of terrain derived from NASA LOLA (Moon), NASA MOLA (Mars) and NOAA ETOPO (Earth) into an explainable search.

A user selects a location on the 3D Moon or Mars globe. TerraTwin outlines the ~15 km regional cell containing it and shows its slopes, relief and roughness. One search compares that cell with every eligible Earth cell, optionally restricted to land that was barren (2017 land cover) and arid (1970–2000 climate). The view then moves to Earth, where the best candidate's footprint emerges at its true location. Each candidate shows target and Earth values, differences, tolerances and points per measurement, its largest mismatch, and Earth context with dates.

Users can compare candidates, open finer local studies (30 m elevation and 10 m land cover at a Gobi candidate; small exposed patches near Sylhet), and export JSON, GeoJSON or a printable investigation brief.

TerraTwin is deliberately honest. Its score is labeled an uncalibrated terrain resemblance index, not accuracy or safety. It shows when no region meets the filters, and it reports missing data (as at Shackleton) instead of inventing a match. No candidate is presented as a field-verified or newly discovered analog.

## How NASA data is used

Moon terrain: LRO LOLA. Mars terrain: MGS MOLA. Earth screening: MODIS-derived land cover. Context layers from Diviner, Lunar Prospector, GRAIL, TES, Mars Odyssey and the Mars cave catalog. Globe imagery from NASA Moon/Mars Trek, CTX and Viking, and the lunar DEM from NASA SVS. Full list: [ATTRIBUTION.md](ATTRIBUTION.md).

## Tools

Python, FastAPI, DuckDB, NumPy, Rasterio; JavaScript with globe.gl and Chart.js; Playwright for testing. AI assistance: Claude Code was used to implement and test the search integration (recorded in commit trailers).

## Links

- Repository: https://github.com/ikat5/mars_moon_earth_dataset (branch `feat/terratwin-search-integration` until merged)
- Demo video: *Pending (final narrated recording)*
- Live demo: *Pending (no public deployment)*

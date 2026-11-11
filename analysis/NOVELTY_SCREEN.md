# Can TerraTwin surface analogs that are not already documented?

Run on 2026-11-12 with release 0.2.0. Reproduce with `python -m processing.novelty_screen --output analysis/novelty_screen_0.2.0.json`. Full output: [novelty_screen_0.2.0.json](novelty_screen_0.2.0.json).

**Short answer:** TerraTwin can produce **unreviewed leads**: Earth regions that repeatedly match Moon/Mars targets and lie far from every known site in our inventories. It **cannot establish novelty.** The inventories are small (62 points), and most strong leads fall in deserts that already have Mars-analog literature these inventories don't list.

## Method

- **18 targets:** 10 Mars (landing points, Jezero centre, ice-rich zones) and 8 Moon (Apollo sites, pits, equator, two Artemis regions) × both profiles × top 10 = 36 searches.
- **Reference set, 62 known sites:** USGS analog portal feed (4), USGS PAAD dune fields (45), predeclared analog controls (3), and the globe's reference analog pins (10, approximate centres).
- **Grouping:** candidate cells within 250 km of each other become one region. Each region gets the distance to the nearest known site.

## Results

- 34 searches returned candidates. Both Artemis polar targets returned **no dry/barren candidates**, a valid no-match.
- 313 unique Earth cells formed 175 regions: 3 lie within 100 km of a known site, 26 within 100–500 km, and **146 more than 500 km away** from every inventory point.
- **This distance is not novelty.** The leading regions sit in large deserts with published analog work that our inventories omit:

| Lead (approx. centre) | Approx. region (verify on a map) | Targets matched | Nearest inventory site | Literature status |
|---|---|---|---|---|
| 19.7°N, 33.2°E | Nubian Desert, Sudan | 8 (Mars + Moon) | Nahal Kasuy, Israel, 894 km | Not reviewed |
| 33.4°N, 60.4°E | Lut / eastern Iran | 7 | Lut desert, 144 km | Lut is a documented Mars analog |
| 24.4°N, 40.1°E; 24.2°N, 43.6°E | Central Arabian Peninsula | 6 and 5 | Qatar barchans, ~570–680 km | Not reviewed |
| 25.5°N, 30.1°E | Western Desert, Egypt | 5 | 475 km | Western Desert has Mars-analog literature |
| 29.5°N, 6.9°W | Southern Morocco | 4 (Mars) | Lanzarote, 495 km | Morocco has been used for Mars-analog field work |
| 38.3°N, 95.0°E | Qaidam / Kumtagh, China | 4 | Kumtagh, 145 km | Qaidam is a documented Mars analog |
| −23.9°S, 67.7°W | Atacama / Puna | 3 | Ojos del Salado, 118 km | Documented analog region |

Region names were inferred from coordinates and must be checked on a map. "Literature status" reflects general knowledge, not a systematic review.

## What the analysis reveals about the method

1. **The score saturates for flat targets.** For Jezero, Utopia and Marius Hills, 365,000–393,000 Earth cells score ≥ 50, and the top 10 all score 98.8–99.8. Rank order among them carries almost no information. A "99.7" here means "one of very many flat, smooth places".
2. **Rugged targets are discriminating, and that's where unusual leads appear.** Apollo 17 (relief 1,943 m) has only 173 dry/barren cells ≥ 50 (top score 75.5). Gale (relief 1,087 m) has 5,149 (top 89.2). Their leads include:
   - **23.2°N, 56.9°E**, approx. northern Oman (Hajar mountains): Apollo 17's best match (75.5); nearest inventory point 597 km
   - **22.1°N, 36.6°E**, approx. Red Sea Hills near the Sudan–Egypt border: Gale #3 (87.8); 894 km
   - **26.2°N, 5.4°E**, approx. central Algerian Sahara: Gale #4 (87.3); 1,707 km
   - **39.2°N, 74.3°E**, approx. western Tarim margin: Apollo 17 #4 (66.4); 1,552 km
   
   These are the most promising directions for a careful review. They are rugged, dry and arid, matched by the less-saturated targets, and far from the inventories. Oman as a whole does have Mars/astrobiology analog studies, so the question is whether *these specific cells and this terrain purpose* are documented.
3. **Terrain alone matches humid lowlands.** 39 of the 107 terrain-only regions are humid (aridity > 0.65), e.g. Borneo and the Congo Basin. Their terrain shape is similar, but they aren't usable analogs. The dry/barren profile exists for this reason.

## What a defensible "new analog" claim needs

For each lead:

1. A literature search: Google Scholar / ADS for the place name + "Mars analog" / "lunar analog" / "planetary analogue".
2. Comparison against fuller inventories (e.g. the Europlanet/ESA analog site lists, LPI analog compendia, ESA PANGAEA training sites).
3. Finer DEM and imagery checks, as in the Gobi study.
4. Expert review of geology and access.

Only after those checks could a lead be called "not previously documented for this purpose". Even then, "newly discovered" overstates it: these regions are known places on Earth, not new to science.

## Recommended next step for the project

Prioritize **rugged-target searches**, where the method discriminates. Add the mobility-slope terms (`slope_frac_gt_mobility`, `slope_frac_gt_landing`) so flat-target rankings regain meaning. Then expand the known-site inventory, so the novelty check measures something real.

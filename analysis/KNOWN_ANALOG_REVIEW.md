# Known-site review: what the catalogs can establish

Two public USGS portal feeds were inspected and snapshotted on 2026-11-06. Their local checksums, source URLs and acquisition scope are recorded under `sources/known_analogs` and `sources/known_analogs_paad`. These are documentation checks, not ground-truth labels for TerraTwin's terrain score.

## General portal feed

The current `terrestrial-analog-sites` endpoint used by the [USGS Terrestrial Analogs Data Portal](https://tadp.astrogeology.usgs.gov/) returned **four volcanic records**: Pisgah Lava Flow, Holuhraun Lava Flow, Oskjuvatn and Baugur. The endpoint was identified in the portal's public client script. Direct retrieval of the related 2020 ScienceBase catalog returned HTTP 403; equivalence between this four-record feed and the full archived release was not verified.

This feed is inadequate as a global known-site inventory. Its absence of a Gobi or Jaflong record provides no useful novelty evidence. One record also has a discrepancy between its geometry and coordinate attributes; both are preserved and their separation is measured. Proximity calculations use geometry coordinates without silently rewriting the source. [Related USGS release](https://www.usgs.gov/data/known-terrestrial-analog-sites-planetary-science).

The complete diagnostic output is [known_analog_review.json](known_analog_review.json). Do not display its large nearest-site distances as evidence of discovery.

## Planetary Aeolian Analog Database

The portal's separate PAAD WFS feed returned **45 dune-field records**, matching the count described in the initial USGS release. The feed explicitly declares EPSG:4326. All 45 geometry coordinates agree with their numeric latitude/longitude attributes within the declared 10 m consistency tolerance. Individual source attributes and references remain available in the snapshot. [USGS PAAD description](https://www.usgs.gov/data/paad-planetary-aeolian-analog-database).

For the Gobi candidate centered at 42.6875°N, 102.4375°E, the nearest PAAD reference point is **Badain Jaran Sand Sea, about 252.7 km away**. For the Jaflong window center, the nearest PAAD reference point is **Kumtagh Desert, about 1,657.9 km away**. These are spherical center-to-center distances, not distances to mapped site boundaries. Large sand seas may extend far from their catalog centers; their full extents were not compared. [Computed review](paad_review.json).

PAAD documents aeolian analogs; it is not a complete inventory of geological, polar, cave, operational or other analog sites. Neither proximity nor catalog absence establishes that a TerraTwin candidate is the same site, is suitable for a particular planetary test, or has not previously been studied.

## Candidate conclusion

The Gobi dossier also identifies prior regional Mars-analog publications. Those studies are not automatically evidence about the selected cell, but they preclude claiming that the broad Gobi–Mars connection is new. The current status remains **remote-sensing candidate, novelty not established**.

For a defensible future novelty claim, a reviewer would need to examine actual site extents, regional/local place names, geological maps and relevant publications, including sources beyond these catalogs. TerraTwin can expose the search scope and its gaps now; it must not convert incomplete documentation into a “new analog” badge.

# TerraTwin blueprint: technical feasibility and data preparation review

Reviewed 2026-11-06 against both pages of `/home/mashrafi/Downloads/TerraTwin Team Briefing & Project Blueprint.pdf`, the challenge supplied in the conversation, all three local integrated dataset schemas, and additional read-only queries of the actual tables.

This is the initial feasibility assessment, retained to explain the design corrections. Subsequent authorized implementation and measured results are documented in [PREPARATION_RESULTS.md](PREPARATION_RESULTS.md); the future product design is in [the master blueprint](../TERRATWIN_MASTER_BLUEPRINT.md). This review does not claim that new analog sites have been discovered. The original quantitative audit is in `dataset_audit.json` and `feature_coverage.csv`.

## Overall finding

The central product is feasible: a user chooses a Moon/Mars target and a testing purpose, then receives ranked Earth candidate regions with an explanation of the relevant similarities and differences. The three integrated tables provide a valuable regional search foundation.

The blueprint currently mixes regional analog discovery, local field-test-site characterization, and prediction of hardware behavior. These require different evidence. Regional discovery is supportable now; local characterization needs finer data; reliable traction, drill-performance and reduced-gravity predictions need geotechnical measurements and validated physical models beyond the supplied tables.

The most important corrections concern the meaning of scores, unresolved local scale, lunar polar terrain coverage, and the proposed ballast calculator. These are solvable software/data issues in some cases, but fundamental physical limitations in others.

## What can be completed here

| Work requested or implied by the blueprint | Assessment | Dependency or boundary |
|---|---|---|
| Deep audit of input tables, missingness, units, definitions, provenance and statistical redundancy | Can complete locally | Raw scientific source validation remains separate |
| Quality-controlled Earth candidate tables and planetary feature tables | Can prepare from existing files after scope/design agreement | Retain source values, missingness and rejection reasons |
| Feature comparability rules and purpose-specific scoring requirements | Can resolve and document | Geology, temperature, water and solar indices need explicit handling |
| Regional Earth analog search for a selected planetary target | Feasible with current terrain data for supported targets | A regional match is not a verified physical testing ground |
| Named planetary targets and region-specific summaries | Feasible | Verified feature identifiers, coordinate reference systems and explicit target footprints required |
| Vegetation, bare-ground and aridity enrichment | Feasible with additional open products | Download access, product QA, coverage and temporal alignment must be verified |
| Lunar south-polar terrain repair | Suitable open source products exist | Polar projection, frames, units and effective comparison baseline must be handled correctly |
| Travel-radius regional filtering | Feasible | Straight-line distance does not establish cost, access or usable test-site permissions |
| Local micro-analog discovery | Feasible for bounded regions with additional fine data | Current approximately 15 km cells cannot resolve quarries, ravines or small dry riverbeds |
| Two-site recommendation for separate test objectives | Feasible as a decision-support feature | Each objective needs measurable requirements and suitable evidence; sites may both fail a requirement |
| Earth solar-angle timing for a chosen date/location | Computable | Terrain horizon, atmosphere and lunar illumination duration remain different |
| Reduced-gravity load illustration | Computable as a restricted physical comparison | Cannot predict lunar sinkage/traction from ballast removal alone |
| Verified drillability, bearing strength, rover traction, ice accessibility or biological equivalence | Not established by supplied data | Requires site-specific observations, measurements or validated models |

## Blueprint corrections supported by the review

### 1. Regional cells are not micro-sites

The Earth grid is 0.125 degrees: approximately 13.9 km north-south. East-west width varies with latitude. Its terrain was derived from roughly 463 m source DEM spacing; it is not the 30 m/90 m SRTM terrain promised by the blueprint.

An individual quarry or ravine can be smaller than one source pixel, let alone one output cell. A map pin drawn at the cell center would imply location precision the data do not possess. Finer imagery and terrain can support local follow-up, but need to be acquired and evaluated for the selected region.

SRTM itself covers approximately 60 N to 56 S and therefore cannot fill Antarctic terrain requirements. Source: [USGS SRTM archive](https://www.usgs.gov/centers/eros/science/usgs-eros-archive-digital-elevation-shuttle-radar-topography-mission-srtm-1?qt-science_center_objects=0).

Even after adding 30 m terrain, wheel-contact-scale stones and granular strength remain unresolved. Fine local terrain characterization and fair cross-body terrain comparison also need separate scale checks: a slope derived at 30 m is not automatically comparable to one derived at roughly 470 m.

### 2. Shackleton is presently missing its principal mechanical terrain features

The [USGS Shackleton entry](https://planetarynames.wr.usgs.gov/Feature/5450) gives a center near -89.67 latitude, 129.78 E longitude. A diagnostic lookup of the containing local lunar cell produced:

| Field | Recorded value |
|---|---|
| Cell ID and center | 259099; -89.75, 129.75 |
| Cell area | 1.003 km2 |
| Elevation, median/p90 slope, relief, roughness | Missing |
| Mean/max/min temperature | 65.81 / 136.03 / 41.51 K |
| Mean illumination fraction | 0 |
| Permanently shadowed area fraction | 1 |

This lookup illustrates data readiness, not an approved Shackleton base footprint. A crater-center cell is not a crater-rim testing objective. In this release all 1,440 lunar cells poleward of 89.5 degrees have missing median slope. Returning a mechanical analog for this target by replacing missing slopes with zero would be invalid.

The very small cell area also illustrates polar grid distortion: the approximately 15 km equatorial width is not a universal cell size. At this latitude a longitude cell is much narrower than its north-south extent and can be narrower than the source DEM sampling.

NASA PGDA publishes [high-resolution lunar south-pole terrain](https://pgda.gsfc.nasa.gov/products/78), including 5 m/pixel projected products for specific sites, and [broader polar topography](https://pgda.gsfc.nasa.gov/products/90). Appropriate coverage must be checked before acquisition. These are not drop-in latitude-longitude replacements: source projection, MOON_ME/ephemeris frame, vertical units, coverage and comparison scale require handling.

### 3. Jezero supports an initial regional terrain comparison

The [USGS Jezero entry](https://planetarynames.wr.usgs.gov/Feature/14300) places its center near 18.41 N, 77.69 E. A diagnostic near 18.40 N, 77.69 E selects cell 412870 at 18.375 N, 77.625 E:

| Feature | Recorded value |
|---|---:|
| Cell area | 208.40 km2 |
| Median slope | 0.557 degrees |
| 90th percentile slope | 1.232 degrees |
| RMS roughness | 10.16 m |
| Relief | 148 m |
| Mapped process class | transition |
| Modeled mean surface temperature | 224.56 K |

These values characterize a grid cell, not the complete crater, delta, actual rover path or landing ellipse. A named crater, an official mission landing ellipse and an illustrative base region are different entities. Gazetteer outlines are approximate feature extents, not authoritative landing boundaries. Each target needs an explicit footprint and purpose, with its coordinate system checked against the data grid.

### 4. The proposed raw score is dimensionally undefined

`100 - sum(weight * absolute_difference)` cannot mix degrees, meters, kelvins, categories and fractions without defining dimensionless scaling and weight normalization. As written it can become negative, and a change in units can change the result. Nor is the result automatically a probability or an accuracy percentage.

The blueprint alternates weighted cosine and distance matching. They answer different questions: vectors [1, 2] and [10, 20] have identical direction and therefore maximal cosine similarity, despite very different magnitudes. The physical relevance of that behavior must be decided before choosing the metric.

Categorical lithology labels do not possess numeric distances. Earth `geo_unit`, lunar units and Martian units also use different vocabularies. The stored water and solar indices have incompatible definitions across bodies. No normalization can make unequal physical quantities become the same measurement.

The existing metadata's analog recipe requests Earth FeO, SiO2, K and Th chemistry, all absent, and Earth rock abundance, also absent. The availability of broad lithology does not make that stored recipe operational.

### 5. Terrain variables repeat much of the same information

Additional full-table Earth Pearson correlations are:

| Pair | Correlation |
|---|---:|
| Median and p90 slope | 0.949 |
| Relief and RMS roughness | 0.956 |
| Median slope and TRI | 0.985 |
| Landing hazard and traversability index | -0.944 |

These are descriptive correlations across the represented grid, not spatially independent statistical tests. They show why eight terrain-derived columns cannot be treated as eight independent pieces of evidence. The two derived exploration indices also reuse slope and roughness already present in the table.

### 6. NDVI does not supply rainfall, and low NDVI does not prove aridity

The blueprint attributes rainfall/aridity to MODIS LST and NDVI. LST measures surface temperature and NDVI describes vegetation greenness. Low NDVI can describe bare soil, rock, water, snow, recently cleared ground or seasonal conditions. A fixed 0.15 threshold alone does not establish a suitable desert analog or low biological activity.

NASA [MODIS vegetation products](https://modis.gsfc.nasa.gov/data/dataprod/mod13.php) can provide a vegetation screen. Precipitation and reference evapotranspiration require other variables, such as those in [TerraClimate](https://www.climatologylab.org/terraclimate.html). Its provider cautions against mixing versions and notes limited Antarctic validation. Quality flags, land cover, seasonality and observation dates matter for local testing.

### 7. Rock type does not determine drillability or traction

The Earth lithology table already distinguishes basic volcanics, intermediate volcanics, acid volcanic material, pyroclastics and several sedimentary classes. These are useful contextual distinctions. They do not measure unconfined compressive strength, abrasion, grain-size distribution, cohesion, friction angle, porosity, bulk density, moisture, regolith thickness or bearing strength.

Consequently a label such as basalt cannot justify an asserted hardware performance or percent hardness match. ASTER spectral indicators can support material interpretation in suitable exposed terrain; they do not directly provide all mechanical properties or validate ice/permafrost accessibility. Snow water equivalent is not a measurement of an ice-bearing drilling substrate.

The blueprint also misattributes MOLA to MRO: MOLA flew on [Mars Global Surveyor](https://science.nasa.gov/mission/mars-global-surveyor/science-instruments/).

### 8. The ballast feature cannot claim to simulate real lunar wheel sinkage

A restricted equality of supported weight is `m_Earth * g_Earth = m_target * g_target`. The lunar gravity ratio is approximately 0.165 according to the [NASA Moon fact sheet](https://nssdc.gsfc.nasa.gov/planetary/factsheet/moonfact.html). Thus a 100 kg lunar vehicle has a static weight comparable to approximately 16.5 kg on Earth, before considering wheel load distribution and other factors.

This does not make a lighter Earth vehicle dynamically equivalent to the lunar vehicle. Its inertia differs, and the soil remains under Earth's gravity; wheel-soil stresses and failure processes do not follow from that one equality. Removing ballast may also be physically impossible if the unballasted chassis already exceeds the desired mass.

A [2025 study in NASA's technical archive](https://ntrs.nasa.gov/citations/20250001809) specifically examines misleading results from gravitational-offset approaches. Any claim of exact sinkage, traction, drilling-force or excavation equivalence needs a validated physical model and measured input parameters. A load illustration can be calculated, but must be named according to its limited purpose.

### 9. Matching a solar angle is not reproducing lunar polar illumination

The blueprint's 1.8 degree angle is not a universal fixed lunar condition. [NASA's lunar polar illumination visualization](https://svs.gsfc.nasa.gov/5228/) illustrates changing Sun position near the horizon. Terrain shadows, slope orientation, observer height, time and location influence actual illumination.

An Earth date/location can have zero, one or more windows near a requested solar altitude. Solar azimuth and horizon occlusion matter too. Such a window does not reproduce lunar shadow duration, atmosphere, irradiance, thermal behavior or an entire testing campaign. [JPL Horizons](https://ssd.jpl.nasa.gov/horizons/) is an authoritative ephemeris reference, but astronomical direction alone does not establish local terrain visibility.

### 10. Data volume and latency are unverified goals

Actual main-table sizes are Earth 160.70 MB, Moon 41.09 MB and Mars 109.19 MB: **310.98 MB compressed in total**. Earth's 48 float columns alone require approximately 271 MB as uncompressed float32 arrays, before string categories, identifiers and other overhead. Five float32 features for all Earth rows require about 28.3 MB before coordinates, flags or metadata.

Therefore the blueprint's 2-15 MB dataset and 5 MB global CSV are not descriptions of the current assets. A curated subset may be that small; a full global dataset with the proposed variables will not automatically meet that budget.

The stated ten-minute GIS processing time and sub-50 ms match time have not been benchmarked. The latter must distinguish scoring computation from query filtering, candidate grouping, disk reads, serialization, network time and rendering. No algorithm should be described as meeting these numbers before measurement on the intended hardware.

The two-site optimizer additionally needs a clear objective and computational limit. Searching all unordered pairs of 1.41 million cells entails roughly one trillion pairs, before constraints; global brute force is not an acceptable implied implementation assumption.

### 11. Source attribution must describe actual providers

The local Earth table is not entirely NASA/USGS: its metadata also lists NOAA ETOPO, Natural Earth masks, ECMWF/Copernicus ERA5, OpenLandMap, a research dune catalog, Wikipedia-transcribed crater records and Wikidata caves. NASA/USGS datasets remain important contributors. Each output needs attribution to the actual primary and intermediary providers and must distinguish observations, interpreted maps, reanalyses, models and derived indices.

The existing dataset contains no verified training labels stating which Earth region is the correct analog for each planetary target and hardware task. It can support similarity ranking and exploratory clustering; it does not justify claiming supervised predictive accuracy or validated AI recommendations.

## Additional Earth readiness findings

- Of 1,413,693 rows, 891,305 have the five core terrain quantities, mean temperature and a nonmissing lithology value. Excluding the literal `undefined` lithology class reduces this to **889,525**. These are availability counts, not screened analog candidates.
- All 1,304,255 rows with complete core terrain already have `dem_valid_frac >= 0.95`; requiring 0.5, 0.8 or 0.95 did not change the joint complete counts. The low-validity deep-ocean-like artifacts reported earlier have missing roughness, so a complete-core-terrain rule excludes them. They still matter for modes permitting partial features.
- **34,645 cells** have `basic.volcanics` lithology together with available roughness and mean temperature. This indicates an existing pool for broad volcanic-context analysis, but does not establish exposed basalt, dryness, access or drilling suitability.
- An illustrative bounding rectangle from 20.5 to 26.7 N and 88 to 92.7 E contains 1,566 selected Earth cells, of which 1,347 have roughness, 1,565 have lithology and 1,562 have mean temperature. None has dominant `geo_class=volcanic`. This is not a country-boundary analysis and does not prove volcanic rocks or useful micro-sites are absent locally. It shows the danger of using coarse dominant-cell labels to make local claims.
- Antarctica remains a major gap: all rows south of 62 S lack the supplied Earth temperature and lithology layers. Thermal mode cannot silently exclude it and still claim complete global polar coverage.
- Even where temperature is present, Earth `tsurf_min_k` spans 222.45-302.05 K, Mars 141.35-194.46 K and Moon 19.39-131.98 K. The recorded ranges are disjoint and derived using different sampling definitions. A nearest match is not necessarily an acceptable match, especially for thermal hardware.

## Data preparation outcomes needed for the final product

These are required outcomes to resolve against the blueprint, not a chosen architecture or an implemented pipeline:

| Outcome | What must be demonstrated before it is called ready |
|---|---|
| Traceable source inventory | Input version, checksum, provider, unit, epoch, coordinate system, native resolution, observation/model type and known limitations are recorded |
| Quality-controlled candidate data | Missing values remain explicit; suspect cells, undefined classes and insufficient coverage have reason codes; original data remain recoverable |
| Comparable feature definitions | Every ranked quantity has a declared physical meaning, comparison scale, normalization and applicability to each body |
| Verified planetary target data | Names and identifiers are sourced; footprints and control networks are explicit; center/floor/rim/delta regions are not confused |
| Earth contextual enrichment | Vegetation, land cover and climatic dryness are supported by real products with QA and known temporal coverage |
| Local evidence for micro-sites | Fine terrain/imagery and named feature evidence actually resolve the proposed testing ground |
| Task-specific evidence | Essential measurements are available for the claimed test, or the mode clearly reports insufficient evidence |
| Product-serving dataset | Actual storage, memory, query latency, map payload and reproducibility are measured; raw archives need not be transferred to the browser |
| Candidate characterization | Each finalist includes a spatial footprint, relevant measurements, sources, uncertainty, physical mismatches and a specific testing use |
| Novelty assessment | Known analog inventories and relevant literature have been checked; unfamiliar is not treated as undiscovered |

## Evaluation requirements

A credible final product needs evaluation beyond attractive map results:

1. The system must reject or flag targets missing essential features, including the present Shackleton mechanical-terrain example.
2. Missing features must not increase a candidate's apparent evidence or silently turn into zero. A high score needs both a defined criterion and sufficient support.
3. Invalid land artifacts and undefined geology need controlled treatment for every supported profile, including profiles that allow partial terrain.
4. Rankings need sensitivity checks for feature scaling, weights, correlated variables, geographic aggregation and missing-data rules.
5. Spatial holdouts or regional separation are needed for any learned or tuned model; adjacent cells with repeated source values are not independent validation samples.
6. Known analogs provide sanity checks, and unsuitable controls can expose failures such as forested terrain ranking as a barren test ground. Neither alone proves predictive validity.
7. A top result may still be a weak analog. Report unsupported physical properties and allow no acceptable match.
8. A suggested pair of sites must be evaluated against its separate test requirements, rather than invented percentages or an undefined notion of complementarity.
9. Prototype performance must be benchmarked, with computation separated from end-to-end interaction and repeatable hardware/data settings documented.

## Understanding to confirm before design and preparation

The supplied blueprint appears to specify:

- A science-backed Earth analog discovery and characterization product for Moon/Mars targets.
- A primary audience of university rover teams and mission/science teams seeking useful testing environments.
- A planetary globe target selector, hardware/task selection and adjustable weighting.
- Earth candidate maps with dimension-specific evidence, comparisons and a field-test-readiness explanation.
- Regional travel-radius search, with micro-site claims depending on additional local evidence.
- Optional two-site testing recommendations and physics/illumination comparisons, with their limits corrected according to the review.
- Reproducible dataset preparation and validation before the final application is built.

Unconfirmed operating assumptions: the first release is a research/challenge prototype; public data are processed offline; this workspace holds preparation outputs; prepared assets support repeatable queries when upstream services are unavailable; no user account or stored travel location is required; team members will own reruns and source updates. Latency and payload budgets will be measured rather than promised. Hosting, concurrency, final local pilot geography and mandatory first-release hardware modes have not been specified.

The following are scientific limits, not silently removed product goals: natural Earth sites do not recreate lunar vacuum/gravity/radiation, and the supplied orbital grids do not establish hardware qualification, drilling strength, verified cave interiors or accessible subsurface ice.

## Decision record

| Item | Current state | Basis |
|---|---|---|
| Globe-to-Earth matching and task selection | User-supplied project intent | Blueprint sections 1 and 3 |
| Near-me, two-site and physical comparison features | User-supplied ambitions | Blueprint section 4 |
| Exact micro-site, material-hardness and sinkage-equivalence claims | Require revision | Resolution audit, missing geotechnical inputs and reduced-gravity literature |
| Final first-release task scope | Awaiting user confirmation | Data requirements differ materially by task |
| New architecture, scoring implementation and production dataset mutation | Not started in this review | Understanding/design confirmation required by the brainstorming workflow |

No implementation choice in this review should be read as approved merely because it appears in the original blueprint or in a feasibility observation.

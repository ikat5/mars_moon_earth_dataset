# Feature and status matrix

"Demonstrated" means exercised in the running application by the automated browser or API checks on 2026-11-12 (see [IMPLEMENTATION_STATUS.md](../analysis/IMPLEMENTATION_STATUS.md)).

## Demonstrated

| Capability | Notes |
|---|---|
| Moon/Mars target by globe click, coordinates (incl. longitude aliases) or example | Resolves to the containing native cell and outlines it |
| Regional terrain of the target cell; missing-terrain detection | Shackleton centre correctly reported as insufficient |
| Lunar DEM point telemetry, kept separate from matching values | Optional; requires the 1.06 GB DEM |
| Terrain screening and historical dry/barren screening | Same score, different Earth eligibility |
| Optional Earth origin + radius; user-initiated geolocation | Origin not stored; omitted from exports by default |
| Live search over the 0.2.0 release via `/api/v1/search` | Identical to the direct Python engine |
| Animated Moon/Mars → Earth reveal of the returned best candidate | Skip control; reduced-motion and no-WebGL show the same final state |
| Ranked list synced with Earth footprints; return to target | Query preserved while switching globes |
| Evidence panel: values, units, differences, tolerances, points, context with epochs, provenance, limitations, next measurements | |
| Two-candidate comparison explaining the score difference | Same query only |
| Gobi and Jaflong local studies with figures, briefs and footprints | Labeled as local studies, not retrieved or verified analogs |
| Exports: results JSON, Earth candidates GeoJSON, printable brief | Nulls and status flags preserved |
| Distinct outcomes: ok, no candidates, insufficient evidence, unavailable profile; plus validation and service errors with retry | |
| Saved release examples for offline demonstration | Banner: "not a newly executed query" |
| Phone layout, keyboard navigation, visible focus | 390×844 and 1440×900 checked |

## Implemented, not fully verified

| Item | Gap |
|---|---|
| Browser geolocation | Needs an interactive permission prompt; manual entry is verified |
| Docker image | `Dockerfile` written; not built in this environment |
| Real-GPU visual quality | Visual checks used software WebGL in headless Chrome |

## Roadmap (not available; selecting these profiles returns what is missing)

| Profile / feature | Missing evidence |
|---|---|
| Volcanic field geology | Exposed-material evidence, validated geology crosswalk, vegetation/land cover |
| Cold/dry operations | Precipitation/PET, temperature-sampling harmonization, Antarctic temperature |
| Cave reconnaissance | Verified cave catalog and local evidence |
| Ice drilling | Ice depth/properties, substrate mechanics |
| Fixed physical footprints (instead of native cells) | New preprocessing and evaluation |
| Seasonal suitability, access, permits, traction | Data and validation not present |
| Public deployment | Host and authorization not provided |

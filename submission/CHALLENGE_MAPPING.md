# Mapping to the 2026 challenge — PENDING

**Status: not completed, because the official challenge text could not be read.**

The master prompt directs this mapping to use the official page:
`https://www.spaceappschallenge.org/2026/challenges/permanent-moon-base-locations-and-mars/`

On 2026-11-12, both the fetch tool and direct HTTPS requests (curl, and Python with the certifi CA bundle) failed certificate verification. The server's chain ends at the legacy Comodo "AAA Certificate Services" root, which current trust stores here do not include. Verification was not bypassed. No challenge objectives, resources, judging criteria or submission limits have been assumed.

## To complete

Open the page in a normal browser and paste or save its text, then fill in:

1. **Challenge objectives.** Map each one to demonstrated features in [FEATURE_STATUS.md](FEATURE_STATUS.md). Label partial matches honestly. The challenge title mentions *permanent Moon base locations*: TerraTwin's demonstrated capability is regional terrain analog screening for a selected location, **not** base-site selection or ranking, so state that difference explicitly.
2. **Listed resources.** Note which ones the project already uses (see [ATTRIBUTION.md](ATTRIBUTION.md)). Before adding a new resource, assess whether it fills a real gap, and if integrated, use a new release version and rerun the checks.
3. **Submission requirements:** project page fields and character limits, video length and format, demo link, and eligibility of prior work (see [PRIOR_ASSETS_AND_NEW_WORK.md](PRIOR_ASSETS_AND_NEW_WORK.md)).
4. **Judging criteria.** Point each criterion to concrete evidence.

Then trim [SUBMISSION_DRAFT.md](SUBMISSION_DRAFT.md) to the verified limits.

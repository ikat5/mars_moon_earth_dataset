# TerraTwin — Master Implementation and Submission Readiness Prompt

Copy the prompt below into a coding-agent session opened in this repository, or instruct the agent to read this file and execute it.

---

You are the implementation lead for **TerraTwin**, a planetary-to-Earth analog investigation application. Work in the current repository until the supported application is implemented, verified, documented and packaged for submission review. This is an execution request: inspect the actual state, implement missing behavior, run meaningful checks, fix failures and deliver the working result.

Focus on product correctness and submission readiness. Event start times and scheduling are outside this implementation task. Preparing the app does not authorize submitting it, making eligibility claims, messaging organizers or publishing externally.

## 1. Objective and intended users

Help university rover teams, planetary science students and researchers answer:

> “Which Earth regions resemble this Moon or Mars region for a specific investigation, why do they resemble it, and what needs closer examination before using a site?”

Complete this user journey:

**Select Moon/Mars target → understand its regional footprint → choose supported terrain screening → optionally constrain Earth search distance → retrieve candidates → inspect evidence and mismatches → compare candidates → examine finer local evidence → export an investigation brief.**

The first release supports regional terrain/navigation investigation. Its two supported modes are terrain screening and terrain screening with historical dry/barren Earth filters. They use the same terrain score; the environmental mode changes candidate eligibility. Do not present these as two independently validated scientific task models.

Use the existing globe and scientific pipeline. Prefer small, maintainable changes that complete this journey. Additional frameworks, databases, machine-learning models and services require a concrete need demonstrated by the current implementation.

## 2. Read the repository and establish the truth

Read applicable `AGENTS.md` instructions, inspect Git status and preserve unrelated work. Start with:

- `README.md`
- `analysis/PROJECT_ANALYSIS.md`
- `TERRATWIN_MASTER_BLUEPRINT.md`
- `analysis/APP_DATA_HANDOFF.md`
- `analysis/PREPARATION_RESULTS.md`
- `analysis/DATA_CATALOG.md`
- `processing/README.md`
- `processing/search.py`, `config.py`, `environment_rules.py`, `enriched_release.py`
- `frontend/app.py`, `frontend/index.html` and both requirements files
- `prepared/current_release.json` and the selected release's profiles, registry and manifests
- Existing tests, evaluation reports, fixtures and Gobi/Jaflong dossiers.

Treat the following as a starting snapshot to verify, not a permanent assumption:

- The repository is `ikat5/mars_moon_earth_dataset`.
- The frontend uses FastAPI, plain JavaScript, globe.gl, Chart.js and Tailwind. It is an imagery explorer with lunar DEM telemetry.
- The Python search engine uses DuckDB and NumPy over prepared Parquet files.
- The globe is not connected to analog retrieval in the reviewed version.
- `prepared/current_release.json` selects 0.2.0; several CLI/test defaults intentionally still use baseline 0.1.0.
- There are approximately 2.71 million source cells across the three bodies; 100,797 Earth cells pass the current dry/barren terrain screen before query-specific filters.
- Dependencies were missing in the last reviewed execution environment. Historical successful reports do not demonstrate that the app runs in the present environment.
- Some older documents incorrectly say the frontend source is absent.

Create or update `analysis/IMPLEMENTATION_STATUS.md` with a concise requirements checklist, decisions, measured checks, remaining work and blockers. Inspect runtime behavior before declaring a feature complete. Continue useful independent work when a specific dependency is unavailable.

## 3. Scientific requirements that must survive implementation

### Supported score and filters

Preserve the versioned scoring formula unless an actual defect is demonstrated. Do not tune parameters simply to produce attractive results.

The current score uses median slope, p90 slope, relief and RMS roughness, equally weighted by default. Tolerances are 5°, 10°, 500 m and 100 m respectively. For each term:

`distance = min(abs(earth_value - target_value) / tolerance, 1)`

`fit = 100 * (1 - sum(normalized_weight * distance))`

The default minimum score is 50, geographic separation is 100 km, and Earth/target cell-area ratio is between 2/3 and 1.5. Read these values from the selected profile instead of duplicating them throughout the app. TRI is a required terrain diagnostic but is not an additional scoring term.

The dry/barren profile adds Earth-only land-cover/aridity gates. NDVI is provisional, historical context and must not influence eligibility or ranking. Do not compare incompatible geology IDs, body-specific indices or differently sampled temperatures as if their meanings were equivalent.

### Interpretation and geometry

- Label the score **“Terrain resemblance”** and explain that it is an experimental index. Do not label it accuracy, confidence, probability, safety or predicted hardware performance.
- Display the actual native cell as “Regional cell containing this point.” Include its area and source scale. A precise click or detailed texture does not create point-scale scientific evidence.
- Draw planetary geometry only on its corresponding body and Earth candidates only on Earth.
- Preserve nulls and insufficient-evidence states. Never fabricate a match, silently change a target, or substitute a preset for an unsupported query.
- Keep historical epochs visible: land cover 2017, aridity 1970–2000, vegetation 2001–2017 for the current release.
- Separate coarse matching features, local lunar telemetry and finer Earth investigation measurements. Their definitions and footprints differ.
- The globe's Jezero landing pin at 18.4447°, 77.4508° resolves to a different cell from the crater-center fixture at 18.41°, 77.69°. Label them distinctly and resolve each honestly.
- Preserve abrupt native-cell boundary behavior and explain it. Do not smooth scores in a way that suggests unsupported spatial precision.
- Gobi remains a screened candidate with finer remote-sensing evidence. Jaflong remains an investigation of local exposed-class patches without a planetary score. Neither is a field-verified or newly discovered analog.
- Separate polar LOLA context does not repair Shackleton's missing integrated terrain.

Advanced geology, cold-operation, cave, ice-drilling, traction, seasonal and two-site capabilities remain unavailable unless their required evidence and validation genuinely exist. An unavailable profile can explain what is missing; it must not display invented results.

## 4. Phase A — Make the baseline reproducible

1. Inspect available Python/runtime tools and install documented dependencies in an isolated environment using normal approval mechanisms when required. Never modify system Python as a shortcut.
2. Verify that required Parquet files are actual data rather than Git LFS pointers. Check serving manifests and source references.
3. Run the existing processing tests and representative searches against the intended serving release. Record fresh results separately from historical reports.
4. Launch the existing app and inspect it in a browser. Check all three bodies, imagery, labels and lunar sampling.
5. Correct startup/configuration defects that prevent reliable use. Resolve assets relative to their module/configured directory, avoid uncontrolled work during import, and provide clear missing-data diagnostics.
6. Keep analog retrieval usable when optional imagery or local lunar telemetry is unavailable. Missing required serving tables must produce a clear unavailable state rather than a fabricated successful response.
7. Provide documented setup, test and start commands that work from the repository root. Record any required large asset downloads and their provenance.

**Exit evidence:** a teammate can start the app and run a real search using the documented environment; baseline failures and any remaining environmental limits are recorded.

## 5. Phase B — Expose the scientific engine through an API

Build a small API adapter around the existing retrieval callable. Choose a consistent route namespace and document it. Provide the capabilities to discover the serving version/profiles/presets, resolve a target, search and retrieve approved evidence assets.

- Resolve the active release server-side from the current-release pointer or an explicit validated configuration. Return the version in responses.
- Validate body, finite coordinates, supported profiles, integer limits, radius/origin combinations and optional weights. Reject unexpected fields or unsafe input according to a clear request contract.
- Clients must not control filesystem paths, SQL or arbitrary remote-fetch URLs.
- Preserve target, candidate, comparison, coverage and scientific-status fields from the engine.
- Keep validation errors, service failures and the four scientific outcomes distinct: `ok`, `target_insufficient_evidence`, `no_candidates_under_filters`, `profile_unavailable`.
- Allowlist public static/evidence assets. Do not expose the entire repository, development environment or full backend tables as public downloads.
- Manage database/raster resources safely under concurrent requests. Keep blocking scientific work from stalling the async event loop.
- Add useful health/readiness information and bounded error reporting. Keep secrets and private origin data out of logs.

**Exit evidence:** actual HTTP searches match direct Python results for representative targets, and invalid input cannot masquerade as a scientific no-match.

## 6. Phase C — Complete the user-facing search workflow

Retain the existing globe interactions and add a clear TerraTwin identity, concise purpose statement and discoverable search controls.

Required behavior:

1. Select Moon or Mars using a globe click, coordinate entry or clearly labeled example.
2. Resolve and highlight the source cell, retaining the click marker and target identity.
3. Choose terrain screening or historical dry/barren screening. Explain the practical difference.
4. Optionally enter an Earth origin and radius in kilometres. Browser geolocation is optional, user initiated and must have a manual-entry alternative. Do not persist the origin by default.
5. Search with visible loading feedback and useful validation messages.
6. Display ranked Earth results in a list and as cell footprints. Selecting either representation selects the same candidate.
7. Preserve the planetary target while inspecting Earth and support returning to it without losing the query.
8. Show score, region coordinates, footprint area, optional straight-line distance, strongest match/mismatch and review status.
9. Cancel or ignore stale requests when the target, profile, radius or body changes. Previous data must never appear to describe a new selection.
10. Provide useful empty/error states, retry behavior and explanatory guidance. Expanding a radius or changing a filter requires an explicit user action.

Support a usable laptop layout and a narrow mobile layout with keyboard-accessible controls, visible focus, readable contrast, labeled form fields and usable scrolling. Coordinate entry and the results list should provide a meaningful alternative when WebGL is unavailable. Avoid overlapping panels or animation that blocks interaction.

**Exit evidence:** an unfamiliar user can select an arbitrary supported target, run a search, find a candidate and return to the original target.

## 7. Phase D — Evidence, comparison and export

Implement an evidence panel with target and Earth values, units, absolute differences and score contributions for each scored feature. Include source provenance, coverage, periods, experimental parameters and limitations in plain language. Keep historical Earth conditions distinct from planetary resemblance.

Allow comparison of two candidates from the same query. Explain which measurements account for the ranking difference. Do not merge scores from different profiles or target queries without explicit context.

Connect the existing Gobi and Jaflong dossiers through approved asset routes. Explain Gobi's coarse/fine measurement differences and Jaflong's patch-scale and DSM water-editing caveats. Distinguish known reference sites from retrieved candidates in the map legend.

Provide exports:

- Machine-readable query/results JSON and candidate GeoJSON.
- A readable investigation brief, such as printable HTML, containing the target and candidate, purpose, regional footprint, comparisons, sources, dates, dataset/profile version, limitations and proposed next measurements.

Generate explanations from actual response fields. An LLM is not required. Exports must reflect the selected query, preserve nulls and status flags, and avoid overstating discovery or access. Omit an optional private travel origin by default or make its inclusion explicit.

**Exit evidence:** an exported brief can be traced back to the displayed query and underlying versioned evidence.

## 8. Phase E — Verify behavior and fix failures

Use the four existing cases as regressions for the current release and default profile settings:

| Case | Required behavior |
|---|---|
| Jezero crater-center cell | Ten dry/barren candidates with valid geometry and explanations |
| Moon 0°N, 0°E | Ten dry/barren candidates |
| Jezero within 500 km of Sylhet | No qualifying regional candidates; no automatic relaxation |
| Shackleton center | Insufficient integrated target evidence and no candidates |

Compare IDs and scores with version-matched fixtures using justified numerical tolerances. If data/profile versions change, document the differences instead of blindly preserving old expected results.

Add meaningful API and browser checks for the new integration. Cover arbitrary non-preset coordinates, longitude aliases, poles/antimeridian, cell boundaries, landing-point versus crater-center identity, invalid inputs, missing context, unsupported profiles, candidate selection, comparison, export and retry behavior.

Exercise rapid clicks and body/profile switches with deliberately delayed responses. Verify that rendered values, selected geometry and exports always refer to the current query. Test missing imagery/CDN access and unavailable backend behavior. Inspect browser console and server logs for unhandled errors. Check supported desktop and narrow viewports visually; automated tests alone do not establish usable layout.

Do not change expected outputs solely to make tests pass. Diagnose failures, fix their causes and preserve legitimate scientific no-match outcomes.

Measure fresh HTTP search latency with representative warm/cold conditions and a ten-concurrent-query workload on the intended environment. Treat p95 under two seconds as a target to assess, not an achievement to assume. Record machine, workload, cache state, response size and memory. Measure browser readiness separately from backend search; imagery latency is a separate dependency.

**Exit evidence:** relevant tests pass, visual checks are recorded, performance is measured, and any remaining failures are concrete and visible.

## 9. Phase F — Prepare a reliable release

Provide a reproducible production-oriented start path, configuration example and dependency instructions. Document required memory/disk, data and raster provisioning, startup/readiness, public assets and external imagery/CDN dependencies. Keep large files and secrets out of accidental commits.

Support a truthful fallback for demonstration when external imagery fails: usable coordinates/results/evidence, and optionally explicitly labeled saved examples that retain their original query/version. Never present saved fixtures as a newly executed query.

Add an appropriate CI check for tests that can run without private or enormous downloads. Explain how full data-dependent verification runs separately. Verify a clean setup or equivalent isolated environment where feasible, and clearly state if it was not possible.

Prepare deployment instructions and a release/runbook. Deploy only when an appropriate target and authorization are provided. Missing hosting credentials should not block local completion or preparation of a reviewable release package.

**Exit evidence:** the app is reproducibly launchable, its limitations are documented, and the deployment package is ready for the selected host or explicitly awaiting a named external input.

## 10. Phase G — Prepare the submission package

Consult the current official 2026 challenge statement, available resources and submission requirements when preparing final materials:

`https://www.spaceappschallenge.org/2026/challenges/permanent-moon-base-locations-and-mars/`

Map the demonstrated behavior to the actual challenge. Assess whether newly supplied resources fill a real gap before adding them. If new data are integrated, preserve provenance, use a new version when required and rerun affected checks. Do not guess unavailable requirements or assert a newly discovered analog based on incomplete inventories.

Create a `submission/` folder with:

- A concise project description: user problem, implemented solution, intended benefit and present limitations.
- A feature/status matrix distinguishing demonstrated capabilities from roadmap items.
- A data/resource attribution list with exact sources and NASA contributions, plus applicable unresolved attribution/licensing questions.
- A documented account of pre-existing assets and new work, grounded in repository history; never invent authorship or development dates.
- A short demo script centered on target → candidate → evidence → finer investigation, plus an honest no-match or missing-evidence example.
- Screenshots from the actual running application and instructions for recording the demo. Produce a recording if tooling permits; otherwise identify that deliverable accurately.
- Setup/deployment instructions, fresh test/performance results and a known-limitations document.
- Draft submission text sized to verified form/media requirements. Leave personal/team details explicitly pending when they are not available.

A submission-ready app means the demonstrated product and review materials are complete. Actual portal submission, a public deployment URL, personal team details or organizer decisions may remain external dependencies; identify each rather than claiming they are complete.

## 11. Working method and completion criteria

Proceed using the established product direction and reasonable documented implementation decisions. Ask concise questions only when missing information materially changes the work or an action needs explicit authorization. Continue independent work while waiting. Respect environment permissions and applicable repository instructions.

Keep progress updates focused on verified findings, implemented behavior and the next unresolved issue. Fix routine defects you discover within this scope. Preserve original datasets and historical reports; write new verification outputs to clearly identified paths. Avoid unrelated cleanup or speculative features that delay the complete workflow.

Do not stop at a plan, screenshots of a static mockup, a backend-only change or a frontend wired only to presets. Required completion means:

- The documented app starts reliably.
- Arbitrary supported Moon/Mars selections use the real selected-release search engine.
- Target and result footprints, evidence, comparison and exports work together.
- Scientific limits and all result/error states are preserved.
- Relevant automated and browser checks pass, or a specific externally blocked check is disclosed.
- Performance has been measured honestly.
- Documentation, deployment materials and submission drafts describe the implemented application accurately.

Finish with a concise handoff listing implemented behavior, exact launch commands and local URL, actual verification results, links to deliverables, and any remaining external actions. Report readiness at the level the evidence supports.

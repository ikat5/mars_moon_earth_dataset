# TerraTwin submission package

Review materials prepared on 2026-11-12. **Nothing has been submitted, deployed publicly, or sent to organizers.** Items that depend on external input are marked *Pending*.

| Document | Contents | State |
|---|---|---|
| [PROJECT_DESCRIPTION.md](PROJECT_DESCRIPTION.md) | Problem, implemented solution, benefit, present limitations | Ready for review |
| [FEATURE_STATUS.md](FEATURE_STATUS.md) | Demonstrated capabilities vs roadmap | Ready for review |
| [DEMO_SCRIPT.md](DEMO_SCRIPT.md) | 3-minute demo script and recording instructions | Ready for review |
| [ATTRIBUTION.md](ATTRIBUTION.md) | Data, imagery and software sources, NASA contributions, open licensing questions | Ready for review; licensing questions open |
| [PRIOR_ASSETS_AND_NEW_WORK.md](PRIOR_ASSETS_AND_NEW_WORK.md) | What existed before and what was added, from Git history | Ready for review |
| [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md) | Scientific and operational limits | Ready for review |
| [CHALLENGE_MAPPING.md](CHALLENGE_MAPPING.md) | Mapping to the 2026 challenge statement | **Pending official challenge text** |
| [SUBMISSION_DRAFT.md](SUBMISSION_DRAFT.md) | Draft form text | **Pending form limits and team details** |

Setup, operation and deployment: [../analysis/RUNBOOK.md](../analysis/RUNBOOK.md). Verified test and performance results: [../analysis/IMPLEMENTATION_STATUS.md](../analysis/IMPLEMENTATION_STATUS.md) and [../analysis/performance_2026-11-12.json](../analysis/performance_2026-11-12.json).

**Screenshots** from the running application (headless Chrome, 2026-11-12) are in [../analysis/screenshots/](../analysis/screenshots/):

| File | Shows |
|---|---|
| `01a_reveal_emerging.png`, `01b_reveal_done.png` | Mars target → Earth reveal of the best returned candidate |
| `01_results_desktop.png` | Ranked results synced with footprints |
| `02_evidence_on_earth.png` | Evidence panel over the candidate's Earth location |
| `03_compare.png` | Two-candidate comparison |
| `04_brief.png` | Printable investigation brief |
| `05_no_match.png`, `06_insufficient_evidence.png` | Honest no-match and missing-evidence outcomes |
| `07_mobile_results.png` | Phone layout |
| `08_no_webgl_fallback.png` | Workflow without the 3D globe |
| `09_gobi_study.png` | Finer local study footprint |

**Demo recording:** a silent 65-second scripted recording is produced locally at `submission/media/terratwin_demo.webm` by `frontend/record_demo.py`. At 22 MB it is not committed. It runs with software rendering, so globe motion is less smooth than on a laptop GPU. A narrated recording on real hardware is recommended for the final video (see [DEMO_SCRIPT.md](DEMO_SCRIPT.md)).

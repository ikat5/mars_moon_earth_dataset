"""Regression: live searches against the serving release must reproduce its version-matched app fixtures.

Each fixture records its own query parameters, so the test re-runs exactly what was exported and
compares status, candidate IDs (in order) and scores. Scores are deterministic float64 arithmetic over
identical Parquet inputs; a 1e-9 tolerance only absorbs summation-order differences, not drift.
"""
import json
import unittest
from pathlib import Path

from processing.search import search

ROOT = Path(__file__).resolve().parents[1]
POINTER = ROOT / "prepared" / "current_release.json"
SCORE_TOLERANCE = 1e-9


def serving_paths():
    pointer = json.loads(POINTER.read_text())
    data_dir = ROOT / "prepared" / pointer["data_directory"]
    app_index = ROOT / "prepared" / pointer["app_index"]
    return pointer["version"], data_dir, app_index


VERSION, DATA_DIR, APP_INDEX = serving_paths()


@unittest.skipUnless((DATA_DIR / "earth_features.parquet").exists(), "Serving release data required")
class ServingReleaseFixtureTests(unittest.TestCase):
    def rerun(self, fixture):
        target, config = fixture["target"], fixture["configuration"]
        origin = tuple(config["origin"]) if config["origin"] is not None else None
        return search(target["body"], target["requested_lat"], target["requested_lon"], data_dir=DATA_DIR,
                      profile=fixture["profile"], limit=10, origin=origin, radius_km=config["radius_km"],
                      separation_km=config["minimum_separation_km"])

    def test_every_case_reproduces(self):
        index = json.loads(APP_INDEX.read_text())
        self.assertEqual(index["version"], VERSION)
        expected_status = {"jezero": ("ok", 10), "lunar_equatorial_coordinate": ("ok", 10),
                           "jezero_near_sylhet": ("no_candidates_under_filters", 0),
                           "shackleton": ("target_insufficient_evidence", 0)}
        self.assertEqual({c["id"] for c in index["cases"]}, set(expected_status))
        for case in index["cases"]:
            with self.subTest(case=case["id"]):
                fixture = json.loads((APP_INDEX.parent / case["query"]).read_text())
                earth = json.loads((APP_INDEX.parent / case["earth_geojson"]).read_text())
                live = self.rerun(fixture)
                self.assertEqual(live["dataset_version"], VERSION)
                self.assertEqual((live["status"], len(live["candidates"])), expected_status[case["id"]])
                self.assertEqual(live["status"], fixture["status"])
                self.assertEqual(live["target"]["feature_id"], fixture["target"]["feature_id"])
                expected = [(f["properties"]["feature_id"], f["properties"]["observed_fit"]) for f in earth["features"]]
                got = [(c["feature_id"], c["observed_fit"]) for c in live["candidates"]]
                self.assertEqual([x[0] for x in got], [x[0] for x in expected])
                for (_, a), (_, b) in zip(got, expected):
                    self.assertAlmostEqual(a, b, delta=SCORE_TOLERANCE)
                for c in live["candidates"]:
                    self.assertAlmostEqual(sum(x["fit_contribution"] for x in c["comparisons"]), c["observed_fit"], places=9)
                    self.assertEqual(c["geometry"]["type"], "Polygon")
                    self.assertFalse(c["local_site_verified"])
                    self.assertTrue(c["land_cover_screened"] and c["aridity_screened"])
                    self.assertFalse(c["vegetation_screened"])

    def test_sylhet_case_is_not_relaxed(self):
        live = search("mars", 18.41, 77.69, data_dir=DATA_DIR, profile="dry_barren_terrain",
                      origin=(24.89, 91.87), radius_km=500)
        self.assertEqual(live["status"], "no_candidates_under_filters")
        self.assertEqual(live["configuration"]["radius_km"], 500)
        self.assertEqual(live["candidates"], [])

    def test_landing_pin_and_crater_center_are_distinct_cells(self):
        landing = search("mars", 18.4447, 77.4508, data_dir=DATA_DIR, profile="dry_barren_terrain", limit=1)
        center = search("mars", 18.41, 77.69, data_dir=DATA_DIR, profile="dry_barren_terrain", limit=1)
        self.assertEqual(landing["target"]["feature_id"], "mars:412869")
        self.assertEqual(center["target"]["feature_id"], "mars:412870")


if __name__ == "__main__":
    unittest.main()

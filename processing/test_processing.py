"""Behavior checks for coordinate resolution, missing evidence and actual retrieval."""
import json
import math
import unittest

from processing.test_support import has_release_data
import numpy as np
from processing.config import DEFAULT_OUTPUT
from processing.search import normalize_location, cell_id_for_location, distances_km, normalized_fit, search


class MathematicalChecks(unittest.TestCase):
    def test_coordinate_boundaries(self):
        grid = {"shape": [360,720], "res_deg": 0.5}
        self.assertEqual(cell_id_for_location(90,180,grid),0)
        self.assertEqual(cell_id_for_location(-90,-180,grid),359*720)
        self.assertEqual(cell_id_for_location(0,360,grid),cell_id_for_location(0,0,grid))
        for lat,lon in [(91,0),(math.nan,0),(0,math.inf)]:
            with self.assertRaises(ValueError):normalize_location(lat,lon)

    def test_great_circle_wrap_and_poles(self):
        self.assertAlmostEqual(float(distances_km(0,179.9,0,-179.9)),22.238985,places=4)
        self.assertAlmostEqual(float(distances_km(90,0,90,120)),0,places=8)
        self.assertAlmostEqual(float(distances_km(0,0,0,180)),math.pi*6371,places=7)

    def test_score_and_missingness(self):
        scores,_=normalized_fit([[0,0],[5,10],[1,2]],[0,0],[1,1],[5,10])
        np.testing.assert_allclose(scores,[100,0,80])
        with self.assertRaises(ValueError):normalized_fit([[math.nan,0]],[0,0],[1,1],[5,10])
        with self.assertRaises(ValueError):normalized_fit([[1,2]],[0,0],[0,0],[5,10])
        with self.assertRaises(ValueError):normalized_fit([[1,2]],[0,0],[1,1],[0,10])


@unittest.skipUnless(has_release_data(DEFAULT_OUTPUT),"Prepared integration fixture not built (git lfs pull)")
class DatasetChecks(unittest.TestCase):
    def test_shackleton_no_fabricated_match(self):
        result=search('moon',-89.67,129.78)
        self.assertEqual(result['status'],'target_insufficient_evidence')
        self.assertFalse(result['candidates'])
        self.assertIn('roughness_rms_m',result['missing_terrain'])

    def test_unavailable_mode(self):
        result=search('mars',18.41,77.69,profile='ice_drilling')
        self.assertEqual(result['status'],'profile_unavailable')

    def test_real_query_explanations_and_separation(self):
        result=search('mars',18.41,77.69,limit=5)
        self.assertEqual(result['status'],'ok')
        self.assertEqual(len(result['candidates']),5)
        json.dumps(result,allow_nan=False)
        previous=101
        for i,c in enumerate(result['candidates']):
            self.assertLessEqual(c['observed_fit'],previous)
            previous=c['observed_fit']
            self.assertAlmostEqual(sum(f['fit_contribution'] for f in c['comparisons']),c['observed_fit'],places=7)
            self.assertFalse(c['local_site_verified'])
            self.assertGreaterEqual(c['target_area_ratio'],2/3)
            self.assertLessEqual(c['target_area_ratio'],1.5)
            for other in result['candidates'][:i]:
                self.assertGreaterEqual(float(distances_km(c['lat'],c['lon'],other['lat'],other['lon'])),100)

    def test_radius_filter(self):
        result=search('mars',18.41,77.69,origin=(24.89,91.87),radius_km=500,limit=3)
        self.assertTrue(result['candidates'])
        for candidate in result['candidates']:
            self.assertLessEqual(candidate['distance_from_origin_km'],500)
        result=search('mars',18.41,77.69,origin=(24.89,91.87),radius_km=0)
        self.assertEqual(result['status'],'no_candidates_under_filters')


if __name__=='__main__':unittest.main()

"""Integration regression: Earth-only gates must not be required on Mars."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
import duckdb
from processing.config import DEFAULT_OUTPUT
from processing.search import search
from processing.prepare import sql_path


@unittest.skipUnless(DEFAULT_OUTPUT.exists(),'Prepared source fixture required')
class EarthOnlyScreeningTests(unittest.TestCase):
    def test_rejects_best_terrain_when_environment_fails_and_preserves_null_context(self):
        baseline=search('mars',18.41,77.69,limit=2)
        candidate_ids=[int(c['feature_id'].split(':')[1]) for c in baseline['candidates']]
        target_id=int(baseline['target']['feature_id'].split(':')[1])
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary)
            (folder/'provenance.json').write_bytes((DEFAULT_OUTPUT/'provenance.json').read_bytes())
            definitions=json.loads((DEFAULT_OUTPUT/'profiles.json').read_text())
            profile=copy.deepcopy(definitions['profiles']['terrain_screening'])
            profile.update({'target_eligibility_column':'eligible_terrain','earth_eligibility_column':'eligible_dry_barren',
                            'earth_context_features':['ndvi_mean_provisional'],'land_cover_screened':True,'aridity_screened':True})
            definitions['profiles']['dry_barren_terrain']=profile
            (folder/'profiles.json').write_text(json.dumps(definitions))
            with duckdb.connect() as db:
                db.execute(f"COPY (SELECT * FROM read_parquet(?) WHERE cell_id=?) TO {sql_path(folder/'mars_features.parquet')} (FORMAT PARQUET)",
                           [str(DEFAULT_OUTPUT/'mars_features.parquet'),target_id])
                # Synthetic eligibility is confined to the temporary test fixture.
                db.execute(f"COPY (SELECT *,cell_id=? AS eligible_dry_barren,NULL::DOUBLE AS ndvi_mean_provisional FROM read_parquet(?) WHERE cell_id IN (?,?)) TO {sql_path(folder/'earth_features.parquet')} (FORMAT PARQUET)",
                           [candidate_ids[1],str(DEFAULT_OUTPUT/'earth_features.parquet'),*candidate_ids])
            result=search('mars',18.41,77.69,folder,profile='dry_barren_terrain')
        self.assertEqual(result['status'],'ok')
        self.assertEqual([x['feature_id'] for x in result['candidates']],[f'earth:{candidate_ids[1]}'])
        candidate=result['candidates'][0]
        self.assertAlmostEqual(candidate['observed_fit'],baseline['candidates'][1]['observed_fit'])
        self.assertIsNone(candidate['earth_environment_context']['ndvi_mean_provisional'])
        self.assertTrue(candidate['land_cover_screened'])
        self.assertTrue(candidate['aridity_screened'])
        self.assertFalse(candidate['vegetation_screened'])
        json.dumps(result,allow_nan=False)


if __name__=='__main__':unittest.main()

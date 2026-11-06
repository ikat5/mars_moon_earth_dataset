"""Exercise arbitrary selections, coordinate aliases and cell-boundary sensitivity."""
import argparse
from datetime import datetime,timezone
import json
import math
from pathlib import Path
import duckdb
from processing.config import ROOT
from processing.prepare import digest,write_json
from processing.enriched_release import verify_manifest
from processing.search import search,normalize_location
from processing.evaluate import regional_overlap


def evaluate(data_dir=ROOT/'prepared/0.1.1'):
    data_dir=Path(data_dir).resolve();manifest=verify_manifest(data_dir)
    provenance=json.loads((data_dir/'provenance.json').read_text())
    points=[(43.123,27.456),(-17.42,138.13),(-52.83,-69.17),(23.4,-127.8),
            (71.2,47.7),(-72.6,99.1),(0,180),(0,-180),(12.34,359.2),
            (12.34,-.8),(90,42),(-90,-85)]
    output={'dataset_version':manifest['version'],'created_utc':datetime.now(timezone.utc).isoformat(),
            'prepared_manifest_sha256':digest(data_dir/'manifest.json'),'engine_sha256':digest(ROOT/'processing/search.py'),
            'scope':'Functional geography and boundary diagnostics; not scientific analog accuracy. Arbitrary points are not selected mission sites.',
            'arbitrary_queries':[],'aliases':[],'boundary_cases':[]}
    results={}
    with duckdb.connect() as db:
        for body in ['moon','mars']:
            for lat,lon in points:
                r=search(body,lat,lon,data_dir,profile='dry_barren_terrain',limit=3)
                nlat,nlon=normalize_location(lat,lon)
                # Independent lookup against exported bounds, not row/column arithmetic.
                row=db.execute('''SELECT feature_id FROM read_parquet(?)
                     WHERE west<=? AND east>? AND north>=? AND (south<? OR (?=-90 AND south=-90))''',
                     [str(data_dir/f'{body}_features.parquet'),nlon,nlon,nlat,nlat,nlat]).fetchall()
                assert len(row)==1 and row[0][0]==r['target']['feature_id'],(body,lat,lon,row,r['target']['feature_id'])
                assert r['status'] in ['ok','target_insufficient_evidence','no_candidates_under_filters']
                if r['status']=='target_insufficient_evidence':assert not r['candidates']
                for candidate in r['candidates']:
                    assert candidate['land_cover_screened'] and candidate['aridity_screened']
                    assert candidate['scored_feature_coverage']==1
                json.dumps(r,allow_nan=False)
                output['arbitrary_queries'].append({'body':body,'lat':lat,'lon':lon,'resolved_id':r['target']['feature_id'],
                    'status':r['status'],'candidate_count':len(r['candidates']),'independent_bounds_lookup':'passed'})
                results[(body,lat,lon)]=r
            for a,b in [((0,180),(0,-180)),((12.34,359.2),(12.34,-.8))]:
                first,second=results[(body,*a)],results[(body,*b)]
                assert first['target']['feature_id']==second['target']['feature_id']
                assert first['candidates']==second['candidates']
                output['aliases'].append({'body':body,'locations':[a,b],'status':'identical_target_and_results'})
    for label,body,lat,lon in [('jezero_northern_cell_boundary','mars',18.5,77.69),
                               ('lunar_equatorial_cell_boundary','moon',0,.25)]:
        epsilon=.0001
        north=search(body,lat+epsilon,lon,data_dir,profile='dry_barren_terrain')
        south=search(body,lat-epsilon,lon,data_dir,profile='dry_barren_terrain')
        assert north['target']['feature_id']!=south['target']['feature_id']
        separation_m=math.radians(2*epsilon)*provenance['bodies'][body]['grid']['radius_km']*1000
        output['boundary_cases'].append({'id':label,'body':body,'selection_separation_m':separation_m,
            'north_target':north['target'],'south_target':south['target'],
            'north_candidate_ids':[c['feature_id'] for c in north['candidates']],
            'south_candidate_ids':[c['feature_id'] for c in south['candidates']],
            'top_ten_regional_retention_100km':regional_overlap(north['candidates'],south['candidates']),
            'interpretation':'A tiny click movement changes the whole containing source cell. This tests grid sensitivity, not a physical change over this small ground distance.'})
    output['status']='functional_checks_passed_boundary_sensitivity_reported'
    destination=ROOT/'analysis'/f'geography_validation_{manifest["version"]}.json'
    write_json(destination,output)
    print('Validated',len(output['arbitrary_queries']),'arbitrary queries and',len(output['aliases']),'longitude aliases.')
    for r in output['boundary_cases']:print(r['id'],r['selection_separation_m'],r['top_ten_regional_retention_100km'])
    return output


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--data-dir',type=Path,default=ROOT/'prepared/0.1.1')
    evaluate(parser.parse_args().data_dir)

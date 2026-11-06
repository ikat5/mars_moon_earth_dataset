"""Export reviewable GeoJSON and evidence cards for the existing globe UI."""
from datetime import datetime, timezone
import argparse
import json
from pathlib import Path
import duckdb
from processing.config import ROOT, DEFAULT_OUTPUT
from processing.prepare import digest, write_json
from processing.search import distances_km


def export(output=ROOT/'prepared'/'app_0.1.0',data_dir=DEFAULT_OUTPUT,query_dir=None):
    output=Path(output).resolve()
    data_dir=Path(data_dir).resolve()
    version=json.loads((data_dir/'manifest.json').read_text())['version']
    if output.exists():raise FileExistsError(output)
    staging=output.with_name(output.name+'.building');staging.mkdir(parents=True)
    query_dir=Path(query_dir).resolve() if query_dir is not None else ROOT/'analysis'/'queries'
    cases=[('jezero','jezero_balanced.json','Jezero crater-center cell'),
           ('lunar_equatorial_coordinate','lunar_equatorial_coordinate_balanced.json','Illustrative lunar coordinate, 0°N 0°E'),
           ('jezero_near_sylhet','jezero_near_sylhet_balanced.json','Jezero terrain query within 500 km of Sylhet'),
           ('shackleton','shackleton_coverage.json','Shackleton center: insufficient integrated terrain')]
    index={'version':version,'created_utc':datetime.now(timezone.utc).isoformat(),'cases':[],
           'scientific_status':'Experimental regional terrain screening; no verified analog discoveries.',
           'usage':'Render returned Earth polygons as screening footprints. Keep target planetary geometry on its own body globe.',
           'score_label':'Terrain resemblance (uncalibrated)',
           'required_visible_caveats':['Fit does not measure overall analog suitability or confidence.',
              'Named planetary centers are not landing ellipses or base footprints.',
              'Scenario retention is sensitivity evidence, not a confidence probability.',
              'A selection represents its entire source cell; crossing a cell boundary can change the ranking abruptly.']}
    if version=='0.1.0':index['required_visible_caveats'].append('January 2001 vegetation sample is provisional context, not a seasonal vegetation screen.')
    else:
        index['required_visible_caveats'].append('Earth land cover (2017) and climate (1970–2000) are historical screening evidence, not current field conditions.')
        if version=='0.2.0':
            index['required_visible_caveats'].append('Vegetation context covers 2001–2017; its NDVI scale is provisional and it never affects the score or eligibility.')
        index['related_investigations']=[{'id':'gobi','path':'../gobi_candidate_0.1.0/metadata.json','geojson':'../gobi_candidate_0.1.0/candidate.geojson',
                                        'status':'finer_remote_sensing_context_unverified_in_field'},
                                       {'id':'jaflong','path':'../local_pilot_0.1.1/metadata.json','geojson':'../local_pilot_0.1.1/patch_candidates.geojson',
                                        'status':'local_exposed_patch_investigation_no_planetary_score'}]
    source_files=[data_dir/'manifest.json',data_dir/'feature_registry.json',query_dir.parent/'retrieval_evaluation.json']
    ndvi=ROOT/'prepared/environment_0.1.0/ndvi_sample' if version=='0.1.0' else None
    if ndvi is not None and ndvi.exists():source_files.extend([ndvi/'manifest.json',ndvi/'metadata.json'])
    with duckdb.connect() as db:
        for key,filename,title in cases:
            query_file=query_dir/filename
            query=json.loads(query_file.read_text());source_files.append(query_file)
            variants={}
            for path in sorted(query_dir.glob(key+'_*.json')):
                variant=path.stem.removeprefix(key+'_')
                if variant in ['balanced','slope_emphasis','amplitude_emphasis','no_median_slope','no_relief']:
                    variants[variant]=json.loads(path.read_text())['candidates'];source_files.append(path)
            features=[]
            for rank,candidate in enumerate(query['candidates'],1):
                cell=int(candidate['feature_id'].split(':')[1])
                evidence={k:v for k,v in candidate.items() if k!='geometry'}
                evidence.update({'body':'earth','rank':rank,'source_cell_id':cell,
                                 'terrain_source_registry':'feature_registry.json#bodies/earth/features'})
                # Cell-level retention intentionally allows any candidate within
                # 100 km in a scenario; unlike whole-list retention it is not 1:1.
                retained={name:any(float(distances_km(candidate['lat'],candidate['lon'],c['lat'],c['lon']))<=100 for c in cs)
                          for name,cs in variants.items()}
                evidence['sensitivity']={'scenarios':retained,'retained_scenarios':sum(retained.values()),
                    'scenario_count':len(retained),'nearby_threshold_km':100,
                    'definition':'Any top-ten candidate within 100 km under each declared weight/feature scenario; scenarios are not independent trials.'}
                cur=db.execute('SELECT geology_unit_known,geo_class,quality_flags,tsurf_mean_k FROM read_parquet(?) WHERE cell_id=?',
                               [str(data_dir/'earth_features.parquet'),cell])
                evidence['unscored_source_context']=dict(zip([x[0] for x in cur.description],cur.fetchone()))
                if ndvi is not None and ndvi.exists():
                    cur=db.execute('SELECT * EXCLUDE(cell_id) FROM read_parquet(?) WHERE cell_id=?',[str(ndvi/'features.parquet'),cell])
                    evidence['vegetation_diagnostic']={**dict(zip([x[0] for x in cur.description],cur.fetchone())),
                        'period':'January 2001 only','scale_status':'provisional_inferred_1e-4',
                        'source':'https://doi.org/10.5281/zenodo.4305975','used_in_rank':False,
                        'limitations':'One smoothed/gap-filled historical monthly composite; no seasonal or bare-ground conclusion.'}
                features.append({'type':'Feature','id':candidate['feature_id'],'geometry':candidate['geometry'],'properties':evidence})
            geojson={'type':'FeatureCollection','features':features}
            assert len(features)==len(query['candidates'])
            assert len({f['id'] for f in features})==len(features)
            for feature in features:
                ring=feature['geometry']['coordinates'][0]
                assert ring[0]==ring[-1] and all(-180<=p[0]<=180 and -90<=p[1]<=90 for p in ring)
                assert feature['properties']['body']=='earth'
            write_json(staging/f'{key}_earth.geojson',geojson)
            detail={k:v for k,v in query.items() if k!='candidates'}
            detail['earth_geojson']=f'{key}_earth.geojson'
            write_json(staging/f'{key}_query.json',detail)
            index['cases'].append({'id':key,'title':title,'status':query['status'],'candidate_count':len(features),
                                   'query':f'{key}_query.json','earth_geojson':f'{key}_earth.geojson'})
    write_json(staging/'cases.json',index)
    (staging/'feature_registry.json').write_bytes((data_dir/'feature_registry.json').read_bytes())
    write_json(staging/'provenance.json',{'source_files':{str(p.relative_to(ROOT)):digest(p) for p in sorted(set(source_files))},
                                         'export_code_sha256':digest(Path(__file__))})
    write_json(staging/'manifest.json',{'files':{p.name:{'bytes':p.stat().st_size,'sha256':digest(p)} for p in staging.iterdir() if p.is_file()}})
    staging.rename(output)
    print(f'Published {output}: {len(index["cases"])} query cases, {sum(c["candidate_count"] for c in index["cases"])} Earth candidate footprints')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'prepared/app_0.1.0')
    parser.add_argument('--data-dir',type=Path,default=DEFAULT_OUTPUT)
    parser.add_argument('--query-dir',type=Path)
    args=parser.parse_args();export(args.output,args.data_dir,args.query_dir)

"""Verify published serving files, references and declared scientific flags."""
import json
from datetime import datetime, timezone
from pathlib import Path
from processing.config import ROOT
from processing.enriched_release import verify_manifest
from processing.prepare import digest, write_json


def verify():
    version='0.2.0';data=ROOT/'prepared'/version;app=ROOT/'prepared'/f'app_{version}'
    folders=[data,app,ROOT/'prepared/gobi_candidate_0.1.0',ROOT/'prepared/local_pilot_0.1.1',
        ROOT/'prepared/environment_0.1.0/landcover_2017',ROOT/'prepared/environment_0.1.0/aridity_0.1.1',
        ROOT/'prepared/environment_0.1.0/ndvi']
    manifests={}
    for folder in folders:
        verify_manifest(folder);manifests[str(folder.relative_to(ROOT))]=digest(folder/'manifest.json')
    index=json.loads((app/'cases.json').read_text());assert index['version']==version
    expected={'jezero':('ok',10),'lunar_equatorial_coordinate':('ok',10),
              'jezero_near_sylhet':('no_candidates_under_filters',0),'shackleton':('target_insufficient_evidence',0)}
    assert {c['id'] for c in index['cases']}==set(expected)
    verified=[]
    for case in index['cases']:
        query=json.loads((app/case['query']).read_text());geo=json.loads((app/case['earth_geojson']).read_text())
        assert query['dataset_version']==version and query['profile']=='dry_barren_terrain'
        assert (case['status'],case['candidate_count'])==expected[case['id']]
        assert query['status']==case['status'] and len(geo['features'])==case['candidate_count']
        assert query['earth_geojson']==case['earth_geojson']
        json.dumps([query,geo],allow_nan=False)
        for feature in geo['features']:
            p=feature['properties']
            assert p['feature_id']==feature['id'] and p['body']=='earth'
            assert p['land_cover_screened'] and p['aridity_screened']
            assert not p['vegetation_screened'] and not p['local_site_verified']
            assert 'ndvi_mean_provisional' in p['earth_environment_context']
            assert p['environment_evidence']['ndvi']['scale_status']=='provisional_not_used_in_gates'
            ring=feature['geometry']['coordinates'][0]
            assert ring[0]==ring[-1] and all(-180<=x<=180 and -90<=y<=90 for x,y in ring)
            assert abs(sum(c['fit_contribution'] for c in p['comparisons'])-p['observed_fit'])<1e-8
        verified.append({'id':case['id'],'status':case['status'],'candidate_count':case['candidate_count'],'checks':'passed'})
    for linked in index['related_investigations']:
        for key in ['path','geojson']:
            p=(app/linked[key]).resolve();assert p.is_relative_to(ROOT/'prepared') and p.is_file()
    required_reports=['ndvi_verification.json','release_upgrade_verification.json','control_evaluation_0.2.0.json',
                      'geography_validation_0.2.0.json','release_summary_0.2.0.json','score_diagnostics_0.2.0.json','benchmark_0.2.0.json']
    reports={}
    for name in required_reports:
        p=ROOT/'analysis'/name;json.dumps(json.loads(p.read_text()),allow_nan=False);reports[name]=digest(p)
    assert json.loads((ROOT/'analysis/enrichment_worker_status.json').read_text())['worker_status']=='processing_complete'
    acquisition=json.loads((ROOT/'sources/enrichment_downloads.json').read_text())
    assert len(acquisition)==410 and all(r['status'].startswith('verified_') for r in acquisition)
    result={'status':'passed','dataset_version':version,'created_utc':datetime.now(timezone.utc).isoformat(),
        'scope':'Serving files and scientific-status contracts; not deployed UI or field validation.',
        'verified_manifests':manifests,'supporting_reports':reports,'cases':verified,
        'app_file_bytes':sum(p.stat().st_size for p in app.iterdir() if p.is_file()),
        'source_plan_files_verified':410,'source_worker_finished':True,'code_sha256':digest(__file__)}
    write_json(ROOT/'analysis/handoff_verification_0.2.0.json',result)
    write_json(ROOT/'prepared/current_release.json',{'version':version,'data_directory':version,'app_index':f'app_{version}/cases.json',
        'manifest_sha256':digest(data/'manifest.json'),'app_manifest_sha256':digest(app/'manifest.json'),
        'status':'experimental_regional_terrain_and_historical_dry_barren_screening',
        'ndvi_policy':'complete_2001_2017_series_provisional_and_unscored','full_product_or_field_validation':False})
    print(f'Handoff verified: {len(folders)} manifests, four cases, twenty Earth footprints, all references and scientific flags.')
    return result


if __name__=='__main__':verify()

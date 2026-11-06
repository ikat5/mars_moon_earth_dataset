"""Prove that adding provisional NDVI context leaves screening and ranking unchanged."""
import json
from pathlib import Path
import duckdb
from processing.config import ROOT
from processing.prepare import digest,write_json,sql_path
from processing.enriched_release import verify_manifest
from processing.search import search


def verify():
    old=ROOT/'prepared/0.1.1';new=ROOT/'prepared/0.2.0'
    verify_manifest(old);verify_manifest(new)
    report={'baseline':'0.1.1','upgraded':'0.2.0','baseline_manifest_sha256':digest(old/'manifest.json'),
            'upgraded_manifest_sha256':digest(new/'manifest.json'),'scope':'NDVI is added as provisional context; existing Earth measurements, gates and terrain ranking parameters must remain unchanged.'}
    with duckdb.connect() as db:
        db.execute(f'CREATE VIEW a AS SELECT * FROM read_parquet({sql_path(old/"earth_features.parquet")})')
        db.execute(f'CREATE VIEW b AS SELECT * FROM read_parquet({sql_path(new/"earth_features.parquet")})')
        columns=[r[0] for r in db.execute('DESCRIBE a').fetchall()]
        assert db.execute('SELECT count(*) FROM (SELECT cell_id FROM a EXCEPT SELECT cell_id FROM b)').fetchone()[0]==0
        assert db.execute('SELECT count(*) FROM (SELECT cell_id FROM b EXCEPT SELECT cell_id FROM a)').fetchone()[0]==0
        differences={}
        for name in columns:
            if name=='vegetation_evidence_status':continue
            count=db.execute(f'SELECT count(*) FROM a JOIN b USING(cell_id) WHERE a."{name}" IS DISTINCT FROM b."{name}"').fetchone()[0]
            if count:differences[name]=count
        assert not differences,differences
        report['preserved_earth_columns_checked']=len(columns)-1
        report['changed_measurements_or_gates']=differences
        report['earth_rows']=db.execute('SELECT count(*) FROM b').fetchone()[0]
        report['ndvi_status']=db.execute('SELECT DISTINCT vegetation_evidence_status FROM b').fetchall()
        assert report['ndvi_status']==[('processed_provisional_2001_2017',)]
    for name in ['moon_features.parquet','mars_features.parquet','planetary_features.parquet']:
        assert digest(old/name)==digest(new/name),name
    report['planetary_files_bit_identical']=True
    a=json.loads((old/'profiles.json').read_text());b=json.loads((new/'profiles.json').read_text())
    keys=['eligibility_column','target_eligibility_column','earth_eligibility_column','features','required_features',
          'minimum_dem_valid_fraction','earth_target_area_ratio','minimum_fit','default_separation_km','earth_environment_rules']
    for profile in ['terrain_screening','dry_barren_terrain']:
        for key in keys:assert a['profiles'][profile].get(key)==b['profiles'][profile].get(key),(profile,key)
    report['ranking_and_eligibility_configuration_unchanged']=True
    cases=[{'body':'mars','lat':18.41,'lon':77.69},{'body':'moon','lat':0,'lon':0},
           {'body':'mars','lat':18.41,'lon':77.69,'origin':(24.89,91.87),'radius_km':500},
           {'body':'moon','lat':-89.67,'lon':129.78},{'body':'mars','lat':43.123,'lon':27.456}]
    checks=[]
    for spec in cases:
        previous=search(**spec,data_dir=old,profile='dry_barren_terrain')
        current=search(**spec,data_dir=new,profile='dry_barren_terrain')
        assert previous['status']==current['status']
        assert previous['target']==current['target']
        assert [(c['feature_id'],c['observed_fit']) for c in previous['candidates']]==[(c['feature_id'],c['observed_fit']) for c in current['candidates']]
        assert all(not c['vegetation_screened'] for c in current['candidates'])
        json.dumps(current,allow_nan=False)
        checks.append({'query':spec,'status':current['status'],'candidate_count':len(current['candidates']),'ids_and_scores_unchanged':True})
    report['query_checks']=checks;report['status']='passed'
    report['interpretation']='NDVI context does not improve the terrain score or verify analog suitability. This invariant check prevents provisional vegetation values from silently affecting recommendations.'
    write_json(ROOT/'analysis/release_upgrade_verification.json',report)
    print('Release upgrade verified: all prior measurements/gates preserved; five query results retain identical IDs and scores.')
    return report


if __name__=='__main__':verify()

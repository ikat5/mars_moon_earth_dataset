"""Publish immutable screening data; optional full NDVI remains unscored context."""
import argparse
import copy
from datetime import datetime,timezone
import json
from pathlib import Path
import shutil
import duckdb
import numpy as np
from processing.config import ROOT,DEFAULT_OUTPUT
from processing.environment import OUTPUT,ARIDITY_OUTPUT
from processing.environment_rules import RULES,FLAGS,environment_flags
from processing.prepare import digest,write_json,sql_path

VERSION='0.2.0'
DESTINATION=ROOT/'prepared'/VERSION


def verify_manifest(folder):
    manifest=json.loads((folder/'manifest.json').read_text())
    for name,item in manifest['files'].items():
        p=folder/name
        if p.stat().st_size!=item['bytes'] or digest(p)!=item['sha256']:
            raise ValueError(f'Corrupt prepared input: {p}')
    return manifest


def environment_definition(name,source,metadata):
    definition={'name':name,'body':'earth','dimensions':['environment','exploration'],
                'source':source,'measurement_type':'derived_context','categories':None,
                'period':metadata['period'],'native_resolution':metadata.get('source_grid',metadata.get('source_grids','See enrichment metadata')),
                'comparison_note':'Earth-only context or eligibility; never directly subtracted from a Moon/Mars value.'}
    if name.startswith('landcover_'):
        definition.update(units='fraction_of_target_cell_area',comparison_policy='earth_only_screening',
                          description='Spherical area fraction of strictly classified 2017 MODIS pixels.' if name.endswith('_class_fraction') else '2017 MODIS class/QC support fraction; see source metadata for the precise code policy.')
        if name=='landcover_labeled_area_coverage':definition['description']='Area carrying class 1–17 and QC 0–9, including unclassified and corrected labels; not strict screening coverage.'
        if name=='landcover_strict_area_coverage':definition['description']='Area carrying class 1–17 and QC 0 or 2 only.'
        if name=='landcover_modified_quality_fraction':definition['description']='Area carrying a valid class and corrected/backfilled QC code 4–9; excluded from strict class fractions.'
        if name=='landcover_unclassified_land_fraction':definition['description']='Area with QC=1, which can have a default barren label; excluded from strict barren fractions.'
    elif name.startswith('aridity_') or name.startswith('reference_et0_'):
        units='fraction_of_target_cell_area' if name.endswith('_area_coverage') else ('mm/year' if name.startswith('reference_et0') else 'dimensionless_precipitation_over_reference_ET0')
        definition.update(units=units,comparison_policy='earth_only_screening' if name.startswith('aridity') else 'unscored_context',
                          description='1970–2000 Global AI/ET0 v3 annual climatology, area-aggregated with documented scaling; coverage fields describe valid source support.')
    elif name.startswith('ndvi_'):
        units=('raw_storage_units' if name.endswith('_raw') else 'provisional_dimensionless_NDVI' if name.endswith('_provisional') else
               'months' if name.endswith('_count') else 'years' if name.endswith('_years') else 'fraction')
        definition.update(units=units,comparison_policy='provisional_context_not_screening',
                          description='2001–2017 monthly composite summary or support diagnostic; provisional 0.0001 scale and gap-filling caveats apply.',
                          scale_verification='inferred_not_provider_confirmed')
    else:raise ValueError(f'Undefined environment feature: {name}')
    return definition


def prepare(output=None,include_ndvi=True):
    version=VERSION if include_ndvi else '0.1.1'
    output=Path(output) if output is not None else ROOT/'prepared'/version
    if output.exists():raise FileExistsError(output)
    verify_manifest(DEFAULT_OUTPUT)
    sources={name:OUTPUT/name for name in ['landcover_2017','aridity']+(['ndvi'] if include_ndvi else [])}
    sources['aridity']=ARIDITY_OUTPUT
    metadata={}
    for name,folder in sources.items():
        verify_manifest(folder)
        metadata[name]=json.loads((folder/'metadata.json').read_text())
        assert metadata[name]['base_earth_sha256']==digest(DEFAULT_OUTPUT/'earth_features.parquet')
    if include_ndvi:assert metadata['ndvi']['expected_months']==204 and metadata['ndvi']['period']=='2001-2017'
    input_checks={}
    for name,filename in [('landcover_2017','landcover_verification.json'),('aridity','aridity_verification.json')]+([('ndvi','ndvi_verification.json')] if include_ndvi else []):
        path=ROOT/'analysis'/filename
        check=json.loads(path.read_text())
        assert check['status']=='passed' and all(c['status']=='passed' for c in check['checks'])
        checked_manifest=check.get('input_manifest_sha256',check.get('source_manifest_sha256'))
        assert checked_manifest==digest(sources[name]/'manifest.json'),f'Stale independent verification for {name}'
        if name=='ndvi':assert check['checked_months']==204
        input_checks[str(path.relative_to(ROOT))]=digest(path)
    stage=output.with_name(output.name+'.building');stage.mkdir(parents=True)
    registry=json.loads((DEFAULT_OUTPUT/'feature_registry.json').read_text())
    registry['version']=version
    profiles=json.loads((DEFAULT_OUTPUT/'profiles.json').read_text());profiles['version']=version
    provenance=json.loads((DEFAULT_OUTPUT/'provenance.json').read_text())
    provenance.update(version=version,created_utc=datetime.now(timezone.utc).isoformat(),
                      parent_release='prepared/0.1.0',enrichment=metadata,independent_input_checks=input_checks)
    provenance['release_code_sha256']={str(p.relative_to(ROOT)):digest(p) for p in [Path(__file__),ROOT/'processing/environment_rules.py',ROOT/'processing/search.py']}
    validation={'version':version,'ndvi_included':include_ndvi,'scope':'Source integrity, exact joins, unchanged parent measurements, explicit Earth screening. Not independent analog suitability validation.',
                'failures':[],'environment_flag_definitions':FLAGS}
    with duckdb.connect() as db:
        db.execute('SET threads=4')
        db.execute(f'CREATE VIEW base AS SELECT * FROM read_parquet({sql_path(DEFAULT_OUTPUT/"earth_features.parquet")})')
        new_names=[]
        for name,folder in sources.items():
            table='env_'+name
            db.execute(f'CREATE VIEW {table} AS SELECT * FROM read_parquet({sql_path(folder/"features.parquet")})')
            count,unique=db.execute(f'SELECT count(*),count(DISTINCT cell_id) FROM {table}').fetchone()
            basecount=db.execute('SELECT count(*) FROM base').fetchone()[0]
            assert count==unique==basecount
            assert db.execute(f'SELECT count(*) FROM (SELECT cell_id FROM base EXCEPT SELECT cell_id FROM {table})').fetchone()[0]==0
            for column,*_ in db.execute(f'DESCRIBE {table}').fetchall():
                if column=='cell_id':continue
                assert column not in new_names
                new_names.append(column)
                registry['bodies']['earth']['features'][column]=environment_definition(column,name,metadata[name])
        ndvi_select=',n.* EXCLUDE(cell_id)' if include_ndvi else ''
        ndvi_join=' JOIN env_ndvi n USING(cell_id)' if include_ndvi else ''
        db.execute(f'''CREATE VIEW joined AS SELECT b.*,l.* EXCLUDE(cell_id),a.* EXCLUDE(cell_id){ndvi_select}
                    FROM base b JOIN env_landcover_2017 l USING(cell_id)
                    JOIN env_aridity a USING(cell_id){ndvi_join}''')
        required=['cell_id','eligible_terrain','landcover_strict_area_coverage','landcover_barren_class_fraction',
                  'landcover_water_class_fraction','landcover_built_class_fraction','landcover_cropland_or_mosaic_class_fraction',
                  'aridity_index','aridity_index_area_coverage']
        arrays=db.execute(f'SELECT {",".join(required)} FROM joined ORDER BY cell_id').fetchnumpy()
        flags,environment_eligible=environment_flags(arrays)
        screening={'cell_id':arrays['cell_id'],'environment_flags':flags,
                   'environment_evidence_eligible':environment_eligible,
                   'eligible_dry_barren':environment_eligible & arrays['eligible_terrain']}
        db.register('screening',screening)
        vegetation_status='processed_provisional_2001_2017' if include_ndvi else 'not_included_full_series_pending'
        db.execute(f'''CREATE VIEW final AS SELECT j.* REPLACE(
            '{vegetation_status}' AS vegetation_evidence_status,
            'processed_historical_1970_2000' AS aridity_evidence_status),
            'processed_strict_classification_2017' AS landcover_evidence_status,
            s.* EXCLUDE(cell_id) FROM joined j JOIN screening s USING(cell_id)''')
        earth=stage/'earth_features.parquet'
        db.execute(f'COPY (SELECT * FROM final ORDER BY cell_id) TO {sql_path(earth)} (FORMAT PARQUET,COMPRESSION ZSTD,ROW_GROUP_SIZE 65536)')
        db.execute(f'CREATE VIEW exported AS SELECT * FROM read_parquet({sql_path(earth)})')
        names=[r[0] for r in db.execute('DESCRIBE base').fetchall() if r[0] not in ['vegetation_evidence_status','aridity_evidence_status']]
        differences=0
        for start in range(0,len(names),12):
            checks=' OR '.join(f'a."{n}" IS DISTINCT FROM b."{n}"' for n in names[start:start+12])
            differences+=db.execute(f'SELECT count(*) FROM base a JOIN exported b USING(cell_id) WHERE {checks}').fetchone()[0]
        assert differences==0
        count,unique,terrain,dry=db.execute('SELECT count(*),count(DISTINCT cell_id),count(*) FILTER(WHERE eligible_terrain),count(*) FILTER(WHERE eligible_dry_barren) FROM exported').fetchone()
        assert count==unique==basecount
        flag_counts={str(bit):int(((flags&bit)!=0).sum()) for bit in map(int,FLAGS)}
        validation.update(earth_rows=count,unique_earth_ids=unique,parent_measurement_changes=differences,
                          terrain_eligible_rows=terrain,dry_barren_eligible_rows=dry,environment_flag_counts=flag_counts,
                          joined_sidecars=list(sources),environment_rules=RULES,status='passed')
    for filename in ['moon_features.parquet','mars_features.parquet','planetary_features.parquet']:
        shutil.copy2(DEFAULT_OUTPUT/filename,stage/filename)
        assert digest(DEFAULT_OUTPUT/filename)==digest(stage/filename)
    baseline=profiles['profiles']['terrain_screening']
    baseline['limitations'].append('Selection resolves to an entire native cell. Small clicks across a cell boundary can change the compared region and ranking sharply; always display its footprint.')
    context=['landcover_strict_area_coverage','landcover_barren_class_fraction','landcover_water_class_fraction',
             'landcover_built_class_fraction','landcover_cropland_or_mosaic_class_fraction',
             'aridity_index','aridity_index_area_coverage']
    if include_ndvi:context.extend(['ndvi_mean_provisional','ndvi_peak_climatology_provisional','ndvi_valid_month_count','ndvi_gapfilled_area_time_fraction'])
    evidence={'landcover':{'period':'2017','source':metadata['landcover_2017']['source'],'license':metadata['landcover_2017']['license'],
                          'meaning':'Area classified as a land-cover class; not measured percent bare rock.'},
              'aridity':{'period':'1970-2000','source':metadata['aridity']['source'],'meaning':'Terrestrial climate screen only.'}}
    evidence['ndvi']=({'period':'2001-2017','source':metadata['ndvi']['source'],'scale_status':'provisional_not_used_in_gates',
                      'meaning':'Smoothed/gap-filled monthly composites, not current site observations.'} if include_ndvi else
                      {'status':'not_included_full_series_pending','used_in_gates':False})
    baseline['earth_context_features']=context;baseline['environment_evidence']=evidence
    dry=copy.deepcopy(baseline)
    dry.update(name='Dry, predominantly barren Earth terrain',
               purpose='Regional terrain exercises on Earth cells meeting explicit historical aridity and barren-class filters',
               target_eligibility_column='eligible_terrain',earth_eligibility_column='eligible_dry_barren',
               earth_environment_rules=RULES,land_cover_screened=True,aridity_screened=True)
    dry['limitations']=[s for s in dry['limitations'] if not s.startswith('Vegetation, land cover')]+[
        'Environmental thresholds are experimental screening choices; no success probability is estimated.',
        'Land cover and aridity are Earth-only filters from different historical periods, not additional similarity terms.',
        'Seasonal greenness, actual access, exposed mineralogy, boulders and mechanical strength remain unverified.',
        'NDVI scale is provisional; NDVI does not affect eligibility or rank.']
    profiles['profiles']['dry_barren_terrain']=dry
    registry['earth_environment_quality_flags']=FLAGS
    registry['earth_screening_rules']=RULES
    registry['earth_operational_fields']={
        'environment_flags':{'units':'bitmask','definition':'Reason codes in earth_environment_quality_flags; may overlap.'},
        'environment_evidence_eligible':{'units':'boolean','definition':'All declared Earth-only land-cover and aridity gates pass; does not include terrain or target area checks.'},
        'eligible_dry_barren':{'units':'boolean','definition':'Earth environment gates and inherited terrain eligibility both pass; target area/radius still apply at query time.'},
        'landcover_evidence_status':{'units':'category','definition':'Processing status and historical epoch, not classification confidence.'}}
    for filename,value in [('feature_registry.json',registry),('profiles.json',profiles),('provenance.json',provenance),('validation.json',validation)]:
        write_json(stage/filename,value)
    targets=json.loads((DEFAULT_OUTPUT/'targets.json').read_text());targets['version']=version;write_json(stage/'targets.json',targets)
    write_json(stage/'readiness.json',{'version':version,'full_product_complete':False,'status':'experimental_environment_screening',
        'scope':'Prepared regional screening data. The broader product roadmap and external scientific validation remain separate.',
        'completed':['three_body_verified_tables','global_landcover_and_aridity_context','Earth_only_screening_profile']+(['full_ndvi_series_provisional_scale'] if include_ndvi else []),
        'remaining':([] if include_ndvi else ['complete_full_NDVI_acquisition_and_processing'])+['verify_or_replace_NDVI_scale','broader_independent_and_field_validation','matched_physical_footprints_for_polar_queries',
                     'material_crosswalk_validation','temperature_sampling_harmonization','full_UI_integration_and_demo_validation']})
    write_json(stage/'manifest.json',{'version':version,'files':{p.name:{'bytes':p.stat().st_size,'sha256':digest(p)} for p in stage.iterdir() if p.is_file()}})
    stage.rename(output)
    print(f'Published {output}: {validation["dry_barren_eligible_rows"]:,} eligible dry/barren terrain cells',flush=True)
    return validation


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--screening-only',action='store_true',help='Publish 0.1.1 with complete land cover and aridity; explicitly omit the unscored NDVI series.')
    prepare(include_ndvi=not parser.parse_args().screening_only)

"""Evaluate predeclared external controls and neighboring-cell sensitivity."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import duckdb
import numpy as np
from processing.config import ROOT,CORE
from processing.enriched_release import DESTINATION,verify_manifest
from processing.environment_rules import FLAGS
from processing.search import cell_id_for_location,normalized_fit,resolve_target
from processing.prepare import digest,write_json


def evaluate(data_dir=DESTINATION):
    data_dir=Path(data_dir);verify_manifest(data_dir)
    control_path=ROOT/'analysis/control_sites.json'
    controls=json.loads(control_path.read_text())
    profiles=json.loads((data_dir/'profiles.json').read_text())
    profile=profiles['profiles']['dry_barren_terrain']
    provenance=json.loads((data_dir/'provenance.json').read_text())
    grid=provenance['bodies']['earth']['grid']
    features=list(profile['features'])
    weights=[profile['features'][f]['weight'] for f in features]
    tolerances=[profile['features'][f]['tolerance'] for f in features]
    output={'version':profiles['version'],'created_utc':datetime.now(timezone.utc).isoformat(),
            'controls_sha256':digest(control_path),'engine_sha256':digest(ROOT/'processing/search.py'),
            'scope':'Small predeclared sanity checks and a 3x3 cell-neighborhood diagnostic; not an accuracy estimate or representative validation sample.',
            'sites':[],'expectation_failures':[]}
    with duckdb.connect() as db:
        target,_=resolve_target(db,data_dir,'mars',18.41,77.69)
        target_values=[target[f] for f in features]
        for site in controls['sites']:
            cell=cell_id_for_location(site['lat'],site['lon'],grid)
            row_index,column_index=divmod(cell,grid['shape'][1])
            neighbor_ids=[r*grid['shape'][1]+(column_index+dc)%grid['shape'][1]
                          for r in range(max(0,row_index-1),min(grid['shape'][0],row_index+2)) for dc in [-1,0,1]]
            cur=db.execute('SELECT * FROM read_parquet(?) WHERE cell_id IN (SELECT unnest(?)) ORDER BY cell_id',
                           [str(data_dir/'earth_features.parquet'),neighbor_ids])
            names=[x[0] for x in cur.description]
            rows=[dict(zip(names,r)) for r in cur.fetchall()]
            selected=next((r for r in rows if r['cell_id']==cell),None)
            if selected is None:
                output['sites'].append({**site,'lookup_status':'outside_retained_Earth_grid'});continue
            records=[]
            for r in rows:
                reasons=[description for bit,description in FLAGS.items() if r['environment_flags']&int(bit)]
                fit=None
                if r['eligible_terrain']:
                    fit=float(normalized_fit([[r[f] for f in features]],target_values,weights,tolerances)[0][0])
                ratio=r['area_km2']/target['area_km2']
                area_ok=profile['earth_target_area_ratio'][0]<=ratio<=profile['earth_target_area_ratio'][1]
                status=('insufficient_environment_evidence' if r['environment_flags']&3 else
                        'fails_declared_environment_filters' if r['environment_flags'] else 'passes_environment_filters')
                keys=['cell_id','lat','lon','area_km2','quality_flags','eligible_terrain','eligible_dry_barren',
                      'environment_flags','landcover_strict_area_coverage','landcover_barren_class_fraction',
                      'landcover_forest_class_fraction','landcover_cropland_or_mosaic_class_fraction',
                      'landcover_unclassified_land_fraction','aridity_index','aridity_index_area_coverage',
                      'ndvi_mean_provisional','ndvi_valid_month_count',*CORE]
                records.append({**{key:r[key] for key in keys if key in r},'environment_status':status,'environment_reasons':reasons,
                                'jezero_terrain_fit':fit,'jezero_area_ratio':ratio,'jezero_area_filter_pass':area_ok,
                                'interpretation':'Cell context, not measurements at the site point.'})
            center=next(r for r in records if r['cell_id']==cell)
            expectation=site['expected_environment_screen']
            check=(center['environment_status']=='passes_environment_filters' if expectation.startswith('pass_is') else
                   center['environment_status']=='fails_declared_environment_filters' if expectation.startswith('reject_is') else
                   center['environment_status']=='insufficient_environment_evidence' if expectation.startswith('insufficient') else None)
            if check is False:output['expectation_failures'].append(site['id'])
            output['sites'].append({**site,'lookup_status':'ok','center_cell':center,'neighborhood':records,
                                   'expectation_observed':check,
                                   'neighbor_cells_passing_environment':sum(r['environment_status']=='passes_environment_filters' for r in records),
                                   'neighbor_cells_with_environment_evidence':sum(r['environment_status']!='insufficient_environment_evidence' for r in records)})
    output['status']='review_required' if output['expectation_failures'] else 'declared_checks_passed'
    output['remaining']='Independent finalist characterization, broader region holdouts, boundary/resolution experiments, and task relevance review.'
    destination=ROOT/'analysis'/f'control_evaluation_{profiles["version"]}.json'
    write_json(destination,output)
    print(f'Saved {destination}; status={output["status"]}')
    for s in output['sites']:
        print(s['id'],s.get('center_cell',{}).get('environment_status'),s.get('expectation_observed'))
    return output


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--data-dir',type=Path,default=DESTINATION)
    evaluate(parser.parse_args().data_dir)

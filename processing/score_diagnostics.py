"""Measure terrain-score selectivity across eligible Earth cells."""
import argparse
import json
from pathlib import Path
import duckdb
import numpy as np
from processing.config import ROOT
from processing.enriched_release import verify_manifest
from processing.prepare import digest, write_json
from processing.search import resolve_target, normalized_fit, sql_column


def analyze(data_dir=ROOT/'prepared/0.2.0'):
    data_dir=Path(data_dir).resolve();manifest=verify_manifest(data_dir)
    config=json.loads((data_dir/'profiles.json').read_text())['profiles']['dry_barren_terrain']
    features=list(config['features']);weights=[config['features'][f]['weight'] for f in features]
    tolerances=[config['features'][f]['tolerance'] for f in features]
    cases=[]
    with duckdb.connect() as db:
        for name,body,lat,lon in [('jezero','mars',18.41,77.69),('lunar_equatorial_coordinate','moon',0,0)]:
            row,target=resolve_target(db,data_dir,body,lat,lon)
            lo,hi=config['earth_target_area_ratio']
            values=db.execute(f'SELECT {",".join(map(sql_column,features))} FROM read_parquet(?) WHERE eligible_dry_barren AND area_km2 BETWEEN ? AND ?',
                [str(data_dir/'earth_features.parquet'),row['area_km2']*lo,row['area_km2']*hi]).fetchnumpy()
            scores,distances=normalized_fit(np.column_stack([values[f] for f in features]),[row[f] for f in features],weights,tolerances)
            cases.append({'id':name,'target':target,'eligible_after_environment_and_area':len(scores),
                'score_quantiles':dict(zip(['minimum','p10','median','p90','p95','p99','maximum'],
                                           np.quantile(scores,[0,.1,.5,.9,.95,.99,1]).tolist())),
                'cells_at_or_above_fit':{str(cut):int((scores>=cut).sum()) for cut in [50,90,95,99,99.5,99.7]},
                'mean_normalized_difference_by_feature':dict(zip(features,distances.mean(axis=0).tolist()))})
    result={'dataset_version':manifest['version'],'profile':'dry_barren_terrain',
        'manifest_sha256':digest(data_dir/'manifest.json'),'code_sha256':digest(__file__),'cases':cases,
        'scope':'Entire Earth pool after environment and target-area gates, before minimum-fit cutoff or geographic thinning; no travel radius.',
        'interpretation':'These are spatially correlated native cells. High-score counts describe selectivity under chosen tolerances, not independent sites, p-values, confidence or validated analog accuracy.'}
    output=ROOT/'analysis'/f'score_diagnostics_{manifest["version"]}.json';write_json(output,result)
    for case in cases:print(case['id'],case['eligible_after_environment_and_area'],case['cells_at_or_above_fit'])
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--data-dir',type=Path,default=ROOT/'prepared/0.2.0')
    analyze(parser.parse_args().data_dir)

"""Evaluate retrieval stability and integrity without claiming scientific ground truth."""
import json
import argparse
import statistics
import time
from pathlib import Path
import numpy as np
from processing.config import ROOT, DEFAULT_OUTPUT
from processing.prepare import digest, write_json
from processing.search import search, distances_km


def regional_overlap(reference, variant, threshold_km=100):
    """Maximum one-to-one matching within a declared geographic distance."""
    edges={i:[] for i in range(len(reference))}
    for i,a in enumerate(reference):
        for j,b in enumerate(variant):
            if distances_km(a['lat'],a['lon'],b['lat'],b['lon'])<=threshold_km:edges[i].append(j)
    matched={}
    def augment(i,visited):
        for j in edges[i]:
            if j in visited:continue
            visited.add(j)
            if j not in matched or augment(matched[j],visited):
                matched[j]=i;return True
        return False
    for i in edges:augment(i,set())
    return len(matched)/len(reference) if reference else None


def evaluate(data_dir=DEFAULT_OUTPUT,profile='terrain_screening',output_dir=None):
    data_dir=Path(data_dir)
    result_dir=Path(output_dir) if output_dir is not None else ROOT/'analysis'
    result_dir.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((data_dir/'manifest.json').read_text())
    failures=[]
    for name,meta in manifest['files'].items():
        p=data_dir/name
        if p.stat().st_size!=meta['bytes'] or digest(p)!=meta['sha256']:failures.append(name)
    assert not failures,failures
    variants={
        'balanced':None,
        'slope_emphasis':{'slope_median_deg':.35,'slope_p90_deg':.35,'relief_m':.15,'roughness_rms_m':.15},
        'amplitude_emphasis':{'slope_median_deg':.15,'slope_p90_deg':.15,'relief_m':.35,'roughness_rms_m':.35},
        'no_median_slope':{'slope_median_deg':0,'slope_p90_deg':.5,'relief_m':.25,'roughness_rms_m':.25},
        'no_relief':{'slope_median_deg':.25,'slope_p90_deg':.25,'relief_m':0,'roughness_rms_m':.5},
    }
    cases=[('jezero','mars',18.41,77.69,None,None),('lunar_equatorial_coordinate','moon',0,0,None,None),
           ('jezero_near_sylhet','mars',18.41,77.69,(24.89,91.87),500)]
    output={'dataset_version':manifest['version'],'profile':profile,'prepared_manifest_verified':True,
            'engine_sha256':digest(ROOT/'processing/search.py'),
            'interpretation':'Weight/feature sensitivity of experimental terrain retrieval. This is not analog accuracy, novelty or suitability validation.',
            'regional_matching_threshold_km':100,'cases':{},'timing_scope':'Sequential local diagnostic queries; includes prepared-file reads; excludes HTTP/frontend and concurrent load.'}
    timings=[]
    query_dir=result_dir/'queries';query_dir.mkdir(exist_ok=True)
    for label,body,lat,lon,origin,radius in cases:
        records={};baseline=None
        for name,weights in variants.items():
            r=search(body,lat,lon,data_dir=data_dir,profile=profile,origin=origin,radius_km=radius,weight_overrides=weights)
            timings.append(r['elapsed_seconds'])
            if baseline is None:baseline=r['candidates']
            exact=set(c['feature_id'] for c in baseline)&set(c['feature_id'] for c in r['candidates'])
            records[name]={'status':r['status'],'candidate_count':len(r['candidates']),
                           'exact_cell_retention':len(exact)/len(baseline) if baseline else None,
                           'regional_retention':regional_overlap(baseline,r['candidates']),
                           'candidate_ids':[c['feature_id'] for c in r['candidates']],
                           'elapsed_seconds':r['elapsed_seconds']}
            write_json(query_dir/f'{label}_{name}.json',r)
        output['cases'][label]=records
    output['timing_seconds']={'queries':len(timings),'median':statistics.median(timings),'max':max(timings),'p95':float(np.quantile(timings,.95))}
    output['remaining_validation']=['Independent candidate/site evidence','Vegetation and aridity controls','Source-scale/boundary sensitivity','Expert/task relevance','Concurrent web-service benchmark']
    write_json(result_dir/'retrieval_evaluation.json',output)
    print(json.dumps(output['timing_seconds']))
    for case,records in output['cases'].items():
        print(case,{k:None if v['regional_retention'] is None else round(v['regional_retention'],2) for k,v in records.items()})
    return output


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir',type=Path,default=DEFAULT_OUTPUT)
    parser.add_argument('--profile',default='terrain_screening')
    parser.add_argument('--output-dir',type=Path)
    args=parser.parse_args();evaluate(args.data_dir,args.profile,args.output_dir)

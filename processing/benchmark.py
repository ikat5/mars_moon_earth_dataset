"""Measure the prepared-data callable and JSON payload; excludes HTTP and UI."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import platform
import resource
import statistics
import time
import numpy as np
from processing.config import ROOT
from processing.enriched_release import verify_manifest
from processing.prepare import digest,write_json
from processing.search import search


def benchmark(data_dir=ROOT/'prepared/0.2.0'):
    data_dir=Path(data_dir).resolve();manifest=verify_manifest(data_dir)
    cases=[{'body':'mars','lat':18.41,'lon':77.69},
           {'body':'moon','lat':0,'lon':0},
           {'body':'mars','lat':43.123,'lon':27.456},
           {'body':'moon','lat':-17.42,'lon':138.13},
           {'body':'mars','lat':18.41,'lon':77.69,'origin':(24.89,91.87),'radius_km':500}]
    def query(spec):
        start=time.perf_counter()
        result=search(**spec,data_dir=data_dir,profile='dry_barren_terrain')
        payload=json.dumps(result,allow_nan=False,separators=(',',':')).encode()
        return {'query':spec,'elapsed_seconds':time.perf_counter()-start,'payload_bytes':len(payload),
                'status':result['status'],'candidate_count':len(result['candidates'])}
    warmup=query(cases[0])
    sequential=[query(spec) for spec in cases]
    started=time.perf_counter()
    with ThreadPoolExecutor(max_workers=10) as pool:concurrent=list(pool.map(query,cases*4))
    wall=time.perf_counter()-started
    def summary(results):
        durations=[r['elapsed_seconds'] for r in results]
        return {'queries':len(results),'median_seconds':statistics.median(durations),'p95_seconds':float(np.quantile(durations,.95)),
                'maximum_seconds':max(durations),'largest_payload_bytes':max(r['payload_bytes'] for r in results)}
    output={'dataset_version':manifest['version'],'created_utc':datetime.now(timezone.utc).isoformat(),
        'prepared_manifest_sha256':digest(data_dir/'manifest.json'),'engine_sha256':digest(ROOT/'processing/search.py'),
        'benchmark_code_sha256':digest(Path(__file__)),'profile':'dry_barren_terrain',
        'scope':'Prepared-data function plus compact JSON serialization. No HTTP transport, frontend, globe rendering, authentication or deployed-service load is included.',
        'conditions':'Files were fully read to verify manifests before measurement; one warm-up query was excluded. These are warm-process/cache diagnostics. Other dataset jobs may be active on the machine.',
        'machine':{'system':platform.system(),'architecture':platform.machine(),'python':platform.python_version(),
                   'logical_cpu_count':os.cpu_count(),'available_cpu_affinity_count':len(os.sched_getaffinity(0)) if hasattr(os,'sched_getaffinity') else None},
        'warmup_excluded':warmup,'sequential':{'summary':summary(sequential),'results':sequential},
        'concurrent':{'workers':10,'wall_seconds':wall,'summary':summary(concurrent),'results':concurrent},
        'process_peak_rss_mib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
        'memory_scope':'Linux process peak RSS across imports, manifest verification, warmup and both query runs; excludes other workers and browser memory.',
        'interpretation':'A backend diagnostic, not proof that the complete app meets the blueprint end-to-end performance target.'}
    destination=ROOT/'analysis'/f'benchmark_{manifest["version"]}.json'
    write_json(destination,output)
    print(json.dumps({'sequential':output['sequential']['summary'],'concurrent':output['concurrent']['summary'],'process_peak_rss_mib':output['process_peak_rss_mib']},indent=2))
    return output


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--data-dir',type=Path,default=ROOT/'prepared/0.2.0')
    benchmark(parser.parse_args().data_dir)

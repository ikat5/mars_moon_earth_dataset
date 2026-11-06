"""Run verified enrichment stages as ongoing source downloads finish.

This local worker does not acquire data or change existing prepared releases.
It writes an explicit progress record and stops on processing failures.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from processing.acquire import plan
from processing.config import ROOT
from processing.environment import OUTPUT, ARIDITY_OUTPUT, aridity, vegetation
from processing.landcover import prepare as landcover
from processing.prepare import digest, write_json


def verified_output(folder):
    manifest=folder/'manifest.json'
    if not manifest.exists():return False
    data=json.loads(manifest.read_text())
    for filename,record in data['files'].items():
        p=folder/filename
        if p.stat().st_size!=record['bytes'] or digest(p)!=record['sha256']:
            raise ValueError(f'Output checksum mismatch: {p}')
    return True


def finish(max_wait_hours=8):
    started=time.monotonic()
    paths=[ROOT/'sources'/item['folder']/item['name'] for item in plan()]
    ndvi=[p for p in paths if p.parent.name=='ndvi_2001_2017']
    ai=[p for p in paths if p.parent.name=='aridity_v3']
    stages={'landcover_2017':landcover,'aridity':aridity,'ndvi':vegetation}
    outputs={key:OUTPUT/key for key in stages};outputs['aridity']=ARIDITY_OUTPUT
    states={key:'complete' if verified_output(outputs[key]) else 'waiting_for_verified_downloads' for key in stages}
    status_path=ROOT/'analysis/enrichment_worker_status.json'
    while True:
        readiness={'landcover_2017':(ROOT/'sources/landcover_downloads.json').exists(),
                   'aridity':all(p.exists() for p in ai),'ndvi':all(p.exists() for p in ndvi)}
        state={'updated_utc':datetime.now(timezone.utc).isoformat(),'stages':states,
               'source_files_present':sum(p.exists() for p in paths),'source_files_expected':len(paths),
               'scientific_status':'Derived context; not external analog validation. NDVI scale remains provisional.',
               'worker_status':'running','elapsed_seconds':round(time.monotonic()-started,1)}
        write_json(status_path,state)
        for key,function in stages.items():
            if states[key]=='complete' or not readiness[key]:continue
            states[key]='processing';write_json(status_path,{**state,'stages':states})
            print(f'Starting {key}',flush=True)
            try:
                function()
                assert verified_output(outputs[key])
                states[key]='complete'
                print(f'Completed {key}',flush=True)
            except Exception as exc:
                states[key]='failed'
                write_json(status_path,{**state,'updated_utc':datetime.now(timezone.utc).isoformat(),
                           'worker_status':'failed','stages':states,'error':repr(exc),'failed_stage':key})
                raise
        if all(value=='complete' for value in states.values()):
            write_json(status_path,{**state,'updated_utc':datetime.now(timezone.utc).isoformat(),
                       'worker_status':'processing_complete','stages':states})
            print('All three enrichment stages processed and their manifests verified.',flush=True)
            return
        if time.monotonic()-started>max_wait_hours*3600:
            write_json(status_path,{**state,'worker_status':'source_wait_timeout','stages':states})
            raise TimeoutError('Source acquisition is incomplete; restart after inspecting download jobs.')
        time.sleep(20)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--max-wait-hours',type=float,default=8)
    args=parser.parse_args()
    if args.max_wait_hours<=0:parser.error('max wait must be positive')
    finish(args.max_wait_hours)

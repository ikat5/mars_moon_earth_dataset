"""Acquire pinned public enrichment files with publisher checksum verification.

Catalogs must already exist in sources/catalogs. Downloads are resumable by file;
verified completed files are reused. Partial files are retained and restarted on retry.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import time

import requests
from processing.config import ROOT
from processing.prepare import write_json, digest


def plan():
    catalogs = ROOT / "sources" / "catalogs"
    vegetation = json.loads((catalogs / "ndvi_4305975.json").read_text())
    aridity = json.loads((catalogs / "aridity_7504448_v5.json").read_text())
    selected = []
    for f in vegetation["files"]:
        name=f["key"]
        if name.startswith("veg_ndvi_"):
            year=int(name.split("s0..0cm_")[1][:4])
            if 2001 <= year <= 2017:
                selected.append({"name":name,"folder":"ndvi_2001_2017","url":f["links"]["self"],
                                 "bytes":f["size"],"md5":f["checksum"].split(":",1)[1],
                                 "source":"https://doi.org/10.5281/zenodo.4305975"})
    assert len(selected)==17*12*2, "Expected monthly vegetation and auxiliary QA for 17 complete years"
    for f in aridity["files"]:
        if f["name"] in ["Global-AI_ET0_annual_v3.zip", "Global-AI_PET_v3 - Readme.pdf"]:
            selected.append({"name":f["name"],"folder":"aridity_v3","url":f["download_url"],
                             "bytes":f["size"],"md5":f["computed_md5"],
                             "source":"https://doi.org/10.6084/m9.figshare.7504448.v5"})
    return sorted(selected,key=lambda f:(f["folder"],f["name"]))


def md5(path):
    with path.open("rb") as f:return hashlib.file_digest(f,"md5").hexdigest()


def download(item):
    root=ROOT / "sources" / item["folder"]
    root.mkdir(parents=True,exist_ok=True)
    name=item["name"]
    assert Path(name).name==name
    destination=root/name
    if destination.exists() and destination.stat().st_size==item["bytes"] and md5(destination)==item["md5"]:
        return {**item,"path":str(destination.relative_to(ROOT)),"sha256":digest(destination),"status":"verified_cached"}
    partial=destination.with_name(destination.name+".part")
    for attempt in range(4):
        try:
            with requests.get(item["url"],stream=True,timeout=(20,90)) as response:
                response.raise_for_status()
                with partial.open("wb") as handle:
                    for chunk in response.iter_content(1024*1024):
                        if chunk:handle.write(chunk)
            if partial.stat().st_size!=item["bytes"] or md5(partial)!=item["md5"]:
                raise ValueError(f"Publisher size/checksum mismatch: {name}")
            partial.replace(destination)
            return {**item,"path":str(destination.relative_to(ROOT)),"sha256":digest(destination),"status":"verified_download"}
        except (requests.RequestException,ValueError) as exc:
            if attempt==3:return {**item,"status":"failed","error":str(exc)}
            time.sleep(min(2**attempt,5))


def acquire(sample=False,workers=3):
    if not 1<=workers<=8:raise ValueError('Use between one and eight download workers')
    items=plan()
    if sample:
        items=[x for x in items if "20010101" in x["name"] or x["name"].endswith("Readme.pdf")]
    root=ROOT/"sources"
    write_json(root/"enrichment_plan.json",{"ndvi_period":[2001,2017],"aridity_period":[1970,2000],
               "temporal_caveat":"Separate historical products; not contemporaneous local testing conditions.",
               "file_count":len(items),"bytes":sum(x['bytes'] for x in items),"files":items})
    print(f"Fetching {len(items)} files, {sum(x['bytes'] for x in items)/1e9:.3f} GB",flush=True)
    manifest=[]
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures=[executor.submit(download,item) for item in items]
        for future in as_completed(futures):
            entry=future.result();manifest.append(entry)
            if len(manifest)%10==0 or entry['status']=='failed' or len(items)<10:
                print(f"Completed {len(manifest)}/{len(items)}; failures {sum(x['status']=='failed' for x in manifest)}",flush=True)
            write_json(root/("sample_downloads.json" if sample else "enrichment_downloads.json"),sorted(manifest,key=lambda x:(x['folder'],x['name'])))
    failed=[x for x in manifest if x['status']=='failed']
    print(f"Finished: {len(manifest)-len(failed)} verified, {len(failed)} failed",flush=True)
    if failed:raise RuntimeError("Some downloads failed; inspect download manifest and rerun to retry only unverified files.")


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sample',action='store_true')
    parser.add_argument('--plan-only',action='store_true')
    parser.add_argument('--workers',type=int,default=3,choices=range(1,9))
    args=parser.parse_args()
    if args.plan_only:
        items=plan();print(json.dumps({'files':len(items),'bytes':sum(x['bytes'] for x in items)},indent=2))
    else:acquire(args.sample,args.workers)

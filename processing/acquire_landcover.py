"""Acquire one documented MODIS land-cover year with its essential QC raster."""
from concurrent.futures import ThreadPoolExecutor
import json
from processing.config import ROOT
from processing.acquire import download
from processing.prepare import write_json


def acquire():
    catalog=json.loads((ROOT/'sources/catalogs/landcover_8367523.json').read_text())
    items=[]
    for f in catalog['files']:
        if '_20170101_' in f['key'] and any(x in f['key'] for x in ['mcd12q1v061.t1_','mcd12q1v061.qc_']):
            items.append({'name':f['key'],'folder':'landcover_2017','url':f['links']['self'],
                          'bytes':f['size'],'md5':f['checksum'].split(':')[-1],
                          'source':'https://doi.org/10.5281/zenodo.8367523'})
    assert len(items)==2
    write_json(ROOT/'sources/landcover_plan.json',items)
    print(f'Acquiring 2017 type-1 land cover and QC: {sum(x["bytes"] for x in items)/1e6:.1f} MB',flush=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        records=list(pool.map(download,items))
    write_json(ROOT/'sources/landcover_downloads.json',records)
    if any(x['status']=='failed' for x in records):raise RuntimeError('Land-cover acquisition incomplete')
    print('Two land-cover files verified against publisher checksums',flush=True)


if __name__=='__main__':acquire()

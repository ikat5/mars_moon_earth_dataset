"""Snapshot explicitly selected public catalogs without replacing prior records."""
import argparse
import requests
from processing.config import ROOT
from processing.prepare import write_json

CATALOGS={
    'landcover':('https://zenodo.org/api/records/8367523','landcover_8367523.json'),
}


def snapshot(name):
    url,filename=CATALOGS[name]
    path=ROOT/'sources/catalogs'/filename
    if path.exists():raise FileExistsError(path)
    response=requests.get(url,timeout=(20,90));response.raise_for_status()
    data=response.json()
    assert data['id']==int(filename.split('_')[-1].split('.')[0])
    write_json(path,data)
    print(f'Saved {path}')
    print('Files:',len(data.get('files',[])))
    for f in data.get('files',[]):
        if '20170101' in f['key'] or not f['key'].endswith('.tif'):
            print(f['key'],f['size'])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('name',choices=CATALOGS)
    snapshot(parser.parse_args().name)

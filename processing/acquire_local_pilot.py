"""Extract small public COG windows for a Sylhet-area scale diagnostic.

The selected window is an analysis extent, not a recommended or authorized field site.
"""
from datetime import datetime,timezone
import argparse
import math
import requests
import rasterio
from rasterio.windows import Window,from_bounds
from processing.config import ROOT
from processing.prepare import digest,write_json

FOLDER=ROOT/'sources/local_pilot'
BOUNDS=[92.005,25.14,92.035,25.17]
SOURCES={
    'worldcover_2021':{
        'url':'https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_N24E090_Map.tif',
        'documentation':'https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/docs/WorldCover_PUM_V2.0.pdf',
        'source':'ESA WorldCover 2021 v200, derived from Copernicus Sentinel-1 and Sentinel-2',
        'license':'CC BY 4.0','period':'2021','buffer_deg':0},
    'copernicus_dsm':{
        'url':'https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N25_00_E092_00_DEM/Copernicus_DSM_COG_10_N25_00_E092_00_DEM.tif',
        'documentation':'https://copernicus-dem-30m.s3.amazonaws.com/readme.html',
        'source':'Copernicus DEM GLO-30 public AWS COG; surface model including vegetation/buildings',
        'license':'Copernicus DEM GLO-30 license; retain provider attribution',
        'license_url':'https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Data/DEM/resources/license/License-COPDEM-30.pdf',
        'period':'TanDEM-X acquisition primarily 2011-2015; mosaic and edits may have other source epochs','buffer_deg':.003},
}


def acquire(bounds_requested=BOUNDS,folder=FOLDER,keys=None,sources=None,prefix='jaflong',location=None):
    folder.mkdir(parents=True,exist_ok=True)
    manifest=folder/'manifest.json'
    if manifest.exists():raise FileExistsError(manifest)
    records=[]
    for name,source in (SOURCES if sources is None else sources).items():
        if keys and name not in keys:continue
        destination=folder/f'{prefix}_{name}.tif'
        if destination.exists():raise FileExistsError(destination)
        response=requests.head(source['url'],timeout=(20,60));response.raise_for_status()
        headers={key:response.headers.get(key) for key in ['ETag','Last-Modified','Content-Length','Accept-Ranges']}
        with requests.get(source['url'],headers={'Range':'bytes=0-15'},stream=True,timeout=(20,60)) as check:
            if check.status_code!=206:raise RuntimeError('Source does not confirm HTTP range support; refusing an accidental full-tile download')
            assert len(check.raw.read(16))==16
        with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR',CPL_VSIL_CURL_ALLOWED_EXTENSIONS='.tif',GDAL_HTTP_TIMEOUT=60,GDAL_HTTP_MAX_RETRY=2):
            with rasterio.open(source['url']) as dataset:
                if dataset.crs.to_epsg()!=4326:raise ValueError('Expected geographic source')
                margin=source['buffer_deg']
                west,south,east,north=bounds_requested
                bounds=[west-margin,south-margin,east+margin,north+margin]
                window=from_bounds(*bounds,dataset.transform)
                col0,row0=math.floor(window.col_off),math.floor(window.row_off)
                col1,row1=math.ceil(window.col_off+window.width),math.ceil(window.row_off+window.height)
                if col0<0 or row0<0 or col1>dataset.width or row1>dataset.height:raise ValueError('Window crosses source tile')
                window=Window(col0,row0,col1-col0,row1-row0)
                data=dataset.read(window=window)
                transform=dataset.window_transform(window)
                profile={'driver':'GTiff','width':data.shape[2],'height':data.shape[1],'count':data.shape[0],
                         'dtype':data.dtype,'crs':dataset.crs,'transform':transform,'nodata':dataset.nodata,'compress':'deflate'}
                with rasterio.open(destination,'w',**profile) as exported:
                    exported.write(data)
                    exported.update_tags(source_url=source['url'],source_product=source['source'])
                original={'shape':dataset.shape,'transform':tuple(dataset.transform),'crs':str(dataset.crs),
                          'nodata':dataset.nodata,'source_window':[window.col_off,window.row_off,window.width,window.height]}
        with rasterio.open(destination) as exported:
            import numpy as np
            np.testing.assert_array_equal(exported.read(),data)
            assert exported.transform==transform
        records.append({**source,'key':name,'path':str(destination.relative_to(ROOT)),
                        'bytes':destination.stat().st_size,'sha256':digest(destination),'remote_headers':headers,
                        'original_grid':original,'checksum_scope':'Local extracted window only. Remote ETag retained; no whole-source checksum verification claimed.'})
        print(f'Extracted {name}: {destination.stat().st_size:,} local bytes',flush=True)
    write_json(manifest,{'created_utc':datetime.now(timezone.utc).isoformat(),'analysis_bounds':bounds_requested,
        **(location or {'selection':'Small exploratory window around the Jaflong landscape northeast of Sylhet; not a site boundary or permission to conduct field operations.',
        'location_evidence':'https://hims.bwdb.gov.bd/hydrology/includes/bm_pillar_sw_print.php?dist=&river=',
        'location_note':'BWDB lists Jaflong_Spill station at 25.156,92.018 inside this window; the window itself is analyst-selected.'}),
        'files':records,'worldcover_input_quality':'Not yet acquired; discrete classes must not be treated as local confidence scores.'})
    print('Saved local-pilot manifest')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--regional',action='store_true')
    if parser.parse_args().regional:
        acquire([92.,25.125,92.125,25.25],ROOT/'sources/local_pilot_regional',['worldcover_2021'])
    else:acquire()

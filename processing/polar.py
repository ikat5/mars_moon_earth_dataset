"""Acquire and characterize independent LOLA south-polar context products.

These 400 m-baseline plane-fit products cannot replace the original terrain
features: the definitions, raster spacing and footprints differ.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

import numpy as np
import rasterio
from pyproj import CRS, Transformer
import requests
from processing.config import ROOT
from processing.prepare import digest, write_json

FOLDER=ROOT/'sources'/'lola_polar_context'
PAGE='https://pgda.gsfc.nasa.gov/products/90'
PRODUCTS={
    'roughness_400m':('LDRM_80S_1000MPP_ADJ_ROUGH_400M.TIF','m','Spread of LOLA height residuals around a plane fit within a 400 m diameter window.'),
    'slope_400m':('LDRM_80S_1000MPP_ADJ_SLP_400M.TIF','degree','Slope of the fitted plane within a 400 m diameter window.'),
}


def acquire():
    FOLDER.mkdir(parents=True,exist_ok=True)
    records=[]
    for key,(name,units,definition) in PRODUCTS.items():
        url='https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/'+name
        p=FOLDER/name
        if not p.exists():
            partial=p.with_suffix('.TIF.part')
            with requests.get(url,stream=True,timeout=(20,90)) as response:
                response.raise_for_status()
                with partial.open('wb') as handle:
                    for chunk in response.iter_content(1024*1024):
                        if chunk:handle.write(chunk)
            with rasterio.open(partial) as ds:
                assert ds.count==1
            partial.replace(p)
        records.append({'key':key,'path':str(p.relative_to(ROOT)),'url':url,'source_page':PAGE,
                        'bytes':p.stat().st_size,'sha256':digest(p),'publisher_checksum':'not_provided',
                        'units':units,'definition':definition,'baseline_m':400,'raster_spacing_m':1000})
    write_json(FOLDER/'manifest.json',{'created_utc':datetime.now(timezone.utc).isoformat(),'files':records})
    print('Downloaded and locally hashed two NASA polar context products')


def characterize():
    manifest=json.loads((FOLDER/'manifest.json').read_text())
    # Named-feature center, not a proposed base, rim site or landing ellipse.
    lat,lon=-89.67,129.78
    radius_m=10000
    record={'target':'Shackleton center, 10 km planar context radius','lat':lat,'lon_east':lon,
            'coordinate_source':'https://planetarynames.wr.usgs.gov/Feature/5450',
            'reference_frame':'MOON_ME, JPL DE421; nominal named-feature coordinate used without epoch/frame adjustment',
            'radius_m':radius_m,'products':{},'matching_status':'context_only_not_admitted_to_score',
            'limitations':['Product footprint and 400 m plane-fit definition differ from integrated-table slope and RMS roughness.',
                           'A center-based circle mixes crater floor, walls and nearby terrain; it is not a rim-base footprint.',
                           'The circle is defined in the source polar projection. It is not an ellipsoidal geodesic buffer.',
                           'This supplement does not fill original missing terrain columns or enable unsupported matching.']}
    for source in manifest['files']:
        p=ROOT/source['path']
        assert digest(p)==source['sha256']
        with rasterio.open(p) as ds:
            projected=CRS.from_wkt(ds.crs.to_wkt())
            geographic=projected.geodetic_crs
            transform=Transformer.from_crs(geographic,projected,always_xy=True)
            x,y=transform.transform(lon,lat)
            data=ds.read(1,masked=True)
            xs=ds.transform.c+(np.arange(ds.width)+.5)*ds.transform.a
            ys=ds.transform.f+(np.arange(ds.height)+.5)*ds.transform.e
            inside=(ys[:,None]-y)**2+(xs[None,:]-x)**2<=radius_m**2
            valid=inside&~np.ma.getmaskarray(data)&np.isfinite(data.data)&(data.data>=0)
            values=data.data[valid]
            assert values.size
            row,col=ds.index(x,y)
            point=float(data[row,col]) if not np.ma.is_masked(data[row,col]) else None
            record['products'][source['key']]={**source,'crs_wkt':ds.crs.to_wkt(),
                'pixel_centers_in_circle':int(inside.sum()),'valid_pixels':int(values.size),
                'valid_center_fraction':float(values.size/inside.sum()),'center_containing_pixel_value':point,
                'minimum':float(values.min()),'median':float(np.median(values)),
                'p90':float(np.quantile(values,.9)),'maximum':float(values.max()),
                'aggregation':'Unweighted statistics of raster pixel centers inside projected circle; no claim of exact area coverage.'}
    output=ROOT/'analysis'/'shackleton_polar_context.json'
    write_json(output,record)
    print(f'Saved {output}')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download',action='store_true')
    args=parser.parse_args()
    if args.download:acquire()
    characterize()

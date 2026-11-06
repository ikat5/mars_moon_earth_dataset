"""Independent small-window checks against original raster pixels.

Uses direct pixel intersections, separate from the separable production reducer.
"""
import argparse
import json
import math
from pathlib import Path
import duckdb
import numpy as np
import rasterio
from rasterio.windows import Window,from_bounds
from processing.config import ROOT,DEFAULT_OUTPUT
from processing.environment import OUTPUT,ARIDITY_OUTPUT
from processing.landcover import GROUPS
from processing.prepare import digest,write_json
from processing.search import cell_id_for_location


def intersecting_pixels(dataset,bounds):
    west,south,east,north=bounds
    if east<=dataset.bounds.left or west>=dataset.bounds.right or north<=dataset.bounds.bottom or south>=dataset.bounds.top:
        return None,None,None
    window=from_bounds(west,south,east,north,dataset.transform)
    col0=max(0,math.floor(window.col_off));col1=min(dataset.width,math.ceil(window.col_off+window.width))
    row0=max(0,math.floor(window.row_off));row1=min(dataset.height,math.ceil(window.row_off+window.height))
    win=Window(col0,row0,col1-col0,row1-row0)
    data=dataset.read(1,window=win,masked=True)
    weights=np.zeros(data.shape)
    total=math.radians(east-west)*(math.sin(math.radians(north))-math.sin(math.radians(south)))
    for i in range(data.shape[0]):
        top=dataset.transform.f+(row0+i)*dataset.transform.e
        bottom=top+dataset.transform.e
        a,b=max(south,bottom),min(north,top)
        lat_area=max(0,math.sin(math.radians(b))-math.sin(math.radians(a)))
        for j in range(data.shape[1]):
            left=dataset.transform.c+(col0+j)*dataset.transform.a
            right=left+dataset.transform.a
            lon_width=max(0,min(east,right)-max(west,left))
            weights[i,j]=math.radians(lon_width)*lat_area/total
    return data,weights,win


def locations():
    controls=json.loads((ROOT/'analysis/control_sites.json').read_text())['sites']
    extra=[{'id':'gobi_candidate','lat':42.6875,'lon':102.4375},
           {'id':'high_greenness_candidate','lat':7.1875,'lon':80.0625}]
    provenance=json.loads((DEFAULT_OUTPUT/'provenance.json').read_text())
    grid=provenance['bodies']['earth']['grid']
    result=[]
    with duckdb.connect() as db:
        for site in controls+extra:
            cell=cell_id_for_location(site['lat'],site['lon'],grid)
            row=db.execute('SELECT west,south,east,north FROM read_parquet(?) WHERE cell_id=?',
                           [str(DEFAULT_OUTPUT/'earth_features.parquet'),cell]).fetchone()
            assert row is not None
            result.append({'id':site['id'],'cell_id':cell,'bounds':list(row)})
    return result


def verify_landcover():
    source_manifest=json.loads((ROOT/'sources/landcover_downloads.json').read_text())
    source_paths={('qc' if '.qc_' in r['name'] else 'lc'):ROOT/r['path'] for r in source_manifest}
    folder=OUTPUT/'landcover_2017'
    checks=[]
    with rasterio.open(source_paths['lc']) as lc,rasterio.open(source_paths['qc']) as qc,duckdb.connect() as db:
        for site in locations():
            classes,weights,win=intersecting_pixels(lc,site['bounds'])
            expected={f'landcover_{name}_class_fraction':None for name in GROUPS}
            expected.update(landcover_strict_area_coverage=0.,landcover_labeled_area_coverage=0.,
                            landcover_modified_quality_fraction=0.,landcover_unclassified_land_fraction=0.)
            if win is not None:
                quality=qc.read(1,window=win,masked=True)
                available=~np.ma.getmaskarray(classes)&~np.ma.getmaskarray(quality)
                labeled=available&(classes.data>=1)&(classes.data<=17)&(quality.data<=9)
                strict=labeled&np.isin(quality.data,[0,2])
                coverage=float(weights[strict].sum())
                expected.update(landcover_strict_area_coverage=coverage,
                                landcover_labeled_area_coverage=float(weights[labeled].sum()),
                                landcover_modified_quality_fraction=float(weights[labeled&(quality.data>=4)].sum()),
                                landcover_unclassified_land_fraction=float(weights[available&(quality.data==1)].sum()))
                if coverage>1e-12:
                    for name,codes in GROUPS.items():
                        expected[f'landcover_{name}_class_fraction']=float(weights[strict&np.isin(classes.data,codes)].sum())
            cur=db.execute('SELECT * FROM read_parquet(?) WHERE cell_id=?',[str(folder/'features.parquet'),site['cell_id']])
            actual=dict(zip([x[0] for x in cur.description],cur.fetchone()))
            errors=[]
            for field,value in expected.items():
                if value is None:
                    assert actual[field] is None,(site['id'],field,actual[field])
                else:
                    error=abs(actual[field]-value);errors.append(error)
                    assert error<1e-8,(site['id'],field,value,actual[field])
            checks.append({**site,'maximum_absolute_error':max(errors),'fractions':{k:actual[k] for k in expected},'status':'passed'})
    report={'kind':'landcover','method':'Independent direct spherical intersection per source pixel in six site/candidate windows.',
            'input_manifest_sha256':digest(folder/'manifest.json'),'checks':checks,'status':'passed',
            'scope':'Numerical/semantic aggregation verification; not a validation of the MODIS classification against field observations.'}
    write_json(ROOT/'analysis/landcover_verification.json',report)
    print('Six independent land-cover window checks passed.')
    return report


def verify_aridity():
    """Check independent pixel-window sums, including a background-only Earth cell."""
    folder=ARIDITY_OUTPUT
    sites=locations()
    sites.append({'id':'background_zero_regression','cell_id':148017,
                  'bounds':[-37.875,83.5,-37.75,83.625]})
    checks=[]
    with rasterio.open(ROOT/'sources/aridity_v3/extracted/ai_v3_yr.tif') as ai, \
         rasterio.open(ROOT/'sources/aridity_v3/extracted/et0_v3_yr.tif') as et,duckdb.connect() as db:
        for site in sites:
            raw,weights,win=intersecting_pixels(ai,site['bounds'])
            denominator=et.read(1,window=win,masked=True)
            valid=(~np.ma.getmaskarray(raw) & ~np.ma.getmaskarray(denominator)
                   & np.isfinite(raw.data) & (denominator.data>0))
            coverage=float(weights[valid].sum())
            expected=float((weights[valid]*raw.data[valid]).sum()/coverage*.0001) if coverage>1e-12 else None
            value,actual_coverage=db.execute('SELECT aridity_index,aridity_index_area_coverage FROM read_parquet(?) WHERE cell_id=?',
                                            [str(folder/'features.parquet'),site['cell_id']]).fetchone()
            assert abs(actual_coverage-coverage)<1e-8
            if expected is None:assert value is None
            else:assert abs(value-expected)<1e-8
            checks.append({**site,'aridity_index':value,'valid_area_coverage':actual_coverage,
                           'maximum_absolute_error':max(abs(actual_coverage-coverage),0 if expected is None else abs(value-expected)),
                           'status':'passed'})
        old=OUTPUT/'aridity/features.parquet'
        differences=db.execute('''SELECT count(*) FILTER(WHERE n.aridity_index_area_coverage<.95),
                    count(*) FILTER(WHERE n.aridity_index IS NULL),
                    count(*) FILTER(WHERE o.aridity_index IS DISTINCT FROM n.aridity_index)
                    FROM read_parquet(?) o JOIN read_parquet(?) n USING(cell_id)''',
                    [str(old),str(folder/'features.parquet')]).fetchone()
    report={'kind':'aridity','status':'passed','checks':checks,
            'method':'Independent direct source-pixel spherical intersections, with valid positive reference ET0 as support for AI.',
            'input_manifest_sha256':digest(folder/'manifest.json'),
            'superseded_output':'prepared/environment_0.1.0/aridity',
            'missing_support_correction':dict(zip(['cells_below_95pct_coverage','cells_without_valid_AI','cells_with_changed_AI_value'],differences)),
            'scope':'Numerical aggregation and missing-data semantics; not a field validation of historical climate.'}
    write_json(ROOT/'analysis/aridity_verification.json',report)
    print('Seven independent aridity window checks passed.')
    return report


def verify_ndvi(sample=False):
    """Independent spatial sums followed by per-site temporal reductions."""
    folder=OUTPUT/('ndvi_sample' if sample else 'ndvi')
    metadata=json.loads((folder/'metadata.json').read_text())
    records={r['name']:ROOT/r['path'] for r in metadata['sources']}
    names=sorted(name for name in records if '.gaps_' not in name)
    expected_months=1 if sample else 204
    assert len(names)==metadata['expected_months']==expected_months
    dates=[name.split('s0..0cm_')[1][:6] for name in names]
    assert len(set(dates))==len(dates)
    if not sample:assert dates==[f'{y}{m:02d}' for y in range(2001,2018) for m in range(1,13)]
    sites=locations();series={s['id']:[] for s in sites}
    for name,date in zip(names,dates):
        qa_name=name.replace('mod09ga_','mod09ga.gaps_')
        with rasterio.open(records[name]) as d,rasterio.open(records[qa_name]) as qa:
            for site in sites:
                values,weights,window=intersecting_pixels(d,site['bounds'])
                assert window is not None
                flags=qa.read(1,window=window)
                valid=(~np.ma.getmaskarray(values) & np.isin(flags,[1,2]) &
                       (values.data>=-10000) & (values.data<=10000))
                coverage=float(weights[valid].sum())
                gap_area=float(weights[valid&(flags==1)].sum())
                mean=float((values.data[valid]*weights[valid]).sum()/coverage) if coverage>1e-12 else None
                accepted=coverage>=.8 and mean is not None
                series[site['id']].append({'date':date,'mean_raw':mean,'coverage':coverage,'gap_area':gap_area,'accepted':accepted})
    checks=[]
    with duckdb.connect() as db:
        for site in sites:
            rows=series[site['id']];accepted=[r for r in rows if r['accepted']]
            climatology=[[r['mean_raw'] for r in accepted if int(r['date'][4:])==month] for month in range(1,13)]
            seasonal=[float(np.mean(v)) for v in climatology if v]
            mean=float(np.mean([r['mean_raw'] for r in accepted])) if accepted else None
            peak=max(seasonal) if len(seasonal)==12 else None
            minimum=min(seasonal) if len(seasonal)==12 else None
            total_coverage=sum(r['coverage'] for r in rows)
            expected={'ndvi_mean_raw':mean,'ndvi_peak_climatology_raw':peak,'ndvi_min_climatology_raw':minimum,
                'ndvi_mean_provisional':None if mean is None else mean*.0001,
                'ndvi_peak_climatology_provisional':None if peak is None else peak*.0001,
                'ndvi_min_climatology_provisional':None if minimum is None else minimum*.0001,
                'ndvi_valid_month_count':len(accepted),
                'ndvi_low_gapfill_month_count':sum(r['gap_area']<=.2*r['coverage'] for r in accepted),
                'ndvi_mean_area_coverage':total_coverage/expected_months,
                'ndvi_gapfilled_area_time_fraction':sum(r['gap_area'] for r in rows)/total_coverage if total_coverage>0 else None,
                'ndvi_min_calendar_month_years':min(map(len,climatology))}
            cur=db.execute('SELECT * EXCLUDE(cell_id) FROM read_parquet(?) WHERE cell_id=?',[str(folder/'features.parquet'),site['cell_id']])
            actual=dict(zip([x[0] for x in cur.description],cur.fetchone()))
            errors={}
            for key,value in expected.items():
                if value is None:assert actual[key] is None,(site['id'],key,actual[key])
                elif key.endswith('_count') or key.endswith('_years'):assert value==actual[key],(site['id'],key,value,actual[key])
                else:
                    errors[key]=abs(value-actual[key])
                    assert errors[key]<(1e-4 if key.endswith('_raw') else 1e-8),(site['id'],key,value,actual[key])
            checks.append({**site,'actual_features':actual,'absolute_errors':errors,'status':'passed'})
    report={'kind':'ndvi_sample' if sample else 'ndvi','status':'passed','period':metadata['period'],
        'checked_months':expected_months,'checks':checks,'source_manifest_sha256':digest(folder/'manifest.json'),
        'method':'Direct spherical source-pixel intersections at six independent control/candidate windows, then separate temporal means, calendar-month extrema, accepted counts and QA area-time reductions.',
        'tolerances':{'raw_units_absolute':1e-4,'fractions_or_provisional_units_absolute':1e-8,'counts':'exact'},
        'scope':'Verifies processing against source pixels, not the undocumented NDVI scale, provider gap-filling accuracy or field vegetation conditions.'}
    write_json(ROOT/'analysis'/f'{report["kind"]}_verification.json',report)
    print('Independent NDVI checks passed:',len(checks),'sites x',expected_months,'months')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('kind',choices=['landcover','aridity','ndvi']);parser.add_argument('--sample',action='store_true')
    args=parser.parse_args()
    if args.sample and args.kind!='ndvi':parser.error('--sample is NDVI-only')
    if args.kind=='ndvi':verify_ndvi(args.sample)
    else:(verify_landcover if args.kind=='landcover' else verify_aridity)()

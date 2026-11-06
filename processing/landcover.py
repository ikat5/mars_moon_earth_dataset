"""Quality-aware, area-weighted MODIS IGBP class fractions for Earth cells.

Fractions describe classified pixel area, not measured bare/vegetated area.
QC is a categorical code, not a bitmask. QC=1 barren defaults are excluded.
"""
import json
from pathlib import Path
import numpy as np
import rasterio
from rasterio.windows import Window
from processing.aggregate import GeographicAggregator
from processing.config import ROOT
from processing.environment import ids, publish, OUTPUT
from processing.prepare import digest
from processing.acquire import md5

GROUPS={
    'forest':list(range(1,6)),'shrub':[6,7],'savanna':[8,9],'grass':[10],
    'wetland':[11],'cropland_or_mosaic':[12,14],'built':[13],
    'snow_ice':[15],'barren':[16],'water':[17],
}
GUIDE='https://lpdaac.usgs.gov/documents/1409/MCD12_User_Guide_V61.pdf'


def class_fractions(lc_dataset, qc_dataset, target_shape=(1440,2880), block_rows=6, progress=False):
    lc,qc=lc_dataset,qc_dataset
    if lc.crs.to_epsg()!=4326 or lc.crs!=qc.crs or lc.shape!=qc.shape or lc.transform!=qc.transform:
        raise ValueError('Class and QC layers must have identical EPSG:4326 grids')
    if qc.nodata==0:
        raise ValueError('QC declares valid code zero as nodata; source semantics need investigation')
    ag=GeographicAggregator(lc.transform,lc.shape,target_shape)
    ir,wr=ag.rows;ic,wc=ag.columns
    output={f'landcover_{name}_class_fraction':np.zeros(target_shape) for name in GROUPS}
    extras=['strict_area_coverage','labeled_area_coverage','modified_quality_fraction','unclassified_land_fraction']
    output.update({f'landcover_{name}':np.zeros(target_shape) for name in extras})
    quality_counts={str(i):0 for i in range(11)}
    for start in range(0,target_shape[0],block_rows):
        stop=min(start+block_rows,target_shape[0]);indices,weights=ir[start:stop],wr[start:stop]
        active=indices[weights>0]
        if not active.size:continue
        first,last=int(active.min()),int(active.max())
        window=Window(0,lc.height-1-last,lc.width,last-first+1)
        classes,quality=lc.read(1,window=window,masked=True)[::-1],qc.read(1,window=window,masked=True)[::-1]
        known=(~np.ma.getmaskarray(classes))&(~np.ma.getmaskarray(quality))
        valid=known&(classes.data>=1)&(classes.data<=17)&(quality.data<=9)
        strict=valid&np.isin(quality.data,[0,2])
        positions=np.clip(indices-first,0,last-first)
        # Pixel counts below are diagnostic window reads and may double count
        # overlap rows. Area-fraction outputs do not double count target area.
        for flag in quality_counts:quality_counts[flag]+=int((known&(quality.data==int(flag))).sum())
        for name in output:
            if name=='landcover_strict_area_coverage':mask=strict
            elif name=='landcover_labeled_area_coverage':mask=valid
            elif name=='landcover_modified_quality_fraction':mask=valid&(quality.data>=4)
            elif name=='landcover_unclassified_land_fraction':mask=known&(quality.data==1)
            else:
                group=name.removeprefix('landcover_').removesuffix('_class_fraction')
                mask=strict&np.isin(classes.data,GROUPS[group])
            middle=np.zeros((stop-start,lc.width))
            for k in range(indices.shape[1]):middle+=mask[positions[:,k],:]*weights[:,k,None]
            out=np.zeros((stop-start,target_shape[1]))
            for k in range(ic.shape[1]):out+=middle[:,ic[:,k]]*wc[None,:,k]
            output[name][start:stop]=np.clip(out,0,1)
        if progress and start%120==0:print(f'Land cover aggregated latitude rows {stop}/{target_shape[0]}',flush=True)
    coverage=output['landcover_strict_area_coverage']
    total=sum(output[f'landcover_{name}_class_fraction'] for name in GROUPS)
    np.testing.assert_allclose(total,coverage,rtol=0,atol=2e-10)
    for name,values in output.items():
        if name.endswith('_class_fraction'):values[coverage<=1e-12]=np.nan
        output[name]=values[::-1].copy()
    return output,quality_counts


def prepare():
    folder=OUTPUT/'landcover_2017'
    if folder.exists():raise FileExistsError(folder)
    catalog=json.loads((ROOT/'sources/catalogs/landcover_8367523.json').read_text())
    records=json.loads((ROOT/'sources/landcover_downloads.json').read_text())
    paths={}
    for record in records:
        if record['status']=='failed':raise ValueError('Incomplete source acquisition')
        p=ROOT/record['path']
        if p.stat().st_size!=record['bytes'] or md5(p)!=record['md5'] or digest(p)!=record['sha256']:
            raise ValueError('Source checksum mismatch')
        paths['qc' if '.qc_' in record['name'] else 'lc']=p
    assert set(paths)=={'lc','qc'}
    with rasterio.open(paths['lc']) as lc,rasterio.open(paths['qc']) as qc:
        outputs,counts=class_fractions(lc,qc,progress=True)
        grid={'shape':lc.shape,'transform':tuple(lc.transform),'crs':str(lc.crs),
              'landcover_nodata':lc.nodata,'qc_nodata':qc.nodata,
              'actual_angular_resolution_deg':list(lc.res)}
    cell_ids=ids().astype(np.int64)
    columns={'cell_id':cell_ids,**{k:v.ravel()[cell_ids] for k,v in outputs.items()}}
    coverage=columns['landcover_strict_area_coverage']
    bare=columns['landcover_barren_class_fraction']
    report={'source':'https://doi.org/10.5281/zenodo.8367523','parent_source':'https://doi.org/10.5067/MODIS/MCD12Q1.061',
            'period':'2017','status':'processed_documented_classes','class_definitions_source':GUIDE,
            'source_grid':grid,'groups':GROUPS,'strict_qc_codes':[0,2],
            'strict_qc_rule':'Only classified land (0) and classified water (2); excluded corrected, backfilled, unclassified and nodata codes.',
            'qc_1_trap':'Unclassified land can carry barren class by default; it never contributes to barren fraction here.',
            'denominator':'Full spherical Earth target-cell area; class fractions sum to strict coverage where available.',
            'zero_vs_missing':'Absent class is zero only when some strict evidence exists. All class fractions are NULL at zero strict coverage.',
            'minimum_recommended_coverage':.95,'covered_cells_95pct':int((coverage>=.95).sum()),
            'barren_class_80pct_and_coverage95pct_cells':int(((coverage>=.95)&(bare>=.8)).sum()),
            'qa_window_read_counts':counts,'qa_count_caveat':'Source rows at processing block edges can be read twice; counts are diagnostic, not unique global source-pixel totals.',
            'landcover_code_sha256':digest(Path(__file__)),
            'caveats':['Fractions describe categorical pixels, not measured percentage of bare rock or vegetation.',
                       'Barren class includes sand, rock and soil; it does not establish mineralogy or mechanical properties.',
                       'Historical 2017 cover may differ from present field conditions.',
                       'Antarctica is excluded by the derivative source.',
                       'The source catalog has inconsistent nominal angular-resolution text; actual GeoTIFF transform is recorded.'],
            'license':catalog['metadata']['license'],
            'license_source':'sources/catalogs/landcover_8367523.json',
            'citation_policy':'Cite NASA parent and OpenGeoHub derivative; preserve the pinned derivative license.'}
    publish(folder,columns,report,records)


if __name__=='__main__':prepare()

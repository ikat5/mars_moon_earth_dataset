"""Acquire and characterize finer Earth context for one reproducible terrain candidate."""
import argparse
import copy
import json
from pathlib import Path
import duckdb
import numpy as np
import rasterio
from rasterio.features import geometry_mask
from rasterio.warp import calculate_default_transform,reproject,Resampling,transform_geom
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch
from processing.config import ROOT,DEFAULT_OUTPUT
from processing.prepare import write_json,digest
from processing.environment import OUTPUT,ARIDITY_OUTPUT
from processing.acquire_local_pilot import acquire,SOURCES
from processing.local_pilot import area_fractions,CLASS_NAMES,COLORS
from processing.search import polygon

CELL_ID=1090899
BOUNDS=[102.375,42.625,102.5,42.75]
SOURCE_FOLDER=ROOT/'sources/gobi_candidate'
DESTINATION=ROOT/'prepared/gobi_candidate_0.1.0'


def acquire_context():
    sources=copy.deepcopy(SOURCES)
    sources['worldcover_2021']['url']=sources['worldcover_2021']['url'].replace('N24E090','N42E102')
    sources['copernicus_dsm']['url']=sources['copernicus_dsm']['url'].replace('N25_00_E092_00','N42_00_E102_00')
    acquire(BOUNDS,SOURCE_FOLDER,sources=sources,prefix='gobi',location={
        'selection':'Earth cell 1090899 selected by the archived Jezero terrain query; footprint is a source cell, not an analog-site boundary.',
        'location_evidence':'analysis/queries/jezero_balanced.json',
        'location_note':'Center 42.6875 N, 102.4375 E. No administrative, protected-area or access determination is made.'})


def row_from_file(db,path):
    cursor=db.execute('SELECT * FROM read_parquet(?) WHERE cell_id=?',[str(path),CELL_ID])
    return dict(zip([x[0] for x in cursor.description],cursor.fetchone()))


def prepare():
    if DESTINATION.exists():raise FileExistsError(DESTINATION)
    source_manifest=json.loads((SOURCE_FOLDER/'manifest.json').read_text())
    for item in source_manifest['files']:assert digest(ROOT/item['path'])==item['sha256']
    paths={item['key']:ROOT/item['path'] for item in source_manifest['files']}
    with duckdb.connect() as db:
        original=row_from_file(db,DEFAULT_OUTPUT/'earth_features.parquet')
        landcover=row_from_file(db,OUTPUT/'landcover_2017/features.parquet')
        aridity=row_from_file(db,ARIDITY_OUTPUT/'features.parquet')
    geometry=polygon(original)
    query=json.loads((ROOT/'analysis/queries/jezero_balanced.json').read_text())
    candidate=next(x for x in query['candidates'] if x['feature_id']==f'earth:{CELL_ID}')
    fractions,coverage=area_fractions(paths['worldcover_2021'],BOUNDS)
    with rasterio.open(paths['worldcover_2021']) as d:
        lc=d.read(1);lc_transform=d.transform
    with rasterio.open(paths['copernicus_dsm']) as source:
        transform,width,height=calculate_default_transform(source.crs,'EPSG:32648',source.width,source.height,*source.bounds,resolution=30)
        dsm=np.full((height,width),np.nan,dtype=np.float32)
        reproject(source=rasterio.band(source,1),destination=dsm,src_transform=source.transform,src_crs=source.crs,
                  dst_transform=transform,dst_crs='EPSG:32648',dst_nodata=np.nan,resampling=Resampling.bilinear)
    dy,dx=np.gradient(dsm,30.,30.)
    slope=np.degrees(np.arctan(np.hypot(dx,dy)))
    roi=geometry_mask([transform_geom('EPSG:4326','EPSG:32648',geometry)],dsm.shape,transform,invert=True)
    valid=roi&np.isfinite(dsm)&np.isfinite(slope)
    assert valid.sum()>100
    stats={'surface_model_spacing_m':30,'pixel_center_coverage':float(valid.sum()/roi.sum()),'valid_pixel_count':int(valid.sum()),
           'median_slope_deg':float(np.median(slope[valid])),'p90_slope_deg':float(np.quantile(slope[valid],.9)),
           'p99_slope_deg':float(np.quantile(slope[valid],.99)),
           'slope_gt_5deg_fraction':float((slope[valid]>5).mean()),'slope_gt_10deg_fraction':float((slope[valid]>10).mean()),
           'surface_elevation_min_m':float(dsm[valid].min()),'surface_elevation_max_m':float(dsm[valid].max()),
           'surface_relief_m':float(np.ptp(dsm[valid]))}
    metadata={'status':'regional_dry_barren_terrain_candidate_with_finer_remote_sensing_context',
        'feature_id':f'earth:{CELL_ID}','center':{'lat':original['lat'],'lon':original['lon']},'bounds':BOUNDS,
        'source_cell_area_km2':original['area_km2'],'terrain_query':candidate,
        'earth_environment':{'landcover_2017':landcover,'aridity_1970_2000':aridity},
        'worldcover_2021':{'class_fractions':fractions,'classified_area_coverage':coverage,'class_names':CLASS_NAMES,
                          'qa_status':'InputQuality raster not acquired; class predictions are not local accuracy estimates.'},
        'surface_model_30m_context':stats,
        'terrain_method':'Copernicus DSM bilinearly reprojected to UTM 48N at 30 m; central finite-difference gradient; statistics at pixel centers inside original Earth cell.',
        'comparison_policy':'Finer Earth context is not inserted into the regional planetary score; source resolution, aggregation and slope definitions differ.',
        'mapped_geology_context':{k:original[k] for k in ['geo_unit','geo_class','geo_unit_frac']},
        'material_interpretation':'Mapped carbonate sedimentary context does not establish exposed patch material or mineralogical similarity to any Jezero unit.',
        'possible_experiment':'Investigate a dry exposed-land regional setting for route-planning and navigation exercises after local imagery and field review.',
        'experiment_outcome':'Compare planned and field-measured route lengths, slope distributions and localization drift at a subsequently surveyed local plot. No traction or hardware pass/fail prediction is made.',
        'planetary_limitations':['Earth gravity, atmosphere and radiation differ substantially.',
            'A Jezero center-cell terrain match is not a match to its delta, rover traverse or a particular lithologic unit.',
            'No boulder census, soil bearing strength, wheel slip, dust properties, ice or biological evidence is measured by these layers.'],
        'discovery_review':{'status':'novelty_not_established',
            'findings':'The Gobi already has published Mars-analog studies. This exact cell has not been established as new; a spatial known-site inventory and deeper literature review remain necessary.',
            'primary_sources':[
                {'url':'https://www.hou.usra.edu/meetings/terrestrialanalogs2021/pdf/8083.pdf','title':'Scuderi and Mason (2021), Gobi Desert Deltas as Analogs for Jezero Delta Mars','scope':'Prior Gobi-delta analog work; not evidence that this cell contains a delta or is the same study site.'},
                {'url':'https://doi.org/10.3390/min10090792','title':'2020 study, Hydrogeochemical Study on Closed-Basin Lakes in Cold and Semi-Arid Climates of the Valley of the Gobi Lakes','scope':'Prior Mongolian lake-system analog work; not a characterization of this selected cell.'}]},
        'jezero_geology_reference':{'url':'https://www.usgs.gov/publications/aqueously-altered-igneous-rocks-sampled-floor-jezero-crater-mars',
            'interpretation':'In-situ observations show igneous crater-floor units altered by water; a generic Earth carbonate label is not equivalent evidence.'},
        'current_condition_verified':False,'access_status':'not_assessed','field_validation':'not_performed',
        'limitations':['WorldCover 2021 and historical climate cannot establish present-day exposure or a suitable testing season.',
            'MODIS 2017 and WorldCover 2021 use different resolutions and class definitions; differences are not measured land-cover change.',
            'Copernicus is a surface model with multiple source epochs and editing; it cannot resolve wheel-contact obstacles.',
            'The absence of a class in a remote-sensing map is not proof that small water, vegetation or buildings are absent.',
            'No road, land tenure, protected-area, national-boundary or permission assessment has been made.'],
        'sources':source_manifest,'code_sha256':digest(Path(__file__)),
        'input_manifests':{str(p.relative_to(ROOT)):digest(p) for p in [DEFAULT_OUTPUT/'manifest.json',OUTPUT/'landcover_2017/manifest.json',ARIDITY_OUTPUT/'manifest.json']}}
    stage=DESTINATION.with_name(DESTINATION.name+'.building');stage.mkdir(parents=True)
    write_json(stage/'metadata.json',metadata)
    write_json(stage/'candidate.geojson',{'type':'FeatureCollection','features':[{'type':'Feature','id':f'earth:{CELL_ID}',
        'geometry':geometry,'properties':{'name':'Gobi regional terrain candidate','review_status':metadata['status'],
        'lat':original['lat'],'lon':original['lon'],'area_km2':original['area_km2'],'planetary_fit_scope':'four-term regional terrain resemblance only',
        'aridity_index':aridity['aridity_index'],'worldcover_bare_sparse_class_fraction':fractions['60'],
        'material_similarity_verified':False,'novelty_established':False,'access_status':'not_assessed'}}]})
    for name,data in [('dsm_utm30m',dsm),('slope_utm30m',slope)]:
        with rasterio.open(stage/f'{name}.tif','w',driver='GTiff',height=height,width=width,count=1,dtype='float32',
                           crs='EPSG:32648',transform=transform,nodata=np.nan,compress='deflate') as out:out.write(data.astype(np.float32),1)
    draw(stage,lc,lc_transform,slope,transform,valid,stats)
    write_json(stage/'manifest.json',{'files':{p.name:{'bytes':p.stat().st_size,'sha256':digest(p)} for p in stage.iterdir() if p.is_file()}})
    stage.rename(DESTINATION)
    print(f'Published {DESTINATION}',flush=True)
    print(json.dumps({'landcover':fractions,'terrain':stats},indent=2))


def draw(stage,lc,lc_transform,slope,transform,valid,stats):
    classes=sorted(CLASS_NAMES)
    indexed=np.full(lc.shape,np.nan)
    for i,c in enumerate(classes):indexed[lc==c]=i
    fig,axes=plt.subplots(1,3,figsize=(15,5.6),layout='constrained')
    extent=[lc_transform.c,lc_transform.c+lc.shape[1]*lc_transform.a,lc_transform.f+lc.shape[0]*lc_transform.e,lc_transform.f]
    axes[0].imshow(indexed,origin='upper',extent=extent,cmap=ListedColormap([COLORS[x] for x in classes]),vmin=0,vmax=len(classes)-1,interpolation='nearest')
    axes[0].set(title='WorldCover 2021: finer land-cover context',xlabel='Longitude (°E)',ylabel='Latitude (°N)',xlim=BOUNDS[::2],ylim=BOUNDS[1::2])
    axes[0].legend(handles=[Patch(facecolor=COLORS[c],label=CLASS_NAMES[c]) for c in classes if (lc==c).any()],loc='lower right',fontsize=8)
    masked=np.where(valid,slope,np.nan)
    extent=[transform.c/1000,(transform.c+slope.shape[1]*transform.a)/1000,(transform.f+slope.shape[0]*transform.e)/1000,transform.f/1000]
    im=axes[1].imshow(masked,extent=extent,origin='upper',cmap='magma',vmin=0,vmax=max(5,stats['p99_slope_deg']),interpolation='nearest')
    axes[1].set(title='30 m surface-model slopes',xlabel='UTM 48N easting (km)',ylabel='UTM 48N northing (km)')
    fig.colorbar(im,ax=axes[1],label='Slope (degrees)',fraction=.05)
    axes[2].hist(slope[valid],bins=60,density=True,color='#597e8b')
    axes[2].axvline(stats['median_slope_deg'],color='#bf5945',label=f"Median {stats['median_slope_deg']:.2f}°")
    axes[2].axvline(stats['p90_slope_deg'],color='#d6a23c',label=f"P90 {stats['p90_slope_deg']:.2f}°")
    axes[2].set(title='Distribution within the candidate cell',xlabel='30 m DSM-derived slope (degrees)',ylabel='Probability density (1/degree)')
    axes[2].legend(fontsize=9)
    fig.suptitle('Gobi candidate 42.6875°N, 102.4375°E — regional terrain resemblance, local evidence still unverified',fontsize=13)
    fig.supxlabel('Sources: ESA WorldCover 2021 and Copernicus DEM GLO-30. Finer slopes are context, not a planetary score or a traction prediction.',fontsize=9)
    fig.savefig(stage/'candidate_context.png',dpi=170)
    fig.savefig(stage/'candidate_context.pdf')
    plt.close(fig)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--download',action='store_true')
    if parser.parse_args().download:acquire_context()
    else:prepare()

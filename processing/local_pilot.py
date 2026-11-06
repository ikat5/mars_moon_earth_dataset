"""Characterize 10 m exposed-surface candidates with independent 30 m DSM context.

Patch candidates are not assigned planetary fit or field-readiness scores.
"""
import json
from pathlib import Path
import math
import numpy as np
import rasterio
from rasterio.features import shapes,rasterize
from rasterio.warp import calculate_default_transform,reproject,Resampling,transform_geom
from pyproj import Geod
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch
from processing.config import ROOT
from processing.prepare import digest,write_json
from processing.search import distances_km

VERSION='0.1.1'
FOLDER=ROOT/f'prepared/local_pilot_{VERSION}'
CLASS_NAMES={10:'Tree cover',20:'Shrubland',30:'Grassland',40:'Cropland',50:'Built-up',
             60:'Bare / sparse vegetation',70:'Snow / ice',80:'Water',90:'Herbaceous wetland',95:'Mangrove',100:'Moss / lichen'}
COLORS={10:'#276a3e',20:'#b1b74e',30:'#bdcb71',40:'#eadb8b',50:'#c45f58',60:'#b6a28d',
        70:'#eef5ff',80:'#498abb',90:'#64b9ba',95:'#42955c',100:'#ceb47d'}
GEOD=Geod(ellps='WGS84')


def polygon_area_perimeter(geometry):
    assert geometry['type']=='Polygon'
    area,perimeter=0.,0.
    for i,ring in enumerate(geometry['coordinates']):
        a,p=GEOD.polygon_area_perimeter([v[0] for v in ring],[v[1] for v in ring])
        area+=abs(a) if i==0 else -abs(a);perimeter+=p
    return area,perimeter


def area_fractions(path,bounds=None):
    with rasterio.open(path) as d:
        data=d.read(1)
        west,south,east,north=bounds or d.bounds
        x0=d.transform.c+np.arange(d.width)*d.transform.a
        y1=d.transform.f+np.arange(d.height)*d.transform.e
        x1=x0+d.transform.a;y0=y1+d.transform.e
        lon=np.radians(np.maximum(0,np.minimum(x1,east)-np.maximum(x0,west)))
        lat=np.maximum(0,np.sin(np.radians(np.minimum(y1,north)))-np.sin(np.radians(np.maximum(y0,south))))
        weights=lat[:,None]*lon[None,:]
        total=math.radians(east-west)*(math.sin(math.radians(north))-math.sin(math.radians(south)))
        fractions={str(k):float(weights[data==k].sum()/total) for k in CLASS_NAMES}
        assert 0<=sum(fractions.values())<=1+1e-10
        return fractions,float(sum(fractions.values()))


def near_water_pixels(water,transform,radius_m=30):
    """Pixel-center proximity using metric spacing at this small window's center."""
    center_lat=transform.f+(water.shape[0]/2)*transform.e
    dx=abs(GEOD.inv(transform.c,center_lat,transform.c+transform.a,center_lat)[2])
    dy=abs(GEOD.inv(transform.c,center_lat,transform.c,center_lat+transform.e)[2])
    pad=math.ceil(radius_m/min(dx,dy))
    padded=np.pad(water,pad,constant_values=False)
    nearby=np.zeros_like(water,dtype=bool)
    for row in range(-pad,pad+1):
        for col in range(-pad,pad+1):
            if math.hypot(row*dy,col*dx)<=radius_m:
                nearby |= padded[pad+row:pad+row+water.shape[0],pad+col:pad+col+water.shape[1]]
    return nearby


def prepare():
    if FOLDER.exists():raise FileExistsError(FOLDER)
    manifests={name:json.loads((ROOT/f'sources/{name}/manifest.json').read_text()) for name in ['local_pilot','local_pilot_regional']}
    for manifest in manifests.values():
        for record in manifest['files']:
            assert digest(ROOT/record['path'])==record['sha256']
    paths={r['key']:ROOT/r['path'] for r in manifests['local_pilot']['files']}
    regional=ROOT/manifests['local_pilot_regional']['files'][0]['path']
    stage=FOLDER.with_name(FOLDER.name+'.building');stage.mkdir(parents=True)
    with rasterio.open(paths['worldcover_2021']) as cover:
        lc=cover.read(1);transform=cover.transform;bounds=list(cover.bounds)
        assert set(np.unique(lc)).issubset({0,*CLASS_NAMES})
        raw=list(shapes((lc==60).astype(np.uint8),mask=lc==60,transform=transform,connectivity=4))
    water_near=near_water_pixels(lc==80,transform)
    with rasterio.open(paths['copernicus_dsm']) as source:
        dsm_transform,width,height=calculate_default_transform(source.crs,'EPSG:32646',source.width,source.height,*source.bounds,resolution=30)
        dsm=np.full((height,width),np.nan,dtype=np.float32)
        reproject(source=rasterio.band(source,1),destination=dsm,src_transform=source.transform,src_crs=source.crs,
                  dst_transform=dsm_transform,dst_crs='EPSG:32646',dst_nodata=np.nan,resampling=Resampling.bilinear)
    dy,dx=np.gradient(dsm,30.,30.)
    slope=np.degrees(np.arctan(np.hypot(dx,dy)))
    candidates=[]
    for geometry,value in raw:
        area,perimeter=polygon_area_perimeter(geometry)
        if area<5000:continue
        mask=rasterize([(geometry,1)],out_shape=lc.shape,transform=transform).astype(bool)
        ys,xs=np.nonzero(mask)
        assert np.all(lc[mask]==60)
        closest=np.argmin((ys-ys.mean())**2+(xs-xs.mean())**2)
        lon,lat=rasterio.transform.xy(transform,int(ys[closest]),int(xs[closest]))
        projected=transform_geom('EPSG:4326','EPSG:32646',geometry)
        terrain_mask=rasterize([(projected,1)],out_shape=dsm.shape,transform=dsm_transform).astype(bool)
        valid=terrain_mask&np.isfinite(dsm)&np.isfinite(slope)
        count=int(valid.sum());residual_rms=None
        zero_slope_fraction=float((slope[valid]<1e-7).mean()) if count else None
        near_water_fraction=float(water_near[mask].mean())
        hydrology_review=near_water_fraction>0 or (zero_slope_fraction is not None and zero_slope_fraction>.25)
        if count>=9:
            yy,xx=np.nonzero(valid)
            design=np.column_stack([(xx-xx.mean())*30,(yy-yy.mean())*30,np.ones(count)])
            coefficients,_,rank,_=np.linalg.lstsq(design,dsm[valid],rcond=None)
            if rank==3:residual_rms=float(np.sqrt(np.mean((dsm[valid]-design@coefficients)**2)))
        props={'area_m2':area,'perimeter_m':perimeter,'compactness_4piA_over_P2':4*math.pi*area/perimeter**2,
               'worldcover_class':60,'worldcover_class_name':CLASS_NAMES[60],'classification_year':2021,
               'worldcover_pixel_count':int(mask.sum()),'representative_point':{'lat':lat,'lon':lon},
               'touches_crop_boundary':bool(np.any((ys==0)|(ys==lc.shape[0]-1)|(xs==0)|(xs==lc.shape[1]-1))),
               'patch_pixel_fraction_within_30m_of_mapped_water':near_water_fraction,
               'straight_line_distance_from_illustrative_sylhet_origin_km':float(distances_km(24.89,91.87,lat,lon)),
               'dsm_30m_sample_count':count,'dsm_median_slope_deg':float(np.median(slope[valid])) if count else None,
               'dsm_p90_slope_deg':float(np.quantile(slope[valid],.9)) if count else None,
               'dsm_relief_m':float(np.ptp(dsm[valid])) if count else None,'dsm_plane_residual_rms_m':residual_rms,
               'dsm_zero_slope_fraction':zero_slope_fraction,
               'terrain_use_status':'requires_water_editing_review' if hydrology_review else 'unvalidated_surface_model_context',
               'review_status':'remote_sensing_candidate_unverified','planetary_fit':None,
               'physical_material_verified':False,'current_condition_verified':False,'access_status':'not_assessed'}
        candidates.append({'type':'Feature','geometry':geometry,'properties':props})
    candidates.sort(key=lambda x:-x['properties']['area_m2'])
    for i,feature in enumerate(candidates,1):
        feature['id']=f'jaflong:patch:{i}';feature['properties']['display_number']=i
    local_fractions,local_coverage=area_fractions(paths['worldcover_2021'])
    regional_fractions,regional_coverage=area_fractions(regional,manifests['local_pilot_regional']['analysis_bounds'])
    geojson={'type':'FeatureCollection','features':candidates}
    write_json(stage/'patch_candidates.geojson',geojson)
    # Source rasters remain separately hashed; these are derived context layers.
    for name,data in [('dsm_utm30m',dsm),('slope_utm30m',slope)]:
        with rasterio.open(stage/f'{name}.tif','w',driver='GTiff',height=height,width=width,count=1,dtype='float32',
                           crs='EPSG:32646',transform=dsm_transform,nodata=np.nan,compress='deflate') as out:out.write(data.astype(np.float32),1)
    metadata={'version':VERSION,'status':'local_remote_sensing_candidates_not_verified_analogs',
              'analysis_bounds':bounds,'requested_bounds':manifests['local_pilot']['analysis_bounds'],
              'regional_bounds':manifests['local_pilot_regional']['analysis_bounds'],
              'patch_count':len(candidates),'minimum_component_area_m2':5000,'connectivity':'four neighboring pixels',
              'local_landcover_class_fractions':local_fractions,'regional_landcover_class_fractions':regional_fractions,
              'local_classified_coverage':local_coverage,'regional_classified_coverage':regional_coverage,
              'class_names':CLASS_NAMES,'sources':manifests,'code_sha256':digest(Path(__file__)),
              'terrain_method':'Bilinear geographic DSM to UTM 46N at 30 m; central finite-difference gradient; statistics at pixel centers in each classified patch; least-squares plane residual only with >=9 valid samples and full rank.',
              'water_proximity_method':'WorldCover pixel centers within 30 m of mapped water using metric spacing at window center; water outside the retrieved crop is not assessed.',
              'hydrology_source':'https://dataspace.copernicus.eu/sites/default/files/media/files/2024-06/geo1988-copernicusdem-spe-002_producthandbook_i5.0.pdf',
              'hydrology_review_rule':'Flag when any patch pixels are within 30 m of mapped water or more than 25% of sampled DSM slopes are numerically zero. This flags a possible influence, not a causal diagnosis.',
              'comparison_policy':'30 m DSM features are local context. They are not substituted into the ~470 m planetary/terrestrial score or claimed to measure boulder roughness.',
              'regional_geology_evidence':{'source':'https://sparrso.gov.bd/sites/default/files/files/sparrso.portal.gov.bd/annual_reports/0b6f4c6e_9faf_48ac_a8f7_16dfb644815e/2022-03-09-08-39-75d87c64703469c15254710071319051.pdf',
                  'locator':'Geology Division, printed pages 28–29',
                  'summary':'SPARRSO describes gravelly sand and marsh clay/peat within the wider Jaflong region. This is regional context; individual patch materials have not been mapped or sampled here.'},
              'potential_use':'Investigate local exposed-surface patches for later navigation or traverse-planning field exercises, subject to current imagery and site review.',
              'limitations':['A 2021 class prediction is not confirmation of current exposed ground or operational suitability.',
                             'The WorldCover input-quality layer was not acquired; no per-patch confidence or accuracy percentage is claimed.',
                             'Bare/sparse class includes soil, sand, rocks, extraction sites and other surfaces; it does not imply regolith chemistry or strength.',
                             'River-adjacent terrain can change. Annual cover does not establish a safe or dry testing season.',
                             'The DSM includes vegetation and buildings and predates the 2021 land-cover map; source epochs differ.',
                             'Copernicus DSM includes water-body flattening and river editing. A zero or gentle DSM slope near water does not establish flat exposed ground.',
                             'Component polygons are clipped to the retrieved raster. Boundary-touching patches may continue beyond the analysis extent.',
                             'Averaged regional conditions can hide local patches. Both scales use the same WorldCover product/year in this diagnostic.',
                             'No current access, national boundary, tenure or field permission assessment has been made.',
                             'This site does not reproduce lunar vacuum/gravity or Martian atmosphere. No claim of a full Moon/Mars analog or novel discovery is made.']}
    write_json(stage/'metadata.json',metadata)
    draw(stage,lc,transform,candidates,slope,dsm_transform,local_fractions,regional_fractions)
    write_json(stage/'manifest.json',{'files':{p.name:{'bytes':p.stat().st_size,'sha256':digest(p)} for p in stage.iterdir() if p.is_file()}})
    stage.rename(FOLDER)
    print(f'Published {FOLDER}: {len(candidates)} classified patches >=0.5 ha',flush=True)
    print('Local/regional bare-class fractions:',local_fractions['60'],regional_fractions['60'])


def draw(stage,lc,transform,candidates,slope,dsm_transform,local,regional):
    labels=sorted(CLASS_NAMES)
    indexed=np.zeros(lc.shape)
    for i,code in enumerate(labels):indexed[lc==code]=i
    extent=[transform.c,transform.c+lc.shape[1]*transform.a,transform.f+lc.shape[0]*transform.e,transform.f]
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10})
    fig,axes=plt.subplots(1,3,figsize=(15,5.8),layout='constrained')
    axes[0].imshow(indexed,extent=extent,origin='upper',cmap=ListedColormap([COLORS[x] for x in labels]),vmin=0,vmax=len(labels)-1,interpolation='nearest')
    for feature in candidates[:8]:
        ring=np.asarray(feature['geometry']['coordinates'][0]);axes[0].plot(ring[:,0],ring[:,1],color='#202020',lw=.7)
        p=feature['properties']['representative_point'];axes[0].text(p['lon'],p['lat'],str(feature['properties']['display_number']),fontsize=8,ha='center',color='black',bbox=dict(facecolor='white',alpha=.8,edgecolor='none',pad=.5))
    axes[0].set(title='2021 land-cover classes and patch candidates',xlabel='Longitude (°E)',ylabel='Latitude (°N)')
    axes[0].ticklabel_format(style='plain',useOffset=False)
    present=[code for code in labels if np.any(lc==code)]
    axes[0].legend(handles=[Patch(color=COLORS[x],label=CLASS_NAMES[x]) for x in present],loc='upper right',fontsize=7,framealpha=.9)
    e=[dsm_transform.c/1000,(dsm_transform.c+slope.shape[1]*dsm_transform.a)/1000,
       (dsm_transform.f+slope.shape[0]*dsm_transform.e)/1000,dsm_transform.f/1000]
    img=axes[1].imshow(slope,extent=e,origin='upper',cmap='magma',vmin=0,vmax=10)
    axes[1].set(title='30 m surface-model slope (local context)',xlabel='UTM 46N easting (km)',ylabel='UTM northing (km)')
    fig.colorbar(img,ax=axes[1],label='Slope (degrees)',shrink=.75)
    keys=['10','30','40','50','60','80'];names=['Tree','Grass','Crop','Built','Bare / sparse','Water']
    y=np.arange(len(keys))
    axes[2].barh(y-.18,[regional[x]*100 for x in keys],height=.35,color='#8b9eac',label='Surrounding 0.125° cell')
    axes[2].barh(y+.18,[local[x]*100 for x in keys],height=.35,color='#b68a4b',label='Local window')
    axes[2].set_yticks(y,names);axes[2].set(xlabel='Classified area (%)',title='Same product and year, different footprints',xlim=(0,100));axes[2].legend(fontsize=8)
    fig.suptitle('TerraTwin local pilot: Jaflong landscape near Sylhet',fontsize=17,weight='bold')
    fig.supxlabel('Candidate polygons require site review. No planetary fit score is assigned. © ESA WorldCover 2021 / Contains modified Copernicus Sentinel data (2021). DSM: Copernicus GLO-30.',fontsize=9)
    fig.savefig(stage/'local_pilot.png',dpi=160);fig.savefig(stage/'local_pilot.pdf');plt.close(fig)


if __name__=='__main__':prepare()

"""Snapshot the public USGS portal inventory and review candidate proximity.

Catalog absence is never converted into a novelty claim or a similarity score.
"""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import requests
import numpy as np
from processing.config import ROOT
from processing.prepare import digest,write_json
from processing.search import distances_km

SOURCE=ROOT/'sources/known_analogs'
ENDPOINT='https://5j7x5wew8j.execute-api.us-west-2.amazonaws.com/prod/api/terrestrial-analog-sites'
PORTAL='https://tadp.astrogeology.usgs.gov/'
SCRIPT='https://tadp.astrogeology.usgs.gov/assets/index-CRhX0gaw.js'
PAAD_ENDPOINT='https://dservices.arcgis.com/v01gqwM5QqNysAAi/arcgis/services/Planetary_Aeolian_Analog_Database/WFSServer?service=wfs&request=GetFeature&typeNames=Planetary_Aeolian_Analog_Database_core_attributes&outputFormat=geojson'
PAAD_FOLDER=ROOT/'sources/known_analogs_paad'


def acquire():
    if (SOURCE/'manifest.json').exists():raise FileExistsError(SOURCE/'manifest.json')
    SOURCE.mkdir(parents=True,exist_ok=True)
    response=requests.get(ENDPOINT,timeout=(20,60));response.raise_for_status()
    wrapper=response.json()
    data=json.loads(wrapper['body']) if isinstance(wrapper.get('body'),str) else wrapper
    assert data['type']=='FeatureCollection' and len(data['features'])>0
    (SOURCE/'response.json').write_bytes(response.content)
    write_json(SOURCE/'sites.geojson',data)
    script=Path('/tmp/terratwin-tadp.js')
    assert script.exists() and ENDPOINT in script.read_text()
    (SOURCE/'portal_client.js').write_bytes(script.read_bytes())
    write_json(SOURCE/'manifest.json',{
        'retrieved_utc':datetime.now(timezone.utc).isoformat(),'source_url':ENDPOINT,
        'official_portal':PORTAL,'endpoint_discovered_in':SCRIPT,
        'related_data_release':'https://doi.org/10.5066/P9J72921',
        'version_scope':'Snapshot of the current portal feed; not verified byte-identical to the 2020 ScienceBase release. Direct ScienceBase catalog retrieval returned HTTP 403.',
        'rights_context':'USGS describes the related known-analog release as CC0 1.0 Universal. Retain individual record references and attribution.',
        'records':len(data['features']),'checksum_scope':'Local snapshot SHA-256; no publisher checksum supplied by this API response.',
        'files':{p.name:{'bytes':p.stat().st_size,'sha256':digest(p)} for p in SOURCE.iterdir() if p.is_file()}})
    print(f'Snapshotted {len(data["features"])} USGS portal analog features',flush=True)


def acquire_paad(import_path=None):
    if (PAAD_FOLDER/'manifest.json').exists():raise FileExistsError(PAAD_FOLDER/'manifest.json')
    if import_path is None:
        response=requests.get(PAAD_ENDPOINT,timeout=(20,60));response.raise_for_status();content=response.content
    else:content=Path(import_path).read_bytes()
    data=json.loads(content)
    assert data['type']=='FeatureCollection' and data['features']
    assert data['crs']['properties']['name']=='EPSG:4326'
    PAAD_FOLDER.mkdir(parents=True,exist_ok=True)
    (PAAD_FOLDER/'sites.geojson').write_bytes(content)
    write_json(PAAD_FOLDER/'manifest.json',{'retrieved_utc':datetime.now(timezone.utc).isoformat(),
        'source_url':PAAD_ENDPOINT,'endpoint_discovered_in':SCRIPT,'official_portal':PORTAL,
        'related_data_release':'https://doi.org/10.5066/P9IFVZEX','source_description':'USGS Planetary Aeolian Analog Database; dune-field analogs, not a comprehensive all-environment inventory.',
        'rights_context':'Related USGS release is marked CC0 1.0 Universal. Retain individual site references.',
        'records':len(data['features']),'source_crs':data['crs'],
        'acquisition_method':'Direct HTTP GET of public WFS feed' if import_path is None else 'Imported bytes from successful curl GET of this exact WFS URL in the current session.',
        'checksum_scope':'Local snapshot SHA-256; no publisher checksum was supplied.',
        'files':{'sites.geojson':{'bytes':len(content),'sha256':digest(PAAD_FOLDER/'sites.geojson')}}})
    print('Snapshotted PAAD records:',len(data['features']))


def review(paad=False):
    source=PAAD_FOLDER if paad else SOURCE
    manifest=json.loads((source/'manifest.json').read_text())
    for name,record in manifest['files'].items():assert digest(source/name)==record['sha256']
    raw=json.loads((source/'sites.geojson').read_text())
    sites=[];excluded=[]
    for i,feature in enumerate(raw['features']):
        geom=feature.get('geometry') or {}
        if geom.get('type')!='Point':
            excluded.append({'source_index':i,'reason':'not_Point'});continue
        lon,lat=geom['coordinates'][:2]
        if not np.isfinite([lat,lon]).all() or not(-90<=lat<=90 and -180<=lon<=180):
            excluded.append({'source_index':i,'reason':'invalid_geographic_coordinate'});continue
        props=feature.get('properties',{})
        coordinate_difference=None
        lat_attr=props.get('Center_L_1') if paad else props.get('Lat')
        lon_attr=props.get('Center_L_2') if paad else props.get('Lon')
        if isinstance(lat_attr,(int,float)) and isinstance(lon_attr,(int,float)):
            coordinate_difference=float(distances_km(lat,lon,lat_attr,lon_attr))
        sites.append({'source_index':i,'source_id':feature.get('id'),'lat':lat,'lon':lon,'properties':props,
                      'geometry_vs_attribute_coordinate_distance_km':coordinate_difference})
    assert sites,'No valid catalog points'
    queries=json.loads((ROOT/'analysis/evaluation_0.1.1/queries/jezero_balanced.json').read_text())['candidates']
    queries += [{'feature_id':'jaflong:window_center','lat':25.155,'lon':92.02}]
    result=[]
    for candidate in queries:
        distances=distances_km(candidate['lat'],candidate['lon'],np.array([s['lat'] for s in sites]),np.array([s['lon'] for s in sites]))
        order=np.argsort(distances,kind='stable')
        result.append({'candidate_id':candidate['feature_id'],'lat':candidate['lat'],'lon':candidate['lon'],
            'nearest_catalog_records':[{**sites[int(i)],'center_distance_km':float(distances[i])} for i in order[:3]],
            'records_within_25km':int((distances<=25).sum()),'records_within_100km':int((distances<=100).sum()),
            'novelty_established':False,'review_state':'limited_feed_checked_not_a_global_novelty_review'})
    output={'created_utc':datetime.now(timezone.utc).isoformat(),'source_manifest_sha256':digest(source/'manifest.json'),
            'source_url':manifest['source_url'],'portal':PORTAL,'total_records':len(raw['features']),'valid_point_records':len(sites),'excluded_records':excluded,
            'coordinate_policy':('PAAD feed explicitly declares EPSG:4326; geometry coordinates agree with numeric longitude/latitude attributes.' if paad else
                'Feed has no explicit CRS; coordinates interpreted using standard GeoJSON longitude/latitude. Geometry coordinates take precedence; attribute-coordinate disagreements are retained and measured.'),
            'catalog_completeness_status':('45 published dune-field records; useful for aeolian documentation context but not a comprehensive all-environment inventory.' if paad else
                'The current endpoint returns only four volcanic records. It is inadequate as a global inventory; do not use absence or large distances to claim novelty.'),
            'proximity_policy':'Great-circle point-to-point center distance on a 6371 km sphere; 25/100 km are review diagnostics, not site identity or novelty thresholds.',
            'limitations':['Catalog is not exhaustive and points may represent large or vaguely located regions.',
                'A nearby catalog point does not prove the candidate is the same field site; a distant one does not prove novelty.',
                'Catalog entries are prior-documentation context, not ground-truth analog labels for this target/profile.',
                'The source feed is snapshotted at retrieval time; no current site condition or access verification is implied.'],
            'candidates':result}
    if paad:assert all(s['geometry_vs_attribute_coordinate_distance_km'] is not None and s['geometry_vs_attribute_coordinate_distance_km']<.01 for s in sites)
    write_json(ROOT/('analysis/paad_review.json' if paad else 'analysis/known_analog_review.json'),output)
    print('Saved catalog proximity review for',len(result),'candidates')
    print('Source properties:',list(sites[0]['properties']))
    for r in result:print(r['candidate_id'],round(r['nearest_catalog_records'][0]['center_distance_km'],1),r['nearest_catalog_records'][0]['properties'].get('Field_Site' if paad else 'Name'))
    return output


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--download',action='store_true');parser.add_argument('--paad',action='store_true')
    parser.add_argument('--import-paad',type=Path)
    args=parser.parse_args()
    if args.import_paad:acquire_paad(args.import_paad)
    elif args.download:(acquire_paad if args.paad else acquire)()
    else:review(args.paad)

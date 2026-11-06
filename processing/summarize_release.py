"""Summarize the published release without reinterpreting missing evidence."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import duckdb
from processing.config import ROOT
from processing.enriched_release import verify_manifest
from processing.prepare import digest, write_json, sql_path


def summarize(data_dir=ROOT/'prepared/0.2.0'):
    data_dir=Path(data_dir).resolve();manifest=verify_manifest(data_dir)
    registry=json.loads((data_dir/'feature_registry.json').read_text())
    result={'dataset_version':manifest['version'],'created_utc':datetime.now(timezone.utc).isoformat(),
        'manifest_sha256':digest(data_dir/'manifest.json'),
        'release_bytes':sum(p.stat().st_size for p in data_dir.iterdir() if p.is_file()),
        'scope':'Counts of represented regional cells, not independent sites or validated analogs.', 'bodies':{}}
    with duckdb.connect() as db:
        for body in ['earth','moon','mars']:
            row=db.execute('SELECT count(*),count(*) FILTER(WHERE eligible_terrain) FROM read_parquet(?)',
                           [str(data_dir/f'{body}_features.parquet')]).fetchone()
            result['bodies'][body]={'rows':row[0],'terrain_eligible_rows':row[1],
                                  'registered_features':len(registry['bodies'][body]['features'])}
        db.execute(f'CREATE VIEW earth AS SELECT * FROM read_parquet({sql_path(data_dir/"earth_features.parquet")})')
        queries={
            'dry_barren_terrain_cells':'eligible_dry_barren',
            'landcover_strict_coverage_ge_095':'landcover_strict_area_coverage>=.95',
            'aridity_coverage_ge_095':'aridity_index_area_coverage>=.95',
            'ndvi_any_accepted_month':'ndvi_valid_month_count>0',
            'ndvi_all_204_months':'ndvi_valid_month_count=204',
            'ndvi_no_accepted_month':'ndvi_valid_month_count=0',
            'ndvi_all_calendar_months_represented':'ndvi_min_calendar_month_years>0',
            'ndvi_all_months_and_gapfilled_fraction_le_02':'ndvi_valid_month_count=204 AND ndvi_gapfilled_area_time_fraction<=.2',
            'dry_barren_with_all_ndvi_months':'eligible_dry_barren AND ndvi_valid_month_count=204',
            'south_of_60S_cells':'lat<-60',
            'south_of_60S_with_any_ndvi_month':'lat<-60 AND ndvi_valid_month_count>0',
        }
        result['earth_counts']={name:db.execute(f'SELECT count(*) FROM earth WHERE {where}').fetchone()[0]
                                for name,where in queries.items()}
        result['ndvi_accepted_month_histogram']=[{'accepted_months':n,'cells':count} for n,count in
            db.execute('SELECT ndvi_valid_month_count,count(*) FROM earth GROUP BY 1 ORDER BY 1').fetchall()]
        result['dry_barren_ndvi_support_histogram']=[{'accepted_months':n,'cells':count} for n,count in
            db.execute('SELECT ndvi_valid_month_count,count(*) FROM earth WHERE eligible_dry_barren GROUP BY 1 ORDER BY 1').fetchall()]
        result['ndvi_gapfill_quantiles_among_cells_with_any_accepted_month']=dict(zip(['p10','median','p90'],
            db.execute('SELECT quantile_cont(ndvi_gapfilled_area_time_fraction,[.1,.5,.9]) FROM earth WHERE ndvi_valid_month_count>0').fetchone()[0]))
        result['scientific_limits']=['NDVI scale is provisional and has no effect on rank or eligibility.',
            'QA fractions measure source support, not classification or analog accuracy.',
            'Land cover (2017), NDVI (2001–2017), and aridity (1970–2000) have different historical periods.',
            'Global grid cells are spatially correlated and have unequal physical areas.']
    output=ROOT/'analysis'/f'release_summary_{manifest["version"]}.json';write_json(output,result)
    print(json.dumps({k:result[k] for k in ['dataset_version','release_bytes','bodies','earth_counts']},indent=2))
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--data-dir',type=Path,default=ROOT/'prepared/0.2.0')
    summarize(parser.parse_args().data_dir)

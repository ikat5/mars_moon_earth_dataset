"""Prepare Earth environment sidecars after checksum-verified acquisition.

Outputs are immutable additions to the terrain release, not replacements for it.
NDVI scaled values remain provisional because the derivative's scale is undocumented.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import zipfile

import duckdb
import numpy as np
import rasterio
from processing.aggregate import GeographicAggregator, aggregate_raster_blocks
from processing.config import ROOT, DEFAULT_OUTPUT
from processing.acquire import plan, md5
from processing.prepare import digest, write_json, sql_path

OUTPUT = ROOT / "prepared" / "environment_0.1.0"
ARIDITY_OUTPUT = OUTPUT / "aridity_0.1.1"
NDVI_SOURCE = "https://doi.org/10.5281/zenodo.4305975"
ARIDITY_SOURCE = "https://doi.org/10.6084/m9.figshare.7504448.v5"


def verified_inputs(kind, sample=False):
    selected = [p for p in plan() if p["folder"].startswith(kind)]
    if sample and kind == "ndvi":
        selected = [p for p in selected if "20010101" in p["name"]]
    records = []
    for item in selected:
        p = ROOT / "sources" / item["folder"] / item["name"]
        if not p.is_file() or p.stat().st_size != item["bytes"]:
            raise FileNotFoundError(f"Acquisition incomplete: {p}")
        if md5(p) != item["md5"]:
            raise ValueError(f"Publisher checksum mismatch: {p}")
        records.append({**item,"path":str(p.relative_to(ROOT)),"sha256":digest(p)})
    return records


def ids():
    with duckdb.connect() as db:
        return db.execute("SELECT cell_id FROM read_parquet(?) ORDER BY cell_id",[str(DEFAULT_OUTPUT/"earth_features.parquet")]).fetchnumpy()["cell_id"]


def publish(folder, columns, report, records):
    folder = Path(folder)
    if folder.exists():
        raise FileExistsError(f"Immutable output already exists: {folder}")
    stage = folder.with_name(folder.name+".building")
    stage.mkdir(parents=True)
    with duckdb.connect() as db:
        db.register("features",columns)
        destination = stage/"features.parquet"
        db.execute(f"COPY features TO {sql_path(destination)} (FORMAT PARQUET, COMPRESSION ZSTD)")
        count, unique = db.execute("SELECT count(*),count(DISTINCT cell_id) FROM features").fetchone()
        assert count == unique == len(columns["cell_id"])
        exported = db.execute("SELECT * FROM read_parquet(?) ORDER BY cell_id",[str(destination)]).fetchnumpy()
        for key, value in columns.items():
            actual = exported[key]
            if np.ma.isMaskedArray(actual):actual = actual.astype(float).filled(np.nan)
            np.testing.assert_allclose(actual,value,equal_nan=True,rtol=0,atol=0)
    report.update({"created_utc":datetime.now(timezone.utc).isoformat(),"rows":count,
                   "base_release":"prepared/0.1.0","base_earth_sha256":digest(DEFAULT_OUTPUT/"earth_features.parquet"),
                   "aggregation":"Exact spherical overlap of piecewise-constant source pixels, with separate observed/modelled valid-area fraction.",
                   "sources":records,"software":{"numpy":np.__version__,"rasterio":rasterio.__version__,"duckdb":duckdb.__version__},
                   "code_sha256":{str(p.relative_to(ROOT)):digest(p) for p in [Path(__file__),ROOT/"processing/aggregate.py"]},
                   "output_invariants":"Unique original Earth cell IDs; row counts and all exported values verified."})
    write_json(stage/"metadata.json",report)
    write_json(stage/"manifest.json",{"files":{p.name:{"bytes":p.stat().st_size,"sha256":digest(p)} for p in stage.iterdir() if p.is_file()}})
    stage.rename(folder)
    print(f"Published {folder}: {count:,} cells",flush=True)


def vegetation(sample=False):
    output = OUTPUT/("ndvi_sample" if sample else "ndvi")
    if output.exists():raise FileExistsError(output)
    records = verified_inputs("ndvi", sample)
    files = {p["name"]:ROOT/p["path"] for p in records}
    names = sorted(name for name in files if ".gaps_" not in name)
    cell_ids = ids().astype(np.int64)
    n = len(cell_ids)
    sums = np.zeros((12,n),np.float64)
    counts = np.zeros((12,n),np.uint16)
    coverage_sum = np.zeros(n,np.float64)
    gap_sum = np.zeros(n,np.float64)
    valid_sum = np.zeros(n,np.float64)
    high_quality_count = np.zeros(n,np.uint16)
    source_ranges, invalid_count = [], 0
    ag, first_grid = None, None
    for i,name in enumerate(names):
        qa_name = name.replace("mod09ga_","mod09ga.gaps_")
        with rasterio.open(files[name]) as d, rasterio.open(files[qa_name]) as qa:
            grid = (tuple(d.transform),d.shape,str(d.crs))
            if d.crs.to_epsg()!=4326 or d.transform!=qa.transform or d.shape!=qa.shape:
                raise ValueError("Vegetation and QA grids must be the same geographic grid")
            if ag is None:
                ag = GeographicAggregator(d.transform,d.shape)
                first_grid = grid
            if grid != first_grid:raise ValueError("Monthly grid changed")
            data, flags = d.read(1,masked=True), qa.read(1)
            if not set(np.unique(flags)).issubset({0,1,2}):raise ValueError("Unknown vegetation QA code")
            valid = ~np.ma.getmaskarray(data) & np.isfinite(data.data) & np.isin(flags,[1,2])
            # Retain raw storage units. Out-of-physical-range values under the
            # explicitly provisional 1e-4 scale are excluded, counted and reported.
            in_range = (data.data>=-10000)&(data.data<=10000)
            invalid_count += int((valid&~in_range).sum())
            valid &= in_range
            raw = data.data
            if valid.any():source_ranges.append([int(raw[valid].min()),int(raw[valid].max())])
            mean, coverage = ag.mean(raw,valid)
            gap_area = ag.weighted_sum((valid & (flags==1)).astype(np.float32))
        mean, coverage, gap_area = [x.ravel()[cell_ids] for x in (mean,coverage,gap_area)]
        month = int(name.split("s0..0cm_")[1][4:6])-1
        accept = (coverage >= .8)&np.isfinite(mean)
        sums[month,accept] += mean[accept]
        counts[month,accept] += 1
        coverage_sum += coverage
        gap_sum += gap_area
        valid_sum += coverage
        high_quality_count += (accept & (gap_area <= .2*coverage)).astype(np.uint16)
        if (i+1)%12==0 or sample:print(f"Vegetation aggregated {i+1}/{len(names)} months",flush=True)
    total = counts.sum(axis=0)
    annual = np.full(n,np.nan)
    np.divide(sums.sum(axis=0),total,out=annual,where=total>0)
    monthly = np.full_like(sums,np.nan)
    np.divide(sums,counts,out=monthly,where=counts>0)
    all_seasons = (counts>0).all(axis=0)
    peak, minimum = np.full(n,np.nan),np.full(n,np.nan)
    peak[all_seasons],minimum[all_seasons] = monthly[:,all_seasons].max(axis=0),monthly[:,all_seasons].min(axis=0)
    gap_fraction=np.full(n,np.nan)
    np.divide(gap_sum,valid_sum,out=gap_fraction,where=valid_sum>0)
    columns = {"cell_id":cell_ids,"ndvi_mean_raw":annual,"ndvi_peak_climatology_raw":peak,
               "ndvi_min_climatology_raw":minimum,"ndvi_mean_provisional":annual*.0001,
               "ndvi_peak_climatology_provisional":peak*.0001,"ndvi_min_climatology_provisional":minimum*.0001,
               "ndvi_valid_month_count":total.astype(np.uint16),"ndvi_low_gapfill_month_count":high_quality_count,
               "ndvi_mean_area_coverage":coverage_sum/len(names),"ndvi_gapfilled_area_time_fraction":gap_fraction,
               "ndvi_min_calendar_month_years":counts.min(axis=0)}
    report={"source":NDVI_SOURCE,"period":"2001-01 only" if sample else "2001-2017",
            "status":"sample_diagnostic" if sample else "processed_provisional_scale",
            "expected_months":len(names),"minimum_monthly_area_coverage":.8,
            "low_gapfill_definition":"Accepted month has gap-filled area <=20% of its valid area.",
            "raw_scale":1,"provisional_scale":.0001,"scale_verification":"inferred_not_confirmed_by_derivative_provider",
            "scale_evidence":["Derivative raw range is consistent with NDVI multiplied by 10,000; not sufficient independent confirmation.",
                              "Referenced NOAA CDR parent documents 0.0001 scaling; derivative GeoTIFF reports identity scale.",
                              "https://developers.google.com/earth-engine/datasets/catalog/NOAA_CDR_AVHRR_NDVI_V5"],
            "scoring_policy":"Do not enable a definitive low-vegetation gate until derivative scale is verified; raw and provisional values are diagnostic context.",
            "processing":"Average accepted monthly p90 composite means with equal month weight. Peak/min are extrema of the 12 calendar-month climatologies, not daily extrema.",
            "qa_values":{"0":"disregarded","1":"gap-filled","2":"smoothed; not an unsmoothed observation"},
            "source_grid":first_grid,"source_raw_ranges":source_ranges,"rejected_out_of_range_pixels":invalid_count,
            "cells_with_any_month":int((total>0).sum()),"cells_with_complete_months":int((total==len(names)).sum()),
            "caveats":["Low greenness does not prove bare rock, absence of biology, or safe access.",
                       "Historical climatology does not describe current site conditions.",
                       "Area fraction describes pixel support; it is not measurement accuracy.",
                       "All source values have been smoothed or gap-filled by the provider."],"license":"CC BY 4.0"}
    publish(output,columns,report,records)


def aridity():
    output = ARIDITY_OUTPUT
    if output.exists():raise FileExistsError(output)
    records=verified_inputs("aridity")
    archive=next(ROOT/p['path'] for p in records if p['name'].endswith('.zip'))
    folder=archive.parent/"extracted"
    folder.mkdir(exist_ok=True)
    rasters={}
    with zipfile.ZipFile(archive) as z:
        for basename in ("ai_v3_yr.tif","et0_v3_yr.tif"):
            candidates=[name for name in z.namelist() if Path(name).name.lower()==basename]
            if len(candidates)!=1:raise ValueError(f"Expected one {basename}; archive contains {z.namelist()}")
            target=folder/basename
            info=z.getinfo(candidates[0])
            if not target.exists() or target.stat().st_size!=info.file_size:
                import shutil
                with z.open(candidates[0]) as source, target.open('wb') as destination:shutil.copyfileobj(source,destination)
            rasters[basename]=target
    cell_ids=ids().astype(np.int64)
    columns={"cell_id":cell_ids}
    grid_info={}
    for basename,name,scale in [("ai_v3_yr.tif","aridity_index",.0001),("et0_v3_yr.tif","reference_et0_mm_yr",1.)]:
        with rasterio.open(rasters[basename]) as d:
            if name=="aridity_index":
                with rasterio.open(rasters["et0_v3_yr.tif"]) as support:
                    values,coverage=aggregate_raster_blocks(d,positive_support=support)
            else:
                values,coverage=aggregate_raster_blocks(d)
            grid_info[name]={"shape":d.shape,"transform":tuple(d.transform),"crs":str(d.crs),"nodata":d.nodata,"storage_dtype":d.dtypes[0]}
        columns[name]=values.ravel()[cell_ids]*scale
        columns[name+"_area_coverage"]=coverage.ravel()[cell_ids]
        print(f"Aggregated {name}",flush=True)
    accepted=(columns['aridity_index_area_coverage']>=.95)&np.isfinite(columns['aridity_index'])
    report={"source":ARIDITY_SOURCE,"period":"1970-2000","status":"processed_documented_scale","processing_version":"0.1.1",
            "validity_policy":"AI must have finite nonnegative storage and finite, unmasked, positive ET0 at the corresponding pixel. AI alone has no nodata tag and zero includes both hyperarid land and ocean background. Valid dry zero is retained; undefined support is excluded.",
            "support_grid_alignment":"Same dimensions, CRS and pixel indices; transform coefficients agree within 1e-7 degrees (origins differ by approximately 1.4e-8 degrees).",
            "supersedes":"prepared/environment_0.1.0/aridity — incorrectly treated all AI background pixels as observed support; do not use that sidecar for screening.",
            "definition":"Annual precipitation divided by annual FAO56 Penman-Monteith reference evapotranspiration; smaller is drier.",
            "aridity_storage_scale":.0001,"et0_units":"mm/year","source_grids":grid_info,
            "eligible_95pct_coverage_cells":int(accepted.sum()),
            "arid_cells_ai_le_0_2_95pct_coverage":int((accepted&(columns['aridity_index']<=.2)).sum()),
            "license_metadata":"CC BY 4.0","license_readme_and_description":"Non-commercial use; commercial permission requested by provider.",
            "license_status":"Conflicting provider statements preserved; no commercial clearance inferred.",
            "caveats":["Historical terrestrial climate index, not a direct Moon/Mars measurement.",
                       "Unsigned 16-bit AI has a finite storage ceiling; upper-end values must not be interpreted as uncensored humidity estimates. This does not affect the <=0.2 arid screen.",
                       "Screen Earth climate separately from terrain fit; not a planetary similarity score.",
                       "Low aridity index alone does not establish bare ground, geological similarity or field suitability."]}
    publish(output,columns,report,records)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kind',choices=['ndvi','aridity'])
    parser.add_argument('--sample',action='store_true')
    args=parser.parse_args()
    if args.kind=='aridity':
        if args.sample:parser.error('--sample is only available for NDVI')
        aridity()
    else:vegetation(args.sample)

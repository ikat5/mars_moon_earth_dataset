"""Build immutable, verified comparison assets from local integrated tables.

Run: python -m processing.prepare [--output prepared/VERSION]
"""
import argparse
import hashlib
import json
import math
import os
import platform
import shutil
from datetime import datetime, timezone
from pathlib import Path

import duckdb
from processing.config import ROOT, VERSION, DEFAULT_OUTPUT, CORE, QC_FLAGS, PROFILES, comparison_policy


def digest(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def sql_path(path):
    return "'" + str(path).replace("'", "''") + "'"


def prepare(output=DEFAULT_OUTPUT):
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError(f"Refusing to replace versioned output: {output}; choose a new output path.")
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = output.with_name(output.name + ".building")
    staging.mkdir()  # Existing failed staging is retained for inspection, never silently reused.
    db = duckdb.connect()
    db.execute("SET threads=4")
    registry = {"version": VERSION, "bodies": {}, "spatial_fields": ["cell_id", "lat", "lon", "area_km2"],
                "quality_flags": QC_FLAGS, "missingness": "SQL NULL means missing; not-applicable is defined by body schema/registry. Zero remains a measured/derived zero."}
    provenance = {"version": VERSION, "created_utc": datetime.now(timezone.utc).isoformat(),
                  "runtime": {"python": platform.python_version(), "duckdb": duckdb.__version__},
                  "input_files": [], "bodies": {}, "code": {}}
    for path in sorted((ROOT / "processing").glob("*.py")):
        provenance["code"][str(path.relative_to(ROOT))] = digest(path)
    validation = {"version": VERSION, "bodies": {}, "failures": [], "scope": "Input integrity, transformation invariants and eligibility; not ground-truth analog validation."}
    for body in ("earth", "moon", "mars"):
        print(f"Preparing {body}", flush=True)
        folder = ROOT / f"{body}_integrated_dataset"
        paths = {s: folder / f"{body}_{s}" for s in ["integrated.parquet", "feature_dictionary.json", "metadata.json"]}
        for p in paths.values():
            provenance["input_files"].append({"path": str(p.relative_to(ROOT)), "bytes": p.stat().st_size, "sha256": digest(p)})
        metadata = json.loads(paths["metadata.json"].read_text())
        dictionary = json.loads(paths["feature_dictionary.json"].read_text())
        provenance["bodies"][body] = metadata
        grid = metadata["grid"]
        registry["bodies"][body] = {"crs": metadata["crs"], "grid": grid, "features": {}}
        for f in dictionary:
            policy, reason = comparison_policy(f["name"], f)
            registry["bodies"][body]["features"][f["name"]] = {**f, "comparison_policy": policy, "comparison_note": reason}
        db.execute(f"CREATE OR REPLACE VIEW source AS SELECT * FROM read_parquet({sql_path(paths['integrated.parquet'])})")
        schema = db.execute("DESCRIBE source").fetchall()
        names = [row[0] for row in schema]
        expected = {f["name"] for f in dictionary} | set(registry["spatial_fields"])
        assert set(names) == expected, f"{body}: schema and dictionary differ"
        replacements = []
        for name, typ, *_ in schema:
            if typ in ("FLOAT", "DOUBLE"):
                replacements.append(f'CASE WHEN isfinite("{name}") THEN "{name}" ELSE NULL END AS "{name}"')
        db.execute("CREATE OR REPLACE VIEW clean AS SELECT * REPLACE (" + ",".join(replacements) + ") FROM source")
        half = grid["res_deg"] / 2
        core_complete = " AND ".join(f'"{name}" IS NOT NULL' for name in CORE)
        terrain_bad = " OR ".join(["slope_median_deg NOT BETWEEN 0 AND 90", "slope_p90_deg NOT BETWEEN 0 AND 90",
                                   "slope_median_deg > slope_p90_deg", "relief_m < 0", "roughness_rms_m < 0", "tri_mean_m < 0"])
        elevation_bad = "elev_min_m > elev_mean_m + 0.001 OR elev_mean_m > elev_max_m + 0.001 OR elev_min_m > elev_max_m + 0.001"
        negative = "elev_mean_m < -500" if body == "earth" else "FALSE"
        flags = [
            (1, "dem_valid_frac IS NULL OR dem_valid_frac < 0.95 OR dem_valid_frac > 1"),
            (2, f"NOT ({core_complete})"), (4, f"coalesce(({terrain_bad}), FALSE)"),
            (8, f"coalesce(({elevation_bad}), FALSE)"),
            (16, "geo_unit IS NULL OR geo_unit IN ('undefined', '')"),
            (32, "tsurf_mean_k IS NULL"), (64, f"coalesce(({negative}), FALSE)"),
        ]
        quality = " + ".join(f"CASE WHEN {condition} THEN {bit} ELSE 0 END" for bit, condition in flags)
        radius = grid["radius_km"]
        db.execute(f"""CREATE OR REPLACE VIEW flagged AS SELECT *,
            '{body}' AS body, '{body}:' || cell_id::VARCHAR AS feature_id,
            (lon-{half})::DOUBLE AS west, (lon+{half})::DOUBLE AS east,
            (lat-{half})::DOUBLE AS south, (lat+{half})::DOUBLE AS north,
            {radius} * radians({grid['res_deg']}) AS cell_height_km,
            {radius} * radians({grid['res_deg']}) * cos(radians(lat)) AS cell_width_km,
            ({quality})::USMALLINT AS quality_flags,
            CASE WHEN geo_unit IS NULL OR geo_unit IN ('undefined','') THEN NULL ELSE geo_unit END AS geology_unit_known,
            CASE WHEN geo_class='volcanic' AND geo_unit IS NOT NULL AND geo_unit NOT IN ('undefined','') THEN TRUE ELSE FALSE END AS volcanic_context,
            'not_integrated' AS vegetation_evidence_status, 'not_integrated' AS aridity_evidence_status,
            'regional_native_cell' AS comparison_scale
            FROM clean""")
        db.execute("""CREATE OR REPLACE VIEW prepared AS SELECT *,
            (quality_flags & 79) = 0 AS eligible_terrain,
            (quality_flags & 127) = 0 AS terrain_temperature_geology_available
            FROM flagged""")
        target = staging / f"{body}_features.parquet"
        db.execute(f"COPY prepared TO {sql_path(target)} (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 65536)")
        db.execute(f"CREATE OR REPLACE VIEW exported AS SELECT * FROM read_parquet({sql_path(target)})")
        count, unique_count, eligible, joint, unknown_geo = db.execute("""SELECT count(*),count(DISTINCT feature_id),
            count(*) FILTER(WHERE eligible_terrain), count(*) FILTER(WHERE terrain_temperature_geology_available),
            count(*) FILTER(WHERE geology_unit_known IS NULL) FROM exported""").fetchone()
        source_count = db.execute("SELECT count(*) FROM source").fetchone()[0]
        coords_bad = db.execute(f"""SELECT count(*) FROM exported WHERE cell_id IS NULL OR lat IS NULL OR lon IS NULL OR area_km2 IS NULL
            OR NOT (lat BETWEEN -90 AND 90) OR NOT (lon >= -180 AND lon < 180) OR area_km2 <= 0
            OR abs(lat - (90 - (floor(cell_id/{grid['shape'][1]}) + 0.5)*{grid['res_deg']})) > 0.00001
            OR abs(lon - (-180 + ((cell_id % {grid['shape'][1]}) + 0.5)*{grid['res_deg']})) > 0.00001""").fetchone()[0]
        differences = 0
        # Check every source column after the documented finite-value normalization.
        for start in range(0, len(names), 12):
            tests = " OR ".join(f'a."{n}" IS DISTINCT FROM b."{n}"' for n in names[start:start+12])
            differences += db.execute(f"SELECT count(*) FROM clean a JOIN exported b USING(cell_id) WHERE {tests}").fetchone()[0]
        quality_counts = {str(bit): db.execute(f"SELECT count(*) FROM exported WHERE quality_flags & {bit} != 0").fetchone()[0] for bit, _ in flags}
        record = {"input_rows": source_count, "output_rows": count, "unique_ids": unique_count,
                  "eligible_terrain_rows": eligible, "terrain_temperature_defined_geology_rows": joint,
                  "unknown_geology_rows": unknown_geo, "invalid_coordinates": coords_bad,
                  "unexpected_value_changes": differences, "quality_flag_counts": quality_counts,
                  "output_bytes": target.stat().st_size, "output_sha256": digest(target)}
        validation["bodies"][body] = record
        if count != source_count or unique_count != count or coords_bad or differences:
            validation["failures"].append({"body": body, "check": "row/schema/value/coordinate invariant"})
        print(f"  {count:,} rows preserved; {eligible:,} terrain eligible", flush=True)
    # One application-facing table for planetary lookup; body-qualified IDs avoid collisions.
    db.execute(f"COPY (SELECT * FROM read_parquet([{sql_path(staging/'moon_features.parquet')},{sql_path(staging/'mars_features.parquet')}], union_by_name=true)) TO {sql_path(staging/'planetary_features.parquet')} (FORMAT PARQUET, COMPRESSION ZSTD)")
    # Recheck source hashes to ensure the run did not alter its scientific inputs.
    for record in provenance["input_files"]:
        assert digest(ROOT / record["path"]) == record["sha256"], f"Input changed: {record['path']}"
    validation["input_checksums_unchanged"] = True
    validation["status"] = "passed" if not validation["failures"] else "failed"
    write_json(staging / "feature_registry.json", registry)
    write_json(staging / "profiles.json", {"version": VERSION, "profiles": PROFILES})
    write_json(staging / "provenance.json", provenance)
    write_json(staging / "validation.json", validation)
    write_json(staging / "targets.json", {"version": VERSION, "targets": [
        {"id": "jezero_center", "body": "mars", "lat": 18.41, "lon": 77.69,
         "name": "Jezero crater center (regional context)", "geometry_type": "named_feature_point",
         "source": "https://planetarynames.wr.usgs.gov/Feature/14300", "coordinate_convention": "planetocentric, east-positive",
         "caveat": "Center is not a landing ellipse or delta footprint; displayed values resolve to the containing native cell."},
        {"id": "shackleton_center", "body": "moon", "lat": -89.67, "lon": 129.78,
         "name": "Shackleton crater center (coverage diagnostic)", "geometry_type": "named_feature_point",
         "source": "https://planetarynames.wr.usgs.gov/Feature/5450", "coordinate_convention": "planetographic, east-positive; lunar spherical working grid",
         "caveat": "Crater center is not a proposed rim base; core terrain is missing in the current integrated table."},
    ]})
    write_json(staging / "readiness.json", {"version": VERSION, "goal_complete": False,
        "completed": ["immutable_input_inventory", "all_body_feature_tables", "quality_flags_and_eligibility", "feature_policy_registry", "experimental_terrain_profile"],
        "remaining": ["earth_vegetation_and_land_cover", "precipitation_and_aridity", "polar_terrain_harmonization", "regional_material_crosswalk_validation", "temperature_sampling_harmonization", "local_candidate_characterization", "ranking_stability_and_external_validation"],
        "scientific_status": "Prepared for regional terrain screening; does not certify physical analog suitability."})
    manifest = {"version": VERSION, "files": {p.name: {"bytes": p.stat().st_size, "sha256": digest(p)} for p in staging.iterdir() if p.is_file()}}
    write_json(staging / "manifest.json", manifest)
    if validation["failures"]:
        raise RuntimeError(f"Validation failed; inspect {staging / 'validation.json'}")
    staging.rename(output)
    print(f"Published {output}", flush=True)
    return validation


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    prepare(parser.parse_args().output)

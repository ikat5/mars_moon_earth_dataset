"""Audit local integrated tables; requires DuckDB. Run from the repository root."""
import csv
import json
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "analysis"
db = duckdb.connect()
db.execute("SET threads=4")
results = {"audit": {"duckdb_version": duckdb.__version__, "scope": "Local integrated Parquet tables and accompanying JSON metadata; not a raw-source validation"}}
coverage_rows = []
features = {}

for body in ("earth", "moon", "mars"):
    print("Auditing", body, flush=True)
    folder = ROOT / f"{body}_integrated_dataset"
    dictionary = json.loads((folder / f"{body}_feature_dictionary.json").read_text())
    metadata = json.loads((folder / f"{body}_metadata.json").read_text())
    features[body] = {f["name"]: f for f in dictionary}
    db.execute(f"CREATE OR REPLACE VIEW data AS SELECT * FROM read_parquet('{folder}/{body}_integrated.parquet')")
    schema = db.execute("DESCRIBE data").fetchall()
    types = {row[0]: row[1] for row in schema}

    def valid(name):
        col = f'"{name}"'
        return f"({col} IS NOT NULL AND {col} <> '')" if types[name] == "VARCHAR" else f"isfinite({col})"

    n, ids, area = db.execute("SELECT count(*), count(DISTINCT cell_id), sum(area_km2) FROM data").fetchone()
    body_result = {"rows": n, "columns": len(schema), "features": len(dictionary), "unique_cell_ids": ids,
                   "represented_cell_area_km2": area, "grid": metadata["grid"], "coverage": {}}
    expr = []
    for f in dictionary:
        name = f["name"]
        ok = valid(name)
        expr.extend([f"count(*) FILTER (WHERE {ok})", f"sum(area_km2) FILTER (WHERE {ok})"])
    counts = []
    for start in range(0, len(expr), 16):
        counts.extend(db.execute("SELECT " + ",".join(expr[start:start+16]) + " FROM data").fetchone())
    for i, f in enumerate(dictionary):
        name = f["name"]
        row = {"body": body, "feature": name, "measurement_type": f["measurement_type"],
               "source": f["source"], "valid_cells": counts[2*i], "cell_fraction": counts[2*i]/n,
               "area_fraction": (counts[2*i+1] or 0)/area,
               "dictionary_coverage_area_frac": f.get("coverage_area_frac")}
        coverage_rows.append(row)
        body_result["coverage"][name] = row

    numeric = [f["name"] for f in dictionary if types[f["name"]] != "VARCHAR"]
    expr = []
    for name in numeric:
        col = f'"{name}"'
        expr.extend([f"min({col}) FILTER (WHERE {valid(name)})", f"max({col}) FILTER (WHERE {valid(name)})",
                     f"count(*) FILTER (WHERE {col} = 0)", f"count(*) FILTER (WHERE {col} = 1)"])
    stats = []
    for start in range(0, len(expr), 16):
        stats.extend(db.execute("SELECT " + ",".join(expr[start:start+16]) + " FROM data").fetchone())
    body_result["numeric_ranges"] = {name: dict(zip(["min", "max", "zero_cells", "one_cells"], stats[4*i:4*i+4]))
                                     for i, name in enumerate(numeric)}
    body_result["categories"] = {}
    for name, typ in types.items():
        if typ == "VARCHAR":
            body_result["categories"][name] = dict(db.execute(f'SELECT "{name}", count(*) FROM data GROUP BY 1 ORDER BY 2 DESC').fetchall())
    core = ["slope_median_deg", "slope_p90_deg", "relief_m", "roughness_rms_m", "tri_mean_m"]
    core_ok = " AND ".join(valid(x) for x in core)
    body_result["complete_terrain_cells"] = db.execute(f"SELECT count(*) FROM data WHERE {core_ok}").fetchone()[0]
    body_result["dem_valid_below_10pct_cells"] = db.execute("SELECT count(*) FROM data WHERE dem_valid_frac < 0.1").fetchone()[0]
    body_result["dem_valid_below_50pct_cells"] = db.execute("SELECT count(*) FROM data WHERE dem_valid_frac < 0.5").fetchone()[0]
    if body == "earth":
        groups = {"all": "TRUE", "south_of_62S": "lat < -62", "north_of_62S": "lat >= -62"}
        body_result["regional_coverage"] = {}
        for label, condition in groups.items():
            selections = ["count(*)"] + [f"count(*) FILTER (WHERE {valid(x)})" for x in ["tsurf_mean_k", "geo_unit", "roughness_rms_m"]]
            body_result["regional_coverage"][label] = dict(zip(["cells", "temperature_cells", "geology_cells", "roughness_cells"],
                db.execute("SELECT " + ",".join(selections) + " FROM data WHERE " + condition).fetchone()))
        body_result["complete_terrain_temperature_geology_cells"] = db.execute(
            f"SELECT count(*) FROM data WHERE {core_ok} AND {valid('tsurf_mean_k')} AND {valid('geo_unit')}").fetchone()[0]
        body_result["deep_negative_elevation_cells"] = db.execute("SELECT count(*) FROM data WHERE elev_mean_m < -500").fetchone()[0]
        body_result["deep_negative_elevation_examples"] = db.execute(
            "SELECT cell_id,lat,lon,elev_mean_m,dem_valid_frac FROM data WHERE elev_mean_m < -500 ORDER BY elev_mean_m LIMIT 5").fetchall()
        body_result["cave_points_counted"] = db.execute("SELECT sum(cave_candidate_count),count(*) FILTER (WHERE cave_candidate_count > 0) FROM data").fetchone()
        body_result["crater_centred_cells"] = db.execute(f"SELECT count(*) FROM data WHERE {valid('crater_largest_d_km')}").fetchone()[0]
    # Compare the configured analog recipe with columns actually available on Earth.
    recipe = metadata["processing_config"]["analog"]["features"]
    body_result["configured_analog_features"] = recipe
    body_result["declared_but_missing_files"] = [f for f in metadata["files"] if not (folder / f).exists()]
    results[body] = body_result

results["shared"] = {"all_three": sorted(set.intersection(*(set(f) for f in features.values())))}
for body in ("moon", "mars"):
    results["shared"][f"earth_{body}"] = sorted(features["earth"].keys() & features[body].keys())
results["recipe_earth_availability"] = {
    dimension: {"available": sorted(set(names) & features["earth"].keys()),
                "missing": sorted(set(names) - features["earth"].keys())}
    for dimension, names in results["earth"]["configured_analog_features"].items()
}
(OUT / "dataset_audit.json").write_text(json.dumps(results, indent=2, allow_nan=False) + "\n")
with (OUT / "feature_coverage.csv").open("w", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(coverage_rows[0]))
    writer.writeheader()
    writer.writerows(coverage_rows)
print("Saved analysis/dataset_audit.json and analysis/feature_coverage.csv")
for body in ("earth", "moon", "mars"):
    r = results[body]
    print(body, r["rows"], "rows;", r["features"], "features;", r["complete_terrain_cells"], "complete terrain cells")
print("Earth joint terrain/temperature/geology:", results["earth"]["complete_terrain_temperature_geology_cells"])
print("Earth regional coverage:", results["earth"]["regional_coverage"])
print("Configured analog recipe:", results["recipe_earth_availability"])

"""Diagnostic, exact regional retrieval over the prepared dataset.

Example: python -m processing.search --body mars --lat 18.41 --lon 77.69 --output analysis/jezero_search.json
Results are screening candidates, not verified analog sites.
"""
import argparse
import json
import math
import re
import time
from pathlib import Path

import duckdb
import numpy as np
from processing.config import DEFAULT_OUTPUT, CORE


def normalize_location(lat, lon):
    if not math.isfinite(lat) or not math.isfinite(lon) or not -90 <= lat <= 90:
        raise ValueError("Latitude must be finite and within [-90,90]; longitude must be finite.")
    return float(lat), float((lon + 180) % 360 - 180)


def cell_id_for_location(lat, lon, grid):
    lat, lon = normalize_location(lat, lon)
    n_lat, n_lon = grid["shape"]
    row = min(n_lat - 1, max(0, math.floor((90 - lat) / grid["res_deg"])))
    col = min(n_lon - 1, max(0, math.floor((lon + 180) / grid["res_deg"])))
    return row * n_lon + col


def distances_km(lat, lon, lats, lons):
    """Spherical Earth distances; inputs can be scalars or NumPy arrays."""
    p1, p2 = np.radians(lat), np.radians(lats)
    dl = np.radians(np.asarray(lons) - lon)
    dp = p2 - p1
    a = np.sin(dp / 2)**2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2)**2
    return 12742.0 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def normalized_fit(values, target, weights, tolerances):
    """Complete-case score. Missing input cannot obtain a numerical score."""
    values, target = np.asarray(values), np.asarray(target)
    weights, tolerances = np.asarray(weights), np.asarray(tolerances)
    if not np.all(np.isfinite(weights)) or np.any(weights < 0) or weights.sum() <= 0:
        raise ValueError("Weights must be finite, nonnegative and have positive total.")
    if not np.all(np.isfinite(tolerances)) or np.any(tolerances <= 0):
        raise ValueError("Tolerances must be positive and finite.")
    if not np.all(np.isfinite(values)) or not np.all(np.isfinite(target)):
        raise ValueError("Cannot score missing/nonfinite essential measurements.")
    distances = np.minimum(np.abs(values - target) / tolerances, 1)
    return 100 * (1 - distances @ (weights / weights.sum())), distances


def polygon(row):
    w, e, s, n = (float(row[x]) for x in ("west", "east", "south", "north"))
    return {"type": "Polygon", "coordinates": [[[w,s],[e,s],[e,n],[w,n],[w,s]]]}


def numeric_context(value):
    if np.ma.is_masked(value) or not np.isfinite(value):
        return None
    return float(value)


def sql_column(name):
    if not re.fullmatch(r'[a-z][a-z0-9_]*',name):
        raise ValueError('Invalid configured column identifier')
    return '"'+name+'"'


def resolve_target(db, data_dir, body, lat, lon):
    if body not in ("moon", "mars"):
        raise ValueError("Target body must be moon or mars.")
    provenance = json.loads((data_dir / "provenance.json").read_text())
    grid = provenance["bodies"][body]["grid"]
    lat, lon = normalize_location(lat, lon)
    identifier = cell_id_for_location(lat, lon, grid)
    cur = db.execute("SELECT * FROM read_parquet(?) WHERE cell_id=?", [str(data_dir / f"{body}_features.parquet"), identifier])
    result = cur.fetchone()
    if result is None:
        raise ValueError("No source grid cell exists for the requested location.")
    row = dict(zip([x[0] for x in cur.description], result))
    return row, {"body": body, "requested_lat": lat, "requested_lon": lon, "feature_id": row["feature_id"],
                 "cell_center": {"lat": row["lat"], "lon": row["lon"]}, "geometry": polygon(row),
                 "area_km2": row["area_km2"], "quality_flags": row["quality_flags"],
                 "core_terrain": {x: row[x] for x in CORE},
                 "interpretation": "Containing native grid cell; not a point measurement or a mission landing footprint."}


def search(body, lat, lon, data_dir=DEFAULT_OUTPUT, profile="terrain_screening", limit=10,
           origin=None, radius_km=None, separation_km=None, weight_overrides=None):
    started = time.perf_counter()
    data_dir = Path(data_dir)
    if not isinstance(limit, int) or not 1 <= limit <= 100:
        raise ValueError("limit must be an integer between 1 and 100")
    if radius_km is not None and (origin is None or not math.isfinite(radius_km) or radius_km < 0):
        raise ValueError("A finite nonnegative radius requires an origin.")
    if origin is not None:
        origin = normalize_location(*origin)
    definitions = json.loads((data_dir / "profiles.json").read_text())
    if profile not in definitions["profiles"]:
        raise ValueError("Unknown profile")
    config = definitions["profiles"][profile]
    response = {"dataset_version": definitions["version"], "profile": profile, "candidates": [],
                "profile_status": config["status"], "scientific_validation": "not_performed"}
    if config["status"] != "experimental_available":
        return {**response, "status": "profile_unavailable", "missing_evidence": config.get("missing", [])}
    sep = config["default_separation_km"] if separation_km is None else separation_km
    if not math.isfinite(sep) or sep < 0:
        raise ValueError("separation_km must be finite and nonnegative")
    features = list(config["features"])
    overrides = weight_overrides or {}
    if set(overrides) - set(features):
        raise ValueError("Unknown weight override feature")
    weights = np.array([overrides.get(f, config["features"][f]["weight"]) for f in features], dtype=float)
    tolerances = np.array([config["features"][f]["tolerance"] for f in features], dtype=float)
    # Validate weights even if there are no eligible candidates.
    normalized_fit(np.zeros((1,len(features))), np.zeros(len(features)), weights, tolerances)
    db = duckdb.connect()
    db.execute("SET threads=2")
    row, target = resolve_target(db, data_dir, body, lat, lon)
    response.update({"target": target, "limitations": config["limitations"],
                     "configuration": {"weights": dict(zip(features, weights.tolist())), "tolerances": dict(zip(features, tolerances.tolist())),
                     "area_ratio": config["earth_target_area_ratio"], "minimum_fit": config["minimum_fit"],
                     "minimum_separation_km": sep, "origin": origin, "radius_km": radius_km}})
    target_eligibility=config.get('target_eligibility_column',config['eligibility_column'])
    earth_eligibility=config.get('earth_eligibility_column',config['eligibility_column'])
    if not row[target_eligibility]:
        db.close()
        return {**response, "status": "target_insufficient_evidence", "missing_terrain": [f for f in CORE if row[f] is None]}
    target_values = np.array([row[f] for f in features], dtype=float)
    context_columns=config.get('earth_context_features',[])
    columns = list(dict.fromkeys(["cell_id", "lat", "lon", "area_km2", "west", "east", "south", "north", *features,*context_columns]))
    lo, hi = config["earth_target_area_ratio"]
    arr = db.execute(f"SELECT {','.join(map(sql_column,columns))} FROM read_parquet(?) WHERE {sql_column(earth_eligibility)} AND area_km2 BETWEEN ? AND ? ORDER BY cell_id",
                     [str(data_dir / "earth_features.parquet"), row["area_km2"]*lo, row["area_km2"]*hi]).fetchnumpy()
    db.close()
    count = len(arr["cell_id"])
    response["eligible_after_area_filter"] = count
    response['earth_environment_rules']=config.get('earth_environment_rules',{})
    radius_distances = None
    if origin is not None:
        radius_distances = distances_km(*origin, arr["lat"], arr["lon"])
        if radius_km is not None:
            within = radius_distances <= radius_km
            arr = {k: v[within] for k,v in arr.items()}
            radius_distances = radius_distances[within]
    response["eligible_after_radius_filter"] = len(arr["cell_id"])
    if not len(arr["cell_id"]):
        return {**response, "status": "no_candidates_under_filters", "elapsed_seconds": time.perf_counter()-started}
    matrix = np.column_stack([arr[f] for f in features]).astype(float)
    scores, diffs = normalized_fit(matrix, target_values, weights, tolerances)
    supported = scores >= config["minimum_fit"]
    response["above_minimum_fit"] = int(supported.sum())
    # Deterministic tie break by cell ID. Geographic thinning retains real cell footprints.
    order = np.lexsort((arr["cell_id"], -scores))
    chosen = []
    for index in order:
        if not supported[index]:
            break
        if chosen:
            distances = distances_km(float(arr["lat"][index]), float(arr["lon"][index]), arr["lat"][chosen], arr["lon"][chosen])
            if np.any(distances < sep):
                continue
        chosen.append(int(index))
        if len(chosen) == limit:
            break
    for i in chosen:
        candidate_row = {key: numeric_context(arr[key][i]) for key in columns}
        comparisons = [{"feature": f, "target_value": float(target_values[j]), "earth_value": float(matrix[i,j]),
                        "absolute_difference": float(abs(matrix[i,j]-target_values[j])), "normalized_distance": float(diffs[i,j]),
                        "normalized_weight": float(weights[j]/weights.sum()),
                        "fit_contribution": float(100*weights[j]/weights.sum()*(1-diffs[i,j]))} for j,f in enumerate(features)]
        response["candidates"].append({"feature_id": f"earth:{int(arr['cell_id'][i])}",
            "lat": candidate_row["lat"], "lon": candidate_row["lon"], "geometry": polygon(candidate_row),
            "area_km2": candidate_row["area_km2"], "target_area_ratio": candidate_row["area_km2"]/row["area_km2"],
            "observed_fit": float(scores[i]), "supported_fit_lower": float(scores[i]), "possible_fit_upper": float(scores[i]),
            "scored_feature_coverage": 1.0, "distance_from_origin_km": None if radius_distances is None else float(radius_distances[i]),
            "comparisons": comparisons, "largest_numeric_mismatch": max(comparisons, key=lambda x:x["normalized_distance"])["feature"],
            "review_status": "unreviewed_screening_candidate", "vegetation_screened": False,
            "land_cover_screened":bool(config.get('land_cover_screened',False)),
            "aridity_screened":bool(config.get('aridity_screened',False)),
            "earth_environment_context":{name:candidate_row[name] for name in context_columns},
            "environment_evidence":config.get('environment_evidence',{}),
            "local_site_verified": False, "rank_stability": None})
    response["status"] = "ok" if chosen else "no_candidates_under_filters"
    response["elapsed_seconds"] = time.perf_counter()-started
    return response


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--body", choices=["moon", "mars"], required=True)
    parser.add_argument("--lat", type=float, required=True)
    parser.add_argument("--lon", type=float, required=True)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--profile", default="terrain_screening")
    parser.add_argument("--origin", nargs=2, type=float, metavar=("LAT", "LON"))
    parser.add_argument("--radius-km", type=float)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = search(args.body, args.lat, args.lon, args.data_dir, args.profile, args.limit, args.origin, args.radius_km)
    content = json.dumps(result, indent=2, allow_nan=False)+"\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content)
        print(f"{result['status']}: {len(result['candidates'])} candidates; saved {args.output}")
    else:
        print(content)

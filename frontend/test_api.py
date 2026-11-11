"""HTTP contract tests for the TerraTwin API. Run from the repository root:

    TERRATWIN_PREWARM=0 TERRATWIN_FETCH_LABELS=0 .venv/bin/python -m pytest frontend/test_api.py -q

They need the serving Parquet release (Git LFS) but not the lunar DEM or network access.
"""
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

os.environ.setdefault("TERRATWIN_PREWARM", "0")
os.environ.setdefault("TERRATWIN_FETCH_LABELS", "0")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import terratwin_service  # noqa: E402
from app import app  # noqa: E402
from processing.search import search  # noqa: E402

client = TestClient(app)
JEZERO = {"body": "mars", "lat": 18.41, "lon": 77.69, "profile": "dry_barren_terrain"}


def post(payload, raw=None):
    if raw is not None:
        return client.post("/api/v1/search", content=raw, headers={"content-type": "application/json"})
    return client.post("/api/v1/search", json=payload)


def release():
    return terratwin_service.get_release()


def test_health_and_meta_bind_current_release():
    pointer = json.loads((terratwin_service.ROOT / "prepared/current_release.json").read_text())
    h = client.get("/api/v1/health")
    assert h.status_code == 200 and h.json()["status"] == "ready"
    assert h.json()["release"]["dataset_version"] == pointer["version"]
    m = client.get("/api/v1/meta").json()
    assert m["dataset_version"] == pointer["version"]
    assert m["score"]["label"] == "Terrain resemblance"
    profiles = {p["id"]: p for p in m["profiles"]}
    assert profiles["terrain_screening"]["available"] and profiles["dry_barren_terrain"]["available"]
    assert profiles["cave_reconnaissance"]["available"] is False and profiles["cave_reconnaissance"]["missing_evidence"]
    assert profiles["dry_barren_terrain"]["minimum_fit"] == 50.0
    assert {e["id"] for e in m["examples"]} >= {"jezero_center", "jezero_landing", "shackleton_center"}


@pytest.mark.parametrize("case_id", ["jezero", "lunar_equatorial_coordinate", "jezero_near_sylhet", "shackleton"])
def test_http_matches_direct_engine_for_release_cases(case_id):
    saved = client.get(f"/api/v1/cases/{case_id}").json()
    assert saved["saved_fixture"]["notice"].startswith("Saved example")
    t, cfg = saved["target"], saved["configuration"]
    payload = {"body": t["body"], "lat": t["requested_lat"], "lon": t["requested_lon"], "profile": saved["profile"]}
    if cfg["origin"]:
        payload |= {"origin": {"lat": cfg["origin"][0], "lon": cfg["origin"][1]}, "radius_km": cfg["radius_km"]}
    r = post(payload)
    assert r.status_code == 200
    live = r.json()
    direct = search(t["body"], t["requested_lat"], t["requested_lon"], data_dir=release().data_dir, profile=saved["profile"],
                    origin=tuple(cfg["origin"]) if cfg["origin"] else None, radius_km=cfg["radius_km"])
    assert live["status"] == direct["status"] == saved["status"]
    assert "saved_fixture" not in live
    assert [(c["feature_id"], c["observed_fit"]) for c in live["candidates"]] == \
           [(c["feature_id"], c["observed_fit"]) for c in direct["candidates"]]
    assert [c["feature_id"] for c in live["candidates"]] == [c["feature_id"] for c in saved["candidates"]]
    assert live["dataset_version"] == release().version
    if case_id == "shackleton":
        assert live["candidates"] == [] and live["missing_terrain"]


def test_arbitrary_target_and_longitude_aliases():
    gale = post({"body": "mars", "lat": -4.5895, "lon": 137.4417, "profile": "terrain_screening", "limit": 5}).json()
    assert gale["status"] in ("ok", "no_candidates_under_filters", "target_insufficient_evidence")
    if gale["status"] == "ok":
        assert 1 <= len(gale["candidates"]) <= 5
    ids = {post({**JEZERO, "lon": lon, "limit": 1}).json()["target"]["feature_id"] for lon in (77.69, 437.69, -282.31)}
    assert ids == {"mars:412870"}
    east, west = (post({"body": "moon", "lat": 10, "lon": lon, "profile": "terrain_screening", "limit": 1}).json()
                  for lon in (180, -180))
    assert east["target"]["feature_id"] == west["target"]["feature_id"]
    assert east["request"]["lon"] == -180 and east["request"]["lon_as_supplied"] == 180


@pytest.mark.parametrize("lat", [90, -90])
def test_poles_resolve_without_error(lat):
    r = post({"body": "moon", "lat": lat, "lon": 0, "profile": "terrain_screening", "limit": 1})
    assert r.status_code == 200 and r.json()["status"] in ("ok", "target_insufficient_evidence", "no_candidates_under_filters")


def test_cell_boundary_switches_regional_cell():
    # Mars cells are 0.25°; latitude 18.5 is a cell boundary.
    north = client.get("/api/v1/target", params={"body": "mars", "lat": 18.5001, "lon": 77.6}).json()["target"]
    south = client.get("/api/v1/target", params={"body": "mars", "lat": 18.4999, "lon": 77.6}).json()["target"]
    assert north["feature_id"] != south["feature_id"]
    assert north["label"] == "Regional cell containing this point"
    assert north["geometry"]["coordinates"][0][0][1] == 18.5  # south edge of the northern cell


def test_landing_point_and_crater_center_are_distinct():
    landing = client.get("/api/v1/target", params={"body": "mars", "lat": 18.4447, "lon": 77.4508}).json()["target"]
    center = client.get("/api/v1/target", params={"body": "mars", "lat": 18.41, "lon": 77.69}).json()["target"]
    assert (landing["feature_id"], center["feature_id"]) == ("mars:412869", "mars:412870")


def test_target_reports_missing_terrain_at_shackleton():
    t = client.get("/api/v1/target", params={"body": "moon", "lat": -89.67, "lon": 129.78}).json()["target"]
    assert t["terrain_eligible"] == {"terrain_screening": False, "dry_barren_terrain": False}
    assert t["missing_terrain"]


def test_unavailable_profile_is_a_scientific_outcome():
    r = post({**JEZERO, "profile": "cave_reconnaissance"})
    assert r.status_code == 200
    assert r.json()["status"] == "profile_unavailable" and r.json()["candidates"] == []
    assert r.json()["missing_evidence"] == ["verified_cave_catalog_and_local_evidence"]


def test_origin_without_radius_reports_distance_only():
    r = post({**JEZERO, "limit": 3, "origin": {"lat": 24.89, "lon": 91.87}}).json()
    assert r["status"] == "ok" and all(c["distance_from_origin_km"] > 0 for c in r["candidates"])
    assert r["request"]["origin_supplied"] is True and "origin" not in r["request"]


@pytest.mark.parametrize("payload", [
    {**JEZERO, "lat": 91},
    {**JEZERO, "lat": "18.41"},
    {**JEZERO, "lat": True},
    {**JEZERO, "lon": 999},
    {**JEZERO, "body": "earth"},
    {**JEZERO, "profile": "no_such_profile"},
    {**JEZERO, "profile": "../../etc"},
    {**JEZERO, "limit": 0},
    {**JEZERO, "limit": 51},
    {**JEZERO, "limit": 10.5},
    {**JEZERO, "limit": "10"},
    {**JEZERO, "radius_km": 100},
    {**JEZERO, "origin": {"lat": 24.89, "lon": 91.87}, "radius_km": -1},
    {**JEZERO, "origin": {"lat": 24.89}},
    {**JEZERO, "origin": {"lat": 24.89, "lon": 91.87, "name": "home"}},
    {**JEZERO, "weights": {"tri_mean_m": 1}},
    {**JEZERO, "weights": {"relief_m": -1}},
    {**JEZERO, "weights": {"slope_median_deg": 0, "slope_p90_deg": 0, "relief_m": 0, "roughness_rms_m": 0}},
    {**JEZERO, "data_dir": "/tmp"},
    {"body": "mars", "lat": 18.41, "lon": 77.69},
])
def test_invalid_input_is_a_validation_error_not_a_no_match(payload):
    r = post(payload)
    assert r.status_code == 422, (payload, r.status_code, r.text)
    assert "status" not in r.json() and "candidates" not in r.json()


@pytest.mark.parametrize("raw", ['{"body":"mars","lat":NaN,"lon":77.69,"profile":"terrain_screening"}',
                                 '{"body":"mars","lat":18.41,"lon":Infinity,"profile":"terrain_screening"}', 'not json'])
def test_non_finite_and_malformed_json_rejected(raw):
    assert post(None, raw=raw).status_code == 422


def test_static_and_evidence_allowlists():
    assert client.get("/").status_code == 200
    assert client.get("/index.html").status_code == 200
    for path in ("/ldem_64.tif", "/app.py", "/terratwin_service.py", "/.venv/pyvenv.cfg", "/requirements.txt",
                 "/tile_cache", "/api/v1/evidence/gobi/dsm_utm30m.tif", "/api/v1/evidence/gobi/..%2F..%2FREADME.md",
                 "/api/v1/evidence/../app.py", "/api/v1/cases/../../profiles"):
        assert client.get(path).status_code == 404, path
    r = client.get("/api/v1/evidence/gobi/metadata.json")
    assert r.status_code == 200 and r.json()["feature_id"] == "earth:1090899"
    assert client.get("/api/v1/evidence/jaflong/patch_candidates.geojson").json()["type"] == "FeatureCollection"


def test_missing_release_is_service_unavailable(monkeypatch):
    monkeypatch.setenv("TERRATWIN_RELEASE_DIR", str(terratwin_service.ROOT / "prepared" / "does_not_exist"))
    terratwin_service.reset_release()
    try:
        assert client.get("/api/v1/health").status_code == 503
        r = post(JEZERO)
        assert r.status_code == 503 and r.json()["detail"]["error"] == "release_unavailable"
    finally:
        monkeypatch.delenv("TERRATWIN_RELEASE_DIR")
        terratwin_service.reset_release()
    assert client.get("/api/v1/health").status_code == 200


def test_release_outside_prepared_is_refused(monkeypatch):
    monkeypatch.setenv("TERRATWIN_RELEASE_DIR", "/tmp")
    terratwin_service.reset_release()
    try:
        assert post(JEZERO).status_code == 503
    finally:
        monkeypatch.delenv("TERRATWIN_RELEASE_DIR")
        terratwin_service.reset_release()


def test_ten_concurrent_searches_are_consistent():
    payloads = [JEZERO, {"body": "moon", "lat": 0, "lon": 0, "profile": "dry_barren_terrain"}] * 5
    with ThreadPoolExecutor(10) as pool:
        results = list(pool.map(post, payloads))
    assert all(r.status_code == 200 for r in results)
    by_body = {}
    for r in results:
        d = r.json()
        by_body.setdefault(d["target"]["body"], set()).add(tuple(c["feature_id"] for c in d["candidates"]))
    assert all(len(v) == 1 for v in by_body.values())

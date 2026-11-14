"""TerraTwin analog-search HTTP adapter around ``processing.search.search``.

Routes live under ``/api/v1``. The serving release is bound server-side from
``prepared/current_release.json`` (or ``TERRATWIN_RELEASE_DIR``); clients never supply paths, SQL or URLs.
Scientific outcomes (``ok``, ``target_insufficient_evidence``, ``no_candidates_under_filters``,
``profile_unavailable``) return HTTP 200 with that ``status``. Invalid input returns 422 and service
failures return 503/500, so neither can masquerade as a scientific no-match.
"""
import json
import logging
import math
import os
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:  # processing/ is a sibling package of frontend/
    sys.path.insert(0, str(ROOT))

import duckdb  # noqa: E402
from processing.config import CORE  # noqa: E402
from processing.search import normalize_location, resolve_target, search  # noqa: E402

API_VERSION = "1"
SCORE_LABEL = "Terrain resemblance"
SCORE_EXPLANATION = ("Experimental, uncalibrated 0–100 index of how closely four regional terrain summaries agree. "
                     "It is not accuracy, confidence, probability, site safety or predicted hardware performance.")
MAX_LIMIT = 50
MAX_RADIUS_KM = 20038.0  # half of Earth's circumference: every point is within this great-circle distance
MAX_CONCURRENT_SEARCHES = int(os.environ.get("TERRATWIN_MAX_CONCURRENT_SEARCHES", "4"))
SEARCH_QUEUE_TIMEOUT_S = 20.0
REQUIRED_TABLES = ("earth_features.parquet", "moon_features.parquet", "mars_features.parquet")
REQUIRED_JSON = ("profiles.json", "provenance.json", "feature_registry.json", "manifest.json")

log = logging.getLogger("terratwin")

FEATURE_LABELS = {
    "slope_median_deg": "Median slope",
    "slope_p90_deg": "90th-percentile slope",
    "relief_m": "Relief (max − min)",
    "roughness_rms_m": "RMS roughness",
    "tri_mean_m": "Terrain ruggedness index (diagnostic, not scored)",
    "landcover_strict_area_coverage": "Land-cover classified coverage",
    "landcover_barren_class_fraction": "Barren class fraction",
    "landcover_water_class_fraction": "Water class fraction",
    "landcover_built_class_fraction": "Built-up class fraction",
    "landcover_cropland_or_mosaic_class_fraction": "Cropland / mosaic class fraction",
    "aridity_index": "Aridity index (P/PET)",
    "aridity_index_area_coverage": "Aridity coverage",
    "ndvi_mean_provisional": "Mean NDVI (provisional scale)",
    "ndvi_peak_climatology_provisional": "Peak-month NDVI climatology (provisional)",
    "ndvi_valid_month_count": "NDVI months available",
    "ndvi_gapfilled_area_time_fraction": "NDVI gap-filled fraction",
}

# Form-filling examples. Every one runs a live search; none substitutes saved results.
EXAMPLES = [
    {"id": "jezero_center", "label": "Jezero crater center (named-feature center)", "body": "mars", "lat": 18.41, "lon": 77.69,
     "profile": "dry_barren_terrain", "note": "USGS named-feature center. Resolves to mars:412870, the regional cell used by the release fixtures."},
    {"id": "jezero_landing", "label": "Perseverance landing point (Jezero)", "body": "mars", "lat": 18.4447, "lon": 77.4508,
     "profile": "dry_barren_terrain", "note": "Rover landing point. Resolves to a different regional cell (mars:412869) from the crater center."},
    {"id": "lunar_equator", "label": "Illustrative lunar coordinate 0°N 0°E", "body": "moon", "lat": 0.0, "lon": 0.0,
     "profile": "dry_barren_terrain", "note": "An arbitrary equatorial coordinate, not a proposed site."},
    {"id": "jezero_near_sylhet", "label": "Jezero center within 500 km of Sylhet", "body": "mars", "lat": 18.41, "lon": 77.69,
     "profile": "dry_barren_terrain", "origin": {"lat": 24.89, "lon": 91.87}, "radius_km": 500,
     "note": "Expected outcome: no qualifying regional candidates. The radius is never relaxed automatically."},
    {"id": "shackleton_center", "label": "Shackleton crater center (coverage diagnostic)", "body": "moon", "lat": -89.67, "lon": 129.78,
     "profile": "dry_barren_terrain", "note": "Expected outcome: insufficient integrated target terrain. Separate polar LOLA context does not fill it."},
]

# Public evidence allowlist: (investigation, file) -> repository-relative path. Nothing else is downloadable.
EVIDENCE = {
    ("gobi", "metadata.json"): "prepared/gobi_candidate_0.1.0/metadata.json",
    ("gobi", "candidate.geojson"): "prepared/gobi_candidate_0.1.0/candidate.geojson",
    ("gobi", "candidate_context.png"): "prepared/gobi_candidate_0.1.0/candidate_context.png",
    ("gobi", "candidate_context.pdf"): "prepared/gobi_candidate_0.1.0/candidate_context.pdf",
    ("gobi", "brief.md"): "analysis/GOBI_CANDIDATE_BRIEF.md",
    ("jaflong", "metadata.json"): "prepared/local_pilot_0.1.1/metadata.json",
    ("jaflong", "patch_candidates.geojson"): "prepared/local_pilot_0.1.1/patch_candidates.geojson",
    ("jaflong", "local_pilot.png"): "prepared/local_pilot_0.1.1/local_pilot.png",
    ("jaflong", "local_pilot.pdf"): "prepared/local_pilot_0.1.1/local_pilot.pdf",
    ("jaflong", "brief.md"): "analysis/JAFLONG_LOCAL_PILOT.md",
    ("known_sites", "review.md"): "analysis/KNOWN_ANALOG_REVIEW.md",
}
MEDIA = {".json": "application/json", ".geojson": "application/geo+json", ".png": "image/png",
         ".pdf": "application/pdf", ".md": "text/markdown; charset=utf-8"}
INVESTIGATIONS = [
    {"id": "gobi", "title": "Gobi regional terrain candidate", "lat": 42.6875, "lon": 102.4375,
     "status": "finer_remote_sensing_context_unverified_in_field",
     "summary": ("A dry/barren Earth cell retrieved for the Jezero crater-center query (archived terrain resemblance ≈ 99.7). "
                 "Finer WorldCover land cover is predominantly bare/sparse, but 30 m DSM slopes show variation hidden by the "
                 "~14 km regional summaries. The 30 m slopes are separate measurements, not inputs to the regional score."),
     "caveats": ["Mapped carbonate-sedimentary geology does not establish exposed materials or chemistry matching Jezero.",
                 "Access, permissions and field suitability are not assessed.",
                 "Not a field-verified or newly discovered analog."],
     "files": ["metadata.json", "candidate.geojson", "candidate_context.png", "candidate_context.pdf", "brief.md"]},
    {"id": "jaflong", "title": "Jaflong local exposed-patch investigation", "lat": 25.155, "lon": 92.02,
     "status": "local_exposed_patch_investigation_no_planetary_score",
     "summary": ("Eight local patches (≥ 0.5 ha) classified bare/sparse in ESA WorldCover 2021 near Sylhet. They show that a "
                 "regional screen can miss small exposed patches. They carry no planetary resemblance score."),
     "caveats": ["Seven patches have potential DSM water-editing effects in their terrain context.",
                 "Patch classification is 2021 land cover, not verified exposed rock.",
                 "Not a field-verified analog or permission to conduct field operations."],
     "files": ["metadata.json", "patch_candidates.geojson", "local_pilot.png", "local_pilot.pdf", "brief.md"]},
]


class ReleaseUnavailable(RuntimeError):
    pass


def _is_lfs_pointer(path):
    with open(path, "rb") as f:
        return f.read(64).startswith(b"version https://git-lfs")


class Release:
    """The validated serving release. Loaded once; immutable afterwards."""

    def __init__(self, root=ROOT):
        override = os.environ.get("TERRATWIN_RELEASE_DIR")
        prepared = (root / "prepared").resolve()
        if override:
            data_dir = Path(override).resolve()
            pointer = {"version": None, "data_directory": data_dir.name, "app_index": None}
        else:
            pointer_path = prepared / "current_release.json"
            if not pointer_path.exists():
                raise ReleaseUnavailable(f"Release pointer missing: {pointer_path.relative_to(root)}")
            pointer = json.loads(pointer_path.read_text())
            data_dir = (prepared / pointer["data_directory"]).resolve()
        if prepared not in data_dir.parents:
            raise ReleaseUnavailable("Serving release must be a directory under prepared/")
        problems = []
        for name in REQUIRED_TABLES + REQUIRED_JSON:
            path = data_dir / name
            if not path.exists():
                problems.append(f"missing {path.relative_to(root)}")
            elif name.endswith(".parquet") and _is_lfs_pointer(path):
                problems.append(f"{path.relative_to(root)} is a Git LFS pointer; run `git lfs pull`")
        if problems:
            raise ReleaseUnavailable("; ".join(problems))
        self.data_dir = data_dir
        self.profiles = json.loads((data_dir / "profiles.json").read_text())
        self.version = self.profiles["version"]
        if pointer.get("version") and pointer["version"] != self.version:
            raise ReleaseUnavailable(f"Pointer version {pointer['version']} != profiles version {self.version}")
        self.pointer = pointer
        provenance = json.loads((data_dir / "provenance.json").read_text())
        self.grids = {b: provenance["bodies"][b]["grid"] for b in ("earth", "moon", "mars")}
        registry = json.loads((data_dir / "feature_registry.json").read_text())
        wanted = set(CORE) | set(FEATURE_LABELS)
        self.features = {}
        for body, entry in registry["bodies"].items():
            feats = entry["features"]
            items = feats.items() if isinstance(feats, dict) else ((f["name"], f) for f in feats)
            self.features[body] = {name: {k: f.get(k) for k in ("units", "description", "source", "native_resolution", "period",
                                                               "measurement_type", "coverage_area_frac")}
                                   | {"label": FEATURE_LABELS.get(name, name)}
                                   for name, f in items if name in wanted}
        index_path = prepared / pointer["app_index"] if pointer.get("app_index") else None
        self.cases = json.loads(index_path.read_text()) if index_path and index_path.exists() else None
        self.cases_dir = index_path.parent if self.cases else None
        targets = data_dir / "targets.json"
        self.named_targets = json.loads(targets.read_text())["targets"] if targets.exists() else []

    def profile_summaries(self):
        out = []
        for pid, p in self.profiles["profiles"].items():
            item = {"id": pid, "status": p["status"], "available": p["status"] == "experimental_available"}
            if item["available"]:
                item.update({k: p.get(k) for k in ("name", "purpose", "minimum_fit", "default_separation_km",
                                                    "earth_target_area_ratio", "limitations", "earth_environment_rules")})
                item["features"] = p["features"]
                item["land_cover_screened"] = bool(p.get("land_cover_screened", False))
                item["aridity_screened"] = bool(p.get("aridity_screened", False))
                item["environment_evidence"] = p.get("environment_evidence", {})
            else:
                item["missing_evidence"] = p.get("missing", [])
            out.append(item)
        return out


_release = None
_release_error = None
_release_lock = threading.Lock()


def get_release():
    global _release, _release_error
    with _release_lock:
        if _release is None and _release_error is None:
            try:
                _release = Release()
            except (ReleaseUnavailable, OSError, KeyError, ValueError) as e:
                _release_error = str(e)
                log.error("TerraTwin release unavailable: %s", e)
    if _release is None:
        raise HTTPException(503, {"error": "release_unavailable", "detail": _release_error})
    return _release


def reset_release():  # tests
    global _release, _release_error
    with _release_lock:
        _release, _release_error = None, None


_learned = None
_learned_error = None


def get_learned():
    """Optional experimental S1 index (prepared/ml_0.3.0, fetched with `python -m ml.serve fetch`).
    Absent or broken -> None; searches then fall back to physical ranking, never fail."""
    global _learned, _learned_error
    with _release_lock:
        if _learned is None and _learned_error is None:
            try:
                from ml.serve import LearnedIndex, NPZ
                _learned = LearnedIndex(NPZ) if NPZ.exists() else None
                _learned_error = None if _learned else "index not installed (python -m ml.serve fetch)"
            except Exception as e:  # noqa: BLE001 - model failure must degrade to the physical method
                _learned_error = f"index failed to load: {type(e).__name__}"
                log.error("learned index unavailable: %s", e)
    return _learned


LEARNED_CAVEAT = ("Experimental: a self-supervised terrain-shape model reorders only candidates that already pass the "
                  "physical screen. Learned similarity is not accuracy, confidence or suitability, and it has not been "
                  "validated against reviewed analog judgments.")


_search_slots = threading.BoundedSemaphore(MAX_CONCURRENT_SEARCHES)
_dem_status = lambda: {"available": False, "detail": "lunar DEM telemetry not configured"}  # noqa: E731


def set_dem_status_provider(fn):
    """The imagery/DEM server registers how to report optional lunar telemetry availability."""
    global _dem_status
    _dem_status = fn


# ---------------------------------------------------------------- request contract
_strict_float = dict(strict=False, allow_inf_nan=False)


class Origin(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lat: float = Field(ge=-90, le=90, **_strict_float)
    lon: float = Field(ge=-540, le=540, **_strict_float)

    @field_validator("lat", "lon", mode="before")
    @classmethod
    def numbers_only(cls, v):
        return _number(v)


def _number(v):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise ValueError("must be a JSON number")
    return v


class SearchRequest(BaseModel):
    """Body of POST /api/v1/search. Unknown fields are rejected."""
    model_config = ConfigDict(extra="forbid")
    body: Literal["moon", "mars"]
    lat: float = Field(ge=-90, le=90, **_strict_float)
    lon: float = Field(ge=-540, le=540, description="East-positive; aliases such as 257.5 normalize to −102.5", **_strict_float)
    profile: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    limit: int = Field(default=10, ge=1, le=MAX_LIMIT, strict=True)
    origin: Optional[Origin] = None
    radius_km: Optional[float] = Field(default=None, ge=0, le=MAX_RADIUS_KM, **_strict_float)
    weights: Optional[dict[str, float]] = None
    ranking: Literal["physical", "learned_experimental"] = "physical"

    @field_validator("lat", "lon", "radius_km", mode="before")
    @classmethod
    def numbers_only(cls, v):
        return v if v is None else _number(v)

    @field_validator("weights")
    @classmethod
    def finite_weights(cls, v):
        if v is None:
            return v
        if not v or len(v) > 8:
            raise ValueError("weights must name 1–4 scored features")
        for name, w in v.items():
            if not math.isfinite(w) or w < 0 or w > 100:
                raise ValueError(f"weight for {name} must be finite and within [0, 100]")
        return v

    @model_validator(mode="after")
    def radius_needs_origin(self):
        if self.radius_km is not None and self.origin is None:
            raise ValueError("radius_km requires an origin")
        return self


def install_error_handlers(app):
    """422 responses list field locations and messages only. Rejected values are never echoed: they may be
    non-finite (unserializable) or a private travel origin."""
    @app.exception_handler(RequestValidationError)
    async def _bounded_validation(_request, exc):
        detail = [{"loc": [str(x) for x in e.get("loc", ())][:6], "msg": str(e.get("msg", "invalid"))[:200]}
                  for e in exc.errors()[:10]]
        return JSONResponse(status_code=422, content={"error": "validation_error", "detail": detail})


def _validation_error(message, field=None):
    return JSONResponse(status_code=422, content={"error": "validation_error",
                                                  "detail": [{"loc": [field] if field else [], "msg": message}]})


# ---------------------------------------------------------------- routes
router = APIRouter(prefix="/api/v1")


@router.get("/health")
def health():
    """Liveness plus readiness of the scientific release (imagery/DEM availability is reported separately)."""
    try:
        release = get_release()
        ready, detail = True, {"dataset_version": release.version, "data_directory": release.data_dir.name}
    except HTTPException as e:
        ready, detail = False, e.detail
    return JSONResponse(status_code=200 if ready else 503,
                        content={"status": "ready" if ready else "unavailable", "api_version": API_VERSION,
                                 "release": detail, "lunar_dem": _dem_status(), "search_slots": MAX_CONCURRENT_SEARCHES})


@router.get("/meta")
def meta():
    release = get_release()
    caveats = (release.cases or {}).get("required_visible_caveats", [])
    return {"api_version": API_VERSION, "dataset_version": release.version,
            "release_status": release.pointer.get("status"),
            "score": {"label": SCORE_LABEL, "explanation": SCORE_EXPLANATION, "range": [0, 100]},
            "required_caveats": caveats, "profiles": release.profile_summaries(),
            "core_terrain": CORE, "features": release.features, "grids": release.grids,
            "examples": EXAMPLES, "named_targets": release.named_targets, "investigations": INVESTIGATIONS,
            "limits": {"max_limit": MAX_LIMIT, "max_radius_km": MAX_RADIUS_KM},
            "learned_ranking": {"available": get_learned() is not None, "detail": _learned_error, "caveat": LEARNED_CAVEAT,
                                "version": (get_learned().meta.get("version") if get_learned() else None)},
            "historical_epochs": {"landcover": "2017", "aridity": "1970–2000", "vegetation": "2001–2017"}}


@router.get("/target")
def target(body: Literal["moon", "mars"], lat: float = Query(ge=-90, le=90), lon: float = Query(ge=-540, le=540)):
    """Resolve a planetary coordinate to its containing native cell, with eligibility per available profile."""
    release = get_release()
    if not (math.isfinite(lat) and math.isfinite(lon)):
        return _validation_error("coordinates must be finite")
    with duckdb.connect() as db:
        try:
            row, resolved = resolve_target(db, release.data_dir, body, lat, lon)
        except ValueError as e:
            return _validation_error(str(e))
    eligibility = {}
    for p in release.profile_summaries():
        if p["available"]:
            column = release.profiles["profiles"][p["id"]].get("target_eligibility_column",
                                                                release.profiles["profiles"][p["id"]]["eligibility_column"])
            eligibility[p["id"]] = bool(row[column])
    grid = release.grids[body]
    resolved.update({"label": "Regional cell containing this point", "terrain_eligible": eligibility,
                     "missing_terrain": [f for f in CORE if row[f] is None],
                     "dem_valid_frac": row.get("dem_valid_frac"),
                     "grid": {"res_deg": grid["res_deg"], "cell_size_km_at_equator": grid["cell_size_km_at_equator"]},
                     "feature_sources": {f: release.features.get(body, {}).get(f) for f in CORE}})
    return {"dataset_version": release.version, "target": _clean(resolved)}


@router.post("/search")
def run_search(request: SearchRequest):
    """Run the selected-release engine. Sync route: FastAPI executes it in a worker thread, off the event loop."""
    release = get_release()
    profiles = release.profiles["profiles"]
    if request.profile not in profiles:
        return _validation_error(f"Unknown profile '{request.profile}'", "profile")
    if request.weights is not None:
        scored = set(profiles[request.profile].get("features", {}))
        unknown = set(request.weights) - scored
        if unknown:
            return _validation_error(f"weights may only name scored features {sorted(scored)}", "weights")
    if not _search_slots.acquire(timeout=SEARCH_QUEUE_TIMEOUT_S):
        raise HTTPException(503, {"error": "busy", "detail": "Search capacity exhausted; retry shortly."})
    started = time.perf_counter()
    learned = get_learned() if request.ranking == "learned_experimental" else None
    try:
        origin = (request.origin.lat, request.origin.lon) if request.origin else None
        result = search(request.body, request.lat, request.lon, data_dir=release.data_dir, profile=request.profile,
                        limit=request.limit, origin=origin, radius_km=request.radius_km, weight_overrides=request.weights,
                        similarity=learned.similarity if learned else None)
    except ValueError as e:  # engine-level input rejection (e.g. no cell, invalid weights): still a client error
        return _validation_error(str(e))
    except Exception:  # never echo internals or the private origin
        log.exception("search failed (body=%s profile=%s)", request.body, request.profile)
        raise HTTPException(500, {"error": "service_error", "detail": "The search engine failed unexpectedly."})
    finally:
        _search_slots.release()
    lat, lon = normalize_location(request.lat, request.lon)
    result["request"] = {"body": request.body, "lat": lat, "lon": lon, "lon_as_supplied": request.lon,
                         "profile": request.profile, "limit": request.limit, "radius_km": request.radius_km,
                         "origin_supplied": origin is not None, "weights": request.weights, "ranking": request.ranking}
    if request.ranking == "learned_experimental":
        if learned is None:
            result.update({"ranking_method": "physical_terrain_fit", "learned_status": "index_unavailable"})
        result["learned_caveat"] = LEARNED_CAVEAT
        result["learned_index_version"] = learned.meta.get("version") if learned else None
    result["api_version"] = API_VERSION
    result["score_label"] = SCORE_LABEL
    result["served_at_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result["service_elapsed_seconds"] = time.perf_counter() - started
    if result.get("target"):
        result["target"]["label"] = "Regional cell containing this point"
    return _clean(result)


@router.get("/cases")
def cases():
    """Saved release fixtures for offline demonstration. Always labeled as saved, never as a fresh query."""
    release = get_release()
    if not release.cases:
        raise HTTPException(404, {"error": "no_saved_cases"})
    return {"dataset_version": release.cases["version"], "created_utc": release.cases["created_utc"], "saved_fixture": True,
            "cases": [{k: c[k] for k in ("id", "title", "status", "candidate_count")} for c in release.cases["cases"]]}


@router.get("/cases/{case_id}")
def case(case_id: str):
    release = get_release()
    entry = next((c for c in (release.cases or {}).get("cases", []) if c["id"] == case_id), None)
    if entry is None:
        raise HTTPException(404, {"error": "unknown_case"})
    query = json.loads((release.cases_dir / entry["query"]).read_text())
    earth = json.loads((release.cases_dir / entry["earth_geojson"]).read_text())
    query["candidates"] = [{**f["properties"], "geometry": f["geometry"]} for f in earth["features"]]
    query["saved_fixture"] = {"case_id": case_id, "title": entry["title"], "created_utc": release.cases["created_utc"],
                              "notice": "Saved example from the release fixtures; not a newly executed query."}
    query["score_label"] = SCORE_LABEL
    return query


@router.get("/evidence/{investigation}/{name}")
def evidence(investigation: str, name: str):
    rel = EVIDENCE.get((investigation, name))
    if rel is None:
        raise HTTPException(404, {"error": "not_public"})
    path = ROOT / rel
    if not path.exists():
        raise HTTPException(404, {"error": "evidence_missing"})
    return FileResponse(path, media_type=MEDIA[path.suffix], headers={"Cache-Control": "public, max-age=3600"})


def _clean(value):
    """JSON-safe copy: NaN/inf become null rather than fabricated numbers."""
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, "item") and not isinstance(value, (str, bytes)):  # NumPy scalar
        return _clean(value.item())
    return value

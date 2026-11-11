"""TerraTwin server: globe imagery/lunar-DEM explorer plus the analog-search API (terratwin_service).

Run from the repository root:  .venv/bin/uvicorn --app-dir frontend app:app --port 8000
Files resolve relative to this module, so the working directory does not matter.
Environment: TERRATWIN_PREWARM=0 disables background tile prewarming; TERRATWIN_FETCH_LABELS=0 skips the
Gazetteer download; TERRATWIN_LDEM overrides the lunar DEM path. The DEM is optional: without it, analog
search still works and only lunar point telemetry is unavailable.
"""
import http.client
import io
import json
import os
import struct
import threading
import urllib.parse
import urllib.request
import warnings
import zipfile
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import from_bounds, rowcol
from rasterio.windows import Window
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from PIL import Image, ImageFilter
from matplotlib import colormaps

import terratwin_service

HERE = Path(__file__).resolve().parent
# ldem_64 = 64 px/deg (~474 m/px). ldem_16 is intentionally not used.
LDEM_URL = "https://svs.gsfc.nasa.gov/vis/a000000/a004700/a004720/ldem_64.tif"
TIF = Path(os.environ.get("TERRATWIN_LDEM", HERE / "ldem_64.tif"))
READ_LOCK = threading.Lock()  # GDAL dataset handles are not thread-safe; FastAPI runs sync routes in a pool
dataset = None
W = H = TRANSFORM = M_PER_PX = IS_KM = None
DEM_ERROR = None


def open_dem():
    """Open the lunar DEM once. Missing/unreadable DEM disables only lunar point telemetry."""
    global dataset, W, H, TRANSFORM, M_PER_PX, IS_KM, DEM_ERROR
    if dataset is not None or DEM_ERROR is not None:
        return dataset
    if not TIF.exists():
        DEM_ERROR = f"{TIF.name} not found in {TIF.parent}; download it from {LDEM_URL}"
        print(f"Lunar telemetry disabled: {DEM_ERROR}")
        return None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", rasterio.errors.NotGeoreferencedWarning)
            ds = rasterio.open(TIF)
        W, H = ds.width, ds.height
        # CGI Moon Kit LDEMs ship without a geotransform: they are global equirectangular,
        # -180..180 lon, 90..-90 lat (verified: max elev lands at 5.4N,158.6W = known lunar high point).
        TRANSFORM = ds.transform if ds.crs else from_bounds(-180, -90, 180, 90, W, H)
        M_PER_PX = 2 * np.pi * 1737400 / W  # 1895.1 m at 16 px/deg, 473.8 m at 64 px/deg
        # Detect units on a coarse nearest-neighbour peek (touches only a few scanlines, not the whole 1 GB file)
        IS_KM = np.nanmax(np.abs(ds.read(1, out_shape=(360, 720)))) < 50
        dataset = ds
        print(f"Loaded DEM: {TIF.name} ({W}x{H} px, {M_PER_PX:.1f} m/px)")
    except rasterio.errors.RasterioError as e:
        DEM_ERROR = f"{TIF.name} unreadable: {e}"
        print(f"Lunar telemetry disabled: {DEM_ERROR}")
    return dataset


def dem_status():
    return {"available": dataset is not None, "source": TIF.name,
            "m_per_px": round(M_PER_PX, 1) if dataset is not None else None, "detail": DEM_ERROR}


def to_m(a):
    return a * 1000.0 if IS_KM else (a - 20000) * 0.5  # km -> m (CGI Moon Kit), else LOLA DN -> m


def build_textures():
    if (HERE / "lunar_bumpmap.png").exists() and (HERE / "lunar_hypsometric.png").exists() or dataset is None:
        return
    elev = to_m(dataset.read(1, out_shape=(2048, 4096), resampling=Resampling.average).astype(np.float32))
    lo, hi = np.nanpercentile(elev, [0.5, 99.5])
    norm = np.clip((elev - lo) / (hi - lo), 0, 1)
    Image.fromarray((norm * 255).astype(np.uint8), "L").save(HERE / "lunar_bumpmap.png")
    rgb = (colormaps["turbo"](norm)[..., :3] * 255).astype(np.uint8)
    Image.fromarray(rgb, "RGB").save(HERE / "lunar_hypsometric.png")
    print(f"Generated textures from {TIF.name} (elev range p0.5..p99.5: {lo:.0f}..{hi:.0f} m)")


MARS_TIF = HERE / "Mars_Viking_ClrMosaic_global_925m.tif"  # RGB imagery only (no elevation), global -180..180


def build_mars_texture():
    if (HERE / "mars_viking.jpg").exists() or not MARS_TIF.exists():
        return
    with rasterio.open(MARS_TIF) as src:
        rgb = src.read((1, 2, 3), out_shape=(3, 2048, 4096), resampling=Resampling.average)
    Image.fromarray(np.moveaxis(rgb, 0, -1), "RGB").save(HERE / "mars_viking.jpg", quality=92)
    print(f"Generated mars_viking.jpg from {MARS_TIF.name}")


GAZETTEER = "https://asc-planetarynames-data.s3.us-west-2.amazonaws.com/{}_nomenclature_center_pts.zip"  # USGS/IAU names
SKIP_CODES = {"SF", "AL"}  # 7k lettered satellite craters ("Marco Polo P") and pre-spacecraft albedo names


def read_dbf(raw):
    """Rows of a dBASE III table (a shapefile's attribute table) as dicts of stripped strings."""
    n, header_len, row_len = struct.unpack("<4xIHH", raw[:12])
    fields = [(raw[i:i + 11].split(b"\0")[0].decode(), raw[i + 16]) for i in range(32, header_len - 1, 32)]
    for r in range(n):
        rec = raw[header_len + r * row_len:header_len + (r + 1) * row_len]
        if rec[:1] == b"*":  # deleted record
            continue
        row, p = {}, 1
        for name, size in fields:
            row[name] = rec[p:p + size].decode("utf-8").strip()
            p += size
        yield row


def build_labels():
    for body in ("moon", "mars"):
        path = HERE / f"labels_{body}.json"
        if path.exists():
            continue
        try:
            with urllib.request.urlopen(GAZETTEER.format(body.upper()), timeout=120) as r:
                raw = zipfile.ZipFile(io.BytesIO(r.read())).read(f"{body.upper()}_nomenclature_center_pts.dbf")
        except OSError as e:  # labels are optional: the globe works without them, retried on next start
            print(f"Skipping {path.name}: Gazetteer download failed ({e})")
            continue
        feats = [[f["clean_name"], round(float(f["center_lat"]), 3), round((float(f["center_lon"]) + 180) % 360 - 180, 3),
                  round(float(f["diameter"]), 1)]
                 for f in read_dbf(raw) if f["code"] not in SKIP_CODES and float(f["diameter"] or 0) > 0]
        feats.sort(key=lambda f: -f[3])  # largest first: the page labels the biggest features that fit on screen
        with open(path, "w") as out:
            json.dump(feats, out, separators=(",", ":"))
        print(f"Generated {path.name} ({len(feats)} named features)")


def _window(row, col, half_rows, half_cols):
    r0, r1 = max(0, row - half_rows), min(H, row + half_rows + 1)
    with READ_LOCK:
        strip = dataset.read(1, window=Window(0, r0, W, r1 - r0))  # full-width rows so longitude can wrap
    rows = np.clip(np.arange(row - half_rows, row + half_rows + 1), 0, H - 1) - r0
    cols = np.arange(col - half_cols, col + half_cols + 1) % W
    return to_m(strip[np.ix_(rows, cols)].astype(np.float64))


def sample_ldem(lat, lng):
    if open_dem() is None:
        raise HTTPException(503, {"error": "lunar_dem_unavailable", "detail": DEM_ERROR})
    lng = ((lng + 180) % 360) - 180
    row, col = rowcol(TRANSFORM, lng, lat)
    row = int(np.clip(row, 0, H - 1))
    col = int(col) % W

    patch = _window(row, col, 2, 2)
    dx = M_PER_PX * max(0.12, np.cos(np.radians(lat)))  # E-W pixel shrinks toward the poles
    gy, gx = np.gradient(patch, M_PER_PX, dx)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    profile = _window(row, col, 0, 10)[0]

    return {
        "lat": round(lat, 4),
        "lng": round(lng, 4),
        "elev_m": round(float(patch[2, 2]), 1),
        "slope_deg": round(float(slope.mean()), 2),
        "roughness_m": round(float(patch.std()), 1),
        "profile": [round(float(v), 1) for v in profile],
        "profile_step_km": round(dx / 1000, 3),
        "source": TIF.name,
        "m_per_px": round(M_PER_PX, 1),
    }


SITES = {
    # Approximate region centers (Artemis III regions per NASA 2024 update).
    "moon": [
        ("Mons Mouton", "artemis", -84.50, 31.20),
        ("Nobile Rim 1", "artemis", -85.40, 37.70),
        ("Nobile Rim 2", "artemis", -83.90, 58.10),
        ("Slater Plain", "artemis", -87.80, 118.00),
        ("Malapert Massif", "artemis", -86.00, 2.90),
        ("de Gerlache Rim 2", "artemis", -88.40, -68.00),
        ("Peak Near Shackleton", "artemis", -88.80, 123.60),
        ("Peak Near Cabeus B", "artemis", -82.20, -54.00),
        ("Mare Tranquillitatis Pit", "lavatube", 8.335, 33.222),
        ("Marius Hills Pit", "lavatube", 14.091, -56.800),
        ("Apollo 16", "apollo", -8.973, 15.500),
        ("Apollo 17", "apollo", 20.191, 30.772),
    ],
    # Rover landing points (planetocentric, east-positive); ice zones are Gazetteer region centers.
    "mars": [
        ("Jezero Crater (Perseverance)", "landing", 18.4447, 77.4508),
        ("Gale Crater (Curiosity)", "landing", -4.5895, 137.4417),
        ("Utopia Planitia (Zhurong)", "landing", 25.066, 109.925),
        ("Elysium Planitia (InSight)", "landing", 4.502, 135.623),
        ("Meridiani Planum (Opportunity)", "landing", -1.9462, -5.5266),
        ("Gusev Crater (Spirit)", "landing", -14.5684, 175.4726),
        ("Arcadia Planitia", "icebase", 49.02, -171.85),
        ("Deuteronilus Mensae", "icebase", 45.11, 23.92),
        ("Erebus Montes", "icebase", 35.66, -174.98),
    ],
    # Well-studied analogs: the baseline that newly discovered candidates are compared against.
    "earth": [
        ("Haughton Crater, Devon Island", "analog", 75.367, -89.683),
        ("Atacama Desert (Yungay)", "analog", -24.083, -69.933),
        ("McMurdo Dry Valleys", "analog", -77.517, 161.833),
        ("Death Valley (Badwater)", "analog", 36.229, -116.767),
        ("Mars Desert Research Station", "analog", 38.406, -110.792),
        ("Mauna Kea", "analog", 19.821, -155.468),
        ("Kilauea", "analog", 19.421, -155.287),
        ("Rio Tinto", "analog", 37.69, -6.59),
        ("Lanzarote (Timanfaya)", "analog", 29.0, -13.75),
        ("Meteor Crater", "analog", 35.027, -111.022),
    ],
}

_STOP = threading.Event()  # set at shutdown so the prewarm thread stops scheduling work


@asynccontextmanager
async def lifespan(_app):
    # One-time asset generation happens at startup, not import, so tests and tools can import this module cheaply.
    open_dem()
    build_textures()
    build_mars_texture()
    if os.environ.get("TERRATWIN_FETCH_LABELS", "1") != "0":
        build_labels()
    try:
        terratwin_service.get_release()  # fail loudly in the log, but keep serving imagery + a 503 readiness state
    except HTTPException:
        pass
    if os.environ.get("TERRATWIN_PREWARM", "1") != "0":
        threading.Thread(target=_prewarm, daemon=True).start()
    yield
    _STOP.set()


app = FastAPI(title="TerraTwin", lifespan=lifespan)
terratwin_service.set_dem_status_provider(dem_status)
terratwin_service.install_error_handlers(app)
app.include_router(terratwin_service.router)

# Equirectangular WMTS sources: level L is 2^(L+1) x 2^L tiles, -180..180 / 90..-90 (incl. poles).
TILE_SOURCES = {
    # JAXA SELENE Kaguya Terrain Camera ortho mosaic via NASA Moon Trek; real data ends at L10 (~21 m/px)
    "moon": ("https://trek.nasa.gov/tiles/Moon/EQ/Kaguya_TCortho_Mosaic_Global_4096ppd/1.0.0/default/default028mm/{z}/{r}/{c}.png", 10),
    # MRO CTX global mosaic (Caltech Murray Lab, 5 m/px) hosted by Esri; L12 ~ 5 m/px
    "mars": ("https://astro.arcgis.com/arcgis/rest/services/OnMars/CTX/MapServer/tile/{z}/{r}/{c}", 12),
}


_FETCH_POOL = ThreadPoolExecutor(32)  # fetch both halves of a tile concurrently
_CONNS = threading.local()  # keep-alive HTTPS connection per thread+host: skips the ~0.55 s TLS handshake per tile


def _http_get(url):
    u = urllib.parse.urlsplit(url)
    conns = _CONNS.__dict__.setdefault("by_host", {})
    for attempt in (0, 1):  # a pooled connection the server already closed fails once; retry on a fresh one
        conn = conns.get(u.netloc) or http.client.HTTPSConnection(u.netloc, timeout=20)
        conns[u.netloc] = conn
        try:
            conn.request("GET", u.path, headers={"User-Agent": "lunar-ldem-explorer/1.0"})
            r = conn.getresponse()
            return r.status, r.read()
        except (http.client.HTTPException, OSError):
            conn.close()
            conns.pop(u.netloc, None)
            if attempt:
                raise


def _fetch_tile(url):
    status, body = _http_get(url)
    if status == 404:
        return None
    if status != 200:
        raise OSError(f"upstream HTTP {status} for {url}")
    return Image.open(io.BytesIO(body)).convert("RGBA")  # alpha 0 = no data


def _stitch(template, z, x, y):
    # globe.gl's equirectangular grid is 2^z x 2^z tiles, each = two side-by-side WMTS tiles at the same level
    halves = list(_FETCH_POOL.map(_fetch_tile, [template.format(z=z, r=y, c=2 * x + i) for i in (0, 1)]))
    if halves == [None, None]:
        return None
    size = next(h.size for h in halves if h)
    out = Image.new("RGBA", (size[0] * 2, size[1]))  # a missing half stays transparent (= no data)
    for i, h in enumerate(halves):
        if h:
            out.paste(h, (i * size[0], 0))
    return out


VIKING_TILES = ("https://trek.nasa.gov/tiles/Mars/EQ/Mars_Viking_MDIM21_ClrMosaic_global_232m/1.0.0/default/default028mm/{z}/{r}/{c}.jpg", 7)  # real data ends at L7
_viking = lru_cache(maxsize=128)(lambda z, x, y: _stitch(VIKING_TILES[0], z, x, y))  # parents are shared by many tiles


def _fill_gaps(im, radius=24):
    # Kaguya has no-data holes (alpha 0, up to ~15% near the poles); fill them from blurred surrounding terrain
    a = np.asarray(im)
    valid = a[..., 3] > 0
    if valid.all() or not valid.any():
        return im
    mask = Image.fromarray(valid.astype(np.uint8) * 255)
    rgb = Image.fromarray(np.where(valid[..., None], a[..., :3], 0).astype(np.uint8))
    num = np.asarray(rgb.filter(ImageFilter.GaussianBlur(radius)), np.float32)
    den = np.asarray(mask.filter(ImageFilter.GaussianBlur(radius)), np.float32)[..., None] / 255
    mean = a[..., :3][valid].mean(axis=0)
    fill = np.where(den > 0.01, num / np.maximum(den, 0.01), mean)  # holes wider than the blur get the tile mean
    return Image.fromarray(np.where(valid[..., None], a[..., :3], fill).clip(0, 255).astype(np.uint8))


def _colorize_mars(ctx, z, x, y):
    # CTX is grayscale and contrast-normalised per strip: keep Viking's color/albedo, add CTX's high-frequency detail
    vz = min(z, VIKING_TILES[1])
    f = 2 ** (z - vz)
    color = _viking(vz, x // f, y // f)
    if color is None:
        return ctx
    w, h = color.size
    box = ((x % f) * w / f, (y % f) * h / f, (x % f + 1) * w / f, (y % f + 1) * h / f)
    color = np.asarray(color.convert("RGB").resize(ctx.size, Image.BILINEAR, box=box), np.float32)
    pan_img = ctx.convert("L")
    pan = np.asarray(pan_img, np.float32)
    low = np.asarray(pan_img.filter(ImageFilter.GaussianBlur(2 * f * ctx.size[0] / 1024)), np.float32)
    lum = np.maximum(color.mean(axis=2), 1)
    # a=0 at Viking resolution (keep its albedo, add CTX detail) -> a=1 three levels deeper (CTX brightness, Viking hue)
    a = min(1.0, np.log2(f) / 3)
    ratio = (pan / np.maximum(low, 1)) * (np.maximum(low, 1) / lum) ** a
    detail = np.where(pan > 0, np.clip(ratio, 0.25, 4.0), 1.0)  # CTX gaps (0) keep Viking color
    return Image.fromarray(np.clip(color * detail[..., None], 0, 255).astype(np.uint8))


TILE_CACHE = str(HERE / "tile_cache")  # upstream NASA/Esri tiles take 2-9 s each, so every rendered tile is kept on disk


def _cached_tile(body, z, x, y):
    """Path of the rendered tile on disk (rendering + saving it first if needed), or None if upstream has no data."""
    path = os.path.join(TILE_CACHE, body, str(z), str(x), f"{y}.jpg")
    if os.path.exists(path):
        return path
    out = _stitch(TILE_SOURCES[body][0], z, x, y)
    if out is None:
        return None
    if body == "moon":
        out = _fill_gaps(out)
    if body == "mars":
        out = _colorize_mars(out, z, x, y)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.{threading.get_ident()}.tmp"
    out.convert("RGB").save(tmp, "JPEG", quality=88)
    os.replace(tmp, path)  # atomic, so a concurrent request never serves a half-written file
    return path


def _prewarm(max_level=4):
    # first view + first zoom steps of each world need levels 0-4 (~340 tiles/world, ~25 MB); fetch them in the background so the globe opens instantly
    jobs = [(b, z, x, y) for z in range(max_level + 1) for b in TILE_SOURCES for x in range(2**z) for y in range(2**z)]

    def job(j):
        if _STOP.is_set():
            return
        try:
            _cached_tile(*j)
        except Exception as e:  # upstream hiccup: the tile is simply fetched again on demand
            print(f"prewarm {j} failed: {e}")

    with ThreadPoolExecutor(8) as pool:
        list(pool.map(job, jobs))
    if not _STOP.is_set():
        print(f"Tile cache warm: levels 0-{max_level} for {', '.join(TILE_SOURCES)}")


@app.get("/tiles/{body}/{z}/{x}/{y}.jpg")
def tile(body: str, z: int, x: int, y: int):
    if body not in TILE_SOURCES or not (0 <= z <= TILE_SOURCES[body][1]) or not (0 <= x < 2**z and 0 <= y < 2**z):
        raise HTTPException(404)
    try:
        path = _cached_tile(body, z, x, y)
    except (http.client.HTTPException, OSError) as e:
        raise HTTPException(502, f"upstream tile fetch failed: {e}")
    if path is None:
        raise HTTPException(404)
    # CORS: the page spreads tile requests over localhost + 127.0.0.1 to get past the browser's 6-connection limit
    return FileResponse(path, media_type="image/jpeg",
                        headers={"Cache-Control": "public, max-age=86400", "Access-Control-Allow-Origin": "*"})


@app.get("/api/sites")
def sites(body: str = "moon"):
    if body not in SITES:
        raise HTTPException(404)
    # only the Moon has a DEM loaded; other worlds' pins (and the Moon without its DEM) carry name and position only
    telemetry = body == "moon" and open_dem() is not None
    return [{"name": n, "category": c, "lat": lat, "lng": lng, **(sample_ldem(lat, lng) if telemetry else {})}
            for n, c, lat, lng in SITES[body]]


@app.get("/api/query")
def query(lat: float = Query(..., ge=-90, le=90), lng: float = Query(..., ge=-360, le=360)):
    return sample_ldem(lat, lng)


# Public static allowlist. The frontend folder also holds the DEM, virtualenvs and caches, which must not be served.
STATIC = {"index.html": "text/html", "terratwin.js": "text/javascript", "terratwin.css": "text/css",
          "labels_moon.json": "application/json", "labels_mars.json": "application/json",
          "mars_viking.jpg": "image/jpeg", "lunar_bumpmap.png": "image/png", "lunar_hypsometric.png": "image/png"}


@app.get("/")
def index():
    return static_file("index.html")


@app.get("/{name}")
def static_file(name: str):
    if name not in STATIC or not (HERE / name).exists():
        raise HTTPException(404)
    cache = "no-cache" if name in ("index.html", "terratwin.js", "terratwin.css") else "public, max-age=86400"
    return FileResponse(HERE / name, media_type=STATIC[name], headers={"Cache-Control": cache})


if __name__ == "__main__":
    open_dem()
    if dataset is None:
        raise SystemExit(f"self-check needs the lunar DEM: {DEM_ERROR}")
    # self-check: the known lunar high point (Selenean summit) must sample near the DEM max
    s = sample_ldem(5.41, -158.63)
    assert s["elev_m"] > 10000, s
    assert len(s["profile"]) == 21
    assert sample_ldem(-90, 180)["elev_m"] == sample_ldem(-90, -180)["elev_m"]
    # labels: Shackleton sits on the south pole; Olympus Mons at 226E must come out as a negative (west) longitude
    moon_names = {n: (lat, lng) for n, lat, lng, _ in json.load(open(HERE / "labels_moon.json"))}
    mars_names = {n: (lat, lng) for n, lat, lng, _ in json.load(open(HERE / "labels_mars.json"))}
    assert moon_names["Shackleton"][0] < -89 and "Marco Polo P" not in moon_names
    assert -134 < mars_names["Olympus Mons"][1] < -133, mars_names["Olympus Mons"]
    assert {s["category"] for s in sites("mars")} == {"landing", "icebase"}
    release = terratwin_service.get_release()
    hit = terratwin_service.run_search(terratwin_service.SearchRequest(body="mars", lat=18.41, lon=77.69, profile="dry_barren_terrain"))
    assert hit["status"] == "ok" and hit["dataset_version"] == release.version and len(hit["candidates"]) == 10, hit["status"]
    print("self-check ok", TIF.name, s["elev_m"], s["slope_deg"], s["roughness_m"])

"""Metric DEM patches + physical descriptors (plan WP2/B1). Runs inside Kaggle CPU kernels.

Patch: 32x32 samples at 500 m spacing (~16 km, matching the regional cell support) on a local
tangent plane centred on each release-0.2.0 cell. Values are elevation minus patch mean (m);
absolute patch mean is kept separately as a georeferencing check. 500 m is sample spacing, not a
validated effective resolution (ETOPO 15s / MOLA 128ppd / LOLA 64ppd are all ~460-475 m).
"""
import base64, hashlib, re, subprocess, sys, time, urllib.request, zlib
from pathlib import Path
import numpy as np

SIZE, SPACING_M, MAX_ABS_LAT = 32, 500.0, 80.0  # ponytail: |lat|>80 needs polar projection; excluded
RADIUS_M = {"earth": 6371000.0, "moon": 1737400.0, "mars": 3396190.0}
GRID = {"earth": (0.125, 2880), "moon": (0.5, 720), "mars": (0.25, 1440)}  # (deg, n_lon); row 0 = north
QS = np.linspace(0.05, 0.95, 19)
PDS = {
    "mars": ["https://pds-geosciences.wustl.edu/mgs/mgs-m-mola-5-megdr-l3-v1/mgsl_300x/meg128/megt%s%s.%%s" % (la, lo)
             for la in ("88n", "44n", "00n", "44s") for lo in ("000hb", "090hb", "180hb", "270hb")],
    "moon": ["https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/cylindrical/img/ldem_64.%s"],
}
ETOPO = "https://www.ngdc.noaa.gov/mgg/global/relief/ETOPO2022/data/15s/15s_surface_elev_gtif/ETOPO_2022_v1_15s_%s%02d%s%03d_surface.tif"


def cell_centers(body, ids):
    res, n_lon = GRID[body]
    row, col = np.divmod(np.asarray(ids, np.int64), n_lon)
    return 90 - (row + 0.5) * res, -180 + (col + 0.5) * res


def split_of(body, lat, lon):
    """Immutable spatial split: 10x10 degree blocks hashed to train/val/test (70/15/15)."""
    blocks = np.c_[np.floor(np.asarray(lat) / 10), np.floor(np.asarray(lon) / 10)].astype(int)
    uniq, inv = np.unique(blocks, axis=0, return_inverse=True)
    names = []
    for a, b in uniq:
        u = int(hashlib.sha256(f"{body}:{a}:{b}".encode()).hexdigest()[:8], 16) / 2**32
        names.append("train" if u < 0.70 else "val" if u < 0.85 else "test")
    return np.array(names, "U5")[inv.ravel()]


def block_interior(body, lat, lon):
    """True when the whole patch lies inside its 10-degree block (buffer against cross-split overlap)."""
    half = np.degrees(SIZE * SPACING_M / 2 / RADIUS_M[body])
    dlon = half / np.maximum(np.cos(np.radians(lat)), 1e-3)
    fl, fo = np.mod(lat, 10), np.mod(lon, 10)
    return (fl > half) & (fl < 10 - half) & (fo > dlon) & (fo < 10 - dlon)


class Mosaic:
    """Equirectangular raster: z[row, col], row 0 at lat_top, col 0 at lon_left, ppd pixels/degree."""
    def __init__(self, z, lat_top, lon_left, ppd, scale=1.0, wrap=False):
        self.z, self.lat_top, self.lon_left, self.ppd, self.scale, self.wrap = z, lat_top, lon_left, ppd, scale, wrap

    def sample(self, lat, lon):
        H, W = self.z.shape
        r = (self.lat_top - lat) * self.ppd - 0.5
        c = np.mod(lon - self.lon_left, 360.0) * self.ppd - 0.5
        r0, c0 = np.floor(r).astype(np.int64), np.floor(c).astype(np.int64)
        fr, fc = (r - r0).astype(np.float32), (c - c0).astype(np.float32)
        bad = (r0 < 0) | (r0 >= H - 1)
        if self.wrap:
            c0, c1 = np.mod(c0, W), np.mod(c0 + 1, W)
        else:
            bad |= (c0 < 0) | (c0 >= W - 1)
            c0 = np.clip(c0, 0, W - 2)
            c1 = c0 + 1
        r0 = np.clip(r0, 0, H - 2)
        z = self.z
        v = ((z[r0, c0] * (1 - fc) + z[r0, c1] * fc) * (1 - fr) + (z[r0 + 1, c0] * (1 - fc) + z[r0 + 1, c1] * fc) * fr)
        v = v.astype(np.float32) * np.float32(self.scale)
        v[bad] = np.nan
        return v


def patch_coords(body, lat0, lon0):
    """Lat/lon of a SIZE x SIZE local tangent-plane grid (row 0 north) around each centre."""
    off = (np.arange(SIZE) - (SIZE - 1) / 2) * SPACING_M
    dy, dx = np.meshgrid(-off, off, indexing="ij")
    R = RADIUS_M[body]
    lat = lat0[:, None, None] + np.degrees(dy / R)[None]
    lon = lon0[:, None, None] + np.degrees(dx[None] / (R * np.cos(np.radians(lat))))
    return lat, lon


def descriptors(z):
    """z: [N,S,S] metric elevation (m). Returns per-patch physical descriptors at the 500 m baseline."""
    valid = np.isfinite(z).mean((1, 2))
    mean = np.nanmean(z, (1, 2))
    a = z - mean[:, None, None]
    gy, gx = np.gradient(a, SPACING_M, axis=(1, 2))
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    n = z.shape[-1]
    yy, xx = np.mgrid[:n, :n]
    A = np.c_[xx.ravel(), yy.ravel(), np.ones(n * n)]
    af = np.nan_to_num(a.reshape(len(z), -1))
    coef = np.linalg.lstsq(A, af.T, rcond=None)[0]
    rough = (af - (A @ coef).T).std(1)  # plane-detrended RMS over the 16 km window
    return {"valid_frac": valid.astype(np.float32), "elev_mean": mean.astype(np.float32),
            "relief": (np.nanmax(a, (1, 2)) - np.nanmin(a, (1, 2))).astype(np.float32),
            "rough_rms": rough.astype(np.float32),
            "slope_q": np.nanquantile(slope.reshape(len(z), -1), QS, axis=1).T.astype(np.float32),
            "hyps_q": np.nanquantile(a.reshape(len(z), -1), QS, axis=1).T.astype(np.float32)}


def _get(url, dest):
    dest = Path(dest)
    if dest.exists():
        return dest
    for attempt in range(12):
        try:
            tmp = dest.with_suffix(".part")
            with urllib.request.urlopen(url, timeout=180) as r, open(tmp, "wb") as f:
                while chunk := r.read(1 << 22):
                    f.write(chunk)
            return tmp.rename(dest)
        except Exception as e:  # transient PDS/NOAA/DNS failures
            print("retry", attempt, url, e, flush=True)
            time.sleep(min(20 * (attempt + 1), 120))
    raise RuntimeError(f"download failed: {url}")


def parse_label(text):
    def num(key, default=None):
        m = re.search(rf"^\s*{key}\s*=\s*\"?([-+0-9.Ee]+)", text, re.M)
        return float(m.group(1)) if m else default
    st = re.search(r"SAMPLE_TYPE\s*=\s*\"?(\w+)", text).group(1)
    return {"lines": int(num("LINES")), "samples": int(num("LINE_SAMPLES")),
            "dtype": (">" if st.startswith(("MSB", "SUN")) else "<") + "i2",
            "scale": num("SCALING_FACTOR", 1.0), "maxlat": num("MAXIMUM_LATITUDE"),
            "west": num("WESTERNMOST_LONGITUDE"), "ppd": num("MAP_RESOLUTION")}


def planetary_mosaic(body, work):
    tiles = []
    for tpl in PDS[body]:
        lbl = parse_label(_get(tpl % "lbl", work / Path(tpl % "lbl").name).read_text(errors="ignore"))
        img = np.fromfile(_get(tpl % "img", work / Path(tpl % "img").name), lbl["dtype"]).reshape(lbl["lines"], lbl["samples"])
        tiles.append((lbl, img))
    ppd = tiles[0][0]["ppd"]
    top = max(l["maxlat"] for l, _ in tiles)
    H = int(round(max((top - l["maxlat"]) * ppd + l["lines"] for l, _ in tiles)))
    z = np.zeros((H, int(round(360 * ppd))), np.int16)
    for l, img in tiles:
        r, c = int(round((top - l["maxlat"]) * ppd)), int(round(np.mod(l["west"], 360) * ppd))
        z[r:r + l["lines"], c:c + l["samples"]] = img
    print(body, "mosaic", z.shape, "ppd", ppd, "top", top, "west", [l["west"] for l, _ in tiles][:4],
          "scale", tiles[0][0]["scale"], flush=True)
    return Mosaic(z, top, 0.0, ppd, tiles[0][0]["scale"], wrap=True)


def earth_mosaic(lon_lo, lon_hi, work):
    try:
        import rasterio
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "rasterio"])
        import rasterio
    # 15-degree ETOPO tile columns covering the band plus one neighbour column each side.
    starts = sorted((L for L in range(-180, 180, 15) if np.mod(L - (lon_lo - 15), 360) < (lon_hi - lon_lo) + 30 - 1e-9),
                    key=lambda L: np.mod(L - (lon_lo - 15), 360))
    ppd = 240
    z = np.full((180 * ppd, len(starts) * 15 * ppd), np.nan, np.float32)
    for j, L in enumerate(starts):
        for top in range(90, -90, -15):
            url = ETOPO % ("N" if top >= 0 else "S", abs(top), "E" if L >= 0 else "W", abs(L))
            path = _get(url, work / Path(url).name)
            with rasterio.open(path) as src:
                b = src.bounds
                assert abs(b.left - L) < 1e-6 and abs(b.top - top) < 1e-6 and np.isclose(src.res[0], 1 / ppd), (url, b, src.res)
                z[(90 - top) * ppd:(105 - top) * ppd, j * 15 * ppd:(j + 1) * 15 * ppd] = src.read(1)
            path.unlink()
        print("etopo column", L, flush=True)
    return Mosaic(z, 90.0, float(starts[0]), ppd)


def build(body, cell_ids, tag, out, mosaic, n_train=0, n_eval=0, seed=0, chunk=20000):
    lat, lon = cell_centers(body, cell_ids)
    patches = np.empty((len(cell_ids), SIZE, SIZE), np.float16)
    desc = {}
    for s in range(0, len(cell_ids), chunk):
        la, lo = patch_coords(body, lat[s:s + chunk], lon[s:s + chunk])
        z = mosaic.sample(la, lo)
        d = descriptors(z)
        patches[s:s + chunk] = (z - d["elev_mean"][:, None, None]).astype(np.float16)
        for k, v in d.items():
            desc.setdefault(k, []).append(v)
        print(tag, s + len(z), "/", len(cell_ids), flush=True)
    desc = {k: np.concatenate(v) for k, v in desc.items()}
    split = split_of(body, lat, lon)
    np.savez(out / f"patches_{tag}.npz", cell_id=cell_ids.astype(np.int32), patch=patches)
    np.savez(out / f"desc_{tag}.npz", cell_id=cell_ids.astype(np.int32), split=split, **desc)
    # Sampled sets: SSL fitting (train blocks), model selection (val), held-out checks (test).
    rng = np.random.default_rng(seed)
    ok = (desc["valid_frac"] >= 0.95) & block_interior(body, lat, lon)
    for name, n in (("train", n_train), ("val", n_eval), ("test", n_eval)):
        idx = np.flatnonzero(ok & (split == name))
        idx = np.sort(rng.choice(idx, min(n, len(idx)), replace=False))
        np.savez(out / f"sample_{name}_{tag}.npz", cell_id=cell_ids[idx].astype(np.int32), patch=patches[idx])
    print("done", tag, {k: int((split == k).sum()) for k in ("train", "val", "test")}, flush=True)


def encode_ids(ids, n_cells):
    bits = np.zeros(n_cells, np.uint8)
    bits[ids] = 1
    return base64.b64encode(zlib.compress(np.packbits(bits).tobytes(), 9)).decode()


def decode_ids(blob, n_cells):
    return np.flatnonzero(np.unpackbits(np.frombuffer(zlib.decompress(base64.b64decode(blob)), np.uint8))[:n_cells])


def run(body, blob, n_cells, shard, n_shards, n_train, n_eval):
    """Kaggle entry point. Earth shards are longitude bands; Moon/Mars shard by cell_id modulo."""
    kaggle = Path("/kaggle/working").exists()
    work = Path("/kaggle/temp" if kaggle else "work")
    out = Path("/kaggle/working" if kaggle else "out")
    work.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    ids = decode_ids(blob, n_cells)
    lat, lon = cell_centers(body, ids)
    if body == "earth":
        lo = -180 + 360 / n_shards * shard
        hi = lo + 360 / n_shards
        ids = ids[(lon >= lo) & (lon < hi)]
        mosaic = earth_mosaic(lo, hi, work)
    else:
        ids = ids[ids % n_shards == shard]
        mosaic = planetary_mosaic(body, work)
    build(body, ids, f"{body}_{shard}", out, mosaic, n_train, n_eval, seed=shard)

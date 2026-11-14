"""Compact S1 retrieval index for the web service (experimental; plan WP8).

  python -m ml.serve build   # from ml_work/ encode outputs -> prepared/ml_0.3.0/s1_index.npz + s1_index.json
  python -m ml.serve fetch   # teammates/servers: download the index from the GitHub release and verify SHA-256

The index holds the S1 embeddings, reduced by PCA-64 (fitted on train-split cells only) and quantized
per vector to int8. Cosine similarity ignores per-vector scale. Recall@100 against the full 256-d float
embeddings is recorded in s1_index.json. Ranking must stay inside the physical screen
(processing.search ``similarity``).
"""
import hashlib, json, subprocess, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
INDEX_DIR = ROOT / "prepared" / "ml_0.3.0"
NPZ, META = INDEX_DIR / "s1_index.npz", INDEX_DIR / "s1_index.json"
REPO, TAG = "ikat5/mars_moon_earth_dataset", "ml-0.3.0"
DIM = 64


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def quantize(x):
    return np.round(x / np.abs(x).max(1, keepdims=True).clip(1e-12) * 127).astype(np.int8)


def unit(x):
    x = np.asarray(x, np.float32)
    return x / np.linalg.norm(x, axis=-1, keepdims=True).clip(1e-12)


class LearnedIndex:
    def __init__(self, path=NPZ):
        z = np.load(path)
        self.ids = {b: z[f"{b}_ids"] for b in ("earth", "moon", "mars")}
        self.targets = {b: z[b] for b in ("moon", "mars")}
        self.earth = unit(z["earth"])  # float32 for fast BLAS matmul (~4 bytes x 64 per Earth cell)
        self.meta = json.loads(META.read_text()) if Path(path) == NPZ and META.exists() else {}

    def similarity(self, target_row, earth_cell_ids):
        body, ids = target_row["body"], self.ids[target_row["body"]]
        i = np.searchsorted(ids, target_row["cell_id"])
        if i >= len(ids) or ids[i] != target_row["cell_id"]:
            return None
        t = unit(self.targets[body][i])
        cells = np.asarray(earth_cell_ids)
        pos = np.searchsorted(self.ids["earth"], cells).clip(0, len(self.ids["earth"]) - 1)
        ok = self.ids["earth"][pos] == cells
        out = np.full(len(cells), np.nan)
        out[ok] = self.earth[pos[ok]] @ t
        return out


def build():
    from ml.patches import cell_centers, split_of
    work = ROOT / "ml_work" / "out"
    emb = {}
    for body in ("earth", "moon", "mars"):
        parts = [np.load(p) for p in sorted(work.glob(f"terratwin-encode-{body}-*/emb_*.npz"))]
        ids = np.concatenate([p["cell_id"] for p in parts])
        order = np.argsort(ids)
        emb[body] = (ids[order], unit(np.concatenate([p["s1"] for p in parts])[order]))
    rng = np.random.default_rng(0)
    fit = []
    for body, (ids, x) in emb.items():
        tr = np.flatnonzero(split_of(body, *cell_centers(body, ids)) == "train")
        fit.append(x[rng.choice(tr, min(40000, len(tr)), replace=False)])
    fit = np.concatenate(fit)
    mean = fit.mean(0)
    comp = np.linalg.svd(fit - mean, full_matrices=False)[2][:DIM].T
    q = {b: quantize((x - mean) @ comp) for b, (_, x) in emb.items()}
    # Recall@100 of the compact index vs full float S1 for 100 Moon + 100 Mars test-split targets.
    E, Eq = emb["earth"][1], unit(q["earth"])
    rec = []
    for body in ("moon", "mars"):
        ids, x = emb[body]
        te = np.flatnonzero(split_of(body, *cell_centers(body, ids)) == "test")
        for i in rng.choice(te, 100, replace=False):
            full = set(np.argpartition(-(E @ x[i]), 100)[:100])
            rec.append(len(full & set(np.argpartition(-(Eq @ unit(q[body][i])), 100)[:100])) / 100)
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    np.savez(NPZ, mean=mean, comp=comp, **{f"{b}_ids": emb[b][0].astype(np.int32) for b in emb}, **q)
    model = work / "terratwin-ssl-train" / "s1_best.pt"
    META.write_text(json.dumps({
        "version": "ml_0.3.0", "status": "experimental_unvalidated_no_relevance_labels",
        "model": "S1 SimCLR terrain encoder (ml/models.py), best of 3 seeds", "model_sha256": sha256(model),
        "representation": f"PCA-{DIM} (fit on train-split cells) of 256-d S1 embeddings, int8 per-vector quantized; cosine similarity",
        "recall_at_100_vs_full_s1": float(np.mean(rec)), "recall_queries": len(rec),
        "counts": {b: int(len(emb[b][0])) for b in emb}, "coverage": "eligible 0.2.0 cells with |lat| <= 80",
        "file": NPZ.name, "bytes": NPZ.stat().st_size, "sha256": sha256(NPZ),
        "download": f"gh release download {TAG} -R {REPO} -p {NPZ.name} -D prepared/ml_0.3.0  (or: python -m ml.serve fetch)",
        "use": "Order Earth candidates that already pass the physical screen; never a confidence, probability or suitability score."},
        indent=1) + "\n")
    print(META.read_text())


def fetch():
    meta = json.loads(META.read_text())
    if not (NPZ.exists() and sha256(NPZ) == meta["sha256"]):
        subprocess.check_call(["gh", "release", "download", TAG, "-R", REPO, "-p", NPZ.name, "-D", str(INDEX_DIR), "--clobber"])
    assert sha256(NPZ) == meta["sha256"], "s1_index.npz checksum mismatch"
    print("ok", NPZ, meta["sha256"])


if __name__ == "__main__":
    {"build": build, "fetch": fetch}[sys.argv[1]]()

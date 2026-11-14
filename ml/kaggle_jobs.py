"""Launch/monitor/fetch the Kaggle stages across several accounts.

Tokens: one file per account in ~/.kaggle/<name>_token (KAGGLE_API_TOKEN format). Nothing secret is
written to the repo; generated kernels and fetched outputs go to ml_work/ (git-ignored).

  python -m ml.kaggle_jobs patches            # stage 1: 11 CPU kernels build DEM patches/descriptors
  python -m ml.kaggle_jobs status patches
  python -m ml.kaggle_jobs fetch patches 'desc_|sample_'
  python -m ml.kaggle_jobs train              # stage 2: GPU SimCLR seeds + F1 PCA on the main account
  python -m ml.kaggle_jobs encode             # stage 3: per-account GPU encoding of every patch shard
"""
import json, os, subprocess, sys, time
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "ml_work"
TOKENS = Path.home() / ".kaggle"
MAIN = os.environ.get("TERRATWIN_MAIN_ACCOUNT", "access")
KAGGLE = str(ROOT / ".venv" / "bin" / "kaggle")
N_CELLS = {"earth": 1440 * 2880, "moon": 360 * 720, "mars": 720 * 1440}
PATCH_JOBS = [("earth", s, 8, 4000, 1500) for s in range(8)] + [("mars", s, 2, 8000, 3000) for s in range(2)] + [("moon", 0, 1, 16000, 6000)]


def accounts():
    names = sorted(p.name[:-6] for p in TOKENS.glob("*_token"))
    return [n for n in names if n != MAIN]


def assigned():
    """(account, job) pairs. ml_work/assign.json {slug: account} moves a job, e.g. off an account without internet."""
    f = WORK / "assign.json"
    override = json.loads(f.read_text()) if f.exists() else {}
    return [(override.get(patch_slug(j[0], j[1]), a), j) for a, j in zip(accounts(), PATCH_JOBS)]


def kaggle(account, *args, check=True):
    env = {**os.environ, "KAGGLE_API_TOKEN": (TOKENS / f"{account}_token").read_text().strip()}
    r = subprocess.run([KAGGLE, *args], env=env, capture_output=True, text=True)
    if check and r.returncode:
        raise RuntimeError(f"{account}: kaggle {' '.join(args)}\n{r.stdout}{r.stderr}")
    return r.stdout


_users = {}
def username(account):
    if account not in _users:
        out = kaggle(account, "config", "view")
        _users[account] = next(l.split(":", 1)[1].strip() for l in out.splitlines() if l.strip().startswith("- username"))
    return _users[account]


def push(account, slug, code, gpu=False, internet=True, datasets=(), kernels=()):
    d = WORK / "kernels" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / "script.py").write_text(code)
    meta = {"id": f"{username(account)}/{slug}", "title": slug.replace("-", " "), "code_file": "script.py",
            "language": "python", "kernel_type": "script", "is_private": True, "enable_gpu": gpu,
            "enable_internet": internet, "dataset_sources": list(datasets), "kernel_sources": list(kernels),
            "competition_sources": [], "model_sources": []}
    if gpu:
        meta["machine_shape"] = "NvidiaTeslaT4"
    (d / "kernel-metadata.json").write_text(json.dumps(meta, indent=1))
    print(account, kaggle(account, "kernels", "push", "-p", str(d)).strip().splitlines()[-1])


def source(*mods):
    return "\n\n".join((ROOT / "ml" / f"{m}.py").read_text().replace("from ml.patches import", "# from ml.patches import")
                       for m in mods)


def patch_slug(body, shard):
    return f"terratwin-patches-{body}-{shard}"


def stage_patches(*only):
    """Push all patch jobs, or only the given slugs (e.g. to rerun failures)."""
    import duckdb
    blobs = {}
    for body in N_CELLS:
        ids = duckdb.sql(f"SELECT cell_id FROM '{ROOT}/prepared/0.2.0/{body}_features.parquet' "
                         f"WHERE eligible_terrain AND abs(lat) <= 80").fetchnumpy()["cell_id"]
        blobs[body] = (source("patches"), ids)
    from ml.patches import encode_ids
    for account, (body, shard, n, ntr, nev) in assigned():
        if only and patch_slug(body, shard) not in only:
            continue
        code, ids = blobs[body]
        call = f"\n\nrun({body!r}, {encode_ids(ids, N_CELLS[body])!r}, {N_CELLS[body]}, {shard}, {n}, {ntr}, {nev})\n"
        push(account, patch_slug(body, shard), code + call)


def jobs(stage):
    if stage == "patches":
        return [(a, patch_slug(b, s)) for a, (b, s, *_) in assigned()]
    if stage == "train":
        return [(MAIN, "terratwin-ssl-train")]
    if stage == "encode":
        return [(a, f"terratwin-encode-{b}-{s}") for a, (b, s, *_) in assigned()]
    raise SystemExit(f"unknown stage {stage}")


def status(stage):
    for a, slug in jobs(stage):
        out = kaggle(a, "kernels", "status", f"{username(a)}/{slug}", check=False).strip()
        print(f"{a:10s} {slug:32s} {out.split(' has status ')[-1] if 'status' in out else out[-120:]}")


def fetch(stage, pattern=".*"):
    for a, slug in jobs(stage):
        dest = WORK / "out" / slug
        dest.mkdir(parents=True, exist_ok=True)
        kaggle(a, "kernels", "output", f"{username(a)}/{slug}", "-p", str(dest), "--file-pattern", pattern, "-o", "-q")
        print(a, slug, sorted(p.name for p in dest.iterdir()))


def dataset(account, slug, files):
    d = WORK / "datasets" / f"{account}-{slug}"
    d.mkdir(parents=True, exist_ok=True)
    for f in files:
        target = d / Path(f).name
        if not target.exists():
            target.symlink_to(Path(f).resolve())
    (d / "dataset-metadata.json").write_text(json.dumps({"title": slug.replace("-", " "), "id": f"{username(account)}/{slug}",
                                                         "licenses": [{"name": "other"}], "isPrivate": True}))
    exists = kaggle(account, "datasets", "status", f"{username(account)}/{slug}", check=False)
    if "ready" in exists:
        kaggle(account, "datasets", "version", "-p", str(d), "-m", "update", "-r", "zip")
    else:
        kaggle(account, "datasets", "create", "-p", str(d), "-r", "zip")
    for _ in range(60):  # wait until attachable
        if "ready" in kaggle(account, "datasets", "status", f"{username(account)}/{slug}", check=False):
            return f"{username(account)}/{slug}"
        time.sleep(10)
    raise RuntimeError(f"dataset {slug} not ready on {account}")


def stage_train():
    """Merge fetched train/val/test samples into one file and launch SimCLR + F1-PCA on the main account."""
    merged = WORK / "samples"
    merged.mkdir(parents=True, exist_ok=True)
    for name in ("train", "val", "test"):
        parts = sorted((WORK / "out").glob(f"*/sample_{name}_*.npz"))
        assert len(parts) == len(PATCH_JOBS), (name, len(parts))
        ids, patch, body = [], [], []
        for p in parts:
            z = np.load(p)
            ids.append(z["cell_id"]); patch.append(z["patch"]); body += [p.stem.split("_")[2]] * len(z["cell_id"])
        np.savez(merged / f"{name}.npz", cell_id=np.concatenate(ids), patch=np.concatenate(patch), body=np.array(body))
    ds = dataset(MAIN, "terratwin-ssl-samples", [merged / f"{n}.npz" for n in ("train", "val", "test")])
    push(MAIN, "terratwin-ssl-train", source("patches", "models") + "\n\ntrain_main()\n", gpu=True, datasets=[ds])


def stage_encode():
    model_dir = WORK / "out" / "terratwin-ssl-train"
    files = [model_dir / "s1_best.pt", model_dir / "f1_pca.npz"]
    assert all(f.exists() for f in files), "fetch train outputs first"
    for a, (body, shard, *_) in assigned():
        ds = dataset(a, "terratwin-models", files)
        push(a, f"terratwin-encode-{body}-{shard}", source("models") + f"\n\nencode_main({body!r}, {shard})\n", gpu=True,
             datasets=[ds], kernels=[f"{username(a)}/{patch_slug(body, shard)}"])


if __name__ == "__main__":
    cmd, *rest = sys.argv[1:]
    {"patches": stage_patches, "train": stage_train, "encode": stage_encode, "status": status, "fetch": fetch}[cmd](*rest)

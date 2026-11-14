"""S1: small self-supervised (SimCLR) DEM encoder.  F1: frozen ImageNet ResNet18 benchmark.

Runs in Kaggle GPU kernels (source is concatenated after ml/patches.py by ml.kaggle_jobs).
Input channels from a metric elevation-anomaly patch: [z/500 m (keeps relief), slope/30 deg,
per-patch standardized z (shape only), validity mask]. Augmentations assume orientation-independent
terrain shape (rot90/flips), +-2 px shifts of a 28 px crop and 1 m noise; no vertical scaling.
"""
import json, time
from pathlib import Path
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

CROP = 28
CFG = {"epochs": 40, "batch": 512, "lr": 1e-3, "wd": 1e-4, "temperature": 0.2, "noise_m": 1.0,
       "seeds": [0, 1, 2], "eval_every": 5, "crop": CROP, "spacing_m": 500.0}
DEV = "cuda" if torch.cuda.is_available() else "cpu"


def channels(z):
    """z: [B,H,W] float elevation anomaly (m), NaN invalid -> [B,4,H,W]."""
    mask = torch.isfinite(z)
    m = mask.float()
    z = torch.nan_to_num(z)
    mean = (z * m).sum((1, 2), keepdim=True) / m.sum((1, 2), keepdim=True).clamp(min=1)
    z = (z - mean) * m
    gy, gx = torch.gradient(z, spacing=CFG["spacing_m"], dim=(1, 2))
    slope = torch.rad2deg(torch.atan(torch.hypot(gx, gy))) / 30
    std = (z.pow(2) * m).sum((1, 2), keepdim=True).div(m.sum((1, 2), keepdim=True).clamp(min=1)).sqrt()
    return torch.stack([z / 500, slope, z / (std + 1), m], 1)


def augment(z, gen):
    """Random rot90/flip, random 28 px crop (+-2 px), 1 m noise. z: [B,32,32]."""
    B, S = len(z), z.shape[-1]
    k = torch.randint(0, 4, (B,), generator=gen, device=z.device)
    out = z.clone()
    for r in range(1, 4):
        sel = k == r
        out[sel] = torch.rot90(z[sel], r, (1, 2))
    flip = torch.rand(B, generator=gen, device=z.device) < 0.5
    out[flip] = out[flip].flip(2)
    oy, ox = (torch.randint(0, S - CROP + 1, (2, B), generator=gen, device=z.device))
    ar = torch.arange(CROP, device=z.device)
    out = out[torch.arange(B, device=z.device)[:, None, None], (oy[:, None] + ar)[:, :, None], (ox[:, None] + ar)[:, None, :]]
    return out + torch.randn(out.shape, generator=gen, device=z.device) * CFG["noise_m"]


def center(z):
    o = (z.shape[-1] - CROP) // 2
    return z[:, o:o + CROP, o:o + CROP]


def conv(i, o):
    return nn.Sequential(nn.Conv2d(i, o, 3, padding=1, bias=False), nn.BatchNorm2d(o), nn.ReLU(inplace=True))


class Encoder(nn.Module):
    def __init__(self, dim=256):
        super().__init__()
        self.f = nn.Sequential(conv(4, 32), conv(32, 32), nn.MaxPool2d(2), conv(32, 64), conv(64, 64), nn.MaxPool2d(2),
                               conv(64, 128), conv(128, 128), nn.MaxPool2d(2), conv(128, dim),
                               nn.AdaptiveAvgPool2d(1), nn.Flatten())
        self.head = nn.Sequential(nn.Linear(dim, dim), nn.ReLU(inplace=True), nn.Linear(dim, 128))

    def forward(self, x):
        return self.f(channels(x))


def nt_xent(a, b, t):
    z = F.normalize(torch.cat([a, b]).float(), dim=1)
    s = z @ z.T / t
    s.fill_diagonal_(float("-inf"))
    n = len(a)
    return F.cross_entropy(s, torch.cat([torch.arange(n, 2 * n), torch.arange(n)]).to(s.device))


@torch.no_grad()
def embed(fn, patches, batch=4096, aug_seed=None):
    """fn: [B,28,28] tensor -> [B,D]. Returns L2-normalized float32 numpy."""
    gen = torch.Generator(device=DEV).manual_seed(aug_seed) if aug_seed is not None else None
    out = []
    for s in range(0, len(patches), batch):
        z = torch.from_numpy(np.asarray(patches[s:s + batch], np.float32)).to(DEV)
        z = augment(z, gen) if gen is not None else center(z)
        out.append(F.normalize(fn(z).float(), dim=1).cpu().numpy())
    return np.concatenate(out)


def invariance(fn, patches, n=5000, seed=123):
    """Held-out view retrieval: query an augmented view, find its own clean patch among n. Not analog accuracy."""
    rng = np.random.default_rng(seed)
    idx = np.sort(rng.choice(len(patches), min(n, len(patches)), replace=False))
    a, b = embed(fn, patches[idx]), embed(fn, patches[idx], aug_seed=seed)
    rank = (b @ a.T > np.sum(a * b, 1)[:, None]).sum(1)
    return {"n": int(len(idx)), "top1": float((rank == 0).mean()), "top10": float((rank < 10).mean())}


class F1:
    """Frozen ImageNet ResNet18 on [z/500, slope, standardized z] upsampled to 64 px; PCA-128 fit on train."""
    def __init__(self):
        import torchvision
        m = torchvision.models.resnet18(weights=torchvision.models.ResNet18_Weights.IMAGENET1K_V1)
        m.fc = nn.Identity()
        self.m = m.eval().to(DEV)
        self.mean = self.comp = None

    @torch.no_grad()
    def raw(self, z):
        x = channels(z)[:, :3].clamp(-3, 3)
        with torch.autocast(DEV, enabled=DEV == "cuda"):
            return self.m(F.interpolate(x, size=64, mode="bilinear", align_corners=False)).float()

    def fit_pca(self, patches, k=128):
        X = torch.from_numpy(embed(self.raw, patches)).to(DEV)
        self.mean = X.mean(0)
        self.comp = torch.linalg.svd(X - self.mean, full_matrices=False)[2][:k].T
        return self

    def __call__(self, z):
        return (self.raw(z) - self.mean) @ self.comp


def train_seed(train, val, seed):
    torch.manual_seed(seed)
    gen = torch.Generator(device=DEV).manual_seed(seed)
    model = Encoder().to(DEV)
    opt = torch.optim.AdamW(model.parameters(), CFG["lr"], weight_decay=CFG["wd"])
    steps = CFG["epochs"] * (len(train) // CFG["batch"])
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, CFG["lr"], total_steps=steps)
    scaler = torch.amp.GradScaler(enabled=DEV == "cuda")
    data = torch.from_numpy(train.astype(np.float32)).to(DEV)
    best, log = (-1, None), []
    for ep in range(CFG["epochs"]):
        model.train()
        perm = torch.randperm(len(data), generator=gen, device=DEV)
        losses = []
        for s in range(0, len(data) - CFG["batch"] + 1, CFG["batch"]):
            z = data[perm[s:s + CFG["batch"]]]
            with torch.autocast(DEV, enabled=DEV == "cuda"):
                loss = nt_xent(model.head(model(augment(z, gen))), model.head(model(augment(z, gen))), CFG["temperature"])
            opt.zero_grad(set_to_none=True)
            scaler.scale(loss).backward()
            scaler.step(opt)
            scaler.update()
            sched.step()
            losses.append(loss.item())
        if (ep + 1) % CFG["eval_every"] == 0 or ep + 1 == CFG["epochs"]:
            model.eval()
            v = invariance(model, val)
            log.append({"epoch": ep + 1, "loss": float(np.mean(losses)), "val": v})
            print(seed, log[-1], flush=True)
            if v["top1"] > best[0]:
                best = (v["top1"], {k: t.detach().cpu().clone() for k, t in model.state_dict().items()})
    return best, log


def find(name):
    return next(Path("/kaggle/input").rglob(name))


def train_main():
    t0 = time.time()
    out = Path("/kaggle/working")
    S = {n: np.load(find(f"{n}.npz")) for n in ("train", "val", "test")}
    train, val, test = (S[n]["patch"] for n in ("train", "val", "test"))
    print("samples", {n: len(S[n]["cell_id"]) for n in S}, torch.cuda.get_device_name(0) if DEV == "cuda" else DEV, flush=True)
    runs = {}
    for seed in CFG["seeds"]:
        (score, state), log = train_seed(train, val, seed)
        runs[seed] = {"best_val_top1": score, "log": log}
        torch.save(state, out / f"s1_seed{seed}.pt")
    best_seed = max(runs, key=lambda s: runs[s]["best_val_top1"])
    model = Encoder().to(DEV)
    model.load_state_dict(torch.load(out / f"s1_seed{best_seed}.pt"))
    torch.save(model.state_dict(), out / "s1_best.pt")
    f1 = F1().fit_pca(train)
    np.savez(out / "f1_pca.npz", mean=f1.mean.cpu().numpy(), comp=f1.comp.cpu().numpy())
    run = {"config": CFG, "best_seed": int(best_seed), "seeds": runs,
           "gpu": torch.cuda.get_device_name(0) if DEV == "cuda" else "cpu", "allocated_gpus": torch.cuda.device_count(),
           "train_wall_seconds": time.time() - t0, "torch": torch.__version__}
    held_out_report(out, S, run)


def held_out_report(out, S, run):
    """Held-out (test-block) view retrieval for S1, F1 and B1 descriptors; writes run.json.
    Also runnable locally: python -m ml.models <dir with s1_best.pt, f1_pca.npz> <dir with train/test.npz> [kernel.log]."""
    from ml.patches import descriptors  # commented out when concatenated for Kaggle (patches.py precedes this file)
    train, test = S["train"]["patch"], S["test"]["patch"]
    model = Encoder().to(DEV)
    model.load_state_dict(torch.load(Path(out) / "s1_best.pt", map_location=DEV))
    model.eval()
    f1, p = F1(), np.load(Path(out) / "f1_pca.npz")
    f1.mean, f1.comp = torch.from_numpy(p["mean"]).to(DEV), torch.from_numpy(p["comp"]).to(DEV)
    vec = lambda d: np.c_[d["slope_q"], d["hyps_q"], d["relief"], d["rough_rms"]]
    vtr = vec(descriptors(train[:20000].astype(np.float32)))
    mu, sd = vtr.mean(0), vtr.std(0) + 1e-6
    b1_fn = lambda z: torch.from_numpy(np.nan_to_num((vec(descriptors(z.cpu().numpy().astype(np.float32))) - mu) / sd)).float()
    held = {"note": "held-out test-block view retrieval among 5000 patches; representation sanity check, not analog relevance",
            "S1": invariance(model, test), "F1": invariance(f1, test), "B1_descriptors": invariance(b1_fn, test)}
    for body in np.unique(S["test"]["body"]):
        held[f"S1_{body}"] = invariance(model, test[S["test"]["body"] == body])
    run["held_out"] = held
    (Path(out) / "run.json").write_text(json.dumps(run, indent=1))
    print(json.dumps(held, indent=1))


def encode_main(body, shard):
    t0 = time.time()
    tag = f"{body}_{shard}"
    z = np.load(find(f"patches_{tag}.npz"))
    model = Encoder().to(DEV)
    model.load_state_dict(torch.load(find("s1_best.pt"), map_location=DEV))
    model.eval()
    f1 = F1()
    p = np.load(find("f1_pca.npz"))
    f1.mean, f1.comp = torch.from_numpy(p["mean"]).to(DEV), torch.from_numpy(p["comp"]).to(DEV)
    patches = z["patch"]
    np.savez(Path("/kaggle/working") / f"emb_{tag}.npz", cell_id=z["cell_id"],
             s1=embed(model, patches).astype(np.float16), f1=embed(f1, patches).astype(np.float16))
    print(tag, len(patches), "encoded in", time.time() - t0, "s", flush=True)


if __name__ == "__main__":
    # Local recovery of run.json from a finished training kernel's checkpoints and log.
    import ast, re, sys
    out, sample_dir = Path(sys.argv[1]), Path(sys.argv[2])
    runs = {}
    if len(sys.argv) > 3:
        text = "".join(x["data"] for x in json.loads(Path(sys.argv[3]).read_text()))
        for seed, rec in re.findall(r"^(\d+) (\{'epoch'.*\})$", text, re.M):
            runs.setdefault(int(seed), {"log": []})["log"].append(ast.literal_eval(rec))
        for r in runs.values():
            r["best_val_top1"] = max(x["val"]["top1"] for x in r["log"])
    best = max(runs, key=lambda s: runs[s]["best_val_top1"]) if runs else None
    S = {n: np.load(sample_dir / f"{n}.npz") for n in ("train", "test")}
    held_out_report(out, S, {"config": CFG, "best_seed": best, "seeds": runs, "gpu": "Tesla T4 (Kaggle; held-out report recomputed on CPU)",
                             "torch_training": "Kaggle default image", "torch_report": torch.__version__})

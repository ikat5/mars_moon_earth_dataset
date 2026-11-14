"""Compare B0/B1/U1/F1/S1 on common eligible observations (plan WP4/sec. 7). CPU, local.

No reviewed relevance labels exist, so nothing here is analog accuracy: it reports data-correctness
checks, cross-method agreement, physical mismatch of returned candidates, diversity, domain-bias
probes and search runtime. Usage: python -m ml.evaluate  (after fetching patch, train and encode outputs)
"""
import hashlib, json, time
from pathlib import Path
import duckdb
import numpy as np
from sklearn.cluster import MiniBatchKMeans
from sklearn.linear_model import LogisticRegression
from processing.search import normalized_fit, distances_km
from ml.patches import cell_centers, QS

ROOT = Path(__file__).resolve().parents[1]
WORK, DATA, OUT = ROOT / "ml_work" / "out", ROOT / "prepared" / "0.2.0", ROOT / "analysis" / "ml_0.3.0"
# B1 tolerances, declared before evaluation (sec. 5): Wasserstein-1 over 19 quantiles, original units.
B1_TOL = {"slope_w1_deg": 5.0, "hypsometry_w1_m": 250.0, "rough_rms_m": 100.0}
FIXTURES = [("jezero_center", "mars", 18.41, 77.69), ("lunar_0n_0e", "moon", 0.0, 0.0)]
K, POOL, SEP_KM, N_RANDOM = 10, 100, 100.0, 100
TABLE_COLS = ["cell_id", "area_km2", "slope_median_deg", "slope_p90_deg", "relief_m", "roughness_rms_m", "elev_mean_m"]


def load(body):
    t = duckdb.sql(f"SELECT {','.join(TABLE_COLS)} FROM '{DATA}/{body}_features.parquet' WHERE eligible_terrain").fetchnumpy()
    d, e = {}, {}
    for p in sorted(WORK.glob(f"terratwin-patches-{body}-*/desc_*.npz")):
        for k, v in np.load(p).items():
            d.setdefault(k, []).append(v)
    for p in sorted(WORK.glob(f"terratwin-encode-{body}-*/emb_*.npz")):
        for k, v in np.load(p).items():
            e.setdefault(k, []).append(v)
    d = {k: np.concatenate(v) for k, v in d.items()}
    e = {k: np.concatenate(v) for k, v in e.items()}
    assert (np.sort(d["cell_id"]) == np.sort(e["cell_id"])).all(), body
    order = np.argsort(e["cell_id"])
    e = {k: v[order] for k, v in e.items()}
    order = np.argsort(d["cell_id"])
    d = {k: v[order] for k, v in d.items()}
    pos = np.searchsorted(t["cell_id"], d["cell_id"])
    keep = d["valid_frac"] >= 0.95
    out = {k: v[keep] for k, v in d.items()}
    out.update({k: v[keep] for k, v in e.items() if k != "cell_id"})
    out.update({f"t_{k}": t[k][pos][keep] for k in TABLE_COLS if k != "cell_id"})
    out["lat"], out["lon"] = cell_centers(body, out["cell_id"])
    for m in ("s1", "f1"):
        x = out[m].astype(np.float32)
        out[m] = x / np.linalg.norm(x, axis=1, keepdims=True)
    return out


def corr(a, b):
    ok = np.isfinite(a) & np.isfinite(b)
    ra, rb = np.argsort(np.argsort(a[ok])), np.argsort(np.argsort(b[ok]))
    return {"pearson": float(np.corrcoef(a[ok], b[ok])[0, 1]), "spearman": float(np.corrcoef(ra, rb)[0, 1]), "n": int(ok.sum())}


def correctness(D):
    return {b: {"elev_mean_vs_table": corr(d["elev_mean"], d["t_elev_mean_m"]), "relief_vs_table": corr(d["relief"], d["t_relief_m"]),
                "slope_p50_vs_table": corr(d["slope_q"][:, 9], d["t_slope_median_deg"]),
                "slope_p90_vs_table": corr(d["slope_q"][:, 17], d["t_slope_p90_deg"]),
                "rough_vs_table": corr(d["rough_rms"], d["t_roughness_rms_m"]),
                "note": "patch (16 km local plane, 500 m spacing) vs release-0.2.0 cell summary; differing windows/baselines"}
            for b, d in D.items()}


def b1_score(E, i, T):
    w = [np.abs(E["slope_q"] - T["slope_q"][i]).mean(1) / B1_TOL["slope_w1_deg"],
         np.abs(E["hyps_q"] - T["hyps_q"][i]).mean(1) / B1_TOL["hypsometry_w1_m"],
         np.abs(E["rough_rms"] - T["rough_rms"][i]) / B1_TOL["rough_rms_m"]]
    return 100 * (1 - np.minimum(np.stack(w), 1).mean(0))


def b0_score(E, i, T, prof):
    f = list(prof["features"])
    x = np.column_stack([E[f"t_{k}"] for k in f]).astype(float)
    ok = np.all(np.isfinite(x), 1)
    s = np.full(len(x), -np.inf)
    s[ok] = normalized_fit(x[ok], np.array([T[f"t_{k}"][i] for k in f], float),
                           np.array([prof["features"][k]["weight"] for k in f]), np.array([prof["features"][k]["tolerance"] for k in f]))[0]
    return s


def thin(order, E, k=K):
    chosen = []
    for j in order:
        if not chosen or np.all(distances_km(E["lat"][j], E["lon"][j], E["lat"][chosen], E["lon"][chosen]) >= SEP_KM):
            chosen.append(int(j))
            if len(chosen) == k:
                break
    return np.array(chosen)


def queries(D):
    q = []
    for name, body, lat, lon in FIXTURES:
        T = D[body]
        i = int(np.argmin(distances_km(lat, lon, T["lat"], T["lon"])))
        q.append((name, body, i))
    rng = np.random.default_rng(0)
    for body in ("moon", "mars"):
        idx = np.flatnonzero(D[body]["split"] == "test")
        q += [(f"{body}_test_{int(D[body]['cell_id'][i])}", body, int(i)) for i in rng.choice(idx, N_RANDOM, replace=False)]
    return q


def compare(D, prof, clusters):
    E = D["earth"]
    lo, hi = prof["earth_target_area_ratio"]
    per, rows = {}, []
    for name, body, i in queries(D):
        T = D[body]
        area = T["t_area_km2"][i]
        cand = np.flatnonzero((E["t_area_km2"] >= area * lo) & (E["t_area_km2"] <= area * hi))
        sub = {k: v[cand] for k, v in E.items()}
        scores = {"B0": b0_score(sub, i, T, prof), "B1": b1_score(sub, i, T),
                  "F1": sub["f1"] @ T["f1"][i], "S1": sub["s1"] @ T["s1"][i]}
        pools = {m: np.argsort(-s, kind="stable")[:POOL] for m, s in scores.items()}
        tops = {m: thin(np.argsort(-s, kind="stable")[:5000], sub) for m, s in scores.items()}
        r = {"query": name, "body": body}
        for m, top in tops.items():
            r[m] = {"b0_fit_top10": float(np.mean(scores["B0"][top])), "b1_fit_top10": float(np.mean(scores["B1"][top])),
                    "abs_relief_diff_m": float(np.mean(np.abs(sub["t_relief_m"][top] - T["t_relief_m"][i]))),
                    "abs_slope_p50_diff_deg": float(np.mean(np.abs(sub["t_slope_median_deg"][top] - T["t_slope_median_deg"][i]))),
                    "jaccard100_vs_B0": len(set(pools[m]) & set(pools["B0"])) / len(set(pools[m]) | set(pools["B0"])),
                    "jaccard100_vs_B1": len(set(pools[m]) & set(pools["B1"])) / len(set(pools[m]) | set(pools["B1"])),
                    "u1_distinct_clusters_top10": int(len(np.unique(clusters["earth"][cand][top]))),
                    "u1_same_cluster_as_target_top10": float(np.mean(clusters["earth"][cand][top] == clusters[body][i]))}
        if name in dict((f[0], 1) for f in FIXTURES):
            per[name] = {"target_cell_id": int(T["cell_id"][i]),
                         "top10": {m: [{"earth_cell_id": int(sub["cell_id"][j]), "lat": float(sub["lat"][j]), "lon": float(sub["lon"][j]),
                                        "score": float(scores[m][j]), "b0_fit": float(scores["B0"][j])} for j in top] for m, top in tops.items()}}
        rows.append(r)
    summary = {}
    for scope in ("fixtures", "moon_test", "mars_test"):
        sel = [r for r in rows if (scope == "fixtures" and "_test_" not in r["query"]) or r["query"].startswith(scope)]
        summary[scope] = {m: {k: float(np.mean([r[m][k] for r in sel])) for k in sel[0][m]} for m in scores}
        summary[scope]["n_queries"] = len(sel)
    return summary, per


def vec(d):
    return np.c_[d["slope_q"], d["hyps_q"], d["relief"], d["rough_rms"]]


def cluster(D, k=32):
    """U1: MiniBatchKMeans on train-split standardized B1 descriptors pooled across bodies."""
    tr = np.concatenate([vec(d)[d["split"] == "train"] for d in D.values()])
    mu, sd = tr.mean(0), tr.std(0) + 1e-6
    km = MiniBatchKMeans(k, random_state=0, n_init=3, batch_size=8192).fit((tr - mu) / sd)
    labels = {b: km.predict((vec(d) - mu) / sd) for b, d in D.items()}
    comp = {int(c): {b: int((labels[b] == c).sum()) for b in D} for c in range(k)}
    mixed = sum(1 for c in comp.values() if sum(v > 0.05 * sum(c.values()) for v in c.values()) >= 2)
    return labels, {"k": k, "clusters_with_2plus_bodies_over_5pct": mixed, "composition": comp}


def domain_probe(D, n=5000):
    """Body predictability (chance = 1/3). High values mean the representation encodes the instrument/body."""
    rng = np.random.default_rng(0)
    res = {}
    feats = {"B1_descriptors": lambda d: vec(d), "F1": lambda d: d["f1"], "S1": lambda d: d["s1"]}
    for name, f in feats.items():
        X, y = {}, {}
        for split in ("train", "test"):
            xs, ys = [], []
            for bi, d in enumerate(D.values()):
                idx = np.flatnonzero(d["split"] == split)
                idx = rng.choice(idx, min(n, len(idx)), replace=False)
                xs.append(f(d)[idx]); ys.append(np.full(len(idx), bi))
            X[split], y[split] = np.concatenate(xs).astype(np.float32), np.concatenate(ys)
        mu, sd = X["train"].mean(0), X["train"].std(0) + 1e-6
        clf = LogisticRegression(max_iter=2000).fit((X["train"] - mu) / sd, y["train"])
        res[name] = float(clf.score((X["test"] - mu) / sd, y["test"]))
    return res


def runtime(D, n=50):
    E = D["earth"]
    out = {}
    for m in ("s1", "f1"):
        M, Q = E[m], D["mars"][m][:n]
        t = []
        for q in Q:
            s = time.perf_counter()
            np.argpartition(-(M @ q), 500)[:500]
            t.append(time.perf_counter() - s)
        out[m] = {"corpus": int(len(M)), "dim": int(M.shape[1]), "matrix_mb_float32": M.nbytes / 1e6,
                  "p50_s": float(np.percentile(t, 50)), "p95_s": float(np.percentile(t, 95)), "concurrency": 1}
    return out


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    D = {b: load(b) for b in ("earth", "moon", "mars")}
    prof = json.loads((DATA / "profiles.json").read_text())["profiles"]["terrain_screening"]
    labels, u1 = cluster(D)
    summary, fixtures = compare(D, prof, labels)
    train = WORK / "terratwin-ssl-train"
    report = {"version": "ml_0.3.0", "status": "experimental; no reviewed relevance labels; not analog accuracy",
              "data": {b: {"n_patches_valid": int(len(d["cell_id"])), "splits": {s: int((d["split"] == s).sum()) for s in ("train", "val", "test")}}
                       for b, d in D.items()},
              "b1_tolerances": B1_TOL, "correctness": correctness(D), "u1": u1, "comparison": summary,
              "domain_probe_body_accuracy": domain_probe(D), "runtime_exact_cosine": runtime(D),
              "ssl_run": json.loads((train / "run.json").read_text()),
              "artifacts_sha256": {p.name: sha(p) for p in sorted(train.glob("*.pt")) + sorted(train.glob("*.npz"))}}
    (OUT / "evaluation.json").write_text(json.dumps(report, indent=1))
    (OUT / "fixtures_top10.json").write_text(json.dumps(fixtures, indent=1))
    print(json.dumps({k: report[k] for k in ("comparison", "domain_probe_body_accuracy", "runtime_exact_cosine")}, indent=1))


if __name__ == "__main__":
    main()

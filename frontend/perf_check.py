"""Measure HTTP search latency, concurrency behaviour, response size, server memory and browser readiness.

    .venv/bin/python frontend/perf_check.py --url http://localhost:8000 --server-pid <uvicorn pid> \
        --output analysis/performance_<date>.json

"Cold" means the first request for each distinct query on a freshly started server (OS file cache state is
recorded as unknown unless you drop caches yourself). Targets are seeded pseudo-random Moon/Mars coordinates,
not presets. p95 < 2 s is a target to assess, not an assumption.
"""
import argparse
import json
import os
import platform
import random
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import httpx

p = argparse.ArgumentParser()
p.add_argument("--url", default="http://localhost:8000")
p.add_argument("--server-pid", type=int)
p.add_argument("--output", type=Path)
p.add_argument("--queries", type=int, default=40)
p.add_argument("--concurrency", type=int, default=10)
p.add_argument("--browser", action="store_true", help="also measure page readiness with Playwright/Chrome")
args = p.parse_args()

rng = random.Random(20261112)
profiles = ["dry_barren_terrain", "terrain_screening"]
queries = [{"body": rng.choice(["moon", "mars"]), "lat": round(rng.uniform(-60, 60), 4), "lon": round(rng.uniform(-180, 180), 4),
            "profile": profiles[i % 2]} for i in range(args.queries)]


def rss(pid):
    if not pid:
        return None
    out = {}
    for line in Path(f"/proc/{pid}/status").read_text().splitlines():
        if line.startswith(("VmRSS", "VmHWM")):
            k, v = line.split(":")
            out[k] = round(int(v.split()[0]) / 1024, 1)
    return out


def timed(client, q):
    t = time.perf_counter()
    r = client.post(f"{args.url}/api/v1/search", json=q, timeout=120)
    dt = time.perf_counter() - t
    body = r.json()
    return {"seconds": dt, "status_code": r.status_code, "status": body.get("status"), "bytes": len(r.content),
            "candidates": len(body.get("candidates", [])), "server_seconds": body.get("service_elapsed_seconds")}


def summary(rows):
    s = sorted(r["seconds"] for r in rows)
    pct = lambda q: s[min(len(s) - 1, int(round(q * (len(s) - 1))))]  # noqa: E731
    return {"n": len(s), "median_s": round(statistics.median(s), 3), "p95_s": round(pct(0.95), 3), "max_s": round(s[-1], 3),
            "mean_server_s": round(statistics.mean(r["server_seconds"] for r in rows if r["server_seconds"]), 3),
            "max_response_bytes": max(r["bytes"] for r in rows), "median_response_bytes": int(statistics.median(r["bytes"] for r in rows)),
            "status_counts": {k: sum(r["status"] == k for r in rows) for k in {r["status"] for r in rows}},
            "http_errors": sum(r["status_code"] != 200 for r in rows), "p95_under_2s": pct(0.95) < 2.0}


def cpu_model():
    try:
        return next(l.split(":", 1)[1].strip() for l in Path("/proc/cpuinfo").read_text().splitlines() if l.startswith("model name"))
    except (OSError, StopIteration):
        return platform.processor()


mem_total = next((int(l.split()[1]) // 1024 for l in Path("/proc/meminfo").read_text().splitlines() if l.startswith("MemTotal")), None)
report = {"measured_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
          "machine": {"cpu": cpu_model(), "logical_cpus": os.cpu_count(), "memory_mib": mem_total, "os": platform.platform(),
                      "python": platform.python_version()},
          "server": {"url": args.url, "health": httpx.get(f"{args.url}/api/v1/health").json(), "rss_mib_before": rss(args.server_pid)},
          "workload": {"queries": args.queries, "concurrency": args.concurrency, "seed": 20261112,
                       "targets": "seeded random Moon/Mars coordinates in ±60° latitude; profiles alternate",
                       "cache_state": "cold = first request per query on this server process; OS page cache not dropped"}}

with httpx.Client() as client:
    cold = [timed(client, q) for q in queries]
    warm = [timed(client, q) for q in queries]
report["cold_sequential"] = summary(cold)
report["warm_sequential"] = summary(warm)
with ThreadPoolExecutor(args.concurrency) as pool, httpx.Client(limits=httpx.Limits(max_connections=args.concurrency)) as client:
    started = time.perf_counter()
    conc = list(pool.map(lambda q: timed(client, q), queries * 2))
    wall = time.perf_counter() - started
report["concurrent"] = summary(conc) | {"wall_s": round(wall, 2), "throughput_qps": round(len(conc) / wall, 2),
                                        "note": f"{args.concurrency} client workers; server admits at most 4 searches at once (TERRATWIN_MAX_CONCURRENT_SEARCHES)"}
report["server"]["rss_mib_after"] = rss(args.server_pid)

if args.browser:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch(channel="chrome", headless=True, args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        runs = []
        for _ in range(3):
            pg = b.new_context().new_page()
            t = time.perf_counter()
            pg.goto(args.url, wait_until="domcontentloaded")
            dom = time.perf_counter() - t
            pg.wait_for_function("document.getElementById('dataVersion').textContent.includes('release')", timeout=60000)
            ready = time.perf_counter() - t
            pg.select_option("#fBody", "mars"); pg.fill("#fLat", "18.41"); pg.fill("#fLon", "77.69")
            pg.click("#coordForm button[type=submit]")
            pg.wait_for_function("TT.state.target && TT.state.target.cell", timeout=60000)
            t2 = time.perf_counter()
            pg.click("#searchBtn")
            pg.wait_for_function("TT.state.result", timeout=60000)
            search_render = time.perf_counter() - t2
            roundtrip_ms = pg.evaluate("TT.state.result.client.browser_roundtrip_ms")
            pg.wait_for_function("TT.state.reveal && TT.state.reveal.stage === 'done'", timeout=60000)
            reveal = time.perf_counter() - t2
            runs.append({"dom_content_loaded_s": round(dom, 2), "panels_ready_s": round(ready, 2),
                         "search_fetch_roundtrip_ms": roundtrip_ms,
                         "click_to_results_wall_s": round(search_render, 2), "click_to_reveal_done_wall_s": round(reveal, 2)})
            pg.context.close()
        b.close()
    report["browser"] = {"runs": runs, "note": "Headless Chrome with software WebGL. Panels-ready = release metadata loaded. "
                                               "search_fetch_roundtrip_ms is measured inside the page around fetch(). Wall times poll via the page and are "
                                               "inflated by software rendering in headless Chrome. Reveal includes ~4.5 s of intentional animation. "
                                               "Imagery tile latency is a separate external dependency."}

text = json.dumps(report, indent=1)
if args.output:
    args.output.write_text(text + "\n")
print(text)

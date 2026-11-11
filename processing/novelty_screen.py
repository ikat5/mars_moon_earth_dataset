"""Screen for recurring Earth candidates that are far from every known analog site in our inventories.

    .venv/bin/python -m processing.novelty_screen --output analysis/novelty_screen_0.2.0.json

This produces *unreviewed leads*, not discoveries. The known-site inventories available here are incomplete
(USGS portal feed: 4 volcanic records; PAAD: 45 dune fields; a few controls and globe reference pins), so a
large distance from them never establishes that a region has not been studied before.
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from processing.search import distances_km, search

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "prepared" / "0.2.0"

TARGETS = [  # (id, body, lat, lon, label) — landing points, base zones and benchmark sites already shown on the globe
    ("jezero_center", "mars", 18.41, 77.69, "Jezero crater centre"),
    ("jezero_landing", "mars", 18.4447, 77.4508, "Perseverance landing point"),
    ("gale", "mars", -4.5895, 137.4417, "Gale crater (Curiosity)"),
    ("utopia", "mars", 25.066, 109.925, "Utopia Planitia (Zhurong)"),
    ("elysium", "mars", 4.502, 135.623, "Elysium Planitia (InSight)"),
    ("meridiani", "mars", -1.9462, -5.5266, "Meridiani Planum (Opportunity)"),
    ("gusev", "mars", -14.5684, 175.4726, "Gusev crater (Spirit)"),
    ("arcadia", "mars", 49.02, -171.85, "Arcadia Planitia (ice-rich zone)"),
    ("deuteronilus", "mars", 45.11, 23.92, "Deuteronilus Mensae (ice-rich zone)"),
    ("erebus", "mars", 35.66, -174.98, "Erebus Montes (ice-rich zone)"),
    ("apollo11", "moon", 0.674, 23.473, "Apollo 11"),
    ("apollo16", "moon", -8.973, 15.5, "Apollo 16"),
    ("apollo17", "moon", 20.191, 30.772, "Apollo 17"),
    ("tranquillitatis_pit", "moon", 8.335, 33.222, "Mare Tranquillitatis pit"),
    ("marius_pit", "moon", 14.091, -56.8, "Marius Hills pit"),
    ("lunar_equator", "moon", 0.0, 0.0, "Lunar 0°N 0°E"),
    ("mons_mouton", "moon", -84.5, 31.2, "Mons Mouton (Artemis region)"),
    ("malapert", "moon", -86.0, 2.9, "Malapert Massif (Artemis region)"),
]
# Well-known analogs pinned on the globe (frontend/app.py SITES["earth"]); approximate centres.
GLOBE_ANALOGS = [
    ("Haughton Crater, Devon Island", 75.367, -89.683), ("Atacama Desert (Yungay)", -24.083, -69.933),
    ("McMurdo Dry Valleys", -77.517, 161.833), ("Death Valley (Badwater)", 36.229, -116.767),
    ("Mars Desert Research Station", 38.406, -110.792), ("Mauna Kea", 19.821, -155.468), ("Kilauea", 19.421, -155.287),
    ("Rio Tinto", 37.69, -6.59), ("Lanzarote (Timanfaya)", 29.0, -13.75), ("Meteor Crater", 35.027, -111.022),
]


def known_sites():
    sites = []
    for src, path in (("USGS analog portal feed", "sources/known_analogs/sites.geojson"),
                      ("USGS PAAD dune fields", "sources/known_analogs_paad/sites.geojson")):
        for f in json.loads((ROOT / path).read_text())["features"]:
            lon, lat = f["geometry"]["coordinates"][:2]
            p = f["properties"]
            name = p.get("Name") or p.get("Field_Site") or "unnamed"
            if p.get("Country"):
                name = f"{name}, {p['Country']}"
            sites.append({"name": str(name), "lat": float(lat), "lon": float(lon), "source": src})
    for s in json.loads((ROOT / "analysis/control_sites.json").read_text())["sites"]:
        if "negative" not in s["role"]:
            sites.append({"name": s["name"], "lat": s["lat"], "lon": s["lon"], "source": "TerraTwin predeclared controls"})
    sites += [{"name": n, "lat": la, "lon": lo, "source": "Globe reference pins (approximate)"} for n, la, lo in GLOBE_ANALOGS]
    return sites


def run(limit=10):
    sites = known_sites()
    slat, slon = np.array([s["lat"] for s in sites]), np.array([s["lon"] for s in sites])
    cells, outcomes = {}, []
    for tid, body, lat, lon, label in TARGETS:
        for profile in ("dry_barren_terrain", "terrain_screening"):
            r = search(body, lat, lon, data_dir=DATA, profile=profile, limit=limit)
            outcomes.append({"target": tid, "label": label, "profile": profile, "status": r["status"],
                             "target_cell": r.get("target", {}).get("feature_id"), "candidates": len(r["candidates"])})
            for rank, c in enumerate(r["candidates"], 1):
                cell = cells.setdefault(c["feature_id"], {"feature_id": c["feature_id"], "lat": c["lat"], "lon": c["lon"],
                                                          "area_km2": c["area_km2"], "hits": [], "context": c["earth_environment_context"]})
                cell["hits"].append({"target": tid, "body": body, "profile": profile, "rank": rank, "fit": c["observed_fit"]})
    for cell in cells.values():
        d = distances_km(cell["lat"], cell["lon"], slat, slon)
        order = np.argsort(d)[:3]
        cell["nearest_known"] = [{**sites[i], "distance_km": round(float(d[i]), 1)} for i in order]
        cell["distinct_targets"] = len({h["target"] for h in cell["hits"]})
        cell["best_fit"] = max(h["fit"] for h in cell["hits"])
        cell["dry_barren_hits"] = sum(h["profile"] == "dry_barren_terrain" for h in cell["hits"])
        nk = cell["nearest_known"][0]["distance_km"]
        cell["documentation_band"] = ("near a known site (<100 km)" if nk < 100 else
                                      "100–500 km from known sites" if nk < 500 else "over 500 km from any known site in our inventories")
    # Group nearby cells (<250 km, single linkage) into regions so one desert doesn't appear as many "leads".
    ids = sorted(cells, key=lambda k: (-cells[k]["distinct_targets"], -cells[k]["best_fit"]))
    regions = []
    for k in ids:
        c = cells[k]
        home = next((g for g in regions if any(distances_km(c["lat"], c["lon"], m["lat"], m["lon"]) < 250 for m in g["cells"])), None)
        (home["cells"].append(c) if home else regions.append({"cells": [c]}))
    out = []
    for g in regions:
        cs = g["cells"]
        targets = sorted({h["target"] for c in cs for h in c["hits"]})
        nearest = min((c["nearest_known"][0] for c in cs), key=lambda x: x["distance_km"])
        out.append({"centre": {"lat": round(float(np.mean([c["lat"] for c in cs])), 3), "lon": round(float(np.mean([c["lon"] for c in cs])), 3)},
                    "cells": len(cs), "distinct_targets": len(targets), "targets": targets,
                    "bodies": sorted({h["body"] for c in cs for h in c["hits"]}),
                    "best_fit": round(max(c["best_fit"] for c in cs), 2),
                    "dry_barren_hits": sum(c["dry_barren_hits"] for c in cs),
                    "nearest_known": nearest,
                    "documentation_band": ("near a known site (<100 km)" if nearest["distance_km"] < 100 else
                                           "100–500 km from known sites" if nearest["distance_km"] < 500 else
                                           "over 500 km from any known site in our inventories"),
                    "barren_fraction_2017": [round(c["context"].get("landcover_barren_class_fraction") or 0, 2) for c in cs][:5],
                    "aridity_index_1970_2000": [None if c["context"].get("aridity_index") is None else round(c["context"]["aridity_index"], 3) for c in cs][:5],
                    "example_cells": [c["feature_id"] for c in cs][:5]})
    out.sort(key=lambda g: (-g["distinct_targets"], -g["best_fit"]))
    return {"dataset_version": "0.2.0", "limit_per_query": limit, "known_sites_used": len(sites),
            "known_site_sources": sorted({s["source"] for s in sites}),
            "queries": outcomes, "unique_candidate_cells": len(cells), "regions": out,
            "interpretation": ("Unreviewed leads only. Inventories are incomplete; distance from them does not establish novelty, "
                               "suitability or access. Each lead requires a literature, map and imagery review before any claim.")}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", type=Path)
    ap.add_argument("--limit", type=int, default=10)
    a = ap.parse_args()
    report = run(a.limit)
    text = json.dumps(report, indent=1, allow_nan=False)
    if a.output:
        a.output.write_text(text + "\n")
    bands = defaultdict(int)
    for g in report["regions"]:
        bands[g["documentation_band"]] += 1
    print(f"{report['unique_candidate_cells']} unique cells in {len(report['regions'])} regions; {dict(bands)}")

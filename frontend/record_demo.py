"""Record the scripted demo (submission/DEMO_SCRIPT.md) from the running app as a WebM video.

    .venv/bin/python frontend/record_demo.py --url http://localhost:8000 --out submission/media

Headless Chrome renders WebGL in software, so globe motion is less smooth than on a real GPU; a narrated
screen recording on a normal laptop is preferable for the final submission video.
"""
import argparse
import shutil
from pathlib import Path

from playwright.sync_api import sync_playwright

p = argparse.ArgumentParser()
p.add_argument("--url", default="http://localhost:8000")
p.add_argument("--out", type=Path, default=Path("submission/media"))
args = p.parse_args()
args.out.mkdir(parents=True, exist_ok=True)
size = {"width": 1280, "height": 800}

with sync_playwright() as pw:
    browser = pw.chromium.launch(channel="chrome", headless=True, args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
    ctx = browser.new_context(viewport=size, record_video_dir=str(args.out / "raw"), record_video_size=size)
    page = ctx.new_page()
    page.goto(args.url)
    page.wait_for_function("TT.state.meta", timeout=30000)
    page.wait_for_timeout(2500)
    # 1. Arbitrary target by coordinates: Jezero crater centre
    page.select_option("#fBody", "mars")
    page.fill("#fLat", "18.41")
    page.fill("#fLon", "77.69")
    page.click("#coordForm button[type=submit]")
    page.wait_for_function("TT.state.target && TT.state.target.cell", timeout=30000)
    page.wait_for_timeout(3500)                      # regional cell + terrain values
    # 2. Search (historical dry/barren screening is the default) → Earth reveal
    page.click("#searchBtn")
    page.wait_for_function("TT.state.reveal && TT.state.reveal.stage === 'done'", timeout=60000)
    page.wait_for_timeout(3500)
    # 3. Evidence for #1
    page.locator("#panelBody").evaluate("e => e.scrollTo({top: 500, behavior: 'smooth'})")
    page.wait_for_timeout(3000)
    # 4. Alternatives and comparison
    page.click("[data-tab=results]")
    page.wait_for_timeout(1500)
    page.check("[data-compare='0']")
    page.check("[data-compare='1']")
    page.click("[data-tab=compare]")
    page.wait_for_timeout(3500)
    page.click("[data-tab=results]")
    page.click("[data-cand='2']")
    page.wait_for_timeout(3000)
    # 5. Finer local evidence (Gobi)
    page.click("[data-tab=investigations]")
    page.wait_for_timeout(1500)
    page.click("[data-study=gobi]")
    page.wait_for_timeout(4000)
    # 6. Honest outcomes: no match within 500 km of Sylhet; missing evidence at Shackleton
    page.click("#returnBtn")
    page.wait_for_timeout(1500)
    page.select_option("#examples", "jezero_near_sylhet")
    page.wait_for_function("TT.state.result && TT.state.result.status === 'no_candidates_under_filters'", timeout=60000)
    page.wait_for_timeout(4000)
    page.select_option("#examples", "shackleton_center")
    page.wait_for_function("TT.state.result && TT.state.result.status === 'target_insufficient_evidence'", timeout=60000)
    page.wait_for_timeout(4000)
    video = page.video.path()
    ctx.close()
    browser.close()

final = args.out / "terratwin_demo.webm"
shutil.move(video, final)
shutil.rmtree(args.out / "raw", ignore_errors=True)
print(f"saved {final} ({final.stat().st_size / 1e6:.1f} MB)")

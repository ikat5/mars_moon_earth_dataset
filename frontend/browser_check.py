"""End-to-end browser check of the TerraTwin workflow against a running server.

    .venv/bin/python frontend/browser_check.py [--url http://localhost:8000] [--shots analysis/screenshots]

Uses Playwright with the system Chrome (``--browser chromium`` uses Playwright's bundled build instead).
Exits non-zero on the first failed check; prints a JSON summary otherwise.
"""
import argparse
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

p = argparse.ArgumentParser()
p.add_argument("--url", default="http://localhost:8000")
p.add_argument("--shots", type=Path, default=None)
p.add_argument("--browser", default="chrome", help="chrome (system) or chromium (bundled)")
args = p.parse_args()
results, console_errors = [], []


def check(name, fn):
    t = time.perf_counter()
    fn()
    results.append({"check": name, "ok": True, "seconds": round(time.perf_counter() - t, 2)})
    print(f"ok  {name}", flush=True)


def shot(page, name):
    if args.shots:
        args.shots.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(args.shots / f"{name}.png"))


def open_page(browser, viewport, block_globe=False):
    ctx = browser.new_context(viewport=viewport, accept_downloads=True)
    page = ctx.new_page()
    page.on("console", lambda m: m.type == "error" and console_errors.append(m.text))
    page.on("pageerror", lambda e: console_errors.append(f"pageerror: {e}"))
    if block_globe:
        page.route("**/globe.gl*", lambda route: route.abort())
    page.goto(args.url, wait_until="domcontentloaded")
    expect(page.locator("#dataVersion")).to_contain_text("release", timeout=20000)
    return ctx, page


def enter(page, body, lat, lon):
    page.select_option("#fBody", body)
    page.fill("#fLat", str(lat))
    page.fill("#fLon", str(lon))
    page.click("#coordForm button[type=submit]")


def search(page):
    page.click("#searchBtn")


with sync_playwright() as pw:
    launch = {"channel": "chrome"} if args.browser == "chrome" else {}
    browser = pw.chromium.launch(headless=True, args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"], **launch)
    ctx, page = open_page(browser, {"width": 1440, "height": 900})
    api = page.request

    def arbitrary_target():
        enter(page, "mars", 18.41, 77.69)
        expect(page.locator("#targetInfo")).to_contain_text("mars:412870", timeout=15000)
        expect(page.locator("#targetInfo")).to_contain_text("Regional cell containing this point")
        enter(page, "mars", -4.5895, 137.4417 + 360)  # longitude alias
        expect(page.locator("#targetInfo")).to_contain_text("entered as", timeout=15000)
    check("arbitrary coordinate target + longitude alias resolve to a regional cell", arbitrary_target)

    def run_jezero():
        enter(page, "mars", 18.41, 77.69)
        expect(page.locator("#targetInfo")).to_contain_text("mars:412870", timeout=15000)
        search(page)
        expect(page.locator("[data-cand]")).to_have_count(10, timeout=30000)
        direct = api.post(f"{args.url}/api/v1/search", data={"body": "mars", "lat": 18.41, "lon": 77.69, "profile": "dry_barren_terrain"}).json()
        first = direct["candidates"][0]
        expect(page.locator("[data-cand='0']")).to_contain_text(f"{first['observed_fit']:.1f}")
        shot(page, "01_results_desktop")
    check("search renders the same ranked candidates as the API", run_jezero)

    def inspect_and_return():
        page.click("[data-cand='0']")
        expect(page.locator("#panelEvidence")).to_contain_text("Terrain resemblance")
        expect(page.locator("#panelEvidence")).to_contain_text("Earth-only historical context")
        expect(page.locator("#returnBar")).to_be_visible()
        assert page.evaluate("GLOBE.world()") == "earth"
        page.wait_for_timeout(2500)
        shot(page, "02_evidence_on_earth")
        page.click("#returnBtn")
        assert page.evaluate("GLOBE.world()") == "mars"
        expect(page.locator("#targetInfo")).to_contain_text("mars:412870")
        assert page.evaluate("TT.state.result.candidates.length") == 10  # query kept while switching globes
    check("select candidate → Earth evidence → return to target keeps the query", inspect_and_return)

    def globe_selects_same_candidate():
        page.evaluate("TT.onPolygonClick({category:'candidate', idx: 3}, 0, 0)")
        expect(page.locator("#panelEvidence")).to_contain_text("Candidate #4")
        page.click("[data-tab=results]")
        expect(page.locator("[data-cand='3']")).to_have_attribute("aria-current", "true")
    check("globe footprint click and list select the same candidate", globe_selects_same_candidate)

    def display_winding():
        # d3-geo/globe.gl fill the complement of a counter-clockwise exterior ring: every overlay must be clockwise,
        # while the exported GeoJSON keeps RFC 7946 counter-clockwise exteriors.
        areas = page.evaluate("""TT.overlayPolygons('earth').concat(TT.overlayPolygons('mars')).map(p => {
            const r = p.geometry.coordinates[0]; let a = 0;
            for (let i = 0; i < r.length - 1; i++) a += r[i][0] * r[i + 1][1] - r[i + 1][0] * r[i][1];
            return a; })""")
        assert areas and all(a < 0 for a in areas), areas
        raw = page.evaluate("TT.state.result.candidates[0].geometry.coordinates[0]")
        assert sum(raw[i][0] * raw[i + 1][1] - raw[i + 1][0] * raw[i][1] for i in range(len(raw) - 1)) > 0
    check("globe footprints use display winding; data keeps RFC 7946 winding", display_winding)

    def compare():
        page.click("[data-tab=results]")
        page.check("[data-compare='0']")
        page.check("[data-compare='2']")
        page.click("[data-tab=compare]")
        expect(page.locator("#panelCompare")).to_contain_text("#1 vs #3")
        expect(page.locator("#panelCompare")).to_contain_text("largest share of the difference")
        shot(page, "03_compare")
    check("compare two candidates from one query", compare)

    def exports():
        page.click("[data-tab=results]")
        with page.expect_download() as d:
            page.click("#exJson")
        data = json.loads(Path(d.value.path()).read_text())
        assert data["status"] == "ok" and data["dataset_version"] and data["target"]["feature_id"] == "mars:412870"
        assert len(data["candidates"]) == 10 and data["terratwin_export"]["origin_included"] is False
        with page.expect_download() as d:
            page.click("#exGeo")
        geo = json.loads(Path(d.value.path()).read_text())
        assert geo["type"] == "FeatureCollection" and len(geo["features"]) == 10
        assert geo["features"][0]["properties"]["rank"] == 1 and geo["terratwin"]["target_feature_id"] == "mars:412870"
        with page.context.expect_page() as popup:
            page.click("#exBrief")
        brief = popup.value
        brief.wait_for_load_state()
        expect(brief.locator("h1")).to_have_text("TerraTwin investigation brief")
        expect(brief.locator("body")).to_contain_text("mars:412870")
        expect(brief.locator("body")).to_contain_text("Proposed next measurements")
        if args.shots:
            brief.screenshot(path=str(args.shots / "04_brief.png"), full_page=True)
        brief.close()
    check("JSON, GeoJSON and brief exports trace back to the query", exports)

    def origin_privacy():
        page.click("[data-tab=target]")
        page.evaluate("document.getElementById('originBox').open = true")
        page.fill("#sOriginLat", "24.89")
        page.fill("#sOriginLon", "91.87")
        expect(page.locator("#panelResults")).not_to_contain_text("#1 ·")  # editing settings discards old results
        search(page)
        expect(page.locator("[data-cand]")).to_have_count(10, timeout=30000)
        with page.expect_download() as d:
            page.click("#exJson")
        data = json.loads(Path(d.value.path()).read_text())
        assert data["configuration"]["origin"] is None and data["terratwin_export"]["origin_omitted"] is True
        assert all(c["distance_from_origin_km"] is None for c in data["candidates"])
        page.click("[data-tab=target]")
        page.fill("#sOriginLat", "")
        page.fill("#sOriginLon", "")
    check("travel origin is omitted from exports by default", origin_privacy)

    def stale_responses():
        def slow(route):
            time.sleep(1.5)
            route.continue_()
        page.route("**/api/v1/search", slow)
        enter(page, "mars", 18.41, 77.69)
        expect(page.locator("#targetInfo")).to_contain_text("mars:412870", timeout=15000)
        search(page)
        enter(page, "moon", 0, 0)  # change target while the Mars search is in flight
        expect(page.locator("#targetInfo")).to_contain_text("moon:", timeout=15000)
        page.wait_for_timeout(2500)
        assert page.evaluate("TT.state.result") is None, "stale Mars result rendered for Moon target"
        search(page)
        page.evaluate("document.querySelector('input[value=terrain_screening]').click()")  # profile change mid-flight
        page.wait_for_timeout(2500)
        assert page.evaluate("TT.state.result") is None, "result rendered after profile changed"
        for _ in range(5):  # rapid clicks
            enter(page, "mars", 10, 10)
            enter(page, "moon", 1, 1)
        search(page)
        page.wait_for_function("TT.state.result !== null", timeout=30000)
        assert page.evaluate("TT.state.result.target.body") == "moon"
        assert page.evaluate("TT.state.result.profile") == "terrain_screening"
        page.unroute("**/api/v1/search")
    check("stale responses are discarded after target/profile changes and rapid clicks", stale_responses)

    def example_outcomes():
        page.select_option("#examples", "jezero_near_sylhet")
        expect(page.locator("#panelResults")).to_contain_text("No qualifying Earth regions", timeout=30000)
        expect(page.locator("#panelResults")).to_contain_text("nothing was relaxed automatically")
        assert page.evaluate("TT.state.result.configuration.radius_km") == 500
        shot(page, "05_no_match")
        page.select_option("#examples", "shackleton_center")
        expect(page.locator("#panelResults")).to_contain_text("Insufficient terrain evidence", timeout=30000)
        assert page.evaluate("TT.state.result.candidates.length") == 0
        shot(page, "06_insufficient_evidence")
        page.select_option("#examples", "jezero_landing")
        expect(page.locator("#targetInfo")).to_contain_text("mars:412869", timeout=15000)
    check("no-match, insufficient-evidence and landing-vs-centre examples", example_outcomes)

    def unavailable_profile_and_invalid_input():
        page.wait_for_function("!TT.state.searching", timeout=30000)
        page.click("[data-tab=target]")
        page.locator("#searchForm details summary").first.click()
        page.locator("input[value=cave_reconnaissance]").check()
        search(page)
        expect(page.locator("#panelResults")).to_contain_text("not available", timeout=15000)
        page.click("[data-tab=target]")
        page.locator("input[value=dry_barren_terrain]").check()
        enter(page, "mars", 95, 0)
        expect(page.locator("#coordError")).to_be_visible()
        page.click("[data-tab=target]")
        page.evaluate("document.getElementById('originBox').open = true")
        page.fill("#sOriginLat", ""); page.fill("#sOriginLon", "")
        page.fill("#sRadius", "100")
        search(page)
        expect(page.locator("#searchMsg")).to_contain_text("A radius needs an Earth origin")
        page.fill("#sRadius", "")
    check("unavailable profile and invalid input give explanations, not results", unavailable_profile_and_invalid_input)

    def service_failure_and_retry():
        page.route("**/api/v1/search", lambda route: route.fulfill(status=503, content_type="application/json",
                                                                    body='{"detail":{"error":"release_unavailable","detail":"test"}}'))
        enter(page, "mars", 18.41, 77.69)
        expect(page.locator("#targetInfo")).to_contain_text("mars:412870", timeout=15000)
        search(page)
        expect(page.locator("#panelResults")).to_contain_text("Search data unavailable", timeout=15000)
        assert page.evaluate("TT.state.result") is None
        page.unroute("**/api/v1/search")
        page.click("#retrySearch")
        expect(page.locator("[data-cand]")).to_have_count(10, timeout=30000)
    check("service failure is an error with retry, never a no-match", service_failure_and_retry)

    def local_studies_and_saved():
        page.click("[data-tab=investigations]")
        expect(page.locator("#panelInvestigations")).to_contain_text("Gobi regional terrain candidate")
        page.click("[data-study=gobi]")
        page.wait_for_function("GLOBE.world() === 'earth' && TT.overlayPolygons('earth').some(p => p.category === 'investigation')", timeout=15000)
        page.wait_for_timeout(2500)
        shot(page, "09_gobi_study")
        page.click("[data-tab=investigations]")
        page.click("[data-saved=jezero]")
        expect(page.locator("#panelResults")).to_contain_text("Saved example", timeout=15000)
        assert page.evaluate("TT.state.result.saved_fixture.case_id") == "jezero"
    check("local studies and saved examples are labeled as such", local_studies_and_saved)
    ctx.close()

    def mobile():
        mctx, m = open_page(browser, {"width": 390, "height": 844})
        m.select_option("#examples", "jezero_center")
        expect(m.locator("[data-cand]")).to_have_count(10, timeout=30000)
        assert m.evaluate("document.documentElement.scrollWidth <= innerWidth"), "horizontal overflow"
        card, left = m.locator("#card").bounding_box(), m.locator("#left").bounding_box()
        assert left["y"] + left["height"] <= card["y"] + 1, "panels overlap on mobile"
        shot(m, "07_mobile_results")
        m.click("#collapseBtn")
        expect(m.locator("#panelBody")).to_be_hidden()
        mctx.close()
    check("narrow mobile layout: no overlap or horizontal scroll, collapsible panel", mobile)

    def no_globe():
        nctx, n = open_page(browser, {"width": 1280, "height": 800}, block_globe=True)
        expect(n.locator("#noGlobe")).to_be_visible()
        enter(n, "mars", 18.41, 77.69)
        expect(n.locator("#targetInfo")).to_contain_text("mars:412870", timeout=15000)
        search(n)
        expect(n.locator("[data-cand]")).to_have_count(10, timeout=30000)
        shot(n, "08_no_webgl_fallback")
        nctx.close()
    check("search workflow works without the globe library/WebGL", no_globe)

    def keyboard():
        kctx, k = open_page(browser, {"width": 1440, "height": 900})
        k.focus("[data-tab=target]")
        k.keyboard.press("ArrowRight")
        assert k.evaluate("document.activeElement.dataset.tab") == "results"
        k.focus("#fLat")
        assert k.evaluate("getComputedStyle(document.activeElement).outlineStyle") != "none"
        kctx.close()
    check("keyboard tab navigation and visible focus", keyboard)
    browser.close()

ignored = ("Failed to load resource", "net::ERR_FAILED", "Failed to load mars", "Failed to load moon", "Failed to load earth")
real_errors = [e for e in console_errors if not any(s in e for s in ignored)]
print(json.dumps({"passed": len(results), "console_errors": real_errors, "checks": results}, indent=1))
sys.exit(1 if real_errors else 0)

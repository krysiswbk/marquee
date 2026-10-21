"""Rendered empty, stale, loading, and populated Home agenda at household sizes."""

import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "REPORTS/marquee-visual-campaign/empty-agenda-batch13"
BASELINE = os.environ.get("MARQUEE_EMPTY_AGENDA_BASELINE") == "1"
PHASE = "before" if BASELINE else "after"


def fixture(kind):
    return {
        "fresh": kind != "offline",
        "lock": "locked",
        "sleeping": True,
        "people": [{"name": "Alex", "state": "Home"}],
        "openings": [], "events": [], "alerts": [],
        "cards": [
            {"type": "calendar_event", "title": f"Household event {i}",
             "subtitle": f"In {i} days · 6:30 PM", "starts": f"2026-11-{i:02d}T18:30:00"}
            for i in range(1, 11)
        ] if kind == "populated" else [],
    }


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"]
    )
    for width, height in ((1500, 971), (1280, 800), (1024, 600)):
        for kind in ("empty", "offline", "loading", "populated"):
            page = browser.new_page(viewport={"width": width, "height": height})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            if kind == "loading":
                page.add_init_script("""const originalFetch = window.fetch;
                    window.fetch = (...args) => String(args[0]).includes('/api/brain')
                      ? new Promise(() => {}) : originalFetch(...args);""")

            def route(request):
                url = request.request.url
                path = url.split("?", 1)[0].split("marquee.test", 1)[-1]
                if path == "/kiosk":
                    return request.fulfill(path=str(ROOT / "output/index.html"), content_type="text/html")
                if path == "/api/brain":
                    if kind == "offline":
                        return request.fulfill(status=503, body="{}", content_type="application/json")
                    return request.fulfill(json=fixture(kind))
                if path in ("/api/config", "/settings.json", "/live-settings.json"):
                    return request.fulfill(json={"providers": {}, "fallback": {}, "transitionMs": 0})
                if path in ("/ambient.json", "/ha-weather.json"):
                    return request.fulfill(json={})
                asset = ROOT / "output" / path.lstrip("/")
                if asset.is_file():
                    return request.fulfill(path=str(asset))
                return request.fulfill(json={})

            page.route("**/*", route)
            page.goto("http://marquee.test/kiosk", wait_until="domcontentloaded")
            page.locator("#brain-agenda").wait_for()
            if kind != "loading":
                page.wait_for_function("document.querySelector('#brain-agenda')?.dataset.agendaState")
            page.wait_for_timeout(600)
            out = EVIDENCE / PHASE
            out.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(out / f"{kind}-{width}x{height}.png"))
            agenda = page.locator("#brain-agenda")
            link = page.locator("#brain-agenda-link")
            metrics = page.evaluate("""() => {
              const panel=document.querySelector('#brain-agenda');
              const house=document.querySelector('#brain-house');
              const activity=document.querySelector('#brain-activity');
              const activityCopy=activity.querySelector('.brain-empty');
              const dock=document.querySelector('.brain-dock');
              const retry=document.querySelector('#brain-retry');
              const copy=panel.querySelector('.brain-empty');
              const link=panel.querySelector('.brain-agenda-more');
              const r=el=>{const b=el.getBoundingClientRect();return {top:b.top,bottom:b.bottom,height:b.height}};
              return {state:panel.dataset.agendaState,panel:r(panel),copy:copy?r(copy):null,
                house:r(house),retry:r(retry),retryVisible:!!retry.getClientRects().length,
                activity:r(activity),activityCopy:activityCopy?r(activityCopy):null,dock:r(dock),
                link:r(link),linkVisible:!!link.getClientRects().length,
                rows:panel.querySelectorAll('.brain-agenda-item:not([hidden])').length,
                overflow:document.documentElement.scrollWidth>innerWidth};
            }""")
            (out / f"{kind}-{width}x{height}.json").write_text(json.dumps(metrics, indent=2))
            if not BASELINE:
                assert not errors, errors
                assert not metrics["overflow"]
                if kind == "populated":
                    assert metrics["state"] == "ready"
                    assert metrics["rows"] >= (7 if width == 1500 else 5 if width == 1280 else 3)
                    assert link.is_visible()
                else:
                    assert metrics["state"] == ("empty" if kind == "empty" else "stale" if kind == "offline" else "loading")
                    assert metrics["panel"]["height"] <= (200 if width == 1500 else 180 if width == 1280 else 170), metrics
                    assert metrics["copy"] and metrics["copy"]["bottom"] <= metrics["panel"]["bottom"] + 1, metrics
                    if kind == "empty":
                        assert "No birthdays or events" in agenda.inner_text()
                        assert link.is_visible()
                        assert metrics["link"]["top"] - metrics["copy"]["bottom"] <= 32, metrics
                        link.focus()
                        assert link.evaluate("el => el === document.activeElement")
                        assert link.get_attribute("href") == "/kiosk?view=calendar&mode=all"
                        link.press("Enter")
                        page.wait_for_url("**/kiosk?view=calendar&mode=all")
                    else:
                        assert not link.is_visible()
                        assert "unavailable" in agenda.inner_text().lower() if kind == "offline" else "loading" in agenda.inner_text().lower()
                    if kind == "offline":
                        assert metrics["retryVisible"]
                        assert metrics["retry"]["bottom"] <= metrics["house"]["bottom"] - 8, metrics
                        assert page.locator("#brain-retry").evaluate(
                            "el => parseFloat(getComputedStyle(el).fontSize) >= 14"
                        )
                        assert metrics["activity"]["height"] <= 110, metrics
                        assert metrics["activityCopy"]["bottom"] <= metrics["activity"]["bottom"] + 1, metrics
                        assert metrics["activity"]["bottom"] <= metrics["dock"]["top"] + 1, metrics
            page.close()
    browser.close()
    print(f"PASS: Home agenda {PHASE} at 1500×971, 1280×800, 1024×600")

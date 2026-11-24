"""Home compares fresh indoor and outdoor HA readings without replaying stale ones."""

import os
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = Path(os.environ.get(
    "MARQUEE_HOME_CLIMATE_EVIDENCE",
    "/home/wbk/REPORTS/kiosk-dashboard-20261124/home-climate-bridge",
))
EVIDENCE.mkdir(parents=True, exist_ok=True)
STATE = {"fresh": True, "people": [{"name": "Kris", "state": "Home"}],
         "climate": {"house_temperature": "23.5"}, "lock": "locked",
         "openings": [], "events": [], "cards": [], "alerts": []}

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"])
    for width, height in ((320, 720), (1500, 1000)):
        weather = {"temp": 2.6, "condition": "sunny", "updated": time.time()}
        page = browser.new_page(viewport={"width": width, "height": height})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        def route(request):
            path = request.request.url.split("?", 1)[0].split("marquee.test", 1)[-1]
            if path == "/kiosk":
                return request.fulfill(path=str(ROOT / "output/index.html"), content_type="text/html")
            if path == "/api/brain":
                return request.fulfill(json=STATE)
            if path == "/ha-weather.json":
                return request.fulfill(json=weather)
            if path in ("/api/config", "/settings.json", "/live-settings.json"):
                return request.fulfill(json={"providers": {}, "fallback": {"screen": "clock_weather"}})
            asset = ROOT / "output" / path.lstrip("/")
            if asset.is_file():
                return request.fulfill(path=str(asset))
            return request.fulfill(json={})

        page.route("**/*", route)
        page.goto("http://marquee.test/kiosk", wait_until="domcontentloaded")
        page.wait_for_function("document.querySelector('#brain-dock-copy')?.dataset.fullText?.includes('Inside is 21°C warmer than outside')")
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        assert not errors, errors
        page.screenshot(path=str(EVIDENCE / f"fresh-{width}x{height}.png"))
        weather = {"temp": 2.6, "condition": "sunny", "updated": 1}
        page.reload(wait_until="domcontentloaded")
        page.wait_for_function("document.querySelector('#brain-house')?.dataset.state === 'ready'")
        page.wait_for_function("document.querySelector('#brain-dock-copy')?.dataset.fullText === 'The house is listening for its next real update'")
        assert not errors, errors
        page.close()
    browser.close()

print("PASS: fresh HA temperature comparison fits phone and desk, stale weather makes no claim")

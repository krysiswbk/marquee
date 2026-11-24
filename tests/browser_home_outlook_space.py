"""Large Home screens use the fresh hourly forecast without changing compact layouts."""

import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = Path(os.environ.get(
    "MARQUEE_HOME_OUTLOOK_EVIDENCE",
    "/home/wbk/REPORTS/kiosk-dashboard-20261124/home-outlook-space",
))
EVIDENCE.mkdir(parents=True, exist_ok=True)
NOW = datetime.now(timezone.utc)
HOURS = [
    {"datetime": (NOW + timedelta(hours=i + 1)).isoformat(),
     "temperature": 3 - i, "condition": "sunny" if i < 3 else "clear-night",
     "precipitation_probability": 10}
    for i in range(12)
]
WEATHER = {"temp": 3, "condition": "sunny", "updated": time.time(),
           "observed_at": NOW.isoformat(), "forecast_updated": time.time(),
           "hourly": HOURS, "daily": []}
BRAIN = {"fresh": True, "people": [{"name": "Kris", "state": "Home"}],
         "openings": [], "events": [], "cards": [], "alerts": []}

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"])
    for width, height, scale, expected in ((320, 720, 1, 4), (1500, 1000, 2, 8), (3000, 2000, 1, 8)):
        page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=scale)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        def route(request):
            path = request.request.url.split("?", 1)[0].split("marquee.test", 1)[-1]
            if path == "/kiosk":
                return request.fulfill(path=str(ROOT / "output/index.html"), content_type="text/html")
            if path == "/api/brain":
                return request.fulfill(json=BRAIN)
            if path in ("/weather", "/ha-weather.json"):
                return request.fulfill(json=WEATHER)
            if path in ("/api/config", "/settings.json", "/live-settings.json"):
                return request.fulfill(json={"providers": {}, "fallback": {"screen": "clock_weather"}})
            asset = ROOT / "output" / path.lstrip("/")
            if asset.is_file():
                return request.fulfill(path=str(asset))
            return request.fulfill(json={})

        page.route("**/*", route)
        page.goto("http://marquee.test/kiosk", wait_until="domcontentloaded")
        page.wait_for_function("!document.querySelector('#home-outlook').hidden")
        count = page.locator("#home-outlook-hours .home-outlook-hour").count()
        assert count == expected, (width, height, count)
        if expected == 8:
            visible = "Array.from(document.querySelectorAll('#home-outlook-hours .home-outlook-hour')).filter(cell => getComputedStyle(cell).display !== 'none').length"
            assert page.evaluate("""() => {
              const panel = document.querySelector('#home-outlook').getBoundingClientRect();
              const last = document.querySelector('#home-outlook-hours .home-outlook-hour:last-child').getBoundingClientRect();
              return last.bottom <= panel.bottom;
            }""")
            page.evaluate("document.querySelector('.brain-shell').classList.remove('brain-no-activity')")
            assert page.evaluate(visible) == 4
            assert page.evaluate("""() => {
              const panel = document.querySelector('#home-outlook').getBoundingClientRect();
              const last = document.querySelector('#home-outlook-hours .home-outlook-hour:nth-child(4)').getBoundingClientRect();
              return last.bottom <= panel.bottom;
            }""")
            page.evaluate("document.querySelector('.brain-shell').classList.add('brain-no-activity')")
            assert page.evaluate(visible) == 8
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        assert page.evaluate("document.documentElement.scrollHeight <= innerHeight")
        assert not errors, errors
        page.screenshot(path=str(EVIDENCE / f"home-{width}x{height}-dpr{scale}.png"))
        page.close()
    browser.close()

print("PASS: fresh Home outlook shows 4 compact or 8 large hourly entries without overflow")

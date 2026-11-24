"""Cast idle shows only recent, observed household facts without crowding weather."""
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

OUTPUT = Path(__file__).resolve().parents[1] / "output"


def test_cast_idle_house_status_uses_fresh_snapshot_and_fits(tmp_path):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"]
        )
        for width, height in ((1024, 600), (1280, 800), (1920, 1080)):
            now = datetime.now(timezone.utc)
            snapshot = {
                "fresh": True,
                "source_at": now.timestamp(),
                "lock": "locked",
                "house_activity": {"living_room_occupied": True},
            }
            brain_error = {"value": False}
            weather = {
                "temp": 3,
                "condition": "Sunny",
                "observed_at": now.isoformat(),
                "forecast_updated": now.timestamp(),
                "daily": [
                    {"datetime": (now + timedelta(days=day)).isoformat(),
                     "temperature": 4 + day, "templow": day, "condition": "Cloudy"}
                    for day in range(1, 5)
                ],
            }
            page = browser.new_page(viewport={"width": width, "height": height})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))

            def route(request):
                path = request.request.url.split("?", 1)[0].split("marquee.test", 1)[-1]
                if path == "/api/brain":
                    if brain_error["value"]:
                        return request.fulfill(status=503)
                    return request.fulfill(json=snapshot)
                if path == "/weather":
                    return request.fulfill(json=weather)
                if path == "/settings.json":
                    return request.fulfill(json={"theme": "synthwave"})
                asset = OUTPUT / ("index.html" if path == "/image" else path.lstrip("/"))
                if asset.is_file():
                    return request.fulfill(
                        path=str(asset), content_type="text/html" if path == "/image" else None
                    )
                return request.fulfill(json={"playing": False})

            page.route("**/*", route)
            page.goto("http://marquee.test/image", wait_until="domcontentloaded")
            page.wait_for_function("!document.querySelector('#cast-house-status').hidden")
            page.wait_for_function("!document.querySelector('#home-outlook').hidden")
            assert page.locator("#cast-house-status").inner_text() == (
                "Front door locked\nLiving room occupied"
            )
            geometry = page.evaluate("""() => {
              const house = document.querySelector('#cast-house-status').getBoundingClientRect();
              const outlook = document.querySelector('#home-outlook').getBoundingClientRect();
              const weather = document.querySelector('#idle-weather').getBoundingClientRect();
              return {houseTop:house.top,houseBottom:house.bottom,
                weatherBottom:weather.bottom,outlookTop:outlook.top,
                scrollWidth:document.documentElement.scrollWidth};
            }""")
            assert geometry["weatherBottom"] <= geometry["houseTop"]
            assert geometry["houseBottom"] <= geometry["outlookTop"] - 4, geometry
            assert geometry["scrollWidth"] <= width
            page.screenshot(path=str(tmp_path / f"cast-house-status-{width}.png"))

            snapshot["openings"] = [{"name": "Garage Door", "state": "open"}]
            page.evaluate("window.MarqueeLifecycle.request('cast-house-status')")
            page.wait_for_function("document.querySelector('#cast-house-status').textContent.includes('Garage Door open')")
            assert "Front door locked" not in page.locator("#cast-house-status").inner_text()

            snapshot["alerts"] = [{"urgency": "important", "title": "Nursery devices offline"}]
            page.evaluate("window.MarqueeLifecycle.request('cast-house-status')")
            page.wait_for_function("document.querySelector('#cast-house-status').textContent.includes('Nursery devices offline')")

            brain_error["value"] = True
            page.evaluate("window.MarqueeLifecycle.request('cast-house-status')")
            page.wait_for_function("document.querySelector('#cast-house-status').hidden")
            brain_error["value"] = False
            snapshot["alerts"] = []

            snapshot["source_at"] = now.timestamp() - 120
            page.evaluate("window.MarqueeLifecycle.request('cast-house-status')")
            page.wait_for_function("document.querySelector('#cast-house-status').hidden")
            assert not errors, errors
            page.close()
        browser.close()

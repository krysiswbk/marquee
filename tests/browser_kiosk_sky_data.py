"""Sky destination renders the live facts published by the HA weather bridge."""
import os
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
SKY = {
    "condition": "partlycloudy",
    "cloud_cover": 38,
    "visibility": 24.4,
    "visibility_unit": "km",
    "sun": {"is_day": False, "elevation": -8.4, "azimuth": 278},
    "moon": {"phase": "waxing_gibbous", "illumination": 0.73},
    "aircraft": [{"id": "abc123", "callsign": "TEST123", "bearing": 90, "elevation": 21}],
}


def test_kiosk_sky_page_shows_available_sensor_facts_without_aurora_alert():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"]
        )
        page = browser.new_page(viewport={"width": 1280, "height": 800})

        def route(request):
            path = urlsplit(request.request.url).path
            if path in ("/kiosk", "/live"):
                return request.fulfill(path=str(ROOT / "output/index.html"), content_type="text/html")
            asset = ROOT / "output" / path.lstrip("/")
            if asset.is_file():
                return request.fulfill(path=str(asset))
            if path == "/api/config":
                return request.fulfill(json={"providers": {"astronomy": {"enabled": True, "targets": ["kiosk"]}}})
            if path == "/contexts":
                return request.fulfill(json={"contexts": [], "browse": {"nhl": []}})
            if path == "/providers":
                return request.fulfill(json={"providers": {"astronomy": {"state": "ok"}}})
            if path == "/ha-weather.json":
                return request.fulfill(json={"temp": 25, "apparent_temperature": 12,
                                             "temperature_unit": "°C", "sky": SKY})
            if path in ("/settings.json", "/live-settings.json"):
                return request.fulfill(json={"transitionMs": 0})
            if path == "/ambient.json":
                return request.fulfill(json={"opacity": 0})
            if path == "/events":
                return request.fulfill(body="", content_type="text/event-stream")
            return request.fulfill(json={})

        page.route("**/*", route)
        page.add_init_script("window.EventSource = class { addEventListener() {} close() {} };")
        page.goto("http://marquee.test/kiosk?view=sky", wait_until="domcontentloaded")
        surface = page.locator(".kiosk-ambient-surface")
        surface.wait_for()
        text = surface.inner_text()
        assert "SKY" in text
        assert "TONIGHT'S MOON" in text
        assert "Waxing gibbous" in text
        assert "73% illuminated" in text
        assert "Partly cloudy" in text
        assert "38% cloud cover" in text
        assert "24.4 km visibility" in text
        assert "Sun -8°" in text
        assert "25°" in text
        assert "Feels like" in text and "12°" in text
        assert "1 nearby aircraft" in text
        assert "TEST123" not in text
        page.get_by_role("button", name="View 1 nearby plane").click()
        assert page.locator(".sky-aircraft-row").count() == 1
        assert "TEST123" in page.locator(".sky-aircraft-row").inner_text()
        assert "21° elevation" in page.locator(".sky-aircraft-row").inner_text()
        page.get_by_role("button", name="Hide 1 nearby plane").click()
        assert page.locator(".sky-aircraft-row").count() == 0
        browser.close()

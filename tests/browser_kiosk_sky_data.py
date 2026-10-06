"""Sky destination renders the live facts published by the HA weather bridge."""
import os
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
SKY = {
    "condition": "partlycloudy",
    "cloud_cover": 38,
    "visibility": 18000,
    "visibility_unit": "m",
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
                return request.fulfill(json={"sky": SKY})
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
        assert "The sky above home" in text
        assert "Partly cloudy" in text
        assert "Cloud cover · 38%" in text
        assert "Visibility · 18,000 m" in text
        assert "Sun elevation · -8.4°" in text
        assert "Moon · waxing gibbous" in text
        assert "Illumination · 73%" in text
        assert "1 aircraft nearby · TEST123" in text
        assert "The sky is quiet for now." not in text
        browser.close()

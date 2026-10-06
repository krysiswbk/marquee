"""Deterministic 1024x600 geometry contract for the optional sky layer."""
import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]


def test_sky_layer_uses_supplied_night_moon_and_only_real_aircraft():
    weather = {"temp": 12, "condition": "clear-night", "isDay": False,
               "sky": {"sun": {"is_day": False}, "cloud_cover": 8,
                       "moon": {"phase": "waxing_crescent", "illumination": .24,
                                "bearing": 0, "azimuth": 90, "elevation": 20},
                       "aircraft": [{"id": "adsb:REAL", "bearing": 90, "elevation": 12}]}}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 1024, "height": 600}, device_scale_factor=1)

        def route(route):
            path = route.request.url.split("?", 1)[0].split("marquee.test", 1)[-1]
            if path == "/image":
                return route.fulfill(path=str(ROOT / "output/index.html"), content_type="text/html")
            if path == "/weather":
                return route.fulfill(json=weather)
            if path in ("/api/config", "/contexts", "/providers"):
                return route.fulfill(json={"providers": {}, "contexts": []})
            if path in ("/settings.json", "/live-settings.json"):
                return route.fulfill(json={"transitionMs": 0})
            asset = ROOT / "output" / path.lstrip("/")
            if asset.is_file():
                return route.fulfill(path=str(asset))
            return route.fulfill(json={})

        page.route("**/*", route)
        page.goto("http://marquee.test/image", wait_until="domcontentloaded")
        page.wait_for_selector("#sky-layer[data-mode=night]")
        result = page.evaluate("""() => ({
          moon: document.querySelectorAll('.sky-moon').length,
          aircraft: document.querySelectorAll('.sky-aircraft').length,
          stars: document.querySelectorAll('.sky-star').length,
          night: document.body.classList.contains('sky-night'),
          day: document.body.classList.contains('sky-day'),
          fill: getComputedStyle(document.querySelector('.sky-fill')).fill,
          box: document.querySelector('#sky-layer').getBoundingClientRect().toJSON(),
          overflow: document.documentElement.scrollWidth > innerWidth || document.documentElement.scrollHeight > innerHeight
        })""")
        assert result["moon"] == 1
        assert result["aircraft"] == 1
        assert result["stars"] > 0
        assert result["night"] is True
        assert result["day"] is False
        assert result["fill"] == "rgb(0, 0, 0)"
        assert result["box"] == {"x": 0, "y": 0, "width": 1024, "height": 600, "top": 0, "right": 1024, "bottom": 600, "left": 0}
        assert not result["overflow"]
        fallback = page.evaluate("""() => {
          window.MarqueeSky.render({isDay: false, sky: {moon: {phase: 'waning_crescent'}}});
          const moon = document.querySelector('.sky-moon');
          return {position: moon?.dataset.position, illumination: moon?.dataset.illumination || null,
                  phase: moon?.dataset.phase, aircraft: document.querySelectorAll('.sky-aircraft').length};
        }""")
        assert fallback == {"position": "ambient", "illumination": None,
                            "phase": "waning_crescent", "aircraft": 0}
        day = page.evaluate("""() => {
          window.MarqueeSky.render({isDay: true, condition: 'sunny'});
          return {mode: document.querySelector('#sky-layer').dataset.mode,
                  day: document.body.classList.contains('sky-day'),
                  night: document.body.classList.contains('sky-night')};
        }""")
        assert day == {"mode": "day", "day": True, "night": False}
        browser.close()

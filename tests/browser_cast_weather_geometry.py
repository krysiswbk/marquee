"""Nest Hub Max geometry and visual contract for the Cast ambient weather rail."""
import json
import os
import time
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
WEATHER = {
    "temp": 17.4,
    "condition": "partlycloudy",
    "code": 2,
    "isDay": True,
    "apparent_temperature": 16.1,
    "forecast_updated": int(time.time()),
    "daily": [{"temperature": 22, "templow": 11}],
    "hourly": [{"precipitation_probability": 65, "precipitation": 8}],
}


def test_cast_weather_keeps_clock_centered_and_uses_condition_icon(tmp_path):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"]
        )
        page = browser.new_page(viewport={"width": 1024, "height": 600}, device_scale_factor=1)

        def route(route):
            url = route.request.url
            path = url.split("?", 1)[0].split("marquee.test", 1)[-1]
            if path in ("/image", "/api/config", "/contexts", "/providers"):
                if path == "/image":
                    return route.fulfill(path=str(ROOT / "output/index.html"), content_type="text/html")
                return route.fulfill(json={"providers": {}, "contexts": []})
            if path == "/weather":
                weather = json.loads(json.dumps(WEATHER))
                referer = route.request.headers.get("referer", "")
                if "no-amount" in url or "no-amount" in referer:
                    weather["hourly"][0].pop("precipitation", None)
                return route.fulfill(json=weather)
            if path in ("/settings.json", "/live-settings.json"):
                return route.fulfill(json={"transitionMs": 0})
            if path == "/ambient.json":
                return route.fulfill(json={"opacity": 0})
            asset = ROOT / "output" / path.lstrip("/")
            if asset.is_file():
                return route.fulfill(path=str(asset))
            return route.fulfill(json={})

        page.route("**/*", route)
        page.goto("http://marquee.test/image", wait_until="domcontentloaded")
        page.wait_for_selector("#idle-weather-icon svg")
        result = page.evaluate(
            """
            () => {
              document.body.classList.add('cast-display');
              document.body.classList.add('idle');
              document.documentElement.style.setProperty('--ambient-ui-dim', '.25');
              const box = selector => document.querySelector(selector).getBoundingClientRect().toJSON();
              const clock = box('#idle-clock'), house = box('.idle-house'), weather = box('#idle-weather');
              const secondary = box('.idle-weather-secondary');
              const weatherClockStyle = getComputedStyle(document.querySelector('.weather-clock'));
              const idleClockStyle = getComputedStyle(document.querySelector('.idle-clock'));
              const secondaryStyle = getComputedStyle(document.querySelector('.idle-weather-secondary'));
              const statusStyle = getComputedStyle(document.querySelector('.idle-weather-status'));
              const idleWeatherStyle = getComputedStyle(document.querySelector('#idle-weather'));
              return {
                clock, house, weather,
                secondaryBox: secondary,
                weatherClockColor: weatherClockStyle.color,
                weatherClockFilter: weatherClockStyle.filter,
                idleClockColor: idleClockStyle.color,
                idleClockFilter: idleClockStyle.filter,
                idleClockShadow: idleClockStyle.textShadow,
                idleWeatherFilter: idleWeatherStyle.filter,
                secondaryColor: secondaryStyle.color,
                statusColor: statusStyle.color,
                skyMode: document.querySelector('#sky-layer')?.dataset.mode,
                skyDay: document.body.classList.contains('sky-day'),
                viewport: {width: innerWidth, height: innerHeight},
                icon: document.querySelector('#idle-weather-icon svg')?.dataset.kind,
                temp: document.querySelector('#idle-weather-temp').textContent,
                condition: document.querySelector('#idle-weather-condition').textContent,
                secondary: document.querySelector('.idle-weather-secondary').innerText,
                overflow: document.documentElement.scrollWidth > innerWidth + 1,
              };
            }
            """
        )
        page.screenshot(path=str(os.environ.get(
            "MARQUEE_QA_SCREENSHOT", tmp_path / "cast-weather-hub-max.png"
        )), full_page=True)
        assert result["icon"] == "partly"
        assert result["temp"] == "17°C"
        assert result["condition"] == "Partly cloudy"
        assert result["weatherClockColor"] == "rgb(255, 255, 255)"
        assert result["weatherClockFilter"] == "none"
        assert result["idleClockColor"] == "rgb(255, 255, 255)"
        assert result["idleClockFilter"] == "none"
        assert result["idleClockShadow"] == "rgba(0, 0, 0, 0.55) 0px 1px 3px"
        assert result["idleWeatherFilter"] == "none"
        assert result["skyMode"] == "day"
        assert result["skyDay"] is True
        assert result["secondaryColor"] == "rgb(40, 52, 61)"
        assert result["secondaryColor"] == result["statusColor"]
        assert "Feels 16°" in result["secondary"]
        assert "High 22° / Low 11°" in result["secondary"]
        assert "Rain 65%" in result["secondary"]
        assert "8 mm expected" in result["secondary"]
        assert result["clock"]["width"] > 0
        assert result["clock"]["height"] >= 150
        assert abs((result["clock"]["left"] + result["clock"]["width"] / 2) - 512) < 1
        assert abs((result["weather"]["left"] + result["weather"]["width"] / 2) - 512) < 1
        assert result["weather"]["width"] >= 500
        assert result["weather"]["height"] >= 180
        assert page.locator("#idle-weather-icon").bounding_box()["width"] >= 90
        assert page.locator("#idle-weather-temp").bounding_box()["height"] >= 55
        assert page.locator("#idle-weather-condition").bounding_box()["height"] >= 25
        assert result["secondaryBox"]["height"] >= 32
        primary_box = page.locator(".idle-weather-primary").bounding_box()
        assert result["secondaryBox"]["y"] > primary_box["y"] + primary_box["height"] + 10
        assert result["secondaryBox"]["bottom"] <= result["viewport"]["height"] - 100
        assert result["secondaryBox"]["height"] < result["weather"]["height"] / 2
        assert result["house"]["height"] >= 350
        assert result["house"]["height"] <= 560
        assert result["house"]["left"] >= 0 and result["house"]["right"] <= 1024
        assert not result["overflow"]
        page.close()

        absent = browser.new_page(viewport={"width": 1024, "height": 600}, device_scale_factor=1)
        absent.route("**/*", route)
        absent.goto("http://marquee.test/image?no-amount=1", wait_until="domcontentloaded")
        absent.wait_for_selector("#idle-weather-icon svg")
        absent_content = absent.locator(".idle-weather-secondary").inner_text()
        assert "Rain 65%" in absent_content
        assert "expected" not in absent_content
        assert "mm" not in absent_content
        absent.close()
        browser.close()

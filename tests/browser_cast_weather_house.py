"""Cast weather and household scenes at Nest Hub Max resolution."""
from datetime import datetime, timezone
from pathlib import Path
import os

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output"


def route_asset(route):
    path = route.request.url.split("?", 1)[0].split("marquee.test", 1)[-1]
    asset = OUTPUT / ("index.html" if path == "/image" else path.lstrip("/"))
    if asset.is_file():
        return route.fulfill(path=str(asset), content_type="text/html" if path == "/image" else None)
    return route.fulfill(json={})


def prepare(page):
    page.route("**/*", route_asset)
    page.goto("http://marquee.test/image", wait_until="networkidle")
    # The Cast stylesheet is authored separately from the shared kiosk CSS.
    # Injecting it here also verifies the rules independently of asset ordering.
    page.add_style_tag(path=str(OUTPUT / "cast-weather-house.css"))
    page.evaluate("""() => {
      const tokens = {'--bg':'#100b22','--panel':'#21123d','--text':'#fff0fb',
        '--text-soft':'#decbe9','--accent':'#ff4fc8',
        '--accent-glow':'rgba(255,79,200,.18)','--line':'#72508c'};
      Object.entries(tokens).forEach(([key, value]) =>
        document.documentElement.style.setProperty(key, value));
      document.body.classList.add('cast-display', 'brain-live');
      document.body.classList.remove('idle');
      document.querySelector('.idle-screen').style.display = 'none';
      const stage = document.querySelector('#stage');
      stage.classList.remove('hidden', 'fade');
      stage.style.transition = 'none';
    }""")


def test_cast_household_attention_is_legible_and_contained(tmp_path):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"]
        )
        for width, height in ((1024, 600), (1280, 800)):
            page = browser.new_page(viewport={"width": width, "height": height})
            prepare(page)
            result = page.evaluate("""() => {
              const stage = document.querySelector('#stage');
              stage.classList.add('contextual');
              const card = document.querySelector('#context-card');
              card.dataset.kind = 'household_attention';
              card.classList.add('no-art');
              document.querySelector('#context-art').hidden = true;
              document.querySelector('#context-source').textContent = 'HOUSEHOLD';
              document.querySelector('#context-clock').textContent = '9:46 AM';
              document.querySelector('#context-weather').textContent = '17°C · Sunny';
              document.querySelector('#context-status').textContent = 'Needs attention';
              document.querySelector('#context-title').textContent = 'Nursery devices are offline';
              document.querySelector('#context-subtitle').textContent = 'Device status needs attention.';
              document.querySelector('#context-detail').textContent =
                'Nursery Door, Nursery Motion & Lux Motion, and Nursery Window are not reporting. Check batteries or connection.';
              const rows = document.querySelector('#context-rows');
              rows.innerHTML = '<span>Nursery Door offline</span><span>Nursery Window offline</span>';
              rows.hidden = false;
              const rect = selector => document.querySelector(selector).getBoundingClientRect();
              const style = selector => getComputedStyle(document.querySelector(selector));
              const cardBox = rect('#context-card'), copy = rect('.context-copy'), details = rect('#context-detail');
              const rowBox = rect('#context-rows');
              return {background:style('#context-card').backgroundImage,
                titleSize:parseFloat(style('#context-title').fontSize),
                detailSize:parseFloat(style('#context-detail').fontSize),
                rowSize:parseFloat(style('#context-rows').fontSize),
                copyBottom:copy.bottom, detailBottom:details.bottom,
                rowsTop:rowBox.top, rowsBottom:rowBox.bottom,
                cardBottom:cardBox.bottom, viewportWidth:document.documentElement.scrollWidth};
            }""")
            assert "rgb(16, 11, 34)" in result["background"]
            assert result["titleSize"] >= 34
            assert result["detailSize"] >= 18
            assert result["rowSize"] >= 17
            assert result["detailBottom"] <= result["copyBottom"] + 1
            assert result["copyBottom"] <= result["rowsTop"] + 1
            assert result["rowsBottom"] <= result["cardBottom"] + 1
            assert result["viewportWidth"] <= width
            page.screenshot(path=str(tmp_path / f"cast-house-{width}.png"))
            page.close()
        browser.close()


def test_cast_weather_broadcast_uses_synth_palette(tmp_path):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"]
        )
        for width, height in ((1024, 600), (1280, 800)):
            page = browser.new_page(viewport={"width": width, "height": height})
            prepare(page)
            context = {
                "id": "weather:cast-contract", "type": "weather", "subtype": "current",
                "title": "Weather at home", "detail": "Comfortable through the evening.",
                "weather": {"timezone": "America/Toronto",
                            "generated_at": datetime.now(timezone.utc).isoformat(),
                            "current": {"temperature_2m": 24, "apparent_temperature": 26,
                                        "relative_humidity_2m": 49, "wind_speed_10m": 12,
                                        "weather_code": 0, "is_day": 1},
                            "hours": [], "days": []},
            }
            result = page.evaluate("""context => {
              document.querySelector('#stage').classList.add('weather-context');
              window.MarqueeWeather.render(context);
              document.querySelector('#weather-clock').textContent = '9:46 AM';
              const card = document.querySelector('.wx-broadcast');
              const box = card.getBoundingClientRect();
              const main = card.querySelector('.wx-main').getBoundingClientRect();
              return {background:getComputedStyle(card).backgroundImage,
                header:getComputedStyle(card.querySelector('.weather-head')).backgroundColor,
                accent:getComputedStyle(card.querySelector('.weather-head')).borderBottomColor,
                temperature:document.querySelector('#channel-temp').innerText,
                cardBottom:box.bottom, mainBottom:main.bottom,
                viewportWidth:document.documentElement.scrollWidth};
            }""", context)
            assert "rgb(16, 11, 34)" in result["background"]
            assert result["header"] == "rgb(33, 18, 61)"
            assert result["accent"] == "rgb(255, 79, 200)"
            assert result["temperature"] == "24°C"
            assert result["mainBottom"] < result["cardBottom"]
            assert result["viewportWidth"] <= width
            page.wait_for_function("""() => getComputedStyle(
              document.querySelector('#weather-conditions')).opacity === '1'""")
            page.screenshot(path=str(tmp_path / f"cast-weather-{width}.png"))
            page.close()
        browser.close()

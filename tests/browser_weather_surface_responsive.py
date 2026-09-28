"""Deterministic contract for the dedicated weather surface hierarchy."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
VIEWPORTS = [(320, 720), (360, 720), (393, 852), (430, 852),
             (700, 900), (1024, 600), (1500, 900)]
HEALTH_NAMES = ["Nursery Motion & Lux Motion — Upstairs Hallway",
                "Nursery Window Contact — South-facing Window"]


def route_for(route):
    parsed = urlparse(route.request.url)
    path = parsed.path
    query = parse_qs(parsed.query)
    referer = route.request.headers.get("referer", "")
    query.update(parse_qs(urlparse(referer).query))
    if path in ("/live", "/kiosk"):
        return route.fulfill(path=str(ROOT / "output/index.html"), content_type="text/html")
    if path == "/api/config":
        return route.fulfill(json={"providers": {"weather": {"enabled": True, "targets": ["kiosk"]}}})
    if path == "/providers":
        return route.fulfill(json={"providers": {"weather": {"state": "ok"}}})
    if path == "/contexts":
        return route.fulfill(json={"contexts": [weather_context(query)]})
    if path == "/now-playing.json":
        return route.fulfill(json={"playing": True, "type": "media_context",
                                   "key": "weather-contract",
                                   "context": weather_context(query)})
    if path == "/api/brain":
        return route.fulfill(json={"fresh": True, "unknown": [], "device_health": [
            {"entity_id": f"sensor.health_{index}", "name": name,
             "state": "unavailable", "location": "nursery"}
            for index, name in enumerate(HEALTH_NAMES)],
            "events": [], "cards": [], "alerts": [], "people": []})
    asset = ROOT / "output" / path.lstrip("/")
    if asset.is_file():
        return route.fulfill(path=str(asset))
    if path in ("/settings.json", "/live-settings.json"):
        return route.fulfill(json={"transitionMs": 0})
    if path == "/ambient.json":
        return route.fulfill(json={"opacity": 0})
    return route.fulfill(json={})


def weather_context(query):
    alert = "weather-alert" in query
    now = datetime.now(timezone.utc)
    hours = [
        {"at": (now.replace(minute=0, second=0, microsecond=0)).isoformat(),
         "temp": 24 + index, "code": 0, "is_day": 1, "rain": index * 5}
        for index in range(6)
    ]
    days = [{
        "date": now.date().fromordinal(now.date().toordinal() + index).isoformat(),
        "high": 27 if index == 0 else 25 - index,
        "low": 18 if index == 0 else 16 - index,
        "code": 0 if index == 0 else 1,
        "rain": 10 if index == 0 else 20 + index,
    } for index in range(5)]
    return {
        "id": "weather:contract",
        "source": "weather",
        "provider": "weather",
        "type": "weather",
        "subtype": "alert" if alert else "current",
        "title": "Heat warning" if alert else "Weather at home",
        "subtitle": "Urgent local alert" if alert else "",
        "detail": ("Hot conditions are expected this afternoon. Follow the guidance "
                    "in the local weather warning." if alert else
                    "A bright afternoon. Comfortable through the evening."),
        "starts": now.isoformat(),
        "weather": {
            "timezone": "America/Toronto",
            "generated_at": now.isoformat(),
            "current": {"temperature_2m": 24, "apparent_temperature": 26,
                         "relative_humidity_2m": 49, "wind_speed_10m": 12,
                         "weather_code": 0, "is_day": 1},
            "hours": hours, "days": days, "radar_relevant": True,
        },
    }


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"]
    )
    for width, height in VIEWPORTS:
        page = browser.new_page(viewport={"width": width, "height": height})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.route("**/*", route_for)
        page.goto("http://marquee.test/kiosk?view=weather", wait_until="domcontentloaded")
        page.wait_for_selector(".stage.weather-context .wx-broadcast")
        page.wait_for_selector('.kiosk-rail .kiosk-primary [data-view="weather"][aria-current="page"]')
        page.wait_for_function("document.querySelector('.stage.weather-context')?.inert === false && document.querySelector('.stage.weather-context')?.getAttribute('aria-hidden') !== 'true'")
        page.wait_for_selector("#brain-dock-copy")
        page.wait_for_timeout(250)

        assert page.locator(".kiosk-rail").is_visible()
        assert page.locator(".stage.weather-context").evaluate("el => !el.inert && !el.hasAttribute('aria-hidden') && !el.classList.contains('kiosk-covered')")
        assert page.locator(".kiosk-section").evaluate("el => el.hidden && el.inert && el.getAttribute('aria-hidden') === 'true'")
        page.locator("#wx-segment-title").focus()
        assert page.evaluate("document.activeElement?.id === 'wx-segment-title'")
        assert page.locator("#wx-segment-title").inner_text() == "Current conditions"
        assert page.locator("#wx-observation-source").count() == 1
        assert page.locator('.kiosk-primary [data-view=""]:visible').count() == 1
        assert page.locator('.kiosk-primary [data-view="weather"]:visible').count() == 1
        assert page.locator(".kiosk-rail").evaluate(
            "el => { const r = el.getBoundingClientRect(); "
            "return r.bottom >= innerHeight - 1 && r.height >= 56; }"
        )
        assert page.locator(".wx-broadcast").evaluate(
            "el => { const r = el.getBoundingClientRect(), rail = "
            "document.querySelector('.kiosk-rail').getBoundingClientRect(); "
            "return r.bottom <= rail.top + 1; }"
        )
        health_copy = page.locator("#brain-dock-copy")
        full_health = "Offline: " + ", ".join(HEALTH_NAMES) + ". Check batteries or connection."
        if width <= 430:
            assert health_copy.inner_text() == "2 devices offline · Check connection"
        elif width <= 700:
            assert health_copy.inner_text().startswith("Offline: ")
        else:
            assert health_copy.inner_text() == full_health
        assert health_copy.get_attribute("aria-label") == full_health
        assert health_copy.get_attribute("title") == full_health
        assert health_copy.get_attribute("data-full-text") == full_health
        assert health_copy.evaluate(
            "el => { const dock = el.closest('.brain-dock').getBoundingClientRect(); "
            "const rail = document.querySelector('.kiosk-rail').getBoundingClientRect(); "
            "return dock.bottom <= rail.top + 1; }"
        )

        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        assert page.locator(".wx-broadcast").evaluate(
            "el => el.scrollWidth <= el.clientWidth"
        )
        assert page.locator(".wx-main").evaluate(
            "el => { const text = el.querySelector('.channel-outlook'); "
            "return !text || text.getBoundingClientRect().bottom <= "
            "el.getBoundingClientRect().bottom + 1; }"
        )

        if width <= 700:
            assert page.locator(".wx-footer").evaluate("el => getComputedStyle(el).display === 'none'")
        else:
            assert page.locator(".wx-footer").evaluate("el => getComputedStyle(el).display !== 'none'")
        assert page.locator(".wx-main").evaluate(
            "el => { const nav = el.parentElement.querySelector('.wx-segments'); "
            "return el.getBoundingClientRect().bottom <= nav.getBoundingClientRect().top + 1; }"
        )

        buttons = page.locator(".wx-segments button:not([hidden])")
        assert buttons.count() >= 2
        for index in range(buttons.count()):
            button = buttons.nth(index)
            assert button.evaluate(
                "el => el.offsetWidth >= 44 && el.offsetHeight >= 44"
            ), (width, height, index)
            button.scroll_into_view_if_needed()
            assert button.is_visible(), (width, height, index)

        for index in range(buttons.count()):
            button = buttons.nth(index)
            button.focus()
            assert button.evaluate("el => document.activeElement === el")
            assert button.get_attribute("aria-pressed") == ("true" if index == 0 else "false")

        for segment in ("conditions", "hours", "forecast", "radar"):
            page.locator(f'.wx-segments button[data-segment="{segment}"]').click()
            page.wait_for_function(
                "segment => document.querySelector('.wx-broadcast')?.dataset.segment === segment",
                arg=segment,
            )
            overlap = page.evaluate("""
                () => {
                    const panel = document.querySelector('.wx-panel:not([hidden])');
                    const nav = document.querySelector('.wx-segments');
                    const controls = [...nav.querySelectorAll('button:not([hidden])')];
                    const content = [...panel.querySelectorAll(
                        '.channel-hour, .channel-day, .wx-radar-frame, .wx-radar-copy, ' +
                        '.channel-current > *'
                    )].filter(Boolean);
                    const rect = el => el.getBoundingClientRect();
                    const intersects = (a, b) => a.left < b.right && a.right > b.left &&
                        a.top < b.bottom && a.bottom > b.top;
                    const collisions = [];
                    for (const item of content) for (const control of controls)
                        if (intersects(rect(item), rect(control)))
                            collisions.push(control.dataset.segment || control.id);
                    return {
                        panelBottom: rect(panel).bottom,
                        navTop: rect(nav).top,
                        contentBottoms: content.map(el => rect(el).bottom),
                        collisions,
                    };
                }
            """)
            assert overlap["panelBottom"] <= overlap["navTop"] + 1, (width, height, segment, overlap)
            assert all(bottom <= overlap["navTop"] + 1 for bottom in overlap["contentBottoms"]), (width, height, segment, overlap)
            assert not overlap["collisions"], (width, height, segment, overlap)

        page.locator('.wx-segments button[data-segment="conditions"]').click()
        page.wait_for_function("document.querySelector('.wx-broadcast')?.dataset.segment === 'conditions'")
        pause = page.locator("#wx-pause")
        pause.focus()
        assert page.evaluate("document.activeElement === document.querySelector('#wx-pause')")
        assert pause.get_attribute("aria-pressed") == "false"
        page.locator('.wx-segments button[data-segment="hours"]').click()
        assert page.locator('.wx-segments button[data-segment="hours"]').get_attribute("aria-pressed") == "true"
        assert page.locator('.wx-segments button[data-segment="conditions"]').get_attribute("aria-pressed") == "false"
        page.locator("#wx-pause").click()
        assert page.locator("#wx-pause").get_attribute("aria-pressed") == "true"
        page.locator('.kiosk-primary [data-view=""]').click()
        page.wait_for_function("new URL(location.href).searchParams.get('view') === null")
        assert page.locator(".stage").evaluate("el => !el.inert && !el.hasAttribute('aria-hidden')")
        assert page.evaluate("document.activeElement?.dataset.view === ''")

        page.screenshot(path=f"/tmp/marquee-2.10.72-weather-{width}x{height}.png")
        assert not errors, (width, height, errors)
        page.close()

        if width == 320:
            alert = browser.new_page(viewport={"width": width, "height": height})
            alert.route("**/*", route_for)
            alert.goto("http://marquee.test/kiosk?view=weather&weather-alert=1", wait_until="domcontentloaded")
            alert.wait_for_selector(".stage.weather-context .wx-broadcast")
            alert.wait_for_function("document.querySelector('.channel-warning:not([hidden])') !== null")
            assert alert.locator(".channel-warning").is_visible()
            assert alert.locator(".wx-broadcast").get_attribute("data-alert") == "true"
            assert alert.locator(".channel-warning").inner_text().strip()
            assert alert.locator(".wx-footer").evaluate("el => getComputedStyle(el).display === 'none'")
            alert.close()
    browser.close()

print("PASS: weather hierarchy has no clipping/overlap, horizontal overflow, or undersized controls across target viewports")

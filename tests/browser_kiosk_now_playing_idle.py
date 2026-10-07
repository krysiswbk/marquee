"""Responsive browser coverage for the calm Plex idle kiosk composition."""

import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
VIEWPORTS = [(390, 844), (768, 1024), (1024, 600), (1280, 720), (1500, 1000)]


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"]
    )
    for width, height in VIEWPORTS:
        page = browser.new_page(viewport={"width": width, "height": height})
        errors = []
        fixture = {"playing": False, "state": "idle", "availability": "idle"}
        page.on("pageerror", lambda error: errors.append(str(error)))

        def route(request):
            path = request.request.url.split("?", 1)[0].split("marquee.test", 1)[-1]
            if path in ("/kiosk", "/live"):
                return request.fulfill(path=str(ROOT / "output/index.html"), content_type="text/html")
            if path == "/api/config":
                data = {"providers": {
                    "plex": {"enabled": True, "targets": ["kiosk"]},
                    "ufc": {"enabled": True, "targets": ["kiosk"]},
                }, "fallback": {}}
            elif path == "/contexts":
                data = {"contexts": [{"id": "ufc:live", "source": "ufc",
                                       "type": "ufc_live", "title": "UFC Fight Night",
                                       "priority": 99, "targets": ["kiosk"]}]}
            elif path == "/providers":
                data = {"providers": {"plex": {"state": "ok", "candidateContexts": 0,
                                                   "eligibleContexts": 0, "contexts": []}}}
            elif path == "/now-playing.json":
                data = fixture
            elif path == "/weather":
                data = {"temp": 15, "condition": "partlycloudy", "code": 2,
                        "daily": [{"temperature": 21, "templow": 12}], "hourly": []}
            elif path in ("/settings.json", "/live-settings.json"):
                data = {"transitionMs": 0}
            elif path == "/ambient.json":
                data = {"opacity": 0}
            else:
                asset = ROOT / "output" / path.lstrip("/")
                if asset.is_file():
                    return request.fulfill(path=str(asset))
                data = {}
            return request.fulfill(body=json.dumps(data), content_type="application/json")

        page.route("**/*", route)
        page.goto("http://marquee.test/kiosk?view=plex", wait_until="domcontentloaded")
        page.wait_for_selector(".kiosk-section:not([hidden]) #kiosk-section-title")
        page.evaluate("""() => {
          document.querySelector('#idle-weather-temp').textContent = '15°C';
          document.querySelector('#idle-weather-condition').textContent = 'Partly cloudy';
          document.querySelector('#idle-weather-range').textContent = 'High 21° / Low 12°';
          document.body.classList.add('cast-display');
          document.querySelector('#idle-weather-condition').classList.add('weather-fact-separator');
          document.querySelector('#idle-weather-range').classList.add('weather-fact-separator');
          window.MarqueeNavigation.resolve({playing:false, state:'idle', availability:'idle'});
        }""")
        assert page.evaluate("getComputedStyle(document.querySelector('.idle-weather-primary')).display") == "flex"
        assert page.evaluate("getComputedStyle(document.querySelector('#idle-weather-condition')).borderInlineStartStyle") == "solid"
        assert page.evaluate("getComputedStyle(document.querySelector('#idle-weather-range')).paddingInlineStart") != "0px"
        assert page.locator("#kiosk-section-title").inner_text() == "Nothing is playing"
        assert page.locator(".kiosk-section.now-playing-surface").evaluate("el => !el.hidden && el.getBoundingClientRect().width > 0 && el.getBoundingClientRect().height > 0")
        assert page.evaluate("getComputedStyle(document.querySelector('.kiosk-now-playing-head > p')).color") == "rgb(255, 226, 120)"
        assert page.evaluate("getComputedStyle(document.querySelector('.kiosk-home-action')).backgroundColor") == "rgb(36, 52, 71)"
        assert page.evaluate("getComputedStyle(document.querySelector('.kiosk-now-playing-body .kiosk-weather-separator')).color") == "rgb(129, 147, 166)"
        assert page.locator(".kiosk-home-action").inner_text() == "Return to Home"
        assert "There is no active session" in page.locator(".kiosk-now-playing-detail").inner_text()
        page.evaluate("window.MarqueeNavigation.resolve({playing:true, state:'playing', title:'Episode', key:'plex:episode', progress:{offsetMs:120, durationMs:600}}); document.body.classList.remove('idle'); document.querySelector('.stage').classList.remove('hidden')")
        assert page.locator(".stage").evaluate("el => !el.classList.contains('kiosk-covered') && !el.inert && el.getBoundingClientRect().width > 0 && el.getBoundingClientRect().height > 0")
        assert page.locator(".kiosk-section.now-playing-surface").evaluate("el => el.hidden && el.inert")
        page.evaluate("window.MarqueeNavigation.resolve({playing:true, state:'paused', title:'Episode', key:'plex:episode', progress:{offsetMs:240, durationMs:600}})")
        assert page.locator(".stage").evaluate("el => !el.classList.contains('kiosk-covered') && !el.inert")
        page.evaluate("window.MarqueeNavigation.resolve({playing:false, state:'stopped', availability:'idle'})")
        assert page.locator(".kiosk-section.now-playing-surface").evaluate("el => !el.hidden && !el.inert")
        assert page.locator(".kiosk-state-mark").count() == 0
        assert "Playback has stopped" in page.locator(".kiosk-now-playing-detail").inner_text()
        assert page.locator(".kiosk-weather-fact").count() == 4
        assert page.locator(".kiosk-weather-separator").count() == 3
        assert page.locator(".kiosk-weather-fact").nth(0).get_attribute("aria-label") == "Temperature: 15°C"
        labels = page.locator(".kiosk-weather-fact").evaluate_all("els => els.map(el => el.getAttribute('aria-label'))")
        assert any(label and label.startswith("Feels like:") for label in labels)
        assert "High and low: High 21° / Low 12°" in labels
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")

        page.locator("#kiosk-section-title").evaluate("el => el.tabIndex = -1")
        page.evaluate("document.querySelector('#kiosk-section-title').focus({focusVisible:true})")
        assert page.evaluate("document.activeElement.id === 'kiosk-section-title'")
        assert page.evaluate("(() => { const s = getComputedStyle(document.activeElement); return s.outlineStyle !== 'none' || s.textDecorationLine.includes('underline'); })()")

        page.evaluate("window.MarqueeNavigation.resolve({playing:false, state:'unavailable', availability:'unavailable'})")
        assert page.locator("#kiosk-section-title").inner_text() == "Media service unavailable"
        assert page.locator(".kiosk-state-mark.is-unavailable").count() == 1
        assert page.locator("[data-kiosk-retry]").count() == 1
        page.evaluate("window.MarqueeNavigation.resolve({playing:false, state:'stale', availability:'stale'})")
        assert page.locator("#kiosk-section-title").inner_text() == "Media status is stale"
        assert page.locator(".kiosk-state-mark.is-stale").count() == 1
        page.evaluate("window.MarqueeNavigation.resolve({playing:false, state:'stopped', availability:'idle'})")
        assert page.locator("#kiosk-section-title").inner_text() == "Nothing is playing"
        assert "Playback has stopped" in page.locator(".kiosk-now-playing-detail").inner_text()
        page.locator('.kiosk-home-action').click()
        page.wait_for_function("new URL(location.href).searchParams.get('view') === null")
        assert page.locator(".kiosk-section").evaluate("el => el.hidden && el.inert")

        # The explicit Plex destination must render the authoritative session
        # payload even while a competing ambient context is available.
        for playback_state in ("playing", "paused"):
            fixture = {"playing": True, "state": playback_state, "title": "2024 Recap",
                       "subtitle": "Season 2 · Episode 4", "key": "plex:session", "type": "episode",
                       "artwork": "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='600' height='900'%3E%3Crect width='600' height='900' fill='%232a4054'/%3E%3C/svg%3E",
                       "progress": {"offsetMs": 1200, "durationMs": 6000},
                       "session": {"device": "Living Room TV", "client": "Plex", "platform": "Roku", "local": True}}
            active_page = browser.new_page(viewport={"width": width, "height": height})
            active_errors = []
            active_page.on("pageerror", lambda error: active_errors.append(str(error)))
            active_page.route("**/*", route)
            with active_page.expect_response(lambda response: response.url.split("?", 1)[0].endswith("/now-playing.json")) as now_playing:
                active_page.goto("http://marquee.test/kiosk?view=plex", wait_until="domcontentloaded")
            active_payload = now_playing.value.json()
            assert active_payload["title"] == "2024 Recap"
            assert active_payload["progress"] == {"offsetMs": 1200, "durationMs": 6000}
            active_page.wait_for_function("document.querySelector('#title')?.textContent === '2024 Recap'")
            assert active_page.locator("#title").inner_text() == "2024 Recap"
            assert active_page.locator("#subtitle").inner_text() == "Season 2 · Episode 4"
            assert active_page.locator("#device-name").inner_text() == "Living Room TV"
            assert active_page.locator(".b-ratings").evaluate("el => getComputedStyle(el).display === 'none'")
            assert active_page.locator(".b-stream").evaluate("el => getComputedStyle(el).display === 'none'")
            if playback_state == "paused":
                assert active_page.locator(".b-progress.paused").count() == 1
            phone_layout = active_page.evaluate("""() => {
                const rect = selector => document.querySelector(selector)?.getBoundingClientRect();
                const identity = rect('.b-identity');
                const header = [rect('#clock'), rect('#wx')].filter(Boolean)
                    .filter(box => box.width > 0 && box.height > 0)
                    .reduce((bottom, box) => Math.max(bottom, box.bottom), 0);
                return {
                    identityTop: identity?.top || 0,
                    headerBottom: header,
                    poster: rect('.b-poster')?.height || 0,
                    progress: rect('.b-progress')?.height || 0,
                    device: rect('.b-device')?.height || 0,
                    overflow: document.documentElement.scrollWidth > window.innerWidth + 1,
                };
            }""")
            if width <= 480:
                assert phone_layout["identityTop"] >= phone_layout["headerBottom"] + 12
                if phone_layout["poster"]:
                    assert phone_layout["poster"] <= 198
                assert phone_layout["progress"] > 0
                if phone_layout["device"]:
                    assert phone_layout["device"] <= 52
            assert not phone_layout["overflow"]
            progress_scale = active_page.locator("#fill").evaluate(
                "el => Number((el.style.transform.match(/scaleX\\(([^)]+)\\)/) || [])[1])")
            assert 0.10 <= progress_scale <= 0.35, (width, playback_state, progress_scale)
            assert not active_errors, (width, height, playback_state, active_errors)
            active_page.close()
        assert not errors, (width, height, errors)
        page.close()
    browser.close()
    print("PASS: Plex idle/unavailable composition, grouped weather, scoped focus, responsive fit, and Home return")

"""Regression coverage for the 2.12.4 direct kiosk contracts."""

import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]


def install_routes(page, requests):
    def route(request):
        url = request.request.url
        path, _, query = url.split("/", 3)[-1].partition("?")
        path = "/" + path
        params = dict(item.split("=", 1) for item in query.split("&") if "=" in item)
        requests.append((path, params))
        if path in ("/kiosk", "/live"):
            return request.fulfill(path=str(ROOT / "output/index.html"), content_type="text/html")
        asset = ROOT / "output" / path.lstrip("/")
        if asset.is_file():
            return request.fulfill(path=str(asset))
        if path == "/api/config":
            return request.fulfill(json={"providers": {
                "plex": {"enabled": True, "targets": ["kiosk"]},
                "pfl": {"enabled": True, "targets": ["kiosk"]},
                "astronomy": {"enabled": True, "targets": ["kiosk"]},
            }, "fallback": {}})
        if path == "/contexts":
            return request.fulfill(json={"contexts": [], "browse": {"nhl": []}})
        if path == "/providers":
            return request.fulfill(json={"providers": {
                "plex": {"state": "ok", "candidateContexts": 0, "eligibleContexts": 0, "contexts": []},
                "pfl": {"state": "ok"}, "astronomy": {"state": "ok"},
            }})
        if path == "/now-playing.json":
            if params.get("display") == "kiosk":
                return request.fulfill(json={"playing": True, "type": "media_context",
                                             "key": "ufc:ambient", "title": "Ambient sports"})
            return request.fulfill(json={"playing": False, "state": "idle", "availability": "idle"})
        if path in ("/settings.json", "/live-settings.json"):
            return request.fulfill(json={"transitionMs": 0})
        if path == "/ambient.json":
            return request.fulfill(json={"opacity": 0})
        if path == "/events":
            return request.fulfill(body="", content_type="text/event-stream")
        return request.fulfill(json={})

    page.route("**/*", route)


def open_page(browser, url, viewport):
    page = browser.new_page(viewport={"width": viewport[0], "height": viewport[1]})
    page.add_init_script("""
      window.__marqueeEventSources = [];
      window.EventSource = class {
        constructor(url) { this.url = url; this.closed = false; window.__marqueeEventSources.push(this); }
        addEventListener() {}
        close() { this.closed = true; }
      };
    """)
    requests = []
    install_routes(page, requests)
    page.goto(url, wait_until="domcontentloaded")
    if "view=" in url:
        page.wait_for_selector(".kiosk-section:not([hidden])")
    else:
        page.wait_for_selector(".kiosk-rail")
    return page, requests


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"]
    )

    home, home_requests = open_page(browser, "http://marquee.test/kiosk", (390, 844))
    home.wait_for_timeout(500)
    assert any(path == "/now-playing.json" and params.get("display") == "kiosk"
               for path, params in home_requests)
    assert home.evaluate("window.__marqueeEventSources.length") == 1
    home.evaluate("[1, 2, 3].forEach(() => window.dispatchEvent(new Event('marquee-navigation')))")
    assert home.evaluate("window.__marqueeEventSources.length") == 1
    home.locator('.kiosk-primary a[data-view="plex"]').click()
    home.wait_for_function("new URL(location.href).searchParams.get('view') === 'plex'")
    assert home.evaluate("window.__marqueeEventSources.length") == 2
    home.locator('.kiosk-primary a[data-view=""]').click()
    home.wait_for_function("!new URL(location.href).searchParams.has('view')")
    assert home.evaluate("window.__marqueeEventSources.length") == 3
    home.close()

    plex, plex_requests = open_page(browser, "http://marquee.test/kiosk?view=plex", (390, 844))
    plex.wait_for_function("document.querySelector('#kiosk-section-title')?.textContent === 'Nothing is playing'")
    assert any(path == "/now-playing.json" and params.get("display") == "plex"
               for path, params in plex_requests)
    assert not plex.locator("body.kiosk-playback-active").count()
    plex.close()

    sky, _ = open_page(browser, "http://marquee.test/kiosk?view=sky", (390, 844))
    sky.wait_for_selector('[aria-current="page"][data-view="astronomy"]')
    assert sky.locator('[aria-current="page"]').count() == 1
    assert "GENERIC" not in sky.locator(".kiosk-section").inner_text()
    sky.close()

    for viewport in ((1500, 1000), (390, 844)):
        pfl, _ = open_page(browser, "http://marquee.test/kiosk?view=pfl", viewport)
        empty = pfl.locator('.kiosk-section[data-section="pfl"] [data-lifecycle="empty"]')
        empty.wait_for()
        section = pfl.locator('.kiosk-section[data-section="pfl"]')
        box, section_box = empty.bounding_box(), section.bounding_box()
        assert box and section_box
        assert box["x"] >= section_box["x"]
        assert box["x"] + box["width"] <= section_box["x"] + section_box["width"] + 1
        assert pfl.locator("html").evaluate("el => el.scrollWidth <= innerWidth + 1")
        if viewport[0] > 900:
            assert box["width"] >= 900
            assert box["height"] >= 0.45 * section_box["height"]
        pfl.close()

    browser.close()
    print("PASS: ambient/Home and explicit Plex authority, Sky alias identity, and PFL empty geometry")

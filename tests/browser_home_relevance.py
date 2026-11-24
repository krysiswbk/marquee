"""Home only promotes destinations and panels that have current content."""

import os
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
state = {"cards": [], "contexts": [], "sky": {}}


def route(request):
    path = request.request.url.split("?", 1)[0].split("marquee.test", 1)[-1]
    if path == "/kiosk":
        return request.fulfill(path=str(ROOT / "output/index.html"), content_type="text/html")
    if path == "/api/config":
        return request.fulfill(json={"providers": {
            key: {"enabled": key != "music", "targets": ["kiosk"]}
            for key in ("plex", "weather", "tv", "music", "calendar", "astronomy")
        }, "fallback": {}})
    if path == "/contexts":
        return request.fulfill(json={"contexts": state["contexts"]})
    if path == "/api/brain":
        return request.fulfill(json={"fresh": True, "openings": [], "events": [],
                                     "alerts": [], "people": [], "cards": state["cards"]})
    if path == "/ha-weather.json":
        return request.fulfill(json=state["sky"])
    if path == "/now-playing.json":
        return request.fulfill(json={"playing": False, "state": "idle", "availability": "idle"})
    if path in ("/settings.json", "/live-settings.json"):
        return request.fulfill(json={"transitionMs": 0})
    asset = ROOT / "output" / path.lstrip("/")
    if asset.is_file():
        return request.fulfill(path=str(asset))
    return request.fulfill(json={})


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"]
    )
    page = browser.new_page(viewport={"width": 1500, "height": 900})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.route("**/*", route)
    page.goto("http://marquee.test/kiosk", wait_until="domcontentloaded")
    page.wait_for_function("document.querySelector('#brain-agenda')?.dataset.agendaState === 'empty'")
    page.wait_for_function("document.querySelector('.kiosk-primary')?.dataset.signature === ''")
    assert page.locator("#brain-agenda").is_hidden()
    assert page.locator(".brain-shell").evaluate("el => el.classList.contains('brain-no-agenda')")
    assert page.locator("#brain-house").evaluate("el => el.getBoundingClientRect().bottom <= document.querySelector('.brain-dock').getBoundingClientRect().top")
    assert page.locator('.kiosk-primary a[data-view=""]').count() == 1
    assert page.locator('.kiosk-primary a[data-view="tv"]').count() == 0

    state["cards"] = [{"type": "calendar_event", "title": "Dinner", "subtitle": "Tonight"}]
    state["contexts"] = [{"id": "tv:one", "provider": "tv", "title": "New episode",
                          "starts": "2099-01-01T12:00:00Z"}]
    page.evaluate("() => { window.MarqueeLifecycle.request('brain'); window.MarqueeNavigation.refresh(); }")
    page.wait_for_function("!document.querySelector('#brain-agenda').hidden")
    page.wait_for_function("document.querySelector('.kiosk-primary a[data-view=tv]') !== null")
    assert page.locator('.kiosk-primary a[data-view="music"]').count() == 0
    assert page.locator('.kiosk-primary a[data-view="weather"]').count() == 0
    assert page.locator('.kiosk-primary a[data-view="plex"]').count() == 0
    page.goto("http://marquee.test/kiosk?view=weather", wait_until="domcontentloaded")
    page.wait_for_selector('.kiosk-primary a[data-view="weather"][aria-current="page"]')
    assert page.locator("#kiosk-panel").is_visible()
    page.locator('.kiosk-primary a[data-view=""]').click()
    page.wait_for_function("new URL(location.href).searchParams.get('view') === null")
    assert page.locator('.kiosk-primary a[data-view="weather"]').count() == 0
    page.evaluate("window.MarqueeNavigation.resolve({playing: true, title: 'Film'})")
    page.wait_for_function("document.querySelector('.kiosk-primary a[data-view=plex]') !== null")
    page.evaluate("window.MarqueeNavigation.resolve({playing: false, state: 'idle'})")
    page.wait_for_function("document.querySelector('.kiosk-primary a[data-view=plex]') === null")
    assert not errors, errors
    page.close()
    state.update(cards=[], contexts=[], sky={"sky": {"sun": {}, "moon": {}, "aircraft": []}})
    sky_page = browser.new_page(viewport={"width": 1500, "height": 900})
    sky_page.route("**/*", route)
    sky_page.goto("http://marquee.test/kiosk", wait_until="domcontentloaded")
    sky_page.wait_for_function("document.querySelector('.kiosk-primary')?.dataset.signature === ''")
    assert sky_page.locator('.kiosk-primary a[data-view="astronomy"]').count() == 0
    state["sky"] = {"sky": {"sun": {"is_day": False, "elevation": 0}}}
    sky_page.evaluate("window.MarqueeNavigation.refresh()")
    sky_page.wait_for_function("document.querySelector('.kiosk-primary a[data-view=astronomy]') !== null")
    state["sky"] = {"sky": {"sun": {}, "moon": {}, "aircraft": []}}
    sky_page.evaluate("window.MarqueeNavigation.refresh()")
    sky_page.wait_for_function("document.querySelector('.kiosk-primary a[data-view=astronomy]') === null")
    sky_page.close()
    browser.close()
    print("PASS: Home hides empty destinations and agenda, then reveals live content")

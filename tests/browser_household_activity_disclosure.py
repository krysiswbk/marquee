"""Rendered lifecycle and responsive contract for the household activity modal."""

import os
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
VIEWPORTS = [(360, 800), (430, 852), (700, 900), (1024, 600), (1500, 900)]


def snapshot(events, fresh=True):
    return {
        "fresh": fresh,
        "events": events,
        "openings": [],
        "cards": [],
        "alerts": [],
        "people": [],
    }


def events(count=8):
    now = int(time.time())
    return [{
        "id": f"fixture:activity:{index}",
        "title": "X" * 500 if index == 0 else f"Front door activity {index} with a deliberately long authoritative description",
        "category": "door",
        "at": now - index * 30,
        "expires": now + 900,
    } for index in range(count)]


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"]
    )
    for width, height in VIEWPORTS:
        page = browser.new_page(viewport={"width": width, "height": height})
        payload = events()
        stale = {"value": False}

        def route(route):
            request = route.request
            path = request.url.split("?", 1)[0].split("marquee.test", 1)[-1]
            if path in ("/live", "/kiosk"):
                return route.fulfill(path=str(ROOT / "output/index.html"), content_type="text/html")
            if path == "/api/brain":
                return route.fulfill(json=snapshot(payload, not stale["value"]))
            if path in ("/api/config", "/settings.json", "/live-settings.json"):
                return route.fulfill(json={"providers": {}, "fallback": {}, "transitionMs": 0})
            if path in ("/ambient.json", "/ha-weather.json"):
                return route.fulfill(json={})
            asset = ROOT / "output" / path.lstrip("/")
            if asset.is_file():
                return route.fulfill(path=str(asset))
            return route.fulfill(json={})

        page.route("**/*", route)
        page.goto("http://marquee.test/live", wait_until="domcontentloaded")
        page.wait_for_selector("#brain-activity-open")
        trigger = page.locator("#brain-activity-open")
        assert trigger.is_visible()
        page.evaluate("""() => {
            const panel = document.querySelector('#brain-agenda');
            panel.setAttribute('aria-hidden', 'false');
            panel.inert = true;
        }""")
        assert page.locator("#brain-agenda").evaluate("el => el.inert && el.getAttribute('aria-hidden') === 'false'")
        trigger.focus()
        trigger.click()
        page.wait_for_function("document.querySelector('#brain-activity-view').hidden === false")
        assert page.url.endswith("#activity")
        assert page.locator("#brain-activity-record").count() == 0
        assert page.locator(".brain-activity-record").count() == 8
        assert page.locator("#brain-activity-close").bounding_box()["height"] >= 44
        assert page.locator("#brain-activity-list").get_attribute("role") == "region"
        assert page.locator("#brain-activity-list").evaluate("el => el.scrollHeight > el.clientHeight")
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        assert page.locator("#brain-activity-view").evaluate("el => el.scrollWidth <= el.clientWidth")
        assert page.locator("#brain-activity-list").evaluate("el => el.scrollWidth <= el.clientWidth")
        assert page.locator(".brain-activity-record strong").first.evaluate("el => el.textContent.length === 500")
        assert page.locator(".brain-activity-record strong").first.evaluate("el => { const r=el.getBoundingClientRect(); const p=el.parentElement.getBoundingClientRect(); return r.right <= p.right + 1 && r.left >= p.left - 1 }")
        assert page.locator(".brain-activity-record strong").evaluate_all("nodes => new Set(nodes.map(n => n.textContent)).size === 8")
        assert page.locator("#brain-house").evaluate("el => el.inert && el.getAttribute('aria-hidden') === 'true'")
        assert page.locator(".ambient-veil").evaluate("el => el.inert && el.getAttribute('aria-hidden') === 'true'")

        page.locator("#brain-activity-close").focus()
        page.keyboard.press("Tab")
        assert page.evaluate("document.activeElement.id === 'brain-activity-list'")
        page.keyboard.press("Tab")
        assert page.evaluate("document.activeElement.id === 'brain-activity-close'")
        page.keyboard.press("Shift+Tab")
        assert page.evaluate("document.activeElement.id === 'brain-activity-list'")
        page.locator("#brain-activity-list").focus()
        assert page.locator("#brain-activity-list").evaluate("el => el.scrollTop === 0")
        page.locator("#brain-activity-list").press("PageDown")
        page.wait_for_function("document.querySelector('#brain-activity-list').scrollTop > 0")
        assert page.locator("#brain-activity-list").evaluate("el => el.scrollTop > 0 && el.scrollTop < el.scrollHeight")

        page.locator("#brain-activity-open").focus()
        stale["value"] = True
        page.wait_for_timeout(3300)
        page.wait_for_function("document.querySelector('#brain-activity-count').textContent.includes('unavailable')")
        assert not page.locator("#brain-activity-open").count()
        page.locator("#brain-activity-close").click()
        page.wait_for_function("document.querySelector('#brain-activity-view').hidden")
        page.wait_for_timeout(100)
        assert page.evaluate("document.activeElement.id === 'brain-headline'")
        assert page.evaluate("document.activeElement !== document.body")
        assert page.locator(".ambient-veil").evaluate("el => !el.inert && el.getAttribute('aria-hidden') === 'true'")
        assert page.locator("#brain-agenda").evaluate("el => el.inert && el.getAttribute('aria-hidden') === 'false'")
        page.close()
        print(f"activity {width}x{height}: modal focus, scroll, stale fallback, overflow PASS")

    for path in ("/live", "/kiosk"):
        page = browser.new_page(viewport={"width": 430, "height": 852})
        console_errors = []
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error: console_errors.append(str(error)))
        payload = events()

        def connected_opener_route(route):
            request = route.request
            route_path = request.url.split("?", 1)[0].split("marquee.test", 1)[-1]
            if route_path in ("/live", "/kiosk"):
                return route.fulfill(path=str(ROOT / "output/index.html"), content_type="text/html")
            if route_path == "/api/brain":
                return route.fulfill(json=snapshot(payload, True))
            if route_path == "/events":
                return route.fulfill(status=200, headers={"content-type": "text/event-stream"}, body=": connected\n\n")
            if route_path in ("/api/config", "/settings.json", "/live-settings.json"):
                return route.fulfill(json={"providers": {}, "fallback": {}, "transitionMs": 0})
            if route_path in ("/ambient.json", "/ha-weather.json"):
                return route.fulfill(json={})
            asset = ROOT / "output" / route_path.lstrip("/")
            if asset.is_file():
                return route.fulfill(path=str(asset))
            return route.fulfill(json={})

        page.route("**/*", connected_opener_route)
        page.goto(f"http://marquee.test{path}", wait_until="domcontentloaded")
        page.wait_for_selector("#brain-activity-open")
        page.evaluate("document.querySelector('#brain-activity-open').click(); document.querySelector('#brain-activity-close').click()")
        page.wait_for_function("document.querySelector('#brain-activity-view').hidden")
        page.wait_for_timeout(200)
        assert page.evaluate("document.activeElement.id === 'brain-activity-open'")
        assert page.url.endswith(path)
        assert not console_errors, console_errors
        page.close()
        print(f"activity {path} 430x852 connected-opener focus and console PASS")

    page = browser.new_page(viewport={"width": 430, "height": 852})
    payload = events()
    responses = {"count": 0}

    def direct_hash_route(route):
        path = route.request.url.split("?", 1)[0].split("marquee.test", 1)[-1]
        if path in ("/live", "/kiosk"):
            return route.fulfill(path=str(ROOT / "output/index.html"), content_type="text/html")
        if path == "/api/brain":
            responses["count"] += 1
            return route.fulfill(json=snapshot([], True) if responses["count"] == 1 else snapshot(payload, True))
        if path in ("/api/config", "/settings.json", "/live-settings.json", "/ambient.json", "/ha-weather.json"):
            return route.fulfill(json={"providers": {}, "fallback": {}, "transitionMs": 0})
        asset = ROOT / "output" / path.lstrip("/")
        return route.fulfill(path=str(asset), content_type="text/javascript" if asset.suffix == ".js" else "text/html") if asset.is_file() else route.fulfill(json={})

    page.route("**/*", direct_hash_route)
    page.goto("http://marquee.test/live#activity", wait_until="domcontentloaded")
    page.wait_for_function("document.querySelectorAll('.brain-activity-record').length === 8")
    assert page.locator("#brain-activity-view").is_visible()
    assert page.url.endswith("#activity")
    page.keyboard.press("Escape")
    page.wait_for_function("document.querySelector('#brain-activity-view').hidden")
    assert page.evaluate("location.hash === '' && document.activeElement.id === 'brain-headline'")
    page.close()

    page = browser.new_page(viewport={"width": 1024, "height": 600})
    kiosk_payload = snapshot(payload, True)

    def kiosk_history_route(route):
        path = route.request.url.split("?", 1)[0].split("marquee.test", 1)[-1]
        if path == "/kiosk":
            return route.fulfill(path=str(ROOT / "output/index.html"), content_type="text/html")
        if path == "/api/brain":
            return route.fulfill(json=kiosk_payload)
        if path == "/api/config":
            return route.fulfill(json={"providers": {"gaming": {"enabled": True, "targets": ["kiosk"]}}, "fallback": {}, "transitionMs": 0})
        if path == "/contexts":
            return route.fulfill(json={"contexts": [{"id": "gaming:history", "provider": "gaming", "title": "History fixture", "starts": "2099-01-01T12:00:00Z"}]})
        if path in ("/providers", "/settings.json", "/live-settings.json", "/ambient.json", "/ha-weather.json"):
            return route.fulfill(json={"providers": {}})
        asset = ROOT / "output" / path.lstrip("/")
        return route.fulfill(path=str(asset)) if asset.is_file() else route.fulfill(json={})

    page.route("**/*", kiosk_history_route)
    page.goto("http://marquee.test/kiosk#activity", wait_until="domcontentloaded")
    page.wait_for_function("document.querySelectorAll('.brain-activity-record').length === 8")
    page.keyboard.press("Escape")
    page.wait_for_function("document.querySelector('#brain-activity-view').hidden")
    page.locator('.kiosk-primary [data-view="gaming"]').click()
    page.wait_for_function("new URL(location.href).searchParams.get('view') === 'gaming'")
    page.go_back(wait_until="domcontentloaded")
    page.wait_for_function("new URL(location.href).searchParams.get('view') === null")
    assert page.evaluate("document.activeElement?.dataset.view === ''")
    page.close()
    print("activity direct-hash close does not poison next kiosk traversal focus PASS")

    page = browser.new_page(viewport={"width": 430, "height": 852})
    def delayed_route(route):
        path = route.request.url.split("?", 1)[0].split("marquee.test", 1)[-1]
        if path in ("/live", "/kiosk"):
            return route.fulfill(path=str(ROOT / "output/index.html"), content_type="text/html")
        if path == "/api/brain":
            return route.fulfill(json=snapshot(payload, True))
        if path in ("/api/config", "/settings.json", "/live-settings.json", "/ambient.json", "/ha-weather.json"):
            return route.fulfill(json={"providers": {}, "fallback": {}, "transitionMs": 0})
        asset = ROOT / "output" / path.lstrip("/")
        return route.fulfill(path=str(asset), content_type="text/javascript" if asset.suffix == ".js" else "text/html") if asset.is_file() else route.fulfill(json={})

    page.route("**/*", delayed_route)
    page.goto("http://marquee.test/live", wait_until="domcontentloaded")
    page.wait_for_selector("#brain-activity-open")
    page.locator("#brain-activity-open").dispatch_event("click")
    page.wait_for_function("document.querySelectorAll('.brain-activity-record').length === 8")
    assert page.locator("#brain-activity-view").is_visible()
    assert page.url.endswith("#activity")
    page.go_back(wait_until="domcontentloaded")
    page.wait_for_selector("#brain-activity-view", state="attached")
    page.wait_for_function("document.querySelector('#brain-activity-view').hidden")
    assert page.evaluate("location.hash === ''")
    page.go_forward(wait_until="domcontentloaded")
    page.wait_for_selector("#brain-activity-view", state="attached")
    page.wait_for_function("document.querySelector('#brain-activity-view').hidden === false")
    assert page.url.endswith("#activity")
    page.keyboard.press("Escape")
    page.wait_for_selector("#brain-activity-view", state="attached")
    page.wait_for_function("document.querySelector('#brain-activity-view').hidden")
    page.wait_for_function("location.hash === '' && document.activeElement.id === 'brain-headline'")
    assert page.evaluate("history.length")
    page.close()
    browser.close()
    print("activity direct-hash async payload and trigger Back/Forward/Escape lifecycle PASS")

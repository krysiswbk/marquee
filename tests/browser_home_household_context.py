"""Rendered household context, agenda space and HA return at display sizes."""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "REPORTS/marquee-visual-campaign/home-usefulness-batch10"
EVIDENCE.mkdir(parents=True, exist_ok=True)


def snapshot(kind):
    now = datetime.now(timezone.utc)
    cards = [
        {
            "type": "calendar_event",
            "title": f"Household event {index}: a title that needs space to read",
            "subtitle": f"In {index} days · 6:30 PM",
            "starts": (now + timedelta(days=index)).isoformat(),
        }
        for index in range(1, 11)
    ]
    state = {
        "fresh": kind != "offline", "lock": "locked", "sleeping": True,
        "guests": True, "garage_occupied": True,
        "people": [{"name": "Alex", "state": "Home"}, {"name": "Jamie", "state": "Away"}],
        "openings": [], "events": [], "cards": cards, "alerts": [],
    }
    if kind == "people":
        state.update(sleeping=False, guests=False, garage_occupied=False)
    if kind in ("alert", "multiple_openings"):
        state["openings"] = [{"id": "fixture:front", "name": "Front door", "category": "exterior_door",
                              "state": "open", "since": now.timestamp() - 120, "duration": 120}]
    if kind == "multiple_openings":
        state["openings"].append({"id": "fixture:window", "name": "Kitchen window",
                                  "category": "window", "state": "open",
                                  "since": now.timestamp() - 90, "duration": 90})
    if kind == "activity":
        state["events"] = [
            {"id": f"fixture:event:{index}", "title": "Front door lock locked" if index == 0 else "Front door closed",
             "at": now.timestamp() - 120 - 60 * index, "expires": now.timestamp() + 600}
            for index in range(2)
        ]
    return state


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"]
    )
    baseline = os.environ.get("MARQUEE_HOME_BASELINE") == "1"
    evidence_dir = EVIDENCE / ("before" if baseline else "after")
    evidence_dir.mkdir(parents=True, exist_ok=True)
    for width, height in ((1500, 971), (1280, 800), (1024, 600)):
        for kind in ("quiet", "alert", "multiple_openings", "activity", "people", "offline"):
            page = browser.new_page(viewport={"width": width, "height": height})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))

            def route(request):
                url = request.request.url
                path = url.split("?", 1)[0].split("marquee.test", 1)[-1]
                if path == "/kiosk":
                    return request.fulfill(path=str(ROOT / "output/index.html"), content_type="text/html")
                if path == "/api/brain":
                    return request.fulfill(json=snapshot(kind))
                if path in ("/api/config", "/settings.json", "/live-settings.json"):
                    return request.fulfill(json={"providers": {}, "fallback": {}, "transitionMs": 0})
                if path in ("/ambient.json", "/ha-weather.json"):
                    return request.fulfill(json={})
                asset = ROOT / "output" / path.lstrip("/")
                if asset.is_file():
                    return request.fulfill(path=str(asset))
                return request.fulfill(json={})

            page.route("**/*", route)
            page.goto("http://marquee.test/kiosk", wait_until="domcontentloaded")
            page.wait_for_function("document.querySelector('#brain-house')?.dataset.state")
            page.wait_for_timeout(450)
            page.screenshot(path=str(evidence_dir / f"{kind}-{width}x{height}.png"))
            if not baseline:
                assert not errors, errors
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                state = page.locator("#brain-household-state")
                if kind == "offline":
                    assert not state.is_visible()
                    assert "unavailable" in page.locator("#brain-summary").inner_text()
                else:
                    if kind == "people":
                        assert state.inner_text() == "Alex home"
                    else:
                        assert "Someone sleeping" in state.inner_text()
                        assert "Guests expected" in state.inner_text()
                        assert "Garage occupied" in state.inner_text()
                        assert "Alex home" not in state.inner_text()
                    assert "Jamie · Away" in page.locator("#brain-people").inner_text()
                    assert "front door" in page.locator("#brain-house").inner_text().lower()
                    if kind in ("alert", "multiple_openings"):
                        assert "front door open" in page.locator("#brain-headline").inner_text().lower()
                    if kind == "multiple_openings":
                        tags = page.locator("#brain-openings .brain-tag")
                        assert tags.count() == 1
                        assert "Kitchen window" in tags.first.inner_text()
                        assert tags.first.evaluate("el => el.getBoundingClientRect().bottom <= document.querySelector('#brain-house').getBoundingClientRect().bottom + 1")
                        if width == 1024:
                            font_size = tags.first.evaluate("el => parseFloat(getComputedStyle(el).fontSize)")
                            print("1024 secondary opening font:", font_size)
                            assert font_size >= 14
                    if kind == "activity":
                        assert page.locator("#brain-activity").is_visible()
                        assert page.locator("#brain-activity").evaluate("""el => {
                          const top = el.getBoundingClientRect().top;
                          return [...document.querySelectorAll('.idle-clock, .idle-date, .idle-weather')]
                            .filter(node => node.getClientRects().length)
                            .every(node => node.getBoundingClientRect().bottom + 4 <= top);
                        }"""), (width, height, "activity overlaps the clock or weather")
                    visible = page.locator("#brain-agenda .brain-agenda-item:visible")
                    minimum = (8 if kind == "quiet" else 7) if width == 1500 else (5 if width == 1280 else 3)
                    if kind == "multiple_openings":
                        minimum -= 1  # A second opening takes priority over one agenda row.
                    assert visible.count() >= minimum, (kind, width, visible.count())
                    assert page.locator("#brain-agenda").evaluate("el => el.getBoundingClientRect().bottom <= document.querySelector('.brain-dock').getBoundingClientRect().top + 1")
                    assert visible.evaluate_all("nodes => nodes.every(node => node.getBoundingClientRect().bottom <= document.querySelector('.brain-agenda-list').getBoundingClientRect().bottom + 1)")
            page.close()

    if not baseline:
        page = browser.new_page(viewport={"width": 1500, "height": 971})
        visits = {"ha": 0}

        def route_ha(request):
            if request.request.url.startswith("http://ha.test/"):
                visits["ha"] += 1
                body = ('<iframe src="http://marquee.test/kiosk" style="position:fixed;inset:0;width:100%;height:100%;border:0"></iframe>'
                        if visits["ha"] == 1 else '<h1>Home Assistant controls</h1>')
                return request.fulfill(body=body, content_type="text/html")
            if request.request.url.split("?", 1)[0].endswith("/api/brain"):
                return request.fulfill(json=snapshot("quiet"))
            return route(request)

        page.route("**/*", route_ha)
        page.goto("http://ha.test/dashboard", wait_until="domcontentloaded")
        action = page.frame_locator("iframe").get_by_role("button", name="Home controls")
        action.wait_for(state="visible")
        page.frame_locator("iframe").locator("body.idle #brain-house[data-state=ready]").wait_for()
        page.wait_for_timeout(500)  # Cross-origin iframe paint can lag the ready DOM.
        for _ in range(3):
            screenshot = page.screenshot(path=str(evidence_dir / "ha-popup-1500x971.png"))
            if len(screenshot) > 100_000:
                break
            page.wait_for_timeout(500)
        assert len(screenshot) > 100_000, "HA iframe did not paint into the screenshot"
        assert action.bounding_box()["height"] >= 44
        action.focus()
        assert action.evaluate("el => el === document.activeElement")
        action.press("Enter")
        page.get_by_role("heading", name="Home Assistant controls").wait_for()
        page.close()

        # Firefox may expose neither a referrer nor ancestorOrigins when HA
        # embeds its version-marked popup under a no-referrer policy.
        page = browser.new_page(viewport={"width": 1500, "height": 971})
        page.add_init_script("""try {
          Object.defineProperty(location, 'ancestorOrigins', {configurable: true, value: undefined});
        } catch (_) { /* Chromium may expose a non-configurable native property. */ }""")

        def route_no_referrer(request):
            url = request.request.url
            if url.startswith("http://ha.test/dashboard"):
                return request.fulfill(
                    body='<iframe src="http://marquee.test/kiosk?v=household-desk-2.9.1" referrerpolicy="no-referrer" style="position:fixed;inset:0;width:100%;height:100%;border:0"></iframe>',
                    content_type="text/html", headers={"Referrer-Policy": "no-referrer"},
                )
            if url.startswith("http://10.10.9.5:8123/dashboard-homepage/0"):
                return request.fulfill(body="<h1>Home Assistant controls</h1>", content_type="text/html")
            if url.split("?", 1)[0].endswith("/api/brain"):
                return request.fulfill(json=snapshot("quiet"))
            return route(request)

        page.route("**/*", route_no_referrer)
        page.goto("http://ha.test/dashboard", wait_until="domcontentloaded")
        popup = page.frame_locator("iframe")
        popup.locator("body.idle #brain-house[data-state=ready]").wait_for()
        assert popup.locator("body").evaluate("() => document.referrer === ''")
        action = popup.get_by_role("button", name="Home controls")
        action.wait_for(state="visible")
        action.click()
        page.get_by_role("heading", name="Home Assistant controls").wait_for()
        assert page.url.startswith("http://10.10.9.5:8123/dashboard-homepage/0?BrowserID=")
        page.close()

        # HA may also expose only its origin. That hint cannot restore the
        # dashboard route, so the marker must still choose the installed URL.
        page = browser.new_page(viewport={"width": 1500, "height": 971})

        def route_origin(request):
            url = request.request.url
            if url.startswith("http://ha.test/dashboard"):
                return request.fulfill(
                    body='<iframe src="http://marquee.test/kiosk?v=household-desk-2.9.1" style="position:fixed;inset:0;width:100%;height:100%;border:0"></iframe>',
                    content_type="text/html", headers={"Referrer-Policy": "origin"},
                )
            if url.startswith("http://10.10.9.5:8123/dashboard-homepage/0"):
                return request.fulfill(body="<h1>Home Assistant controls</h1>", content_type="text/html")
            if url.split("?", 1)[0].endswith("/api/brain"):
                return request.fulfill(json=snapshot("quiet"))
            return route(request)

        page.route("**/*", route_origin)
        page.goto("http://ha.test/dashboard", wait_until="domcontentloaded")
        popup = page.frame_locator("iframe")
        popup.locator("body.idle #brain-house[data-state=ready]").wait_for()
        assert popup.locator("body").evaluate("() => document.referrer === 'http://ha.test/'")
        popup.get_by_role("button", name="Home controls").click()
        page.get_by_role("heading", name="Home Assistant controls").wait_for()
        assert page.url.startswith("http://10.10.9.5:8123/dashboard-homepage/0?BrowserID=")
        page.close()
    browser.close()
    print("PASS: household facts, agenda, stale truth and HA return at display sizes")

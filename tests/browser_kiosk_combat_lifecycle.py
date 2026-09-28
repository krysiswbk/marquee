"""Deterministic UFC/PFL lifecycle and responsive kiosk contracts."""

import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
VIEWPORTS = [(393, 852), (430, 852), (700, 900), (1024, 600), (1500, 900)]


def event(promotion, state="UPCOMING", suffix="1"):
    return {
        "id": f"{promotion}:fixture-{suffix}",
        "provider": promotion,
        "source": promotion,
        "title": f"{promotion.upper()} Fight Night {suffix}",
        "subtitle": "Main event",
        "detail": "Las Vegas",
        "starts": "2099-10-01T23:00:00+00:00",
        "eventState": state,
        "status": "Live now" if state == "LIVE" else "Coming up",
        "left": {"name": "Fighter Alpha", "record": "18-3"},
        "right": {"name": "Fighter Bravo", "record": "16-2"},
        "rows": ["CARD · Main event"],
        "targets": ["kiosk"],
        "expires": "2099-10-05T00:00:00+00:00",
    }


def run():
    errors = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"]
        )
        for width, height in VIEWPORTS:
            for promotion in ("ufc", "pfl"):
                for lifecycle in ("empty", "stale", "unavailable", "populated"):
                    page = browser.new_page(viewport={"width": width, "height": height})
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)

                    def route(route):
                        request = route.request
                        path = request.url.split("?", 1)[0].split("marquee.test", 1)[-1]
                        if path in ("/kiosk", "/live"):
                            return route.fulfill(path=str(ROOT / "output/index.html"), content_type="text/html")
                        asset = ROOT / "output" / path.lstrip("/")
                        if asset.is_file():
                            return route.fulfill(path=str(asset))
                        if path == "/api/config":
                            return route.fulfill(json={"providers": {promotion: {"enabled": True, "targets": ["kiosk"]}}})
                        if path == "/contexts":
                            values = [] if lifecycle != "populated" else [event(promotion), event(promotion, suffix="2")]
                            return route.fulfill(json={"contexts": values, "browse": {}})
                        if path == "/providers":
                            health = {"state": "degraded", "stale": True, "reason": "schedule refresh delayed"} if lifecycle == "stale" else {"state": "disabled", "reason": "source disabled for fixture"} if lifecycle == "unavailable" else {"state": "ok"}
                            return route.fulfill(json={"providers": {promotion: health}})
                        if path in ("/settings.json", "/live-settings.json"):
                            return route.fulfill(json={"transitionMs": 0})
                        if path == "/ambient.json":
                            return route.fulfill(json={"opacity": 0})
                        if path == "/events":
                            return route.fulfill(body="", content_type="text/event-stream")
                        return route.fulfill(json={})

                    page.route("**/*", route)
                    page.goto(f"http://marquee.test/kiosk?view={promotion}", wait_until="domcontentloaded")
                    page.wait_for_selector(".kiosk-section:not([hidden])")
                    if lifecycle == "populated":
                        page.wait_for_selector(".kiosk-broadcast-layout")
                    else:
                        page.wait_for_function("document.querySelector('[data-lifecycle]') !== null")
                    if lifecycle == "empty":
                        assert page.locator('[data-lifecycle="empty"]').is_visible()
                        assert promotion.upper() in page.locator(".kiosk-state").inner_text()
                        assert "No upcoming" in page.locator(".kiosk-state").inner_text()
                        assert page.locator('[data-lifecycle="empty"] .kiosk-state-mark').count() == 0
                    elif lifecycle == "stale":
                        assert page.locator('[data-lifecycle="stale"]').is_visible()
                        assert "not being presented as current" in page.locator(".kiosk-state").inner_text()
                    elif lifecycle == "unavailable":
                        assert page.locator('[data-lifecycle="unavailable"]').is_visible()
                        assert "source cannot be reached" in page.locator(".kiosk-state").inner_text()
                    else:
                        assert page.locator(".kiosk-broadcast-layout").is_visible()
                        assert page.locator(".kiosk-broadcast-matchup").is_visible()
                        disclosure = page.get_by_role("button", name=f"View all 2 {promotion.upper()} events")
                        assert disclosure.is_visible()
                        disclosure.click()
                        assert page.locator(".kiosk-sports-detail").is_visible()
                        assert page.locator("#kiosk-section-title").evaluate("el => document.activeElement === el"), page.evaluate("() => ({active: document.activeElement?.outerHTML?.slice(0,240), heading: document.querySelector('#kiosk-section-title')?.outerHTML})")
                        assert page.url.endswith(f"view={promotion}&mode=all&page=1")
                        assert page.evaluate("() => document.documentElement.scrollWidth <= innerWidth")
                        assert page.locator(".kiosk-sports-content").evaluate("el => el.scrollHeight >= el.clientHeight && getComputedStyle(el).overflowY === 'auto'")
                        assert page.evaluate("() => { const el=document.querySelector('.kiosk-sports-controls'), r=el.getBoundingClientRect(), p=el.closest('.kiosk-section').getBoundingClientRect(), q=document.querySelector('.kiosk-rail').getBoundingClientRect(); return {ok:r.bottom <= p.bottom + 1 && r.top < q.top, r:{top:r.top,bottom:r.bottom},p:{top:p.top,bottom:p.bottom},q:{top:q.top,bottom:q.bottom}}; }")['ok'], page.evaluate("() => { const el=document.querySelector('.kiosk-sports-controls'), r=el.getBoundingClientRect(), p=el.closest('.kiosk-section').getBoundingClientRect(), q=document.querySelector('.kiosk-rail').getBoundingClientRect(); return {r:{top:r.top,bottom:r.bottom},p:{top:p.top,bottom:p.bottom},q:{top:q.top,bottom:q.bottom}}; }")
                        assert page.locator(".kiosk-sports-count").inner_text() == "Event 1 of 2"
                        page.get_by_role("button", name="Next event").click()
                        assert page.locator(".kiosk-sports-count").inner_text() == "Event 2 of 2"
                        assert page.evaluate("document.activeElement?.dataset?.sportsControl === 'previous'"), page.evaluate("() => ({tag:document.activeElement?.tagName, control:document.activeElement?.dataset?.sportsControl, id:document.activeElement?.id})")
                        page.keyboard.press("PageUp")
                        assert page.locator(".kiosk-sports-count").inner_text() == "Event 1 of 2"
                        assert page.evaluate("document.activeElement?.dataset?.sportsControl === 'next'")
                        page.get_by_role("button", name="Back to schedule").click()
                        assert page.get_by_role("button", name=f"View all 2 {promotion.upper()} events").is_visible()
                        assert page.evaluate("document.activeElement?.matches('[data-sports-disclosure]')"), page.evaluate("() => ({tag:document.activeElement?.tagName, cls:document.activeElement?.className, text:document.activeElement?.textContent})")
                        page.get_by_role("button", name=f"View all 2 {promotion.upper()} events").click()
                        page.wait_for_function("new URL(location.href).searchParams.get('mode') === 'all'")
                        page.go_back(); page.wait_for_function("!new URL(location.href).searchParams.has('mode')")
                        assert page.evaluate("document.activeElement?.matches('[data-sports-disclosure]')")
                        page.go_forward(); page.wait_for_function("new URL(location.href).searchParams.get('mode') === 'all'")
                        assert page.evaluate("document.activeElement?.id === 'kiosk-section-title'")
                        assert page.locator('.kiosk-rail a[data-view="' + promotion + '"][aria-current="page"]').count() == 1
                        panel_before_return = page.locator(".kiosk-section").bounding_box()
                        page.get_by_role("link", name="Return to Home", exact=True).click()
                        assert page.locator('.kiosk-primary a[data-view=""][aria-current="page"]').count() == 1
                    assert page.locator('[aria-current="page"]').count() == 1
                    if lifecycle != "populated":
                        assert page.locator('.kiosk-rail a[data-view="' + promotion + '"][aria-current="page"]').count() == 1
                    assert page.locator(".kiosk-section").evaluate("el => el.scrollWidth <= el.clientWidth + 1")
                    rail = page.locator(".kiosk-rail").bounding_box()
                    panel = panel_before_return if lifecycle == "populated" else page.locator(".kiosk-section").bounding_box()
                    assert panel["y"] + panel["height"] <= rail["y"] + 1, (width, height, promotion, lifecycle)
                    page.close()

        assert "Checking the published ${promotion} schedule." in (ROOT / "output/kiosk-menu.js").read_text()
        browser.close()
    assert not errors, errors
    print("PASS: UFC/PFL loading, resolved empty, stale, and populated states fit all target viewports without browser errors")


if __name__ == "__main__":
    run()

"""Deterministic direct-kiosk sports stage contracts and screenshot fixtures."""

import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
VIEWPORTS = [(1500, 900), (1920, 1080), (1920, 540), (700, 900), (430, 852), (320, 720)]
SVG = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Ccircle cx='50' cy='50' r='42' fill='%23b6f378'/%3E%3C/svg%3E"


def context(state="UPCOMING", logos=True, long_names=False, title="Toronto Maple Leafs"):
    left = {"name": "Toronto Maple Leafs" if not long_names else "The Toronto Maple Leafs Hockey Club", "abbr": "TOR", "homeAway": "home"}
    right = {"name": "Montreal Canadiens" if not long_names else "Les Canadiens de Montréal Hockey Club", "abbr": "MTL", "homeAway": "away"}
    if logos:
        left["logo"], right["logo"] = SVG, SVG
    if state == "LIVE":
        left["score"], right["score"] = "3", "2"
    if state in ("RESULT", "POST_EVENT"):
        left["score"], right["score"] = "4", "2"
    live = state == "LIVE"
    return {"id": "nhl:fixture", "provider": "nhl", "source": "nhl", "title": title, "subtitle": "NHL Hockey", "detail": "Scotiabank Arena", "broadcast": "Sportsnet", "starts": "2026-10-01T23:00:00+00:00", "eventState": state, "status": "Final" if state in ("RESULT", "POST_EVENT") else "In Progress" if live else "Coming up", "sourceStatus": "Final" if state in ("RESULT", "POST_EVENT") else "In Progress" if live else "", "left": left, "right": right, "targets": ["kiosk"], "expires": "2026-12-05T00:00:00+00:00", "rows": [], "lastGoal": "1st 9:08 · MTL · Cole Caufield", "powerPlay": "MTL" if live else "", "scoreDetails": ["1st 9:08 · MTL · Cole Caufield Goal (2), assists: Nick Suzuki", "2nd 2:14 · TOR · Auston Matthews Goal (4)"] if live else []}


def run():
    errors = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"])
        for width, height in VIEWPORTS:
            page = browser.new_page(viewport={"width": width, "height": height})
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
            for fixture in ("scheduled", "live", "final", "distinct", "empty", "stale"):
                def route(route):
                    path = route.request.url.split("?", 1)[0].split("marquee.test", 1)[-1]
                    if path in ("/kiosk", "/live"):
                        return route.fulfill(path=str(ROOT / "output/index.html"), content_type="text/html")
                    asset = ROOT / "output" / path.lstrip("/")
                    if asset.is_file():
                        return route.fulfill(path=str(asset))
                    if path == "/api/config":
                        return route.fulfill(json={"providers": {"nhl": {"enabled": True, "targets": ["kiosk"]}}})
                    if path == "/contexts":
                        item = [] if fixture in ("empty", "stale") else [context("LIVE" if fixture == "live" else "POST_EVENT" if fixture == "final" else "UPCOMING", logos=fixture != "scheduled", long_names=width <= 430, title="Stanley Cup Playoffs" if fixture == "distinct" else "Toronto Maple Leafs")]
                        return route.fulfill(json={"contexts": [], "browse": {"nhl": item}})
                    if path == "/providers":
                        health = {"nhl": {"state": "degraded", "stale": True, "reason": "NHL schedule has not refreshed"}} if fixture == "stale" else {"nhl": {"state": "ok"}}
                        return route.fulfill(json={"providers": health})
                    if path in ("/settings.json", "/live-settings.json"):
                        return route.fulfill(json={"transitionMs": 0})
                    if path == "/ambient.json":
                        return route.fulfill(json={"opacity": 0})
                    if path == "/events":
                        return route.fulfill(body="", content_type="text/event-stream")
                    return route.fulfill(json={})

                page.unroute("**/*")
                page.route("**/*", route)
                page.goto(f"http://marquee.test/kiosk?view=nhl&fixture={fixture}", wait_until="domcontentloaded")
                page.wait_for_selector(".kiosk-section:not([hidden])")
                if fixture in ("scheduled", "live", "final", "distinct"):
                    page.wait_for_selector(".kiosk-broadcast-layout")
                    assert page.locator(".kiosk-broadcast-matchup").is_visible()
                    assert page.locator(".kiosk-sport-context").is_visible()
                    assert page.locator(".kiosk-section").evaluate("el => el.scrollWidth <= el.clientWidth + 1"), (width, height, fixture)
                    geometry = page.locator(".kiosk-broadcast-matchup").evaluate("el => { const r=el.getBoundingClientRect(), p=el.closest('.kiosk-section').getBoundingClientRect(), i=el.querySelector('img,.kiosk-team-mark'); return {ok:r.width > 0 && r.height > 0 && r.bottom <= p.bottom + 1, r:{y:r.y,bottom:r.bottom,height:r.height}, p:{y:p.y,bottom:p.bottom,height:p.height}, css:i ? {height:getComputedStyle(i).height,width:getComputedStyle(i).width} : null, children:[...el.children].map(x=>({tag:x.tagName,rect:x.getBoundingClientRect().toJSON(),font:getComputedStyle(x).fontSize}))}; }")
                    assert geometry["ok"], (width, height, fixture, geometry)
                    if fixture == "scheduled":
                        assert page.locator(".kiosk-broadcast-state").inner_text() == "VS"
                        page.wait_for_timeout(250)
                        assert page.locator(".kiosk-broadcast-layout h2").count() == 0, page.evaluate("() => document.querySelector('.kiosk-broadcast-layout h2')?.parentElement?.outerHTML")
                    elif fixture == "distinct":
                        assert page.locator(".kiosk-broadcast-layout h2").inner_text() == "Stanley Cup Playoffs"
                    elif fixture == "live":
                        assert "3" in page.locator(".kiosk-broadcast-state").inner_text()
                        assert "LAST GOAL" in page.locator(".kiosk-sport-context").inner_text()
                        assert "POWER PLAY · MTL" in page.locator(".kiosk-sport-context").inner_text()
                        assert page.locator(".kiosk-sport-score-details").count() == 1
                        assert not page.locator(".kiosk-sport-score-details").evaluate("el => el.open")
                        page.locator(".kiosk-sport-score-details summary").click()
                        assert "Cole Caufield" in page.locator(".kiosk-sport-score-details li").first.inner_text()
                        page.locator(".kiosk-sport-score-details summary").click()
                    else:
                        assert "4" in page.locator(".kiosk-broadcast-state").inner_text()
                elif fixture == "empty":
                    assert page.locator('[data-lifecycle="empty"]').is_visible()
                else:
                    assert page.locator('[data-lifecycle="stale"]').is_visible()
                rail = page.locator(".kiosk-rail").bounding_box()
                panel = page.locator(".kiosk-section").bounding_box()
                assert panel["y"] + panel["height"] <= rail["y"] + 1, (width, height, fixture, panel, rail)
                if (width, height, fixture) in ((1500, 900, "scheduled"), (1920, 1080, "live"), (1920, 540, "final"), (430, 852, "scheduled")):
                    page.screenshot(path=f"/tmp/marquee-sports-{width}x{height}-{fixture}.png", full_page=True)
            page.close()
        browser.close()
    assert not errors, errors
    print("PASS: sports scheduled/live/final/empty/stale stages fit all target viewports with fallback marks, rail separation, and no browser errors")


if __name__ == "__main__":
    run()

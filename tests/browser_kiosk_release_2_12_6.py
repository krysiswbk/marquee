"""Browser regression for stable kiosk actions across ordinary refreshes."""

import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]


def calendar_contexts(refresh_number):
    return [{
        "id": f"calendar:event-{index}",
        "source": "calendar",
        "provider": "calendar",
        "type": "calendar_event",
        "subtype": "event",
        "title": f"Calendar event {index}",
        "subtitle": f"Refresh {refresh_number}" if index == 1 else "Stable detail",
        "location": "Home",
        "starts": f"2099-01-{index + 1:02d}T12:00:00Z",
        "ends": f"2099-01-{index + 1:02d}T13:00:00Z",
        "targets": ["kiosk"],
        "expires": "2100-01-01T00:00:00Z",
    } for index in range(6)]


def install_routes(page):
    refreshes = {"contexts": 0}

    def route(request):
        path = request.request.url.split("?", 1)[0].split("marquee.test", 1)[-1]
        if path in ("/kiosk", "/live"):
            return request.fulfill(path=str(ROOT / "output/index.html"), content_type="text/html")
        asset = ROOT / "output" / path.lstrip("/")
        if asset.is_file():
            return request.fulfill(path=str(asset))
        if path == "/api/config":
            return request.fulfill(json={"providers": {"calendar": {"enabled": True, "targets": ["kiosk"]}}})
        if path == "/contexts":
            refreshes["contexts"] += 1
            return request.fulfill(json={"contexts": calendar_contexts(refreshes["contexts"])})
        if path == "/providers":
            return request.fulfill(json={"providers": {"calendar": {"state": "ok"}}})
        if path in ("/settings.json", "/live-settings.json"):
            return request.fulfill(json={"transitionMs": 0})
        if path == "/ambient.json":
            return request.fulfill(json={"opacity": 0})
        return request.fulfill(json={})

    page.route("**/*", route)


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"]
    )
    page = browser.new_page(viewport={"width": 390, "height": 844}, reduced_motion="reduce")
    install_routes(page)
    page.goto("http://marquee.test/kiosk?view=calendar&mode=all", wait_until="domcontentloaded")
    page.wait_for_selector('.kiosk-calendar-detail')

    identity = page.evaluate("""async () => {
        const selectors = [
            '#kiosk-panel [data-view=""]', '#kiosk-panel [data-calendar-summary]'
        ];
        const refs = selectors.map(selector => document.querySelector(selector));
        if (refs.some(ref => !ref)) return {ok: false, reason: 'missing control', connected: refs.map(Boolean)};
        for (let cycle = 0; cycle < 3; cycle += 1) {
            await window.MarqueeNavigation.refresh();
            const same = refs.map((ref, index) => ref.isConnected && ref === document.querySelector(selectors[index]));
            if (same.some(value => !value)) return {ok: false, cycle: cycle + 1, same};
        }
        return {ok: true};
    }""")
    assert identity["ok"], identity

    page.locator('#kiosk-panel [data-calendar-summary]').click()
    assert page.url.endswith("/kiosk?view=calendar")

    page.goto("http://marquee.test/kiosk?view=calendar&mode=all", wait_until="domcontentloaded")
    page.wait_for_selector('.kiosk-calendar-detail')
    home = page.locator('#kiosk-panel [data-view=""]').element_handle()
    for _ in range(3):
        page.evaluate("() => window.MarqueeNavigation.refresh()")
        page.wait_for_function("node => node.isConnected", arg=home)
    page.locator('#kiosk-panel [data-view=""]').click()
    assert page.url.endswith("/kiosk")
    assert page.locator('.kiosk-primary a[data-view=""][aria-current="page"]').count() == 1
    browser.close()
    print("PASS: Calendar Home and summary actions survive ordinary refreshes and activate normally")

"""Editorial destinations fit the kiosk stage at tablet and wall sizes."""

import os
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
VIEWS = ("movies", "tv", "gaming")


def items(view):
    return [
        {"id": f"{view}:{index}", "provider": view,
         "title": f"{view.title()} title {index}", "subtitle": "Coming soon",
         "starts": f"2026-12-{index + 1:02d}T12:00:00Z", "targets": ["kiosk"]}
        for index in range(1, 7)
    ]


def run():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"]
        )
        for width, height in ((1280, 800), (1500, 1000), (3000, 2000)):
            for view in VIEWS:
                page = browser.new_page(viewport={"width": width, "height": height})
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))

                def route(route):
                    path = route.request.url.split("?", 1)[0].split("marquee.test", 1)[-1]
                    if path in ("/kiosk", "/live"):
                        return route.fulfill(path=str(ROOT / "output/index.html"), content_type="text/html")
                    asset = ROOT / "output" / path.lstrip("/")
                    if asset.is_file():
                        return route.fulfill(path=str(asset))
                    if path == "/api/config":
                        return route.fulfill(json={"providers": {
                            key: {"enabled": True, "targets": ["kiosk"]} for key in VIEWS
                        }})
                    if path == "/contexts":
                        return route.fulfill(json={"contexts": items(view)})
                    if path == "/providers":
                        return route.fulfill(json={"providers": {view: {"state": "ok"}}})
                    if path in ("/settings.json", "/live-settings.json"):
                        return route.fulfill(json={"transitionMs": 0})
                    if path == "/ambient.json":
                        return route.fulfill(json={"opacity": 0})
                    if path == "/events":
                        return route.fulfill(body="", content_type="text/event-stream")
                    return route.fulfill(json={})

                page.route("**/*", route)
                page.goto(f"http://marquee.test/kiosk?view={view}", wait_until="domcontentloaded")
                page.wait_for_selector(".kiosk-editorial-feature h2")
                geometry = page.locator(f'.kiosk-section[data-section="{view}"]').evaluate("""section => {
                    const rect = node => node.getBoundingClientRect();
                    const card = section.querySelector('.kiosk-editorial');
                    const feature = section.querySelector('.kiosk-editorial-feature');
                    const queue = section.querySelector('.kiosk-support');
                    return {panelScroll: section.scrollHeight - section.clientHeight,
                        sectionBottom: rect(section).bottom, card: rect(card).toJSON(),
                        feature: rect(feature).toJSON(), queue: rect(queue).toJSON(),
                        queueScroll: queue.scrollHeight - queue.clientHeight};
                }""")
                assert geometry["panelScroll"] <= 1, (width, height, view, geometry)
                assert geometry["card"]["bottom"] <= geometry["sectionBottom"] + 1, (width, height, view, geometry)
                assert geometry["feature"]["bottom"] <= geometry["sectionBottom"] + 1, (width, height, view, geometry)
                assert geometry["queue"]["bottom"] <= geometry["sectionBottom"] + 1, (width, height, view, geometry)
                if width == 3000:
                    assert geometry["card"]["width"] >= 2100, (view, geometry)
                    assert 350 <= geometry["card"]["x"] <= 450, (view, geometry)
                    assert geometry["card"]["height"] >= 1100, (view, geometry)
                assert not errors, (width, height, view, errors)
                page.close()
        browser.close()
    print("PASS: editorial stages fit above the feed and fill large kiosk screens")


if __name__ == "__main__":
    run()

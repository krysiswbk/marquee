"""Check that Street playback fits between the header and kiosk controls."""

import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
SUMMARY = "A long episode description stays available to read on the kiosk. " * 18
SESSION = {
    "playing": True, "state": "playing", "type": "episode", "key": "plex:episode",
    "title": "The Haunting", "subtitle": "S1 · E1 · 2018 - Steven Sees a Ghost",
    "summary": SUMMARY, "poster": True, "posterVersion": "fixture",
    "year": "2018", "runtime": "59m",
    "progress": {"offsetMs": 900000, "durationMs": 3540000},
    "session": {"device": "SHIELD", "client": "Plex", "platform": "Android", "local": True},
}


def route(request):
    path = request.request.url.split("?", 1)[0].split("marquee.test", 1)[-1]
    if path in ("/kiosk", "/live"):
        return request.fulfill(path=str(ROOT / "output/index.html"), content_type="text/html")
    responses = {
        "/now-playing.json": SESSION,
        "/settings.json": {"template": "street", "theme": "synthwave"},
        "/live-settings.json": {"template": "street", "theme": "synthwave"},
        "/api/config": {"providers": {"plex": {"enabled": True, "targets": ["kiosk"]}}},
        "/contexts": {"contexts": []},
        "/providers": {"providers": {"plex": {"state": "ok"}}},
        "/weather": {"temp": 17, "condition": "clear-night", "hourly": [], "daily": []},
        "/ambient.json": {"opacity": 0},
    }
    if path in responses:
        return request.fulfill(body=json.dumps(responses[path]), content_type="application/json")
    if path == "/poster.jpg":
        return request.fulfill(body="<svg xmlns='http://www.w3.org/2000/svg' width='600' height='900'><rect width='600' height='900' fill='#314a58'/></svg>", content_type="image/svg+xml")
    asset = ROOT / "output" / path.lstrip("/")
    if asset.is_file():
        return request.fulfill(path=str(asset))
    return request.fulfill(body="{}", content_type="application/json")


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"]
    )
    for width, height in ((1024, 600), (1280, 960)):
        page = browser.new_page(viewport={"width": width, "height": height})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.route("**/*", route)
        page.goto("http://marquee.test/kiosk", wait_until="domcontentloaded")
        page.wait_for_function("document.body.dataset.template === 'street' && document.querySelector('#plot')?.textContent.length > 500")
        page.wait_for_function("document.querySelector('.b-poster')?.getBoundingClientRect().width > 0")
        page.wait_for_timeout(300)
        boxes = page.evaluate("""() => {
          const rect = selector => {
            const element = document.querySelector(selector);
            const box = element.getBoundingClientRect();
            return {top: box.top, bottom: box.bottom, left: box.left,
                    right: box.right, width: box.width, height: box.height,
                    display: getComputedStyle(element).display,
                    scrollHeight: element.scrollHeight, clientHeight: element.clientHeight};
          };
          return Object.fromEntries(['.b-identity','.b-meta','.b-device','.b-plot',
            '.b-progress','.b-streetframe','.b-nowplaying','.b-poster',
            '.brain-dock','.kiosk-rail'].map(selector => [selector, rect(selector)]));
        }""")
        assert page.locator("#plot").text_content() == SUMMARY
        assert boxes[".b-identity"]["bottom"] < boxes[".b-meta"]["top"]
        assert boxes[".b-device"]["display"] == "none"
        assert boxes[".b-meta"]["bottom"] < boxes[".b-plot"]["top"]
        assert boxes[".b-plot"]["bottom"] < boxes[".b-progress"]["top"]
        assert boxes[".b-progress"]["bottom"] < boxes[".brain-dock"]["top"]
        assert boxes[".b-plot"]["scrollHeight"] > boxes[".b-plot"]["clientHeight"]
        assert boxes[".b-streetframe"]["display"] != "none"
        assert boxes[".b-nowplaying"]["display"] != "none"
        assert page.locator("#streetframe svg rect").first.get_attribute("stroke") == "#5A4533"
        assert page.locator("#nowplaying svg rect").first.get_attribute("stroke") == "#5A4533"
        assert page.locator("#streetframe .bl").count() > 20
        assert boxes[".b-streetframe"]["left"] < boxes[".b-poster"]["left"]
        assert boxes[".b-poster"]["right"] < boxes[".b-streetframe"]["right"]
        assert boxes[".b-streetframe"]["bottom"] < boxes[".brain-dock"]["top"]
        assert not errors, (width, height, errors)
        page.close()
    browser.close()
print("PASS: Street playback keeps full description scrollable and theater lights visible")

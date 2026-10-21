"""Cast media and sports readability/containment at receiver sizes."""

import os
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1] / "output"
CASES = (("sports-demo=1", ".sports-card", ".sport-matchup"),
         ("context-demo=media", ".context-card", ".context-copy"),
         ("context-demo=media-long", ".context-card", ".context-copy"))


def test_cast_calendar_and_plex_are_separate_scenes():
    calendar = {"playing": True, "type": "media_context", "key": "calendar:agenda",
                "context": {"source": "calendar", "type": "calendar_event",
                            "subtype": "pickup_notice",
                            "title": "Garbage, blue box, green cart, bulk waste (3 items max), and yard waste",
                            "subtitle": "Today", "artwork": "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg'/%3E",
                            "rows": [{"when": "Tomorrow", "title": "Birthday"}]}}
    plex = {"playing": True, "type": "episode", "key": "plex:episode",
            "title": "Scariest House in America", "subtitle": "S3 · E4", "poster": True,
            "progress": {"offsetMs": 600000, "durationMs": 2400000}}
    current = {"payload": calendar}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"])
        def route(request):
            path = request.request.url.split("?", 1)[0].split("marquee.test", 1)[-1]
            if path == "/image":
                return request.fulfill(path=str(ROOT / "index.html"), content_type="text/html")
            if path == "/now-playing.json":
                return request.fulfill(json=current["payload"])
            if path == "/settings.json":
                return request.fulfill(json={"theme": "synthwave", "template": "bigclock"})
            if path == "/poster.jpg":
                return request.fulfill(body="<svg xmlns='http://www.w3.org/2000/svg' width='200' height='300' />",
                                       content_type="image/svg+xml")
            asset = ROOT / path.lstrip("/")
            if asset.is_file():
                return request.fulfill(path=str(asset))
            return request.fulfill(json={})

        for width, height in ((800, 480), (1024, 600), (1280, 800)):
            page = browser.new_page(viewport={"width": width, "height": height})
            page.route("**/*", route)
            current["payload"] = calendar
            page.goto("http://marquee.test/image", wait_until="domcontentloaded")
            page.wait_for_function("document.querySelector('#stage').classList.contains('contextual')")
            assert page.locator("#context-card").evaluate(
                "el => el.classList.contains('calendar-scene') && el.classList.contains('no-art')")
            assert page.locator(".b-identity").evaluate("el => getComputedStyle(el).display") == "none"
            assert page.locator(".context-time").evaluate("el => getComputedStyle(el).display") == "none"
            assert "Birthday" in page.locator("#context-rows").inner_text()
            assert "[object Object]" not in page.locator("#context-rows").inner_text()
            calendar_boxes = page.evaluate("""() => {
                const box = s => document.querySelector(s).getBoundingClientRect();
                const card = box('#context-card'), copy = box('.context-copy'), rows = box('#context-rows');
                return {cardBottom:card.bottom, copyBottom:copy.bottom, rowsBottom:rows.bottom,
                    gap:rows.left-copy.right, copyScroll:document.querySelector('.context-copy').scrollHeight,
                    copyHeight:document.querySelector('.context-copy').clientHeight};
            }""")
            assert calendar_boxes["gap"] >= 0, (width, height, calendar_boxes)
            assert calendar_boxes["copyBottom"] <= calendar_boxes["cardBottom"] + 1
            assert calendar_boxes["rowsBottom"] <= calendar_boxes["cardBottom"] + 1
            assert calendar_boxes["copyScroll"] <= calendar_boxes["copyHeight"] + 1, (width, height, calendar_boxes)

            current["payload"] = plex
            page.evaluate("window.MarqueeLifecycle.request('now-playing')")
            page.wait_for_function("document.querySelector('#stage').classList.contains('cast-media')")
            assert page.locator("#context-card").evaluate("el => getComputedStyle(el).display") == "none"
            assert page.locator("#title").inner_text() == plex["title"]
            assert page.locator("#title").evaluate("el => getComputedStyle(el).display !== 'none' && el.getBoundingClientRect().width > 0")
            assert not page.locator("#bg").evaluate("el => el.classList.contains('on')")
            assert page.locator(".b-progress").evaluate("el => getComputedStyle(el).display") != "none"
            page.wait_for_selector(".b-poster:not([hidden])")
            media_boxes = page.evaluate("""() => {
                const box = s => document.querySelector(s).getBoundingClientRect();
                const stage = box('#stage'), identity = box('.b-identity');
                const poster = box('.b-poster'), progress = box('.b-progress');
                return {stageBottom:stage.bottom, identityBottom:identity.bottom,
                    posterBottom:poster.bottom, progressTop:progress.top,
                    progressBottom:progress.bottom, posterLeft:poster.left,
                    identityRight:identity.right};
            }""")
            assert media_boxes["identityRight"] <= media_boxes["posterLeft"] + 1, (width, height, media_boxes)
            assert media_boxes["identityBottom"] <= media_boxes["progressTop"] + 1, (width, height, media_boxes)
            assert media_boxes["posterBottom"] <= media_boxes["progressTop"] + 1, (width, height, media_boxes)
            assert media_boxes["progressBottom"] <= media_boxes["stageBottom"] + 1
            current["payload"] = calendar
            page.evaluate("window.MarqueeLifecycle.request('now-playing')")
            page.wait_for_function("document.querySelector('#stage').classList.contains('contextual')")
            assert page.locator(".b-identity").evaluate("el => getComputedStyle(el).display") == "none"
            page.close()
        browser.close()


def test_cast_idle_uses_saved_synth_theme():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 1024, "height": 600})

        def route(request):
            path = request.request.url.split("?", 1)[0].split("marquee.test", 1)[-1]
            if path == "/image":
                return request.fulfill(path=str(ROOT / "index.html"), content_type="text/html")
            asset = ROOT / path.lstrip("/")
            if asset.is_file():
                return request.fulfill(path=str(asset))
            if path == "/settings.json":
                return request.fulfill(json={"theme": "synthwave", "accent": "#2675df"})
            return request.fulfill(json={"playing": False})

        page.route("**/*", route)
        page.goto("http://marquee.test/image", wait_until="domcontentloaded")
        page.wait_for_function("document.documentElement.dataset.theme === 'synthwave'")
        assert page.locator("body").evaluate("el => el.classList.contains('idle')")
        assert page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--accent').trim()") == "#ff4fc8"
        page.evaluate("document.body.classList.add('sky-day')")
        assert page.locator("#idle-weather-temp").evaluate(
            "el => getComputedStyle(el).color") == "rgb(255, 240, 251)"
        page.close()
        browser.close()


def test_bigclock_keeps_saved_no_poster_layout_across_polls():
    """The household's Big Clock hides posters; playback must stay artwork-led."""
    payload = {"playing": True, "type": "movie", "key": "movie:sample",
               "title": "Practical Magic 2", "poster": True, "backdrop": True,
               "progress": {"offsetMs": 3400000, "durationMs": 7800000}}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"])
        for width, height in ((1024, 600), (1280, 800)):
            page = browser.new_page(viewport={"width": width, "height": height})
            poster_requests = []
            page.on("request", lambda request: poster_requests.append(request.url)
                    if "/poster.jpg" in request.url else None)

            def route(request):
                path = request.request.url.split("?", 1)[0].split("marquee.test", 1)[-1]
                if path == "/image":
                    return request.fulfill(path=str(ROOT / "index.html"), content_type="text/html")
                if path == "/now-playing.json":
                    return request.fulfill(json=payload)
                if path == "/settings.json":
                    return request.fulfill(json={"theme": "synthwave", "template": "bigclock",
                        "blockVisibility": {"bigclock": {"poster": False}}})
                if path == "/backdrop.jpg":
                    return request.fulfill(body="<svg xmlns='http://www.w3.org/2000/svg' width='1280' height='800'><rect width='1280' height='800' fill='#553d70'/></svg>",
                                           content_type="image/svg+xml")
                asset = ROOT / path.lstrip("/")
                if asset.is_file():
                    return request.fulfill(path=str(asset))
                return request.fulfill(json={})

            page.route("**/*", route)
            page.goto("http://marquee.test/image?display=hubs", wait_until="domcontentloaded")
            page.wait_for_function("document.querySelector('#stage').classList.contains('cast-media')")
            # The receiver polls every five seconds; verify the settled state,
            # not the brief frame immediately after the poster image loads.
            page.wait_for_timeout(6200)
            metrics = page.evaluate("""() => {
                const stage = document.querySelector('#stage');
                const clock = document.querySelector('.b-clock').getBoundingClientRect();
                const title = document.querySelector('.b-identity').getBoundingClientRect();
                const progress = document.querySelector('.b-progress').getBoundingClientRect();
                return {posterHidden:document.querySelector('.b-poster').hidden,
                    posterReady:stage.classList.contains('poster-ready'),
                    columns:getComputedStyle(stage).gridTemplateColumns,
                    clockSize:parseFloat(getComputedStyle(document.querySelector('.clock')).fontSize),
                    clockCenter:clock.left+clock.width/2,
                    clockBottom:clock.bottom, titleTop:title.top, titleBottom:title.bottom,
                    progressTop:progress.top, progressBottom:progress.bottom,
                    backdropOn:document.querySelector('#bg').classList.contains('on')};
            }""")
            assert metrics["posterHidden"] and not metrics["posterReady"], (width, metrics)
            assert not poster_requests, (width, poster_requests)
            assert metrics["backdropOn"]
            assert metrics["clockSize"] >= 100, (width, metrics)
            assert abs(metrics["clockCenter"] - width / 2) < width * .12, (width, metrics)
            assert metrics["clockBottom"] <= metrics["titleTop"] + 1, (width, metrics)
            assert metrics["titleBottom"] <= metrics["progressTop"] + 1, (width, metrics)
            assert metrics["progressBottom"] <= height + 1, (width, metrics)
            page.close()
        browser.close()


def run():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"])
        for width, height in ((1024, 600), (1280, 800), (800, 480)):
            page = browser.new_page(viewport={"width": width, "height": height})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))

            def route(request):
                path = request.request.url.split("?", 1)[0].split("marquee.test", 1)[-1]
                if path == "/image":
                    return request.fulfill(path=str(ROOT / "index.html"), content_type="text/html")
                asset = ROOT / path.lstrip("/")
                if asset.is_file():
                    return request.fulfill(path=str(asset))
                if path == "/settings.json":
                    return request.fulfill(json={"theme": "synthwave"})
                if path == "/weather.json":
                    return request.fulfill(json={})
                return request.fulfill(status=404)

            page.route("**/*", route)
            for query, scene, content in CASES:
                page.goto(f"http://marquee.test/image?demo=1&edit=1&{query}", wait_until="domcontentloaded")
                page.wait_for_selector(f".stage{'.sports' if 'sports' in query else '.contextual'} {scene}")
                assert page.locator('link[href*="cast-media-sports.css"]').count() == 1
                details = page.evaluate("""({scene, content}) => {
                    const card = document.querySelector(scene), child = document.querySelector(content);
                    const c = card.getBoundingClientRect(), d = child.getBoundingClientRect();
                    const css = getComputedStyle(card);
                    return {card: c.toJSON(), content: d.toJSON(), background: css.backgroundImage,
                        overflow: card.scrollHeight > card.clientHeight + 1,
                        childContained: d.top >= c.top && d.bottom <= c.bottom + 1};
                }""", {"scene": scene, "content": content})
                assert not details["overflow"], (width, height, query, details)
                assert details["childContained"], (width, height, query, details)
                assert "16, 11, 34" in details["background"] or "33, 18, 61" in details["background"], details
                if "sports" in query:
                    assert page.locator(".sport-record").first.evaluate(
                        "el => parseFloat(getComputedStyle(el).fontSize)") >= 14
                    assert page.locator(".sport-league-logo").evaluate(
                        "el => getComputedStyle(el).display") == "none"
                else:
                    assert page.locator(".context-detail").evaluate(
                        "el => parseFloat(getComputedStyle(el).fontSize)") >= 17
                    assert page.locator(".context-rows").evaluate(
                        "el => el.scrollWidth <= el.clientWidth + 1"), query
                page.screenshot(path=f"/tmp/marquee-cast-{query.split('=')[0]}-{width}x{height}.png")
            assert not errors, errors
            page.close()
        browser.close()
    print("PASS: cast sports/media synth backgrounds and contained primary content at 1024x600, 1280x800, 800x480")


if __name__ == "__main__":
    run()

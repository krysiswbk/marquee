"""Repeated touch/remote navigation while kiosk resources and media rerender."""

import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
DESTINATIONS = ("plex", "nhl", "ufc", "pfl", "weather", "tv", "astronomy",
                "gaming", "calendar", "movies", "trailers", "major_events", "music")


def install_routes(page):
    def route(request):
        path = request.request.url.split("?", 1)[0].split("marquee.test", 1)[-1]
        if path in ("/kiosk", "/live"):
            return request.fulfill(path=str(ROOT / "output/index.html"), content_type="text/html")
        asset = ROOT / "output" / path.lstrip("/")
        if asset.is_file():
            return request.fulfill(path=str(asset))
        if path == "/api/config":
            return request.fulfill(json={"providers": {
                key: {"enabled": True, "targets": ["kiosk"]} for key in DESTINATIONS
            }, "fallback": {}})
        if path == "/contexts":
            return request.fulfill(json={"contexts": [
                {"id": f"{key}:fixture", "provider": key,
                 "title": f"{key} fixture", "starts": "2099-01-01T12:00:00Z"}
                for key in DESTINATIONS if key != "plex"
            ]})
        if path == "/providers":
            return request.fulfill(json={"providers": {
                key: {"state": "ok"} for key in DESTINATIONS
            }})
        if path == "/now-playing.json":
            return request.fulfill(json={"playing": False, "state": "idle", "availability": "idle"})
        if path in ("/settings.json", "/live-settings.json"):
            return request.fulfill(json={"transitionMs": 0})
        if path == "/ambient.json":
            return request.fulfill(json={"opacity": 0})
        return request.fulfill(json={})

    page.route("**/*", route)


def activate(page, destination, touch):
    direct = page.locator(f'.kiosk-primary a[data-view="{destination}"]')
    if not direct.is_visible():
        page.locator(".kiosk-more").click()
        target = page.locator(f'.kiosk-menu a[data-view="{destination}"]')
    else:
        target = direct
    if touch:
        target.tap()
    else:
        target.click()
    page.wait_for_function(
        "target => new URL(location.href).searchParams.get('view') === target",
        arg=destination,
    )
    page.wait_for_selector(f'[aria-current="page"][data-view="{destination}"]')
    assert page.locator(".kiosk-rail").evaluate(
        "el => [...el.querySelectorAll('a[data-view]')].some(a => a.offsetHeight >= 44)"
    )


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"]
    )
    for width, height in ((390, 844), (800, 900), (1500, 1000)):
        context = browser.new_context(viewport={"width": width, "height": height}, has_touch=True)
        for direct_view, expected_theme in (("", "synthwave"), ("calendar", "synthwave"), ("plex", None)):
            cold_page = context.new_page()
            install_routes(cold_page)
            cold_page.route("**/kiosk-menu.js*", lambda route: route.abort())
            cold_url = f"http://marquee.test/kiosk?view={direct_view}" if direct_view else "http://marquee.test/kiosk"
            cold_page.goto(cold_url, wait_until="domcontentloaded")
            assert cold_page.locator("html").get_attribute("data-kiosk-theme") == expected_theme
            if expected_theme:
                initial_canvas = cold_page.evaluate("""() => {
                  const section=document.createElement('section'); section.className='kiosk-section';
                  document.body.append(section);
                  const stage=document.querySelector('.stage')||document.body.appendChild(document.createElement('div'));
                  stage.classList.add('stage'); document.body.classList.add('brain-live');
                  const context=document.createElement('section'); context.className='context-card';
                  context.innerHTML='<p class="eyebrow">Provider accent</p>'; stage.append(context);
                  document.documentElement.style.setProperty('--accent','#b6f378');
                  const style=getComputedStyle(section), theme=getComputedStyle(document.documentElement);
                  return {background:style.backgroundColor,image:style.backgroundImage,
                    accent:theme.getPropertyValue('--accent').trim(),
                    contextImage:getComputedStyle(context).backgroundImage,
                    contextAccent:getComputedStyle(context.querySelector('.eyebrow')).color};
                }""")
                assert initial_canvas["background"] == "rgb(16, 11, 34)" and "rgba(255, 79, 200," in initial_canvas["image"], (width, direct_view, initial_canvas)
                assert initial_canvas["accent"] == "#ff4fc8", (width, direct_view, initial_canvas)
                if not direct_view:
                    assert "rgba(255, 79, 200," in initial_canvas["contextImage"], (width, initial_canvas)
                    assert initial_canvas["contextAccent"] == "rgb(255, 112, 210)", (width, initial_canvas)
            cold_page.close()
        page = context.new_page()
        install_routes(page)
        page.goto("http://marquee.test/kiosk", wait_until="domcontentloaded")
        page.wait_for_selector('.kiosk-primary [data-view=""][aria-current="page"]')
        if width == 390:
            page.locator(".kiosk-more").click()
            settings = page.locator(".kiosk-menu details")
            settings.locator("summary").click()
            assert settings.evaluate("el => el.open")
            assert settings.locator("nav a").count() == 5
            assert all(settings.locator("nav a").nth(index).is_visible() for index in range(5))
            first_link = settings.locator("nav a").first.bounding_box()
            menu_box = page.locator(".kiosk-menu").bounding_box()
            assert first_link["y"] < menu_box["y"] + menu_box["height"] - 44, (first_link, menu_box)
            page.keyboard.press("Escape")
        for index in range(3):
            for destination in DESTINATIONS:
                # Start the same resource refresh that normally follows a
                # navigation, then activate during its render window.
                page.evaluate("window.MarqueeNavigation.refresh()")
                activate(page, destination, touch=index % 2 == 0)
                assert page.locator("html").get_attribute("data-kiosk-theme") == ("synthwave" if destination != "plex" else None)
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (width, height, destination)
                if destination not in ("plex", "weather"):
                    surface = page.locator("#kiosk-panel")
                    page.wait_for_function("key => { const panel=document.querySelector('#kiosk-panel'); return panel && !panel.hidden && panel.dataset.section===key }", arg=destination)
                    palette = surface.evaluate("el => { const s=getComputedStyle(el); return {background:s.backgroundColor,image:s.backgroundImage,color:s.color,border:s.borderColor,box:el.getBoundingClientRect().toJSON()} }")
                    assert palette["background"] == "rgb(16, 11, 34)", (width, destination, palette)
                    assert "rgba(255, 79, 200," in palette["image"], (width, destination, palette)
                    assert palette["color"] == "rgb(255, 240, 251)", (width, destination, palette)
                    box = palette["box"]
                    assert box["left"] >= -1 and box["top"] >= -1 and box["right"] <= width + 1 and box["bottom"] <= height + 1, (width, height, destination, box)
                    lime = surface.evaluate("""el => {
                      const tokens=['rgb(182, 243, 120)','rgb(216, 255, 149)','rgb(195, 252, 134)','rgb(199, 250, 143)','rgb(210, 255, 155)'];
                      return [...el.querySelectorAll('*')].filter(node => node.getClientRects().length).flatMap(node => {
                        const s=getComputedStyle(node), values=[s.color,s.backgroundColor,s.borderColor,s.outlineColor,s.fill,s.stroke,s.backgroundImage,s.boxShadow];
                        return values.some(value => tokens.some(token => value.includes(token)))
                          ? [{tag:node.tagName,classes:String(node.className?.baseVal||node.className||''),text:(node.textContent||'').trim().slice(0,70),values:values.filter(value=>tokens.some(token=>value.includes(token)))}] : [];
                      }).slice(0,12);
                    }""")
                    assert not lime, (width, destination, lime)
                assert page.locator(
                    f'.kiosk-rail a[data-view="{destination}"][aria-current="page"], '
                    f'.kiosk-menu a[data-view="{destination}"][aria-current="page"]'
                ).count() == 1
                if page.locator(".kiosk-menu[open]").count():
                    page.keyboard.press("Escape")
            home = page.locator('.kiosk-primary a[data-view=""]')
            if not home.is_visible():
                page.locator(".kiosk-more").click()
                home = page.locator('.kiosk-menu a[data-view=""]')
            (home.tap() if index % 2 == 0 else home.click())
            page.wait_for_function("!new URL(location.href).searchParams.get('view')")
            assert page.locator('.kiosk-primary [data-view=""][aria-current="page"]').count() == 1
            assert page.locator("html").get_attribute("data-kiosk-theme") == "synthwave"
            assert page.locator(".kiosk-menu[open]").count() == 0
        context.close()
    browser.close()
    print("PASS: repeated touch/click destination activation survives refresh, overflow, and Home return")

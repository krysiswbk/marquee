"""Offline browser regression checks for media -> household delivery/navigation."""
import json
import os
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path=os.environ.get('MARQUEE_CHROMIUM'), args=['--no-sandbox'])
    page = browser.new_page(viewport={'width': 700, 'height': 900})
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.add_init_script('''
      window.media = {playing:true,key:'test-film',title:'Test film',type:'movie'};
      window.pendingPolls = [];
      window.holdPolls = false;
      const originalFetch = window.fetch;
      window.fetch = (url, options) => String(url).startsWith('/now-playing.json')
        ? window.holdPolls ? new Promise(resolve => window.pendingPolls.push(resolve))
          : Promise.resolve(new Response(JSON.stringify(window.media)))
        : originalFetch(url, options);
      window.EventSource = class {
        addEventListener(type, callback) { if(type === 'context') window.sendContext =
          payload => callback({data:JSON.stringify(payload)}); }
      };
    ''')
    def route(r):
        path = urlparse(r.request.url).path
        if path == '/live':
            return r.fulfill(path=str(ROOT / 'output/index.html'), content_type='text/html')
        asset = ROOT / 'output' / path.lstrip('/')
        if asset.is_file():
            return r.fulfill(path=str(asset))
        if path == '/api/config':
            data = {'providers': {key: {'enabled': True, 'targets': ['kiosk']} for key in ('plex', 'nhl', 'ufc', 'pfl', 'weather', 'tv', 'astronomy', 'gaming', 'calendar', 'movies', 'trailers', 'major_events', 'music')}, 'fallback': {}}
        elif path == '/contexts':
            data = {'contexts': [], 'browse': {}}
        elif path == '/providers':
            data = {'providers': {}}
        elif path in ['/settings.json', '/live-settings.json']:
            data = {'transitionMs': 0}
        elif path == '/ambient.json':
            data = {'opacity': 0}
        else:
            data = {}
        r.fulfill(body=json.dumps(data), content_type='application/json')
    page.route('**/*', route)
    page.goto('http://marquee.test/live', wait_until='networkidle')
    page.wait_for_function("!document.body.classList.contains('idle') && document.querySelector('#title').textContent === 'Test film'")
    # A response already in flight must not restore Plex after an idle SSE event.
    page.evaluate("holdPolls=true; window.dispatchEvent(new Event('marquee-navigation'))")
    page.wait_for_function('pendingPolls.length > 0')
    page.evaluate("sendContext({playing:false}); pendingPolls.shift()(new Response(JSON.stringify(media)))")
    page.wait_for_timeout(100)
    assert page.locator('body').evaluate("el=>el.classList.contains('idle')")
    assert page.locator('.idle-screen').is_visible()
    # Starting a newer request must not starve an earlier successful response.
    page.evaluate('sendContext(media)')
    page.evaluate("window.dispatchEvent(new Event('marquee-navigation')); window.dispatchEvent(new Event('marquee-navigation'))")
    page.wait_for_function('pendingPolls.length === 2')
    page.evaluate("pendingPolls.shift()(new Response(JSON.stringify({playing:false})))")
    page.wait_for_timeout(100)
    assert page.locator('.idle-screen').is_visible()
    # Once a newer poll succeeds, an older response cannot restore stale media.
    page.evaluate("window.dispatchEvent(new Event('marquee-navigation'))")
    page.wait_for_function('pendingPolls.length === 2')
    page.evaluate("pendingPolls.pop()(new Response(JSON.stringify({playing:false})))")
    page.wait_for_timeout(100)
    page.evaluate("pendingPolls.shift()(new Response(JSON.stringify(media)))")
    page.wait_for_timeout(100)
    assert page.locator('.idle-screen').is_visible()
    # Direct rail destinations and the More overflow are the current kiosk contract.
    page.evaluate('sendContext(media)')
    page.wait_for_function("!document.body.classList.contains('idle')")
    page.wait_for_selector('.kiosk-primary a[data-view=""]')
    assert page.get_by_role('button', name='Menu', exact=True).count() == 0
    assert page.get_by_role('button', name='More destinations').count() == 1
    direct = page.locator('.kiosk-primary a[data-view]:not([data-view=""])').first
    direct.click()
    page.wait_for_function("new URL(location.href).searchParams.has('view')")
    assert page.locator('a[aria-current="page"]').count() == 1
    assert page.locator('.kiosk-primary a[data-view=""]').count() == 1
    # Keyboard return from a direct destination.
    page.locator('.kiosk-primary a[data-view=""]').focus()
    page.keyboard.press('Enter')
    page.wait_for_function("!new URL(location.href).searchParams.has('view')")
    assert page.locator('.kiosk-primary a[data-view=""][aria-current="page"]').count() == 1
    # Touch/click return from an overflow destination, with one current state.
    page.get_by_role('button', name='More destinations').click()
    overflow_destination = page.locator('.kiosk-menu a[data-view]:not([data-view=""])').first
    overflow_destination.click()
    page.wait_for_function("new URL(location.href).searchParams.has('view')")
    assert page.locator('a[aria-current="page"]').count() == 1
    page.locator('.kiosk-home-action').click()
    page.wait_for_function("!new URL(location.href).searchParams.has('view')")
    assert page.locator('.kiosk-primary a[data-view=""][aria-current="page"]').count() == 1
    assert page.locator('body').evaluate("el=>el.classList.contains('idle')") is False
    assert not errors, errors
    browser.close()
    print('PASS: stale polls are superseded; direct rail, More overflow, keyboard Home, touch Home, current-state, and Menu contracts hold')

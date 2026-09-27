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
    page = browser.new_page(viewport={'width': 1280, 'height': 800})
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
            data = {'providers': {'plex': {'enabled': True}}, 'fallback': {}}
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
    # Return to media, then choose Household with requests deliberately stalled.
    page.evaluate('sendContext(media)')
    page.wait_for_function("!document.body.classList.contains('idle')")
    page.get_by_role('button', name='Menu', exact=True).click()
    page.locator('a[data-view="household"]').click()
    page.wait_for_timeout(100)
    assert page.locator('.idle-screen').is_visible()
    assert page.locator('body').evaluate("el=>el.classList.contains('idle')")
    assert not errors, errors
    browser.close()
    print('PASS: SSE supersedes stale polls; overlapping polls do not starve or regress; Household navigation works with stalled requests')

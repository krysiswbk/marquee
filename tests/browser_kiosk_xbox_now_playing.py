import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=os.environ['MARQUEE_CHROMIUM'], args=['--no-sandbox'])
    page = browser.new_page(viewport={'width': 1280, 'height': 800})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    def route(request):
        path = request.request.url.split('?', 1)[0].split('marquee.test', 1)[-1]
        if path in ('/kiosk', '/live'):
            return request.fulfill(path=str(ROOT / 'output/index.html'), content_type='text/html')
        if path in ('/now-playing.json', '/xbox-now-playing.json'):
            data = {'playing': True, 'state': 'playing', 'title': 'Plex movie', 'key': 'plex:test', 'xbox': {'active': True, 'title': 'Forza Horizon 6', 'activity': 'Going Sideways at the Shimanoyama Drift Attack', 'genre': 'Racing & flying', 'platform': 'Xbox Series X|S', 'progress': '85 %', 'description': 'Explore Japan and become a racing legend.', 'poster': '/xbox-poster'}}
            if path == '/xbox-now-playing.json': data = data['xbox']
        elif path in ('/settings.json', '/live-settings.json', '/api/config'):
            data = {'transitionMs': 0, 'providers': {}, 'fallback': {}}
        elif path == '/providers': data = {'providers': {}}
        elif path == '/contexts': data = {'contexts': []}
        elif path == '/xbox-poster':
            return request.fulfill(body=b'<svg xmlns="http://www.w3.org/2000/svg" width="2" height="3"><rect width="2" height="3" fill="#ff4fc8"/></svg>', content_type='image/svg+xml')
        elif path == '/ambient.json': data = {'opacity': 0}
        elif path == '/weather': data = {'temp': 16, 'condition': 'cloudy', 'daily': [], 'hourly': []}
        else:
            asset = ROOT / 'output' / path.lstrip('/')
            if asset.is_file(): return request.fulfill(path=str(asset))
            data = {}
        return request.fulfill(body=json.dumps(data), content_type='application/json')
    page.route('**/*', route)
    page.goto('http://marquee.test/kiosk?view=plex', wait_until='domcontentloaded')
    page.wait_for_selector('.kiosk-xbox-floating-toggle:not([hidden])')
    assert page.locator('#title').inner_text() == 'Plex movie'
    assert page.locator('.kiosk-xbox-floating-toggle').inner_text() == 'Next · Xbox: Forza Horizon 6'
    page.locator('.kiosk-xbox-floating-toggle').click()
    assert page.locator('#kiosk-section-title').inner_text() == 'Forza Horizon 6'
    assert 'Going Sideways' in page.locator('.kiosk-now-playing-detail').inner_text()
    assert page.locator('.kiosk-xbox-description').inner_text() == 'Explore Japan and become a racing legend.'
    page.wait_for_function("document.querySelector('.kiosk-xbox-poster')?.naturalWidth === 2")
    assert 'Xbox Series X|S' in page.locator('.kiosk-xbox-facts').inner_text()
    assert page.locator('.kiosk-xbox-floating-toggle').inner_text() == 'Back to Plex'
    page.locator('.kiosk-xbox-floating-toggle').click()
    assert page.locator('.stage').evaluate("el => !el.classList.contains('hidden') && !el.classList.contains('kiosk-covered')")
    assert page.locator('.kiosk-section.now-playing-surface').evaluate('el => el.hidden')
    page.evaluate("window.MarqueeNavigation.resolve({playing:false,state:'idle',availability:'idle',xbox:{active:true,title:'Forza Horizon 6',activity:'Going Sideways'}})")
    assert page.locator('#kiosk-section-title').inner_text() == 'Forza Horizon 6'
    assert page.locator('.kiosk-xbox-floating-toggle').evaluate('el => el.hidden')
    assert not errors, errors
    page.screenshot(path='/tmp/marquee-evidence-xbox-now-playing.png')
    browser.close()
print('PASS: simultaneous Plex and Xbox keep Plex primary, flip to Xbox details, and return to Plex')

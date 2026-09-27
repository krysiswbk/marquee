import json, os, sys
from pathlib import Path
from urllib.parse import urlparse
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from cast.marquee.core.arbitration import ContextArbiter
from playwright.sync_api import sync_playwright
items = [dict(id='a', title='Weather at home', source='weather', type='weather', subtitle='21°C', detail='Clear this afternoon', rows=['Clear this afternoon', 'Humidity 60%', 'Humidity 60%'], priority=50), dict(id='b', title='A new game', source='gaming', type='gaming', subtitle='Tomorrow', priority=40)]
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=os.environ.get('MARQUEE_CHROMIUM'), args=['--no-sandbox'])
    for width, height in [(1280,800),(390,844)]:
        arbiter=ContextArbiter(rotation_seconds=300)
        page=browser.new_page(viewport={'width':width,'height':height})
        errors=[]
        page.on('pageerror', lambda error: errors.append(str(error)))
        def selected():
            return arbiter.select(items, [], display='kiosk')
        def route(r):
            path=urlparse(r.request.url).path
            if path in ['/live', '/kiosk', '/image']:
                return r.fulfill(body=(root/'output/index.html').read_text(), content_type='text/html')
            if path == '/events':
                return r.abort()
            if path == '/api/display-control':
                selected()
                if r.request.method=='POST':
                    arbiter.control(r.request.post_data_json['action'])
                    selected()
                data=arbiter.control_state()
            elif path=='/now-playing.json':
                winner=selected()
                data={'playing': True,'key': winner['id'],'type':'media_context','context':winner}
            elif path=='/api/config': data={'fallback':{}}
            elif path in ['/settings.json', '/live-settings.json']: data={'transitionMs':0}
            elif path in ['/weather','/ha-weather.json']: data={'temp':21, 'condition':'sunny'}
            elif path=='/ambient.json': data={'opacity':.95}
            else: return r.fulfill(status=404, body='')
            r.fulfill(body=json.dumps(data),content_type='application/json')
        page.route('**/*', route)
        page.goto('http://marquee.test/kiosk')
        page.wait_for_selector('.screen-controls')
        page.get_by_role('button',name='Freeze',exact=True).click()
        assert arbiter.control_state()['frozen']
        first=arbiter.control_state()['selected']
        page.get_by_role('button',name='Next screen').click()
        page.wait_for_timeout(100)
        assert arbiter.control_state()['selected'] != first
        assert arbiter.control_state()['frozen']
        page.get_by_role('button',name='Previous screen').click()
        page.wait_for_timeout(100)
        assert arbiter.control_state()['selected']==first
        # Select weather deterministically, maintaining freeze.
        if first!='a':
            page.get_by_role('button',name='Next screen').click()
            page.wait_for_timeout(100)
        assert page.locator('#weather-body').inner_text()=='Clear this afternoon'
        assert page.locator('#weather-stats').inner_text()=='Humidity 60%'
        assert page.locator('#weather-radar').evaluate('(el) => getComputedStyle(el).filter') == 'none'
        assert page.locator('#weather-radar').evaluate('(el) => getComputedStyle(el).mixBlendMode') == 'normal'
        page.get_by_role('button',name='Resume',exact=True).click()
        assert not arbiter.control_state()['frozen']
        page.locator('body').click(position={'x':1,'y':1})
        page.keyboard.press('Space')
        page.wait_for_timeout(100)
        assert arbiter.control_state()['frozen']
        box=page.locator('.screen-controls').bounding_box()
        assert box['x']>=0 and box['x']+box['width']<=width
        assert not errors, errors
        page.screenshot(path=f'/tmp/marquee-controls-{width}.png')
        page.goto('http://marquee.test/image')
        assert page.locator('.screen-controls').count()==0
        print(f'{width}x{height}: navigation, freeze/resume, keyboard, weather deduplication, bounds, Cast isolation PASS')
        page.close()
    browser.close()

"""Run against an isolated loopback app with Playwright installed."""
import os
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright
base=os.environ.get('MARQUEE_SMOKE_URL','http://127.0.0.1:18086')
assert urlparse(base).hostname in ('127.0.0.1','localhost')
with sync_playwright() as p:
 b=p.chromium.launch(headless=True,executable_path=os.environ.get('MARQUEE_CHROMIUM'),args=['--no-sandbox'])
 page=b.new_page(viewport={'width':1024,'height':600});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 for template in ['bigclock','spotlight','split','hero','lowerthird','street','fanart']:
  page.goto(base+'/image?demo=1&edit=1&tpl='+template,wait_until='domcontentloaded');page.wait_for_timeout(400)
  page.evaluate('window.postMessage({type:"marquee-cfg",cfg:{clockSeconds:true}},location.origin)');page.wait_for_timeout(700)
  results=page.evaluate('''()=>{const e=document.querySelector('#clock'),r=document.createRange();r.selectNodeContents(e);const a=r.getBoundingClientRect();return {a:a.toJSON(),others:['.b-identity','.b-progress','.wx'].map(s=>{const o=document.querySelector(s),b=o.getBoundingClientRect();return {s,visible:!!o.getClientRects().length,overlap:b.width>0&&b.height>0&&a.left<b.right&&a.right>b.left&&a.top<b.bottom&&a.bottom>b.top}})}}''')
  assert results['a']['width']>0,template
  assert results['a']['x']>=0 and results['a']['right']<=1024,(template,results)
  assert not any(x['visible'] and x['overlap'] for x in results['others']),(template,results)
  page.screenshot(path='/tmp/marquee-scenes-media-'+template+'.png')
 assert not errors,errors
 print('PASS: all seven Cast media templates have visible, bounded clocks without media/weather/progress overlap, seconds enabled')
 b.close()

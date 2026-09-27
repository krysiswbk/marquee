"""Run against an isolated loopback app with Playwright installed."""
import os
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright
import json
base=os.environ.get('MARQUEE_SMOKE_URL','http://127.0.0.1:18086')
assert urlparse(base).hostname in ('127.0.0.1','localhost')
with sync_playwright() as p:
 b=p.chromium.launch(headless=True,executable_path=os.environ.get('MARQUEE_CHROMIUM'),args=['--no-sandbox'])
 errors=[]
 for width,height in [(1024,600),(1280,800),(800,480),(1440,900)]:
  page=b.new_page(viewport={'width':width,'height':height});page.on('pageerror',lambda e:errors.append(str(e)))
  for path in ['/image','/live','/kiosk']:
   for demo,clock,others in [('sports-demo=1','#sport-clock',['.sport-matchup','#sport-footer']),('context-demo=weather-clear','#weather-clock',['.weather-source']),('context-demo=weather','#weather-clock',['.weather-source']),('context-demo=media','#context-clock',['#context-source','#context-title'])]:
    page.goto(base+path+'?demo=1&edit=1&'+demo,wait_until='domcontentloaded');page.wait_for_timeout(400)
    for size in [60,100,180]:
     page.evaluate('(size)=>window.postMessage({type:"marquee-cfg",cfg:{sportsClockSize:size,clockSeconds:true}},location.origin)',size)
     page.wait_for_timeout(700)
     result=page.evaluate('''({clock,others})=>{const a=document.querySelector(clock).getBoundingClientRect();return {a:a.toJSON(),others:others.map(s=>{const e=document.querySelector(s),b=e.getBoundingClientRect();return {s,b:b.toJSON(),overlap:a.left<b.right&&a.right>b.left&&a.top<b.bottom&&a.bottom>b.top}})}}''',{'clock':clock,'others':others})
     assert result['a']['width'] and result['a']['height'],(path,demo,'clock hidden')
     assert not any(x['overlap'] for x in result['others']),(width,height,path,demo,size,result)
    if width==1024 and path=='/image':page.screenshot(path='/tmp/marquee-scenes-final-'+demo.replace('=','-')+'.png')
  page.close()
 assert not errors,errors
 print('PASS: clocks visible and non-overlapping across 4 display sizes, Cast/Live, 4 scenes, 60/100/180% sizing, seconds enabled; no JS errors')
 b.close()

"""Run the real app and browser attention smoke test without configured Cast targets.
Requires optional playwright and Chromium; artifacts are retained in a temporary directory.
"""
import json, os, shutil, subprocess, tempfile, time, urllib.request, sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
work=Path(tempfile.mkdtemp(prefix='marquee-brain-smoke-'))
shutil.copytree(root/'output',work/'output',ignore=shutil.ignore_patterns('*.bak-*'))
(work/'cast').mkdir()
for path in (root/'cast').glob('*.html'): shutil.copy2(path,work/'cast'/path.name)
(work/'data').mkdir()
providers={name:{'enabled':False} for name in ('sports','weather','tv','calendar','gaming','astronomy')}
(work/'data'/'marquee.json').write_text(json.dumps({'providers':providers,'attention':{
 'signal_bindings':[{'entity_id':'binary_sensor.test_leak','category':'leak'}],
 'rules':[{'id':'test_leak','match':{'category':'leak'},'title':'Test leak detected','active_state':'on',
  'acknowledgement_required':True,'escalation':[{'id':'critical','urgency':'CRITICAL','priority':100}]}]}}))
env={**os.environ,'REPO_DIR':str(work),'DATA_DIR':str(work/'data'),'PAGE_URL':'http://127.0.0.1:18084/image','SERVE_PORT':'18084','POLL_SECONDS':'1','HUB_IP':'','GARAGE_HUB_IP':'','PLEX_TOKEN':'','PLEX_HOST':''}
log=open(work/'application.log','w')
process=subprocess.Popen([sys.executable,str(root/'cast'/'cast.py')],cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT)

for _ in range(50):
 try:
  with urllib.request.urlopen('http://127.0.0.1:18084/healthz',timeout=1) as response: print(response.read().decode())
  break
 except Exception: time.sleep(.2)
else:
 print((work/'application.log').read_text());process.terminate();raise SystemExit(1)
print(str(work))

try:
 testenv=dict(os.environ)
 subprocess.run([sys.executable,str(root/'tests/browser_attention.py')],env=testenv,check=True)
finally:
 process.terminate();process.wait(timeout=10)

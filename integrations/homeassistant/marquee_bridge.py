"""HA-local bridge credentials, with verified TLS and no credential redirects."""
import json
from pathlib import Path
from urllib.parse import urlsplit
import requests

class BridgeSession(requests.Session):
    def __init__(self):
        super().__init__()
        config=json.loads(Path('/config/marquee-bridge/client.json').read_text())
        self.base=config['url'].rstrip('/')
        if not self.base.startswith('https://'): raise ValueError('Bridge requires HTTPS')
        self.verify='/config/marquee-bridge/server.crt'
        self.headers['Authorization']='Bearer '+config['token']
        self.trust_env=False

    def request(self, method, url, **kwargs):
        # All callers use the same configured, pinned endpoint. Never send
        # the bridge credential to the HA API or to a redirected host.
        parsed=urlsplit(url)
        target=self.base+parsed.path+('?' + parsed.query if parsed.query else '')
        kwargs['allow_redirects']=False
        return super().request(method, target, **kwargs)

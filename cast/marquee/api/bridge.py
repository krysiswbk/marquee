"""Scoped, authenticated HTTPS for HA producers; secrets never enter UI config."""
import hmac
import os
import ssl
from pathlib import Path
from http.server import ThreadingHTTPServer

WRITES = frozenset(('/ha-weather', '/weather-context', '/weather-radar', '/ambient',
    '/garage-occupancy', '/calendar-events', '/gaming-releases', '/contexts',
    '/kiosk-activity', '/api/attention/signals'))
READS = frozenset(('/api/attention/bindings', '/now-playing.json', '/healthz'))

def authorize(handler, data_dir, method):
    path = handler.path.split('?')[0]
    secure = isinstance(getattr(handler, "connection", None), ssl.SSLSocket)
    token_path = Path(data_dir) / 'bridge-security/token'
    if not token_path.exists():
        return True  # Standalone installations can provision the bridge later.
    if not secure and not (method == 'POST' and path in WRITES):
        return True
    allowed = path in (WRITES if method == 'POST' else READS if method == 'GET' else ())
    supplied = handler.headers.get('Authorization', '')
    if secure and allowed and hmac.compare_digest(supplied, 'Bearer ' + token_path.read_text().strip()):
        return True
    handler._send('{"error":"authenticated HTTPS bridge required"}', 'application/json', 401)
    return False

def https_server(handler, data_dir):
    directory = Path(data_dir) / 'bridge-security'
    if not (directory / 'token').exists():
        return None
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(directory / 'server.crt', directory / 'server.key')
    server = ThreadingHTTPServer(('', int(os.environ.get('BRIDGE_PORT', '8085'))), handler)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    return server

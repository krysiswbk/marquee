"""The Cast launcher consumes the actual discovery envelope, not a list fixture."""
import io
import json
from unittest.mock import patch

from cast.marquee.api import http


def test_discovered_receiver_launch_uses_discovery_devices():
    launched = []
    class Thread:
        def __init__(self, target, args, **kwargs):
            self.target, self.args = target, args
        def start(self):
            self.target(*self.args)
    class Threads:
        pass
    Threads.Thread = Thread
    with patch.multiple(http, create=True, json=json, threading=Threads,
                        scan_devices=lambda refresh: {"devices": [{"ip": "192.0.2.10", "name": "Test Hub", "model": "Nest Hub"}], "current": "192.0.2.10"},
                        hold_manual_cast=lambda target: True,
                        cast_card=lambda target: launched.append(target)):
        handler = object.__new__(http.WebHandler)
        handler.path = '/api/cast'
        body = json.dumps({"target": "192.0.2.10"}).encode()
        handler.headers = {"Content-Length": str(len(body))}
        handler.rfile = io.BytesIO(body)
        replies = []
        handler._send = lambda body, ctype, code=200: replies.append((json.loads(body), code))
        handler.do_POST()
        assert replies[-1][1] == 202 and launched == ["192.0.2.10"]

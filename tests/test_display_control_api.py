import io
import json
import unittest
from unittest.mock import patch
from cast.marquee.api import http
from cast.marquee.core.arbitration import ContextArbiter


class DisplayControlAPITests(unittest.TestCase):
    def request(self, method='GET', body=None):
        handler = object.__new__(http.WebHandler)
        handler.path = '/api/display-control'
        raw = json.dumps(body).encode()
        handler.headers = {'Content-Length': str(len(raw))}
        handler.rfile = io.BytesIO(raw)
        result = []
        handler._send = lambda data, ctype, code=200: result.append((code, json.loads(data)))
        getattr(handler, 'do_' + method)()
        return result[0]

    def test_real_handler_navigation_freeze_and_validation(self):
        arbiter = ContextArbiter(rotation_seconds=300)
        candidates = [{'id':'one', 'priority':50}, {'id':'two','priority':50}]
        def best_context(plex, display):
            return arbiter.select(candidates, [], display=display)
        with patch.multiple(http, create=True, ARBITER=arbiter, json=json,
                            CURRENT_PLEX={'info':None}, best_context=best_context):
            code, initial = self.request()
            self.assertEqual(code, 200)
            self.assertEqual(initial['count'], 2)
            code, changed = self.request('POST', {'action':'next'})
            self.assertEqual(code, 200)
            self.assertNotEqual(initial['selected'], changed['selected'])
            self.assertTrue(self.request('POST', {'action':'freeze'})[1]['frozen'])
            self.assertFalse(self.request('POST', {'action':'resume'})[1]['frozen'])
            for bad in [[], None, {'action':'unknown'}, {'action':[]}, {'action':'x'*1024}]:
                self.assertEqual(self.request('POST', bad)[0], 400)

from pathlib import Path
import unittest


class WeatherRadarDeliveryTests(unittest.TestCase):
    def test_provider_versions_atomic_radar_replacements(self):
        source = (Path(__file__).parents[1] / "cast" / "marquee" / "providers" / "weather.py").read_text()
        self.assertIn('os.stat(radar_file).st_mtime_ns', source)
        self.assertIn('radar_path += f"?v=', source)

    def test_uploaded_gif_is_served_byte_for_byte(self):
        import base64
        import io
        import json
        import os
        import tempfile
        import urllib.parse
        from unittest.mock import patch
        from cast.marquee.api import http

        # A GIF with a comment extension: serving must preserve metadata too.
        raw = base64.b64decode('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7')
        raw = raw[:-1] + b'\x21\xfe\x08original\x00\x3b'
        with tempfile.TemporaryDirectory() as directory:
            def atomic_write(path, data, mode):
                with open(path, mode) as handle:
                    handle.write(data)
            with patch.multiple(http, create=True, DATA_DIR=directory, json=json,
                                os=os, urllib=urllib, atomic_write=atomic_write,
                                radar_mime=lambda header: 'image/gif' if header.startswith(b'GIF89a') else None):
                handler = object.__new__(http.WebHandler)
                handler.path = '/weather-radar'
                handler.headers = {'Content-Length': str(len(raw))}
                handler.rfile = io.BytesIO(raw)
                result = []
                handler._send = lambda body, ctype, code=200: result.append((body, ctype, code))
                handler.do_POST()
                self.assertEqual(result[-1][2], 200)
                self.assertTrue(json.loads(result[-1][0])['ok'])
                handler.path = '/provider-assets/weather-radar.img?v=original'
                handler.do_GET()
                self.assertEqual(result[-1], (raw, 'image/gif', 200))

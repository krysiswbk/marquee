import io
import json
import sys

sys.path.insert(0, "cast")

from marquee import composition
from marquee.api import http


def _request(path, method="GET", body=None, raw=None, content_length=None):
    handler = object.__new__(http.WebHandler)
    handler.path = path
    encoded = raw if raw is not None else json.dumps(body).encode() if body is not None else b""
    handler.headers = {"Content-Length": str(len(encoded) if content_length is None else content_length)}
    handler.rfile = io.BytesIO(encoded)
    result = []
    handler._send = lambda data, ctype="text/html; charset=utf-8", code=200: result.append(
        (code, ctype, json.loads(data) if ctype == "application/json" else data)
    )
    handler._send_file = lambda path, code=200: result.append((code, "file", path))
    handler._redirect = lambda path: result.append((302, "redirect", path))
    getattr(handler, "do_" + method)()
    return result[0]


def _configure_handler(monkeypatch, tmp_path):
    settings_path = tmp_path / "settings.json"
    live_path = tmp_path / "live-settings.json"
    monkeypatch.setattr(composition, "SETTINGS_PATH", str(settings_path))
    monkeypatch.setattr(composition, "LIVE_SETTINGS_PATH", str(live_path))
    monkeypatch.setattr(composition, "REPO", str(tmp_path))
    http.handler_for(composition)
    monkeypatch.setattr(http, "authorize", lambda *_: True)
    monkeypatch.setattr(http, "attention_route", lambda *_: False)
    monkeypatch.setattr(http, "plex_creds", lambda _: ("http://plex", "token"))
    monkeypatch.setattr(http, "ENV_BACKEND", "plex")
    return settings_path, live_path


def test_canonical_pages_and_retired_bookmarks(monkeypatch, tmp_path):
    _configure_handler(monkeypatch, tmp_path)
    for route, file in {
        '/settings': 'settings-control.html',
        '/settings/layout?profile=cast': 'cast-layout.html',
        '/settings/layout?profile=live': 'live-layout.html',
        '/settings/attention': 'attention-settings.html',
        '/settings/tests': 'display-tests.html',
    }.items():
        assert _request(route) == (200, 'file', str(tmp_path / 'cast' / file))
    for old, new in {
        '/': '/settings', '/settings-preview': '/settings',
        '/?tab=casting': '/settings/layout?profile=cast&tab=casting',
        '/live-settings': '/settings/layout?profile=live',
        '/settings?tab=design': '/settings/layout?profile=cast&tab=design',
        '/settings?tab=connection': '/settings/layout?profile=cast&tab=connection',
        '/admin': '/settings#content', '/admin/fallback': '/settings#displays',
        '/admin/?page=general': '/settings#advanced',
        '/admin/?page=interests': '/settings?source=interests#content',
        '/admin/provider/weather': '/settings?source=weather#content',
        '/admin/attention': '/settings/attention', '/admin/tests': '/settings/tests',
    }.items():
        assert _request(old) == (302, 'redirect', new)


def test_partial_profile_patches_preserve_secrets_and_isolate_profiles(monkeypatch, tmp_path):
    settings_path, live_path = _configure_handler(monkeypatch, tmp_path)
    settings_path.write_text(json.dumps({
        "template": "street", "rotateSeconds": 41, "plexHost": "http://saved-plex",
        "plexToken": "cast-secret", "fanartKey": "fanart-secret",
        "blockLayout": {"street": {"clock": {"x": 3}}},
        "presets": [{"name": "Old", "template": "street"}],
    }))
    live_path.write_text(json.dumps({"template": "fanart", "rotateSeconds": 88}))

    code, _, response = _request("/settings", "PATCH", {
        "rotateSeconds": 55,
        "showDeviceLocation": False,
        "blockLayout": {"spotlight": {"clock": {"x": 20}}},
        "presets": [{"name": "New", "template": "hero"}],
        "plexToken": "",
    })
    assert code == 200 and response["ok"]
    assert "plexToken" not in response["settings"]
    assert response["settings"]["plexTokenSet"] is True
    saved_cast = json.loads(settings_path.read_text())
    assert saved_cast["rotateSeconds"] == 55
    assert saved_cast["showDeviceLocation"] is False
    assert saved_cast["plexToken"] == "cast-secret"
    assert saved_cast["fanartKey"] == "fanart-secret"
    assert saved_cast["blockLayout"]["street"]["clock"]["x"] == 3
    assert saved_cast["blockLayout"]["spotlight"]["clock"]["x"] == 20
    assert [preset["name"] for preset in saved_cast["presets"]] == ["New"]

    code, _, response = _request("/live-settings", "PATCH", {"template": "street"})
    assert code == 200 and response["ok"]
    saved_live = json.loads(live_path.read_text())
    assert saved_live["template"] == "street"
    assert saved_live["rotateSeconds"] == 88
    assert "plexToken" not in saved_live and "plexHost" not in saved_live
    assert json.loads(settings_path.read_text())["template"] == "street"

    before_live = live_path.read_text()
    code, _, response = _request("/live-settings", "PATCH", {"plexToken": "replace"})
    assert code == 400
    assert response["ok"] is False
    assert "Cast/shared settings" in response["error"]
    assert live_path.read_text() == before_live


def test_partial_profile_patch_rejects_unknown_settings_without_writing(monkeypatch, tmp_path):
    settings_path, _ = _configure_handler(monkeypatch, tmp_path)
    settings_path.write_text(json.dumps({"rotateSeconds": 41, "plexToken": "cast-secret"}))
    before = settings_path.read_text()

    code, _, response = _request("/settings", "PATCH", {"notASetting": True})

    assert code == 400
    assert response["ok"] is False
    assert "unknown settings" in response["error"]
    assert settings_path.read_text() == before


def test_partial_profile_patch_rejects_malformed_and_oversized_bodies(monkeypatch, tmp_path):
    settings_path, _ = _configure_handler(monkeypatch, tmp_path)
    settings_path.write_text(json.dumps({"rotateSeconds": 41, "plexToken": "cast-secret"}))
    before = settings_path.read_text()

    code, _, response = _request("/settings", "PATCH", raw=b"{not json")
    assert code == 400
    assert response["ok"] is False
    assert settings_path.read_text() == before

    code, _, response = _request("/settings", "PATCH", raw=b"", content_length=256 * 1024 + 1)
    assert code == 400
    assert response["ok"] is False
    assert "1..262144 bytes" in response["error"]
    assert settings_path.read_text() == before


def test_layout_map_replacement_can_reset_without_changing_other_settings(monkeypatch, tmp_path):
    settings_path, live_path = _configure_handler(monkeypatch, tmp_path)
    settings_path.write_text(json.dumps({
        'plexToken': 'keep-secret', 'castKioskActivity': False,
        'blockLayout': {'street': {'clock': {'x': 15}}, 'hero': {'clock': {'x': 25}}},
    }))
    code, _, result = _request('/settings?replace=blockLayout', 'PATCH', {
        'blockLayout': {'hero': {'clock': {'x': 25}}},
    })
    assert code == 200
    stored = json.loads(settings_path.read_text())
    assert 'street' not in stored['blockLayout']
    assert stored['blockLayout']['hero']['clock']['x'] == 25
    assert stored['plexToken'] == 'keep-secret'
    assert stored['castKioskActivity'] is False
    before = settings_path.read_text()
    for path, body in [('/settings?replace=plexToken', {'plexToken': 'bad'}),
                       ('/settings?replace=blockLayout', {'theme': 'ice'}),
                       ('/settings?replace=blockLayout', {'blockLayout': None})]:
        assert _request(path, 'PATCH', body)[0] == 400
        assert settings_path.read_text() == before
    live_path.write_text(json.dumps({'liveLayout': {'home': {'clock': {'x': 10}}}}))
    assert _request('/live-settings?replace=liveLayout', 'PATCH', {'liveLayout': {}})[0] == 200
    assert json.loads(live_path.read_text())['liveLayout'] == {}
    assert settings_path.read_text() == before

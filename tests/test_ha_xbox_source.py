from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from test_ha_weather_source import load_ambient


def test_xbox_publisher_sends_only_live_game_facts():
    module = load_ambient()
    app = module.MarqueeAmbient()
    states = {
        app.XBOX_NOW_PLAYING: {"state": "Forza Horizon 6", "attributes": {
            "short_description": "Explore Japan.", "genres": "Racing & flying",
            "developer": "Playground Games", "publisher": "Xbox Game Studios",
            "achievements": "49 / 0", "gamerscore": "850 / 1000",
            "progress": "85 %", "platform": "Xbox Series X|S"}},
        app.XBOX_ACTIVITY: "Forza Horizon 6 - Going Sideways",
        app.XBOX_IN_GAME: "on",
        app.XBOX_POSTER: {"state": "2026-10-12T18:08:11Z", "attributes": {"entity_picture": "/api/image_proxy/image.krysiswbk_poster?token=private"}},
    }
    app.get_state = lambda entity, **kwargs: states.get(entity)
    app.bridge = SimpleNamespace(post=Mock(return_value=SimpleNamespace(raise_for_status=Mock())))
    image_response = SimpleNamespace(status_code=200, headers={"Content-Type": "image/jpeg"},
                                     iter_content=lambda size: [b"game-poster"], close=Mock())
    with patch.object(module.requests, "post", return_value=SimpleNamespace(raise_for_status=Mock())), \
            patch.object(module.requests, "get", return_value=image_response):
        app.XBOX_URL = "http://marquee.test:8084/ha-xbox"
        app.publish_xbox({})
    payload = app.bridge.post.call_args.kwargs["json"]
    assert payload["active"] is True
    assert payload["title"] == "Forza Horizon 6"
    assert payload["activity"].endswith("Going Sideways")
    assert payload["platform"] == "Xbox Series X|S"
    assert payload["progress"] == "85 %"
    assert payload["posterData"] == "Z2FtZS1wb3N0ZXI="
    assert payload["posterType"] == "image/jpeg"
    assert "private" not in repr(payload)


def test_xbox_publisher_clears_game_when_not_in_game():
    module = load_ambient()
    app = module.MarqueeAmbient()
    states = {app.XBOX_NOW_PLAYING: {"state": "Forza Horizon 6", "attributes": {}},
              app.XBOX_ACTIVITY: "Idle", app.XBOX_IN_GAME: "off"}
    app.get_state = lambda entity, **kwargs: states.get(entity)
    app.bridge = SimpleNamespace(post=Mock(return_value=SimpleNamespace(raise_for_status=Mock())))
    with patch.object(module.requests, "post", return_value=SimpleNamespace(raise_for_status=Mock())):
        app.XBOX_URL = "http://marquee.test:8084/ha-xbox"
        app.publish_xbox({})
    payload = app.bridge.post.call_args.kwargs["json"]
    assert payload == {"active": False, "title": "", "activity": "", "poster": "",
                       "posterData": "", "posterType": "",
                       "description": "", "genre": "", "developer": "", "publisher": "",
                       "achievements": "", "gamerscore": "", "progress": "", "platform": ""}


def test_xbox_publisher_refreshes_changed_states_and_periodically():
    source = (Path(__file__).parents[1] / "integrations/homeassistant/marquee_ambient.py").read_text()
    assert 'self.listen_state(self.xbox_changed, self.XBOX_NOW_PLAYING' in source
    assert 'self.listen_state(self.xbox_changed, self.XBOX_ACTIVITY' in source
    assert 'self.run_every(self.publish_xbox, "now+15", 15)' in source


def test_bridge_allows_only_authenticated_xbox_publish_route():
    source = (Path(__file__).parents[1] / "cast/marquee/api/bridge.py").read_text()
    assert "'/ha-weather', '/ha-xbox'" in source


def test_xbox_ui_has_separate_flip_control_and_keeps_plex_primary():
    root = Path(__file__).parents[1]
    menu = (root / "output/kiosk-menu.js").read_text()
    page = (root / "output/index.html").read_text()
    assert "Next · Xbox:" in menu
    assert "Back to Plex" in menu
    assert "nowPlayingPlatform !== 'xbox'" in menu
    assert "xboxResponse = await fetch('/xbox-now-playing.json" in page
    assert "NOW PLAYING · XBOX" in menu

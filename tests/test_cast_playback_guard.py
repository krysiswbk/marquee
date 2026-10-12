import json
from types import SimpleNamespace
from unittest.mock import Mock

from cast.marquee.runtime import Runtime
from cast.marquee.services import media


def test_external_cast_playback_is_busy_until_fresh_idle_snapshot(tmp_path, monkeypatch):
    path = tmp_path / "ha-cast-playback.json"
    monkeypatch.setattr(media, "HA_CAST_PLAYBACK_PATH", str(path))

    assert media.cast_external_playback("10.10.3.73", now=1000)
    path.write_text(json.dumps({"updated": 990,
                                "10.10.3.73": {"state": "paused", "app": "Plex"},
                                "10.10.3.74": {"state": "idle", "app": "DashCast"}}))
    assert media.cast_external_playback("10.10.3.73", now=1000)
    assert not media.cast_external_playback("10.10.3.74", now=1000)
    assert media.cast_external_playback("10.10.3.74", now=1030)


def test_main_receiver_defers_both_idle_and_marquee_media_casts(monkeypatch):
    busy = {"value": True}
    s = SimpleNamespace(hub_ip=lambda: "main", cast_external_playback=lambda _: busy["value"],
                        cast_card=Mock(), dashcast_active=Mock(return_value=False))
    guard = Runtime(s)
    guard._reconcile_main({"title": "Movie"}, True, (False, False),
                          None, (False, False), 0)
    guard._reconcile_main(None, False, (False, False), None, (False, False), 0)
    s.cast_card.assert_not_called()
    s.dashcast_active.assert_not_called()
    busy["value"] = False
    guard._reconcile_main(None, False, (False, False), None, (False, False), 6)
    s.cast_card.assert_called_once_with()


def test_presence_receiver_retries_after_external_cast_session():
    s = SimpleNamespace(PRESENCE_TARGETS={"hub": "bedroom"},
                        PRESENCE_STATE={"rooms": {"hub": {"eligible": True}}},
                        cast_external_playback=lambda _: True, cast_card=Mock(), catt_for=Mock())
    guard = Runtime(s)
    assert guard._reconcile_presence_targets(None, False, 100, {"hub": False}) == {"hub": False}
    s.cast_external_playback = lambda _: False
    assert guard._reconcile_presence_targets(None, False, 115, {"hub": False}) == {"hub": True}
    s.cast_card.assert_called_once_with("hub")
    s.catt_for.assert_not_called()


def test_garage_receiver_suppresses_automatic_cast_and_stop():
    s = SimpleNamespace(GARAGE_HUB_IP="garage", cast_external_playback=lambda _: True,
                        cast_card=Mock(), catt_for=Mock(), garage_dashcast_active=Mock())
    guard = Runtime(s)
    result = guard._reconcile_garage("plex", True, "mirror", True, (False, False),
                                     False, (False, False))
    assert result is False
    result = guard._reconcile_garage("plex", False, "off", False, (False, False),
                                     True, (False, False))
    assert result is False
    s.cast_card.assert_not_called()
    s.catt_for.assert_not_called()
    s.garage_dashcast_active.assert_not_called()

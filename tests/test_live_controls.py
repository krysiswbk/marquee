import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "cast"))
from marquee import composition
from marquee.composition import clean_display_settings, clean_live_visibility


def test_live_size_controls_are_bounded_and_persistable():
    value = {"displayWidth": 1280, "displayHeight": 800,
             "sportsClockSize": 999, "sportsArtworkSize": 143,
             "sportsTextSize": 20, "sportsWeatherSize": "106"}
    clean_display_settings(value)
    assert value["sportsClockSize"] == 180
    assert value["sportsArtworkSize"] == 143
    assert value["sportsTextSize"] == 60
    assert value["sportsWeatherSize"] == 106


def test_live_visibility_drops_unknown_control_paths():
    value = clean_live_visibility({"media": {"artwork": False, "title": True,
                                               "secret": False},
                                   "unknown": {"clock": False}})
    assert value == {"media": {"title": True, "artwork": False}}


def test_kiosk_activity_gate_expires_and_does_not_apply_to_cast(monkeypatch):
    monkeypatch.setattr(composition.CONFIG_REPOSITORY, "effective",
                        lambda: {"display": {"kiosk_interaction_idle_seconds": 30}})
    composition.KIOSK_ACTIVITY.update(last=100.0, source="test")
    assert composition.kiosk_interacting(129.9)
    assert not composition.kiosk_interacting(130.0)
    # The gate is consulted only for kiosk; hubs still reaches arbitration.
    class Arbiter:
        def select(self, saved, modular, plex, display):
            return {"id": "plex:now", "payload": plex}
    monkeypatch.setattr(composition, "ARBITER", Arbiter())
    monkeypatch.setattr(composition, "saved_contexts", lambda: [])
    monkeypatch.setattr(composition, "PROVIDER_ENGINE", {"value": None})
    monkeypatch.setattr(composition, "kiosk_interacting", lambda: True)
    assert composition.best_context({"title": "Movie"}, "kiosk") is None
    assert composition.best_context({"title": "Movie"}, "hubs")["title"] == "Movie"


def test_live_positions_are_validated_without_changing_cast_template_layout():
    positions = {"home": {"clock": {"x": -25, "y": 19, "scale": 1.4, "width": 44},
                          "unknown": {"x": 5}},
                 "weather": {"clock": {"x": 1000, "scale": 20}},
                 "unknown": {"clock": {"x": 1}}}
    clean = composition.clean_live_layout(positions)
    assert clean["home"]["clock"] == {"x": -25, "y": 19, "scale": 1.4, "width": 44}
    assert clean["weather"]["clock"] == {"x": 100, "scale": 3}
    assert "unknown" not in clean and "unknown" not in clean["home"]


def test_live_layout_survives_profile_load(tmp_path):
    import json
    path = tmp_path / "live-settings.json"
    path.write_text(json.dumps({"liveLayout": {"home": {"clock": {"x": 23}}}}))
    value = composition._load_settings_file(path)
    assert value["liveLayout"]["home"]["clock"]["x"] == 23

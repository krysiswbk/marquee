"""The kiosk's MQTT display bridge must power off and restore its LCD."""

import runpy
from pathlib import Path
from types import SimpleNamespace


def test_zero_powers_off_after_gnome_dims_and_auto_powers_on_first():
    path = Path(__file__).parents[1] / "integrations/homeassistant/kiosk_display_agent.py"
    agent = runpy.run_path(str(path))
    events = []
    agent["set_brightness"].__globals__["set_ambient"] = lambda enabled: events.append(("ambient", enabled))
    agent["set_brightness"].__globals__["set_panel_power"] = lambda enabled: events.append(("panel", enabled))
    agent["set_brightness"].__globals__["subprocess"] = SimpleNamespace(
        run=lambda args, **kwargs: events.append(("brightness", args[-1]))
    )

    assert agent["set_brightness"](b"0") == "0"
    assert events == [("ambient", False), ("brightness", "<0>"), ("panel", False)]

    events.clear()
    assert agent["set_brightness"](b"auto") == "auto"
    assert events == [("ambient", False), ("panel", True), ("brightness", "<50>"), ("ambient", True)]


def test_manual_brightness_wakes_panel_before_setting_level():
    path = Path(__file__).parents[1] / "integrations/homeassistant/kiosk_display_agent.py"
    agent = runpy.run_path(str(path))
    events = []
    agent["set_brightness"].__globals__["set_ambient"] = lambda enabled: events.append(("ambient", enabled))
    agent["set_brightness"].__globals__["set_panel_power"] = lambda enabled: events.append(("panel", enabled))
    agent["set_brightness"].__globals__["subprocess"] = SimpleNamespace(
        run=lambda args, **kwargs: events.append(("brightness", args[-1]))
    )

    assert agent["set_brightness"](b"25") == "25"
    assert events == [("ambient", False), ("panel", True), ("brightness", "<25>")]

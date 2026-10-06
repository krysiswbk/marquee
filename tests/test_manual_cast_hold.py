from types import SimpleNamespace

from cast.marquee.core.presence import PresenceGate
from cast.marquee.runtime import Runtime


def test_presence_release_is_suppressed_until_manual_hold_expires():
    calls = []
    service = SimpleNamespace(
        PRESENCE_TARGETS={"living": "living_room"},
        PRESENCE_STATE={"rooms": {"living": {"eligible": False,
                                               "absoluteVeto": False}}},
        manual_cast_hold_active=lambda target, now: now < 300,
        dashcast_active_for=lambda target: True,
        catt_for=lambda target, action: calls.append((target, action)),
    )
    runtime = Runtime(service)
    runtime._presence_gates["living"] = PresenceGate(activation_seconds=0)

    assert runtime._reconcile_presence_targets(None, False, 100, {"living": True}) == {"living": False}
    assert calls == []
    assert runtime._reconcile_presence_targets(None, False, 300, {"living": True}) == {"living": False}
    assert calls == [("living", "stop")]


def test_absolute_veto_still_releases_during_manual_hold():
    calls = []
    service = SimpleNamespace(
        PRESENCE_TARGETS={"bedroom": "bedroom"},
        PRESENCE_STATE={"rooms": {"bedroom": {"eligible": False,
                                                "absoluteVeto": True}}},
        manual_cast_hold_active=lambda target, now: True,
        dashcast_active_for=lambda target: True,
        catt_for=lambda target, action: calls.append((target, action)),
    )
    runtime = Runtime(service)
    assert runtime._reconcile_presence_targets(None, False, 100, {"bedroom": True}) == {"bedroom": False}
    assert calls == [("bedroom", "stop")]

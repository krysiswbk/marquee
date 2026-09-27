from datetime import datetime, timezone

from cast.marquee.providers.gaming import GamingProvider


class Client:
    def json(self, url, timeout=8):
        assert url == "http://fgc/claims"
        return {"claims": [{
            "id": "gog:state-of-mind", "title": "State of Mind", "store": "GOG",
            "claimed_at": "2026-09-08T12:21:15Z", "url": "https://example/game",
            "artwork": "https://cdn.example/game.jpg"
        }]}


def test_recent_claim_becomes_compact_kiosk_context(tmp_path):
    provider = GamingProvider({"enabled": True, "priority": 45,
                               "claims_url": "http://fgc/claims", "lookback_days": 7,
                               "timezone": "America/Toronto"},
                              str(tmp_path), client=Client())
    contexts = provider.contexts(provider.fetch(),
                                datetime(2026, 9, 9, tzinfo=timezone.utc))
    assert len(contexts) == 1
    assert contexts[0].title == "State of Mind"
    assert contexts[0].subtitle == "Claimed free on GOG"
    assert contexts[0].targets == ["kiosk"]
    assert contexts[0].artwork_url == "https://cdn.example/game.jpg"
    assert contexts[0].display_dict()["status"] == "Claimed"


def test_old_claim_is_not_presented(tmp_path):
    provider = GamingProvider({"enabled": True, "claims_url": "http://fgc/claims",
                               "lookback_days": 1}, str(tmp_path), client=Client())
    assert provider.contexts(provider.fetch(),
                             datetime(2026, 9, 10, tzinfo=timezone.utc)) == []


def test_monday_claim_is_expired_by_wednesday_even_with_week_lookback(tmp_path):
    provider = GamingProvider({"enabled": True, "lookback_days": 7,
                               "claim_ttl_hours": 24}, str(tmp_path))
    payload = {"claims": [{"id": "old", "title": "Monday Game", "store": "Epic",
                            "claimed_at": "2026-09-07T12:00:00Z"}]}
    assert provider.contexts(payload, datetime(2026, 9, 9, tzinfo=timezone.utc)) == []


def test_game_release_feed_becomes_upcoming_context(tmp_path):
    (tmp_path / "ha-gaming-releases.json").write_text(
        '{"updated": 1788912000, "events": [{"id": "one", '
        '"summary": "Hollow Knight: Silksong", '
        '"start": "2026-09-10T14:00:00+00:00"}]}')
    provider = GamingProvider({"enabled": True, "priority": 45,
                               "release_lookahead_days": 30, "max_releases": 3},
                              str(tmp_path), clock=lambda: 1788912000)
    contexts = provider.contexts(provider.fetch(),
                                 datetime(2026, 9, 9, tzinfo=timezone.utc))
    assert len(contexts) == 1
    assert contexts[0].subtype == "game_release"
    assert contexts[0].title == "Hollow Knight: Silksong"
    assert contexts[0].targets == ["kiosk"]


def test_stale_game_release_feed_is_ignored(tmp_path):
    (tmp_path / "ha-gaming-releases.json").write_text(
        '{"updated": 1, "events": [{"summary": "Old feed", '
        '"start": "2026-09-10T14:00:00+00:00"}]}')
    provider = GamingProvider({"enabled": True}, str(tmp_path),
                              clock=lambda: 1788912000)
    assert provider.fetch()["releases"] == []


def test_claim_disappears_at_toronto_midnight_even_if_just_collected(tmp_path):
    provider = GamingProvider({"enabled": True, "timezone": "America/Toronto"}, str(tmp_path))
    payload = {"claims": [{"id": "late", "title": "Late game", "claimed_at": "2026-09-11T03:55:00Z"}]}
    before = datetime(2026, 9, 11, 3, 59, tzinfo=timezone.utc)
    contexts = provider.contexts(payload, before)
    assert len(contexts) == 1  # UTC date changed; Toronto is still September 10.
    midnight = datetime(2026, 9, 11, 4, tzinfo=timezone.utc)
    assert contexts[0].expires_at == midnight
    assert contexts[0].expired(midnight)  # Even before the next provider refresh.
    assert provider.contexts(payload, midnight) == []


def test_claim_expiry_tracks_dst_and_ignores_legacy_hour_limit(tmp_path):
    provider = GamingProvider({"enabled": True, "timezone": "America/Toronto",
                               "claim_ttl_hours": 1}, str(tmp_path))
    for stamp, now, expiry in [
        ("2026-03-08T05:15:00Z", "2026-03-08T21:00:00Z", "2026-03-09T04:00:00Z"),
        ("2026-11-01T04:15:00Z", "2026-11-02T04:30:00Z", "2026-11-02T05:00:00Z"),
    ]:
        payload = {"claims": [{"title": "Game", "claimed_at": stamp}]}
        contexts = provider.contexts(payload, datetime.fromisoformat(now))
        assert len(contexts) == 1
        assert contexts[0].expires_at == datetime.fromisoformat(expiry)


def test_future_claim_is_not_displayed(tmp_path):
    provider = GamingProvider({"enabled": True, "timezone": "America/Toronto"}, str(tmp_path))
    payload = {"claims": [{"title": "Future", "claimed_at": "2026-09-11T03:59:00Z"}]}
    assert provider.contexts(payload, datetime(2026, 9, 11, 3, tzinfo=timezone.utc)) == []

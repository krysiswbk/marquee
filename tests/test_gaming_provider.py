import json
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit

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
                              str(tmp_path), client=ArtworkClient(), clock=lambda: 1788912000)
    contexts = provider.contexts(provider.fetch(),
                                 datetime(2026, 9, 9, tzinfo=timezone.utc))
    assert len(contexts) == 1
    assert contexts[0].subtype == "game_release"
    assert contexts[0].title == "Hollow Knight: Silksong"
    assert contexts[0].targets == ["kiosk"]
    assert contexts[0].artwork_url.endswith("/silksong/header.jpg")
    assert contexts[0].background_url.endswith("/silksong/background.jpg")


class ArtworkClient:
    def __init__(self, store_name="Hollow Knight: Silksong", detail_name=None):
        self.store_name = store_name
        self.detail_name = detail_name or store_name
        self.calls = []

    def json(self, url, timeout=8):
        self.calls.append(url)
        if urlsplit(url).path.endswith("storesearch/"):
            assert parse_qs(urlsplit(url).query)["term"] == ["Hollow Knight: Silksong"]
            return {"items": [{"id": 103030, "name": self.store_name}]}
        if urlsplit(url).path.endswith("appdetails"):
            return {"103030": {"success": True, "data": {
                "name": self.detail_name,
                "header_image": "https://shared.steamstatic.com/silksong/header.jpg",
                "background_raw": "https://shared.steamstatic.com/silksong/background.jpg"}}}
        raise AssertionError(url)


def test_release_artwork_strips_platforms_and_uses_cache(tmp_path):
    client = ArtworkClient()
    provider = GamingProvider({"max_releases": 3}, str(tmp_path), client=client,
                              clock=lambda: 1788912000)
    releases = [{"summary": "Hollow Knight: Silksong (PC)", "start": "2026-09-10"}]
    provider.enrich_releases(releases)
    assert releases[0]["artwork"].endswith("/silksong/header.jpg")
    assert len(client.calls) == 2
    provider.enrich_releases(releases)
    assert len(client.calls) == 2
    cached = json.loads((tmp_path / "provider-cache" / "gaming-artwork.json").read_text())
    assert "hollow knight silksong" in cached


def test_release_artwork_rejects_nonmatching_store_entry(tmp_path):
    client = ArtworkClient(store_name="Hollow Knight: Silksong Soundtrack")
    provider = GamingProvider({"max_releases": 3}, str(tmp_path), client=client,
                              clock=lambda: 1788912000)
    releases = [{"summary": "Hollow Knight: Silksong", "start": "2026-09-10"}]
    provider.enrich_releases(releases)
    assert releases[0]["artwork"] == ""
    assert len(client.calls) == 1


def test_release_artwork_failure_preserves_event(tmp_path):
    class OfflineClient:
        def json(self, url, timeout=8):
            raise OSError("store unavailable")

    provider = GamingProvider({"max_releases": 3}, str(tmp_path), client=OfflineClient(),
                              clock=lambda: 1788912000)
    releases = [{"summary": "Hollow Knight: Silksong", "start": "2026-09-10T14:00:00+00:00"}]
    provider.enrich_releases(releases)
    assert provider.contexts({"claims": [], "releases": releases},
                             datetime(2026, 9, 9, tzinfo=timezone.utc))[0].artwork_url == ""


def test_duplicate_calendar_entries_do_not_consume_artwork_slots(tmp_path):
    class TwoGames(ArtworkClient):
        def json(self, url, timeout=8):
            if urlsplit(url).path.endswith("storesearch/"):
                title = parse_qs(urlsplit(url).query)["term"][0]
                return {"items": [{"id": 103030 if title == "Hollow Knight: Silksong" else 103031,
                                   "name": title}]}
            title = "Hollow Knight: Silksong" if "103030" in url else "Second Game"
            app_id = "103030" if title == "Hollow Knight: Silksong" else "103031"
            return {app_id: {"success": True, "data": {
                "name": title, "header_image": "https://shared.steamstatic.com/game/header.jpg"}}}

    provider = GamingProvider({"max_releases": 2}, str(tmp_path), client=TwoGames(),
                              clock=lambda: 1788912000)
    releases = [
        {"summary": "Hollow Knight: Silksong", "start": "2026-09-10"},
        {"summary": "Hollow Knight: Silksong", "start": "2026-09-10"},
        {"summary": "Second Game", "start": "2026-09-11"},
    ]
    provider.enrich_releases(releases)
    assert releases[0]["artwork"]
    assert releases[2]["artwork"]


class ConsoleClient:
    def __init__(self, wrong_title=False):
        self.wrong_title = wrong_title
        self.calls = []

    def json(self, url, headers=None, timeout=8):
        self.calls.append(url)
        path = urlsplit(url).path
        if "graphql" in path:
            assert headers == {"Content-Type": "application/json"}
            title = "Different Game" if self.wrong_title else "Hela: of Mice & Magic"
            return {"data": {"universalSearch": {"results": [{"name": title, "media": [
                {"type": "IMAGE", "role": "SIXTEEN_BY_NINE_BANNER",
                 "url": "https://image.api.playstation.com/hela.jpg"}]}]}}}
        if path.endswith("autosuggest"):
            return {"Results": [{"Products": [
                {"Title": "Arkheron Friend Pass", "Type": "Game", "ProductId": "wrong"},
                {"Title": "Arkheron (Game Preview)", "Type": "Game", "ProductId": "right"}]}]}
        if path.endswith("products"):
            return {"Products": [{"ProductId": "right", "LocalizedProperties": [{
                "ProductTitle": "Arkheron (Game Preview)", "Images": [
                    {"ImagePurpose": "SuperHeroArt", "Width": 1920, "Height": 1080,
                     "Uri": "//store-images.s-microsoft.com/arkheron.jpg"}]}]}]}
        if path.endswith("storesearch/"):
            return {"items": []}
        raise AssertionError(url)


def test_ps5_release_prefers_exact_playstation_banner(tmp_path):
    client = ConsoleClient()
    provider = GamingProvider({"max_releases": 1}, str(tmp_path), client=client,
                              clock=lambda: 1788912000)
    releases = [{"summary": "Hela: Of Mice & Magic (PS5/Xbox/PC)", "start": "2026-09-10"}]
    provider.enrich_releases(releases)
    assert releases[0]["artwork"] == "https://image.api.playstation.com/hela.jpg"
    assert len(client.calls) == 1


def test_xbox_release_uses_game_preview_hero_not_friend_pass(tmp_path):
    client = ConsoleClient()
    provider = GamingProvider({"max_releases": 1}, str(tmp_path), client=client,
                              clock=lambda: 1788912000)
    releases = [{"summary": "Arkheron (Xbox/PC)", "start": "2026-09-10"}]
    provider.enrich_releases(releases)
    assert releases[0]["artwork"] == "https://store-images.s-microsoft.com/arkheron.jpg"
    assert len(client.calls) == 2


def test_same_title_ps5_and_xbox_releases_keep_platform_art_separate(tmp_path):
    class PlatformClient:
        def json(self, url, headers=None, timeout=8):
            path = urlsplit(url).path
            if "graphql" in path:
                return {"data": {"universalSearch": {"results": [{"name": "Shared Game", "media": [
                    {"type": "IMAGE", "role": "SIXTEEN_BY_NINE_BANNER",
                     "url": "https://image.api.playstation.com/shared-ps5.jpg"}]}]}}}
            if path.endswith("autosuggest"):
                return {"Results": [{"Products": [{"Title": "Shared Game", "Type": "Game",
                                                     "ProductId": "shared-xbox"}]}]}
            if path.endswith("products"):
                return {"Products": [{"ProductId": "shared-xbox", "LocalizedProperties": [{
                    "ProductTitle": "Shared Game", "Images": [
                        {"ImagePurpose": "SuperHeroArt", "Width": 1920, "Height": 1080,
                         "Uri": "https://store-images.s-microsoft.com/shared-xbox.jpg"}]}]}]}
            raise AssertionError(url)

    provider = GamingProvider({"max_releases": 2}, str(tmp_path), client=PlatformClient(),
                              clock=lambda: 1788912000)
    releases = [{"summary": "Shared Game (PS5)", "start": "2026-09-10"},
                {"summary": "Shared Game (Xbox)", "start": "2026-09-11"}]
    provider.enrich_releases(releases)
    assert releases[0]["artwork"].endswith("shared-ps5.jpg")
    assert releases[1]["artwork"].endswith("shared-xbox.jpg")
    cached = json.loads((tmp_path / "provider-cache" / "gaming-artwork.json").read_text())
    assert set(cached) == {"shared game:ps5", "shared game:xbox"}


def test_console_title_mismatch_keeps_text_card(tmp_path):
    provider = GamingProvider({"max_releases": 1}, str(tmp_path), client=ConsoleClient(wrong_title=True),
                              clock=lambda: 1788912000)
    releases = [{"summary": "Hela: Of Mice & Magic (PS5)", "start": "2026-09-10"}]
    provider.enrich_releases(releases)
    assert releases[0]["artwork"] == ""


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

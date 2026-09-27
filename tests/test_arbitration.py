import unittest
from datetime import datetime, timedelta, timezone

from cast.marquee.core.arbitration import ContextArbiter
from cast.marquee.core.events import EventBus


NOW = datetime(2026, 9, 9, tzinfo=timezone.utc)


class ArbitrationTests(unittest.TestCase):
    def test_ufc_blocks_pfl_overlap_even_when_pfl_priority_is_higher(self):
        arbiter = ContextArbiter(minimum_context_seconds=12)
        pfl = {"id":"pfl:1", "source":"pfl", "type":"pfl_in", "priority":99,
               "eventState":"LIVE", "castTakeover":True}
        ufc = {"id":"ufc:1", "source":"ufc", "type":"ufc_in", "priority":90,
               "eventState":"LIVE", "castTakeover":True}
        for display in ("kiosk", "hubs"):
            self.assertEqual(arbiter.select([pfl], [], display=display, now=NOW)["id"], "pfl:1")
            self.assertEqual(arbiter.select([pfl, ufc], [], display=display, now=NOW)["id"], "ufc:1")
        self.assertEqual(arbiter.control_state()["count"], 1)
        self.assertEqual(arbiter.select([pfl, dict(ufc, eventState="POST_EVENT")], [],
                                       display="kiosk", now=NOW)["id"], "pfl:1")

    def test_expired_or_far_future_ufc_does_not_block_live_pfl(self):
        pfl = {"id":"pfl:1", "source":"pfl", "type":"pfl_in", "priority":89,
               "eventState":"LIVE"}
        ufc = {"id":"ha:ufc", "source":"ufc", "type":"ufc_pre", "priority":80,
               "starts":(NOW + timedelta(days=1)).isoformat()}
        arbiter = ContextArbiter()
        self.assertEqual(arbiter.select([ufc,pfl], [], display="kiosk", now=NOW)["id"], "pfl:1")
        ufc["starts"] = (NOW + timedelta(minutes=30)).isoformat()
        self.assertEqual(arbiter.select([ufc,pfl], [], display="kiosk", now=NOW)["id"], "ha:ufc")
        ufc["expires"] = NOW.isoformat()
        self.assertEqual(arbiter.select([ufc,pfl], [], display="kiosk", now=NOW)["id"], "pfl:1")

    def test_expired_and_below_relevance_candidates_are_ineligible(self):
        arbiter = ContextArbiter(minimum_relevance=40)
        expired = {"id": "old", "priority": 100, "relevance": 100,
                   "expires": (NOW - timedelta(seconds=1)).isoformat()}
        irrelevant = {"id": "noise", "priority": 99, "relevance": 20,
                      "expires": (NOW + timedelta(hours=1)).isoformat()}
        useful = {"id": "useful", "priority": 60, "relevance": 80,
                  "expires": (NOW + timedelta(hours=1)).isoformat()}
        self.assertEqual(arbiter.select([expired, irrelevant, useful], [], now=NOW)["id"],
                         "useful")

    def test_provider_weight_is_a_hard_eligibility_gate(self):
        tv = {"id": "sonarr:1", "type": "tv_release", "priority": 63,
              "providerWeight": 15, "relevance": 90,
              "title": "The Secret Lives of Mormon Wives",
              "subtitle": "S04E01 · Premiere", "targets": ["kiosk"]}
        game = {"id": "gaming:1", "type": "gaming", "priority": 45,
                "providerWeight": 45, "relevance": 65, "title": "Real Game",
                "targets": ["kiosk"]}
        winner = ContextArbiter(minimum_relevance=20, rotate_relevant=False).select(
            [], [tv, game], display="kiosk", now=NOW)
        self.assertEqual(winner["id"], "gaming:1")

    def test_legacy_context_priority_is_weight_fallback(self):
        tv = {"id": "sonarr:1", "priority": 15, "relevance": 90,
              "title": "TV", "targets": ["kiosk"]}
        self.assertIsNone(ContextArbiter(minimum_relevance=20).select(
            [], [tv], display="kiosk", now=NOW))

    def test_household_candidate_wins_tie_and_is_enriched(self):
        explicit = {"id": "ha:fight", "source": "ufc", "title": "Fight Night",
                    "priority": 90, "left": {"logo": "headshot"}, "rows": []}
        generated = {"id": "ufc:1", "source": "ufc", "title": "Fight Night",
                     "priority": 90, "left": {"logo": "flag"}, "rows": ["result"]}
        winner = ContextArbiter().select([explicit], [generated], now=NOW)
        self.assertEqual(winner["id"], "ha:fight")
        self.assertEqual(winner["left"]["logo"], "headshot")
        self.assertEqual(winner["rows"], ["result"])

    def test_aged_household_result_suppresses_duplicate_generated_result(self):
        old = (NOW - timedelta(minutes=31)).isoformat()
        explicit = {"id": "ha:fight", "source": "ufc", "title": "Fight Night",
                    "type": "ufc_post", "priority": 85, "observedAt": old,
                    "left": {"logo": "headshot"}}
        generated = {"id": "ufc:1", "source": "ufc", "title": "Fight Night",
                     "type": "ufc_post", "priority": 85,
                     "left": {"logo": "flag"}}
        winner = ContextArbiter(post_event_max_seconds=1800).select(
            [explicit], [generated], plex={"title": "Movie"}, now=NOW)
        self.assertEqual(winner["id"], "plex:now")

    def test_selection_change_emits_event_once(self):
        bus, seen = EventBus(), []
        bus.subscribe("context.selected", lambda event, payload: seen.append(payload))
        arbiter = ContextArbiter(bus)
        item = {"id": "one", "priority": 50}
        arbiter.select([item], [], now=NOW)
        arbiter.select([item], [], now=NOW)
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0]["selected"], "one")

    def test_takeovers_can_be_disabled_while_plex_is_active(self):
        arbiter = ContextArbiter(takeovers_enabled=False)
        weather = {"id": "storm", "priority": 100, "targets": ["hubs"]}
        plex = {"title": "Movie"}
        self.assertEqual(arbiter.select([], [weather], plex=plex)["payload"], plex)

    def test_post_event_yields_to_plex_after_short_grace(self):
        arbiter = ContextArbiter(post_event_plex_grace_seconds=300)
        result = {"id": "fight", "type": "ufc_post", "priority": 85}
        plex = {"title": "Movie"}
        first = arbiter.select([result], [], plex=plex, now=NOW)
        later = arbiter.select([result], [], plex=plex,
                               now=NOW + timedelta(minutes=6))
        self.assertEqual(first["id"], "plex:now")
        self.assertEqual(later["id"], "plex:now")

    def test_default_post_event_yields_to_active_plex_immediately(self):
        result = {"id": "fight", "type": "ufc_post", "priority": 85}
        winner = ContextArbiter().select([result], [], plex={"title": "Movie"}, now=NOW)
        self.assertEqual(winner["id"], "plex:now")

    def test_post_event_has_a_maximum_display_lifetime(self):
        arbiter = ContextArbiter(post_event_max_seconds=1800)
        result = {"id": "fight", "type": "ufc_post", "priority": 85}
        self.assertIsNone(arbiter.select([result], [], now=NOW))
        self.assertIsNone(arbiter.select([result], [],
                                        now=NOW + timedelta(minutes=31)))

    def test_persisted_post_timestamp_survives_arbiter_restart(self):
        result = {"id": "fight", "type": "ufc_post", "priority": 85,
                  "observedAt": (NOW - timedelta(minutes=31)).isoformat()}
        self.assertIsNone(ContextArbiter(post_event_max_seconds=1800)
                          .select([result], [], now=NOW))

    def test_cast_ignores_ambient_discovery_but_keeps_emergency_takeover(self):
        ambient = {"id": "tv", "priority": 60, "targets": ["hubs"]}
        storm = {"id": "storm", "priority": 95, "targets": ["hubs"]}
        arbiter = ContextArbiter()
        self.assertIsNone(arbiter.select([], [ambient], display="hubs", now=NOW))
        self.assertEqual(arbiter.select([], [ambient, storm], display="hubs",
                                        now=NOW)["id"], "storm")

    def test_cast_specific_takeover_can_opt_in_below_emergency_tier(self):
        takeover = {"id": "goal", "priority": 90, "castTakeover": True,
                    "targets": ["hubs"]}
        self.assertEqual(ContextArbiter().select([], [takeover], display="hubs",
                                                 now=NOW)["id"], "goal")

    def test_live_event_pins_kiosk_instead_of_rotating(self):
        live = {"id": "game", "priority": 90, "eventState": "LIVE",
                "targets": ["kiosk"]}
        release = {"id": "episode", "priority": 99,
                   "targets": ["kiosk"]}
        arbiter = ContextArbiter(rotation_seconds=30)
        self.assertEqual(arbiter.select([], [release, live], display="kiosk",
                                        now=NOW)["id"], "game")
        self.assertEqual(arbiter.select([], [release, live], display="kiosk",
                                        now=NOW + timedelta(seconds=30))["id"], "game")

    def test_lone_useful_kiosk_context_never_gets_a_fake_fallback_slot(self):
        item = {"id": "episode", "priority": 60, "targets": ["kiosk"]}
        arbiter = ContextArbiter(rotation_seconds=30, fallback_every=2,
                                 single_item_seconds=12)
        epoch = datetime.fromtimestamp(0, timezone.utc)
        for seconds in (0, 12, 30, 60, 600):
            self.assertEqual(arbiter.select([], [item], display="kiosk",
                                            now=epoch + timedelta(seconds=seconds))["id"],
                             "episode")

    def test_lone_active_plex_always_wins_on_kiosk(self):
        arbiter = ContextArbiter(rotation_seconds=30, fallback_every=2)
        plex = {"title": "X-Men '97", "playing": True}
        epoch = datetime.fromtimestamp(0, timezone.utc)
        for seconds in (0, 30, 60, 300):
            self.assertEqual(arbiter.select([], [], plex, display="kiosk",
                                            now=epoch + timedelta(seconds=seconds))["payload"],
                             plex)

    def test_plex_and_household_context_rotate_without_fallback(self):
        arbiter = ContextArbiter(rotation_seconds=30, fallback_every=2,
                                 minimum_context_seconds=0)
        plex = {"title": "X-Men '97", "playing": True}
        household = {"id": "calendar:pickup", "priority": 40,
                     "title": "School pickup", "targets": ["kiosk"]}
        epoch = datetime.fromtimestamp(0, timezone.utc)
        winners = [arbiter.select([household], [], plex, display="kiosk",
                                  now=epoch + timedelta(seconds=seconds))
                   for seconds in (0, 30, 60)]
        self.assertEqual([w.get("id", "plex:now") for w in winners],
                         ["plex:now", "calendar:pickup", "plex:now"])

    def test_kiosk_falls_back_only_when_no_useful_context_exists(self):
        self.assertIsNone(ContextArbiter().select([], [], display="kiosk", now=NOW))

    def test_cast_selection_does_not_rotate_or_admit_kiosk_contexts(self):
        arbiter = ContextArbiter(rotation_seconds=5, minimum_context_seconds=0)
        plex = {"title": "X-Men '97", "playing": True}
        household = {"id": "calendar:pickup", "priority": 100,
                     "title": "School pickup", "targets": ["kiosk"]}
        for seconds in (0, 5, 10):
            winner = arbiter.select([household], [], plex, display="hubs",
                                    now=NOW + timedelta(seconds=seconds))
            self.assertEqual(winner["payload"], plex)

    def test_manual_screen_test_pins_kiosk(self):
        forced = {"id": "screen-test:live", "priority": 100,
                  "targets": ["kiosk"]}
        ambient = {"id": "episode", "priority": 60,
                   "targets": ["kiosk"]}
        arbiter = ContextArbiter(rotation_seconds=30)
        self.assertEqual(arbiter.select([forced], [ambient], display="kiosk",
                                        now=NOW)["id"], "screen-test:live")

    def test_post_event_state_is_never_rendered(self):
        result = {"id": "episode", "type": "tv_release", "priority": 99,
                  "eventState": "POST_EVENT", "targets": ["kiosk"]}
        self.assertIsNone(ContextArbiter().select([], [result], display="kiosk", now=NOW))

    def test_tba_tv_cannot_rotate_against_fgc_claim(self):
        claimed = {"id": "gaming:claimed:one", "type": "gaming", "priority": 45,
                   "title": "A Real Game", "subtitle": "Claimed free on Epic",
                   "targets": ["kiosk"]}
        tba = {"id": "sonarr:999", "type": "tv_release", "priority": 99,
               "title": "The Secret Lives of Mormon Wives",
               "subtitle": "S04E01 · TBA", "targets": ["kiosk"]}
        arbiter = ContextArbiter(rotation_seconds=30, fallback_every=0)
        epoch = datetime.fromtimestamp(0, timezone.utc)
        for offset in (0, 42, 84, 126):
            winner = arbiter.select([], [claimed, tba], display="kiosk",
                                    now=epoch + timedelta(seconds=offset))
            self.assertEqual(winner["id"], "gaming:claimed:one")

    def test_minimum_context_time_prevents_one_second_handoff(self):
        game = {"id": "gaming:1", "priority": 45, "title": "Game",
                "targets": ["kiosk"]}
        show = {"id": "tv:1", "priority": 60, "title": "Show",
                "targets": ["kiosk"]}
        arbiter = ContextArbiter(minimum_context_seconds=12, rotate_relevant=False)
        self.assertEqual(arbiter.select([], [game], display="kiosk", now=NOW)["id"],
                         "gaming:1")
        self.assertEqual(arbiter.select([], [game, show], display="kiosk",
                                        now=NOW + timedelta(seconds=1))["id"], "gaming:1")
        self.assertEqual(arbiter.select([], [game, show], display="kiosk",
                                        now=NOW + timedelta(seconds=12))["id"], "tv:1")


if __name__ == "__main__": unittest.main()

import tempfile
import unittest
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

from cast.marquee.providers.engine import ContextEngine
from cast.marquee.providers.model import EventState
from cast.marquee.providers.sports import NHLProvider, PFLProvider, UFCProvider

NOW = datetime(2026, 9, 9, 1, 0, tzinfo=timezone.utc)


def athlete(name, winner=False, ident="1"):
    return {"winner": winner, "athlete": {"displayName": name,
            "headshot": {"href": f"https://img/{ident}.png"}},
            "records": [{"summary": "10-1-0"}]}


class SportsProviderTests(unittest.TestCase):
    def setUp(self): self.tmp = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmp.cleanup()

    def test_ufc_live_keeps_headshots_and_last_two_results(self):
        done1 = {"competitors": [athlete("A"), athlete("B", True, "2")],
                 "status": {"period": 2, "displayClock": "1:32",
                            "type": {"state": "post"}}}
        done2 = {"competitors": [athlete("C", True, "3"), athlete("D")],
                 "status": {"period": 3, "displayClock": "5:00",
                            "type": {"state": "post"}}}
        live = {"type": {"abbreviation": "Middleweight"},
                "competitors": [athlete("E", ident="5"), athlete("F", ident="6")],
                "status": {"type": {"state": "in", "shortDetail": "Round 1"}},
                "odds": [{"details": "Fighter E -145", "overUnder": "2.5"}]}
        payload = {"events": [{"id": "card", "name": "UFC Fight Night",
            "date": "2026-09-08T23:00Z", "status": {"type": {"state": "in"}},
            "competitions": [done1, done2, live], "venues": [{"fullName": "Arena"}]}]}
        provider = UFCProvider({"enabled": True, "priority": 90}, self.tmp.name)
        context = provider.contexts(payload, NOW)[0]
        self.assertEqual(context.event_state, EventState.LIVE)
        self.assertEqual(context.raw["left"]["logo"], "https://img/5.png")
        self.assertEqual(context.stats,
            ["LAST · C def. D · R3 5:00", "LAST · B def. A · R2 1:32",
             "ODDS · Fighter E -145 · O/U 2.5"])

    def test_nhl_summary_maps_last_goal_and_live_power_play_without_empty_net_false_positive(self):
        summary = {
            "header": {"competitions": [{"competitors": [
                {"team": {"id": "21", "abbreviation": "TOR"}},
                {"team": {"id": "27", "abbreviation": "NSH"}}],
                "status": {"displayClock": "10:00", "displayPeriod": "2nd"}}]},
            "plays": [{"scoringPlay": True, "text": "Steven Stamkos Goal (2) Wrist Shot",
                       "clock": {"displayValue": "7:13"},
                       "period": {"displayValue": "1st"}, "team": {"id": "27"}}],
            "onIce": [{"teamId": "21", "entries": [{"athleteid": str(i)} for i in range(1, 7)]},
                      {"teamId": "27", "entries": [{"athleteid": str(i)} for i in range(11, 16)]}],
            "boxscore": {"players": [{"statistics": [{"name": "goalies", "athletes": [
                {"athlete": {"id": "1"}}, {"athlete": {"id": "11"}}]}]}]}}
        details = NHLProvider._score_details(summary)
        self.assertEqual(details["lastGoal"], "1st 7:13 · NSH · Steven Stamkos")
        self.assertEqual(details["powerPlay"], "TOR")
        self.assertEqual(details["scoreDetails"], ["1st 7:13 · NSH · Steven Stamkos Goal (2) Wrist Shot"])
        summary["header"]["competitions"][0]["status"]["displayClock"] = "20:00"
        summary["plays"].append({"type": {"text": "Period End"}})
        self.assertEqual(NHLProvider._score_details(summary)["powerPlay"], "")
        summary["header"]["competitions"][0]["status"]["displayClock"] = "10:00"
        summary["plays"].pop()
        summary["onIce"][0]["entries"] = summary["onIce"][0]["entries"][1:]
        self.assertEqual(NHLProvider._score_details(summary)["powerPlay"], "")
        summary["onIce"][0]["entries"].append({"athleteid": "1"})
        summary["onIce"][1]["entries"].extend([{"athleteid": "16"}, {"athleteid": "17"}])
        summary["boxscore"]["players"][0]["statistics"][0]["athletes"].append(
            {"athlete": {"id": "16"}})
        self.assertEqual(NHLProvider._score_details(summary)["powerPlay"], "No active power play")

    def test_pfl_normalizes_its_own_league_with_fighter_art(self):
        fight = {"competitors":[athlete("Fighter A", ident="10"), athlete("Fighter B", ident="11")],
                 "status":{"type":{"state":"in", "shortDetail":"Round 2"}}}
        payload = {"events":[{"id":"123", "name":"PFL Finals", "date":NOW.isoformat(),
                              "status":{"type":{"state":"in"}}, "competitions":[fight]}]}
        provider = PFLProvider({"enabled":True, "priority":89}, self.tmp.name)
        context = provider.contexts(payload, NOW)[0]
        self.assertEqual(context.id, "pfl:123")
        self.assertEqual(context.provider, "pfl")
        self.assertEqual(context.type, "pfl_in")
        self.assertEqual(context.priority, 89)
        self.assertEqual(context.event_state, EventState.LIVE)
        self.assertEqual(context.raw["left"]["logo"], "https://img/10.png")
        self.assertEqual(provider.sport_path, "mma/pfl")

    def test_nhl_filters_to_followed_team(self):
        payload = {"events": [{"id": "game", "name": "Toronto vs Montreal",
            "date": "2026-09-09T01:00Z", "status": {"type": {"state": "in"}},
            "competitions": [{"competitors": [
                {"team": {"abbreviation": "TOR", "displayName": "Maple Leafs"}},
                {"team": {"abbreviation": "MTL", "displayName": "Canadiens"}}]}],
            "_marqueeScoreDetails": {"lastGoal": "1st 7:13 · MTL · Cole Caufield",
                                     "powerPlay": "MTL", "scoreDetails": ["Goal detail"]}}]}
        provider = NHLProvider({"enabled": True, "priority": 90, "teams": ["TOR"]},
                               self.tmp.name)
        values = provider.contexts(payload, NOW)
        self.assertEqual(len(values), 1)
        self.assertEqual(values[0].event_state, EventState.LIVE)
        rendered = values[0].display_dict()
        self.assertEqual(rendered["lastGoal"], "1st 7:13 · MTL · Cole Caufield")
        self.assertEqual(rendered["powerPlay"], "MTL")
        self.assertEqual(rendered["scoreDetails"], ["Goal detail"])

    def test_nhl_browse_keeps_future_followed_game_out_of_interruption_candidates(self):
        payload = {"events": [{"id": "future", "name": "Maple Leafs at Canadiens",
            "date": "2026-09-12T23:00Z", "status": {"type": {"state": "pre", "shortDetail": "Scheduled"}},
            "competitions": [{"broadcasts": [{"names": ["Sportsnet"]}], "competitors": [
                {"homeAway": "away", "team": {"abbreviation": "TOR", "displayName": "Maple Leafs"}},
                {"homeAway": "home", "team": {"abbreviation": "MTL", "displayName": "Canadiens"}}]}]}]}
        provider = NHLProvider({"enabled": True, "priority": 90, "teams": ["TOR"]}, self.tmp.name)
        self.assertEqual(provider.contexts(payload, NOW), [])
        browse = provider.browse_contexts(payload, NOW)
        self.assertEqual(len(browse), 1)
        rendered = browse[0].display_dict()
        self.assertEqual(rendered["left"]["homeAway"], "away")
        self.assertEqual(rendered["right"]["homeAway"], "home")
        self.assertEqual(rendered["sourceStatus"], "Scheduled")
        self.assertEqual(rendered["broadcast"], "Sportsnet")

    def test_nhl_browse_omits_games_without_a_followed_team(self):
        payload = {"events": [{"id": "other", "date": "2026-09-12T23:00Z",
            "competitions": [{"competitors": [{"team": {"abbreviation": "MTL"}},
                                                 {"team": {"abbreviation": "BOS"}}]}]}]}
        provider = NHLProvider({"enabled": True, "teams": ["TOR"]}, self.tmp.name)
        self.assertEqual(provider.browse_contexts(payload, NOW), [])

    def test_nhl_aggregates_single_dates_deduplicates_and_maps_lifecycle(self):
        calls = []
        def event(ident, state, date):
            return {"id": ident, "name": ident,
            "date": date, "status": {"type": {"state": state}},
            "competitions": [{"venue": {"fullName": "Arena"}, "competitors": [
                {"team": {"abbreviation": "TOR", "displayName": "Maple Leafs"}, "score": "3"},
                {"team": {"abbreviation": "MTL", "displayName": "Canadiens"}, "score": "2"}]}]}
        payloads = [{"events": [event("game-live", "in", NOW.isoformat())]},
                    {"events": [event("game-live", "in", NOW.isoformat()),
                                event("game-final", "post", "2026-09-08T23:00Z")]},
                    {"events": []}]

        class Client:
            def json(self, url, timeout=8):
                if "/summary?" in url:
                    return {"plays": []}
                calls.append(parse_qs(urlparse(url).query)["dates"][0])
                return payloads[min(len(calls) - 1, 2)]

        provider = NHLProvider({"enabled": True, "priority": 90, "teams": ["TOR"]},
                               self.tmp.name, client=Client(), clock=lambda: NOW.timestamp())
        result = provider.fetch()
        self.assertEqual(len(calls), 9)
        self.assertEqual(len(result["events"]), 2)
        values = provider.contexts(result, NOW)
        self.assertEqual([value.event_state for value in values],
                         [EventState.POST_EVENT, EventState.LIVE])
        self.assertEqual(result["_fetch"]["successfulDates"], 9)

    def test_nhl_partial_and_total_failures_are_explicit(self):
        class Partial:
            def __init__(self): self.calls = 0
            def json(self, url, timeout=8):
                self.calls += 1
                if self.calls == 2:
                    raise RuntimeError("HTTP 400")
                return {"events": []}

        provider = NHLProvider({"enabled": True}, self.tmp.name, client=Partial(),
                               clock=lambda: NOW.timestamp())
        result = provider.fetch()
        details = provider.health_details(result)
        self.assertEqual(details["state"], "degraded")
        self.assertIn("8/9", details["error"])

        class Down:
            def json(self, url, timeout=8): raise RuntimeError("HTTP 400")

        down = NHLProvider({"enabled": True}, self.tmp.name, client=Down(),
                           clock=lambda: NOW.timestamp())
        with self.assertRaisesRegex(RuntimeError, "every requested date"):
            down.fetch()

    def test_nhl_partial_health_survives_context_engine(self):
        class Client:
            calls = 0
            def json(self, url, timeout=8):
                self.calls += 1
                if self.calls == 2:
                    raise RuntimeError("HTTP 400")
                return {"events": []}

        provider = NHLProvider({"enabled": True}, self.tmp.name, client=Client(),
                               clock=lambda: NOW.timestamp())
        engine = ContextEngine([provider], clock=lambda: NOW.timestamp())
        engine.tick()
        engine.futures["nhl"].result()
        engine.tick()
        health = engine.diagnostics()["providers"]["nhl"]
        self.assertEqual(health["state"], "degraded")
        self.assertIn("failed dates", health["error"])


if __name__ == "__main__":
    unittest.main()

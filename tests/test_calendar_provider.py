import json
from datetime import datetime, timezone

from cast.marquee.providers.calendar import CalendarProvider


NOW = datetime(2026, 9, 9, 12, tzinfo=timezone.utc)


def provider(tmp_path, **config):
    return CalendarProvider({"enabled": True, "priority": 40, "timezone": "America/Toronto",
                             "lookahead_days": 14, "targets": ["kiosk"], **config},
                            str(tmp_path), clock=lambda: NOW.timestamp())


def test_timed_event_urgency_increases_and_deduplicates(tmp_path):
    event = {"uid": "one", "entity_id": "calendar.games", "summary": "Showcase",
             "start": "2026-09-09T13:00:00Z", "end": "2026-09-09T14:00:00Z"}
    values = provider(tmp_path).contexts({"events": [event, dict(event)]}, NOW)
    assert len(values) == 1
    assert values[0].event_state.value == "STARTING_SOON"
    assert values[0].urgency >= 90


def test_all_day_uses_household_timezone_and_expires_at_end(tmp_path):
    event = {"uid": "day", "entity_id": "calendar.releases", "summary": "Game Day",
             "start": "2026-09-09", "end": "2026-09-10", "all_day": True}
    value = provider(tmp_path).contexts({"events": [event]}, NOW)[0]
    assert value.start_time.isoformat() == "2026-09-09T04:00:00+00:00"
    assert value.expires_at.isoformat() == "2026-09-10T04:00:00+00:00"
    assert value.event_state.value == "LIVE"


def test_expired_and_tba_events_are_noise(tmp_path):
    events = [{"summary": "TBA", "start": "2026-09-10", "end": "2026-09-11",
               "all_day": True}, {"summary": "Old", "start": "2026-09-07T10:00:00Z",
               "end": "2026-09-07T11:00:00Z"}]
    assert provider(tmp_path).contexts({"events": events}, NOW) == []


def test_calendar_is_kiosk_only_without_explicit_cast_policy(tmp_path):
    event = {"summary": "Urgent", "start": "2026-09-09T13:00:00Z",
             "end": "2026-09-09T14:00:00Z", "priority": 100,
             "targets": ["kiosk", "hubs"]}
    normal = provider(tmp_path, targets=["kiosk", "hubs"]).contexts({"events": [event]}, NOW)[0]
    assert normal.targets == ["kiosk"]
    allowed = provider(tmp_path, targets=["kiosk", "hubs"], allow_cast=True,
                       cast_min_priority=95).contexts({"events": [event]}, NOW)[0]
    assert allowed.targets == ["kiosk", "hubs"]
    assert allowed.raw["castTakeover"] is True


def test_stale_feed_returns_no_events(tmp_path):
    (tmp_path / "ha-calendar-events.json").write_text(json.dumps(
        {"updated": 1, "events": [{"summary": "Old feed"}]}))
    assert provider(tmp_path).fetch() == {"events": []}


def birthday(name, date, calendar="calendar.birthdays", end=None):
    from datetime import date as Date, timedelta
    return {"summary": name, "entity_id": calendar, "start": date,
            "end": end or (Date.fromisoformat(date) + timedelta(days=1)).isoformat(), "all_day": True}


def test_birthdays_share_one_card_closest_featured_and_cross_calendar_duplicates_removed(tmp_path):
    events = [birthday("Mark's Birthday", "2026-09-23"),
              birthday("Judy's Birthday", "2026-09-13"),
              birthday("Lucie's Birthday", "2026-09-17"),
              birthday("Mark's Birthday", "2026-09-23", "calendar.family")]
    values = provider(tmp_path, lookahead_days=21).contexts({"events": events}, NOW)
    assert len(values) == 1
    card = values[0]
    assert card.subtype == "birthday_rollup"
    assert card.title == "Judy's Birthday"
    assert card.stats == ["Lucie's Birthday · In 8 days · Sep 17", "Mark's Birthday · In 14 days · Sep 23"]
    # The rollup title is the featured/nearest birthday; stats contains only
    # additional birthdays consumed by dashboard summaries.
    assert card.title not in card.stats
    assert len(card.stats) + 1 == 3
    assert card.targets == ["kiosk"]


def test_past_birthdays_drop_out_even_with_late_end_and_horizon_is_three_weeks(tmp_path):
    events = [birthday("Old Birthday", "2026-09-08", end="2026-09-12"),
              birthday("Today's Birthday", "2026-09-09"),
              birthday("Soon Birthday", "2026-09-29"),
              birthday("Later Birthday", "2026-10-01")]
    p = provider(tmp_path, lookahead_days=21)
    card = p.contexts({"events": events}, NOW)[0]
    assert card.title == "Today's Birthday"
    assert len(card.stats) == 1 and "Soon" in card.stats[0]
    midnight = datetime(2026, 9, 10, 4, tzinfo=timezone.utc)
    assert card.expired(midnight)
    assert p.contexts({"events": events}, midnight)[0].title == "Soon Birthday"


def test_bills_never_become_cards_but_bill_can_have_a_birthday(tmp_path):
    events = [{"summary": "Pay day", "entity_id": "calendar.bills", "start": "2026-09-10", "end": "2026-09-11", "all_day": True},
              {"summary": "Internet Bill", "entity_id": "calendar.home", "start": "2026-09-10", "end": "2026-09-11", "all_day": True},
              birthday("Bill's Birthday", "2026-09-10"),
              {"summary": "Student loan", "entity_id": "calendar.home", "start": "2026-09-10", "end": "2026-09-11", "all_day": True}]
    values = provider(tmp_path).contexts({"events": events}, NOW)
    assert len(values) == 1 and values[0].title == "Bill's Birthday"

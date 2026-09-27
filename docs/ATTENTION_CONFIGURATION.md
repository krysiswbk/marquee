# Configuring household attention

The `attention` object in `/config/marquee.json` is schema version **1**. It can
also be edited at `/admin/attention` or replaced using `PUT /api/attention/config`.
The general configuration API still accepts partial top-level updates. Lists are
replaced, not appended. Unknown attention fields and invalid types/ranges are
rejected before saving. `attention.enabled: false` restores ambient-only selection.

The shipped default adds a native weather-alert policy. No door, leak, occupancy
or appliance entity is assumed. [Complete examples](attention.example.json) use
intentionally fictitious `example_*` entity names: replace those before enabling.
Keep the default weather rule when replacing the rule list if you want its takeover.

## Inputs and context

`signal_bindings` entries have `entity_id`, optional `type` (defaults to the HA
domain), `category` (default household), `location`, and `ttl` seconds. Every binding
produces a normal signal and an `availability` signal in category `sensor_health`.
An unavailable normal signal expires immediately; its availability observation
remains fresh so a *separate*, debounced health policy can aggregate outages.

`context_bindings` maps semantic names to `{entity_id, values?, attribute?, ttl?}`.
`values` maps raw strings to semantic values, including booleans. Unmapped values,
missing entities in a full snapshot, and expired observations become `null`.
For example:

```json
{"home":{"entity_id":"binary_sensor.example_occupied",
         "values":{"on":true,"off":false}}}
```

A known boolean `home` derives `nobody_home`. Bind `sleeping`, `occupancy`,
`weather_state`, `calendar`, `network_health`, `security_state` or other semantic
names as needed. The engine provides `active_media` from native media observations
unless explicitly bound. `hour`, `time_of_day` and `quiet_hours` derive from
`general.timezone`. Quiet hours use integer local hours; start inclusive, end
exclusive, wrapping midnight; equal start/end disables the interval.

Native contexts also become signals: source = provider/source, type = context type,
category = subtype (or source), state = `active`, entity_id = context ID,
attributes = the context presentation data. Media is `source: media`, `type: media`.
Priority/severity in observations are inputs only; policies own the final decision.

## Rule contract

Each rule requires a unique `id`, a nonempty `match`, and an `escalation` list.
`match` supports exact `type`, `source`, `category` and a list of `entities`.
`active_state` defaults to `on`; any other known state resolves the item. Optional
`resolution_state` explicitly documents the clearing state. Unknown/stale inputs
expire rather than resolve. Active durations restart after a clear or freshness gap.

| Field | Default / meaning |
|---|---|
| title / summary | Household attention / empty; empty title uses source title |
| debounce | 0 seconds continuously active before eligibility |
| cooldown | 300 seconds before a resolved/timed item may reappear |
| persistence | `while_active` or `timed` |
| minimum_display_time | 15 seconds; soft hold, released on resolution/expiry |
| maximum_display_time | 0; required positive for timed items |
| interruptibility | true; false holds timed items until their display window ends |
| acknowledgement_required | false; exposes requirement in presentation/API |
| acknowledgement | `reduce` score or `suppress` until condition clears/escalates |
| ack_delta / recent_delta | -30 / -15 |
| confidence_weight | 20; penalty = -(1-confidence) × weight |
| worsening_seconds | 300; window for item.worsening after escalation |
| strategy | global / local / targeted / ambient / critical |
| eligible_displays | empty means all; targeted requires IDs |
| preferred_scene / fallback_scene | attention / attention |
| grouping_key | empty; same key aggregates active items without summing scores |
| dedupe_key | empty; defaults to rule ID plus source dedupe identity |
| modifiers | list of `{id, when, delta}` |

A timed item's wall-clock display window starts on its first selected display.
On completion it enters cooldown, then may resurface if still active. Preemption
does not extend that window. A `while_active` item has no maximum window: use stages,
acknowledgement or timed persistence if reminders should stop. Explicit suppression
is temporary and episode-scoped. Critical conditions remain visible after ack and
cannot be manually suppressed. Acknowledging a group covers its currently active
members, not future events.

## Escalation and scoring

Stages have `id`, `after` seconds (default 0), `priority` (0..1000, default 20),
`urgency` (default ACTIONABLE), optional `when`, and optional `persistence` override.
One rule can express every duration and occupancy stage. Among matching stages,
higher urgency wins, then priority, then duration, then declaration order. A stage
with an unmet context condition never applies. Unknown occupancy does not imply away.

The hierarchy is **CRITICAL > IMPORTANT > ACTIONABLE > CONTEXTUAL > AMBIENT**.
Scores refine ordering *within* a tier. Score = stage priority + matching modifier
values + confidence penalty + acknowledgement/recent-display adjustments. Ties use
stable item IDs. `switch_margin` (default 5) prevents small same-tier score changes
from churning screens. Higher-tier critical items preempt immediately, bypassing
minimum dwell, debounce, cooldown and manual screen freeze. Worsening to a higher
stage renews acknowledgement and cooldown eligibility.

Predicates are JSON objects, never Python expressions:

```json
{"field":"context.sleeping","op":"eq","value":true}
```

Operators: `eq`, `ne`, `gt`, `gte`, `lt`, `lte`, `in`, `exists`. Combine with
`{"all":[...]}`, `{"any":[...]}` or `{"not":{...}}` (depth <= 8). Missing fields
are unknown: comparisons fail, including `ne`; use `exists` to test knownness.
Negating an unknown comparison has ordinary boolean semantics—prefer positive
known-value comparisons for occupancy/security policy.

Fields can reference `signal.*` (including duration, confidence, recurrence,
severity, priority, attributes), `context.*`, `item.acknowledged`,
`item.recently_displayed`, `item.worsening`, `competition.active_signals`, and
`display.*` in local/targeted/ambient score modifiers. Stage evaluation is display-independent. Actionable,
expected and other household concepts can be supplied through attributes/context
and scored with modifiers. The engine does not guess them from entity names.

## Displays and renderers

`displays` contains unique IDs and optional fields: family (`kiosk`/`hubs`), location,
supports_image, supports_video, supports_animation, supports_touch, supports_audio,
screen_size, orientation, idle_state, user_visible, critical_capable, available.
Boolean defaults are in the diagnostic config; image/animation, availability,
visibility, idle and critical capability default true, other capabilities false.

- global: all eligible displays receive the same candidate and score. Display-specific
  modifiers require a local, targeted or ambient strategy.
- local: location must match the signal's configured location.
- targeted: only named eligible displays.
- ambient: only idle displays.
- critical: broadcast to all available critical-capable displays, even if busy;
  ignores location and explicit target restrictions.

Supported scenes: `attention` (text, universal), `source` (existing context renderer,
requires image), `image` (image-capable), `radar` (image + animation). The fallback is
chosen when preferred requirements are missing. Video/audio capabilities are modeled
for future renderers; this release does not add a video or audio alert renderer.
Radar assets are passed through unchanged; no image processing or visual filters.

Browser pages accept `?display=ID`; existing kiosk/hubs URLs retain their meaning.
Garage Cast URLs now carry `display=garage`, so garage-local or critical attention
can activate that target independently of main-Hub playback. Additional Cast
transports still require runtime integration; adding a browser display only needs
configuration and its URL. Availability/idle state can be supplied by an adapter
through the display API; automatic browser heartbeat availability is not inferred.

## APIs and HA bridge

- GET `/api/attention`: fresh signals/items/context, last display decisions, history.
- GET `/api/attention/bindings`: entity/attribute allowlist and heartbeat interval.
- POST `/api/attention/signals`: `{states:[{entity_id,state,attributes?}],full:true,
  observed_at:UNIX_SECONDS}`. Full snapshots expire missing configured entities.
- POST `/api/attention/action`: `{id,action:"acknowledge"|"suppress",seconds?:300}`.
- POST `/api/attention/display`: `{id,state:{available:false}}`; also idle_state and
  user_visible. Runtime state is temporary; configure persistent defaults in JSON.
- PUT `/api/attention/config`: complete attention object, validated and saved.

Use the optional [AppDaemon producer](../integrations/homeassistant/marquee_attention.py).
It fetches configured bindings, listens for state changes and sends full snapshots
at the recommended interval. Configure `marquee_url` in apps.yaml. Existing HA
automations are untouched. There is one ordered HA publisher per Marquee instance;
`observed_at` rejects stale/out-of-order snapshots and must use a synchronized clock.
Payloads are limited to 256 KiB / 2,000 entities. Inputs are allowlisted by bindings.
The endpoints use the application's existing trusted-network access model.

## Retention and operational behavior

Defaults: source TTL 90 seconds, max_signals 2,000, history_limit 2,000 events,
history_seconds 604,800 (seven days). Each HA binding consumes two signal slots.
History bodies are capped at 8 KiB; SQLite reuses freed pages, so its allocated
file size can retain the previous bounded high-water mark. History records signal
changes, transitions, escalation, suppression and winner changes, not every poll.

Cooldowns completed/resolved before restart are persisted. Active observations and
acknowledgements are deliberately not replayed as home truth after restart: fresh
HA snapshots rebuild episodes. Config reload also clears observations so removed
policies/bindings cannot keep a stale scene eligible. Diagnostics reads do not mark
items as displayed. Display explanations include an evaluation timestamp: they
represent the last delivery decision, while active-item data is refreshed on read.

The original arbiter remains the ambient strategy. Its manual controls, UFC-over-PFL
precedence, provider thresholds and Cast calmness are preserved. Individual ambient
candidates are visible as normalized signals; their full historical scoring has not
been migrated into the new policy schema. Cast launch latency still depends on the
existing media/reconciliation loop and the device connection. Policy preemption on
an already-open browser feed is immediate on its next request/SSE tick.

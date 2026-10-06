# Marquee context providers

Marquee's provider engine is the canonical owner of UFC, NHL/Leafs, weather,
TV and astronomy candidates. Plex's high-frequency active-session service feeds
the same arbiter as the fallback media context.
Providers emit normalized candidates; they never cast or manipulate the page.
The arbiter chooses the highest-scoring, unexpired candidate for each display.
Plex remains priority 70 and the fallback when nothing more relevant is active.
The configured provider priority/weight is also a hard eligibility gate against
`context_engine.minimum_relevance`: a provider at 15 cannot surface when the
minimum is 20, regardless of an individual item's urgency or relevance score.
Post-event/recap candidates are suppressed at both provider and final-arbiter
boundaries. Backend lifecycle tokens such as `COMING_SOON`, `STATUS_FINAL`, or
`POST_EVENT` are converted to concise human-facing status copy before rendering.

The optional secondary/garage Cast target has an explicit
`display.secondary_screen_mode`:

- `off` (default) preserves existing behavior: cast only while occupied and an
  active context exists, then release the display.
- `weather` keeps an occupied secondary display on Marquee's clock/weather
  fallback even when no media context is active.
- `mirror` follows the active primary Cast context whether or not the secondary
  room's occupancy sensor is active, and releases when the primary has no
  context.

## Context contract

`Context` supports provider/type/subtype, title/copy, UTC start/end/expiry and
refresh times, lifecycle state, priority, relevance, urgency, freshness,
significance, artwork/background/icon/accent, display targets, source link,
stats and optional raw diagnostic metadata. Fields are optional where a source
cannot honestly supply them. Scores are deterministic: the explicit priority
tier dominates and the four relevance factors refine within it.

Lifecycle values are `UPCOMING`, `STARTING_SOON`, `LIVE`, `RESULT`,
`POST_EVENT`, and `EXPIRED`. Expired candidates are removed during arbitration.

## Configuration

Configure providers at `/admin`. Durable versioned configuration is stored at
`/config/marquee.json`; `providers.json` is imported automatically from the
previous fork layout. `marquee.example.json` documents the full shape. Never
commit the live file: it may contain a Sonarr API key. Environment variables
override stored values:

- `MARQUEE_LATITUDE`, `MARQUEE_LONGITUDE`, `MARQUEE_TIMEZONE`
- `SONARR_URL`, `SONARR_API_KEY`

All providers are independently enabled. Optional placeholders appear in
diagnostics even before their adapters are configured.

`GET /providers` reports state, last fetch/success, next refresh, stale-cache
use, candidate/eligible counts, errors, reasons and normalized candidates.
`GET /contexts` remains the compatibility view for pushed UFC/NHL contexts.

`GET /live` is the responsive browser/tablet display. It subscribes to
`GET /events?display=kiosk` using Server-Sent Events and normally reflects a
new winning context within about half a second. A 30-second JSON poll remains
as a fallback for browsers or reverse proxies that suspend SSE connections.

## Production providers

### Weather

- Environment Canada integration observations and `camera.*_radar` may be
  pushed by `integrations/homeassistant/marquee_sources.py` every 10 minutes.
- The radar bridge reads the camera through Home Assistant authorization and
  sends only the radar image bytes (including its animated GIF). Its temporary
  camera token is never stored by Marquee.
- MSC GeoMet `RADAR_1KM_RRAI` WMS is the official fallback when the HA radar
  image is older than 20 minutes.
- ECCC OGC collection `weather-alerts` supplies official warnings/watches.
- Open-Meteo supplies keyless hourly precipitation probability/timing because
  the HA Environment Canada entity does not expose hourly forecasts in state.

Weather is silent during ordinary conditions. A candidate is created for an
official alert, precipitation active at home, precipitation crossing the
configured probability/amount threshold, extreme temperature, or strong gusts.
Approaching precipitation is kiosk-first; active/severe weather may target hubs.

Refresh: 10 minutes. Successful responses remain usable for 30 minutes.
Radar is fetched at most once per 10 minutes and an HA radar remains preferred
for 20 minutes. No account or API registration is required.

AppDaemon entry:

```yaml
marquee_sources:
  module: marquee_sources
  class: MarqueeSources
  marquee_url: http://10.10.9.37:8084
  radar_entity: camera.halton_hills_radar
  sensor_prefix: sensor.environment_canada_
  kiosk_browser: your-browser-mod-id
```

### TV releases (Sonarr)

The Sonarr v3 calendar is household-specific because only monitored series are
eligible. `tracked_shows` can narrow that set further. Episodes within ±24
hours become candidates; episode 1 receives season-premiere significance and
an episode with a file becomes `POST_EVENT` / "Available now".

Refresh: 15 minutes, stale cache: 2 hours. Requires an existing Sonarr URL and
API key; no new service registration is required.

`providers.tv.tracking_mode` is explicit: `show_all` preserves the existing
default (all monitored series when `tracked_shows` is empty, otherwise the
listed subset), while `tracked_only` emits nothing unless a series is named in
`tracked_shows`. Placeholder series/episode titles (`TBA`, `TBD`, `Unknown`,
`Untitled`, or “To be announced/determined”) and missing/placeholder air dates
are always suppressed in both modes.

### Astronomy

NOAA SWPC's one-minute planetary K-index JSON creates an aurora candidate only
at the configured high threshold (default Kp 6). Copy explicitly says this is
planetary activity, not a guaranteed local sighting. Routine moon facts do not
create contexts.

Refresh: 15 minutes, stale cache: 1 hour. No registration required.

### Gaming and claimed free games

- A read-only FGC bridge publishes only claim title, store, timestamp and URL.
  Account identifiers, browser state, cookies and redemption codes never leave
  FGC. Marquee deduplicates store/title and shows at most three recent claims.
- FGC claim files do not contain artwork. The sanitized bridge now resolves the
  public store page's Open Graph image for only the six newest claims, caches
  both hits and misses for the process lifetime, and publishes that URL as the
  claim artwork. Metadata lookup failure leaves a text-only card without
  delaying later feed polls.
- Epic Store pages return HTTP 403 to the bridge, so Epic claims use the
  official Epic promotions JSON and its CDN `OfferImageWide`/key art instead of
  HTML scraping. Older claims and Epic mobile offer URLs additionally use the
  official Store Content API, normalizing `-android-<id>` / `-ios-<id>` offer
  slugs back to the parent product and preferring 2560×1440 key art. Both hits
  and misses use bounded 256-entry process caches. GOG and Prime retain the
  Open Graph path.
- A grabbed-game confirmation appears only on the local calendar day it was
  collected, using `general.timezone`, and expires at the next local midnight.
  Cached candidates also expire at midnight without waiting for a feed refresh.
  Legacy `claim_ttl_hours` and `lookback_days` values remain accepted for config
  compatibility but no longer extend or shorten confirmation visibility.
  Upcoming game releases keep their separate look-ahead schedule.
- Gaming targets the kiosk at priority 45, below Plex, sports and severe weather.
- AppDaemon also discovers calendars whose entity ID or friendly name contains
  `game release` and pushes their next 30 days of events through a sanitized
  local endpoint. Only summary, description, dates and event URL cross the
  bridge. Set `game_release_calendar_terms` to match differently named release
  calendars, or `game_release_calendars` to explicitly allowlist entity IDs.
- Up to three upcoming releases become compact kiosk contexts. The pushed feed
  expires after two hours so a stopped bridge cannot leave old calendar data
  circulating indefinitely.

Refresh: 10 minutes, stale cache: 2 hours. The saved GG.deals key remains stored
as a write-only provider secret, but deal cards stay disabled because the public
API does not expose deal discovery or deal rating. A future source must already
apply `onlyHistoricalLow=1` and `minRating=8`; Marquee will not approximate that
signal from an unrelated popularity list or scrape GG.deals.

Optional AppDaemon overrides:

```yaml
  game_release_calendar_terms:
    - game release
  game_release_calendars: []
  game_release_lookahead_days: 30
```

### Calendar presentation

The sanitized `POST /calendar-events` feed is owned by a first-class calendar
provider. It handles timed and all-day events in the household timezone,
deduplicates calendar/UID/start identities, raises urgency near the start, and
drops expired or placeholder events before arbitration.

Calendar contexts default to kiosk only. Adding `hubs` to
`providers.calendar.targets` is insufficient by itself: `allow_cast` must also
be true and the event must meet `cast_min_priority` (minimum 80, default 95).
Only then does the provider mark an explicit Cast takeover.

The kiosk renderer treats `calendar_event` contexts and game-release calendar
contexts as glanceable event cards. It uses human lifecycle copy, local
date/time, a countdown only within 24 hours, an explicit all-day label, and an
optional location. Metadata is deduplicated and capped at four items. Cards
without usable artwork collapse to a text layout instead of reserving an empty
image column; failed images fall back the same way.

These rich calendar/discovery cards remain kiosk-first through the arbiter.
Cast stays media-first: active media and emergency/explicit `castTakeover`
contexts retain priority, while the ordinary `/image` receiver may sample an
eligible existing provider context during the deterministic ambient window
(`fallback.cast_ambient_interval_seconds` / `fallback.cast_ambient_duration_seconds`).
Outside that window the established clock/weather idle surface remains visible.

When the kiosk rotation reaches its home slot, the browser composes a quiet
home-state screen from local time and the existing Home Assistant weather
bridge: time-aware greeting, clock, full date and current conditions. Each
piece can be hidden under **Live surfaces → Home**. The extra home copy is
explicitly suppressed on Cast, leaving its established big-clock treatment
unchanged.

## Deliberately not enabled yet

- Movies: choose Radarr/Plex watchlist plus TMDb as the relevance path.
- Trailers: TMDb video metadata or explicit official-channel feeds; YouTube API
  is optional and must not become mandatory.
- Major events: require curated interests/feed selection to avoid a generic-news
  firehose.
- Music: the local Music Assistant integration is the preferred first adapter.
- ISS passes: no dependable free endpoint was selected; N2YO requires a key and
  Open Notify pass data is not reliable enough for a production interruption.

These appear as disabled provider slots rather than fake implementations.

## Failure behavior

Fetches run in a background executor. A slow provider never blocks Plex polling
or rendering. Providers have bounded timeouts, independent health/error state,
disk caches, stale-data limits and conservative refresh intervals. Malformed or
unavailable sources affect only their own provider.


## Household calendar curation and Live layout

Bills calendars and bill notices do not become display cards. Home Assistant's
bridge also excludes the Bills calendar. Birthdays from the configured calendar
window (default 21 days) share one `birthday_rollup` card: the nearest date is
featured, remaining dates are chronological, and duplicate name/date pairs from
multiple calendars collapse. Today's birthdays remain through local midnight;
past birthday dates are excluded even if an event has a later end timestamp.
The card expires at midnight so a cached older winner cannot linger.

The Live screen builder at `/live-settings` follows the Cast editor's select-item,
preview, drag and inspector workflow. `liveLayout` stores positions by surface and
block independently of Cast's `blockLayout`. Home, Sports, Weather and Events/media
support X/Y offsets, width, scale, alignment, font/color, grid snapping and resets.
Clock/weather controls are independent; Sports also has a separate date item.
Save persists only the Live profile; Discard restores the last saved preview.

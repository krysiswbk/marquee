# Marquee behavioral inventory

This document records the behavior of the working fork before its modular
architecture migration. It is a compatibility specification, not a proposed
design.

## Entrypoint and runtime

- `python cast/cast.py` initializes `/config`, creates default settings when
  absent, loads provider configuration, starts the HTTP server in a daemon
  thread, then runs the media/cast reconciliation loop on the main thread.
- The media loop defaults to 5 seconds (`POLL_SECONDS`). It writes
  `now-playing.json` atomically and only talks to Cast receivers on state
  transitions or every sixth poll for reconciliation.
- Provider fetches use a bounded four-worker executor and never run in an HTTP
  request. Each provider owns its refresh and stale-cache intervals.
- Main Hub liveness is based on its `/now-playing.json` heartbeat, with a grace
  window after startup/cast. A DashCast process without a heartbeat is recast.
- Garage casting additionally requires occupancy. An unoccupied garage display
  is released at startup. Casting uses mute, settle, launch, wait, and restores
  the receiver's previous mute state.
- Repeated media-server errors are suppressed until the error changes or the
  backend recovers.

## HTTP contract

GET routes: `/`, `/settings`, `/image`, `/kiosk`, `/live`, `/events`,
`/settings.json`, `/env-defaults`, `/devices`, `/weather`, `/sessions`,
`/contexts`, `/providers`, `/ambient.json`, `/ha-weather.json`,
`/provider-assets/*`, `/custom-backdrop`, `/now-playing.json`, `/healthz`, and
`/release-notes`, plus basename-only static files from `output/`.

POST routes: `/save`, `/contexts`, `/ambient`, `/ha-weather`,
`/weather-context`, `/weather-radar`, `/garage-occupancy`, and
`/custom-backdrop`. DELETE `/custom-backdrop` removes the persisted image.

`/events` is SSE, checks the selected context every 500 ms, emits only changes,
and sends a 15-second keepalive. The browser retains a slower JSON polling
fallback. Kiosk arbitration is calculated live; Hub JSON is the atomically
published snapshot from the main loop.

## Persistence and configuration

- Durable state lives under `DATA_DIR` (normally the `/config` volume):
`settings.json`, `providers.json`, pushed contexts, ambient/weather state,
  custom artwork, radar/provider assets, and per-provider response caches.
- Writes use same-directory temporary files followed by `os.replace`.
- Existing visual settings are allowlisted, normalized and migrated on load or
  save. Old flat block layouts and visibility flags migrate automatically.
- Media backend credentials use stored settings first and environment values as
  fallback. Provider location and Sonarr environment values currently override
  `providers.json`.
- Secrets are write-only in the settings API. The browser receives only `*Set`
  booleans and allowlisted non-secret environment defaults.
- A blank secret field preserves the stored value.
- No application authentication exists. The current deployment assumes a
  trusted household LAN; exposing the port through a reverse proxy requires
  authentication and TLS at that proxy.

## Selection and provider behavior

- Pushed Home Assistant contexts, built-in NHL/UFC contexts, modular provider
  contexts and Plex playback compete by priority. Exact ties prefer explicitly
  pushed household contexts so richer Team Tracker artwork survives.
- Plex playback has priority 70. Live followed sport is normally 90; post-event
  is 85; starting within two hours is 80; ordinary upcoming is 50.
- Contexts require ISO expiration and naturally disappear. Targets independently
  control kiosk and Hub eligibility.
- UFC combines Home Assistant fighter headshots with ESPN completed-bout rows.
  The last two results show winner/loser plus round/time. NHL and UFC query the
  prior UTC date so Toronto evening events survive midnight UTC.
- Weather is exceptional, not ambient filler: official alerts, active or
  approaching precipitation, extremes and high wind can create candidates.
  Home Assistant radar is preferred while fresh; MSC GeoMet is the fallback.
- Sonarr accepts monitored, optionally explicitly tracked household series.
  Astronomy currently emits only high-Kp aurora possibilities.
- Provider errors and stale cache state are independent and visible through
  diagnostics. Optional unimplemented providers remain disabled diagnostic
  slots rather than pretending to work.

## Media behavior at risk during extraction

- Plex, Emby and Jellyfin share selection semantics but have distinct parsing,
  stream/track normalization and artwork endpoints.
- User/device allowlists, content blocking, multi-session deterministic
  rotation, direct-play/transcode labels, subtitle/audio metadata, stinger
  detection, Fanart rotation and custom backdrop behavior are all observable.
- Settings-selected backend/device values override their environment defaults;
  clearing a normal filter restores the environment fallback.
- Missing credentials keep the web/settings server available rather than
  causing a restart loop. `PAGE_URL` remains the only fatal startup setting.

## Deployment

- One Python/Alpine container, host networking, durable `/config` bind mount,
  no broker or database, and `catt` for receiver control.
- Docker health probes `/healthz`. The entrypoint fixes volume ownership then
  drops privileges to the `marquee` user.

# Household desk (2.9.0)

Live and kiosk now use a household desk as their resting state. The desk composes fresh house state, observed door/lock activity, a three-week birthday rollup, and upcoming dates. A lower strip carries secondary releases, same-day game claims, family presence, and household details. Routine cards do not enter automatic or manual Live scene rotation. Sports, active Plex, significant weather, and explicit screen tests retain their scene contracts and precedence. Cast receiver profiles and arbitration eligibility remain separate.

`GET /api/brain` is a bounded read-only presentation snapshot. It does not run a display selection or start attention dwell timers. Normalized HA transitions generate at most 80 recent activity entries, retained in memory for 15 minutes. Initial states, unavailable states, and stale-to-fresh reconnects do not assert an observed transition. Events show for 12 seconds as a brief notice only when observed in the last 45 seconds. Bridge snapshots refresh every 30 seconds or on change; the browser polls the desk every three seconds. Losing the feed replaces current claims with an offline treatment. Current open-state duration means continuously observed duration, not HA historical duration before this process connected.

Important household attention brings the desk forward with its active condition and acknowledgement. Acknowledgement suppresses the policy episode, while the open/unlocked state remains visible until resolution. Critical attention keeps its full takeover. Forecast and weather-warning scenes retain their existing attention behavior. `/live?view=weather` opens the real weather context on demand and still yields to household focus/critical attention.

`liveTheme` selects Studio, After Hours, or Dispatch in the Live builder. They have distinct type, surface treatment, and graphics; `liveLayout.home` now also supports `house`, `activity`, and `agenda`. Clock and existing surface controls are preserved. Desk styling is scoped to Live/kiosk; saved Cast settings are not migrated. Blank fallback settings continue to hide desk panels and the feed.

The AppDaemon source bridge opens the desk once after startup and foregrounds changed household attention keys, using the existing configured kiosk browser. No locks, sensors, alarm helpers, or external notification channels are operated by this feature. Its module reload refreshes the kiosk iframe to the new release. Closing a popup does not immediately reopen the same unchanged scene.

Preview data exists only on explicitly labelled `?demo=1` pages. The production desk uses actual configured sources; it does not synthesize household events or infer missing sensor state.

## 2.9.1 weather and scene layout update

The weather provider publishes a bounded `weather` presentation object with six hourly periods and five daily forecasts. Dry conditions lead with observed conditions and forecasts; radar is used for active or approaching precipitation. Dry alerts still receive a prominent warning banner. Missing numerical values remain unknown and hourly icons use forecast day/night flags. Live supports additional weather layout blocks: `conditions`, `hours`, and `forecast`.

Sports uses a clock grid row on both Cast and Live; its former floating Cast overlay is inactive. Rich scene clock size controls share the selected profile's `sportsClockSize`. Cast settings now provide an event-clock control and preview buttons. Media template fallback clock/weather positions are separate and rendered clock text fits its available area without modifying saved coordinates. Regression scripts `tests/browser_scene_layouts.py` and `tests/browser_media_clocks.py` use an isolated loopback server and `MARQUEE_CHROMIUM` when a custom Chromium path is needed.

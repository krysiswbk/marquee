# 2.12.29

- Supporting weather facts now share the status-line dark gray on Cast.
- Center the clock for single-event calendar displays and brighten Cast
  secondary weather facts for across-room readability.

# 2.12.27

- Add anonymous Home Assistant OpenSky entry/exit events to the ambient sky
  contract with bounded stale expiry, truthful entry-time geometry, and no
  fabricated heading, speed, or continuous track.

# 2.12.26

- Add source-grounded ambient sky and phase-only moon fallback.

# 2.12.25

- Make every Cast page URL unique with a timestamped nonce so repeated explicit
  casts cannot reuse a receiver's old document. Explicit `/api/cast` recasts
  stop an active DashCast session before launching the fresh URL, while normal
  reconciliation avoids unnecessary reloads.
- Keep dynamic HTML/API responses uncached and allow only query-versioned local
  CSS/JavaScript/font/SVG assets to use immutable browser caching.
- Do not infer precipitation amounts when the live weather source omits them;
  `null` remains an honest source-data result.

# 2.12.24

- Cast ambient weather now shows authoritative rain/snow accumulation when
  available, with normalized units and truthful omission for unknown amounts.

# 2.12.23

- Enlarge only the Cast ambient weather detail line for across-room readability, give it tasteful lower spacing, and keep the one-line 1024×600 composition overflow-safe.

# 2.12.22

- Enlarge the Cast ambient weather icon, current conditions, and especially the secondary forecast for across-room Nest Hub Max readability while keeping the clock centered and the composition overflow-safe.

# 2.12.21

- Redesign Cast ambient weather around the geometrically centered primary clock, with condition-aware inline SVG icons, a coherent temperature/condition group, and a restrained forecast line for Nest Hub Max.

## 2.12.20

- Replace Cast ambient weather divider pipes with whitespace while keeping each
  weather fact intact during flex wrapping; preserve browser-controls dividers.

## 2.12.19

- Restore visible separators between Cast ambient weather facts so current
  conditions, feels-like, high/low, and precipitation remain legible on Hub
  displays without changing the established composition.

## 2.12.18

- Keep explicit `/api/cast` requests visible for five minutes when room
  presence is false, then return control to normal presence reconciliation.
- Preserve the bedroom sleep and 22:00 absolute veto even during a manual hold.

## 2.12.17

- Fix the Cast calendar composition at Nest Hub scale: ordinary single-event
  cards now use the same swapped clock/agenda regions as the multi-event
  ambient agenda, with the clock retaining primary visual hierarchy.

## 2.12.16

- Clear the shared Live/Kiosk configuration-refresh warning after the config
  resource recovers successfully, preserving the last saved settings during
  transient failures.

## 2.12.15

- Keep the established Cast ambient clock and agenda sizing while swapping
  only their display regions; preserve the chronological agenda's five-event
  limit.

## 2.12.14

- Swap the Cast ambient calendar regions: the large clock now occupies the
  former agenda/footer region, while the compact chronological agenda remains
  subordinate in the former clock/header region. Preserve up to five events.
- Route the living room, garage, and bedroom Cast displays from authoritative
  occupancy, with debounce/grace release and absolute bedroom sleep/cutoff vetoes.
- Keep Cast ambient provider views clock-first, with a compact multi-event
  calendar agenda subordinate to the clock.
- Preserve the existing ambient cadence, active-media priority, and urgent
  takeover behavior.

## 2.12.12

- Restore the established Street theater-screening composition on the kiosk
  Now Playing destination.
- Keep Cast on its calm clock by default, with a deterministic periodic window
  for existing provider content when the receiver is idle.

## 2.12.10

- Clear the Cast configuration-refresh error after a successful `/settings.json`
  retry so a transient request failure cannot remain permanently visible.

## 2.12.9

- Ignore numeric/count-only Home Assistant warning, watch, advisory, and
  statement values so they cannot become false weather alert titles.
- Keep legitimate textual weather alerts visible while containing their warning
  band, current conditions, controls, and viewport at kiosk sizes.

## 2.12.8

- Commit kiosk context replacements before transition animation so rapid
  refreshes cannot leave the only content stage transparent or detach touch
  controls; keep the last trustworthy frame visible while data is in flight.
- Remove the Browser Mod iframe aspect-ratio row reservation and position its
  dismiss control as a safe-area-aware 56px overlay without a blank top row.

## 2.12.7

- Keep Calendar Previous and Next natively disabled, semantically disabled, and
  out of sequential navigation until measured pagination settles.
- Use a compact two-column full agenda on short-wide 1024×600 displays so
  ordinary events remain ordered and reachable in materially fewer pages while
  irreducibly tall entries retain their bounded reveal behavior.

## 2.12.6

- Preserve unchanged kiosk panel action controls across ordinary data refreshes,
  keeping Calendar, shared detail, retry, and Home actions normally clickable.

## 2.12.5

- Make suppressed attention state and available time truthful, with no invalid
  actions while cooldown or explicit suppression is active.
- Mount the known kiosk destination rail during direct-load fetches to keep
  navigation exits stable, and give Weather heading focus the shared kiosk
  treatment.

## 2.12.4

- Scope explicit Now Playing to the Plex lifecycle so ambient sports cannot
  appear while Plex is idle, paused, stopped, unavailable, or stale.
- Canonicalize the Sky alias to the Astronomy destination and give large PFL
  empty states an intentional kiosk canvas while preserving phone containment.

## 2.12.3

- Direct kiosk navigation now keeps rail targets stable while polling,
  rendering, and focus transitions settle, preventing touch/remote activation
  from being overridden by a concurrent refresh.
- Kiosk Plex playback now has deterministic playing/paused responsive coverage;
  its composition keeps title, episode context, progress, and playback device
  primary while omitting ratings and stream diagnostics.

## 2.12.2

- Add authoritative feels-like temperature to compact sports and generic media
  context weather lines, with deliberate narrow-phone wrapping.

## 2.12.1

- Refine narrow-phone playback, weather context, household feed truncation,
  empty sports states, and administration action presentation.

## 2.12.0

- Add shared Live/Kiosk lifecycle coordination for visibility suspension,
  coalesced polling, late-response protection, cleanup, and accessible
  configuration-refresh failure status.

## 2.11.4

- Anchor active Home and Now Playing progress directly above the shared kiosk
  dock safe area on non-phone displays while preserving phone in-flow layout.

## 2.11.3

- Reserve the shared household feed and kiosk navigation safe area above active playback progress on Home and Now Playing surfaces across non-phone kiosk sizes.

## 2.11.2

- Clean invalid leading `0000 -` tokens from Plex episode titles without
  changing legitimate years or numbers elsewhere in the title.
- Separate active phone playback content from the clock/weather header while
  preserving the shared Home and Now Playing composition.

## 2.11.1

- Omit invalid Plex years from rendered episode subtitles while preserving
  valid episode years.

## 2.11.0

- Unify Home and Now Playing around the same active-playback composition at
  every kiosk viewport, with bounded poster art, readable device identity,
  progress, and hidden decorative/technical blocks.
- Omit invalid Plex years such as `0`, `0000`, null, and non-finite values.

## 2.10.99

- Restore an explicit in-flow phone playback composition for both Home and now-playing routes, with bounded supporting artwork, progress, and device context.
- Hide the phone household people strip while retaining ellipsized dock feed copy and navigation.

## 2.10.98

- Source feels-like weather from `sensor.outside_feels_like_temperature` into the existing authoritative payload field, with truthful null handling.
- Give active phone playback a compact, uncropped summary and constrain poster art to a real 2:3 supporting column; make phone dock copy truncate safely.

## 2.10.97

### Kiosk now-playing follow-up

- Remove the decorative Street frame and sign during active kiosk playback.
- Keep poster artwork in a bounded 2:3 supporting column at kiosk sizes.
- Normalize numeric-string apparent temperatures while preserving truthful
  unavailable output when the authoritative field is null or empty.


### Kiosk playback and navigation

- Show Home Assistant's authoritative apparent temperature as a truthful
  feels-like value in kiosk weather context.
- Make destination activation stable across rail redraws, pointer input, idle
  transitions, and browser history changes.
- Give kiosk now-playing title, episode/context, progress, navigation, and
  useful device context priority; remove stream technicals and ratings from
  that composition and constrain poster art to supporting imagery.


- Keep active and grace-period paused Plex playback authoritative on the
  now-playing endpoint while retaining ambient arbitration when media is idle.

## 2.10.94

- Establish a shared loading, empty, stale, partial, disconnected, and error
  state contract across dashboard, weather, and provider-driven destinations.
- Preserve clearly marked last-known weather and provider data through refresh
  failures, distinguish partial schedules from empty schedules, and keep
  retry/Home actions reachable.

## 2.10.93

- Scope administrative settings controls to the active tab and appearance
  profile so hidden fields cannot participate in validation or interaction.
- Keep tab changes keyboard-safe with predictable panel scrolling, and make
  optional diagnostics, alert, and provider panels tolerate missing elements.

## 2.10.92

- Make full Calendar agenda pagination adapt to the settled viewport, keeping
  ordinary events grouped on tall narrow displays while splitting only pages
  made too tall by long or unbroken content.
- Preserve truthful page URLs, controls, focus, safe-area layout, and
  readable single-event overflow for irreducibly tall entries.

## 2.10.91

- Give manually selected Now Playing a truthful, visible lifecycle surface
  when playback is idle, stopped, unavailable, stale, or recovering, while
  keeping active playing and paused sessions owned by the real media stage.
- Add responsive browser coverage for lifecycle payload agreement, owner
  geometry, Home return, and overflow/error safety.

## 2.10.90

- Keep selected kiosk destinations visible when the live shell enters its idle
  state, including direct links, browser history, and overflow navigation.

## 2.10.89

- Give UFC and PFL browse destinations an explicit full-schedule disclosure
  backed by their existing authoritative event contexts.
- Add paged event navigation with keyboard, remote, and touch-sized controls,
  browser history, and direct Return to Home behavior across narrow, tablet,
  and TV layouts.

## 2.10.88

- Replace the narrow gaming `+N more` dead end with an accessible expander
  backed by the existing authoritative gaming context rows.
- Preserve the compact ambient card, full desktop rows, keyboard/touch sizing,
  and non-interactive Cast presentation.

## 2.10.87

- Replace the inert recent-activity remainder with an accessible full activity
  presentation backed by the authoritative household event payload.
- Preserve the compact ambient summary while supporting touch, keyboard,
  browser-history, stale, empty, and unavailable activity states.

## 2.10.86

- Gate Calendar page fitting on font and layout settlement so the measured capacity cannot change after paging begins.
- Make dashboard birthday and upcoming-calendar summaries link to the existing full Calendar agenda instead of inert `+N` notices.

## 2.10.84

- Settle kiosk config, context, and provider refreshes independently, retaining
  last-good snapshots through partial failures and recovering each resource
  without erasing healthy destinations.
- Keep Plex navigation authoritative to `/now-playing.json?display=kiosk` and
  add deterministic browser coverage for partial failure and recovery.

## 2.10.82

- Keep direct kiosk destination heading focus for assistive technology while
  replacing the oversized heading box with a non-boxy underline treatment.
- Preserve strong interactive focus indicators and refresh local asset cache
  identity across the release surfaces.

## 2.10.81

- Load numeric-control accessibility behavior as a standalone shared helper so
  `/settings` can enhance dynamic provider controls without importing the
  specialist workspace navigation shell.
- Preserve the 2.10.80 validation cleanup and cache-bust all administration
  assets for the repaired clean-load path.

## 2.10.80

- Clear stale numeric validation descriptions without removing persistent helper context.

## 2.10.79

- Centralize numeric-control naming, stable IDs, range help, and validation cleanup in the shared control shell.
- Preserve existing numeric required/optional semantics and keep the direct kiosk rail/Home browser contract wording current.

## 2.10.78

- Give every numeric administration control a programmatic name, explicit unit/range context, bounded validation, and tablet-safe focus clearance.
- Reconcile the dashboard-return browser contract with direct kiosk destinations, the More overflow, and the Home rail action.

## 2.10.77

- Scale the kiosk destination rail for large displays with explicit 1024px and
  wide-TV icon/type tiers, a centered destination grouping, and preserved
  brand/status and More regions.
- Keep the accepted phone/tablet rail, deliberate overflow, active state,
  touch targets, focus restoration, and Home return behavior unchanged while
  adding breakpoint-specific sizing and distribution coverage.

## 2.10.76

- Replace OS-dependent kiosk rail emoji with a deterministic, product-owned
  monochrome SVG icon system that inherits the active cyan/green state color.
- Keep destination identity distinct for Home, Now Playing, Weather, NHL, UFC,
  PFL, Calendar, TV, Sky, Gaming, and More while preserving direct labels,
  overflow priority, touch targets, accessibility, and Home return behavior.
- Add source and browser coverage for icon uniqueness, decorative semantics,
  current-color rendering, responsive rail composition, and single-current
  destination state.

## 2.10.75

- Rebalance the phone People First / On the Horizon continuation so its date,
  detail, and intentional remainder lines remain contained at narrow phone
  heights while preserving the fixed dock and rail safe areas.
- Add deterministic internal agenda overflow and text-line containment checks
  across the responsive household-feed matrix.

## 2.10.74

- Extend the phone household dashboard with a compact People First / On the
  Horizon continuation when fresh birthday or upcoming calendar context exists.
- Keep stale household context out of current agenda presentation, truncate by
  authoritative priority, and add responsive browser coverage for agenda fit,
  empty states, overflow, and fixed-feed safe areas.

## 2.10.73

- Give UFC and PFL direct kiosk destinations promotion-specific resolved empty,
  loading, stale, source-error, and unavailable states without changing their
  normalized ESPN payloads or shared populated sports stage.
- Remove the unexplained resolved-empty mark and add deterministic UFC/PFL
  lifecycle coverage across phone, tablet, short-wide, and desktop viewports.

## 2.10.72

- Keep the Weather segment and Pause controls in a dedicated flow region on
  phone layouts so current, hourly, five-day, and radar content cannot paint
  over the 44px control targets.
- Add rectangle-based responsive browser coverage for every Weather mode across
  phone, tablet, short-wide, and desktop viewports, while preserving the
  Weather accessibility lifecycle and kiosk safe areas.

## 2.10.71

- Fix the Weather kiosk lifecycle so the visible Weather stage, accessibility
  tree, focus targets, and background state share one authoritative surface.
- Expose the direct Weather heading, current summary, source/freshness, and
  44px segment/Pause controls across current, forecast, radar, paused, alert,
  stale, and unavailable states with truthful pressed semantics.
- Add deterministic Weather source and browser regressions for stage exposure,
  keyboard reachability, mode selection, viewport fit, console errors, and
  return to Home.

## 2.10.70

- Restore Home as the single current kiosk rail destination on the dashboard
  and after returning from every destination, while keeping More and utility
  links neutral.
- Add source and browser regressions for initial Home, destination returns,
  More, utility links, and URL/history state across kiosk rail widths.

## 2.10.69

- Correct kiosk current-destination semantics so only the active destination
  link exposes `aria-current="page"`; More and utility links remain neutral.
- Give narrow kiosk navigation distinct NHL, UFC, PFL, Calendar, and TV marks
  while preserving direct Home/current destinations, overflow, and touch targets.
- Add responsive browser coverage for current-state cardinality and destination
  identity across phone, tablet, desktop, and TV rail widths.

## 2.10.68

- Recompose the shared kiosk sports stage into an overscan-safe broadcast matchup surface with stronger team marks, a centered scheduled/live/final state, balanced identities, and cohesive date/venue/broadcast context.
- Preserve truthful empty, unavailable, and stale states plus UFC/PFL shared sports rendering, and add deterministic browser coverage across TV, short-wide, tablet, and phone viewports.

## 2.10.67

- Calm live offline-device health copy across phone, tablet, desktop, and TV
  widths while preserving full named remediation detail in the household panel
  and accessible feed metadata.
- Add deterministic device-health browser coverage for count grammar, bounded
  tablet names, full desktop detail, overflow, rail/dock layout, and errors.

## 2.10.66

- Make the persistent household feed truthful and readable on narrow kiosk
  widths with explicit disconnected/offline state, counted device summaries,
  bounded event/calendar summaries, and an accessible full-text contract.
- Add deterministic browser coverage for target viewport overflow, readability,
  full text, and desktop wording.

## 2.10.65

- Refine the dedicated weather surface for narrow phones into a flowing,
  scrollable hierarchy that keeps current conditions and near-term context
  ahead of reachable forecast controls without clipping the Today narrative.
- Preserve alert, stale/unavailable, forecast-mode, touch, keyboard, kiosk
  rail, and desktop/TV behavior while adding deterministic viewport coverage
  for overflow, clipping, overlap, reachability, and touch targets.

## 2.10.64

- Keep the active/current destination text label visible in the narrow kiosk
  rail while inactive destinations remain compact glyph controls.
- Reserve direct Home and the selected destination during responsive fitting,
  preserving More overflow, 44px touch targets, keyboard focus, and
  `aria-current` semantics without rail clipping or wrapping.
- Add responsive browser coverage across phone, tablet, desktop, and TV rail
  widths for sports identity, overflow, Home reachability, focus, and return
  to the dashboard.

## 2.10.63

- Redesign the idle Now Playing kiosk surface into a calm weather-and-Home composition.
- Remove the ambiguous idle mark and redundant copy while preserving a distinct unavailable/retry state.
- Scope heading focus to the heading content and add responsive idle, weather-grouping, and return-to-Home coverage.

## 2.10.62

- Refine the NHL browse matchup into a single team-vs-team composition with
  authoritative logos, one local date/time, venue and broadcast details, and
  useful live/delayed/final status without repeated ESPN timestamps.
- Give the semantic matchup heading a scoped, accessible focus treatment.

## 2.10.61

- Add a truthful NHL browse contract sourced from the authoritative aggregated
  ESPN snapshot, showing the next followed-team game without widening automatic
  interruption eligibility.

## 2.10.60

- Restore NHL schedule freshness by aggregating bounded single-date ESPN
  scoreboard requests, deduplicating events, and reporting partial-date
  failures truthfully through provider health and cached payloads.

## 2.10.59

- Make narrow kiosk media titles preserve whole-word wrapping while exposing
  deliberate slash-boundary breaks for platform suffixes, with responsive hero
  sizing and deterministic long-title coverage across browse destinations.

## 2.10.58

- Correct the browser attention fixture contract to identify generated
  stage-after controls through explicit semantic metadata and verify their
  accessible help/error references.

## 2.10.57

- Eliminate duplicate attention-editor IDs with deterministic rule, stage,
  modifier, binding, condition, help, and error associations.
- Complete generated Main Settings provider numeric bounds and descriptions,
  with browser contracts for references, invalid states, and responsive admin
  surfaces.

## 2.10.56

- Harden administration touch targets and numeric-input semantics across Main
  Settings, Cast and Live layout, Attention policy, and Test screens. Numeric
  controls now expose truthful model-backed bounds, units, helper text, and
  accessible descriptions while preserving dirty Save/Discard lifecycles.

## 2.10.55

- Include attention event outcome/state in full-payload disclosure names so
  same-kind, same-id, same-time transitions remain uniquely discoverable.

## 2.10.54

- Distinguish recent attention full-payload disclosures by available source,
  event id, context, and display identity while preserving concise visible copy.

## 2.10.53

- Present recent attention history as responsive human-readable event summaries
  with accessible full-payload disclosure, truthful progressive loading, and
  explicit unavailable and empty states.

## 2.10.52

- Keep the Main Settings mobile Save/Discard dock fixed to the viewport through
  long settings pages, with safe-area clearance and deterministic deep-scroll
  reachability coverage.

## 2.10.51

- Keep main Settings save/discard actions reachable on phones with a compact,
  safe-area-aware action bar while preserving truthful pristine and dirty state.
- Give Cast and Live layout editors a baseline-driven dirty lifecycle: pristine
  direct loads disable actions, edits enable them, discard restores the
  baseline, and save success/failure remains accessible and truthful.

## 2.10.50

- Make kiosk destinations an accessible application state: hide and inert the
  covered Home dashboard while browsing, restore its semantics on Home,
  Escape, and browser back, and keep navigation focus truthful.

## 2.10.49

- Recompose sparse Gaming/media browse queues so the lead item stays dominant
  while every current authoritative item remains legible and ordered across
  kiosk, tablet, phone, and large-screen surfaces.

## 2.10.48

- Make the dashboard's compact rain signal complete and truthful: use the
  authoritative hourly timestamp when it provides a near-term horizon, and
  otherwise show only the available precipitation probability.

## 2.10.47

- Make browse artwork truthful: contexts without a generated poster, including
  weather, use their semantic no-art presentation without requesting a known
  404; real media posters remain on the existing endpoint, and failed poster
  identities are not retried on every poll.

## 2.10.46

- Restore viewing-distance readability for the complete shallow-landscape
  weather first look by widening the readings composition and raising the
  narrative, metric-label, metric-value, and provenance type hierarchy while
  preserving exact source values and no-scroll fit.

## 2.10.45

- Fit normal current weather conditions completely on shallow landscape
  Nest Hub-class displays by rebalancing the observation, readings, and
  forecast narrative hierarchy without hiding or truncating authoritative
  content.

## 2.10.44

- Restore explicit Tutorial click launching in both layout workspaces while
  keeping Tutorial outside the real tablist and preserving active-tab state.

## 2.10.43

- Give Cast and settings layout tabs complete roving-tab semantics with truthful
  panel relationships, wrapping Arrow/Home/End activation, and URL state.
- Keep Tutorial as an action dialog that preserves the active real tab and its
  focus/selection contract.

## 2.10.42

- Make the settings walkthrough an accessible action dialog with truthful tab
  state, managed focus, Escape/Skip/Done closure, and launcher focus restore.
- Keep the ordered walkthrough behavior, responsive editor fit, reduced-motion
  behavior, unsaved drafts, and legitimate numeric settings unchanged.

## 2.10.41

- Remove decorative sequence labels from the public setup explanation and
  editor walkthrough while preserving the walkthrough's ordered Back/Next
  navigation and meaningful numeric settings.

## 2.10.40

- Correct the UFC short-wide empty-state heading's fractional line-box
  rounding so its selected stage reports an exact 435px scroll height while
  preserving the complete readable action and PFL's exact fit.

## 2.10.39

- Correct the shared short-wide UFC/PFL empty-state box so its readable
  heading, truthful copy, and complete Return Home action stay inside the
  435px stage without clipping or hidden overflow.

## 2.10.38

- Fit UFC and PFL truthful empty-state headings, copy, and Return Home actions
  inside the shared 435px short-wide kiosk stage while retaining readable type
  and the 48px action target.

## 2.10.37

- Extend truthful shallow-landscape destination fitting through 17:10 displays.
- Keep the Now Playing ambient ring fixed to the viewport so decoration cannot
  inflate the destination stage's scroll geometry.
- Tighten Gaming's content box to end within the stage on short-wide displays.

## 2.10.36

- Add a short-wide kiosk presentation mode for shallow landscape displays.
  Keep Now Playing, source-error and empty states, Calendar, and Gaming primary
  context plus actions in the first view, while summarizing secondary items
  with truthful remainder counts and preserving the existing phone and normal
  TV layouts.

## 2.10.35

- Align dedicated Attention Policy and Display Tests workspaces with the shared
  44px administration touch-target contract while preserving desktop density.

## 2.10.34

- Present provider diagnostics as concise, human-readable status with recency
  while retaining raw provider failures in server-side evidence.
- Correct the About source attribution to the authoritative Marquee fork.

## 2.10.33

- Guard optional layout-editor resize targets so absent panels never receive an
  observer subscription with a null target.
- Make compact Home weather facts visibly distinct with measured spacing and a
  persistent boundary while retaining empty-fact separator suppression.

## 2.10.32

- Keep the authoritative now-playing progress display monotonic while playing;
  paused, idle, unavailable, and recovered states retain their explicit reset
  and stationary behavior.
- Add readable separators to compact Home weather facts on browser-controlled
  kiosk surfaces without changing the weather payload or entity model.

## 2.10.31

- Make the dashboard Customize action a labeled, deliberate masthead control
  with a minimum 44px target on narrow displays and a clear desktop target.
- Preserve the existing layout destination, accessible name, and kiosk data
  flows while preventing the inline action from collapsing to its glyph.

## 2.10.30

- Give the desktop current-conditions outlook enough height for complete
  authoritative forecast narratives without the unnecessary internal scrollbar.
- Preserve the existing narrow weather hierarchy and full-text behavior.

## 2.10.29

- Give the empty activity state a deliberate compact treatment on phone and
  tablet displays so its complete message fits inside the bounded panel.
- Preserve the 2.10.28 agenda geometry and explicit `+N more` summaries while
  removing the tablet overflow escape hatch.

## 2.10.28

- Recompose the 481–700px Home support band so activity and agenda content
  remains fully readable above the household feed and navigation dock.
- Preserve complete agenda detail and summarize only additional recent events
  with an explicit remainder count; remove tablet-only clipping and hidden copy.

## 2.10.27

- Restore shared `.brain-panel` overflow containment while keeping household
  fitting scoped to `#brain-house`.
- Preserve readable compact household text and a minimum 44px acknowledgement
  touch target at phone and tablet widths without hiding household content.
- Retain the 2.10.25 mast/weather improvements and 2.10.26 render-time fitting
  lifecycle with refreshed cache-busted assets.

## 2.10.25

- Fit the populated portrait Home household panel after layout: compact only
  when its rendered content exceeds the panel, while preserving complete
  opening tags, device-health copy, and acknowledgement actions.
- Refit household content after data renders, viewport changes, and supported
  font readiness; refresh all cache-busted assets.

## 2.10.26

- Harden the portrait Home composition with explicit masthead, identity,
  household, activity, agenda, and dock zones.
- Promote phone weather temperature, condition, and secondary facts to a
  legible first-class glance; retain complete long household status copy with
  deterministic dense-panel fitting.

## 2.10.24

- Promote dashboard weather to a persistent current-conditions hierarchy with
  truthful stale, unknown, unavailable, and partial forecast states.

## 2.10.23

- Give the Cast Layout workspace an explicit narrow composition: heading and
  helper copy retain hierarchy, editor rows wrap safely, and primary actions
  remain reachable at phone and tablet widths without changing desktop layout.

## 2.10.22

- Make Settings and admin workspace navigation intentional at narrow widths: configuration destinations wrap into readable, keyboard/touch-sized links and the external display action remains directly reachable without page overflow or clipped labels.

## 2.10.21

- Finalize the kiosk editorial fixed-stage correction with explicit desktop and
  tablet compaction contracts and refreshed shared asset cache identities.

## 2.10.20

- Correct the exposed kiosk Gaming, UFC, and TV editorial stages with
  destination-scoped fixed-stage geometry, safe long-title wrapping, and a
  truthful compact-phone Up Next summary.

## 2.10.19

- Recompose Gaming, UFC, and TV kiosk stages to fit the fixed primary surface
  without hidden internal scrolling; long platform metadata now has safe visual
  break opportunities and Gaming summarizes extra queue items on phones.

## 2.10.18

- Distinguish the initial and retry loading lifecycle from unavailable and
  provider failure states in forced kiosk destinations, with request-generation
  guards so late responses cannot repaint a newer navigation or retry state.

## 2.10.17

- Modernize Attention policy inputs with schema-backed constraints, inline validation, stable field identities, and tablet-safe save-bar clearance.
- Load Test Screens samples independently from Cast discovery and expose authoritative identity for duplicate active attention items.

## 2.10.16

- Make populated Calendar intentionally fit the selected-panel first view on 481–700px tablet displays by removing tablet-only feature dead space and tightening vertical rhythm without reducing comfortable tablet typography.

## 2.10.15

- Fit UFC’s complete single-event summary and the bounded Calendar agenda in the 393px first view with deliberate narrow hierarchy and responsive agenda remainder counts.

## 2.10.14

- Mark the active overflow destination on the narrow More control and make Escape return any forced destination to Home while preserving dialog close/focus behavior.
- Keep healthy empty destinations neutral, bound agenda summaries with an explicit remainder count, and remove narrow single-event layout overflow for UFC and TV.

## 2.10.13

- Resolve each forced kiosk destination from its provider lifecycle, distinguishing populated, empty, stale, unavailable, and provider-error states.
- Present provider failures as unavailable/error copy without treating failed data as current; preserve calm empty-state copy for healthy providers.

## 2.10.12

- Replace forced kiosk browse cards with category-specific sports, agenda,
  editorial media, and calm astronomy compositions.
- Add chronological calendar grouping, human-friendly source presentation,
  shared unavailable/empty actions, responsive dock-safe containment, and
  deterministic architecture contracts.

## 2.10.11 — Contain narrow now-playing overflow

- Clip the forced now-playing surface’s horizontal scrollable overflow while preserving the ambient orbit composition at tablet and phone widths.
- Keep the document and kiosk panel x-axes contained and add a regression contract for the actual scrolling element.

## 2.10.10 — Purposeful now-playing surface

- Keep the authoritative now-playing lifecycle payload intact through forced Plex navigation.
- Add composed idle and unavailable states with Home return, retry, keyboard escape, and responsive kiosk geometry.
- Let active and paused media continue through the existing presentation and progress renderer without cached titles.

## 2.10.9 — Unified now-playing lifecycle

- Clear the authoritative media payload immediately when Plex/Emby becomes unavailable; the API now distinguishes unavailable media from genuine idle without replaying the last title.
- Bound provider progress values, preserve zero offsets, and keep paused playback stationary in the renderer.
- Give unavailable media a deliberate reconnect state while preserving the accepted Home, kiosk, tablet, and phone navigation surfaces.

## 2.10.8 — Remove decorative sequencing

- Remove ornamental numeric prefixes from the household desk section labels.
- Keep the browser-control support-panel geometry contract scoped away from
  481–700px tablet and phone layouts so their dock-safe panel rules win.

## 2.10.7 — Tablet support geometry contract

- Give 481–700px activity and agenda panels explicit dock-safe heights instead
  of relying on an unbounded auto-height plus bottom inset.
- Recompose the tablet activity empty state as a complete, recency-preserving
  phrase within the available panel height.
- Replace the prior bottom-inset regression proof with explicit geometry and
  content-treatment coverage.

## 2.10.6 — Tablet alert content refinement

- Prioritize the specific actionable device-health message in urgent tablet
  household cards and remove duplicated unavailable-sensor prose.
- Keep tablet support panels above the painted dock boundary, limiting lower-
  priority copy when the available height is tight.
- Add regression coverage for alert content priority and dock-safe support bounds.

## 2.10.5 — Tablet dashboard box-model refinement

- Make 481–700px Home panel bounds explicit border boxes with dock-safe insets.
- Prioritize actionable device-health detail over secondary opening chips at tablet widths.
- Add regression coverage for the padding and safe-area contract.

## 2.10.4 — Responsive household hierarchy and release asset identity

- Give the current household state deliberate vertical clearance from activity
  and agenda content at tablet widths.
- Preserve complete actionable device-health detail on phone layouts while
  simplifying and reprioritizing supporting panels below it.
- Align local stylesheet cache-busters with the release version and add a
  regression contract for stale asset identities.

## 2.10.3 — Tablet ambient weather refinement

- Give the 481–700px Home weather summary a wide, balanced two-line composition
  with explicit clearance before the household panel.
- Omit unavailable daily high/low values instead of rendering placeholder dashes.
- Add regression coverage for the weather phrase and tablet layout contract.

## 2.10.2 — Weather hierarchy and narrow-device repair

- Promote Weather in the responsive destination rail so it displaces lower-priority sports when space is limited.
- Keep narrow navigation unobstructed, restore 44px weather controls, and synchronize More dialog close state and focus.
- Make Home weather a compact authoritative summary with available near-term signals, and let narrow weather narrative flow without a nested clipped scroller.
- Add deliberate spacing between the ambient weather line and the live household surface at mid-narrow widths.

## 2.10.1 — Kiosk destination shell

- Publish the reconciled Marquee modernization source and generated frontend assets.
- Replace the kiosk/live generic Menu entry point with direct destination navigation.
- Keep Home and priority destinations visible, using explicit measured overflow only
  when the available width cannot fit the remaining destinations.
- Preserve keyboard/touch access, current state, safe-area spacing, and explicit
  offline, empty, stale, and provider-health treatments.

## 2.10.0 — Consolidated settings and layout workspaces

- Make the four-area Settings page the default: Displays, Content, Alerts, and Advanced.
- Bring all former source-editor controls and household interests into Settings.
- Share a consistent charcoal-and-amber navigation across Settings, Cast/Live Layout, Alert rules, and Test screens.
- Retain rich layout positioning, presets, import/export, custom backdrops, device discovery, and media tools; stage imported setups for review before saving.
- Save layout changes narrowly, preserve unrelated settings and write-only secrets, detect conflicting edits, and support explicit layout resets.
- Replace the long attention form with searchable, collapsed editors and compact diagnostics; protect drafts during failed or concurrent saves.
- Retire previous settings/source/attention/test page files and redirect old bookmarks to their replacements.
- Highlight unavailable nursery devices in the household headline while preserving native Cast modes and configured window exclusions.

## 2.9.8 — Exact kiosk layout on Cast

- Kiosk-mode Cast loads the actual kiosk page in a 1500×1000 reference viewport, scaled proportionally to fit the receiver.
- Preserve the complete kiosk navigation, typography, scene layout, house feed, artwork and animations at both Cast display sizes; no receiver-specific reflow or cropping.
- Keep per-device activity/attention routing and garage occupancy behavior, while fitting the same kiosk canvas to each display.

## 2.9.7 — One Marquee control room

- Shared navigation, active-page state, theme colors and Marquee typography across Cast, Kiosk/Live, Sources, Household Attention and screen tests.
- Dedicated Cast devices tab with independent “use kiosk experience” switches, clear mode explanations and links to kiosk appearance and sources.
- Keep the original Cast design, connection, tutorial, release notes and About sections; add direct tab links and remove duplicate page-link bars.
- Preserve saved display profiles, Cast modes and playback behavior.
- Accept valid decimal location/radar values; saving reveals and focuses an invalid field with a specific inline explanation, including fields on hidden source sections.

## 2.9.6 — Home Assistant weather and secure bridge

- Use the existing HA weather entity for all current conditions and hourly/daily forecasts; remove independent Open-Meteo and IP-location requests.
- Preserve unknown readings and stop using expired forecasts. Refresh the HA observation each minute even when its state has not changed.
- Add a dedicated HTTPS bridge with verified certificate trust and a scoped bearer credential for HA feeds, isolated from browser settings.
- Keep the themed weather channel, animated icons, HA radar, and kiosk/Cast preferences.

## 2.9.5 — Synth scenes and optional kiosk activity on Cast

- Calendar and UFC lists/full screens inherit the selected Live theme, with matching typography, accent lines and panels.
- Weather icons animate sun rays, clouds, moon, rain, snow and fog without changing the weather layout. Reduced-motion users receive static icons.
- Casting settings provide independent main and garage “Kiosk activity” switches, both off by default. Enabled receivers use the kiosk theme, household desk, selection and pacing between playback sessions; garage occupancy/wake rules remain in effect. Saving a switch reconciles the receiver automatically; switching off restores the normal Cast page.
- Receiver pages omit the browser navigation menu. Local kiosk interaction does not blank opted-in receivers; existing per-display attention policy remains in effect.

## 2.9.4 — Themed weather channel

- Weather opens directly from the shared menu into a full-screen broadcast sequence: current conditions, hourly outlook, five-day forecast, and original local radar.
- Each segment uses the selected Marquee theme, with a station masthead, clock, weather ticker, direct segment controls and pause/play. Segments rotate every 15 seconds; reduced-motion/editor views start paused and weather warnings hold their presentation.
- Stale observations, model conditions and radar show explicit unavailable states. Radar metadata carries the original file timestamp and configured enablement; sun and model observation times retain their source timezone.
- Touch layouts and the existing kiosk Menu/household feed stay accessible. Saved appearance, configuration, and Cast arbitration are preserved.

## 2.9.3 — Configuration-driven kiosk menu

- Shared Menu on Live/Kiosk replaces Previous/Next/Freeze with configured source sections and a household desk destination.
- Enabled providers populate navigation automatically, including future provider names; disabled and non-kiosk sources are excluded.
- Browse current source items without changing automatic rotation or Cast selection. Empty and unavailable sections remain explicit; household attention temporarily takes precedence.
- Menu supports touch, keyboard focus, Escape dismissal, narrow screens, and current-section highlighting. Source configuration refreshes every 15 seconds.

## 2.9.2 — Shared kiosk and Live layout repair

- Move navigation into an accessible Menu and reserve a bottom control bar on Live and kiosk; controls no longer cover titles, footers, or the house feed.
- Keep competitor artwork, names and records together; fit artwork within the space left by configurable clocks.
- Add portrait sports composition and readable footer wrapping. Preserve saved layouts and size preferences.
- Version display assets so refreshed kiosk pages load the corrected styles.

## 2.9.1 — Forecast channel and clock layout repair

- Replaced the floating Cast sports clock with a sized grid row. Clock sizing now applies to Cast sports, weather, and event scenes; time strings with seconds fit their reserved space.
- Separated automatic clock/weather anchors on media templates and added overlap fitting for clocks. Preserved saved layouts.
- Added Cast event-clock sizing and sports/weather previews. Live weather builder includes conditions, hourly, forecast, and rain/radar views.
- Weather now leads with current conditions, six hourly periods, and five forecast days. Radar appears for active or approaching precipitation; dry warnings remain prominent. Original radar animation is preserved.
- Added real forecast temperatures, precipitation probabilities, day/night flags, feels-like, humidity, wind, and UV data. Missing values stay unknown.
- Fixed Cast launch discovery-envelope handling.

## 2.9.0 — The household desk

- Rebuilt Live around current household state, recent activity, compact birthdays and dates, and a persistent house feed. Routine calendar, game, TV-release, and summary contexts no longer consume full-screen rotation; Plex and sports keep their dedicated presentations.
- Actual door/lock transitions get brief notices and a 15-minute activity trail. Startup and reconnect snapshots do not invent activity. Open doors/windows and unlocked locks remain visible with observed duration; important events foreground the desk with acknowledgement, while critical alerts retain full takeover.
- Three distinct Live visual directions: Studio, After Hours, and Dispatch. Each has its own typography, surfaces, and graphic treatment. New household panels remain positionable in the builder.
- Broadcast-style local weather presentation with original radar, current observations, and a direct weather view. Offline household feeds visibly stop asserting current state.
- Updated HA kiosk delivery to open the household desk and foreground household attention. Saved Cast profiles remain separate.

## 2.8.2 — 2026-09-10

- Exclude bills from calendar display and consolidate the next three weeks of
  birthdays into one card, featuring the closest and deduplicating calendars.
- Expire birthday cards at local midnight so past birthdays leave the display.
- Restore Live screen item positioning with a selectable/drag-enabled preview,
  X/Y, width, size, font/color, alignment, snap and per-item/screen reset.
- Persist layouts independently for Home, Sports, Weather and Events/media;
  provide separate clock/weather positions while retaining Cast configuration.

## 2.8.1 — 2026-09-10

- Show grabbed free games only on their collection day in the household timezone,
  expiring cached cards at local midnight, including daylight-saving transitions.
- Remove the misleading claim-hours control; upcoming releases remain independent.
- Complete HA bridge calendar response handling, timezone-aware all-day releases,
  household status labels and connection health reporting.

## 2.8.0 — 2026-09-10

- Add a modular household attention engine with normalized signals, semantic house
  context, declarative escalation, contextual scoring and explained arbitration.
- Add acknowledgement, cooldowns, debounce, immediate resolution/expiry, bounded
  history, grouped health notices and capability-based display targeting.
- Native weather alerts outrank ambient content; existing rotation, manual controls,
  UFC/PFL precedence and unmodified radar rendering remain in place.
- Add `/admin/attention`, attention APIs, optional generic HA producer, schema and
  example household policies. Garage attention has its own display feed.
- Add deterministic scenario tests and scoped lint/strict type checks to CI.

## 2.7.0 — 2026-09-10

- Add PFL schedules, bouts, fighter artwork, and results through the shared
  ESPN MMA provider, with source controls and a PFL screen-test sample.
- UFC takes precedence over PFL during live/approaching coverage, including
  Team Tracker contexts. PFL returns when UFC ends or expires.
- Extend the Home Assistant bridge to normalize custom PFL tracker data and
  publish the preferred MMA league for the shared UFC/PFL dashboard card.

## 2.6.1 — 2026-09-10

- Display the original radar image without brightness, contrast, saturation,
  blend effects, or ambient image dimming. Preserve its original animation
  and colors; the upload and serving endpoints retain the source bytes.

## 2.6.0 — 2026-09-10

- Live and kiosk displays now have previous/next and Freeze/Resume controls,
  plus left/right arrow and Space keyboard shortcuts.
- Manual navigation bypasses the minimum screen dwell and grants a full
  rotation interval. Frozen screens keep receiving live data; unavailable or
  expired content returns to automatic selection. Controls are shared between
  live/kiosk clients and reset after a service restart.
- Weather summaries appear once, including when older cached feeds repeat
  the description as a statistic.
- Regression coverage for navigation, freeze, expiry, and Cast isolation.

## 2.5.0 — 2026-09-08

- **Marquee is now an independent fork** with a small composition entrypoint,
  modular runtime, HTTP API, media services, provider package, context arbiter,
  event bus, and versioned configuration repository.
- **New Admin page** for household interests, context priorities, NHL/UFC,
  weather/radar, TV/Sonarr, astronomy, optional providers, provider health and
  manual refresh. Existing settings are migrated automatically and secrets stay
  write-only.
- NHL and UFC now use the common provider scheduler/cache/health contract. UFC
  continues to combine Team Tracker headshots with ESPN fight results.
- Provider diagnostics include fetch duration, cache age, last success, next
  refresh, candidates and isolated errors.
- Removed the duplicate legacy sports scheduler, monolithic runtime/HTTP path,
  and embedded ad-hoc test suite.

## 2.4.1 — 2026-08-25

- **Clearer logs.** Connection problems now say what's actually wrong and where —
  e.g. "can't reach plex at http://…:32400 — connection refused (is it
  running?)" instead of a raw errno — and they're colour-coded. Repeated
  failures collapse to a single line and print a "recovered" note when the server
  comes back, instead of spamming the log every few seconds.
- **Fix: metadata no longer refetched constantly** when two people stream at
  once — the per-title cache kept only one title, so rotation re-pulled art and
  ratings on every flip.
- **Fix: a blocked title no longer hides the other stream.** With a do-not-cast
  filter set and two people watching, a blocked title could blank the whole card;
  now it just skips that title.
- **Fix: false "Atmos" badge** on audio tracks whose name merely contained
  "atmos".

## 2.4.0 — 2026-08-23

- **New: persistent custom backdrop.** Upload your own image (JPEG/PNG/WebP, up
  to 15 MB) to replace the movie/show backdrop, from the Backdrop block editor.
  Fit (cover/contain/stretch), 50–300% zoom, horizontal/vertical focus, opacity,
  blur, and brightness. Off until you upload; the image is stored on the config
  volume and never included in shared or exported looks. Feature by @pqpxo,
  submitted and reviewed by @TRusselo.

## 2.3.0 — 2026-08-23

- **New: session blocks.** Optional Viewer, Device, Stream, Active streams, and
  Audio & subtitles blocks — show who's watching, what they're playing on, the
  playback path (Direct Play / Direct Stream / Transcoding) with resolution, HDR
  and codecs, the server-wide stream count, and the selected audio/subtitle
  tracks. All off by default; add the ones you want from Design → + Add. Works on
  Plex, Emby, and Jellyfin — fields a server doesn't report are simply left off.
- **New: Category is its own block.** Genres split out of the title so you can
  move, size, colour, and font them independently.
- **New: movable Street decorations.** The bulb-lit poster frame and the NOW
  PLAYING sign are now independent blocks you can reposition and resize; rain
  animation gets its own toggle, and the Credits badge is a normal add/removable
  block.
- **New: better title logos.** A bounded, centered logo viewport with
  transparent-padding trim, contain/width/natural fit, and 50–200% zoom — plus
  ten more title fonts.

Thanks to [@TRusselo](https://github.com/TRusselo) (#42).

## 2.2.3 — 2026-08-21

- **Preview at your display's real size.** A "Target display" picker above the
  settings preview sizes the card to the screen it'll actually run on — Nest Hub,
  Nest Hub Max, HD, Full HD, 4:3, a small panel, or a custom size — so what you
  design is what you'll see on the Hub. Preview-only; the card served stays
  responsive. Thanks to [@TRusselo](https://github.com/TRusselo) (#41).

## 2.2.2 — 2026-08-18

- **Settings preview no longer flashes blank on load.** While the card iframe
  boots and paints, the frame shows a subtle shimmer and swaps to the live
  preview on the real first paint — not just when the iframe reports loaded.

## 2.2.1 — 2026-08-02

- **Fanart rotation now floors at 5 minutes** (up to 60), picked from a
  dropdown — the Hub is ambient, not a slideshow. The settings preview still
  rotates fast so you can see it working.
- **Weather only runs where it shows.** A weather block on one template no
  longer keeps the weather fetch alive on every other template.
- **Fixed: chips now see the card's edges.** A block dragged off the edge
  reported as visible; now it ghosts its chip the moment it leaves the frame,
  and truth updates on every slider move instead of waiting for a re-render.

## 2.2.0 — 2026-08-02

- **New: Fanart template.** Rotating fanart.tv artwork for whatever's
  playing — backgrounds by default, or posters, logos, clear art, banners,
  thumbs — crossfading on a timer you set. It starts empty on purpose: add
  only the blocks you want over the art. Tap the background for art type and
  speed; paste a free fanart.tv API key on the Connection tab (stored
  server-side, write-only, like every key).
- **New: fog is real smoke.** Rising particle smoke replaces the old flat
  haze (technique by dburrell, credited), and fixing it uncovered a
  frame-rate bug foggy weather had always carried — gone.
- **New: try any weather.** The Weather editor previews rain, snow, storm,
  fog, cloudy, and day/night on demand. Preview only; never saved.
- **Fixed: adding a block always shows it.** Some combos (Metadata on Big
  Clock, Plot on Hero and Lower Third…) silently never appeared. Chips also
  now verify a block really painted before claiming it's on screen.

## 2.1.0 — 2026-08-01

- **New: share your look.** "Share this look" exports your setup as a small
  credited file; anyone importing it gets it on their carousel as a preset
  "by you", one tap from applied. Credentials and location never ride along.
- **New: honest chips.** A block that's on your card but has nothing to show
  for the current title goes dim and dashed, and the editor says so —
  instead of letting you drag sliders at nothing.
- **New: About credits + support.** Contributors, catt, and the CodePen
  artists behind the weather are named — plus an optional Buy Me a Coffee
  button.
- What's new renders as release cards now instead of a wall of text.

## 2.0.0 — 2026-08-01

Settings v2: the card fills the page and you edit what you're looking at.

- **New: tap-to-edit.** Tap any block on the live preview — or the card's
  background — and only that block's controls appear: font, per-block color
  (new), position, size, and its own settings.
- **New: presets.** Snapshot your current look onto the template carousel;
  Export backs presets up.
- **New: block chips.** One pill per block on the card — tap to edit,
  × to remove, "+ Add" brings anything back.
- **New: a six-step guided tour**, once, on first run — and a phone layout
  where the preview pins to the top so the keyboard can never cover it.
- **Removed:** the vibes/theme rows (per-block color replaces them; saved
  themes keep tinting until you recolor), card-wide font rows, and poster
  side. Every old save and export still imports cleanly.

## 1.12.2 — 2026-08-01

- Real design work on the only page we have: the card-content toggle wall is
  now a light board — every card element is a bulb chip, lit amber when it's
  on the card, dim glass when off. Fourteen full-width switch rows became
  three rows of chips, with the clock and weather fine-tuning grouped
  beneath them, still gated by their chips.
- Tapping a block on the preview flashes its chip, so on/off and
  place-and-size always point at each other.

## 1.12.1 — 2026-08-01

- Course correction on the editor idea: nothing hides anymore. Every option
  is on the page, organized under sticky section chips (Template · Look ·
  Card · Connection); tapping a region of the card now scrolls its controls
  into view and flashes them instead of swapping panes.
- The preview is a small monitor — sticky top-right on desktop, and back in
  the bottom sheet on phones (the pattern that worked), sized down so the
  controls keep the room.

## 1.12.0 — 2026-07-31

- The settings page is now an editor: the card fills the page and is the
  navigation. Tap anything on it — the poster, the plot, the clock — and just
  that thing's controls appear in the inspector rail. Look (templates, vibes,
  theme, fonts) is the rail's home; server, casting, filters, and
  export/import live behind Connection & casting in the top bar.
- Save moved to the top bar, always in reach; on phones the card rides sticky
  at the top while the inspector scrolls beneath it.
- Nothing about the card or the saved settings changed — same keys, same
  save flow, same instant preview.

## 1.11.4 — 2026-07-31

- The settings page now looks like the product it controls: the masthead is a
  letterboard between two bulb rails in the card's own Bebas Neue, section
  titles speak the same face, toggles glow amber when lit, the preview sits in
  a real screen bezel that spills a little light, and the marquee's glow pools
  down from the top of the page.

## 1.11.3 — 2026-07-31

- Settings page pass: Card content rows are grouped now — Clock style and
  seconds sit under the Clock toggle, weather intensity/ZIP/units under the
  weather toggles, and controls whose parent is off dim and disable instead
  of silently doing nothing.
- The preview leads: on desktop the demo card now sits right under Save with
  the block editor folded beneath it (tap a block to unfold it, same as
  phones), so the preview is always in view instead of below an open editor.
- Panel headings got a size bump and a hairline rule — the long page scans.

## 1.11.2 — 2026-07-22

- The card now accepts a `?tpl=<template>` query param to preview any
  template without changing saved settings — so a demo link like
  `/image?demo=1&tpl=street&wx=rain&day=0` always shows the Street scene and
  weather regardless of which template is saved. View it on a wide/landscape
  screen; the card is designed for the Hub's 16:9 display.

## 1.11.1 — 2026-07-22

- Fixed the now-playing card requesting a missing `/favicon.ico` (a harmless
  404 and console error). The card now carries the same tab icon as the
  settings page.

## 1.11.0 — 2026-07-22

### Street weather, rebuilt for real

The live weather on the Street scene got a full realism pass, built around
techniques from four community CodePens (credited in `CREDITS.md`):

- **Rain and snow now draw on a `<canvas>`** — real particles, not CSS
  tiles. Rain streaks vary in length with fall speed and kick up splash
  droplets when they land, coloured near‑white rather than blue. Snow is
  150 flakes with random size, speed, and wind drift — no repeating grid.
- **Fog** is three soft layers drifting at different speeds with
  independently pulsing opacity under a blur — a real rolling haze instead
  of a flat wash.
- **Overcast** casts a slow drifting cloud shadow instead of flat dimming.
- **Thunderstorms** (`?wx=storm`) are their own condition with denser rain
  and stronger dimming.
- **The "NOW PLAYING" sign glows like neon** with an irregular flicker,
  theme‑tinted, resting in daylight.

The canvas only runs while rain/snow/storm is active and stops otherwise,
so it costs nothing on a clear day.

**Weather effects are now their own setting** — **Weather effects** under
Card content, separate from the **Weather** text chip. You can have the
temperature readout without the scene effects, or the effects without the
readout; neither is tied to the other. On by default so Street keeps its
signature look.

**Effect intensity (1–4)** — a new dropdown under Card content scales how
strong the weather looks: particle count, particle opacity, and fog/cloud
density. Defaults to **2 (Light)**, which stays easy to ignore if the
screen sits in the corner of your eye while you watch something.

Test any condition live with `?wx=rain|snow|fog|cloud|storm`, `?day=1|0`,
and `?wxi=1..4` on `/image`.

## 1.10.0 — 2026-07-21

### Mix and match any block, on any template

The block editor's "Selected block" dropdown now only ever lists what's
actually on the current template. A new **Add a block** control sits next
to it: pick a name and it's placed on the template immediately (auto-slotted
onto an open spot, ready to drag), then resets itself so it's always ready
for the next one. A **Remove block** button drops the selected block back
off. Every template ships with its original block set untouched — this is
purely additive, so nothing changes until you actually add or remove
something. **Reset this template** now restores the template's shipped
block set too, not just positions.

Weather is no longer nested inside the clock block sharing its position —
it's its own block, sized and placed independently. Adding it also turns
its data fetch on if it wasn't already (that one setting used to default
off, unlike everything else you can add).

Every block change is scoped to the template you're looking at: nudging a
block's position on Spotlight no longer silently nudges it on Street too,
the way it used to.

### The mobile settings page gets a top strip instead of a wall of cards

On phones, the Template grid and the inline Vibes stepper — two overlapping
ways to pick mostly the same thing — collapse into one looping, swipeable
carousel pinned under the header. Swipe through and the preview updates
live, the same way Vibes always has; tap a card or let it settle and it's
applied. Frees up most of a screen's worth of vertical space before you
even reach a real control.

Also on phones: a focused text field elsewhere on the page popping the
keyboard used to leave the fixed preview sheet pinned across most of the
little space the keyboard left, crushing whatever you were trying to type
into down to a sliver. The sheet now gets out of the way while a keyboard's
up — nothing in it needs one.

### Real weather on the Street scene

Street's brick wall now reacts to actual conditions: rain streaks, drifting
snow, or overcast dimming, plus true day/night — daylight brightens the
wall and rests the marquee's bulb-twinkle and sign-chase animations instead
of running them under a bright sky. Same `/weather` endpoint every template
already used for the weather chip; Street just also fetches it for itself
when you haven't turned the chip on. `?wx=rain|snow|fog|cloud` and
`?day=1|0` force a condition, for testing without waiting for the sky to
cooperate.

The poster also picked up a theme-colored glow bleeding onto the brick
behind it, like backlighting through the marquee case — it retints with
whichever accent color the card is using, the same as the progress bar and
title glow already do.

## 1.9.0 — 2026-07-20

### A "do not cast" list, so the marquee can't overshare

A new **Do not cast** filter: comma-separated words, checked against every
session's genres, tags, and content rating. A match means that session is
never cast — no title, no poster, no card. Set it as `BLOCK_TAGS` in the
container or type it on the settings page (same default-vs-override rule as
the other filters, with the env value shown as a greyed placeholder).
`adult, xxx, 18+, nc-17, tv-ma` is the obvious use, but it's just words —
block `horror` on the family display if you like.

Matching is deliberately broad: case-insensitive, and words of three or more
characters match inside terms, so `adult` also blocks an "Adult Animation"
genre — for an overshare guard, blocking too much beats leaking. Shorter
words match a term exactly, so blocking the `R` rating doesn't take Horror
and Drama with it. On Emby/Jellyfin, where `/Sessions`
sometimes omits the genre list, the picked item is re-checked after its full
record is fetched: better a blank display than a title the pre-filter
couldn't see. Blocked sessions still appear in the settings page's Active
sessions list (marked not allowed), so the admin can see the filter doing
its job.

### Env vars are defaults you can see, not overrides you can't

`PLEX_USERS` / `PLEX_DEVICES` used to **merge** with the settings page instead
of being replaced by it. The env list was invisible — the Users field showed
empty while every other session was silently ignored — and unliftable: the
page could only add names to what the env var already allowed, so clearing the
field changed nothing. `HUB_IP` alone behaved correctly.

Now all three follow `HUB_IP`'s rule: a typed value replaces the env var, a
blank field inherits it. The inherited value is shown as a greyed placeholder —
`jamison (from PLEX_USERS)` — via a new `/env-defaults` route that serves
exactly those three values and nothing else, an allowlist so nothing
credential-shaped can leak to a browser by default. `selftest` pins the
override semantics (blank inherits, typed replaces, the env is never unioned
back in) and the allowlist (no token/key-shaped name may ever join the hints).

The Emby/Jellyfin session picker now uses that same `filter_set` resolution —
previously only the Plex path did, so on an Emby backend the user/device fields
still merged with the env var (invisible, unliftable) while the docs promised
they replaced it. Both backends read the same settings fields, so both now
behave identically; `selftest` drives `emby_current_session()` to prove a typed
user list excludes an env-allowed user rather than unioning it in.

### Emby and Jellyfin join Plex

Marquee can now watch an Emby or Jellyfin server instead of Plex. Set
`MEDIA_BACKEND=emby` (with `EMBY_HOST` / `EMBY_API_KEY`) or
`MEDIA_BACKEND=jellyfin` (with `JELLYFIN_HOST` / `JELLYFIN_API_KEY`); Plex
stays the default and the Plex path is untouched.

Both backends produce the same now-playing dict, so every template, theme,
toggle, and the session filters and rotation work identically — the selftest
asserts the two parsers emit the same keys. Emby's `/Sessions` omits some of
the fields the card wants (genres, media streams, ratings, overview), so the
backend fetches them from `/Items` once per title and caches them, exactly as
the Plex path caches its metadata lookups. Artwork (poster, backdrop, logo)
comes from the item image endpoints at the same sizes the Plex transcoder
delivers.

Jellyfin forked from Emby in 2018 and the handful of APIs Marquee uses —
`api_key` query auth, `/Sessions`, `/Items`, `/Items/{id}/Images/*` — are
byte-compatible, so Jellyfin rides the Emby code path unchanged. The
`JELLYFIN_*` env names are aliases for the `EMBY_*` pair, accepted so a
compose file can say what it means. Verified end to end against live Emby and
Jellyfin (10.11) servers, through to the card rendering on a real Nest Hub.

### Switch backends from the settings page

A new **Media server** panel picks the backend: one dropdown (Plex / Emby /
Jellyfin), one server-address field, one key field. The dropdown decides
which backend the two fields edit; each backend keeps its own stored pair,
so switching between servers loses nothing. Like every other setting,
nothing changes until **Save**; the choice is then resolved every poll, so a
saved change takes effect within ~5 seconds — no container restart. The
settings page wins and env is the container-level default, exactly the rule
the cast device field has always followed; with nothing set anywhere, the
backend is plex, as it has always been.

Keys and tokens are write-only secrets: stored server-side, never served
back to a browser. `/settings.json` replaces each with a saved/not-saved
hint, the page shows *saved — blank keeps it*, and Export/Import never
carries them. Saving a backend that has no server configured anywhere is
rejected with a clear error rather than stored — a backend that fails
silently on the next poll would just be a blank display with no explanation.

With that, only `PAGE_URL` is required at startup. A container with no
media-server credentials at all no longer exits; it warns and serves the
settings page, where the server address and key finish the job. Every
credential env var still works exactly as before — it is simply no longer
the only way in.

## 1.8.0 — 2026-07-19

### The block editor grows up

- **Font per block**: a Block font picker next to Selected block. The clock,
  progress bar, plot — any block — can now carry its own face; Theme default
  keeps the card-wide fonts. Title & logo blocks apply it to the text title
  too.
- **Snap to grid**: get a block close, hit the button, and its top-left corner
  lands on the nearest line of the grid you already see while editing
  (every 2.5% of the screen).
- **Justify tells the truth**: Left/Center/Right now aligns the logo image and
  the plain-text title the same way, in every template. Before, templates that
  center the title block (Hero, Big Clock) kept centering the *logo* while the
  text obeyed your choice — so a movie without a clear-logo drew its title
  off-center from where the logo had been.
- The editor also no longer writes `align: left` into your layout the first
  time you touch a slider — that silent write was how most off-center titles
  happened. No Justify button lights up until you actually pick one.

### Phones stopped fighting you

The preview, the block controls, and Save now ride together in one fixed
bottom sheet. Scrolling the settings page can't graze a slider and skew a
block, Save is always next to what you're previewing, and tapping a block in
the preview unfolds the editor right above it. On desktop nothing moved —
the editor just gained the same Snap button and font picker, and folds away
if you want it gone.

## 1.7.0 — 2026-07-14

### The Hub no longer sits on a blank screen

Marquee decided whether to cast by asking the Hub whether the DashCast app was
loaded. That answers the wrong question: a Hub whose card page has died — it
crashed, reloaded into nothing, or was left holding a stale page — keeps
reporting DashCast forever. Marquee concluded the card was already up and did
nothing, silently, while the display showed nothing. There was no error, and
nothing in the log.

The card fetches `/now-playing.json` every `POLL_SECONDS`, so the server already
knew whether the page was alive; it just wasn't looking. That fetch is now
timestamped, and a card silent for longer than 45 seconds is treated as gone and
re-cast. A page cast moments ago gets one window to load before it counts.

`/healthz` reports `cardPollAgo`, `cardAlive`, and `cardGrace`, so a display
showing a dead page is now visible from outside the container — which matters,
because per-request logging is suppressed.

### More than one person is watching

When two people stream at once, the card used to flip between their titles at
random. `/status/sessions` has no defined order, Plex reorders it as sessions
come and go, and Marquee took whichever session happened to be listed first —
re-deciding every poll.

Sessions are now sorted by user, then device, then title, so the choice is
stable. When more than one allowed session is playing, each takes the display
in turn: a new **Rotate between sessions** setting, 30 seconds by default. Set
it to 0 to pin the first one instead.

Rotation is a pure function of the clock, so nothing needs to be remembered
across a restart, and two displays watching the same server show the same
session at the same time. Your user and device filters still decide who is
eligible — rotation only orders whoever is left, so filtering to yourself with
two devices rotates rather than flickering.

## 1.6.0 — 2026-07-09

### Share your look

- **Export / Import**: two buttons next to Save. Export copies your whole
  setup as text; Import pastes someone else's and applies it (your cast
  device stays yours). Post your look, let people steal it.

### Mobile

- The settings page works properly on phones now — no more sideways
  overflow — and the **live preview rides the bottom of the screen**, so
  stepping vibes, flipping toggles, and changing fonts is always visible
  while you scroll the controls.

### Type

- **Card font** joins Title font: pick a face for everything else — plot,
  metadata, clock. Per-element size still lives on the block editor's
  Size slider.

### Odds & ends

- Street's pay phone is retired.
- `?demo=N` pins a demo film again (and holds through the rotation timer).
- README leads with a variety collage and real-library screenshots.

## 1.4.0 — 2026-07-08

### Session filters

- New "Who triggers the marquee" section in settings: limit casting to
  specific Plex **users** and **devices**, editable live — no container
  restart. Empty fields keep the old behavior (everyone, any device), so a
  shared user's stream — or your own phone away from home — no longer takes
  over the Hub.
- An "Active sessions" check shows exactly who is playing what on which
  device, with the exact names to copy into the filters, and flags sessions
  the current filters exclude.
- `PLEX_DEVICES` env var joins `PLEX_USERS` as a container-level fallback;
  both merge with the settings-page lists.

### Demo reel

- The single demo movie is now a four-film reel of original fictional
  comedies — *Shaking Hands & Kissing Babies* (campaign-poster style),
  *Rat King III: Still Gnawing* (graffiti stencil), *Participation Trophy*
  (sticker bomb), and *B-Sides* (vinyl sleeve). Each has hand-built vector
  poster, backdrop, and logo art; the preview picks one at random per load,
  and pure demo mode (`/image?demo`) rotates every 20 seconds.
  `?demo=N` pins a film. Roughly 70KB lighter than the old embedded art.

### Street template & vibes

- New **Street** template: a living night scene — brick wall, pay phone,
  and your poster hanging in a bulb-lit **NOW PLAYING** marquee frame. The
  clear-logo (or title) reads as spray-painted onto the brick, grain and all.
  The lighting is alive: marquee bulbs twinkle on their own phases, the sign
  bulbs chase, the neon flickers now and then, the street-lamp pool breathes,
  and the marquee trim re-lights in your theme's accent. Honors
  prefers-reduced-motion.
- Four new themes named for the demo reel: **Campaign** (navy & red tape),
  **Concrete** (back-alley gold), **Trophy** (gold-star yellow), and
  **B-Sides** (dollar-bin orange).
- **Vibes**: one-tap presets bundling theme + font + template — Campaign
  Trail, Back Alley, Gold Star, Dollar Bin, Simulation ("we're all just
  programming ourselves"), and Third Act ("the universe is on its final
  reel"). Tap one, tweak, save.

### Preview & accent

- Changing the title font now previews instantly even when a clear-logo is
  shown: the card swaps in the text title for a few seconds so you can see
  the font.
- A custom accent color now tints as deeply as the built-in themes: metadata
  chip borders and the progress track pick it up too.
- The Big Clock template's clock now glows in the accent color.

## 1.3.0 — 2026-07-07

### Layout & type

- Every block can now be justified left, center, or right from the editor.
- Title fonts: Bebas Neue, Oswald, Playfair Display, Cinzel, and Space
  Grotesk (free Google fonts, system fallback when offline).
- Themes go deeper: each theme now tints panels, chips, and progress tracks,
  and the accent glows through the title and progress bar.

### Feel

- Saves reach the Hub in ~2 seconds — the card polls settings on a fast
  loop instead of waiting for the next now-playing cycle.
- Template picker cards show real screenshots of each layout.
- The demo movie now includes a title logo, so the clear-logo look
  (pulled from Plex metadata on real playback) is visible in the preview.

## 1.2.0 — 2026-07-07

### Device discovery

- The settings page now finds Google Cast devices on your LAN (mDNS via
  `catt scan`) — press Scan and pick your Hub from a dropdown instead of
  typing an IP. `HUB_IP` remains as an env fallback and is no longer
  required, so the container starts fine before a device is chosen.

### Cleanup

- Removed one-time repo bootstrap scripts.
- `PLEX_HOST` defaults to `http://localhost:32400`; field descriptions now
  explain why `PAGE_URL` must be a LAN IP the Hub can reach.

## 1.1.0 — 2026-07-06

### Templates

- Rebuilt the card around self-contained blocks (title/logo identity, grouped
  ratings, metadata chips, plot, progress, clock, poster) and added five
  hand-designed templates that arrange them into genuinely different
  compositions: Spotlight, Split, Hero, Lower Third, and Big Clock.
- Template picker in settings with sketch thumbnails and instant live preview —
  changes preview in the demo frame without touching the Hub until saved.

### Customization

- Custom accent color picker alongside the four themes.
- Clock styles: 12/24-hour format and optional seconds.
- Block editor now moves and resizes whole blocks: position, width, and a new
  size control; every block can be shown or hidden independently.

### UI

- Release notes moved into a slide-over panel ("What's new") instead of a
  page-bottom section.
- Demo art is embedded in the card, so the settings preview always renders
  fully even before anything has played.

### Fixes

- New `PLEX_USERS` setting limits which Plex users trigger the marquee.
  Previously any session on the server — including shared and home users —
  would take over the Hub.
- Metadata strings are now HTML-escaped on the card, so titles or ratings
  containing &, <, or quotes render correctly.

## 1.0.1 — 2026-07-06

### Reliability

- Fixed a crash loop on first start when `/config` is a host-owned bind mount
  (e.g. Unraid appdata, which arrives root-owned): the container now starts as
  root, chowns `/config` to the `marquee` user via an entrypoint, then drops
  privileges with `su-exec` before running the app. No more manual `chmod` on
  the appdata folder.

## 1.0.0 — 2026-07-05

### Features

- Initial Marquee release with Plex session polling, artwork, metadata, scores,
  progress, clock, poster/backdrop layouts, themes, and Google Nest Hub casting.
- Added one-click presets for minimal, clock-focused, poster wall, cinema, and
  dusk presentation styles.
- Added snap-grid move and width-resize controls in the live preview.
- Added persistent container settings under `/config`.

### Reliability

- Hardened container publishing so Docker Hub login is only used when
  credentials are present.
- Kept the cast workflow on current GitHub Actions releases.
- Added explicit Cast command error logging and retry behavior.

### Documentation

- Added a polished public README, screenshots, and version-history links.
- Removed internal Unraid/template setup language from the public docs.
- Kept the release notes visible in the settings panel for quick review.

### Notes

- Added explicit versioning and a clean container/Compose deployment path.

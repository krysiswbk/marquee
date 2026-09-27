# Attention architecture review

Marquee already separates provider acquisition, context arbitration, HTTP delivery,
Cast reconciliation and browser rendering. This change extends those seams; it does
not replace providers or rebuild Home Assistant automations.

## Decision

A normalized signal store owns source freshness and continuous-condition timing.
A house-context provider maps configured state inputs into semantic values. A pure
attention manager evaluates declarative stages and modifiers, owns lifecycle,
acknowledgement, cooldown and display dwell, then chooses a scene for each display.
Renderers receive presentation data only. All clocks are injectable in tests.

Existing provider contexts and Plex remain under the existing ambient selection
strategy (including rotation, manual freeze, UFC precedence and Cast eligibility).
The attention service presents that strategy's choice as the ambient baseline to
arbitration. Policies may independently consume normalized provider signals. This
explicit compatibility boundary protects successful behavior while new conditions
can outrank it. Ambient rotation is a policy, not a promise that the largest numeric
score occupies the screen forever.

The hierarchy is lexicographic: CRITICAL, IMPORTANT, ACTIONABLE, CONTEXTUAL,
AMBIENT; within a tier, explained contextual scores select the winner. Critical
items bypass debounce, cooldown, manual controls and minimum dwell. Resolution and
expiry always release a previous selection, including a frozen ambient selection.

## Modules

- `signals`: normalized observations, freshness, episodes and HA binding adapter.
- `context`: semantic house snapshot with unknown values when inputs expire.
- `attention/schema`: validated declarative conditions, stages, scoring and displays.
- `attention/manager`: deterministic lifecycle and arbitration; no network calls.
- `attention/scoring`, `targeting`, `history`: independent policy mechanisms.
- `attention/service`: synchronization and compatibility/presentation boundary.
- `api/attention`: bounded ingestion, diagnostics and acknowledgement API.

History is bounded by count and age and persisted locally. No stale signals are
replayed after restart. Diagnostics include suppressed candidates, stages, score
components, display eligibility and winner reasons. Configuration updates invalidate
old policy decisions immediately. Acknowledgement applies to an episode/stage;
a worsening stage can demand attention again.

## Operational boundaries

Home Assistant remains the authority. An optional generic AppDaemon adapter forwards
only configured bindings and periodic snapshots. No entity identifiers are baked
into the engine. Example door/leak/laundry policies are opt-in. Missing or stale
telemetry is unknown, never an invented healthy state. Source updates are ordered
and refresh freshness without restarting a continuously active condition.

Browser feeds evaluate attention on each request/SSE tick. Cast startup/release is
still reconciled by the existing runtime; physical transport latency is distinct
from immediate policy preemption. New display IDs map to an existing transport
family, while capabilities and locations remain independent of device models.

## Validation plan

Deterministic unit and scenario tests cover stages, contextual scoring, grouping,
flapping, cooldown, acknowledgement, resolution, expiry, critical preemption,
dwell, targeting and offline displays. Existing provider, radar, manual-control
and runtime tests remain the regression baseline. HTTP and browser smoke checks
exercise the production composition without sending simulated alarms to the house.

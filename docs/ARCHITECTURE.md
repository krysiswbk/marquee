# Marquee fork architecture

Marquee is a single-process, modular Python application. The running behavior
of the pre-fork implementation is the compatibility contract; modules are now
organized by responsibility rather than by their upstream file location.

## Directory map

```text
cast/cast.py                       executable entrypoint
cast/marquee/application.py        composition root
cast/marquee/runtime.py            scheduler and Cast reconciliation
cast/marquee/config.py             schema, validation, migration, persistence
cast/marquee/core/arbitration.py   eligibility, enrichment and selection
cast/marquee/core/events.py        in-process lifecycle events
cast/marquee/providers/            provider API, engine and adapters
cast/marquee/services/media.py     Plex/Emby/Jellyfin, artwork and Cast service
cast/marquee/api/http.py           HTTP/SSE/static/upload API
cast/marquee/composition.py        shared state and display-config composition
cast/admin.html                    provider/context administration
cast/settings.html                 visual designer and media connection settings
output/index.html                  kiosk/Hub presentation
tests/                             offline unit and characterization tests
```

`cast.py` only selects self-test versus application startup. `application.py`
constructs the runtime. The runtime initializes validated configuration,
providers, the HTTP thread and the media reconciliation loop. External fetches
run only in provider workers or the media loop, never in request handlers.

## Context engine

Providers emit `Context` instances with stable Marquee fields, lifecycle,
expiry, targeting and deterministic scoring inputs. `ContextEngine` schedules
independent cached fetches and owns provider health. `ContextArbiter` combines
provider candidates, explicitly pushed household candidates and active Plex.
It filters expiry/relevance, enriches matching household contexts without
replacing their artwork, and selects per display. Selection transitions publish
`context.selected` on the in-process event bus.

Specialized presentation remains intentional: normalized data feeds the Plex,
sports, radar and generic renderers rather than flattening them into one card.

## Provider contract

A provider subclasses `Provider`, declares `name`, `refresh_seconds` and
`stale_seconds`, then implements `fetch()` and `contexts(payload, now)`.
`fetch()` returns source data; `contexts()` validates and normalizes it. The base
class supplies bounded-client access, atomic disk caching and stale fallback.
The engine supplies failure isolation, scheduling, diagnostics, manual refresh,
and executor cleanup.

To add a provider:

1. Add its typed defaults to `marquee.config.DEFAULT_CONFIG`.
2. Implement it in `marquee/providers/` without importing HTTP or Cast code.
3. Register it in `providers/registry.py`.
4. Add focused mocked-source tests and its practical controls to `admin.html`.
5. Document credentials, refresh interval, stale lifetime and trigger policy.

## Configuration and migration

Two durable documents have deliberately separate ownership:

- `/config/settings.json`: Cast visual layout and media-server connection settings,
- `/config/live-settings.json`: browser/kiosk visual overrides (source settings
  and credentials remain inherited from `settings.json`),
  maintained by the established display designer.
- `/config/marquee.json`: versioned application, interest, arbitration and
  provider configuration, maintained by `/admin`.

On first fork startup, `providers.json` is imported into `marquee.json`; the
existing display rotation is imported from `settings.json`. Existing files are
not destroyed, so rollback remains possible. Writes are validated before an
atomic replace. Configuration and legacy media settings containing credentials
are mode `0600`. Browser APIs replace secrets with `*_set` booleans; an empty
secret input preserves the stored value.

Effective provider precedence is environment override, then stored value, then
schema default. Currently supported overrides are `MARQUEE_LATITUDE`,
`MARQUEE_LONGITUDE`, `MARQUEE_TIMEZONE`, `SONARR_URL`, and `SONARR_API_KEY`.
Media server environment fallback behavior is unchanged.

## HTTP and realtime

`api/http.py` owns the existing route contract listed in
`BEHAVIORAL_INVENTORY.md`, plus `/admin`, `GET /api/config`, and
`PUT /api/config`. SSE at `/events` is the fast browser/tablet path; JSON
polling remains a fallback. `/providers` exposes state, fetch/success times,
next refresh, duration, cache age, candidates, errors and eligibility.

## Debugging

Open `/admin`, select **Health**, and use **Refresh providers**. A provider
failure is isolated and includes an error/reason. Logs report startup,
provider errors, media recovery and structured `context.selected` transitions.
No secret is included in diagnostic payloads or logs.

## Development

Run all offline tests with:

```sh
python3 -m pip install -r requirements-dev.txt
python3 -m pytest -q
PYTHONPATH=cast python3 cast/cast.py --selftest
```

External HTTP is mocked in tests. Build/run behavior remains Docker Compose
with a host network and durable `/config` volume.

### Manual display selection

The arbiter owns live/kiosk navigation and freeze state under a reentrant lock.
Selection uses fresh eligible candidates; it never stores a frozen payload.
Manual selection overrides automatic pinning and dwell, while eligibility and
expiry still apply. Cast selection is separate. `/api/display-control` exposes
state and validates actions. The state is shared across live/kiosk clients and
is intentionally cleared by a process restart. Container CI runs the full
pytest suite and self-test before building or publishing.

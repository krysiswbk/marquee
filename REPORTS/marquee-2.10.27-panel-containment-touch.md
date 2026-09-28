# RESULT

Status: PASS

Marquee 2.10.27 supersedes the published but unaccepted 2.10.26 release. The
correction restores shared `.brain-panel` `overflow:hidden`, scopes the
household exception to `#brain-house`, keeps complete household content
visible, and preserves a minimum 44x44 CSS-pixel acknowledgement control.

## Repository

- Commit: `ca02ad7eb757640ac71d0275bcb379f64c8d8253`
- Branch: `main`, pushed to `origin/main` (`git@github.com:krysiswbk/marquee.git`)
- Version: `2.10.27`
- Cache-busted references: all checked references are `2.10.27`; no stale
  `2.10.26` references remain outside historical changelog content.
- Validation: `284 passed, 24 subtests passed`; Ruff clean; strict mypy clean
  (`Success: no issues found in 18 source files`); compileall clean; Node
  syntax clean for all 8 output JavaScript files; `git diff --check` clean.

## Deployment

- Runtime: PVE1 CT127, `/opt/marquee`, `http://10.10.9.37:8084`.
- Deployment fast-forwarded CT127 from `ed2e9ce` to the exact commit above.
- Only the `marquee` compose service was rebuilt and recreated.
- `/healthz` returned HTTP 200 and version `2.10.27`; compose reports the
  Marquee service `Up (healthy)`.
- Verified HTTP 200 routes/assets: `/healthz`, `/live`, `brain.css`,
  `brain.js`, `screens.css`, `weather-channel.css`, `weather-channel.js`,
  and `kiosk-menu.js`, all with the 2.10.27 cache identity where applicable.
- Rollback archive: `/opt/marquee-backups/pre-2.10.27-20260928/source.tar.gz`
  (201,428,611 bytes), created before the fast-forward and excluding
  `marquee.env`, `data/`, and `.git`.
- `marquee.env` was preserved with SHA-256
  `4b65ed206429c07c4bc739cae2c191e09011cef4a27f3cbe5f12a64c72a6495d`.
  The persistent `data/` mount remained in place; normal service startup
  refreshed provider/runtime cache files, with no deletion or replacement of
  the data directory.

## Deployed browser evidence

Playwright ran against the live URL at 393x852, 700x900, and 1500x900. Each
case had no page errors. Authoritative data, an injected 8-opening
opening-heavy state, and an injected long-device state were checked.

- 393x852: household `scrollHeight/clientHeight` was `194/194` for all three
  states. Long-device acknowledgement was visible at `166.23x44`.
- 700x900: household `scrollHeight/clientHeight` was `223/223` for all three
  states. Long-device acknowledgement was visible at `165.05x44`.
- 1500x900: household `scrollHeight/clientHeight` was `331/331` for all three
  states. Long-device acknowledgement was visible at `204.16x44`.
- All intended opening tags, long device-health names, `Offline:` copy, and
  `Got it · keep monitoring` action text were present in the injected states.
- The authoritative state rendered the live `Front door lock` content and
  `HOUSE CONNECTED` label.
- `document.scrollWidth` equaled the viewport width at every size: 393,
  700, and 1500 CSS pixels.
- Computed panel overflow remained `hidden` for `#brain-activity` and
  `#brain-agenda`; only `#brain-house` used the scoped visible overflow needed
  for rendered fitting measurement.
- Masthead and household weather remained present at every size; live weather
  temperature rendered as `16°C`.


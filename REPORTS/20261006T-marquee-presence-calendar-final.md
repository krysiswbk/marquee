# RESULT

## TARGETS

- Repository: `/home/wbk/homelab-operator/.work/marquee-candidate`
- Marquee runtime: PVE1 CT127 `/opt/marquee`, `http://10.10.9.37:8084`
- Home Assistant/AppDaemon: VM 221 on PVE2, AppDaemon add-on `app_a0d7b954_appdaemon`
- Exact receiver mapping: living room `10.10.3.73`, garage `10.10.3.74`, bedroom `10.10.3.81`

## FINDINGS

- The preserved visual-swap work was already committed at the candidate starting
  SHA and was retained. It is a structural region swap: large clock in the
  former agenda/footer region and compact up-to-five agenda in the former
  clock/header region.
- The prior changelog had the visual-swap entry under `2.12.13` while VERSION
  was `2.12.14`; this was corrected into the `2.12.14` heading.

## CHANGES

- Added authoritative AppDaemon presence routing for the three exact IPs.
- Bedroom eligibility requires `binary_sensor.bedroom_occupancy` on,
  `input_boolean.kris_is_asleep` off, `input_boolean.magda_is_asleep` off, and
  America/Toronto local time before 22:00. Sleep and cutoff are absolute vetoes.
- Added 15-second activation debounce and 30-second release grace. Startup
  stale DashCast sessions are released when ineligible; active media and
  critical attention remain protected.
- Added authenticated `/presence` bridge payload and health visibility.
- Preserved existing cadence, kiosk behavior, persistence, active-media and
  urgent-takeover arbitration.

## VALIDATION

- `pytest -q`: **387 passed, 45 subtests**.
- Ruff, Python compileall, Node syntax, and `git diff --check`: passed.
- Deployed browser geometry: `tests/browser_runtime_configuration.py` passed
  Settings, Cast layout, and Live layout at 1500x900, 1024x600, 700x900, and
  393x852 with no console/network failures or overflow.

## GIT

- Implementation SHA: `d8468853cfb4497d131f752c3488d547000335cf`.
- CT127 and `origin/main` were reconciled to the final report-bearing SHA
  after this report commit.
- Pre-existing CT127 `rollback/` remained untouched and untracked.

## RUNTIME

- CT127 predeploy archives were created with secrets, mutable data, backups,
  rollback, and `.git` excluded. Final archive was named with the prior exact
  SHA and UTC timestamp.
- HA backup: `/config/backups/marquee-presence-predeploy-20261006T142659Z.tar.gz`.
- AppDaemon was narrowly restarted; logs show `marquee_ambient` initialized
  and `Marquee Cast presence routing refreshed`.
- Current bridge snapshot: bedroom occupied=false/eligible=false,
  living occupied=false/eligible=false, garage occupied=true/eligible=true;
  current time was before the bedroom cutoff and no absolute veto was active.
- Receiver verification: 10.10.3.73 Backdrop, 10.10.3.74 DashCast,
  10.10.3.81 Backdrop. Active media/critical protection remains in code.
- `/healthz` returned 200 and version `2.12.14`; `/kiosk` returned 200.

## SURFACE VERIFY

- Kiosk and receiver HTTP connectivity passed. The primary living receiver's
  `cardAlive=false` after verification is expected because it was correctly
  released to Backdrop while living occupancy was false; it is not reported as
  a kiosk failure.

## BLOCKERS

- None.

## FOLLOW-UP

- When validating a positive bedroom case, use the real occupancy/sleep state
  transition and verify activation after debounce, then clear occupancy and
  verify release after grace. No production state was changed for this report.

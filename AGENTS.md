# Agent instructions

## Canonical source and branch

- The maintained fork is `https://github.com/krysiswbk/marquee.git` (`origin`). Do not treat `upstream` as the source for this installation.
- `main` is the canonical integration and deployment branch. GitHub Actions tests and publishes images from pushes to `main` (and version tags).
- Start work on `main`. Do not create task, Codex, or feature branches for routine work. If a session opens on another branch, first preserve its changes, then reconcile them onto `main`; do not leave finished work stranded there.
- Before editing, inspect `git status`, the current branch, and its relationship to `origin/main`. Preserve existing user changes and untracked files. Never stage unrelated files, generated artifacts, screenshots, credentials, `data/`, or deployment configuration just to make the tree look clean.
- Before pushing, confirm the task changes are the only staged changes, `origin/main` has been fetched, and the push will not discard remote commits. Integrate remote changes safely; do not force-push. Push completed work to `origin/main` and verify that the remote SHA equals the intended commit. A local commit or a push to a side branch is not completion.

## Completion means deployed and verified

- For application changes, local edits, passing tests, a commit, and a push are intermediate steps. Do not report the task complete until the exact `origin/main` commit is deployed to production and runtime verification passes.
- Production is PVE1, LXC CT 127, checkout `/opt/marquee`, served at `http://10.10.9.37:8084`. Deploy only the exact commit pushed to `origin/main`; verify the host checkout/revision before rebuilding. Preserve existing user state and rollback materials. In particular, do not overwrite `/opt/marquee/data` or `/opt/marquee/marquee.env`.
- On CT127, use the explicit Compose file `/opt/marquee/docker-compose.yml` when rebuilding/recreating Marquee. Do not substitute `/opt/marquee/compose.yaml`.
- After deployment, verify the Marquee container is healthy, `/healthz` reports the expected version/revision, and the deployed assets or API responses match the pushed source. For visual changes, inspect the affected page on the live kiosk/browser and confirm the requested behavior there; source tests alone are not deployment evidence.
- Keep a recoverable pre-deploy source/image rollback point when changing the application. Record the deployed commit, health/version result, and relevant live verification in the release notes or task summary.
- If pushing or deploying is blocked, report the exact blocker and leave the task explicitly incomplete. Never describe a local-only change as installed, deployed, or finished.
- Documentation-only changes to agent/developer instructions do not require rebuilding the application image. They must still be committed and pushed to `origin/main` so future sessions receive them.

## Verification and reporting

- Inspect project guidance, available tools, and the relevant test/build commands before changing code. Use the shared toolchain at `C:\Dev\CodexBuildTools` before concluding that a tool is unavailable.
- Run focused verification for the change and the normal project checks when practical. Report exact commands and results, including platform-specific failures; do not convert a failed or skipped check into a pass.
- Keep changes scoped to the request. Preserve unrelated local files and existing host state, and never expose secrets in logs, commits, or reports.

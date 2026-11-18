# Verification (addon and uploader)

Replaces PR #8 (without pixel baselines, AD3, and without the cross-repo deploy key, AD10). The aim: an agent proves its work from text output in one pass plus at most one fix.

## 1. Commands
| Command | What | Time today |
|---|---|---|
| `python tests/run.py` | addon under Lua 5.1 + LuaJIT with stubs; compares output with `contract/golden/` (after A2) | 0.3 s |
| `python tests/run.py --write-golden` | regenerate golden files for a **new** version (never to "fix" an old one) | – |
| `sh tests/package-check.sh` | build a zip with test config and check what ships | seconds |
| `tests/api-check.py` (A3) | every WoW API/event the addon uses exists in wowless `wowf` data | < 5 s |
| `tests/wowless/run.sh` (A4) | build the addon, run the scenarios in wowless (Docker) | target < 5 min cached |
| `cd uploader && cargo fmt --check && cargo clippy --locked -- -D warnings && cargo test --locked` | core + app | 0.8 s tests, 31 s cold build |
| `node --test uploader/app/ui/` | UI logic | 0.15 s |
| `cd uploader/app/ui/e2e && npx playwright test` (A6) | window states with a fake Tauri bridge | < 1 min |

Every command prints failures plus one summary line.

## 2. Layers
1. **Static:** `luacheck` (Lua 5.1 std + a `.luacheckrc` listing the WoW globals the addon uses, `Libs/` excluded); `tests/api-check.py` against wowless data; `cargo fmt --check`; `clippy -D warnings`; `check-no-branding.sh`.
2. **Unit and golden:** `tests/run.py` (exports, round trips, HMAC vectors, the no-guild case) and `cargo test`. Both **compare their wire output byte for byte with `contract/golden/`**; any difference fails with the file named.
3. **Contract rules** (`contract/SPEC.md` §5.2): a PR that modifies or deletes an existing file under `contract/golden/exports/` fails unless it has the `golden-break` label; new versions are new files. `contract/golden/MANIFEST.json` lists every file, the export versions, the uploader protocol version and the generating commit.
4. **In-game (wowless, AD8):** scenarios in `tests/wowless/scenarios/*.lua`, each a named test: login + roster ready (rank names captured), guild bank open with tabs and gold, profession window open (recipes saved), every slash command and its output, `/reload` (SavedVariables written then read back), no-guild character, location sharing on/off. Pass = no Lua error from addon files, plus the scenario's own assertions on SavedVariables and printed lines.
5. **HTTP contract (Rust):** the real `http.rs` client against a local mock server (`wiremock`, pinned) serving `contract/golden/uploader/*.response.json`: happy path per endpoint; 401 (reconnect), 409/422 (rejected), 413, 429 with `Retry-After`, 5xx with backoff, TLS/connection failure; OAuth authorize → consent → token and switch with state and PKCE checks. The user-visible reason codes live in one file, `contract/golden/uploader/reasons.json`, read by the Rust tests and the UI tests.
6. **Update checks:** `update.rs` and `app_update.rs` against recorded release JSON: never offer a draft, a prerelease (unless opted in) or a downgrade.
7. **Uploader UI (AD11):** Playwright (Chromium only, pinned) serves `uploader/app/ui/` with `fake-tauri.js`. One test per state: first run, connecting, connected idle, uploading, done, each reason in `reasons.json`, game not found, addon missing or outdated, update available, account switch. Each asserts `toMatchAriaSnapshot()` (YAML reviewed like code) and the layout: no scrollbars, nothing clipped at the `tauri.conf.json` window size with the longest string.
8. **Native (AD12):** Windows and macOS builds run `--smoke`; CI asserts on the JSON (window title, visible state, versions, no error). No window screenshots.
9. **Manual (AD13):** `docs/testing/in-game-checklist.md` and `docs/testing/native-checklist.md`, short numbered steps with expected results, run by the owner before a release; the release PR records client or OS version and result.

## 3. CI
`ci.yml` on `pull_request` and push to `main`, in the org's shape (`ci` repo, `AGENTS.md` and `docs/PLAN.md` §5, §7.1): `changes` (path filter) → area jobs → **`ci-ok`** → `ready`.

| Job | Runs when these change | Runner |
|---|---|---|
| `branding` | anything (secret-dependent; skips on fork PRs, runs on `main`) | ubuntu |
| `workflows` | `.github/**`, `scripts/ci/**`, `tests/workflows_check.py`, `tests/ready_test.py` | ubuntu: the workflow rules (timeouts, runners, triggers, `ci-ok` wiring) and the ready step's tests |
| `addon` | `addon/**`, `tests/**`, `contract/**`, `scripts/build-addon.sh` | ubuntu: luacheck, api-check, run.py, package-check, golden add-only rule |
| `wowless` | same as `addon` | ubuntu, Docker; wowless image built from a pinned commit and cached |
| `core` | `uploader/core/**`, `uploader/Cargo.*`, `contract/**` | ubuntu: fmt, clippy, test (incl. mock-server tests) |
| `ui` | `uploader/app/ui/**`, `contract/golden/uploader/**` | ubuntu: node --test, Playwright |
| `app` | `uploader/app/src-tauri/**`, `uploader/Cargo.*`, `uploader/core/**` | ubuntu with Tauri Linux deps: clippy, test |
| `native` | `uploader/app/**`, `uploader/core/**`, `uploader/Cargo.*`, or label `native-build` | reusable workflow: windows-2022 + macos-15, build, `launch-smoke.ps1`, `--smoke` JSON, dmg check, no signing |
| `ci-ok` | always | needs all; skipped counts as success; **the required check**. `pr-wait`, `pr-automerge` and `ready` read only it |
| `ready` | PRs from this repo, after `ci-ok` | adds `ready-for-review` (green) or `ci-failed` (red) to a non-draft PR and removes the opposite label; `ready.yml` does the same when a draft is marked ready |

- PR jobs: `permissions: contents: read` (`ready` also `issues: write`), no secrets needed. Pinned actions, Rust 1.90.0, `lupa==2.4`, luacheck version.
- **Every job has `timeout-minutes`**, at most 120 (the gates `changes`, `ci-ok` and `ready` at most 5). `tests/workflows_check.py` enforces it, as the `ci` repo's `check-workflow-timeouts` does for the private repos (a public repo's CI can't read the private `ci` repo).
- A label read by a job (`native-build`, `golden-break`) is read from the PR when the job runs, so adding it and choosing "Re-run failed jobs" is enough.
- Tag workflows (`addon-v*`, `uploader-v*`, `uploader-app-v*`) call the same jobs, then build and publish with their existing write permissions. `pull_request:` is removed from the release workflow.
- `dependabot.yml` for cargo, github-actions and pip.
- **Step summary:** one Markdown table, one row per failure (job › test › first error line). Agents read this, not logs.

### Where jobs run (AD14, 2026-11-18)
All jobs run on **GitHub-hosted runners**: Linux for everything but the native build, Windows and macOS for that. Why, and not the org's self-hosted runners (`[self-hosted, Linux, X64]`) that the site repos use:
- This repo is **public**, and GitHub doesn't meter hosted minutes for public repos, so "Actions minutes are nearly used up" doesn't apply to it.
- The org's only runner group serves **the org's private repos only** (public repos are not allowed in it). A job here asking for those labels would wait for a runner that never comes, and the org's alerting would report a runner down.
- A public repo's fork PRs must never reach the owner's machines. A fork can change the workflow file in its own PR, so a job-level `if:` guard doesn't make self-hosted safe here.
- Native Windows and macOS builds can't run on the Linux runners in any case. The cheap split: `native` runs only when uploader paths change (or the PR has `native-build`), and on tags (`uploader-app-release.yml`). A docs-only or addon-only PR never starts it.
- `tests/workflows_check.py` rule R2 keeps every job on a hosted runner, so an agent can't switch one by accident.

Moving the Linux jobs onto the org's runners later is a decision for the owner (Q7). It needs: the repo added to the runner group with "Allow public repositories" on (GitHub advises against it for public repos); `runs-on: [self-hosted, Linux, X64]` plus the fork guard `if:` on each job; and an answer for the `app` job, because those runners run as user `ci` with no sudo, no Rust and none of the Tauri system libraries (a container image, or libraries installed on every runner host). Then R2 and `ci.yml` change together.

## 4. Agent rules (copied into `AGENTS.md` by A0.2)
- Run the commands for the area you touched before asking for review; read the CI summary, not logs.
- After every push, run `../ci/tools/pr-wait <repo> <pr>` as a background command, and fix a red `ci-ok` yourself. Never sleep-poll or watch runs in a loop (`ci/AGENTS.md`, "Waiting for CI").
- Wire-format changes follow `contract/SPEC.md` §5.2: new version, new golden files, never edit an old one, link the matching site PR.
- Never claim in-game or native behaviour was verified unless wowless/the smoke JSON or the checklist shows it. Write "not verified in game" plainly otherwise.
- Never claim CI passed without the run link for the head SHA. Never skip, disable or loosen a test, and never mark the wowless job non-blocking, to get green.
- Never touch `scripts/uploader-sign-release.sh`, release workflows or permissions in a feature PR.
- Never update ARIA snapshots without explaining each changed line.
- Keep `check-no-branding.sh` green; neutral names only; the test secret only.
- One task from `06-plan.md` per PR; follow the PR template.

## 5. PR template (`.github/pull_request_template.md`)
The org's shape, as in the site repos: a first line, `## Summary` (two or three plain sentences), `## Check it yourself` (what to do → what you should see, each item verified by the agent first, with direct links), then a folded **Agent notes** block. This repo's own fields live in the Agent notes: task id, area, requirements → tests, wire-format changes with the site PR link, what was not verified (in game, natively), exceptions, rollback, follow-ups. The first line is `**Preview:** n/a: …` because this repo has no previews and the owner merges every PR: `none` would let the shared `pr-automerge` merge it (AGENTS.md rule 12, Q8). The file itself is added by A0.2.

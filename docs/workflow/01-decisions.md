# Decisions (addon and uploader)

The owner made these on 2026-11-13. Decisions shared with the site repo are summarised here (the site's `docs/workflow/01-decisions.md` has the long form, numbered D1–D16). Change one with a new entry, not a silent edit.

## Shared with the site
- **AD1 (D1) Workflow fix, no rewrite.** Keep the code; add CI, the contract, text-based checks and agent rules.
- **AD2 (D2) The contract lives here.** `contract/SPEC.md` and `contract/golden/` are the single source of the wire format. This repo is public, so the site's CI fetches the golden files with no secret. Golden files are add-only: a changed encoding is a new `v<n+1>` file; the previous version stays until the site has dropped it.
- **AD3 (D3) No pixel tests.** No `toHaveScreenshot`, baselines or full-page shots. PR #8 Part 4.4 is dropped. Screenshots only on request, one element, for a human.
- **AD4 (D11) Guildmates install the addon and the uploader.** Both stay.
- **AD5 (D12, D13) Spec-first; CI is the only judge.** First commit holds failing requirement tests; agents read the step summary; no "tests pass" without a CI link; merging is human.
- **AD6 (D14) Agents.** `AGENTS.md` is the rule source, `CLAUDE.md` imports it. Only Claude Code until 2026-11-17 13:00; then Grok Bot dispatches self-contained tasks to Claude Code via T3 Code.
- **AD7 (D15) Public-repo hygiene.** Neutral fixture names ("Example Guild", "Testchar"), the test secret `"11" * 32` only, no hostnames.

## This repo
### AD8. wowless is the main in-game harness
- **Decision:** run the built addon inside [wowless](https://github.com/wowless/wowless), product `wowf` (WoW Forever, interface 16001), in CI on every addon PR. Scenario scripts fire the events the addon uses, run its slash commands, and reload SavedVariables. A Lua error raised from the addon's files fails the job.
- **Why:** WoW Forever runs the retail Lua API, and wowless already tracks this exact client build (data updated 2026-11-11). It tests what our stubs can't: the real FrameXML, real API signatures and event wiring.
- **Risks accepted:** wowless is pre-alpha. Pin a wowless commit; bump it on purpose in its own PR. An error whose stack is entirely inside wowless is reported as a wowless issue (job annotation), not an addon failure.
- **Kept alongside:** `tests/run.py` stays as the fast unit layer and the golden-fixture generator (deterministic, 0.3 s, Lua 5.1 + LuaJIT). A static check (A3) compares every WoW API and event the addon uses with wowless's `data/products/wowf/{apis,events,globals}.yaml`.
- **Fallback:** if A4 cannot get the addon to load in wowless within its timebox, the job is marked non-blocking, the reasons are recorded in `07-open-questions.md`, and the static check plus `run.py` scenarios carry the load until a wowless bump fixes it.

### AD9. CI on every PR, cheap by default
- **Decision:** one `ci.yml` with path-filtered jobs (`branding`, `addon`, `wowless`, `core`, `ui`, `app`, `native`) and a final `ci-ok` that treats skipped as success; `ci-ok` is the required check. The Windows + macOS Tauri build runs only when uploader paths change or the PR has the `native-build` label. PR jobs get `contents: read`; only tag jobs keep write, `id-token` and attestation permissions. Release workflows call the same jobs instead of keeping copies.

### AD10. The site pulls the contract; this repo doesn't need the site
- **Decision:** this repo's CI proves its own output matches `contract/golden/` (drift fails) and that old golden files are never edited. The site's CI fetches the golden files and proves it can read them (site P5.1, weekly run). PR #8's cross-repo job with a deploy key is dropped: no secret is needed in either direction.
- **When the wire format changes:** the addon PR adds the new golden files and links a matching site PR. The site must accept a new version before an addon release that produces it.

### AD11. Uploader UI: browser tests with a fake Tauri bridge, text only
- **Decision:** the window UI (`uploader/app/ui/`) is tested in Chromium with a scripted fake `__TAURI__`, one test per state, asserting ARIA snapshots and layout (no scrollbars or clipped text at the window size from `tauri.conf.json`). No baselines.

### AD12. Native evidence by `--smoke` JSON
- **Decision:** the built app on Windows and macOS CI starts with `--smoke`, writes its visible state (text, buttons, versions) as JSON and exits. CI asserts on the JSON. What still can't be automated (tray, autostart, installer, Gatekeeper) is a short checklist run by the owner before an uploader release.

### AD13. Manual in-game checks only for what wowless can't reach
- **Decision:** before tagging an addon release, the owner runs a short checklist in the real client for the things no emulator sees: a real guild bank open, real guild roster and rank names, addon-to-addon comms between two players, and the uploader picking up a real SavedVariables file. Result recorded in the release PR. Feature PRs rely on CI.

### AD14. CI follows the org's conventions; hosted runners here (2026-11-18)
- **Decision:** the repo moved into the guild's GitHub organization and its CI follows the org's shared conventions (the shared `ci` repo): the one check `ci-ok`; the `ready` step (`ready-for-review` and `ci-failed` labels, `ready.yml`); `timeout-minutes` on every job; agents run `ci/tools/pr-wait` in the background after every push and fix red CI themselves. Jobs stay on **GitHub-hosted runners**, because the repo is public (no metered minutes), the org's runner group doesn't serve it, and fork PRs must not reach the owner's machines. Native Windows and macOS builds run only when uploader paths change, on the `native-build` label, and on tags. Details and the way to move: `05-verification.md` §3.
- **Supersedes:** AD9's runner and job list where they differ. Everything else in AD9 stands.
- **Needs the owner (Q7, Q8):** whether to open the org's runners to this public repo (the default is no), and installing the org's CI bot (a GitHub App) on this repo, which today covers only the org's private repos.

### AD15. Link v2: two hand-offs instead of three (2026-11-21)
- **Decision (owner's request):** the site shows `/<cmd> link <26-character code>`; the addon derives the character's secret from the code with HKDF-SHA256 bound to the GUID and an addon nonce, keeps it, and shows a `!BF:link:v2:` string signed with it; the site re-derives the secret and stores it. No `link-ok` import. Exact rules, site steps and the threat comparison: `contract/SPEC.md` §3.3.
- **Why HKDF-SHA256:** the addon already ships SHA-256 and HMAC in pure Lua, HKDF is two HMAC calls on top, and Node has `crypto.hkdfSync`, so both sides use a standard function with no new code to trust.
- **State rule:** the newest link wins at once (no pending slot); the same code again reuses its nonce. Trade-off: an abandoned relink of a linked character makes its uploads fail until the next link. The owner accepts or changes this in the PR.
- **Compatibility:** v1 (8-character code and `link-ok` import) stays on both sides during the transition; linked characters keep their secrets. The addon ships first; the site accepts `link` v2 before it shows 26-character codes. The uploader takes no part in linking.

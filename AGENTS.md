# Agent rules (addon and uploader)

> **Workspace map and shared rules:** `../ci/AGENTS.md` (the shared `ci` repo, cloned next to this one in the `~/websites` workspace).
> CI, PR plumbing, merging and timeouts follow it. Where it disagrees with this file, this file wins for this repo's code, its
> public-repo hygiene and its runners (rules 13 and 14).

The single source of rules for every agent working in this repo. `CLAUDE.md` imports this file.
Spec and plan: `docs/workflow/`. Wire format: `contract/SPEC.md`. If these disagree with older notes, they win.

**This repo is public.** Never add guild, character, domain, owner or machine names, secrets or production URLs.
Use neutral names ("Example Guild", "Testchar", `https://guild.example`) and only the test secret `"11" * 32`.

## Repo map
| Path | What |
|---|---|
| `addon/` | In-game addon (Lua 5.1). `Codec.lua` = export strings, `Core.lua` = commands and imports, `Bank.lua`, `Recipes.lua`, `Guild.lua`, `Comms.lua`. `Libs/` is vendored; don't edit. |
| `addon/Addon.toc.template`, `scripts/build-addon.sh` | Build config comes from repo variables (`ADDON_NAME`, `ADDON_SLASH`, …), never hard-coded. |
| `tests/run.py` | Loads the addon under Lua 5.1 and LuaJIT (lupa) with WoW API stubs and a fixed clock. |
| `tests/package-check.sh` | Builds a zip with test config and checks what ships. |
| `uploader/core/` | Rust crate `guild-uploader-core`: envelope, HTTP, OAuth sign-in, ranks, logs, updates, game detection. |
| `uploader/app/src-tauri/` | Rust crate `guild-uploader-app` (Tauri desktop app, updater binary). |
| `uploader/app/ui/` | Plain HTML/JS window UI, tested with `node --test`. |
| `contract/` | `SPEC.md` (the wire format) and, after A2, `golden/` fixtures. |
| `.github/workflows/` | `ci.yml` (PRs and `main`: path-filtered jobs, `ci-ok`, `ready`), `ready.yml`, reusable `addon-checks.yml` and `uploader-app-build.yml`, and the release workflows (tags). |
| `scripts/ci/ready.py`, `tests/workflows_check.py` | The ready step (labels a PR from its `ci-ok`) and the rules every workflow must follow (rule 14). |

## Commands
Run the ones for the area you touched. Each prints failures and a summary line.
```sh
python3 -m venv v && v/bin/pip install lupa==2.4 pillow==11.0.0   # once
v/bin/python tests/run.py                                       # addon, Lua 5.1 + LuaJIT (< 1 s)
PATH=$PWD/v/bin:$PATH sh tests/package-check.sh                 # addon packaging
(cd uploader && cargo test -p guild-uploader-core --locked)     # core (~1 s after the first build)
(cd uploader && cargo test -p guild-uploader-app --locked)      # app (needs Tauri system libs on Linux)
(cd uploader/app/ui && node --test)                             # window UI logic
BRANDING_WORDS=... scripts/check-no-branding.sh                 # CI runs it with a repo secret
python3 tests/workflows_check.py && python3 tests/ready_test.py # workflow rules, ready step (needs PyYAML)
../ci/tools/pr-wait <repo> <pr>                                 # after every push, in the background (rule 3)
```
Planned (see `docs/workflow/06-plan.md`; use them once they exist): luacheck, `cargo fmt --check`, clippy (A1.2),
`tests/run.py --write-golden` (A2), `tests/api-check.py` (A3), `tests/wowless/run.sh` (A4), uploader UI Playwright (A6).

## Rules
1. **One task per PR.** Take it from `docs/workflow/06-plan.md` by ID (A1.1, A2, …). Follow `.github/pull_request_template.md`.
2. **Spec-first.** The first commit holds the failing requirement tests, titled `R<n>: <requirement>`. Implement until green.
   Never loosen an approved assertion without the owner's OK written in the PR body.
3. **CI is the only judge.** Never claim "tests pass" without the CI run link for the head SHA. Read the `ci-ok` job log and
   step summary, not raw logs. Never skip, disable or loosen a test, and never make a blocking job non-blocking, to get green.
   **After every push run `../ci/tools/pr-wait <repo> <pr>` as a background command** (`<repo>` is this folder's name); it wakes
   you when `ci-ok` concludes. Fix a red `ci-ok` yourself. Never sleep-poll or run `gh run watch`. One push per review round:
   finish the code, the tests and any rebase first.
4. **Wire format** (`contract/SPEC.md` §5.2): a changed encoding is a new version `v<n+1>` with new golden files.
   Never edit an existing golden file. Link the matching site PR when the site must change, and the site must accept
   a new version before an addon release produces it.
5. **No pixel tests.** No `toHaveScreenshot`, baseline images or full-page screenshots. UI is proven by ARIA snapshots
   and layout assertions. Screenshots only when a human asks, one element at a time.
6. **Never update ARIA snapshots** without explaining each changed line in the PR body.
7. **Say what was not verified.** In-game and native behaviour count as verified only through wowless, the `--smoke`
   JSON or the release checklists. Otherwise write "not verified in game" or "not verified natively".
8. **Don't touch release machinery in a feature PR:** `scripts/uploader-sign-release.sh`, release workflows, workflow
   permissions, signing keys.
9. **Pin tools:** action versions, Rust 1.90.0, `lupa==2.4`, and any new dev dependency.
10. **Keep `scripts/check-no-branding.sh` green.**
11. Commit messages say what changed and why, in plain words. No model names, in commits or in PR text.
12. **Merging is the owner's.** Never merge, never push to `main`, never change repository settings. The shared `pr-automerge`
    isn't used here: the PR's first line is `**Preview:** n/a: …`, never `none`, so it can't pick the PR up (Q8).
13. **Act as the CI bot** for pushes, PRs, comments and labels (`../ci/AGENTS.md`, "Pull requests") once it is installed on this
    repo. Today it isn't (Q8): use the clone's own `gh` login, and say so in the PR. The PR template is `.github/pull_request_template.md`.
    `ready-for-review` and `ci-failed` come from the `ready` job; never set them by hand. Report a PR ready only with its `ci-ok` run link.
14. **Runners and workflows.** CI runs on GitHub-hosted runners: this repo is public, so no `self-hosted` label, no
    `pull_request_target`, and no `pull_request` trigger in a release workflow (`tests/workflows_check.py` fails on each). Every job
    has `timeout-minutes` (at most 120; `changes`, `ci-ok` and `ready` at most 5). Native Windows and macOS builds run only when
    uploader paths change, with the `native-build` label, or on tags; a label read by a job is read when the job runs, so add it
    and re-run the failed jobs. Reasons and the way to move to the org's runners: `docs/workflow/05-verification.md` §3 (AD14, Q7).

## Escalate to the owner instead of guessing
Anything in `docs/workflow/07-open-questions.md` that your task depends on and has no default; a test that seems wrong;
a change that needs a secret, a repo setting, a runner, the org's CI bot, or a release.

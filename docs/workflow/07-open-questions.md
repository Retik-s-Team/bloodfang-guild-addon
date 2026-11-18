# Open questions (addon and uploader)

Each has a default. If unanswered when a task needs it, the agent uses the default and says so in the PR body.

| # | Question | Needed by | Default |
|---|---|---|---|
| Q1 | `signups` (site → addon) is produced by the site but refused by the addon; `signup`, `attendance` and `kills` are accepted by the site but produced by no part (SPEC §6 gaps 4–5). Build them in the addon, or remove them from the site? | A2.1 | Keep the site readers, add golden files only for what exists today; decide per type in a feature task. |
| Q2 | Import signatures (SPEC §6 gap 3): the addon doesn't verify Ed25519 on `link-ok` (deferred on 2026-11-04). Do it now? | A9 | After A4, so the change is tested in wowless too. |
| Q3 | Rank-name length: 160 bytes in the addon and uploader, 40 characters in the site's envelope path, 32 on `/api/uploader/ranks`. Which limit wins? | A2.1 | 32 characters everywhere, checked on both sides, matching what the in-game rank editor allows (agent confirms in wowless data). |
| Q4 | `/api/uploader/ranks` accepts an unsigned rank block while the signed `ranks` export also exists (SPEC §6 gap 9). Keep both paths? | A2.1 | Keep (it needs an uploader token), but cover both with golden fixtures and one shared validator on the site. |
| Q5 | Should the wowless Docker image be published to the repo's container registry (faster CI) or built and cached per run? | A4 | Cache per run with `actions/cache`; publish only if cold builds exceed 10 minutes. |
| Q6 | `/api/uploader/latest` exists on the site but the uploader never calls it. Remove it or use it? | A2.1 | Keep, documented as unused; remove in a later site cleanup if still unused after the next uploader release. |
| Q7 | Run this repo's Linux CI on the org's self-hosted runners (`[self-hosted, Linux, X64]`) like the site repos? It needs the repo in the org runner group with public repos allowed, which exposes the owner's machines to a public repo's workflow code. See `05-verification.md` §3. | any time | No. Stay on GitHub-hosted runners, which are free for a public repo (AD14). |
| Q8 | Install the org's CI bot (a GitHub App) on this repo? Today it covers only the org's private repos. Without it agents push as the clone's own `gh` login, new PRs are opened under the owner's account, and the shared `pr-automerge` tool can't merge here. | any time | Not installed. The owner merges every PR by hand, as AGENTS.md says. |

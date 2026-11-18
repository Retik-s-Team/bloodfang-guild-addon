#!/usr/bin/env python3
"""Rules for this repo's GitHub Actions workflows. Needs PyYAML (CI installs it pinned): `python3 tests/workflows_check.py`.

The ci repo's check-workflow-timeouts can't be called from here (the ci repo is private), so this repo carries the same rule
and the ones that follow from where it runs. Each rule prints one line per problem; the exit status is 1 when any broke.
  R1 every job has timeout-minutes, 1 to 120; the gate jobs (changes, ci-ok, ready) at most 5 (ci AGENTS.md "Timeouts").
  R2 every job runs on a GitHub-hosted runner. This repo is public: the org's self-hosted runners don't serve it (their
     runner group lists only private repos), and a fork PR's code must never reach them. Moving to them is a decision
     for the owner (docs/workflow/05-verification.md section 3); then this rule and ci.yml change together.
  R3 only ci.yml and ready.yml run on pull requests, and no workflow uses pull_request_target: the release workflows
     keep write, id-token and attestation permissions, so they must never run PR code.
  R4 ci-ok needs every other ci.yml job except `ready`, and `ready` needs ci-ok and skips fork PRs.
  R5 the ready jobs can write labels on a PR: `pull-requests: write` and `issues: write`. (With `issues: write` alone the
     labels API answers 403 on a pull request; seen on this repo's first run, 2026-11-18.)
"""
import pathlib
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"
HOSTED = {"ubuntu-24.04", "windows-2022", "macos-14", "macos-15"}
GATES = {"changes", "ci-ok", "ready"}
PR_WORKFLOWS = {"ci.yml", "ready.yml"}
FORK_GUARD = "github.event.pull_request.head.repo.full_name == github.repository"


def triggers(doc):
    on = doc.get("on", doc.get(True))  # YAML 1.1 reads a bare `on:` key as True
    if isinstance(on, str):
        return {on}
    return set(on) if on else set()


def runners(job):
    """The runner names a job can get: its runs-on, or every os of the matrix it reads."""
    on = job.get("runs-on")
    names = [on] if isinstance(on, str) else list(on or [])
    out = []
    for n in names:
        if isinstance(n, str) and n.strip().startswith("${{ matrix."):
            key = n.strip()[len("${{ matrix."):].split("}}")[0].strip()
            out += [m[key] for m in (job.get("strategy") or {}).get("matrix", {}).get("include", []) if key in m]
        else:
            out.append(n)
    return out


def label_permission_problems(name, job):
    perms = job.get("permissions") or {}
    return [f"R5 {name} > ready: `{k}: write` is missing from its permissions" for k in ("pull-requests", "issues") if perms.get(k) != "write"]


def check(workflows_dir=WORKFLOWS):
    problems = []
    docs = {}
    for f in sorted(workflows_dir.glob("*.y*ml")):
        try:
            docs[f.name] = yaml.safe_load(f.read_text()) or {}
        except yaml.YAMLError as e:
            problems.append(f"{f.name}: not valid YAML ({type(e).__name__})")
    for name, doc in docs.items():
        on = triggers(doc)
        if "pull_request_target" in on:
            problems.append(f"R3 {name}: pull_request_target runs with write access on a fork's PR")
        if "pull_request" in on and name not in PR_WORKFLOWS:
            problems.append(f"R3 {name}: runs on pull requests but is neither ci.yml nor ready.yml")
        for job_id, job in (doc.get("jobs") or {}).items():
            if "uses" in job:  # a reusable workflow's own jobs are checked in its own file
                continue
            t = job.get("timeout-minutes")
            cap = 5 if job_id in GATES else 120
            if isinstance(t, str) and t.strip().startswith("${{"):
                pass
            elif not isinstance(t, int) or isinstance(t, bool) or not 1 <= t <= cap:
                problems.append(f"R1 {name} > {job_id}: timeout-minutes is {t!r}, must be a whole number from 1 to {cap}")
            bad = [r for r in runners(job) if r not in HOSTED]
            if bad or not runners(job):
                problems.append(f"R2 {name} > {job_id}: runs on {job.get('runs-on')!r}; only GitHub-hosted runners {sorted(HOSTED)} are allowed here")
    ci = docs.get("ci.yml")
    if ci:
        jobs = ci.get("jobs") or {}
        needs = jobs.get("ci-ok", {}).get("needs") or []
        needs = [needs] if isinstance(needs, str) else needs
        missing = sorted(set(jobs) - set(needs) - {"ci-ok", "ready"})
        if "ci-ok" not in jobs:
            problems.append("R4 ci.yml: no ci-ok job")
        elif missing:
            problems.append(f"R4 ci.yml: ci-ok doesn't wait for {', '.join(missing)}")
        r = jobs.get("ready", {})
        if r.get("needs") != "ci-ok" or FORK_GUARD not in str(r.get("if", "")):
            problems.append("R4 ci.yml: `ready` must need ci-ok and skip fork PRs")
        problems += label_permission_problems("ci.yml", r)
    ry = docs.get("ready.yml")
    if ry and FORK_GUARD not in str(ry.get("jobs", {}).get("ready", {}).get("if", "")):
        problems.append("R4 ready.yml: its job must skip fork PRs")
    if ry:
        problems += label_permission_problems("ready.yml", ry.get("jobs", {}).get("ready", {}))
    return problems


if __name__ == "__main__":
    found = check()
    for p in found:
        print(p)
    print(f"workflows check: {len(list(WORKFLOWS.glob('*.y*ml')))} workflow files, {len(found)} problem(s)")
    sys.exit(1 if found else 0)

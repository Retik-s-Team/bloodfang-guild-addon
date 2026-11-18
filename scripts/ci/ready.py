#!/usr/bin/env python3
"""The `ready` step: once a pull request's head commit has its `ci-ok` verdict, say so on the PR with a label.

    GITHUB_REPOSITORY=<owner/name> python3 scripts/ci/ready.py <40-character head sha>

Runs at the end of ci.yml (after ci-ok; CI_OK_RESULT then carries that job's result) and from ready.yml when a draft is
marked ready (then the verdict is read from the ci-ok check run). Uses `gh api` with GH_TOKEN, the job's GITHUB_TOKEN.
  - Only an open, non-draft, same-repo PR whose current head is <sha>; anything else does nothing.
  - Green (ci-ok succeeded): adds ready-for-review, removes ci-failed and ci-running.
    Red (failed, cancelled, timed out): adds ci-failed, removes ready-for-review. Anything else: no label change.
  - A GitHub API error only warns. This step must never turn CI red: exit 0, and exit 2 only for a bad argument.
The same behaviour as the site repo's scripts/ci/ready.mjs (ci docs/PLAN.md 7.1), without the preview half: this repo
has no previews. Labels set with GITHUB_TOKEN start no workflows, so this can't loop.
"""
import json
import os
import re
import subprocess
import sys

READY, FAILED, RUNNING = "ready-for-review", "ci-failed", "ci-running"
RED = {"failure", "cancelled", "timed_out", "startup_failure"}


class ApiError(Exception):
    def __init__(self, message, status=0):
        super().__init__(message)
        self.status = status


def gh(path, method="GET", payload=None):
    """One `gh api` call: the JSON answer, or an ApiError with the HTTP status. Only gh's first error line is kept."""
    cmd = ["gh", "api", "-X", method, path]
    if payload is not None:
        cmd += ["--input", "-"]
    where = f"{method} {path.split('?')[0]}"
    try:
        r = subprocess.run(cmd, input=json.dumps(payload) if payload is not None else "", capture_output=True,
                           text=True, timeout=60, check=True)
    except subprocess.CalledProcessError as e:
        first = (e.stderr or "").strip().split("\n")[0][:200]
        m = re.search(r"HTTP (\d{3})", first)
        raise ApiError(f"{where}: {first}", int(m.group(1)) if m else 0) from None
    except (OSError, subprocess.TimeoutExpired) as e:
        raise ApiError(f"{where}: {type(e).__name__}") from None
    return json.loads(r.stdout) if r.stdout.strip() else None


def classify(conclusion):
    """A check conclusion or a job result: green, red or pending."""
    return "green" if conclusion == "success" else "red" if conclusion in RED else "pending"


def ci_ok_from_checks(repo, sha, call=gh):
    """(what it said, verdict) from the newest `ci-ok` check run of <sha>."""
    r = call(f"repos/{repo}/commits/{sha}/check-runs?check_name=ci-ok&filter=latest&per_page=100")
    runs = sorted((r or {}).get("check_runs") or [], key=lambda c: str(c.get("started_at")), reverse=True)
    if not runs:
        return "ci-ok missing", "pending"
    if runs[0].get("status") != "completed":
        return f"ci-ok {runs[0].get('status')}", "pending"
    return f"ci-ok {runs[0].get('conclusion')}", classify(runs[0].get("conclusion"))


def label_plan(verdict, have):
    """(labels to add, labels to remove) for a verdict, given the PR's labels."""
    add, remove = {"green": ([READY], [FAILED, RUNNING]), "red": ([FAILED], [READY])}.get(verdict, ([], []))
    return [x for x in add if x not in have], [x for x in remove if x in have]


def apply_labels(repo, pr, verdict, call=gh):
    add, remove = label_plan(verdict, {x["name"] for x in pr.get("labels") or []})
    if add:
        call(f"repos/{repo}/issues/{pr['number']}/labels", "POST", {"labels": add})
    for name in remove:
        try:
            call(f"repos/{repo}/issues/{pr['number']}/labels/{name}", "DELETE")
        except ApiError as e:
            if e.status != 404:  # already gone
                raise
    return " ".join([f"+{x}" for x in add] + [f"-{x}" for x in remove]) or "no change"


def run(sha, repo, ci_ok_result="", call=gh, log=print):
    """Do the step for <sha>. Never raises for an API error: it warns."""
    short = sha[:7]
    try:
        found = call(f"repos/{repo}/commits/{sha}/pulls?per_page=100") or []
        open_pr = next((p for p in found if p.get("state") == "open" and (p.get("head") or {}).get("sha") == sha
                        and ((p.get("head") or {}).get("repo") or {}).get("full_name") == repo), None)
        if not open_pr:
            return log(f"ready: no open pull request of this repo has {short} as its head: nothing to do")
        pr = call(f"repos/{repo}/pulls/{open_pr['number']}")  # fresh: draft and head may have changed since
    except ApiError as e:
        return log(f"::warning title=ready step::couldn't find the pull request for {short} ({e}); labels unchanged")
    at = f"PR #{pr['number']}"
    if pr.get("state") != "open":
        return log(f"ready: {at} is {pr.get('state')}: nothing to do")
    if pr.get("draft"):
        return log(f"ready: {at} is a draft: nothing to do")
    if (pr.get("head") or {}).get("sha") != sha:
        return log(f"ready: {at} has moved on to {str((pr.get('head') or {}).get('sha'))[:7]}; this run is for {short}: nothing to do")
    try:
        said, verdict = (f"ci-ok {ci_ok_result}", classify(ci_ok_result)) if ci_ok_result else ci_ok_from_checks(repo, sha, call)
        log(f"ready: {at} at {short}: {said} -> {verdict}; labels: {apply_labels(repo, pr, verdict, call)}")
    except ApiError as e:
        log(f"::warning title=ready step::{at}: labels unchanged ({e})")


def main(argv, env):
    sha = argv[1] if len(argv) > 1 else ""
    repo = env.get("GITHUB_REPOSITORY", "")
    if not re.fullmatch(r"[0-9a-f]{40}", sha) or not re.fullmatch(r"[\w.-]+/[\w.-]+", repo):
        print("usage: GITHUB_REPOSITORY=<owner/name> python3 scripts/ci/ready.py <40-character head sha>", file=sys.stderr)
        return 2
    try:
        run(sha, repo, env.get("CI_OK_RESULT", ""))
    except Exception as e:  # never turn CI red
        print(f"::warning title=ready step::unexpected error, nothing more done ({type(e).__name__})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv, os.environ))

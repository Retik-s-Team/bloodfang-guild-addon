#!/usr/bin/env python3
"""Tests for scripts/ci/ready.py, the ready step. Standard library only: `python3 tests/ready_test.py`.

Each test fakes the GitHub API with a list of (method, path, payload) calls, so nothing here talks to GitHub.
"""
import contextlib
import importlib.util
import io
import pathlib
import unittest

spec = importlib.util.spec_from_file_location("ready", pathlib.Path(__file__).resolve().parent.parent / "scripts/ci/ready.py")
ready = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ready)

REPO = "org/addon"
SHA = "a" * 40


class FakeApi:
    """Answers the calls ready.py makes. `pr` is the pull request object; `checks` the ci-ok check runs."""

    def __init__(self, pr=None, checks=None, fail_on=None, delete_status=None, fresh=None):
        self.pr, self.checks, self.fail_on, self.delete_status = pr, checks or [], fail_on, delete_status
        self.fresh = fresh or pr  # what reading the PR again says; the commit lookup lists `pr`
        self.calls = []

    def __call__(self, path, method="GET", payload=None):
        self.calls.append((method, path, payload))
        if self.fail_on and self.fail_on in path:
            raise ready.ApiError(f"{method} {path}: HTTP 500")
        if method == "DELETE" and self.delete_status:
            raise ready.ApiError("gone", self.delete_status)
        if "/commits/" in path and path.endswith("/pulls?per_page=100"):
            return [self.pr] if self.pr else []
        if "/check-runs" in path:
            return {"check_runs": self.checks}
        if "/pulls/" in path:
            return self.fresh
        return None

    def writes(self):
        return [(m, p.rsplit("/", 1)[-1] if m == "DELETE" else p.split("/issues/")[-1], pl) for m, p, pl in self.calls if m != "GET"]


def pr(number=7, state="open", draft=False, head=SHA, labels=(), head_repo=REPO):
    return {"number": number, "state": state, "draft": draft, "labels": [{"name": n} for n in labels],
            "head": {"sha": head, "repo": {"full_name": head_repo}}}


def run(api, result=""):
    out = []
    ready.run(SHA, REPO, result, call=api, log=out.append)
    return "\n".join(out)


class Verdicts(unittest.TestCase):
    def test_classify(self):
        self.assertEqual(ready.classify("success"), "green")
        for c in ("failure", "cancelled", "timed_out", "startup_failure"):
            self.assertEqual(ready.classify(c), "red", c)
        for c in ("skipped", "neutral", None, "", "in_progress"):
            self.assertEqual(ready.classify(c), "pending", c)

    def test_label_plan(self):
        self.assertEqual(ready.label_plan("green", set()), ([ready.READY], []))
        self.assertEqual(ready.label_plan("green", {ready.FAILED, ready.RUNNING}), ([ready.READY], [ready.FAILED, ready.RUNNING]))
        self.assertEqual(ready.label_plan("green", {ready.READY}), ([], []))
        self.assertEqual(ready.label_plan("red", {ready.READY}), ([ready.FAILED], [ready.READY]))
        self.assertEqual(ready.label_plan("red", {ready.FAILED}), ([], []))
        self.assertEqual(ready.label_plan("pending", {ready.READY, ready.FAILED}), ([], []))

    def test_newest_check_run_decides(self):
        old = {"status": "completed", "conclusion": "failure", "started_at": "2026-11-18T10:00:00Z"}
        new = {"status": "completed", "conclusion": "success", "started_at": "2026-11-18T10:05:00Z"}
        self.assertEqual(ready.ci_ok_from_checks(REPO, SHA, FakeApi(checks=[old, new]))[1], "green")
        running = {"status": "in_progress", "conclusion": None, "started_at": "2026-11-18T10:06:00Z"}
        self.assertEqual(ready.ci_ok_from_checks(REPO, SHA, FakeApi(checks=[old, new, running])), ("ci-ok in_progress", "pending"))
        self.assertEqual(ready.ci_ok_from_checks(REPO, SHA, FakeApi(checks=[])), ("ci-ok missing", "pending"))


class Step(unittest.TestCase):
    def test_green_from_the_jobs_own_result(self):
        api = FakeApi(pr(labels=[ready.FAILED, ready.RUNNING]))
        run(api, "success")
        self.assertEqual(api.writes(), [("POST", "7/labels", {"labels": [ready.READY]}), ("DELETE", ready.FAILED, None), ("DELETE", ready.RUNNING, None)])
        self.assertFalse([c for c in api.calls if "check-runs" in c[1]], "an explicit result needs no check-run lookup")

    def test_red_from_the_jobs_own_result(self):
        for result in ("failure", "cancelled"):
            api = FakeApi(pr(labels=[ready.READY]))
            run(api, result)
            self.assertEqual(api.writes(), [("POST", "7/labels", {"labels": [ready.FAILED]}), ("DELETE", ready.READY, None)], result)

    def test_skipped_result_changes_nothing(self):
        api = FakeApi(pr(labels=[ready.READY]))
        run(api, "skipped")
        self.assertEqual(api.writes(), [])

    def test_ready_for_review_event_reads_the_check_run(self):
        done = {"status": "completed", "conclusion": "success", "started_at": "2026-11-18T10:00:00Z"}
        api = FakeApi(pr(), checks=[done])
        self.assertIn("ci-ok success -> green", run(api))
        self.assertEqual(api.writes(), [("POST", "7/labels", {"labels": [ready.READY]})])

    def test_ci_still_running_changes_nothing(self):
        api = FakeApi(pr(labels=[ready.READY]), checks=[{"status": "in_progress", "started_at": "2026-11-18T10:00:00Z"}])
        run(api)
        self.assertEqual(api.writes(), [])

    def test_drafts_closed_prs_and_moved_heads_do_nothing(self):
        for fresh, why in ((pr(draft=True), "draft"), (pr(state="closed"), "closed"), (pr(head="b" * 40), "moved on")):
            api = FakeApi(pr(), fresh=fresh)  # listed as open at SHA; the fresh read says otherwise
            self.assertIn(why, run(api, "success"))
            self.assertEqual(api.writes(), [], why)

    def test_no_open_pr_for_the_commit(self):
        api = FakeApi(None)
        self.assertIn("nothing to do", run(api, "success"))
        self.assertEqual(api.writes(), [])

    def test_a_fork_pr_is_ignored(self):
        api = FakeApi(pr(head_repo="someone/addon"))
        self.assertIn("nothing to do", run(api, "success"))
        self.assertEqual(api.writes(), [])

    def test_an_api_error_warns_and_never_raises(self):
        for where in ("check-runs", "/labels", "/commits/"):
            api = FakeApi(pr(), checks=[{"status": "completed", "conclusion": "success", "started_at": "x"}], fail_on=where)
            out = run(api, "" if where == "check-runs" else "success")
            self.assertIn("::warning", out, where)

    def test_a_label_that_is_already_gone_is_fine(self):
        api = FakeApi(pr(labels=[ready.FAILED]), delete_status=404)
        self.assertNotIn("::warning", run(api, "success"))

    def test_bad_arguments(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(ready.main(["ready.py", "nothex"], {"GITHUB_REPOSITORY": REPO}), 2)
            self.assertEqual(ready.main(["ready.py", SHA], {}), 2)


if __name__ == "__main__":
    unittest.main(verbosity=1)

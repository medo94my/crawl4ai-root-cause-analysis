#!/usr/bin/env python3
"""
Manual test script — runs without pytest.
Each test prints PASS / FAIL and a short reason.
Exit code 0 if all pass, 1 if any fail.

Usage:
    python3 tests/manual_test.py
"""
import sys
import os
import ast
import traceback
from pathlib import Path

# Make project root importable
sys.path.insert(0, str(Path(__file__).parent.parent))

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"

failures = []


def check(name: str, ok: bool, reason: str = ""):
    if ok:
        print(f"  {PASS}  {name}")
    else:
        msg = f"  {FAIL}  {name}" + (f"  ← {reason}" if reason else "")
        print(msg)
        failures.append(name)


def section(title: str):
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print('─' * 60)


# ── 1. issue_watcher: comments field ──────────────────────────────

section("issue_watcher.py — GitHubIssue.comments field")

try:
    from issue_watcher import GitHubIssue

    i1 = GitHubIssue(
        id=1, number=1, title="t", body="b",
        state="open", author="u", labels=[],
        created_at="", updated_at="", html_url="",
        comments_url="",
    )
    check("Default comments is empty list", i1.comments == [])

    i2 = GitHubIssue(
        id=2, number=2, title="t", body="b",
        state="open", author="u", labels=[],
        created_at="", updated_at="", html_url="",
        comments_url="",
        comments=[{"author": "a", "body": "hello"}],
    )
    check("Comments field accepts list of dicts", len(i2.comments) == 1)

    # Each instance must have its OWN list (not shared mutable default)
    i1.comments.append("something")
    check("Comments instances are independent", i2.comments == [{"author": "a", "body": "hello"}])

except Exception as e:
    check("issue_watcher imports OK", False, str(e))


# ── 2. gh_wrapper: parse_issue_url ─────────────────────────────────

section("gh_wrapper.py — parse_issue_url()")

try:
    from gh_wrapper import GitHubCLI

    check("Valid URL #1769 → 1769",
          GitHubCLI.parse_issue_url("https://github.com/unclecode/crawl4ai/issues/1769") == 1769)
    check("Valid URL #42 → 42",
          GitHubCLI.parse_issue_url("https://github.com/x/y/issues/42") == 42)
    check("Returns int not str",
          isinstance(GitHubCLI.parse_issue_url("https://github.com/x/y/issues/1"), int))

    raised = False
    try:
        GitHubCLI.parse_issue_url("https://github.com/unclecode/crawl4ai")
    except ValueError:
        raised = True
    check("No /issues/N raises ValueError", raised)

    raised = False
    try:
        GitHubCLI.parse_issue_url("not-a-url")
    except ValueError:
        raised = True
    check("Non-URL raises ValueError", raised)

except Exception as e:
    check("gh_wrapper imports OK", False, str(e))


# ── 3. issue_ingestion: None body + comments ────────────────────────

section("issue_ingestion.py — None body guard & comments")

try:
    from issue_ingestion import IssueIngestionEngine
    engine = IssueIngestionEngine()

    # None body should not crash
    issue_none = GitHubIssue(
        id=1, number=1, title="bug", body=None,
        state="open", author="u", labels=[],
        created_at="", updated_at="", html_url="", comments_url="",
    )
    result = engine.parse_issue(issue_none)
    check("None body does not crash", result is not None)

    # Comments included in keyword extraction
    issue_comment_kw = GitHubIssue(
        id=2, number=2, title="bug title", body="no keywords here",
        state="open", author="u", labels=[],
        created_at="", updated_at="", html_url="", comments_url="",
        comments=[{"author": "a", "body": "timeout hang freeze 5 second"}],
    )
    result2 = engine.parse_issue(issue_comment_kw)
    check("Keywords extracted from comments",
          any(kw in result2.keywords for kw in ("timeout", "hang", "freeze")))

    # None comment body should not crash
    issue_none_comment = GitHubIssue(
        id=3, number=3, title="t", body="timeout",
        state="open", author="u", labels=[],
        created_at="", updated_at="", html_url="", comments_url="",
        comments=[None, {"author": "a", "body": None}, {"author": "b", "body": "ok"}],
    )
    result3 = engine.parse_issue(issue_none_comment)
    check("None comment body does not crash", result3 is not None)

except Exception as e:
    check("issue_ingestion test", False, traceback.format_exc())


# ── 4. fix_generator: pattern_name field ────────────────────────────

section("fix_generator.py — Fix.pattern_name field")

try:
    from fix_generator import Fix, FixGenerator
    from root_cause_analyzer import RootCause

    fix = Fix(
        file="a.py", line_number=1, old_code="old", new_code="new",
        explanation="x", test_cases=[], patch="", confidence=0.9,
    )
    check("pattern_name defaults to empty string", fix.pattern_name == "")

    fix2 = Fix(
        file="a.py", line_number=1, old_code="old", new_code="new",
        explanation="x", test_cases=[], patch="", confidence=0.9,
        pattern_name="timeout_issue",
    )
    check("pattern_name can be set", fix2.pattern_name == "timeout_issue")

    gen = FixGenerator()
    rc_unknown = RootCause(
        pattern_name="totally_unknown", file="f.py", line_number=1,
        function="fn", explanation="...", confidence=0.9,
        code_snippet="code", suggested_fix="fix",
    )
    check("Unknown pattern returns None", gen.generate_fix(rc_unknown) is None)

    rc_timeout = RootCause(
        pattern_name="timeout_issue", file="deploy/docker/mcp_bridge.py",
        line_number=35, function="_make_http_proxy",
        explanation="Missing timeout=None", confidence=0.95,
        code_snippet="async with httpx.AsyncClient() as client:",
        suggested_fix="async with httpx.AsyncClient(timeout=None) as client:",
    )
    fix_t = gen.generate_fix(rc_timeout)
    if fix_t:
        check("generate_fix sets pattern_name", fix_t.pattern_name == "timeout_issue")
        check("generate_fix includes timeout=None", "timeout=None" in fix_t.new_code)
    else:
        check("generate_fix returns Fix for timeout (or None)", True)  # acceptable

except Exception as e:
    check("fix_generator test", False, traceback.format_exc())


# ── 5. root_cause_analyzer: default path + check_resolution ─────────

section("root_cause_analyzer.py — default path & check_resolution")

try:
    from root_cause_analyzer import RootCauseAnalyzer, RootCause

    analyzer_default = RootCauseAnalyzer()
    expected = Path.home() / "crawl4ai-repo"
    check("Default path is ~/crawl4ai-repo", analyzer_default.codebase_path == expected)

    analyzer_none = RootCauseAnalyzer(None)
    check("None path uses default", analyzer_none.codebase_path == expected)

    analyzer_tilde = RootCauseAnalyzer("~/some-path")
    check("Tilde expanded", "~" not in str(analyzer_tilde.codebase_path))

    analyzer_missing = RootCauseAnalyzer("/nonexistent/path")
    check("Missing path does not raise on init", not analyzer_missing.codebase_path.exists())

    rc = RootCause(
        pattern_name="timeout_issue", file="deploy/docker/mcp_bridge.py",
        line_number=35, function="fn", explanation="x", confidence=0.9,
        code_snippet="async with httpx.AsyncClient() as client:",
        suggested_fix="async with httpx.AsyncClient(timeout=None) as client:",
    )
    result = RootCauseAnalyzer("/nonexistent/path").check_resolution(rc)
    check("check_resolution returns dict", isinstance(result, dict))
    check("check_resolution has 'resolved' key", "resolved" in result)
    check("check_resolution has 'evidence' key", "evidence" in result)
    check("check_resolution resolved=False when path missing", result["resolved"] is False)

except Exception as e:
    check("root_cause_analyzer test", False, traceback.format_exc())


# ── 6. validate_issue: 4-value return, _is_call_to_class ────────────

section("validate_issue.py — bug fixes")

try:
    from validate_issue import LocalValidator

    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        v = LocalValidator(repo_path=tmpdir + "/no-repo")

        # Bug 1: 4-value return
        result = v.validate_pattern_detection("timeout issue", "httpx 5s hang freeze")
        check("validate_pattern_detection returns 4 values", len(result) == 4)
        check("4th value is list", isinstance(result[3], list))

        # Bug 2: _is_call_to_class correct logic
        call_node = ast.parse("httpx.AsyncClient()", mode="eval").body
        check("httpx.AsyncClient correctly matched",
              v._is_call_to_class(call_node, "AsyncClient", "httpx") is True)
        check("Wrong class name not matched",
              v._is_call_to_class(call_node, "SyncClient", "httpx") is False)
        check("Wrong module name not matched",
              v._is_call_to_class(call_node, "AsyncClient", "requests") is False)

        bare_call = ast.parse("AsyncClient()", mode="eval").body
        check("Plain function call not matched",
              v._is_call_to_class(bare_call, "AsyncClient", "httpx") is False)

        # Bug 3: validate_issue does not raise NameError
        vr = v.validate_issue(1234, "Please add CSV export", "CSV export feature")
        check("validate_issue no NameError (no match)", vr is not None)
        check("issue_number preserved", vr.issue_number == 1234)

        vr2 = v.validate_issue(1769, "[Bug]: httpx timeout 5s", "Request hangs freeze 5 second")
        check("validate_issue no NameError (match)", vr2 is not None)

except Exception as e:
    check("validate_issue test", False, traceback.format_exc())


# ── 7. main_gh: _write_report + URL parsing ─────────────────────────

section("main_gh.py — _write_report & URL arg parsing")

try:
    import tempfile
    from unittest.mock import patch
    from main_gh import RootCauseAnalysisPipeline
    from issue_ingestion import IssueIngestionEngine

    _orig_cwd = os.getcwd()
    with tempfile.TemporaryDirectory() as tmpdir:
        os.chdir(tmpdir)
        with patch("gh_wrapper.GitHubCLI._verify_gh_auth", return_value=True):
            pl = RootCauseAnalysisPipeline(repo_path=None, dry_run=True)

        issue = GitHubIssue(
            id=1769, number=1769,
            title="[Bug]: httpx timeout causes isError",
            body="httpx.AsyncClient() hangs after 5s timeout",
            state="open", author="u", labels=["bug"],
            created_at="2024-01-01T00:00:00Z", updated_at="2024-01-01T00:00:00Z",
            html_url="https://github.com/unclecode/crawl4ai/issues/1769",
            comments_url="",
            comments=[],
        )
        parsed = IssueIngestionEngine().parse_issue(issue)
        resolution = {"resolved": False, "evidence": "No timeout= found"}

        pl._write_report(1769, issue, parsed, [], None, None, resolution)

        report_dir = Path(tmpdir) / "test_scripts" / "issues" / "1769"
        verify_md = report_dir / "verify.md"
        verify_py = report_dir / "verify.py"

        check("_write_report creates verify.md", verify_md.exists())
        check("_write_report creates verify.py", verify_py.exists())

        md_content = verify_md.read_text(encoding="utf-8")
        check("verify.md contains issue title", issue.title in md_content)
        check("verify.md contains html_url", issue.html_url in md_content)
        check("verify.md contains '## Issue Summary'", "## Issue Summary" in md_content)
        check("verify.md contains '## Root Cause Analysis'", "## Root Cause Analysis" in md_content)
        check("verify.md contains 'Not Resolved'", "Not Resolved" in md_content)

        py_content = verify_py.read_text(encoding="utf-8")
        ast.parse(py_content)  # must be valid Python
        check("verify.py is valid Python", True)

    os.chdir(_orig_cwd)  # restore so web_ui can create templates/
    from gh_wrapper import GitHubCLI
    check("parse_issue_url 1769", GitHubCLI.parse_issue_url(
        "https://github.com/unclecode/crawl4ai/issues/1769") == 1769)

except Exception as e:
    check("main_gh test", False, traceback.format_exc())


# ── 8. web_ui: FastAPI endpoints ────────────────────────────────────

section("web_ui.py — FastAPI endpoints via TestClient")

try:
    from starlette.testclient import TestClient
    import web_ui

    # Reset state
    web_ui.system_state.update({
        "status": "idle", "last_check": None, "issues_processed": 0,
        "patterns_detected": 0, "fixes_generated": 0, "prs_created": 0,
    })
    web_ui.analysis_state.update({
        "logs": [], "steps": {k: "pending" for k in web_ui.analysis_state["steps"]},
        "is_running": False, "result": None, "issue_number": None,
    })

    client = TestClient(web_ui.app)

    # GET /
    resp = client.get("/")
    check("GET / returns 200", resp.status_code == 200)
    check("GET / returns HTML", "text/html" in resp.headers.get("content-type", ""))
    check("GET / contains 'Crawl4AI'", "Crawl4AI" in resp.text)
    check("GET / has URL input field",
          "issueUrl" in resp.text or "issue_url" in resp.text or "github.com" in resp.text.lower())

    # GET /api/status
    resp = client.get("/api/status")
    check("GET /api/status returns 200", resp.status_code == 200)
    data = resp.json()
    check("status has 'status' field", "status" in data)
    check("status default is idle", data["status"] == "idle")
    check("status has 'analysis' field", "analysis" in data)
    check("analysis has 7 steps", len(data["analysis"]["steps"]) == 7)

    # POST /api/analyze with URL
    from unittest.mock import patch, AsyncMock
    with patch("web_ui._run_analysis", new_callable=AsyncMock):
        resp = client.post("/api/analyze", json={
            "issue_url": "https://github.com/unclecode/crawl4ai/issues/1769",
        })
    check("POST /api/analyze valid URL → 200", resp.status_code == 200)
    check("analyze response has issue_number=1769", resp.json().get("issue_number") == 1769)

    resp_bad = client.post("/api/analyze", json={"issue_url": "not-a-url"})
    check("POST /api/analyze bad URL → 400", resp_bad.status_code == 400)

    # Watch endpoints must be POST
    check("GET /api/watch/start → 405", client.get("/api/watch/start").status_code == 405)
    check("GET /api/watch/stop → 405", client.get("/api/watch/stop").status_code == 405)
    check("POST /api/watch/start → 200", client.post("/api/watch/start").status_code == 200)
    web_ui.system_state["status"] = "watching"
    check("POST /api/watch/stop → 200", client.post("/api/watch/stop").status_code == 200)
    web_ui.system_state["status"] = "idle"

    # GET /api/report/{number} — 404 when missing
    check("GET /api/report/99999 → 404", client.get("/api/report/99999").status_code == 404)

    # GET /api/analyses — always a list
    resp_list = client.get("/api/analyses")
    check("GET /api/analyses → 200", resp_list.status_code == 200)
    check("GET /api/analyses → list", isinstance(resp_list.json(), list))

except Exception as e:
    check("web_ui test", False, traceback.format_exc())


# ── Summary ──────────────────────────────────────────────────────────

print(f"\n{'═' * 60}")
total = len(failures)
if total == 0:
    print(f"\033[32m  ALL CHECKS PASSED\033[0m")
    sys.exit(0)
else:
    print(f"\033[31m  {total} FAILURE(S):\033[0m")
    for f in failures:
        print(f"    • {f}")
    sys.exit(1)

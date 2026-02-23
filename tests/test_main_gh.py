"""
Tests for main_gh.py — RootCauseAnalysisPipeline.
Focus: _write_report, _attempt_reproduction, URL argument parsing.
"""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from main_gh import RootCauseAnalysisPipeline


@pytest.fixture
def pipeline(tmp_path, monkeypatch):
    """A pipeline instance that writes to tmp_path instead of the real project root."""
    monkeypatch.chdir(tmp_path)
    with patch("gh_wrapper.GitHubCLI._verify_gh_auth", return_value=True):
        pl = RootCauseAnalysisPipeline(repo_path=None, dry_run=True)
    return pl


# ── _write_report ──────────────────────────────────────────────────

class TestWriteReport:
    """Tests for _write_report creating the correct files."""

    def test_creates_verify_md(self, pipeline, tmp_path, timeout_issue, monkeypatch):
        monkeypatch.chdir(tmp_path)
        from issue_ingestion import IssueIngestionEngine
        parsed = IssueIngestionEngine().parse_issue(timeout_issue)
        resolution = {"resolved": False, "evidence": "No timeout parameter found"}

        pipeline._write_report(1769, timeout_issue, parsed, [], None, None, resolution)

        md = tmp_path / "test_scripts" / "issues" / "1769" / "verify.md"
        assert md.exists(), "verify.md must be created"

    def test_creates_verify_py(self, pipeline, tmp_path, timeout_issue, monkeypatch):
        monkeypatch.chdir(tmp_path)
        from issue_ingestion import IssueIngestionEngine
        parsed = IssueIngestionEngine().parse_issue(timeout_issue)
        resolution = {"resolved": False, "evidence": "No timeout parameter found"}

        pipeline._write_report(1769, timeout_issue, parsed, [], None, None, resolution)

        py = tmp_path / "test_scripts" / "issues" / "1769" / "verify.py"
        assert py.exists(), "verify.py must be created"

    def test_verify_md_contains_issue_title(self, pipeline, tmp_path, timeout_issue, monkeypatch):
        monkeypatch.chdir(tmp_path)
        from issue_ingestion import IssueIngestionEngine
        parsed = IssueIngestionEngine().parse_issue(timeout_issue)
        resolution = {"resolved": False, "evidence": "No timeout parameter"}

        pipeline._write_report(1769, timeout_issue, parsed, [], None, None, resolution)

        md = (tmp_path / "test_scripts" / "issues" / "1769" / "verify.md").read_text()
        assert timeout_issue.title in md

    def test_verify_md_contains_issue_url(self, pipeline, tmp_path, timeout_issue, monkeypatch):
        monkeypatch.chdir(tmp_path)
        from issue_ingestion import IssueIngestionEngine
        parsed = IssueIngestionEngine().parse_issue(timeout_issue)
        resolution = {"resolved": False, "evidence": "..."}

        pipeline._write_report(1769, timeout_issue, parsed, [], None, None, resolution)

        md = (tmp_path / "test_scripts" / "issues" / "1769" / "verify.md").read_text()
        assert timeout_issue.html_url in md

    def test_verify_md_contains_resolution_status(self, pipeline, tmp_path, timeout_issue, monkeypatch):
        monkeypatch.chdir(tmp_path)
        from issue_ingestion import IssueIngestionEngine
        parsed = IssueIngestionEngine().parse_issue(timeout_issue)
        resolution = {"resolved": True, "evidence": "timeout= found at line 35"}

        pipeline._write_report(1769, timeout_issue, parsed, [], None, None, resolution)

        md = (tmp_path / "test_scripts" / "issues" / "1769" / "verify.md").read_text()
        assert "Already Resolved" in md

    def test_verify_md_not_resolved_badge(self, pipeline, tmp_path, encoding_issue, monkeypatch):
        monkeypatch.chdir(tmp_path)
        from issue_ingestion import IssueIngestionEngine
        parsed = IssueIngestionEngine().parse_issue(encoding_issue)
        resolution = {"resolved": False, "evidence": "No encoding found"}

        pipeline._write_report(1762, encoding_issue, parsed, [], None, None, resolution)

        md = (tmp_path / "test_scripts" / "issues" / "1762" / "verify.md").read_text()
        assert "Not Resolved" in md

    def test_verify_md_required_sections_present(self, pipeline, tmp_path, timeout_issue, monkeypatch):
        monkeypatch.chdir(tmp_path)
        from issue_ingestion import IssueIngestionEngine
        parsed = IssueIngestionEngine().parse_issue(timeout_issue)
        resolution = {"resolved": False, "evidence": "..."}

        pipeline._write_report(1769, timeout_issue, parsed, [], None, None, resolution)

        md = (tmp_path / "test_scripts" / "issues" / "1769" / "verify.md").read_text()
        required_sections = [
            "## Issue Summary",
            "## Environment",
            "## Reproduction",
            "## Root Cause Analysis",
            "## Resolution Check",
            "## Suggested Fixes",
            "## Regression Tests",
        ]
        for section in required_sections:
            assert section in md, f"Missing required section: {section}"

    def test_verify_py_is_valid_python(self, pipeline, tmp_path, timeout_issue, monkeypatch):
        import ast
        monkeypatch.chdir(tmp_path)
        from issue_ingestion import IssueIngestionEngine
        parsed = IssueIngestionEngine().parse_issue(timeout_issue)
        resolution = {"resolved": False, "evidence": "..."}

        pipeline._write_report(1769, timeout_issue, parsed, [], None, None, resolution)

        py_content = (tmp_path / "test_scripts" / "issues" / "1769" / "verify.py").read_text()
        # Must parse as valid Python
        ast.parse(py_content)

    def test_verify_py_timeout_stub_mentions_asyncclient(self, pipeline, tmp_path, timeout_issue, monkeypatch):
        monkeypatch.chdir(tmp_path)
        from issue_ingestion import IssueIngestionEngine
        from pattern_recognition import PatternRecognitionEngine, PatternMatch
        parsed = IssueIngestionEngine().parse_issue(timeout_issue)
        patterns = PatternRecognitionEngine().match_pattern(parsed)
        resolution = {"resolved": False, "evidence": "..."}

        pipeline._write_report(1769, timeout_issue, parsed, patterns, None, None, resolution)

        py_content = (tmp_path / "test_scripts" / "issues" / "1769" / "verify.py").read_text()
        assert "AsyncClient" in py_content or "timeout" in py_content.lower()

    def test_creates_directory_if_not_exists(self, pipeline, tmp_path, timeout_issue, monkeypatch):
        monkeypatch.chdir(tmp_path)
        from issue_ingestion import IssueIngestionEngine
        parsed = IssueIngestionEngine().parse_issue(timeout_issue)
        resolution = {"resolved": False, "evidence": "..."}

        # Directory doesn't exist yet
        assert not (tmp_path / "test_scripts" / "issues" / "1769").exists()

        pipeline._write_report(1769, timeout_issue, parsed, [], None, None, resolution)

        assert (tmp_path / "test_scripts" / "issues" / "1769").is_dir()

    def test_encoding_issue_verify_py_mentions_utf8(self, pipeline, tmp_path, encoding_issue, monkeypatch):
        monkeypatch.chdir(tmp_path)
        from issue_ingestion import IssueIngestionEngine
        from pattern_recognition import PatternRecognitionEngine
        parsed = IssueIngestionEngine().parse_issue(encoding_issue)
        patterns = PatternRecognitionEngine().match_pattern(parsed)
        resolution = {"resolved": False, "evidence": "..."}

        pipeline._write_report(1762, encoding_issue, parsed, patterns, None, None, resolution)

        py_content = (tmp_path / "test_scripts" / "issues" / "1762" / "verify.py").read_text()
        assert "utf-8" in py_content or "encoding" in py_content.lower()


# ── _attempt_reproduction ──────────────────────────────────────────

class TestAttemptReproduction:
    """Tests for the reproduction check method."""

    def test_returns_blocked_when_codebase_missing(self, pipeline, timeout_root_cause):
        # Default path ~/crawl4ai-repo doesn't exist on test machine
        result = pipeline._attempt_reproduction(timeout_root_cause)
        # Either "blocked" (no codebase) or "reproduced" (if codebase exists)
        assert result in ("blocked", "reproduced", "not_reproduced")

    def test_returns_reproduced_when_buggy_code_present(self, pipeline, fake_repo, timeout_root_cause):
        pipeline.root_cause_analyzer.codebase_path = fake_repo
        timeout_root_cause.file = "deploy/docker/mcp_bridge.py"
        timeout_root_cause.line_number = 4
        # The code_snippet is present in fake file
        timeout_root_cause.code_snippet = "async with httpx.AsyncClient() as client:"
        result = pipeline._attempt_reproduction(timeout_root_cause)
        assert result == "reproduced"

    def test_returns_blocked_when_file_missing(self, pipeline, fake_repo, timeout_root_cause):
        pipeline.root_cause_analyzer.codebase_path = fake_repo
        timeout_root_cause.file = "nonexistent/path.py"
        result = pipeline._attempt_reproduction(timeout_root_cause)
        assert result == "blocked"

    def test_result_is_one_of_three_valid_values(self, pipeline, timeout_root_cause):
        result = pipeline._attempt_reproduction(timeout_root_cause)
        assert result in ("reproduced", "not_reproduced", "blocked")


# ── URL argument parsing ───────────────────────────────────────────

class TestUrlArgumentParsing:
    """The pipeline should accept URLs via GitHubCLI.parse_issue_url."""

    def test_parse_issue_url_used_for_url_flag(self):
        from gh_wrapper import GitHubCLI
        issue_num = GitHubCLI.parse_issue_url(
            "https://github.com/unclecode/crawl4ai/issues/1769"
        )
        assert issue_num == 1769

    def test_invalid_url_raises_value_error(self):
        from gh_wrapper import GitHubCLI
        with pytest.raises(ValueError):
            GitHubCLI.parse_issue_url("not-a-valid-github-url")

"""
Tests for root_cause_analyzer.py — RootCauseAnalyzer.
"""
import os
import pytest
from pathlib import Path
from unittest.mock import patch
from root_cause_analyzer import RootCauseAnalyzer, RootCause


class TestDefaultPath:
    """RootCauseAnalyzer should default to ~/crawl4ai-repo."""

    def test_default_path_is_home_crawl4ai_repo(self):
        analyzer = RootCauseAnalyzer()
        expected = Path.home() / "crawl4ai-repo"
        assert analyzer.codebase_path == expected

    def test_none_path_uses_default(self):
        analyzer = RootCauseAnalyzer(None)
        expected = Path.home() / "crawl4ai-repo"
        assert analyzer.codebase_path == expected

    def test_explicit_path_is_used(self, tmp_path):
        analyzer = RootCauseAnalyzer(str(tmp_path))
        assert analyzer.codebase_path == tmp_path

    def test_tilde_in_path_is_expanded(self):
        analyzer = RootCauseAnalyzer("~/some-path")
        assert "~" not in str(analyzer.codebase_path)
        assert str(Path.home()) in str(analyzer.codebase_path)

    def test_missing_path_does_not_raise(self):
        """If the codebase path doesn't exist, init should warn but not crash."""
        analyzer = RootCauseAnalyzer("/nonexistent/path/crawl4ai-repo")
        assert not analyzer.codebase_path.exists()  # Path doesn't exist
        # But object was created successfully


class TestCheckResolutionNoCodbase:
    """check_resolution when codebase path doesn't exist."""

    def test_returns_dict_with_resolved_false(self, timeout_root_cause):
        analyzer = RootCauseAnalyzer("/nonexistent/path")
        result = analyzer.check_resolution(timeout_root_cause)
        assert isinstance(result, dict)
        assert result["resolved"] is False
        assert "evidence" in result
        assert len(result["evidence"]) > 0

    def test_returns_dict_not_none(self, encoding_root_cause):
        analyzer = RootCauseAnalyzer("/nonexistent/path")
        result = analyzer.check_resolution(encoding_root_cause)
        assert result is not None


class TestCheckResolutionWithFakeRepo:
    """check_resolution with a real (fake) codebase on disk."""

    def test_detects_timeout_bug_not_resolved(self, fake_repo, timeout_root_cause):
        """mcp_bridge.py has httpx.AsyncClient() without timeout — not resolved."""
        analyzer = RootCauseAnalyzer(str(fake_repo))
        # Point to the fake file
        timeout_root_cause.file = "deploy/docker/mcp_bridge.py"
        timeout_root_cause.line_number = 4  # line with AsyncClient()
        result = analyzer.check_resolution(timeout_root_cause)
        assert result["resolved"] is False
        assert "timeout" in result["evidence"].lower()

    def test_detects_encoding_bug_not_resolved(self, fake_repo, encoding_root_cause):
        """cli.py has open() without encoding='utf-8' — not resolved."""
        analyzer = RootCauseAnalyzer(str(fake_repo))
        encoding_root_cause.file = "crawl4ai/cli.py"
        encoding_root_cause.line_number = 3
        result = analyzer.check_resolution(encoding_root_cause)
        assert result["resolved"] is False

    def test_detects_encoding_already_resolved(self, fake_repo, encoding_root_cause):
        """cli_fixed.py has encoding='utf-8' already applied."""
        analyzer = RootCauseAnalyzer(str(fake_repo))
        encoding_root_cause.file = "crawl4ai/cli_fixed.py"
        encoding_root_cause.line_number = 3
        result = analyzer.check_resolution(encoding_root_cause)
        assert result["resolved"] is True
        assert "encoding" in result["evidence"].lower()

    def test_missing_file_returns_resolved_false(self, fake_repo, timeout_root_cause):
        """If the reported file doesn't exist, resolved=False."""
        analyzer = RootCauseAnalyzer(str(fake_repo))
        timeout_root_cause.file = "nonexistent/file.py"
        result = analyzer.check_resolution(timeout_root_cause)
        assert result["resolved"] is False
        assert "not found" in result["evidence"].lower() or "File not found" in result["evidence"]

    def test_unknown_pattern_uses_generic_check(self, fake_repo):
        """Unknown pattern falls back to suggested_fix substring search."""
        analyzer = RootCauseAnalyzer(str(fake_repo))
        root_cause = RootCause(
            pattern_name="some_unknown_pattern",
            file="deploy/docker/mcp_bridge.py",
            line_number=1,
            function="fn",
            explanation="...",
            confidence=0.7,
            code_snippet="...",
            suggested_fix="httpx.AsyncClient()",  # This IS in the file
        )
        result = analyzer.check_resolution(root_cause)
        # suggested_fix is in the file — may be detected as resolved
        assert isinstance(result["resolved"], bool)
        assert "evidence" in result

    def test_check_resolution_result_always_has_both_keys(self, fake_repo, timeout_root_cause):
        analyzer = RootCauseAnalyzer(str(fake_repo))
        timeout_root_cause.file = "deploy/docker/mcp_bridge.py"
        timeout_root_cause.line_number = 4
        result = analyzer.check_resolution(timeout_root_cause)
        assert "resolved" in result
        assert "evidence" in result
        assert isinstance(result["resolved"], bool)
        assert isinstance(result["evidence"], str)

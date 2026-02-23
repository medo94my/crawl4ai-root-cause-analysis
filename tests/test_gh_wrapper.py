"""
Tests for gh_wrapper.py — GitHubCLI.
"""
import json
import pytest
from unittest.mock import patch, MagicMock
from gh_wrapper import GitHubCLI


# ── parse_issue_url ────────────────────────────────────────────────

class TestParseIssueUrl:
    """parse_issue_url is a static method — no GitHub auth needed."""

    @pytest.mark.parametrize("url,expected", [
        ("https://github.com/unclecode/crawl4ai/issues/1769", 1769),
        ("https://github.com/unclecode/crawl4ai/issues/1",    1),
        ("https://github.com/some/other-repo/issues/42",      42),
        ("https://github.com/org/repo/issues/99999",          99999),
        # URL with trailing slash or fragment still works
        ("https://github.com/unclecode/crawl4ai/issues/100/", 100),
    ])
    def test_valid_urls(self, url, expected):
        assert GitHubCLI.parse_issue_url(url) == expected

    @pytest.mark.parametrize("bad_url", [
        "https://github.com/unclecode/crawl4ai",            # no /issues/
        "https://github.com/unclecode/crawl4ai/pulls/1769", # pull request not issue
        "not-a-url",
        "",
        "https://github.com/",
    ])
    def test_invalid_urls_raise_value_error(self, bad_url):
        with pytest.raises(ValueError, match="Could not parse issue number"):
            GitHubCLI.parse_issue_url(bad_url)

    def test_returns_int_not_string(self):
        result = GitHubCLI.parse_issue_url("https://github.com/a/b/issues/123")
        assert isinstance(result, int)


# ── _verify_gh_auth ───────────────────────────────────────────────

class TestVerifyGhAuth:
    """Test that auth check reads both stdout and stderr."""

    def _make_run_result(self, stdout="", stderr="", returncode=0):
        m = MagicMock()
        m.stdout = stdout
        m.stderr = stderr
        m.returncode = returncode
        return m

    def test_logged_in_in_stdout(self, mock_gh_auth):
        # mock_gh_auth fixture bypasses the real check; test the method directly
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = self._make_run_result(stdout="Logged in to github.com as user")
            with patch("gh_wrapper.GitHubCLI._verify_gh_auth"):
                gh = GitHubCLI.__new__(GitHubCLI)
                gh.owner = "unclecode"
                gh.repo = "crawl4ai"
                gh.full_repo = "unclecode/crawl4ai"
            # Call the real method
            with patch("subprocess.run") as mock_run2:
                mock_run2.return_value = self._make_run_result(stdout="Logged in to github.com")
                result = GitHubCLI._verify_gh_auth(gh)
                assert result is True

    def test_logged_in_in_stderr(self):
        with patch("gh_wrapper.GitHubCLI._verify_gh_auth"):
            gh = GitHubCLI.__new__(GitHubCLI)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = self._make_run_result(
                stdout="",
                stderr="Logged in to github.com as myuser (oauth_token)"
            )
            result = GitHubCLI._verify_gh_auth(gh)
            assert result is True

    def test_not_authenticated_returns_false(self):
        with patch("gh_wrapper.GitHubCLI._verify_gh_auth"):
            gh = GitHubCLI.__new__(GitHubCLI)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = self._make_run_result(
                stdout="You are not logged in",
                stderr=""
            )
            result = GitHubCLI._verify_gh_auth(gh)
            assert result is False

    def test_gh_not_installed_raises(self):
        with patch("gh_wrapper.GitHubCLI._verify_gh_auth"):
            gh = GitHubCLI.__new__(GitHubCLI)
        with patch("subprocess.run", side_effect=FileNotFoundError):
            with pytest.raises(RuntimeError, match="GitHub CLI not installed"):
                GitHubCLI._verify_gh_auth(gh)


# ── get_issue returns comments ─────────────────────────────────────

class TestGetIssueComments:
    """Test that get_issue fetches and maps comments correctly."""

    def test_get_issue_includes_comments_field(self, mock_gh_auth):
        fake_response = {
            "number": 1769,
            "title": "Timeout bug",
            "body": "Issue body",
            "state": "open",
            "author": {"login": "reporter"},
            "labels": [{"name": "bug"}],
            "createdAt": "2024-02-21T00:00:00Z",
            "updatedAt": "2024-02-21T00:00:00Z",
            "url": "https://github.com/unclecode/crawl4ai/issues/1769",
            "comments": [
                {"author": {"login": "alice"}, "body": "Me too!", "createdAt": "2024-02-21T01:00:00Z"},
                {"author": {"login": "bob"},   "body": "Confirmed.", "createdAt": "2024-02-21T02:00:00Z"},
            ],
        }
        with patch("gh_wrapper.GitHubCLI._run_command", return_value=fake_response):
            gh = GitHubCLI(owner="unclecode", repo="crawl4ai")
            result = gh.get_issue(1769)

        assert "comments" in result
        assert len(result["comments"]) == 2
        assert result["comments"][0]["author"] == "alice"
        assert result["comments"][0]["body"] == "Me too!"
        assert result["comments"][1]["author"] == "bob"

    def test_get_issue_empty_comments(self, mock_gh_auth):
        fake_response = {
            "number": 42,
            "title": "Minor bug",
            "body": "Body text",
            "state": "open",
            "author": {"login": "reporter"},
            "labels": [],
            "createdAt": "2024-01-01T00:00:00Z",
            "updatedAt": "2024-01-01T00:00:00Z",
            "url": "https://github.com/unclecode/crawl4ai/issues/42",
            "comments": [],
        }
        with patch("gh_wrapper.GitHubCLI._run_command", return_value=fake_response):
            gh = GitHubCLI()
            result = gh.get_issue(42)

        assert result["comments"] == []

    def test_get_issue_missing_comments_key(self, mock_gh_auth):
        """If gh CLI omits comments key, result should still have empty list."""
        fake_response = {
            "number": 10,
            "title": "Test",
            "body": "Body",
            "state": "open",
            "author": {"login": "u"},
            "labels": [],
            "createdAt": "2024-01-01T00:00:00Z",
            "updatedAt": "2024-01-01T00:00:00Z",
            "url": "https://github.com/unclecode/crawl4ai/issues/10",
            # No 'comments' key
        }
        with patch("gh_wrapper.GitHubCLI._run_command", return_value=fake_response):
            gh = GitHubCLI()
            result = gh.get_issue(10)

        assert result["comments"] == []

    def test_get_issue_json_fields_include_comments(self, mock_gh_auth):
        """Verify the --json argument passed to gh CLI includes 'comments'."""
        with patch("gh_wrapper.GitHubCLI._run_command") as mock_run:
            mock_run.return_value = {
                "number": 1, "title": "t", "body": "b", "state": "open",
                "author": {"login": "u"}, "labels": [],
                "createdAt": "2024-01-01T00:00:00Z", "updatedAt": "2024-01-01T00:00:00Z",
                "url": "https://github.com/a/b/issues/1", "comments": [],
            }
            gh = GitHubCLI()
            gh.get_issue(1)
            args_passed = mock_run.call_args[0][0]
            # Find the --json argument value
            json_idx = args_passed.index("--json")
            json_fields = args_passed[json_idx + 1]
            assert "comments" in json_fields

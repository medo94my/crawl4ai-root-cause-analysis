"""
Tests for issue_ingestion.py — IssueIngestionEngine.
"""
import pytest
from issue_ingestion import IssueIngestionEngine, ParsedIssue


@pytest.fixture
def engine():
    return IssueIngestionEngine()


class TestNoneBodyGuard:
    """parse_issue must not crash when body is None."""

    def test_none_body_does_not_crash(self, engine, no_body_issue):
        result = engine.parse_issue(no_body_issue)
        assert isinstance(result, ParsedIssue)

    def test_empty_string_body_does_not_crash(self, engine):
        from issue_watcher import GitHubIssue
        issue = GitHubIssue(
            id=1, number=1, title="t", body="", state="open",
            author="a", labels=[], created_at="", updated_at="",
            html_url="", comments_url="",
        )
        result = engine.parse_issue(issue)
        assert isinstance(result, ParsedIssue)


class TestCommentsIncludedInParsing:
    """Comments should be included when extracting code, errors, and keywords."""

    def test_keywords_extracted_from_comments(self, engine):
        from issue_watcher import GitHubIssue
        issue = GitHubIssue(
            id=1, number=1,
            title="Something weird",
            body="The request fails.",
            state="open", author="u", labels=[],
            created_at="", updated_at="", html_url="", comments_url="",
            comments=[
                {"author": "alice", "body": "This is a timeout issue, 5 second hang", "created_at": ""},
            ],
        )
        result = engine.parse_issue(issue)
        # 'timeout' keyword should be detected from the comment
        assert "timeout" in result.keywords

    def test_code_snippets_extracted_from_comments(self, engine):
        from issue_watcher import GitHubIssue
        issue = GitHubIssue(
            id=1, number=1, title="Code in comment",
            body="No code here.",
            state="open", author="u", labels=[],
            created_at="", updated_at="", html_url="", comments_url="",
            comments=[
                {"author": "alice", "body": "```python\nasync with httpx.AsyncClient() as client:\n    r = await client.get(url)\n```", "created_at": ""},
            ],
        )
        result = engine.parse_issue(issue)
        assert len(result.code_snippets) > 0
        assert any("AsyncClient" in s.code for s in result.code_snippets)

    def test_errors_extracted_from_comments(self, engine):
        from issue_watcher import GitHubIssue
        issue = GitHubIssue(
            id=1, number=1, title="Error in comment",
            body="No error in body.",
            state="open", author="u", labels=[],
            created_at="", updated_at="", html_url="", comments_url="",
            comments=[
                {"author": "alice", "body": "TimeoutError: Request timed out after 5s", "created_at": ""},
            ],
        )
        result = engine.parse_issue(issue)
        assert len(result.errors) > 0

    def test_empty_comments_list_is_safe(self, engine, timeout_issue):
        timeout_issue.comments = []
        result = engine.parse_issue(timeout_issue)
        assert isinstance(result, ParsedIssue)

    def test_comment_with_none_body_is_skipped(self, engine):
        from issue_watcher import GitHubIssue
        issue = GitHubIssue(
            id=1, number=1, title="t", body="timeout hang 5 second",
            state="open", author="u", labels=[],
            created_at="", updated_at="", html_url="", comments_url="",
            comments=[
                None,
                {"author": "a", "body": None, "created_at": ""},
                {"author": "b", "body": "valid comment", "created_at": ""},
            ],
        )
        # Should not crash even with None entries
        result = engine.parse_issue(issue)
        assert isinstance(result, ParsedIssue)


class TestIssueClassification:
    """Issue type classification should still work correctly."""

    def test_timeout_issue_is_bug(self, engine, timeout_issue):
        result = engine.parse_issue(timeout_issue)
        assert result.issue_type == "bug"

    def test_encoding_issue_is_bug(self, engine, encoding_issue):
        result = engine.parse_issue(encoding_issue)
        assert result.issue_type == "bug"

    def test_parsed_issue_has_original_reference(self, engine, timeout_issue):
        result = engine.parse_issue(timeout_issue)
        assert result.original is timeout_issue
        assert result.original.number == 1769


class TestMetadataExtraction:
    """Version and OS metadata extraction."""

    def test_python_version_extracted_from_body(self, engine):
        from issue_watcher import GitHubIssue
        issue = GitHubIssue(
            id=1, number=1, title="t",
            body="Python version: 3.11.5\nOS: Windows",
            state="open", author="u", labels=[],
            created_at="", updated_at="", html_url="", comments_url="",
        )
        result = engine.parse_issue(issue)
        assert result.metadata.python_version == "3.11.5"

    def test_python_version_extracted_from_comments(self, engine):
        from issue_watcher import GitHubIssue
        issue = GitHubIssue(
            id=1, number=1, title="t", body="Something broken",
            state="open", author="u", labels=[],
            created_at="", updated_at="", html_url="", comments_url="",
            comments=[
                {"author": "user", "body": "Running Python: 3.12 on macOS", "created_at": ""},
            ],
        )
        result = engine.parse_issue(issue)
        assert result.metadata.python_version == "3.12"

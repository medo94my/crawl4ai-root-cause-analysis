"""
Tests for issue_watcher.py — GitHubIssue dataclass.
"""
import pytest
from issue_watcher import GitHubIssue


class TestGitHubIssueComments:
    """Tests for the comments field added to GitHubIssue."""

    def test_comments_defaults_to_empty_list(self):
        issue = GitHubIssue(
            id=1, number=1, title="t", body="b", state="open",
            author="a", labels=[], created_at="", updated_at="",
            html_url="", comments_url="",
        )
        assert issue.comments == []

    def test_comments_field_accepts_list_of_dicts(self):
        comments = [
            {"author": "alice", "body": "Great issue!", "created_at": "2024-01-01"},
            {"author": "bob", "body": "Confirmed.", "created_at": "2024-01-02"},
        ]
        issue = GitHubIssue(
            id=1, number=1, title="t", body="b", state="open",
            author="a", labels=[], created_at="", updated_at="",
            html_url="", comments_url="", comments=comments,
        )
        assert len(issue.comments) == 2
        assert issue.comments[0]["author"] == "alice"
        assert issue.comments[1]["body"] == "Confirmed."

    def test_comments_instances_are_independent(self):
        """Each instance has its own comments list — no shared mutable default."""
        i1 = GitHubIssue(id=1, number=1, title="t", body="b", state="open",
                         author="a", labels=[], created_at="", updated_at="",
                         html_url="", comments_url="")
        i2 = GitHubIssue(id=2, number=2, title="t", body="b", state="open",
                         author="a", labels=[], created_at="", updated_at="",
                         html_url="", comments_url="")
        i1.comments.append({"author": "x", "body": "y"})
        assert i2.comments == [], "Comments list should not be shared between instances"

    def test_comments_with_none_body_still_works(self, no_body_issue):
        assert no_body_issue.body is None
        assert no_body_issue.comments == []

    def test_all_original_fields_still_present(self):
        issue = GitHubIssue(
            id=42, number=100, title="My Title", body="My body",
            state="closed", author="user123", labels=["bug", "help"],
            created_at="2024-01-01T00:00:00Z", updated_at="2024-01-02T00:00:00Z",
            html_url="https://github.com/x/y/issues/100",
            comments_url="https://api.github.com/repos/x/y/issues/100/comments",
        )
        assert issue.id == 42
        assert issue.number == 100
        assert issue.title == "My Title"
        assert issue.state == "closed"
        assert "bug" in issue.labels
        assert issue.html_url == "https://github.com/x/y/issues/100"

"""
Shared pytest fixtures for all test modules.
"""
import sys
import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Make sure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))


# ── GitHub Issue Fixtures ──────────────────────────────────────────

@pytest.fixture
def timeout_issue():
    """A GitHubIssue that should match the timeout_issue pattern."""
    from issue_watcher import GitHubIssue
    return GitHubIssue(
        id=1769,
        number=1769,
        title="[Bug]: mcp_bridge: httpx default 5s timeout causes isError",
        body=(
            "When an LLM-backed endpoint takes longer than 5 seconds to respond, "
            "httpx.AsyncClient() raises a timeout error causing isError=True. "
            "The 5 second timeout causes the request to hang and freeze."
        ),
        state="open",
        author="testuser",
        labels=["bug"],
        created_at="2024-02-21T00:00:00Z",
        updated_at="2024-02-21T00:00:00Z",
        html_url="https://github.com/unclecode/crawl4ai/issues/1769",
        comments_url="https://api.github.com/repos/unclecode/crawl4ai/issues/1769/comments",
        comments=[
            {"author": "contributor1", "body": "Same issue — 5 second timeout hang on my end too.", "created_at": "2024-02-21T01:00:00Z"},
            {"author": "maintainer", "body": "The httpx default timeout is the culprit.", "created_at": "2024-02-21T02:00:00Z"},
        ],
    )


@pytest.fixture
def encoding_issue():
    """A GitHubIssue that should match the encoding_issue pattern."""
    from issue_watcher import GitHubIssue
    return GitHubIssue(
        id=1762,
        number=1762,
        title="[Bug]: CLI Error charmap codec can't encode",
        body=(
            "Getting this error on Windows:\n"
            "UnicodeEncodeError: 'charmap' codec can't encode character '\\u2019' "
            "in position 42: character maps to <undefined>\n"
            "Python 3.11, Windows 11"
        ),
        state="open",
        author="windowsuser",
        labels=["bug"],
        created_at="2024-02-20T00:00:00Z",
        updated_at="2024-02-20T00:00:00Z",
        html_url="https://github.com/unclecode/crawl4ai/issues/1762",
        comments_url="https://api.github.com/repos/unclecode/crawl4ai/issues/1762/comments",
        comments=[],
    )


@pytest.fixture
def no_body_issue():
    """A GitHubIssue with None body (edge case)."""
    from issue_watcher import GitHubIssue
    return GitHubIssue(
        id=9999,
        number=9999,
        title="[Bug]: something broken",
        body=None,
        state="open",
        author="anon",
        labels=[],
        created_at="2024-01-01T00:00:00Z",
        updated_at="2024-01-01T00:00:00Z",
        html_url="https://github.com/unclecode/crawl4ai/issues/9999",
        comments_url="",
        comments=[],
    )


# ── Root Cause Fixtures ────────────────────────────────────────────

@pytest.fixture
def timeout_root_cause():
    from root_cause_analyzer import RootCause
    return RootCause(
        pattern_name="timeout_issue",
        file="deploy/docker/mcp_bridge.py",
        line_number=35,
        function="_make_http_proxy",
        explanation="Missing timeout=None in httpx.AsyncClient()",
        confidence=0.95,
        code_snippet="async with httpx.AsyncClient() as client:\n    r = await client.get(url)",
        suggested_fix="async with httpx.AsyncClient(timeout=None) as client:",
    )


@pytest.fixture
def encoding_root_cause():
    from root_cause_analyzer import RootCause
    return RootCause(
        pattern_name="encoding_issue",
        file="crawl4ai/cli.py",
        line_number=100,
        function="main",
        explanation="Missing encoding='utf-8' in open() call",
        confidence=0.85,
        code_snippet="with open(output_file, 'w') as f:\n    f.write(data)",
        suggested_fix="with open(output_file, 'w', encoding='utf-8') as f:",
    )


# ── Auth Mock ─────────────────────────────────────────────────────

@pytest.fixture
def mock_gh_auth():
    """Patch _verify_gh_auth so tests don't need a real gh CLI."""
    with patch("gh_wrapper.GitHubCLI._verify_gh_auth", return_value=True):
        yield


# ── Fake Codebase ─────────────────────────────────────────────────

@pytest.fixture
def fake_repo(tmp_path):
    """
    Create a minimal fake crawl4ai repo with real-looking code for
    testing static analysis methods.
    """
    # deploy/docker/mcp_bridge.py — has timeout bug
    mcp_bridge = tmp_path / "deploy" / "docker" / "mcp_bridge.py"
    mcp_bridge.parent.mkdir(parents=True)
    mcp_bridge.write_text(
        'import httpx\n'
        '\n'
        'async def _make_http_proxy(url, **kwargs):\n'
        '    async with httpx.AsyncClient() as client:\n'
        '        try:\n'
        '            r = await client.get(url, params=kwargs)\n'
        '            return r.json()\n'
        '        except Exception as e:\n'
        '            return {"isError": True, "message": str(e)}\n',
        encoding="utf-8",
    )

    # crawl4ai/cli.py — has encoding bug
    cli_py = tmp_path / "crawl4ai" / "cli.py"
    cli_py.parent.mkdir(parents=True)
    cli_py.write_text(
        'def main(output_file):\n'
        '    data = crawl()\n'
        "    with open(output_file, 'w') as f:\n"
        '        f.write(data)\n',
        encoding="utf-8",
    )

    # crawl4ai/cli_fixed.py — has encoding fix already applied
    cli_fixed = tmp_path / "crawl4ai" / "cli_fixed.py"
    cli_fixed.write_text(
        'def main(output_file):\n'
        '    data = crawl()\n'
        "    with open(output_file, 'w', encoding='utf-8') as f:\n"
        '        f.write(data)\n',
        encoding="utf-8",
    )

    return tmp_path

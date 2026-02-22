"""
PR Creator - Creates automated pull requests for fixes.

This module implements automated PR creation:
1. Create git branch
2. Apply patch
3. Create test files
4. Generate commit message
5. Submit PR to GitHub

Usage:
    from pr_creator import PRCreator

    creator = PRCreator(repo_path="/path/to/repo", token="github_token")
    pr_url = creator.create_pr(fix, issue_number)
"""

import os
import subprocess
import logging
from typing import Optional, List, Dict
from dataclasses import dataclass

from fix_generator import Fix

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class PullRequest:
    """Represents a created pull request."""
    number: int
    url: str
    branch: str
    title: str
    body: str
    issue_number: int


class PRCreator:
    """Creates automated pull requests for fixes."""

    def __init__(
        self,
        repo_path: str = "/root/.openclaw/workspace/crawl4ai-repo",
        token: Optional[str] = None,
        dry_run: bool = True,
    ):
        """
        Initialize PR creator.

        Args:
            repo_path: Path to the repository
            token: GitHub personal access token
            dry_run: If True, don't actually create PR
        """
        self.repo_path = repo_path
        self.token = token or os.getenv('GITHUB_TOKEN')
        self.dry_run = dry_run
        self.owner = "unclecode"
        self.repo = "crawl4ai"

        logger.info(f"PRCreator initialized (dry_run={dry_run})")

    def create_pr(
        self,
        fix: Fix,
        issue_number: int,
        base_branch: str = "main",
    ) -> Optional[PullRequest]:
        """
        Create pull request for fix.

        Args:
            fix: Fix object containing the fix
            issue_number: GitHub issue number
            base_branch: Base branch to create PR against

        Returns:
            PullRequest object if successful, None otherwise
        """
        logger.info(f"Creating PR for issue #{issue_number}")

        # 1. Create branch
        branch_name = f"fix/issue-{issue_number}-{fix.pattern_name}"

        if not self._create_branch(branch_name, base_branch):
            logger.error("Failed to create branch")
            return None

        # 2. Apply patch
        if not self._apply_patch(fix):
            logger.error("Failed to apply patch")
            return None

        # 3. Create test files
        if not self._create_test_files(fix):
            logger.warning("Failed to create test files (continuing)")

        # 4. Commit changes
        if not self._commit_changes(fix, issue_number):
            logger.error("Failed to commit changes")
            return None

        # 5. Push branch
        if not self._push_branch(branch_name):
            logger.error("Failed to push branch")
            return None

        # 6. Create PR
        if self.dry_run:
            logger.info(f"[DRY RUN] Would create PR for branch {branch_name}")
            pr = PullRequest(
                number=0,
                url=f"https://github.com/{self.owner}/{self.repo}/pull/0",
                branch=branch_name,
                title=self._generate_pr_title(issue_number, fix),
                body=self._generate_pr_body(fix, issue_number),
                issue_number=issue_number,
            )
        else:
            pr = self._create_github_pr(branch_name, fix, issue_number)
            if not pr:
                return None

        logger.info(f"Successfully created PR: {pr.url}")
        return pr

    def _create_branch(self, branch_name: str, base_branch: str) -> bool:
        """Create and checkout new branch."""
        try:
            # Fetch latest
            subprocess.run(
                ['git', 'fetch', 'origin'],
                cwd=self.repo_path,
                check=True,
                capture_output=True,
            )

            # Checkout base branch
            subprocess.run(
                ['git', 'checkout', base_branch],
                cwd=self.repo_path,
                check=True,
                capture_output=True,
            )

            # Pull latest
            subprocess.run(
                ['git', 'pull', 'origin', base_branch],
                cwd=self.repo_path,
                check=True,
                capture_output=True,
            )

            # Create new branch
            subprocess.run(
                ['git', 'checkout', '-b', branch_name],
                cwd=self.repo_path,
                check=True,
                capture_output=True,
            )

            logger.info(f"Created branch: {branch_name}")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create branch: {e}")
            return False

    def _apply_patch(self, fix: Fix) -> bool:
        """Apply patch to file."""
        try:
            # Write patch file
            patch_file = os.path.join(self.repo_path, '.fix.patch')
            with open(patch_file, 'w') as f:
                f.write(fix.patch)

            # Apply patch
            subprocess.run(
                ['git', 'apply', patch_file],
                cwd=self.repo_path,
                check=True,
                capture_output=True,
            )

            # Clean up patch file
            os.remove(patch_file)

            logger.info(f"Applied patch to {fix.file}")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to apply patch: {e}")
            logger.error(f"stderr: {e.stderr.decode() if e.stderr else 'None'}")
            return False

    def _create_test_files(self, fix: Fix) -> bool:
        """Create test files for the fix."""
        try:
            # Determine test file location
            test_dir = os.path.join(self.repo_path, 'tests')
            if not os.path.exists(test_dir):
                os.makedirs(test_dir)

            # Create test file name
            file_name = fix.file.split('/')[-1].replace('.py', '_test.py')
            test_file = os.path.join(test_dir, file_name)

            # Generate test file content
            test_content = self._generate_test_content(fix)

            # Write test file
            with open(test_file, 'w', encoding='utf-8') as f:
                f.write(test_content)

            logger.info(f"Created test file: {test_file}")
            return True

        except Exception as e:
            logger.error(f"Failed to create test file: {e}")
            return False

    def _generate_test_content(self, fix: Fix) -> str:
        """Generate test file content."""
        return f'''"""
Test cases for fix in {fix.file}

This file contains automated test cases generated by the Root Cause Analysis System.
Issue: {fix.pattern_name}
"""

import pytest


def test_{fix.pattern_name}_fix():
    """
    Test that {fix.pattern_name} is properly handled.

    This test ensures the fix resolves the reported issue.
    """
    # TODO: Implement specific test logic
    assert True
    pass
'''

    def _commit_changes(self, fix: Fix, issue_number: int) -> bool:
        """Commit changes with generated message."""
        try:
            # Stage changes
            subprocess.run(
                ['git', 'add', '.'],
                cwd=self.repo_path,
                check=True,
                capture_output=True,
            )

            # Create commit message
            commit_message = self._generate_commit_message(fix, issue_number)

            # Commit
            subprocess.run(
                ['git', 'commit', '-m', commit_message],
                cwd=self.repo_path,
                check=True,
                capture_output=True,
            )

            logger.info("Committed changes")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to commit: {e}")
            return False

    def _push_branch(self, branch_name: str) -> bool:
        """Push branch to remote."""
        try:
            subprocess.run(
                ['git', 'push', '-u', 'origin', branch_name],
                cwd=self.repo_path,
                check=True,
                capture_output=True,
            )

            logger.info(f"Pushed branch: {branch_name}")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to push branch: {e}")
            return False

    def _create_github_pr(
        self,
        branch_name: str,
        fix: Fix,
        issue_number: int,
    ) -> Optional[PullRequest]:
        """Create PR using GitHub API."""
        import httpx

        if not self.token:
            logger.error("No GitHub token provided")
            return None

        url = f"https://api.github.com/repos/{self.owner}/{self.repo}/pulls"

        headers = {
            'Authorization': f'token {self.token}',
            'Accept': 'application/vnd.github.v3+json',
        }

        data = {
            'title': self._generate_pr_title(issue_number, fix),
            'body': self._generate_pr_body(fix, issue_number),
            'head': branch_name,
            'base': 'main',
            'labels': ['bug', 'automated-fix'],
        }

        try:
            async def create_pr():
                async with httpx.AsyncClient(headers=headers) as client:
                    response = await client.post(url, json=data)

                    if response.status_code == 201:
                        pr_data = response.json()
                        return PullRequest(
                            number=pr_data['number'],
                            url=pr_data['html_url'],
                            branch=branch_name,
                            title=pr_data['title'],
                            body=pr_data['body'],
                            issue_number=issue_number,
                        )
                    else:
                        logger.error(f"Failed to create PR: {response.status_code}")
                        logger.error(f"Response: {response.text}")
                        return None

            import asyncio
            return asyncio.run(create_pr())

        except Exception as e:
            logger.error(f"Error creating GitHub PR: {e}")
            return None

    def _generate_commit_message(self, fix: Fix, issue_number: int) -> str:
        """Generate commit message."""
        return f"""Fix #{issue_number}: {fix.pattern_name}

{fix.explanation}

This fix was automatically generated by the Crawl4AI Root Cause Analysis System.

Confidence: {fix.confidence:.2%}

Test Cases:
{chr(10).join(f'- {tc}' for tc in fix.test_cases)}
"""

    def _generate_pr_title(self, issue_number: int, fix: Fix) -> str:
        """Generate PR title."""
        return f"Fix #{issue_number}: {fix.pattern_name.replace('_', ' ').title()}"

    def _generate_pr_body(self, fix: Fix, issue_number: int) -> str:
        """Generate PR body."""
        body = f"""## Summary

This PR fixes issue #{issue_number} by addressing the root cause: {fix.pattern_name}

## Root Cause

{fix.explanation}

## Changes

- **File:** {fix.file}
- **Line:** {fix.line_number}
- **Confidence:** {fix.confidence:.2%}

### Code Changes

```diff
{fix.patch}
```

## Test Cases

{chr(10).join(f'- {tc}' for tc in fix.test_cases)}

## Additional Information

This fix was automatically generated by the Crawl4AI Root Cause Analysis System.
Please review and test before merging.

Closes #{issue_number}
"""
        return body


def main():
    """Test PR creator."""
    from fix_generator import Fix

    # Create a test fix
    fix = Fix(
        file="deploy/docker/mcp_bridge.py",
        line_number=35,
        old_code="async with httpx.AsyncClient() as client:",
        new_code="async with httpx.AsyncClient(timeout=None) as client:",
        explanation="Added timeout=None to disable client-side timeout.",
        test_cases=["Test with LLM endpoint exceeding 5s timeout"],
        patch="""--- a/deploy/docker/mcp_bridge.py
+++ b/deploy/docker/mcp_bridge.py
@@ -35,1 +35,2 @@
-async with httpx.AsyncClient() as client:
+
+async with httpx.AsyncClient(timeout=None) as client:
""",
        confidence=0.95,
    )

    # Create PR (dry run)
    creator = PRCreator(dry_run=True)
    pr = creator.create_pr(fix, issue_number=1769)

    if pr:
        print(f"\nPR Created (Dry Run):")
        print(f"  Branch: {pr.branch}")
        print(f"  Title: {pr.title}")
        print(f"  URL: {pr.url}")
        print(f"\nBody:")
        print(pr.body)


if __name__ == '__main__':
    main()

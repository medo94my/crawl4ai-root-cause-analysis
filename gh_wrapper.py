"""
GitHub CLI Wrapper - Uses gh CLI for GitHub operations.

This module wraps GitHub CLI (gh) operations for use in the root cause
analysis system. Uses existing gh authentication.

Usage:
    from gh_wrapper import GitHubCLI

    gh = GitHubCLI()
    pr_url = gh.create_pr(title, body, branch)
"""

import subprocess
import json
import logging
from typing import Dict, Optional, List, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class GitHubCLI:
    """Wrapper for GitHub CLI (gh) operations."""

    def __init__(self, owner: str = "unclecode", repo: str = "crawl4ai"):
        """
        Initialize GitHub CLI wrapper.

        Args:
            owner: Repository owner (username or organization)
            repo: Repository name
        """
        self.owner = owner
        self.repo = repo
        self.full_repo = f"{owner}/{repo}"

        # Verify gh CLI is available and authenticated
        self._verify_gh_auth()

        logger.info(f"GitHubCLI initialized for {self.full_repo}")

    def _verify_gh_auth(self):
        """Verify that gh CLI is installed and authenticated."""
        try:
            result = subprocess.run(
                ['gh', 'auth', 'status'],
                capture_output=True,
                text=True,
                check=True,
            )

            if 'Logged in' in result.stdout:
                logger.info("✅ GitHub CLI authenticated")
                return True
            else:
                logger.warning("⚠️  GitHub CLI not authenticated")
                return False

        except FileNotFoundError:
            logger.error("❌ GitHub CLI not found. Install with: https://cli.github.com/")
            raise RuntimeError("GitHub CLI not installed")
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ GitHub CLI error: {e}")
            raise RuntimeError("GitHub CLI authentication failed")

    def _run_command(self, args: List[str], json_output: bool = True) -> Any:
        """
        Run a gh CLI command.

        Args:
            args: Command arguments
            json_output: Parse output as JSON

        Returns:
            Command output (parsed JSON or text)
        """
        cmd = ['gh'] + args

        # Don't add --json flag - it should already be in args if needed

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )

            if json_output:
                return json.loads(result.stdout)
            else:
                return result.stdout

        except subprocess.CalledProcessError as e:
            logger.error(f"Command failed: {' '.join(cmd)}")
            logger.error(f"stderr: {e.stderr}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            raise

    def get_issues(
        self,
        state: str = "open",
        limit: int = 100,
        labels: Optional[List[str]] = None,
    ) -> List[Dict]:
        """
        Get list of issues from repository.

        Args:
            state: Issue state (open, closed, all)
            limit: Maximum number of issues to return
            labels: Filter by labels

        Returns:
            List of issue dictionaries
        """
        # Specify JSON fields required for issue list
        json_fields = 'number,title,body,state,author,labels,createdAt,updatedAt,url'
        args = [
            'issue', 'list',
            '--repo', self.full_repo,
            '--limit', str(limit),
            '--json', json_fields,
        ]

        if state:
            args.extend(['--state', state])

        if labels:
            args.extend(['--label', ','.join(labels)])

        issues = self._run_command(args, json_output=True)

        # Convert to expected format
        return [
            {
                'id': issue.get('id', issue['number']),  # gh issue list doesn't include id field
                'number': issue['number'],
                'title': issue['title'],
                'body': issue.get('body') or '',
                'state': issue['state'],
                'author': issue['author']['login'],
                'labels': [label['name'] for label in issue.get('labels', [])],
                'created_at': issue.get('createdAt', ''),
                'updated_at': issue.get('updatedAt', ''),
                'html_url': issue.get('url', f"https://github.com/{self.owner}/{self.repo}/issues/{issue['number']}"),
                'comments_url': f"https://api.github.com/repos/{self.owner}/{self.repo}/issues/{issue['number']}/comments",
            }
            for issue in issues
        ]

    def get_issue(self, issue_number: int) -> Optional[Dict]:
        """
        Get a specific issue.

        Args:
            issue_number: Issue number

        Returns:
            Issue dictionary or None
        """
        # Specify JSON fields required for issue view
        json_fields = 'number,title,body,state,author,labels,createdAt,updatedAt,url'
        args = ['issue', 'view', str(issue_number), '--repo', self.full_repo, '--json', json_fields]
        issue = self._run_command(args, json_output=True)

        return {
            'id': issue.get('id', 0),
            'number': issue['number'],
            'title': issue['title'],
            'body': issue.get('body') or '',
            'state': issue['state'],
            'author': issue['author']['login'],
            'labels': [label['name'] for label in issue.get('labels', [])],
            'created_at': issue['createdAt'],
            'updated_at': issue['updatedAt'],
            'html_url': issue['url'],
            'comments_url': f"https://api.github.com/repos/{self.owner}/{self.repo}/issues/{issue_number}/comments",
        }

    def create_pr(
        self,
        title: str,
        body: str,
        head: str,
        base: str = "main",
        labels: Optional[List[str]] = None,
        draft: bool = False,
    ) -> Dict:
        """
        Create a pull request.

        Args:
            title: PR title
            body: PR body/description
            head: Branch name (e.g., "username:fix-branch")
            base: Base branch (default: main)
            labels: List of labels to add
            draft: Create as draft PR

        Returns:
            Created PR information
        """
        args = [
            'pr', 'create',
            '--title', title,
            '--body', body,
            '--repo', self.full_repo,
            '--base', base,
            '--head', head,
        ]

        if draft:
            args.append('--draft')

        if labels:
            args.extend(['--label', ','.join(labels)])

        logger.info(f"Creating PR: {title}")

        result = self._run_command(args, json_output=False)

        # Extract PR URL from output
        pr_url = result.strip()
        pr_number = pr_url.split('/')[-1]

        return {
            'number': int(pr_number),
            'url': pr_url,
            'title': title,
            'body': body,
            'branch': head,
        }

    def create_branch(self, branch_name: str, base: str = "main") -> bool:
        """
        Create a new branch using git.

        Args:
            branch_name: Name of new branch
            base: Base branch to branch from

        Returns:
            True if successful
        """
        import os

        try:
            # Fetch latest
            subprocess.run(
                ['git', 'fetch', 'origin'],
                check=True,
                capture_output=True,
            )

            # Checkout base branch
            subprocess.run(
                ['git', 'checkout', base],
                check=True,
                capture_output=True,
            )

            # Pull latest
            subprocess.run(
                ['git', 'pull', 'origin', base],
                check=True,
                capture_output=True,
            )

            # Create and checkout new branch
            subprocess.run(
                ['git', 'checkout', '-b', branch_name],
                check=True,
                capture_output=True,
            )

            logger.info(f"✅ Created branch: {branch_name}")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Failed to create branch: {e}")
            return False

    def commit_changes(self, message: str) -> bool:
        """
        Commit staged changes.

        Args:
            message: Commit message

        Returns:
            True if successful
        """
        try:
            # Stage all changes
            subprocess.run(
                ['git', 'add', '.'],
                check=True,
                capture_output=True,
            )

            # Commit
            subprocess.run(
                ['git', 'commit', '-m', message],
                check=True,
                capture_output=True,
            )

            logger.info("✅ Committed changes")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Failed to commit: {e}")
            return False

    def push_branch(self, branch_name: str) -> bool:
        """
        Push branch to remote.

        Args:
            branch_name: Branch name to push

        Returns:
            True if successful
        """
        try:
            subprocess.run(
                ['git', 'push', '-u', 'origin', branch_name],
                check=True,
                capture_output=True,
            )

            logger.info(f"✅ Pushed branch: {branch_name}")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Failed to push branch: {e}")
            return False


def main():
    """Test GitHub CLI wrapper."""
    print("Testing GitHub CLI wrapper...\n")

    # Create GitHub CLI instance
    gh = GitHubCLI()

    # Test 1: Get issues
    print("1. Testing issue listing...")
    issues = gh.get_issues(state='open', limit=3)
    print(f"   Found {len(issues)} issues")
    for issue in issues[:2]:
        print(f"   - #{issue['number']}: {issue['title'][:50]}...")

    # Test 2: Get specific issue
    print("\n2. Testing specific issue fetch...")
    issue = gh.get_issue(1769)
    if issue:
        print(f"   ✓ Found issue #{issue['number']}: {issue['title'][:50]}...")

    print("\n✅ GitHub CLI wrapper working correctly!")


if __name__ == '__main__':
    main()

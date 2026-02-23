"""
GitHub Issues Watcher - Polls GitHub for new issues and triggers analysis pipeline.

This module implements the GitHub polling mechanism that:
1. Polls the Crawl4AI repository for new issues every 5 minutes
2. Filters issues by labels and creation time
3. Triggers the analysis pipeline for new issues
4. Maintains state to avoid reprocessing issues

Usage:
    python issue_watcher.py
"""

import os
import time
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict, field

import httpx

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class GitHubIssue:
    """Structured representation of a GitHub issue."""
    id: int
    number: int
    title: str
    body: str
    state: str
    author: str
    labels: List[str]
    created_at: str
    updated_at: str
    html_url: str
    comments_url: str
    comments: list = field(default_factory=list)


class GitHubAPI:
    """Wrapper for GitHub API interactions."""

    def __init__(self, token: Optional[str] = None):
        """
        Initialize GitHub API client.

        Args:
            token: GitHub personal access token. If None, uses GITHUB_TOKEN env var.
        """
        self.token = token or os.getenv('GITHUB_TOKEN')
        self.base_url = "https://api.github.com"
        self.headers = {}
        if self.token:
            self.headers['Authorization'] = f'token {self.token}'
        self.headers['Accept'] = 'application/vnd.github.v3+json'

    async def get_issues(
        self,
        repo: str = "unclecode/crawl4ai",
        state: str = "open",
        since: Optional[str] = None,
        labels: Optional[List[str]] = None,
    ) -> List[GitHubIssue]:
        """
        Fetch issues from GitHub repository.

        Args:
            repo: Repository in format "owner/repo"
            state: Issue state (open, closed, all)
            since: ISO 8601 timestamp to filter issues created after
            labels: List of label names to filter by

        Returns:
            List of GitHubIssue objects
        """
        url = f"{self.base_url}/repos/{repo}/issues"
        params = {
            "state": state,
            "sort": "created",
            "direction": "desc",
            "per_page": 100,
        }
        if since:
            params['since'] = since
        if labels:
            params['labels'] = ','.join(labels)

        issues = []
        async with httpx.AsyncClient(headers=self.headers) as client:
            page = 1
            while True:
                params['page'] = page
                response = await client.get(url, params=params)

                if response.status_code != 200:
                    logger.error(f"Failed to fetch issues: {response.status_code}")
                    break

                data = response.json()
                if not data:
                    break

                for item in data:
                    if 'pull_request' in item:
                        # Skip pull requests
                        continue

                    issue = GitHubIssue(
                        id=item['id'],
                        number=item['number'],
                        title=item['title'],
                        body=item['body'] or '',
                        state=item['state'],
                        author=item['user']['login'],
                        labels=[label['name'] for label in item['labels']],
                        created_at=item['created_at'],
                        updated_at=item['updated_at'],
                        html_url=item['html_url'],
                        comments_url=item['comments_url'],
                    )
                    issues.append(issue)

                page += 1
                # Stop if we've fetched all issues since our last check
                if since and len(issues) > 0:
                    if datetime.fromisoformat(issues[-1].created_at.replace('Z', '+00:00')) < datetime.fromisoformat(since.replace('Z', '+00:00')):
                        break

        return issues


class IssueWatcher:
    """Main watcher that polls GitHub and triggers analysis."""

    def __init__(
        self,
        repo: str = "unclecode/crawl4ai",
        poll_interval: int = 300,  # 5 minutes
        state_file: str = "last_check.json",
        labels: Optional[List[str]] = None,
    ):
        """
        Initialize issue watcher.

        Args:
            repo: Repository in format "owner/repo"
            poll_interval: Seconds between polls
            state_file: File to store last check timestamp
            labels: List of label names to filter issues by
        """
        self.repo = repo
        self.poll_interval = poll_interval
        self.state_file = state_file
        self.labels = labels or ['bug', 'Bug', 'enhancement']  # Focus on bugs
        self.api = GitHubAPI()
        self.last_check = self._load_state()

    def _load_state(self) -> Optional[datetime]:
        """Load last check timestamp from state file."""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                    return datetime.fromisoformat(data['last_check'])
            except Exception as e:
                logger.warning(f"Failed to load state: {e}")
        return None

    def _save_state(self, timestamp: datetime):
        """Save last check timestamp to state file."""
        try:
            with open(self.state_file, 'w') as f:
                json.dump({'last_check': timestamp.isoformat()}, f)
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    async def check_for_new_issues(self) -> List[GitHubIssue]:
        """
        Check for new issues since last check.

        Returns:
            List of new GitHubIssue objects
        """
        since = None
        if self.last_check:
            since = self.last_check.isoformat()

        issues = await self.api.get_issues(
            repo=self.repo,
            state='open',
            since=since,
            labels=self.labels,
        )

        # Filter issues that are actually new
        new_issues = []
        if self.last_check:
            cutoff = self.last_check
            new_issues = [
                issue for issue in issues
                if datetime.fromisoformat(issue.created_at.replace('Z', '+00:00')) > cutoff
            ]

        # Update last check time
        self.last_check = datetime.now()
        self._save_state(self.last_check)

        return new_issues

    def should_analyze(self, issue: GitHubIssue) -> bool:
        """
        Determine if an issue should be analyzed.

        Args:
            issue: GitHubIssue to evaluate

        Returns:
            True if issue should be analyzed
        """
        # Skip if no description
        if not issue.body or len(issue.body) < 50:
            logger.debug(f"Skipping issue #{issue.number} - insufficient description")
            return False

        # Skip if already has 'automated-fix' label
        if 'automated-fix' in issue.labels:
            logger.debug(f"Skipping issue #{issue.number} - already has automated-fix label")
            return False

        return True

    async def process_issue(self, issue: GitHubIssue):
        """
        Process a single issue.

        Args:
            issue: GitHubIssue to process
        """
        logger.info(f"Processing issue #{issue.number}: {issue.title}")

        # This is where we would call the ingestion engine
        # For now, just log the issue
        logger.info(f"Issue URL: {issue.html_url}")
        logger.info(f"Author: {issue.author}")
        logger.info(f"Labels: {issue.labels}")
        logger.info(f"Body length: {len(issue.body)} chars")

        # TODO: Call issue_ingestion.parse_issue(issue)
        # TODO: Call pattern_recognition.match_pattern(parsed_issue)
        # TODO: Call root_cause_analyzer.analyze(parsed_issue, pattern)
        # TODO: Call fix_generator.generate_fix(root_cause)
        # TODO: Call pr_creator.create_pr(fix)

    async def run(self):
        """Main run loop."""
        logger.info(f"Starting issue watcher for {self.repo}")
        logger.info(f"Polling every {self.poll_interval} seconds")

        while True:
            try:
                logger.info("Checking for new issues...")
                new_issues = await self.check_for_new_issues()

                if new_issues:
                    logger.info(f"Found {len(new_issues)} new issues")
                    for issue in new_issues:
                        if self.should_analyze(issue):
                            await self.process_issue(issue)
                        else:
                            logger.debug(f"Skipping issue #{issue.number}")
                else:
                    logger.info("No new issues found")

            except Exception as e:
                logger.error(f"Error in watcher loop: {e}", exc_info=True)

            logger.info(f"Waiting {self.poll_interval} seconds before next check...")
            await httpx.AsyncClient().aclose()  # Close any open connections
            time.sleep(self.poll_interval)


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="GitHub Issues Watcher for Crawl4AI")
    parser.add_argument(
        '--repo',
        default='unclecode/crawl4ai',
        help='Repository to watch (format: owner/repo)'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=300,
        help='Poll interval in seconds (default: 300)'
    )
    parser.add_argument(
        '--once',
        action='store_true',
        help='Run once and exit'
    )

    args = parser.parse_args()

    watcher = IssueWatcher(
        repo=args.repo,
        poll_interval=args.interval,
    )

    if args.once:
        logger.info("Running once...")
        new_issues = await watcher.check_for_new_issues()
        logger.info(f"Found {len(new_issues)} new issues")
        for issue in new_issues:
            if watcher.should_analyze(issue):
                await watcher.process_issue(issue)
    else:
        await watcher.run()


if __name__ == '__main__':
    import asyncio
    asyncio.run(main())

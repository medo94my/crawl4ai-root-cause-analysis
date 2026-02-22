"""
Main Orchestration Script - Coordinates root cause analysis pipeline using GitHub CLI.

This script orchestrates the complete automated root cause analysis pipeline
using the gh CLI for GitHub operations.

Usage:
    python3 main_gh.py [--watch] [--issue ISSUE_NUMBER] [--dry-run]
"""

import argparse
import asyncio
import logging
from typing import Optional

from issue_ingestion import IssueIngestionEngine
from pattern_recognition import PatternRecognitionEngine
from root_cause_analyzer import RootCauseAnalyzer
from fix_generator import FixGenerator
from gh_wrapper import GitHubCLI

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RootCauseAnalysisPipeline:
    """Main pipeline orchestrator using GitHub CLI."""

    def __init__(
        self,
        repo_path: str = "/root/.openclaw/workspace/crawl4ai-repo",
        owner: str = "unclecode",
        repo: str = "crawl4ai",
        dry_run: bool = True,
        confidence_threshold: float = 0.7,
    ):
        """
        Initialize pipeline.

        Args:
            repo_path: Path to Crawl4AI repository
            owner: Repository owner (username or organization)
            repo: Repository name
            dry_run: If True, don't create actual PRs
            confidence_threshold: Minimum confidence to proceed with fix
        """
        self.repo_path = repo_path
        self.owner = owner
        self.repo = repo
        self.dry_run = dry_run
        self.confidence_threshold = confidence_threshold

        # Initialize components
        self.gh = GitHubCLI(owner=owner, repo=repo)
        self.ingestion_engine = IssueIngestionEngine()
        self.pattern_engine = PatternRecognitionEngine()
        self.root_cause_analyzer = RootCauseAnalyzer(repo_path)
        self.fix_generator = FixGenerator()

        logger.info("Root Cause Analysis Pipeline initialized (GitHub CLI mode)")
        logger.info(f"Repo: {owner}/{repo}")
        logger.info(f"Path: {repo_path}")
        logger.info(f"Dry run: {dry_run}")
        logger.info(f"Confidence threshold: {confidence_threshold:.2%}")

    async def process_issue(self, issue_number: int) -> bool:
        """
        Process a single issue through the complete pipeline.

        Args:
            issue_number: GitHub issue number

        Returns:
            True if fix generated successfully, False otherwise
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"Processing issue #{issue_number}")
        logger.info(f"{'='*80}\n")

        # Step 1: Fetch issue using gh CLI
        logger.info("Step 1: Fetching issue...")
        issue_data = self.gh.get_issue(issue_number)

        if not issue_data:
            logger.error(f"Failed to fetch issue #{issue_number}")
            return False

        # Convert to GitHubIssue format
        from issue_watcher import GitHubIssue
        github_issue = GitHubIssue(
            id=issue_data['id'],
            number=issue_data['number'],
            title=issue_data['title'],
            body=issue_data['body'],
            state=issue_data['state'],
            author=issue_data['author'],
            labels=issue_data['labels'],
            created_at=issue_data['created_at'],
            updated_at=issue_data['updated_at'],
            html_url=issue_data['html_url'],
            comments_url=issue_data['comments_url'],
        )

        # Step 2: Ingest and parse issue
        logger.info("Step 2: Ingesting and parsing issue...")
        parsed_issue = self.ingestion_engine.parse_issue(github_issue)
        logger.info(f"Issue type: {parsed_issue.issue_type}")
        logger.info(f"Priority: {parsed_issue.priority}")
        logger.info(f"Keywords: {parsed_issue.keywords}")

        # Skip non-bug issues
        if parsed_issue.issue_type != 'bug':
            logger.info(f"Skipping non-bug issue (type: {parsed_issue.issue_type})")
            return False

        # Step 3: Recognize patterns
        logger.info("Step 3: Recognizing patterns...")
        pattern_matches = self.pattern_engine.match_pattern(parsed_issue)

        if not pattern_matches:
            logger.info("No patterns matched for this issue")
            return False

        logger.info(f"Found {len(pattern_matches)} pattern match(es)")

        # Process only best match
        best_match = pattern_matches[0]
        logger.info(f"Best match: {best_match.name} (confidence: {best_match.confidence:.2%})")

        if best_match.confidence < self.confidence_threshold:
            logger.info(f"Confidence {best_match.confidence:.2%} below threshold {self.confidence_threshold:.2%}")
            return False

        # Step 4: Analyze root cause
        logger.info("Step 4: Analyzing root cause...")
        root_cause = self.root_cause_analyzer.analyze(parsed_issue, best_match)

        if not root_cause:
            logger.error("Failed to identify root cause")
            return False

        logger.info(f"Root cause: {root_cause.file}:{root_cause.line_number}")
        logger.info(f"Function: {root_cause.function}")
        logger.info(f"Confidence: {root_cause.confidence:.2%}")

        # Step 5: Generate fix
        logger.info("Step 5: Generating fix...")
        fix = self.fix_generator.generate_fix(root_cause)

        if not fix:
            logger.error("Failed to generate fix")
            return False

        logger.info(f"Fix generated for {fix.file}:{fix.line_number}")
        logger.info(f"Valid: {self.fix_generator.validate_fix(fix)}")

        # Step 6: Create PR
        if self.dry_run:
            logger.info("Step 6: Skipping PR creation (dry run mode)")
            logger.info("\nWould create PR:")
            logger.info(f"  Title: Fix #{issue_number}: {fix.pattern_name}")
            logger.info(f"  Branch: fix/issue-{issue_number}-{fix.pattern_name}")
            logger.info(f"  Labels: bug, automated-fix")
        else:
            logger.info("Step 6: Creating pull request...")
            branch_name = f"fix/issue-{issue_number}-{fix.pattern_name}"

            # Create branch
            if not self.gh.create_branch(branch_name):
                logger.error("Failed to create branch")
                return False

            # Apply patch
            if not self._apply_patch(fix):
                logger.error("Failed to apply patch")
                return False

            # Commit changes
            commit_message = self._generate_commit_message(fix, issue_number)
            if not self.gh.commit_changes(commit_message):
                logger.error("Failed to commit changes")
                return False

            # Push branch
            if not self.gh.push_branch(branch_name):
                logger.error("Failed to push branch")
                return False

            # Create PR
            pr = self.gh.create_pr(
                title=f"Fix #{issue_number}: {fix.pattern_name}",
                body=self._generate_pr_body(fix, issue_number),
                head=branch_name,
                base="main",
                labels=['bug', 'automated-fix'],
            )

            logger.info(f"\n{'='*80}")
            logger.info(f"SUCCESS! PR created: {pr['url']}")
            logger.info(f"{'='*80}\n")

        return True

    def _apply_patch(self, fix) -> bool:
        """Apply patch to file."""
        import subprocess
        import os

        try:
            # Create patch file
            patch_file = os.path.join(self.repo_path, '.fix.patch')
            with open(patch_file, 'w', encoding='utf-8') as f:
                f.write(fix.patch)

            # Apply patch
            subprocess.run(
                ['git', 'apply', patch_file],
                cwd=self.repo_path,
                check=True,
                capture_output=True,
            )

            # Clean up
            os.remove(patch_file)

            logger.info(f"✅ Applied patch to {fix.file}")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Failed to apply patch: {e}")
            return False

    def _generate_commit_message(self, fix, issue_number: int) -> str:
        """Generate commit message."""
        return f"""Fix #{issue_number}: {fix.pattern_name}

{fix.explanation}

This fix was automatically generated by Crawl4AI Root Cause Analysis System.

Confidence: {fix.confidence:.2%}

Test Cases:
{chr(10).join(f'- {tc}' for tc in fix.test_cases)}
"""

    def _generate_pr_body(self, fix, issue_number: int) -> str:
        """Generate PR body."""
        return f"""## Summary

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

This fix was automatically generated by Crawl4AI Root Cause Analysis System
using GitHub CLI.

Please review and test before merging.

Closes #{issue_number}
"""

    async def run_single_mode(self, issue_number: int):
        """Run in single mode, processing one specific issue."""
        logger.info(f"Running in single mode for issue #{issue_number}")
        await self.process_issue(issue_number)

    async def run_watch_mode(self):
        """Run in watch mode, continuously polling for new issues."""
        logger.info("Starting watch mode...")
        logger.info("Polling for new issues every 5 minutes")

        last_processed = set()

        while True:
            try:
                # Fetch open issues
                issues = self.gh.get_issues(state='open', limit=50)

                # Find new issues
                new_issues = [
                    issue for issue in issues
                    if issue['number'] not in last_processed
                ]

                if new_issues:
                    logger.info(f"Found {len(new_issues)} new issue(s)")

                    for issue in new_issues:
                        last_processed.add(issue['number'])
                        await self.process_issue(issue['number'])
                else:
                    logger.info("No new issues found")

            except Exception as e:
                logger.error(f"Error in watch loop: {e}", exc_info=True)

            # Wait before next check
            await asyncio.sleep(300)  # 5 minutes


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Crawl4AI Automated Root Cause Analysis Pipeline (GitHub CLI mode)"
    )
    parser.add_argument(
        '--watch',
        action='store_true',
        help='Run in watch mode (continuously poll for new issues)'
    )
    parser.add_argument(
        '--issue',
        type=int,
        help='Process a specific issue number'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        default=True,
        help='Dry run mode (don\'t create actual PRs)'
    )
    parser.add_argument(
        '--confidence',
        type=float,
        default=0.7,
        help='Minimum confidence threshold (default: 0.7)'
    )
    parser.add_argument(
        '--repo-path',
        type=str,
        default='/root/.openclaw/workspace/crawl4ai-repo',
        help='Path to Crawl4AI repository'
    )
    parser.add_argument(
        '--owner',
        type=str,
        default='medo94my',
        help='Repository owner (default: medo94my)'
    )
    parser.add_argument(
        '--repo',
        type=str,
        default='crawl4ai',
        help='Repository name (default: crawl4ai)'
    )

    args = parser.parse_args()

    # Create pipeline
    pipeline = RootCauseAnalysisPipeline(
        repo_path=args.repo_path,
        owner=args.owner,
        repo=args.repo,
        dry_run=args.dry_run,
        confidence_threshold=args.confidence,
    )

    # Run in appropriate mode
    if args.watch:
        await pipeline.run_watch_mode()
    elif args.issue:
        await pipeline.run_single_mode(args.issue)
    else:
        parser.print_help()
        logger.info("\nPlease specify either --watch or --issue ISSUE_NUMBER")


if __name__ == '__main__':
    asyncio.run(main())

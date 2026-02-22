"""
Main Orchestration Script - Coordinates the root cause analysis pipeline.

This script orchestrates the complete automated root cause analysis pipeline:
1. Watch for new GitHub issues
2. Ingest and parse issues
3. Recognize patterns
4. Analyze root causes
5. Generate fixes
6. Create pull requests

Usage:
    python main.py [--watch] [--issue ISSUE_NUMBER] [--dry-run]
"""

import argparse
import asyncio
import logging
from typing import Optional

from issue_watcher import IssueWatcher
from issue_ingestion import IssueIngestionEngine
from pattern_recognition import PatternRecognitionEngine
from root_cause_analyzer import RootCauseAnalyzer
from fix_generator import FixGenerator
from pr_creator import PRCreator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RootCauseAnalysisPipeline:
    """Main pipeline orchestrator."""

    def __init__(
        self,
        repo_path: str = "/root/.openclaw/workspace/crawl4ai-repo",
        dry_run: bool = True,
        confidence_threshold: float = 0.7,
    ):
        """
        Initialize pipeline.

        Args:
            repo_path: Path to Crawl4AI repository
            dry_run: If True, don't create actual PRs
            confidence_threshold: Minimum confidence to proceed with fix
        """
        self.repo_path = repo_path
        self.dry_run = dry_run
        self.confidence_threshold = confidence_threshold

        # Initialize components
        self.watcher = IssueWatcher()
        self.ingestion_engine = IssueIngestionEngine()
        self.pattern_engine = PatternRecognitionEngine()
        self.root_cause_analyzer = RootCauseAnalyzer(repo_path)
        self.fix_generator = FixGenerator()
        self.pr_creator = PRCreator(repo_path, dry_run=dry_run)

        logger.info("Root Cause Analysis Pipeline initialized")
        logger.info(f"Repo path: {repo_path}")
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

        # Step 1: Fetch issue
        logger.info("Step 1: Fetching issue...")
        github_issue = await self._fetch_issue(issue_number)
        if not github_issue:
            logger.error(f"Failed to fetch issue #{issue_number}")
            return False

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
        logger.info("Step 6: Creating pull request...")
        pr = self.pr_creator.create_pr(fix, issue_number)

        if not pr:
            logger.error("Failed to create PR")
            return False

        logger.info(f"\n{'='*80}")
        logger.info(f"SUCCESS! PR created: {pr.url}")
        logger.info(f"{'='*80}\n")

        return True

    async def _fetch_issue(self, issue_number: int):
        """Fetch a specific issue from GitHub."""
        from issue_watcher import GitHubAPI

        api = GitHubAPI()
        issues = await api.get_issues(repo='unclecode/crawl4ai', state='open')

        for issue in issues:
            if issue.number == issue_number:
                return issue

        return None

    async def run_watch_mode(self):
        """Run in watch mode, continuously polling for new issues."""
        logger.info("Starting watch mode...")

        while True:
            try:
                # Check for new issues
                new_issues = await self.watcher.check_for_new_issues()

                if new_issues:
                    logger.info(f"Found {len(new_issues)} new issue(s)")

                    for issue in new_issues:
                        if self.watcher.should_analyze(issue):
                            await self.process_issue(issue.number)

            except Exception as e:
                logger.error(f"Error in watch loop: {e}", exc_info=True)

            # Wait before next check
            await asyncio.sleep(self.watcher.poll_interval)

    async def run_single_mode(self, issue_number: int):
        """Run in single mode, processing one specific issue."""
        logger.info(f"Running in single mode for issue #{issue_number}")
        await self.process_issue(issue_number)


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Crawl4AI Automated Root Cause Analysis Pipeline"
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

    args = parser.parse_args()

    # Create pipeline
    pipeline = RootCauseAnalysisPipeline(
        repo_path=args.repo_path,
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

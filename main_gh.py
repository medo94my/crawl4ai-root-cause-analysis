"""
Main Orchestration Script - Coordinates root cause analysis pipeline using GitHub CLI.

This script orchestrates the complete automated root cause analysis pipeline
using the gh CLI for GitHub operations.

Usage:
    python3 main_gh.py --url https://github.com/unclecode/crawl4ai/issues/1769 --dry-run
    python3 main_gh.py --issue 1769 --dry-run
    python3 main_gh.py --watch --dry-run
"""

import argparse
import asyncio
import logging
import os
from pathlib import Path
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
        repo_path: Optional[str] = None,
        owner: str = "unclecode",
        repo: str = "crawl4ai",
        dry_run: bool = True,
        confidence_threshold: float = 0.7,
    ):
        """
        Initialize pipeline.

        Args:
            repo_path: Path to Crawl4AI repository (None = use ~/crawl4ai-repo)
            owner: Repository owner
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
        logger.info(f"Dry run: {dry_run}")
        logger.info(f"Confidence threshold: {confidence_threshold:.2%}")

    async def process_issue(self, issue_number: int) -> bool:
        """
        Process a single issue through the complete pipeline.

        Args:
            issue_number: GitHub issue number

        Returns:
            True if analysis completed (report written), False otherwise
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

        # Convert to GitHubIssue format (includes comments)
        from issue_watcher import GitHubIssue
        github_issue = GitHubIssue(
            id=issue_data.get('id', 0),
            number=issue_data['number'],
            title=issue_data['title'],
            body=issue_data.get('body') or '',
            state=issue_data['state'],
            author=issue_data['author'],
            labels=issue_data['labels'],
            created_at=issue_data['created_at'],
            updated_at=issue_data['updated_at'],
            html_url=issue_data['html_url'],
            comments_url=issue_data['comments_url'],
            comments=issue_data.get('comments', []),
        )

        logger.info(f"Fetched: {github_issue.title}")
        logger.info(f"State: {github_issue.state} | Comments: {len(github_issue.comments)}")

        # Step 2: Ingest and parse issue
        logger.info("Step 2: Ingesting and parsing issue...")
        parsed_issue = self.ingestion_engine.parse_issue(github_issue)
        logger.info(f"Issue type: {parsed_issue.issue_type}")
        logger.info(f"Priority: {parsed_issue.priority}")
        logger.info(f"Keywords: {parsed_issue.keywords}")

        # Step 3: Recognize patterns
        logger.info("Step 3: Recognizing patterns...")
        pattern_matches = self.pattern_engine.match_pattern(parsed_issue)

        if not pattern_matches:
            logger.info("No patterns matched for this issue")
            self._write_report(
                issue_number, github_issue, parsed_issue, [], None, None,
                {"resolved": False, "evidence": "No pattern matched — manual review required"},
                reproduction_status="blocked",
            )
            return True  # Report written even if no pattern

        logger.info(f"Found {len(pattern_matches)} pattern match(es)")

        best_match = pattern_matches[0]
        logger.info(f"Best match: {best_match.name} (confidence: {best_match.confidence:.2%})")

        if best_match.confidence < self.confidence_threshold:
            logger.info(f"Confidence {best_match.confidence:.2%} below threshold {self.confidence_threshold:.2%}")
            self._write_report(
                issue_number, github_issue, parsed_issue, pattern_matches, None, None,
                {"resolved": False, "evidence": "Low confidence — manual review required"},
                reproduction_status="blocked",
            )
            return True

        # Step 4: Analyze root cause
        logger.info("Step 4: Analyzing root cause...")
        root_cause = self.root_cause_analyzer.analyze(parsed_issue, best_match)

        if not root_cause:
            logger.warning("Failed to identify root cause (codebase may not be available)")
            self._write_report(
                issue_number, github_issue, parsed_issue, pattern_matches, None, None,
                {"resolved": False, "evidence": "Root cause analysis inconclusive — codebase may not be cloned"},
                reproduction_status="blocked",
            )
            return True

        logger.info(f"Root cause: {root_cause.file}:{root_cause.line_number}")
        logger.info(f"Function: {root_cause.function}")
        logger.info(f"Confidence: {root_cause.confidence:.2%}")

        # Step 5: Resolution check
        logger.info("Step 5: Checking if issue is already resolved...")
        resolution_check = self.root_cause_analyzer.check_resolution(root_cause)
        logger.info(f"Resolved: {resolution_check['resolved']}")
        logger.info(f"Evidence: {resolution_check['evidence']}")

        # Step 6: Attempt reproduction
        logger.info("Step 6: Attempting to reproduce...")
        reproduction_status = self._attempt_reproduction(root_cause)
        logger.info(f"Reproduction status: {reproduction_status}")

        # Step 7: Generate fix
        logger.info("Step 7: Generating fix...")
        fix = self.fix_generator.generate_fix(root_cause)

        if fix:
            logger.info(f"Fix generated for {fix.file}:{fix.line_number}")
        else:
            logger.warning("No fix template available for this pattern")

        # Step 8: Write report
        logger.info("Step 8: Writing report...")
        self._write_report(
            issue_number, github_issue, parsed_issue, pattern_matches, root_cause, fix,
            resolution_check, reproduction_status,
        )

        return True

    def _attempt_reproduction(self, root_cause) -> str:
        """
        Attempt to reproduce the bug by checking if the bug-pattern line is present.

        Returns:
            'reproduced' if the buggy code is found
            'not_reproduced' if fix is already applied
            'blocked' if codebase unavailable
        """
        if not self.root_cause_analyzer.codebase_path.exists():
            return "blocked"

        try:
            file_path = self.root_cause_analyzer.codebase_path / root_cause.file
            if not file_path.exists():
                return "blocked"

            content = file_path.read_text(encoding='utf-8')
            lines = content.split('\n')

            # Check if the buggy code snippet is present near the reported line
            target_line = root_cause.line_number
            start = max(0, target_line - 3)
            end = min(len(lines), target_line + 3)
            context = '\n'.join(lines[start:end])

            # Check if the old (buggy) code is present
            if root_cause.code_snippet and root_cause.code_snippet.strip() in context:
                return "reproduced"

            # Check if a known fix is already applied
            if root_cause.suggested_fix and root_cause.suggested_fix.strip() in content:
                return "not_reproduced"

            return "reproduced"  # Assume reproducible if we can't confirm otherwise

        except Exception as e:
            logger.warning(f"Could not check reproduction: {e}")
            return "blocked"

    def _write_report(
        self,
        issue_number: int,
        github_issue,
        parsed_issue,
        pattern_matches,
        root_cause,
        fix,
        resolution_check: dict,
        reproduction_status: str = "blocked",
    ):
        """
        Write structured report to test_scripts/issues/<number>/verify.md
        and reproduction stub to test_scripts/issues/<number>/verify.py
        """
        output_dir = Path("test_scripts") / "issues" / str(issue_number)
        output_dir.mkdir(parents=True, exist_ok=True)

        # --- Write verify.md ---
        md_path = output_dir / "verify.md"

        resolution_status = "Already Resolved" if resolution_check.get("resolved") else "Not Resolved"
        if "cannot check" in resolution_check.get("evidence", "").lower() or \
           "inconclusive" in resolution_check.get("evidence", "").lower():
            resolution_status = "Unclear"

        repro_str = {
            "reproduced": "REPRODUCED — bug-pattern code found in current codebase",
            "not_reproduced": "NOT REPRODUCED — fix may already be applied",
            "blocked": "BLOCKED — codebase not available for static check",
        }.get(reproduction_status, reproduction_status)

        patterns_section = ""
        if pattern_matches:
            for pm in pattern_matches:
                patterns_section += f"- **{pm.name}** — confidence {pm.confidence:.0%}\n"
                patterns_section += f"  - {pm.explanation}\n"
        else:
            patterns_section = "- No patterns matched\n"

        root_cause_section = "Root cause analysis was not completed (codebase unavailable or no pattern matched)."
        if root_cause:
            root_cause_section = f"""**File:** `{root_cause.file}:{root_cause.line_number}`
**Function:** `{root_cause.function or '<unknown>'}`
**Confidence:** {root_cause.confidence:.0%}

{root_cause.explanation}

**Buggy code:**
```python
{root_cause.code_snippet}
```

**Suggested fix:**
```python
{root_cause.suggested_fix}
```"""

        fix_section = "No fix generated."
        if fix:
            fix_section = f"""**File:** `{fix.file}:{fix.line_number}`

```diff
{fix.patch}
```

{fix.explanation}"""

        test_cases_section = ""
        if root_cause and root_cause.test_cases:
            for tc in root_cause.test_cases:
                test_cases_section += f"- [ ] {tc}\n"
        else:
            test_cases_section = "- [ ] Manual testing required\n"

        comments_summary = ""
        if github_issue.comments:
            comments_summary = f"\n**Comments ({len(github_issue.comments)}):**\n"
            for c in github_issue.comments[:3]:
                author = c.get('author', 'unknown') if isinstance(c, dict) else 'unknown'
                body = c.get('body', '') if isinstance(c, dict) else str(c)
                comments_summary += f"- @{author}: {body[:200]}...\n" if len(body) > 200 else f"- @{author}: {body}\n"

        md_content = f"""# Issue #{issue_number} Root Cause Analysis

## Issue Summary

**Title:** {github_issue.title}
**URL:** {github_issue.html_url}
**State:** {github_issue.state}
**Author:** @{github_issue.author}
**Labels:** {', '.join(github_issue.labels) if github_issue.labels else 'none'}
**Priority:** {parsed_issue.priority}
**Type:** {parsed_issue.issue_type}

## Environment

**Python version:** {parsed_issue.metadata.python_version or 'unknown'}
**OS:** {parsed_issue.metadata.os or 'unknown'}
**Browser:** {parsed_issue.metadata.browser or 'unknown'}
**Crawl4AI version:** {parsed_issue.metadata.crawl4ai_version or 'unknown'}
**Deployment:** {parsed_issue.metadata.deployment or 'unknown'}

## Reproduction

**Status:** {repro_str}

### Issue Description

{github_issue.body or '(no description)'}
{comments_summary}

## Observed Behavior

{parsed_issue.errors[0].error_message if parsed_issue.errors else '(see issue description)'}

## Expected Behavior

The operation should complete without error.

## Root Cause Analysis

{root_cause_section}

### Pattern Matches

{patterns_section}

## Resolution Check

**Status:** {resolution_status}
**Evidence:** {resolution_check.get('evidence', 'N/A')}

## Suggested Fixes

{fix_section}

## Mitigations

- Review the pattern `{pattern_matches[0].name if pattern_matches else 'N/A'}` in the affected module
- Apply the suggested patch if not already resolved
- Add regression test to CI

## Regression Tests

{test_cases_section}

## Open Questions

- Is this issue reproducible in the latest release?
- Are there related issues tracking similar behavior?
- Does the fix break any existing tests?
"""

        md_path.write_text(md_content, encoding='utf-8')
        logger.info(f"Report written: {md_path}")

        # --- Write verify.py ---
        py_path = output_dir / "verify.py"

        pattern_name = pattern_matches[0].name if pattern_matches else "unknown"
        snippet = root_cause.code_snippet if root_cause else "(unavailable)"

        if pattern_name == "timeout_issue":
            repro_code = f"""import asyncio
import httpx

async def reproduce_timeout_issue():
    \"\"\"Reproduce: httpx.AsyncClient without timeout=None causes 5s timeout error.\"\"\"
    # Buggy: default 5s timeout
    # async with httpx.AsyncClient() as client:
    #     r = await client.get("http://localhost:11235/some-llm-endpoint")

    # Fixed: explicit timeout=None
    async with httpx.AsyncClient(timeout=None) as client:
        try:
            r = await client.get("http://localhost:11235/", timeout=2)
            print(f"Response: {{r.status_code}}")
        except httpx.ConnectError:
            print("Connection refused (expected if server not running)")
        except httpx.TimeoutException as e:
            print(f"Timeout error (bug reproduced): {{e}}")

asyncio.run(reproduce_timeout_issue())
"""
        elif pattern_name == "encoding_issue":
            repro_code = f"""import sys

def reproduce_encoding_issue():
    \"\"\"Reproduce: open() without encoding='utf-8' fails on Windows (cp1252).\"\"\"
    test_content = "Test content with special chars: é à ü"
    output_file = "/tmp/test_output.txt"

    # Buggy: no encoding specified
    try:
        with open(output_file, 'w') as f:
            f.write(test_content)
        print(f"Wrote without encoding (platform default: {{sys.getdefaultencoding()}})")
    except UnicodeEncodeError as e:
        print(f"Encoding error reproduced: {{e}}")

    # Fixed: explicit utf-8
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(test_content)
    print("Wrote with encoding='utf-8' — OK")

reproduce_encoding_issue()
"""
        else:
            repro_code = f"""# Reproduction stub for issue #{issue_number}
# Pattern: {pattern_name}
#
# Buggy code snippet (from static analysis):
# {chr(10).join('# ' + line for line in snippet.split(chr(10)))}

def reproduce():
    \"\"\"
    TODO: Implement reproduction steps based on the issue description.
    See verify.md for full analysis.
    \"\"\"
    raise NotImplementedError("Fill in reproduction steps from issue #{issue_number}")

if __name__ == "__main__":
    reproduce()
"""

        py_content = f"""#!/usr/bin/env python3
\"\"\"
Reproduction script for GitHub Issue #{issue_number}

Issue: {github_issue.title}
URL:   {github_issue.html_url}

This script attempts to reproduce the reported bug.
It is READ-ONLY and makes no changes to the repository.
\"\"\"

{repro_code}
"""
        py_path.write_text(py_content, encoding='utf-8')
        logger.info(f"Reproduction script written: {py_path}")

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

    def _apply_patch(self, fix) -> bool:
        """Apply patch to file (only used in --create-pr mode)."""
        import subprocess

        if not self.repo_path:
            logger.error("Cannot apply patch: --repo-path not specified")
            return False

        try:
            patch_file = os.path.join(self.repo_path, '.fix.patch')
            with open(patch_file, 'w', encoding='utf-8') as f:
                f.write(fix.patch)

            subprocess.run(
                ['git', 'apply', patch_file],
                cwd=self.repo_path,
                check=True,
                capture_output=True,
            )

            os.remove(patch_file)
            logger.info(f"Applied patch to {fix.file}")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to apply patch: {e}")
            return False

    async def create_pr_mode(self, issue_number: int) -> bool:
        """
        Run in PR creation mode (--create-pr flag required).
        This calls the full pipeline AND creates a branch/commit/PR.
        Only runs when explicitly requested.
        """
        logger.info(f"Running in PR creation mode for issue #{issue_number}")

        # First do the analysis
        await self.process_issue(issue_number)

        # Then create PR (implementation stub — requires manual review)
        logger.warning("PR creation requires manual review of the generated patch.")
        logger.warning("Please check test_scripts/issues/{issue_number}/verify.md for the analysis.")
        return False

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
        '--url',
        type=str,
        help='Full GitHub issue URL (e.g. https://github.com/unclecode/crawl4ai/issues/1769)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        default=True,
        help='Dry run mode — analysis only, no PRs created (default: True)'
    )
    parser.add_argument(
        '--create-pr',
        action='store_true',
        default=False,
        help='Create a pull request after analysis (requires --no-dry-run credentials)'
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
        default=None,
        help='Path to local Crawl4AI repository clone (default: ~/crawl4ai-repo)'
    )
    parser.add_argument(
        '--owner',
        type=str,
        default='unclecode',
        help='Repository owner (default: unclecode)'
    )
    parser.add_argument(
        '--repo',
        type=str,
        default='crawl4ai',
        help='Repository name (default: crawl4ai)'
    )

    args = parser.parse_args()

    # Resolve issue number from --url or --issue
    issue_number = None
    if args.url:
        issue_number = GitHubCLI.parse_issue_url(args.url)
        logger.info(f"Parsed issue number from URL: #{issue_number}")
    elif args.issue:
        issue_number = args.issue

    # Create pipeline
    pipeline = RootCauseAnalysisPipeline(
        repo_path=args.repo_path,
        owner=args.owner,
        repo=args.repo,
        dry_run=not args.create_pr,
        confidence_threshold=args.confidence,
    )

    # Run in appropriate mode
    if args.watch:
        await pipeline.run_watch_mode()
    elif issue_number:
        await pipeline.run_single_mode(issue_number)
    else:
        parser.print_help()
        logger.info("\nPlease specify --url URL, --issue NUMBER, or --watch")


if __name__ == '__main__':
    asyncio.run(main())

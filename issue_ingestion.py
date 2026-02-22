"""
Issue Ingestion Engine - Parses GitHub issues into structured format.

This module implements the parsing and structuring of GitHub issues:
1. Extracts metadata (title, body, labels, author, etc.)
2. Extracts code snippets from issue descriptions
3. Extracts error messages and stack traces
4. Extracts OS, Python, and browser version information
5. Categorizes issues by type (bug, feature, question)

Usage:
    from issue_ingestion import IssueIngestionEngine

    engine = IssueIngestionEngine()
    issue = engine.parse_issue(github_issue_data)
"""

import re
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass, field

from issue_watcher import GitHubIssue

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class CodeSnippet:
    """Represents a code snippet extracted from an issue."""
    code: str
    language: Optional[str] = None
    context: str = ""
    line_number: int = 0


@dataclass
class ErrorInfo:
    """Represents error information extracted from an issue."""
    error_type: str
    error_message: str
    stack_trace: Optional[str] = None
    file_path: Optional[str] = None
    line_number: Optional[int] = None


@dataclass
class IssueMetadata:
    """Metadata extracted from issue."""
    os: Optional[str] = None
    os_version: Optional[str] = None
    python_version: Optional[str] = None
    browser: Optional[str] = None
    browser_version: Optional[str] = None
    crawl4ai_version: Optional[str] = None
    deployment: Optional[str] = None  # e.g., 'docker', 'local', 'pip'


@dataclass
class ParsedIssue:
    """Structured representation of a parsed GitHub issue."""
    original: GitHubIssue
    issue_type: str  # 'bug', 'feature', 'question', 'other'
    code_snippets: List[CodeSnippet] = field(default_factory=list)
    errors: List[ErrorInfo] = field(default_factory=list)
    metadata: IssueMetadata = field(default_factory=IssueMetadata)
    keywords: List[str] = field(default_factory=list)
    priority: str = "medium"  # 'low', 'medium', 'high', 'critical'

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            'id': self.original.id,
            'number': self.original.number,
            'title': self.original.title,
            'body': self.original.body,
            'issue_type': self.issue_type,
            'code_snippets': [{'code': s.code, 'language': s.language} for s in self.code_snippets],
            'errors': [{'type': e.error_type, 'message': e.error_message} for e in self.errors],
            'metadata': {
                'os': self.metadata.os,
                'python_version': self.metadata.python_version,
                'crawl4ai_version': self.metadata.crawl4ai_version,
            },
            'priority': self.priority,
        }


class IssueIngestionEngine:
    """Parses and structures GitHub issues."""

    # Regex patterns for extraction
    CODE_BLOCK_PATTERNS = [
        r'```(\w+)?\n(.*?)```',  # Markdown code blocks
        r'`([^`\n]+)`',  # Inline code
        r'```\n(.*?)```',  # Code blocks without language
    ]

    ERROR_PATTERNS = [
        r'(\w+Error|Exception):?\s*([^\n]+)',
        r'(?:Traceback|Traceback \(most recent call last\)):?\s*\n(?:[^\n]*\n)*?(\w+Error|Exception):?\s*([^\n]+)',
        r'(?:Error|Exception):\s*([^\n]+)',
        r'failed with\s+([^\n]+)',
    ]

    VERSION_PATTERNS = {
        'os': [
            r'OS[:\s]+(Windows|Linux|macOS|Darwin)',
            r'Operating System[:\s]+(Windows|Linux|macOS)',
        ],
        'python_version': [
            r'Python version[:\s]+([\d.]+)',
            r'Python[:\s]+([\d.]+)',
        ],
        'browser': [
            r'Browser[:\s]+(Chrome|Firefox|Safari|Edge|Chromium)',
        ],
        'crawl4ai_version': [
            r'crawl4ai version[:\s]+([\d.]+)',
            r'version[:\s]+([\d.]+)',
        ],
    }

    KEYWORD_PATTERNS = {
        'bug': ['bug', 'broken', 'crash', 'error', 'fail', 'not work', 'exception'],
        'timeout': ['timeout', 'slow', 'hang', 'freeze', '5s', '5 second'],
        'encoding': ['charmap', 'encoding', 'codec', 'utf-8', 'cp1252'],
        'docker': ['docker', 'container', 'image', 'build'],
        'mcp': ['mcp', 'model context protocol'],
        'cli': ['cli', 'command line', 'crwl'],
        'browser': ['browser', 'playwright', 'chromium', 'selenium'],
        'llm': ['llm', 'gpt', 'claude', 'extraction', 'ai'],
    }

    PRIORITY_KEYWORDS = {
        'critical': ['critical', 'urgent', 'security', 'production'],
        'high': ['high', 'major', 'important'],
        'low': ['minor', 'trivial', 'cosmetic'],
    }

    def __init__(self):
        """Initialize issue ingestion engine."""
        logger.info("IssueIngestionEngine initialized")

    def parse_issue(self, github_issue: GitHubIssue) -> ParsedIssue:
        """
        Parse a GitHub issue into structured format.

        Args:
            github_issue: GitHubIssue object from issue_watcher

        Returns:
            ParsedIssue object
        """
        logger.info(f"Parsing issue #{github_issue.number}: {github_issue.title}")

        # Determine issue type
        issue_type = self._classify_issue_type(github_issue)

        # Extract code snippets
        code_snippets = self._extract_code_snippets(github_issue.body)

        # Extract errors
        errors = self._extract_errors(github_issue.body)

        # Extract metadata
        metadata = self._extract_metadata(github_issue.body)

        # Extract keywords
        keywords = self._extract_keywords(github_issue.title + ' ' + github_issue.body)

        # Determine priority
        priority = self._determine_priority(github_issue, keywords, errors)

        return ParsedIssue(
            original=github_issue,
            issue_type=issue_type,
            code_snippets=code_snippets,
            errors=errors,
            metadata=metadata,
            keywords=keywords,
            priority=priority,
        )

    def _classify_issue_type(self, issue: GitHubIssue) -> str:
        """
        Classify issue type based on labels and content.

        Args:
            issue: GitHubIssue object

        Returns:
            Issue type: 'bug', 'feature', 'question', 'other'
        """
        # Check labels first
        label_lower = [label.lower() for label in issue.labels]
        if 'bug' in label_lower or 'bug' in issue.title.lower():
            return 'bug'
        if any(l in label_lower for l in ['enhancement', 'feature', 'proposal']):
            return 'feature'
        if any(l in label_lower for l in ['question', 'help', 'documentation']):
            return 'question'

        # Check content
        title_lower = issue.title.lower()
        body_lower = issue.body.lower() if issue.body else ''

        bug_indicators = ['bug', 'error', 'fail', 'crash', 'broken', 'not work']
        if any(indicator in title_lower for indicator in bug_indicators):
            return 'bug'

        feature_indicators = ['feature', 'enhancement', 'add', 'support', 'implement']
        if any(indicator in title_lower for indicator in feature_indicators):
            return 'feature'

        question_indicators = ['how', 'question', 'help', 'is it possible', 'can i']
        if any(indicator in title_lower for indicator in question_indicators):
            return 'question'

        return 'other'

    def _extract_code_snippets(self, text: str) -> List[CodeSnippet]:
        """
        Extract code snippets from issue description.

        Args:
            text: Issue body text

        Returns:
            List of CodeSnippet objects
        """
        snippets = []

        # Extract markdown code blocks
        for pattern in self.CODE_BLOCK_PATTERNS:
            matches = re.findall(pattern, text, re.DOTALL)
            for match in matches:
                if isinstance(match, tuple):
                    if len(match) == 2:
                        language, code = match
                    else:
                        code = match[0]
                        language = None
                else:
                    code = match
                    language = None

                if code and len(code.strip()) > 10:  # Filter out empty snippets
                    snippets.append(CodeSnippet(
                        code=code.strip(),
                        language=language,
                    ))

        return snippets

    def _extract_errors(self, text: str) -> List[ErrorInfo]:
        """
        Extract error information from issue description.

        Args:
            text: Issue body text

        Returns:
            List of ErrorInfo objects
        """
        errors = []

        for pattern in self.ERROR_PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                groups = match.groups()
                if len(groups) >= 2:
                    error_type = groups[0]
                    error_message = groups[1]
                elif len(groups) == 1:
                    error_type = 'Error'
                    error_message = groups[0]
                else:
                    continue

                errors.append(ErrorInfo(
                    error_type=error_type.strip(),
                    error_message=error_message.strip(),
                ))

        return errors

    def _extract_metadata(self, text: str) -> IssueMetadata:
        """
        Extract metadata (OS, Python version, etc.) from issue description.

        Args:
            text: Issue body text

        Returns:
            IssueMetadata object
        """
        metadata = IssueMetadata()

        # Extract OS
        for pattern in self.VERSION_PATTERNS['os']:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                metadata.os = match.group(1).strip()
                break

        # Extract Python version
        for pattern in self.VERSION_PATTERNS['python_version']:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                metadata.python_version = match.group(1).strip()
                break

        # Extract browser
        for pattern in self.VERSION_PATTERNS['browser']:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                metadata.browser = match.group(1).strip()
                break

        # Extract Crawl4AI version
        for pattern in self.VERSION_PATTERNS['crawl4ai_version']:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                metadata.crawl4ai_version = match.group(1).strip()
                break

        # Infer deployment type from content
        text_lower = text.lower()
        if 'docker' in text_lower:
            metadata.deployment = 'docker'
        elif 'pip install' in text_lower or 'setup.py' in text_lower:
            metadata.deployment = 'pip'
        else:
            metadata.deployment = 'local'

        return metadata

    def _extract_keywords(self, text: str) -> List[str]:
        """
        Extract relevant keywords from issue text.

        Args:
            text: Combined title and body text

        Returns:
            List of keywords
        """
        text_lower = text.lower()
        keywords = []

        for category, patterns in self.KEYWORD_PATTERNS.items():
            for pattern in patterns:
                if pattern.lower() in text_lower:
                    keywords.append(category)
                    break  # Only add category once

        return keywords

    def _determine_priority(
        self,
        issue: GitHubIssue,
        keywords: List[str],
        errors: List[ErrorInfo],
    ) -> str:
        """
        Determine issue priority based on various factors.

        Args:
            issue: GitHubIssue object
            keywords: Extracted keywords
            errors: Extracted errors

        Returns:
            Priority: 'critical', 'high', 'medium', 'low'
        """
        # Check labels first
        label_lower = [label.lower() for label in issue.labels]
        if 'critical' in label_lower or 'urgent' in label_lower:
            return 'critical'
        if 'high' in label_lower or 'high priority' in label_lower:
            return 'high'

        # Check keywords
        for keyword in keywords:
            if keyword in self.PRIORITY_KEYWORDS['critical']:
                return 'critical'
            if keyword in self.PRIORITY_KEYWORDS['high']:
                return 'high'

        # Check for certain error types
        error_types = [e.error_type.lower() for e in errors]
        critical_errors = ['memoryerror', 'segmentationfault', 'critical']
        if any(ce in error_types for ce in critical_errors):
            return 'critical'

        # Default to medium
        return 'medium'


def main():
    """Test the issue ingestion engine."""
    import asyncio
    from issue_watcher import GitHubAPI, GitHubIssue

    async def test():
        api = GitHubAPI()
        issues = await api.get_issues(repo='unclecode/crawl4ai', state='open', limit=5)

        engine = IssueIngestionEngine()

        for issue in issues[:3]:  # Test first 3 issues
            print(f"\n{'='*80}")
            print(f"Issue #{issue.number}: {issue.title}")
            print(f"URL: {issue.html_url}")
            print(f"{'='*80}\n")

            parsed = engine.parse_issue(issue)

            print(f"Type: {parsed.issue_type}")
            print(f"Priority: {parsed.priority}")
            print(f"Keywords: {parsed.keywords}")
            print(f"\nMetadata:")
            print(f"  OS: {parsed.metadata.os}")
            print(f"  Python: {parsed.metadata.python_version}")
            print(f"  Crawl4AI: {parsed.metadata.crawl4ai_version}")
            print(f"\nErrors ({len(parsed.errors)}):")
            for error in parsed.errors:
                print(f"  - {error.error_type}: {error.error_message[:80]}")
            print(f"\nCode Snippets ({len(parsed.code_snippets)}):")
            for snippet in parsed.code_snippets:
                print(f"  - Language: {snippet.language}")
                print(f"    Length: {len(snippet.code)} chars")

    asyncio.run(test())


if __name__ == '__main__':
    main()

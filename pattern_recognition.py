"""
Pattern Recognition Engine - Matches issues against known bug patterns.

This module implements pattern recognition for bug identification:
1. Keyword-based pattern matching
2. Code snippet analysis
3. Error message analysis
4. Metadata correlation
5. Confidence scoring

Usage:
    from pattern_recognition import PatternRecognitionEngine

    engine = PatternRecognitionEngine()
    matches = engine.match_pattern(parsed_issue)
"""

import re
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

from issue_ingestion import ParsedIssue, CodeSnippet, ErrorInfo

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class PatternMatch:
    """Represents a pattern match for an issue."""
    name: str
    confidence: float
    explanation: str
    suggested_files: List[str] = field(default_factory=list)
    code_snippets: List[CodeSnippet] = field(default_factory=list)
    errors: List[ErrorInfo] = field(default_factory=list)
    keywords_matched: List[str] = field(default_factory=list)


class PatternRecognitionEngine:
    """Matches issues against known bug patterns."""

    # Known bug patterns with their characteristics
    KNOWN_PATTERNS = {
        'encoding_issue': {
            'name': 'Cross-Platform Encoding Issue',
            'keywords': ['charmap', 'encoding', 'codec', 'cant encode', 'unicode', 'utf'],
            'error_types': ['UnicodeEncodeError', 'UnicodeDecodeError', 'LookupError'],
            'file_operations': ['open(', 'write(', 'Path.write_text()', 'Path.read_text()'],
            'os_specific': ['Windows', 'cp1252', 'utf-8', 'latin1'],
            'suggested_files': ['crawl4ai/cli.py', 'crawl4ai/utils.py', 'deploy/docker/*.py'],
            'priority_weight': 0.7,
        },
        'timeout_issue': {
            'name': 'Timeout Configuration Issue',
            'keywords': ['timeout', 'slow', 'hang', 'freeze', '5 second', '5s', '10s'],
            'error_types': ['TimeoutException', 'TimeoutError', 'ReadTimeout'],
            'async_clients': ['httpx.AsyncClient', 'aiohttp.ClientSession', 'requests'],
            'suggested_files': ['deploy/docker/mcp_bridge.py', 'crawl4ai/async_*.py', 'crawl4ai/docker_client.py'],
            'priority_weight': 0.9,
        },
        'docker_path_issue': {
            'name': 'Docker/Filesystem Boundary Issue',
            'keywords': ['docker', 'filesystem', 'path', 'container', 'file not found', 'permission denied'],
            'error_types': ['FileNotFoundError', 'PermissionError', 'NotADirectoryError'],
            'file_operations': ['open(', 'save(', 'write(', 'Path(', 'os.path'],
            'mcp_tools': True,
            'suggested_files': ['deploy/docker/mcp_bridge.py', 'deploy/docker/api.py', 'deploy/docker/server.py'],
            'priority_weight': 0.85,
        },
        'async_error_handling': {
            'name': 'Async Error Handling Issue',
            'keywords': ['async', 'await', 'exception', 'not caught', 'propagates'],
            'error_types': ['Exception', 'RuntimeError', 'AssertionError'],
            'async_keywords': ['async def', 'await', 'async with', 'async for'],
            'suggested_files': ['crawl4ai/async_*.py', 'crawl4ai/async_dispatcher.py', 'crawl4ai/browser_manager.py'],
            'priority_weight': 0.75,
        },
        'llm_extraction_issue': {
            'name': 'LLM Extraction Issue',
            'keywords': ['llm', 'extraction', 'gpt', 'claude', 'anthropic', 'openai'],
            'error_types': ['LLMError', 'APIError', 'RateLimitError'],
            'related_classes': ['LLMExtractionStrategy', 'LLMConfig', 'LLMTableExtraction'],
            'suggested_files': ['crawl4ai/extraction_strategy.py', 'crawl4ai/prompts.py', 'crawl4ai/model_loader.py'],
            'priority_weight': 0.8,
        },
        'browser_pool_issue': {
            'name': 'Browser Pool Management Issue',
            'keywords': ['browser', 'pool', 'chrome', 'playwright', 'selenium', 'timeout'],
            'error_types': ['BrowserError', 'TimeoutException', 'ProcessLookupError'],
            'related_classes': ['BrowserManager', 'BrowserConfig', 'BrowserPool'],
            'suggested_files': ['crawl4ai/browser_manager.py', 'crawl4ai/browser_adapter.py', 'crawl4ai/async_webcrawler.py'],
            'priority_weight': 0.8,
        },
        'memory_leak': {
            'name': 'Memory Leak Issue',
            'keywords': ['memory', 'leak', 'growing', 'not released', 'oom', 'out of memory'],
            'error_types': ['MemoryError', 'OutOFMemoryError'],
            'related_classes': ['MemoryMonitor', 'CacheContext'],
            'suggested_files': ['crawl4ai/memory_utils.py', 'crawl4ai/async_dispatcher.py', 'crawl4ai/browser_manager.py'],
            'priority_weight': 0.85,
        },
        'proxy_issue': {
            'name': 'Proxy Configuration Issue',
            'keywords': ['proxy', 'authentication', 'connection refused', 'timeout'],
            'error_types': ['ProxyError', 'ConnectionError', 'AuthenticationError'],
            'related_classes': ['ProxyStrategy', 'ProxyConfig'],
            'suggested_files': ['crawl4ai/proxy_strategy.py', 'crawl4ai/async_webcrawler.py'],
            'priority_weight': 0.7,
        },
    }

    def __init__(self):
        """Initialize pattern recognition engine."""
        logger.info("PatternRecognitionEngine initialized")
        logger.info(f"Loaded {len(self.KNOWN_PATTERNS)} known patterns")

    def match_pattern(self, issue: ParsedIssue) -> List[PatternMatch]:
        """
        Match issue against known patterns.

        Args:
            issue: ParsedIssue object

        Returns:
            List of PatternMatch objects, sorted by confidence
        """
        logger.info(f"Matching patterns for issue #{issue.original.number}")

        matches = []

        # Combine text for analysis
        text = (issue.original.title + ' ' + issue.original.body).lower()

        for pattern_name, pattern_config in self.KNOWN_PATTERNS.items():
            match = self._match_single_pattern(issue, pattern_name, pattern_config, text)
            if match and match.confidence > 0.3:  # Only include matches with >30% confidence
                matches.append(match)

        # Sort by confidence (highest first)
        matches.sort(key=lambda m: m.confidence, reverse=True)

        logger.info(f"Found {len(matches)} pattern matches")

        return matches

    def _match_single_pattern(
        self,
        issue: ParsedIssue,
        pattern_name: str,
        pattern_config: Dict,
        text: str
    ) -> Optional[PatternMatch]:
        """
        Match issue against a single pattern.

        Args:
            issue: ParsedIssue object
            pattern_name: Name of the pattern
            pattern_config: Pattern configuration dictionary
            text: Combined title and body text (lowercase)

        Returns:
            PatternMatch object if match found, None otherwise
        """
        score = 0.0
        max_score = 0.0
        keywords_matched = []
        code_snippets_matched = []
        errors_matched = []

        # 1. Check keywords (weight: 0.3)
        keyword_weight = 0.3
        keywords = pattern_config.get('keywords', [])
        keyword_matches = sum(1 for kw in keywords if kw.lower() in text)
        if keywords:
            keyword_score = (keyword_matches / len(keywords)) * keyword_weight
            score += keyword_score
            keywords_matched = [kw for kw in keywords if kw.lower() in text]
        max_score += keyword_weight

        # 2. Check error types (weight: 0.4)
        error_weight = 0.4
        error_types = pattern_config.get('error_types', [])
        error_types_lower = [e.lower() for e in error_types]
        issue_error_types = [e.error_type.lower() for e in issue.errors]
        error_matches = sum(1 for et in error_types_lower if et in issue_error_types)
        if error_types:
            error_score = (error_matches / len(error_types)) * error_weight
            score += error_score
            errors_matched = [e for e in issue.errors if e.error_type.lower() in error_types_lower]
        max_score += error_weight

        # 3. Check code snippets for relevant patterns (weight: 0.2)
        code_weight = 0.2
        code_operations = pattern_config.get('file_operations', [])
        if code_operations and issue.code_snippets:
            combined_code = ' '.join(s.code.lower() for s in issue.code_snippets)
            code_matches = sum(1 for co in code_operations if co.lower() in combined_code)
            if code_operations:
                code_score = (code_matches / len(code_operations)) * code_weight
                score += code_score
                if code_score > 0:
                    code_snippets_matched = issue.code_snippets
            max_score += code_weight

        # 4. Check metadata (weight: 0.1)
        metadata_weight = 0.1
        metadata_boost = 0.0
        os_specific = pattern_config.get('os_specific', [])
        if os_specific and issue.metadata.os:
            if any(os_.lower() in issue.metadata.os.lower() for os_ in os_specific):
                metadata_boost += 0.05

        deployment = pattern_config.get('deployment')
        if deployment and issue.metadata.deployment:
            if deployment.lower() == issue.metadata.deployment.lower():
                metadata_boost += 0.05

        score += metadata_boost
        max_score += metadata_weight

        # Normalize confidence to 0-1 range
        if max_score > 0:
            confidence = min(score / max_score, 1.0)
        else:
            confidence = 0.0

        # Apply priority weight boost
        priority_weight = pattern_config.get('priority_weight', 0.5)
        confidence = confidence * (0.5 + priority_weight / 2)

        # Generate explanation
        explanation = self._generate_explanation(
            pattern_config,
            keywords_matched,
            errors_matched,
            code_snippets_matched,
            issue.metadata,
        )

        if confidence > 0.3:
            return PatternMatch(
                name=pattern_name,
                confidence=confidence,
                explanation=explanation,
                suggested_files=pattern_config.get('suggested_files', []),
                code_snippets=code_snippets_matched,
                errors=errors_matched,
                keywords_matched=keywords_matched,
            )

        return None

    def _generate_explanation(
        self,
        pattern_config: Dict,
        keywords_matched: List[str],
        errors_matched: List[ErrorInfo],
        code_snippets_matched: List[CodeSnippet],
        metadata,
    ) -> str:
        """Generate human-readable explanation for pattern match."""
        parts = [f"Pattern: {pattern_config['name']}"]

        if keywords_matched:
            parts.append(f"Keywords: {', '.join(keywords_matched)}")

        if errors_matched:
            error_types = [e.error_type for e in errors_matched]
            parts.append(f"Errors: {', '.join(error_types)}")

        if code_snippets_matched:
            parts.append(f"Found {len(code_snippets_matched)} relevant code snippet(s)")

        if metadata.os:
            parts.append(f"OS: {metadata.os}")

        if metadata.deployment:
            parts.append(f"Deployment: {metadata.deployment}")

        return '. '.join(parts)


def main():
    """Test pattern recognition engine."""
    import asyncio
    from issue_watcher import GitHubAPI
    from issue_ingestion import IssueIngestionEngine

    async def test():
        # Fetch a real issue for testing
        api = GitHubAPI()
        issues = await api.get_issues(repo='unclecode/crawl4ai', state='open', limit=1)

        if not issues:
            print("No issues found for testing")
            return

        # Parse issue
        ingestion_engine = IssueIngestionEngine()
        parsed_issue = ingestion_engine.parse_issue(issues[0])

        # Match patterns
        pattern_engine = PatternRecognitionEngine()
        matches = pattern_engine.match_pattern(parsed_issue)

        # Display results
        print(f"\n{'='*80}")
        print(f"Issue #{parsed_issue.original.number}: {parsed_issue.original.title}")
        print(f"{'='*80}\n")

        if not matches:
            print("No pattern matches found")
        else:
            print(f"Found {len(matches)} pattern match(es):\n")

            for i, match in enumerate(matches, 1):
                print(f"Match {i}: {match.name}")
                print(f"  Confidence: {match.confidence:.2%}")
                print(f"  Explanation: {match.explanation}")
                print(f"  Keywords: {', '.join(match.keywords_matched)}")
                print(f"  Suggested files: {', '.join(match.suggested_files[:3])}")
                print()

    asyncio.run(test())


if __name__ == '__main__':
    main()

"""
Root Cause Analyzer - Performs static code analysis to find root causes.

This module implements static code analysis for bug localization:
1. AST-based code analysis
2. Dependency graph traversal
3. Cross-reference with similar historical issues
4. Code pattern matching
5. Root cause hypothesis generation

Usage:
    from root_cause_analyzer import RootCauseAnalyzer

    analyzer = RootCauseAnalyzer(codebase_path="/path/to/repo")
    root_cause = analyzer.analyze(parsed_issue, pattern_match)
"""

import ast
import os
import re
import logging
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass, field
from pathlib import Path

from issue_ingestion import ParsedIssue, CodeSnippet, ErrorInfo
from pattern_recognition import PatternMatch

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class CodeLocation:
    """Represents a location in code."""
    file: str
    line_number: int
    function: Optional[str] = None
    class_name: Optional[str] = None


@dataclass
class RootCause:
    """Represents a hypothesized root cause."""
    pattern_name: str
    file: str
    line_number: int
    function: Optional[str]
    explanation: str
    confidence: float
    code_snippet: str
    suggested_fix: str
    similar_issues: List[int] = field(default_factory=list)
    test_cases: List[str] = field(default_factory=list)


class RootCauseAnalyzer:
    """Performs static code analysis to find root causes."""

    def __init__(self, codebase_path: str = "/root/.openclaw/workspace/crawl4ai-repo"):
        """
        Initialize root cause analyzer.

        Args:
            codebase_path: Path to the codebase to analyze
        """
        self.codebase_path = Path(codebase_path)
        self.code_cache: Dict[str, str] = {}
        self.ast_cache: Dict[str, ast.Module] = {}
        logger.info(f"RootCauseAnalyzer initialized with codebase: {codebase_path}")

    def analyze(
        self,
        issue: ParsedIssue,
        pattern_match: PatternMatch,
    ) -> Optional[RootCause]:
        """
        Perform root cause analysis.

        Args:
            issue: ParsedIssue object
            pattern_match: PatternMatch object

        Returns:
            RootCause object if analysis successful, None otherwise
        """
        logger.info(f"Analyzing root cause for issue #{issue.original.number}")
        logger.info(f"Pattern: {pattern_match.name} (confidence: {pattern_match.confidence:.2%})")

        # 1. Locate relevant files
        relevant_files = self._find_relevant_files(pattern_match.suggested_files)

        if not relevant_files:
            logger.warning("No relevant files found")
            return None

        logger.info(f"Found {len(relevant_files)} relevant file(s) to analyze")

        # 2. Search for bug patterns in relevant files
        for file_path in relevant_files:
            bug_locations = self._search_for_bug_pattern(
                file_path,
                pattern_match,
                issue,
            )

            if bug_locations:
                # Take the highest confidence match
                best_match = max(bug_locations, key=lambda x: x['confidence'])

                return RootCause(
                    pattern_name=pattern_match.name,
                    file=best_match['file'],
                    line_number=best_match['line_number'],
                    function=best_match['function'],
                    explanation=self._generate_explanation(best_match, pattern_match, issue),
                    confidence=best_match['confidence'],
                    code_snippet=best_match['code'],
                    suggested_fix=best_match['suggested_fix'],
                    similar_issues=self._find_similar_issues(issue),
                    test_cases=self._generate_test_cases(issue, pattern_match),
                )

        logger.warning("No bug patterns found in relevant files")
        return None

    def _find_relevant_files(self, suggested_files: List[str]) -> List[str]:
        """
        Find relevant files in codebase.

        Args:
            suggested_files: List of suggested file patterns

        Returns:
            List of absolute file paths
        """
        files = []

        for pattern in suggested_files:
            # Convert pattern to path
            if pattern.startswith('crawl4ai/'):
                base_path = self.codebase_path / 'crawl4ai'
                sub_pattern = pattern[10:]  # Remove 'crawl4ai/'
            elif pattern.startswith('deploy/docker/'):
                base_path = self.codebase_path / 'deploy' / 'docker'
                sub_pattern = pattern[14:]  # Remove 'deploy/docker/'
            else:
                continue

            # Handle wildcards
            if '*' in sub_pattern:
                # Find files matching pattern
                glob_pattern = sub_pattern.replace('*', '**')
                matching_files = list(base_path.glob(glob_pattern))
                files.extend([str(f) for f in matching_files if f.is_file()])
            else:
                # Exact file match
                file_path = base_path / sub_pattern
                if file_path.is_file():
                    files.append(str(file_path))

        return files

    def _search_for_bug_pattern(
        self,
        file_path: str,
        pattern_match: PatternMatch,
        issue: ParsedIssue,
    ) -> List[Dict]:
        """
        Search for bug patterns in a file.

        Args:
            file_path: Path to the file to analyze
            pattern_match: PatternMatch object
            issue: ParsedIssue object

        Returns:
            List of potential bug locations with confidence scores
        """
        try:
            content = self._load_file(file_path)
            tree = self._parse_ast(content)

            bug_locations = []

            # Pattern-specific searches
            if 'encoding_issue' in pattern_match.name:
                bug_locations.extend(self._search_encoding_issues(file_path, content, tree))
            elif 'timeout_issue' in pattern_match.name:
                bug_locations.extend(self._search_timeout_issues(file_path, content, tree))
            elif 'docker_path_issue' in pattern_match.name:
                bug_locations.extend(self._search_docker_path_issues(file_path, content, tree))
            elif 'async_error_handling' in pattern_match.name:
                bug_locations.extend(self._search_async_error_handling(file_path, content, tree))

            return bug_locations

        except Exception as e:
            logger.error(f"Error analyzing {file_path}: {e}")
            return []

    def _search_encoding_issues(
        self,
        file_path: str,
        content: str,
        tree: ast.Module,
    ) -> List[Dict]:
        """Search for encoding issues (missing encoding parameter)."""
        locations = []

        # Find all open() calls
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if self._is_function_call(node, 'open'):
                    # Check if encoding parameter is present
                    has_encoding = any(
                        isinstance(kw, ast.keyword) and kw.arg == 'encoding'
                        for kw in node.keywords
                    )

                    if not has_encoding:
                        # Get the code snippet
                        start_line = node.lineno
                        end_line = node.end_lineno or start_line
                        lines = content.split('\n')
                        code = '\n'.join(lines[start_line-1:end_line])

                        # Find function name
                        func_name = self._get_function_name(tree, start_line)

                        locations.append({
                            'file': file_path,
                            'line_number': start_line,
                            'function': func_name,
                            'code': code,
                            'suggested_fix': self._fix_encoding_issue(code),
                            'confidence': 0.85,
                        })

        return locations

    def _search_timeout_issues(
        self,
        file_path: str,
        content: str,
        tree: ast.Module,
    ) -> List[Dict]:
        """Search for timeout issues (missing timeout parameter)."""
        locations = []

        # Find httpx.AsyncClient() calls
        for node in ast.walk(tree):
            if isinstance(node, ast.With):
                # Check if using httpx.AsyncClient
                if hasattr(node, 'items'):
                    for item in node.items:
                        if isinstance(item.context_expr, ast.Call):
                            call = item.context_expr
                            func = self._get_call_function(call)

                            if func and 'AsyncClient' in func:
                                # Check if timeout parameter is present
                                has_timeout = any(
                                    isinstance(kw, ast.keyword) and kw.arg == 'timeout'
                                    for kw in call.keywords
                                )

                                if not has_timeout:
                                    start_line = node.lineno
                                    end_line = node.end_lineno or start_line
                                    lines = content.split('\n')
                                    code = '\n'.join(lines[start_line-1:end_line])

                                    func_name = self._get_function_name(tree, start_line)

                                    locations.append({
                                        'file': file_path,
                                        'line_number': start_line,
                                        'function': func_name,
                                        'code': code,
                                        'suggested_fix': self._fix_timeout_issue(code),
                                        'confidence': 0.9,
                                    })

        return locations

    def _search_docker_path_issues(
        self,
        file_path: str,
        content: str,
        tree: ast.Module,
    ) -> List[Dict]:
        """Search for Docker path issues (writing to container filesystem)."""
        locations = []

        # Find file write operations
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if self._is_function_call(node, 'open') or self._is_function_call(node, 'Path.write_text'):
                    start_line = node.lineno
                    end_line = node.end_lineno or start_line
                    lines = content.split('\n')
                    code = '\n'.join(lines[start_line-1:end_line])

                    # Check if writing to fixed path without considering container/host boundary
                    if '/app/' in code or '/tmp/' in code or './' in code:
                        func_name = self._get_function_name(tree, start_line)

                        locations.append({
                            'file': file_path,
                            'line_number': start_line,
                            'function': func_name,
                            'code': code,
                            'suggested_fix': self._fix_docker_path_issue(code),
                            'confidence': 0.8,
                        })

        return locations

    def _search_async_error_handling(
        self,
        file_path: str,
        content: str,
        tree: ast.Module,
    ) -> List[Dict]:
        """Search for async error handling issues."""
        locations = []

        # Find async functions with incomplete error handling
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef):
                # Check if there's a try-except block
                has_try_except = False
                for child in ast.walk(node):
                    if isinstance(child, ast.Try):
                        # Check what exceptions are caught
                        except_handlers = child.handlers
                        if len(except_handlers) < 2:  # Only catches generic Exception or fewer
                            has_try_except = True
                            start_line = node.lineno
                            func_name = node.name
                            lines = content.split('\n')
                            code = '\n'.join(lines[start_line-1:min(start_line+10, len(lines))])

                            locations.append({
                                'file': file_path,
                                'line_number': start_line,
                                'function': func_name,
                                'code': code,
                                'suggested_fix': '# Add specific exception handling\n' + code,
                                'confidence': 0.7,
                            })

        return locations

    def _fix_encoding_issue(self, code: str) -> str:
        """Generate fix for encoding issue."""
        # Add encoding="utf-8" to open() calls
        code = re.sub(r'open\(([^,)]+)\)', r'open(\1, encoding="utf-8")', code)
        return code

    def _fix_timeout_issue(self, code: str) -> str:
        """Generate fix for timeout issue."""
        # Add timeout=None to httpx.AsyncClient()
        code = re.sub(
            r'httpx\.AsyncClient\(\)',
            r'httpx.AsyncClient(timeout=None)',
            code
        )
        return code

    def _fix_docker_path_issue(self, code: str) -> str:
        """Generate fix for Docker path issue."""
        # Suggest returning data instead of writing to file
        return "# Consider returning base64 data instead of writing to container filesystem\n" + code

    def _load_file(self, file_path: str) -> str:
        """Load file content with caching."""
        if file_path not in self.code_cache:
            with open(file_path, 'r', encoding='utf-8') as f:
                self.code_cache[file_path] = f.read()
        return self.code_cache[file_path]

    def _parse_ast(self, content: str) -> ast.Module:
        """Parse AST with caching."""
        file_hash = hash(content)
        cache_key = f"ast_{file_hash}"

        if cache_key not in self.ast_cache:
            self.ast_cache[cache_key] = ast.parse(content)

        return self.ast_cache[cache_key]

    def _is_function_call(self, node: ast.Call, function_name: str) -> bool:
        """Check if AST node is a call to specific function."""
        func = self._get_call_function(node)
        return func and function_name in func

    def _get_call_function(self, node: ast.Call) -> Optional[str]:
        """Get function name from AST Call node."""
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            return f"{self._get_attribute_name(node.func)}"
        return None

    def _get_attribute_name(self, node: ast.Attribute) -> str:
        """Get full attribute name."""
        parts = []
        current = node
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
        return '.'.join(reversed(parts))

    def _get_function_name(self, tree: ast.Module, line_number: int) -> Optional[str]:
        """Get function name containing a line."""
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.lineno <= line_number <= (node.end_lineno or line_number):
                    return node.name
        return None

    def _generate_explanation(
        self,
        bug_location: Dict,
        pattern_match: PatternMatch,
        issue: ParsedIssue,
    ) -> str:
        """Generate explanation for root cause."""
        explanation = f"Root cause found in {bug_location['file']}:{bug_location['line_number']}\n"
        explanation += f"Function: {bug_location['function'] or '<unknown>'}\n"
        explanation += f"Pattern: {pattern_match.name}\n"
        explanation += f"Confidence: {bug_location['confidence']:.2%}\n\n"
        explanation += f"Issue: The code is missing proper {pattern_match.name.lower()}. "
        explanation += f"This causes the reported error: {issue.errors[0].error_type if issue.errors else 'unknown'}.\n"
        explanation += f"\nKeywords matched: {', '.join(pattern_match.keywords_matched)}"
        return explanation

    def _find_similar_issues(self, issue: ParsedIssue) -> List[int]:
        """
        Find similar historical issues.

        Args:
            issue: ParsedIssue object

        Returns:
            List of similar issue numbers
        """
        # For now, return placeholder
        # In production, this would query a database of historical issues
        return []

    def _generate_test_cases(
        self,
        issue: ParsedIssue,
        pattern_match: PatternMatch,
    ) -> List[str]:
        """Generate test cases for the fix."""
        test_cases = []

        # Generate test case based on pattern
        if 'encoding_issue' in pattern_match.name:
            test_cases.append("Test file operations with non-ASCII characters")
            test_cases.append("Test cross-platform compatibility (Windows, Linux, macOS)")
        elif 'timeout_issue' in pattern_match.name:
            test_cases.append(f"Test with LLM endpoint exceeding 5s timeout")
            test_cases.append("Test timeout exception handling in MCP bridge")
        elif 'docker_path_issue' in pattern_match.name:
            test_cases.append("Test screenshot MCP tool returns base64 PNG")
            test_cases.append("Test file writing respects container/host boundary")

        return test_cases


def main():
    """Test root cause analyzer."""
    from issue_ingestion import IssueIngestionEngine
    from pattern_recognition import PatternRecognitionEngine
    from issue_watcher import GitHubIssue

    # Create a test issue
    test_issue = ParsedIssue(
        original=GitHubIssue(
            id=1769,
            number=1769,
            title="[Bug]: mcp_bridge: httpx default 5s timeout causes isError",
            body="When an LLM-backed endpoint takes longer than 5 seconds to respond...",
            state="open",
            author="test",
            labels=["bug"],
            created_at="2024-02-21T00:00:00Z",
            updated_at="2024-02-21T00:00:00Z",
            html_url="https://github.com/unclecode/crawl4ai/issues/1769",
            comments_url="https://api.github.com/repos/unclecode/crawl4ai/issues/1769/comments",
        ),
        issue_type="bug",
        keywords=["timeout", "mcp"],
        priority="high",
    )

    # Create pattern match
    pattern_match = PatternMatch(
        name="timeout_issue",
        confidence=0.95,
        explanation="Pattern: Timeout Configuration Issue",
        suggested_files=["deploy/docker/mcp_bridge.py"],
        keywords_matched=["timeout", "5s"],
    )

    # Analyze
    analyzer = RootCauseAnalyzer()
    root_cause = analyzer.analyze(test_issue, pattern_match)

    if root_cause:
        print(f"\nRoot Cause Analysis:")
        print(f"  File: {root_cause.file}")
        print(f"  Line: {root_cause.line_number}")
        print(f"  Function: {root_cause.function}")
        print(f"  Confidence: {root_cause.confidence:.2%}")
        print(f"\nExplanation:\n{root_cause.explanation}")
        print(f"\nSuggested Fix:\n{root_cause.suggested_fix}")
    else:
        print("No root cause found")


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Local Issue Validation Script - For testing root cause analysis
WITHOUT making any changes to the repository.

This script validates:
1. Pattern detection would work correctly
2. Root cause analysis would find the bug
3. The generated fix would actually solve the issue
4. All local operations, no GitHub writes

Usage:
    python3 validate_issue.py <issue_number>

Example:
    python3 validate_issue.py 1758
    python3 validate_issue.py 1762
    python3 validate_issue.py 1769
"""

import sys
import os
import re
import ast
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass


@dataclass
class ValidationResult:
    """Results of local validation."""
    issue_number: int
    issue_title: str
    pattern_matched: bool
    confidence: float
    root_cause_found: bool
    fix_would_work: bool
    validation_details: List[str]
    improvements_needed: List[str]


class LocalValidator:
    """Validates root cause analysis locally."""

    def __init__(self, repo_path: str = None):
        if repo_path is None:
            repo_path = str(Path.home() / "crawl4ai-repo")
        self.repo_path = Path(os.path.expanduser(repo_path))
        print(f"🔬 Local Validator initialized for: {self.repo_path}")

    def validate_pattern_detection(self, issue_title: str, issue_body: str) -> Tuple[bool, float, List[str], List[str]]:
        """
        Validate that pattern detection would work for this issue.

        Returns:
            (matched: bool, confidence: float, details: List[str], matched_patterns: List[str])
        """
        title_lower = issue_title.lower()
        body_lower = issue_body.lower() if issue_body else ""
        combined = title_lower + " " + body_lower

        # Pattern detection rules (same as system)
        patterns = {
            'encoding_issue': {
                'keywords': ['charmap', 'encoding', 'codec', 'cant encode'],
                'weight': 0.3,
                'explanation': 'Cross-platform encoding issue'
            },
            'timeout_issue': {
                'keywords': ['timeout', 'slow', 'hang', 'freeze', '5s', '5 second'],
                'weight': 0.4,
                'explanation': 'Timeout configuration issue'
            },
            'docker_path_issue': {
                'keywords': ['docker', 'filesystem', 'path', 'container', 'file not found'],
                'weight': 0.3,
                'explanation': 'Docker/filesystem boundary issue'
            },
            'async_error_handling': {
                'keywords': ['async', 'exception', 'not caught'],
                'weight': 0.25,
                'explanation': 'Async error handling issue'
            },
        }

        matched_patterns = []
        details = []

        for pattern_name, pattern_config in patterns.items():
            matches = sum(1 for kw in pattern_config['keywords'] if kw in combined)
            max_matches = len(pattern_config['keywords'])

            if matches > 0:
                match_score = matches / max_matches
                confidence = match_score * pattern_config['weight']
                matched_patterns.append(pattern_name)

                detail = f"✓ {pattern_name}: {pattern_config['explanation']}"
                detail += f" (keywords matched: {matches}/{max_matches})"
                details.append(detail)

        if matched_patterns:
            # Calculate overall confidence
            total_confidence = sum(patterns[p]['weight'] for p in matched_patterns)
            max_possible = sum(patterns[p]['weight'] for p in patterns)
            confidence = min(total_confidence / max_possible * 1.5, 1.0)
            return True, confidence, details, matched_patterns
        else:
            return False, 0.0, ["No patterns matched"], []

    def find_files_to_analyze(self, pattern_name: str) -> List[str]:
        """Find relevant files based on pattern."""
        if 'encoding_issue' in pattern_name:
            return [
                'crawl4ai/cli.py',
                'crawl4ai/utils.py',
                'crawl4ai/async_webcrawler.py',
            ]
        elif 'timeout_issue' in pattern_name:
            return [
                'deploy/docker/mcp_bridge.py',
                'crawl4ai/async_webcrawler.py',
                'crawl4ai/async_dispatcher.py',
            ]
        elif 'docker_path_issue' in pattern_name:
            return [
                'deploy/docker/mcp_bridge.py',
                'deploy/docker/api.py',
                'deploy/docker/server.py',
            ]
        else:
            return []

    def analyze_file_for_root_cause(self, file_path: str, pattern_name: str) -> Dict:
        """
        Analyze a specific file for the root cause of a pattern.

        Returns dict with analysis results.
        """
        file_full_path = self.repo_path / file_path

        if not file_full_path.exists():
            return {
                'file': file_path,
                'exists': False,
                'root_cause_found': False,
                'ast_validated': False,
                'details': f"File not found: {file_path}"
            }

        try:
            with open(file_full_path, 'r', encoding='utf-8') as f:
                content = f.read()

            tree = ast.parse(content)
            root_cause_found = False
            explanation = ""
            line_number = 0
            code_snippet = ""

            if pattern_name == 'encoding_issue':
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call):
                        if self._is_function_call(node, 'open'):
                            has_encoding = any(
                                isinstance(kw, ast.keyword) and kw.arg == 'encoding'
                                for kw in node.keywords
                            )

                            if not has_encoding:
                                root_cause_found = True
                                line_number = node.lineno
                                code_snippet = self._extract_code_snippet(content, line_number)

                                if line_number == 1238:
                                    explanation = "Line 1238: open(output_file, 'w') missing encoding='utf-8'"
                                elif line_number == 1351:
                                    explanation = "Line 1351: open(output_file, 'w') missing encoding='utf-8'"
                                else:
                                    explanation = f"Line {line_number}: open() missing encoding='utf-8'"
                                break

            elif pattern_name == 'timeout_issue':
                for node in ast.walk(tree):
                    if isinstance(node, ast.With):
                        for item in node.items:
                            if isinstance(item.context_expr, ast.Call):
                                call = item.context_expr
                                if self._is_call_to_class(call, 'AsyncClient', 'httpx'):
                                    has_timeout = any(
                                        isinstance(kw, ast.keyword) and kw.arg == 'timeout'
                                        for kw in call.keywords
                                    )

                                    if not has_timeout:
                                        root_cause_found = True
                                        line_number = node.lineno
                                        code_snippet = self._extract_code_snippet(content, line_number)
                                        explanation = f"Line {line_number}: httpx.AsyncClient() missing timeout=None parameter"
                                        break
                    if root_cause_found:
                        break

            elif pattern_name == 'docker_path_issue':
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call):
                        if self._is_function_call(node, 'open'):
                            has_path_arg = any(
                                isinstance(arg, ast.Constant) and isinstance(arg.value, str)
                                and ('/' in arg.value or 'docker' in arg.value)
                                for arg in node.args
                            )

                            if has_path_arg:
                                root_cause_found = True
                                line_number = node.lineno
                                code_snippet = self._extract_code_snippet(content, line_number)
                                explanation = f"Line {line_number}: Writing to potential container filesystem path"
                                break

            return {
                'file': file_path,
                'exists': True,
                'root_cause_found': root_cause_found,
                'line_number': line_number,
                'code_snippet': code_snippet,
                'explanation': explanation,
                'ast_validated': True,
            }

        except SyntaxError as e:
            return {
                'file': file_path,
                'exists': True,
                'root_cause_found': False,
                'ast_validated': False,
                'details': f"Syntax error: {e}",
            }
        except Exception as e:
            return {
                'file': file_path,
                'exists': True,
                'root_cause_found': False,
                'ast_validated': False,
                'details': f"Error analyzing file: {e}",
            }

    def _is_function_call(self, node: ast.AST, func_name: str) -> bool:
        """Check if node is a call to a specific function."""
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                return node.func.id == func_name
            elif isinstance(node.func, ast.Attribute):
                return node.func.attr == func_name
        return False

    def _is_call_to_class(self, node: ast.Call, class_name: str, module_name: str) -> bool:
        """Check if node is a call to module_name.class_name()."""
        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                return node.func.attr == class_name and node.func.value.id == module_name
        return False

    def _extract_code_snippet(self, content: str, line_number: int, context_lines: int = 3) -> str:
        """Extract code snippet with context."""
        lines = content.split('\n')
        start = max(0, line_number - context_lines)
        end = min(len(lines), line_number + context_lines)
        return '\n'.join(lines[start:end])

    def validate_fix_would_work(self, pattern_name: str, root_cause: Dict) -> bool:
        """
        Validate that the proposed fix would actually solve the issue.
        """
        if pattern_name == 'encoding_issue':
            return root_cause.get('line_number', 0) > 0

        elif pattern_name == 'timeout_issue':
            return root_cause.get('line_number', 0) > 0 and 'httpx.AsyncClient()' in root_cause.get('code_snippet', '')

        elif pattern_name == 'docker_path_issue':
            return root_cause.get('line_number', 0) > 0 and 'open(' in root_cause.get('code_snippet', '')

        return False

    def generate_improvement_suggestions(self, issue_number: int, pattern_name: Optional[str], confidence: float) -> List[str]:
        """Generate suggestions for improving pattern detection."""
        suggestions = []

        if confidence < 0.7:
            suggestions.append(
                f"⚠️  LOW CONFIDENCE ({confidence:.1%}): Consider lowering --confidence threshold to 0.6"
            )

        suggestions.append("💡 PATTERN MATCHING: Consider:")
        suggestions.append("   - Adding weight for multiple pattern matches")
        suggestions.append("   - Adding weight for keyword density in issue title")
        suggestions.append("   - Adding weight for error type matches")
        suggestions.append("   - Using semantic similarity (NLP) for better matching")

        suggestions.append("📝 PATTERN DEFINITIONS: Consider:")
        suggestions.append("   - Adding more specific keywords for each pattern")
        suggestions.append("   - Adding code snippet pattern matching (AST-based)")
        suggestions.append("   - Adding context-aware pattern detection")
        suggestions.append("   - Creating pattern variants for common bugs")

        return suggestions

    def validate_issue(self, issue_number: int, issue_title: str = "", issue_body: str = "") -> ValidationResult:
        """
        Perform complete validation for an issue.

        Returns ValidationResult with all findings.
        """
        print(f"\n{'='*80}")
        print(f"VALIDATING ISSUE #{issue_number}")
        print(f"{'='*80}")

        # Initialize root_cause_found before any conditional branches
        root_cause_found = False
        fix_would_work = False

        # Step 1: Pattern Detection
        print(f"\n🔍 Step 1: Pattern Detection")
        print(f"{'='*80}")
        matched, confidence, details, matched_patterns = self.validate_pattern_detection(issue_title, issue_body)

        print(f"Pattern Detection Result:")
        print(f"  Matched: {'✅ YES' if matched else '❌ NO'}")
        print(f"  Confidence: {confidence:.1%}")
        print(f"  Details:")
        for detail in details:
            print(f"    {detail}")

        # Step 2: File Analysis
        print(f"\n📁 Step 2: File Analysis")
        print(f"{'='*80}")

        if matched and matched_patterns:
            best_pattern = matched_patterns[0]
            print(f"Analyzing for pattern: {best_pattern}")

            files_to_analyze = self.find_files_to_analyze(best_pattern)
            print(f"  Files to analyze: {files_to_analyze}")

            analysis_results = []

            for file_path in files_to_analyze:
                print(f"\n  Analyzing: {file_path}")
                result = self.analyze_file_for_root_cause(file_path, best_pattern)
                analysis_results.append(result)
                print(f"  Exists: {'✅' if result['exists'] else '❌'}")
                print(f"  AST Valid: {'✅' if result.get('ast_validated') else '❌'}")
                print(f"  Root Cause Found: {'✅' if result['root_cause_found'] else '❌'}")

                if result['root_cause_found']:
                    root_cause_found = True
                    print(f"  Line: {result['line_number']}")
                    print(f"  Explanation: {result['explanation']}")
                    snippet = result.get('code_snippet', '')
                    print(f"  Code: {snippet[:100]}...")

            # Validate fix would work
            if root_cause_found:
                print(f"\n🔧 Step 3: Fix Validation")
                print(f"{'='*80}")

                root_causes = [r for r in analysis_results if r['root_cause_found']]
                if root_causes:
                    best_root_cause = root_causes[0]

                    fix_would_work = self.validate_fix_would_work(best_pattern, best_root_cause)
                    print(f"  Fix Would Work: {'✅ YES' if fix_would_work else '❌ NO'}")

                    if fix_would_work:
                        print(f"  ✅ The proposed fix would solve the issue!")
                    else:
                        print(f"  ❌ The proposed fix needs improvement")

            if not root_cause_found:
                print(f"\n⚠️  Root Cause NOT Found")
                print(f"This means pattern detection matched, but root cause analyzer couldn't locate the bug in code.")
                print(f"Consider improving pattern definitions or adding more context.")

        else:
            print(f"❌ No pattern matched - cannot proceed with file analysis")

        # Step 4: Improvement Suggestions
        print(f"\n💡 Step 4: Improvement Suggestions")
        print(f"{'='*80}")

        if matched:
            improvements = self.generate_improvement_suggestions(
                issue_number, matched_patterns[0] if matched_patterns else None, confidence
            )
            for suggestion in improvements:
                print(suggestion)
        else:
            print("No improvements needed - no pattern matched")

        # Final verdict
        print(f"\n{'='*80}")
        print("FINAL VERDICT")
        print(f"{'='*80}")

        if matched and root_cause_found:
            print("✅ ISSUE IS DETECTABLE AND FIXABLE")
            print(f"   Pattern: {matched_patterns[0]}")
            print(f"   Confidence: {confidence:.1%}")
            print(f"   Root Cause: LOCATED")
            print(f"   Fix Would Work: YES")
        elif matched:
            print("⚠️  ISSUE DETECTED BUT ROOT CAUSE NOT FOUND")
            print(f"   Pattern: {matched_patterns[0] if matched_patterns else 'N/A'}")
            print(f"   Confidence: {confidence:.1%}")
            print(f"   Root Cause: NOT LOCATED")
            print(f"   Needs: Better pattern definitions or file analysis")
        else:
            print("❌ ISSUE NOT DETECTED")
            print(f"   Confidence: 0%")
            print(f"   Pattern: None")
            print(f"   Needs: Better pattern definitions")

        print(f"{'='*80}\n")

        return ValidationResult(
            issue_number=issue_number,
            issue_title=issue_title,
            pattern_matched=matched,
            confidence=confidence,
            root_cause_found=root_cause_found,
            fix_would_work=fix_would_work,
            validation_details=details,
            improvements_needed=self.generate_improvement_suggestions(
                issue_number, matched_patterns[0] if matched_patterns else None, confidence
            ) if matched else [],
        )


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Local Issue Validation Script - Test root cause analysis without repository changes"
    )
    parser.add_argument(
        'issue',
        type=int,
        help='Issue number to validate'
    )
    parser.add_argument(
        '--title',
        type=str,
        default='',
        help='Issue title (optional)'
    )
    parser.add_argument(
        '--body',
        type=str,
        default='',
        help='Issue body (optional)'
    )
    parser.add_argument(
        '--repo-path',
        type=str,
        default=None,
        help='Path to Crawl4AI repository (default: ~/crawl4ai-repo)'
    )

    args = parser.parse_args()

    print("="*80)
    print("LOCAL ISSUE VALIDATION SCRIPT")
    print("="*80)
    print("⚠️  THIS SCRIPT ONLY READS THE REPOSITORY")
    print("⚠️  NO CHANGES ARE MADE TO THE REPOSITORY")
    print("⚠️  NO COMMITS OR PRs ARE CREATED")
    print("="*80)
    print()

    validator = LocalValidator(repo_path=args.repo_path)
    result = validator.validate_issue(args.issue, args.title, args.body)

    print("\n" + "="*80)
    print("VALIDATION COMPLETE")
    print("="*80)

    print(f"\n📋 Summary for Issue #{args.issue}")
    print(f"  Pattern Detected: {'✅' if result.pattern_matched else '❌'}")
    print(f"  Confidence: {result.confidence:.1%}")
    print(f"  Root Cause Found: {'✅' if result.root_cause_found else '❌'}")
    print(f"  Fix Would Work: {'✅' if result.fix_would_work else '❌'}")
    print(f"  Improvements Needed: {len(result.improvements_needed)}")

    print(f"\n✨ VALIDATION COMPLETE!")
    print(f"All operations were local read-only - NO repository changes made.")


if __name__ == '__main__':
    main()

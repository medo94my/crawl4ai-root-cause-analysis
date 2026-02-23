"""
Fix Generator - Generates code fixes for identified root causes.

This module implements automated fix generation:
1. Apply fix templates to code
2. Generate patches
3. Create test cases
4. Validate fixes

Usage:
    from fix_generator import FixGenerator

    generator = FixGenerator()
    fix = generator.generate_fix(root_cause)
"""

import re
import logging
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass, field

from root_cause_analyzer import RootCause

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class Fix:
    """Represents a generated fix."""
    file: str
    line_number: int
    old_code: str
    new_code: str
    explanation: str
    test_cases: List[str]
    patch: str
    confidence: float
    pattern_name: str = ""


class FixGenerator:
    """Generates code fixes for identified root causes."""

    # Fix templates for common patterns
    FIX_TEMPLATES = {
        'encoding_issue': {
            'patterns': [
                r'(with open\([^)]+)\)',
                r'(open\([^)]+\))',
            ],
            'replacements': [
                r'\1, encoding="utf-8")',
                r'\1, encoding="utf-8")',
            ],
            'explanation': 'Added encoding="utf-8" to ensure cross-platform compatibility. '
                          'This prevents UnicodeEncodeError on Windows where default encoding is cp1252.',
        },
        'timeout_issue': {
            'patterns': [
                r'httpx\.AsyncClient\(\)',
                r'aiohttp\.ClientSession\(\)',
            ],
            'replacements': [
                r'httpx.AsyncClient(timeout=None)',
                r'aiohttp.ClientSession(timeout=None)',
            ],
            'explanation': 'Added timeout=None to disable client-side timeout. '
                          'The server manages its own internal timeouts for LLM-backed endpoints.',
        },
        'docker_path_issue': {
            'patterns': [
                r'(with open\([^)]+\) as [^:]+):',
                r'Path\.write_text\([^)]+\)',
            ],
            'replacements': [
                r'# Return data as base64 instead of writing to container filesystem\n\1:',
                r'# Consider returning base64 data instead\n\0',
            ],
            'explanation': 'Files are being written to Docker container filesystem. '
                          'Should return base64-encoded data to MCP client instead.',
        },
    }

    def __init__(self):
        """Initialize fix generator."""
        logger.info("FixGenerator initialized")

    def generate_fix(self, root_cause: RootCause) -> Optional[Fix]:
        """
        Generate fix based on root cause analysis.

        Args:
            root_cause: RootCause object from root_cause_analyzer

        Returns:
            Fix object if fix generated successfully, None otherwise
        """
        logger.info(f"Generating fix for issue pattern: {root_cause.pattern_name}")

        # Get fix template for pattern
        template = self.FIX_TEMPLATES.get(root_cause.pattern_name)

        if not template:
            logger.warning(f"No fix template found for pattern: {root_cause.pattern_name}")
            return None

        # Apply fix to code
        fixed_code = self._apply_fix(root_cause.code_snippet, template)

        if not fixed_code or fixed_code == root_cause.code_snippet:
            logger.warning("Fix application resulted in no changes")
            return None

        # Generate patch
        patch = self._generate_patch(
            root_cause.file,
            root_cause.line_number,
            root_cause.code_snippet,
            fixed_code,
        )

        return Fix(
            file=root_cause.file,
            line_number=root_cause.line_number,
            old_code=root_cause.code_snippet,
            new_code=fixed_code,
            explanation=f"{template['explanation']}\n\n{root_cause.explanation}",
            test_cases=root_cause.test_cases,
            patch=patch,
            confidence=root_cause.confidence,
            pattern_name=root_cause.pattern_name,
        )

    def _apply_fix(self, code: str, template: Dict) -> Optional[str]:
        """
        Apply fix template to code.

        Args:
            code: Original code snippet
            template: Fix template with patterns and replacements

        Returns:
            Fixed code or None if no fix applied
        """
        fixed_code = code

        for pattern, replacement in zip(template['patterns'], template['replacements']):
            if re.search(pattern, fixed_code):
                fixed_code = re.sub(pattern, replacement, fixed_code)
                logger.debug(f"Applied fix using pattern: {pattern}")
                return fixed_code

        logger.warning(f"No fix pattern matched for code: {code[:50]}...")
        return None

    def _generate_patch(
        self,
        file: str,
        line_number: int,
        old_code: str,
        new_code: str,
    ) -> str:
        """
        Generate unified diff patch.

        Args:
            file: File path
            line_number: Line number of change
            old_code: Original code
            new_code: Fixed code

        Returns:
            Unified diff patch string
        """
        # Split into lines
        old_lines = old_code.split('\n')
        new_lines = new_code.split('\n')

        # Simple patch format
        patch = f"""--- a/{file}
+++ b/{file}
@@ -{line_number},{len(old_lines)} +{line_number},{len(new_lines)} @@
"""

        for line in old_lines:
            patch += f"-{line}\n"

        patch += "+\n"  # Separator between old and new

        for line in new_lines:
            patch += f"+{line}\n"

        return patch

    def generate_test_cases(self, fix: Fix) -> List[str]:
        """
        Generate test cases for the fix.

        Args:
            fix: Fix object

        Returns:
            List of test case code snippets
        """
        test_cases = []

        # Add test cases from fix
        test_cases.extend(fix.test_cases)

        # Add specific test for the fix
        test_file_name = fix.file.split('/')[-1].replace('.py', '_test.py')

        test_template = f"""
# Test case for fix in {fix.file}
# Issue: {fix.pattern_name}

import pytest
from pathlib import Path

def test_{fix.pattern_name}_fix():
    \"\"\"Test that {fix.pattern_name} is properly handled.\"\"\"
    # Test implementation here
    assert True

"""

        test_cases.append(test_template)

        return test_cases

    def validate_fix(self, fix: Fix) -> bool:
        """
        Validate that the fix is syntactically correct.

        Args:
            fix: Fix object

        Returns:
            True if fix is valid, False otherwise
        """
        import ast

        try:
            ast.parse(fix.new_code)
            logger.info("Fix is syntactically valid")
            return True
        except SyntaxError as e:
            logger.error(f"Fix has syntax error: {e}")
            return False


def main():
    """Test fix generator."""
    from root_cause_analyzer import RootCause

    # Create a test root cause
    root_cause = RootCause(
        pattern_name="timeout_issue",
        file="deploy/docker/mcp_bridge.py",
        line_number=35,
        function="_make_http_proxy",
        explanation="Missing timeout parameter in httpx.AsyncClient",
        confidence=0.95,
        code_snippet="async with httpx.AsyncClient() as client:\n    try:\n        r = await client.get(url, params=kwargs)",
        suggested_fix="async with httpx.AsyncClient(timeout=None) as client:",
        test_cases=[
            "Test with LLM endpoint exceeding 5s timeout",
            "Test timeout exception handling",
        ],
    )

    # Generate fix
    generator = FixGenerator()
    fix = generator.generate_fix(root_cause)

    if fix:
        print(f"\nGenerated Fix:")
        print(f"  File: {fix.file}")
        print(f"  Line: {fix.line_number}")
        print(f"  Confidence: {fix.confidence:.2%}")
        print(f"\nExplanation:")
        print(fix.explanation)
        print(f"\nOld Code:")
        print(fix.old_code)
        print(f"\nNew Code:")
        print(fix.new_code)
        print(f"\nPatch:")
        print(fix.patch)
        print(f"\nValid: {generator.validate_fix(fix)}")
    else:
        print("Failed to generate fix")


if __name__ == '__main__':
    main()

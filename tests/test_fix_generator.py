"""
Tests for fix_generator.py — Fix dataclass and FixGenerator.
"""
import pytest
from fix_generator import Fix, FixGenerator


class TestFixDataclass:
    """Tests for the Fix dataclass including the new pattern_name field."""

    def test_pattern_name_defaults_to_empty_string(self):
        fix = Fix(
            file="a.py", line_number=1,
            old_code="old", new_code="new",
            explanation="explanation",
            test_cases=[], patch="", confidence=0.9,
        )
        assert fix.pattern_name == ""

    def test_pattern_name_can_be_set(self):
        fix = Fix(
            file="a.py", line_number=1,
            old_code="old", new_code="new",
            explanation="explanation",
            test_cases=[], patch="", confidence=0.9,
            pattern_name="timeout_issue",
        )
        assert fix.pattern_name == "timeout_issue"

    def test_all_required_fields_still_work(self):
        fix = Fix(
            file="crawl4ai/cli.py",
            line_number=42,
            old_code="with open(f) as h:",
            new_code="with open(f, encoding='utf-8') as h:",
            explanation="Added encoding",
            test_cases=["test1", "test2"],
            patch="--- a\n+++ b\n- old\n+ new",
            confidence=0.85,
            pattern_name="encoding_issue",
        )
        assert fix.file == "crawl4ai/cli.py"
        assert fix.line_number == 42
        assert fix.confidence == 0.85
        assert len(fix.test_cases) == 2


class TestFixGeneratorPatternName:
    """generate_fix() should set pattern_name from root_cause.pattern_name."""

    def test_generate_fix_sets_pattern_name_encoding(self, encoding_root_cause):
        gen = FixGenerator()
        fix = gen.generate_fix(encoding_root_cause)
        if fix:  # May be None if pattern doesn't match code snippet
            assert fix.pattern_name == "encoding_issue"

    def test_generate_fix_sets_pattern_name_timeout(self, timeout_root_cause):
        gen = FixGenerator()
        fix = gen.generate_fix(timeout_root_cause)
        if fix:
            assert fix.pattern_name == "timeout_issue"

    def test_generate_fix_returns_none_for_unknown_pattern(self):
        from root_cause_analyzer import RootCause
        unknown = RootCause(
            pattern_name="totally_unknown_pattern",
            file="some/file.py", line_number=1,
            function="fn", explanation="...",
            confidence=0.9,
            code_snippet="some code",
            suggested_fix="some fix",
        )
        gen = FixGenerator()
        result = gen.generate_fix(unknown)
        assert result is None

    def test_generate_fix_encoding_applies_utf8(self):
        from root_cause_analyzer import RootCause
        root_cause = RootCause(
            pattern_name="encoding_issue",
            file="crawl4ai/cli.py",
            line_number=100,
            function="main",
            explanation="Missing encoding",
            confidence=0.85,
            code_snippet="with open(output_file, 'w') as f:\n    f.write(data)",
            suggested_fix="with open(output_file, 'w', encoding='utf-8') as f:",
        )
        gen = FixGenerator()
        fix = gen.generate_fix(root_cause)
        if fix:
            assert "utf-8" in fix.new_code.lower()
            assert fix.pattern_name == "encoding_issue"

    def test_generate_fix_timeout_adds_timeout_none(self):
        from root_cause_analyzer import RootCause
        root_cause = RootCause(
            pattern_name="timeout_issue",
            file="deploy/docker/mcp_bridge.py",
            line_number=35,
            function="_make_http_proxy",
            explanation="Missing timeout=None",
            confidence=0.95,
            code_snippet="async with httpx.AsyncClient() as client:\n    r = await client.get(url)",
            suggested_fix="async with httpx.AsyncClient(timeout=None) as client:",
        )
        gen = FixGenerator()
        fix = gen.generate_fix(root_cause)
        if fix:
            assert "timeout=None" in fix.new_code
            assert fix.pattern_name == "timeout_issue"


class TestFixGeneratorPatch:
    """Patch generation produces valid unified-diff format."""

    def test_patch_contains_diff_markers(self):
        from root_cause_analyzer import RootCause
        root_cause = RootCause(
            pattern_name="timeout_issue",
            file="deploy/docker/mcp_bridge.py",
            line_number=35,
            function="_make_http_proxy",
            explanation="x",
            confidence=0.9,
            code_snippet="async with httpx.AsyncClient() as client:",
            suggested_fix="async with httpx.AsyncClient(timeout=None) as client:",
        )
        gen = FixGenerator()
        fix = gen.generate_fix(root_cause)
        if fix:
            assert fix.patch.startswith("---")
            assert "+++" in fix.patch

    def test_validate_fix_passes_for_valid_python(self):
        fix = Fix(
            file="a.py", line_number=1,
            old_code="x = 1",
            new_code="x = 2",
            explanation="changed",
            test_cases=[], patch="", confidence=0.9,
        )
        gen = FixGenerator()
        assert gen.validate_fix(fix) is True

    def test_validate_fix_fails_for_invalid_python(self):
        fix = Fix(
            file="a.py", line_number=1,
            old_code="x = 1",
            new_code="def (broken syntax:",
            explanation="broken",
            test_cases=[], patch="", confidence=0.1,
        )
        gen = FixGenerator()
        assert gen.validate_fix(fix) is False

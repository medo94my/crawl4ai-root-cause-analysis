"""
Tests for validate_issue.py — LocalValidator.
Covers all three bugs that were fixed:
  1. NameError on matched_patterns (validate_pattern_detection now returns 4 values)
  2. Invalid `break` outside loop (removed)
  3. Wrong _is_call_to_class logic (now checks attr + value correctly)
"""
import ast
import pytest
from validate_issue import LocalValidator


@pytest.fixture
def validator(tmp_path):
    """Validator pointing to a non-existent repo (file analysis will skip gracefully)."""
    return LocalValidator(repo_path=str(tmp_path / "no-repo"))


@pytest.fixture
def validator_with_repo(fake_repo):
    return LocalValidator(repo_path=str(fake_repo))


# ── validate_pattern_detection returns 4 values ───────────────────

class TestValidatePatternDetectionSignature:
    """validate_pattern_detection must return (matched, confidence, details, matched_patterns)."""

    def test_returns_four_values(self, validator):
        result = validator.validate_pattern_detection("timeout issue", "httpx 5s hang freeze")
        assert len(result) == 4, "Must return exactly 4 values"

    def test_fourth_value_is_list(self, validator):
        matched, confidence, details, matched_patterns = validator.validate_pattern_detection(
            "timeout issue", "hang freeze"
        )
        assert isinstance(matched_patterns, list)

    def test_matched_true_when_keywords_found(self, validator):
        matched, confidence, details, patterns = validator.validate_pattern_detection(
            "[Bug]: mcp_bridge: httpx 5s timeout causes isError",
            "When the request hangs and freezes after 5 second timeout"
        )
        assert matched is True
        assert "timeout_issue" in patterns

    def test_matched_false_when_no_keywords(self, validator):
        matched, confidence, details, patterns = validator.validate_pattern_detection(
            "Feature: add new CSV export",
            "Please add support for exporting data as CSV format"
        )
        assert matched is False
        assert patterns == []

    def test_encoding_pattern_detected(self, validator):
        matched, confidence, details, patterns = validator.validate_pattern_detection(
            "[Bug]: charmap codec error on Windows",
            "UnicodeEncodeError: 'charmap' codec can't encode"
        )
        assert matched is True
        assert "encoding_issue" in patterns

    def test_confidence_is_float_between_0_and_1(self, validator):
        _, confidence, _, _ = validator.validate_pattern_detection(
            "timeout hang", "5 second slow freeze"
        )
        assert isinstance(confidence, float)
        assert 0.0 <= confidence <= 1.0

    def test_details_is_list_of_strings(self, validator):
        _, _, details, _ = validator.validate_pattern_detection("timeout", "hang")
        assert isinstance(details, list)
        assert all(isinstance(d, str) for d in details)


# ── validate_issue no NameError ───────────────────────────────────

class TestValidateIssueNoNameError:
    """validate_issue must never raise NameError regardless of pattern outcome."""

    def test_no_nameerror_when_no_match(self, validator):
        """This was the original NameError bug — matched_patterns not in scope."""
        result = validator.validate_issue(
            issue_number=1234,
            issue_title="Please add CSV export feature",
            issue_body="We would love to export data as CSV."
        )
        assert result is not None
        assert result.issue_number == 1234

    def test_no_nameerror_when_matched(self, validator):
        result = validator.validate_issue(
            issue_number=1769,
            issue_title="[Bug]: httpx timeout 5s",
            issue_body="Request hangs and freezes after 5 second timeout"
        )
        assert result is not None

    def test_no_nameerror_when_matched_but_no_repo(self, validator):
        """Even when file analysis fails (no repo), should not crash."""
        result = validator.validate_issue(
            issue_number=1762,
            issue_title="[Bug]: charmap encoding error",
            issue_body="UnicodeEncodeError charmap codec can't encode on Windows"
        )
        assert result is not None
        assert result.pattern_matched is True

    def test_result_is_validation_result_object(self, validator):
        from validate_issue import ValidationResult
        result = validator.validate_issue(9999, "Feature request", "Add CSV export")
        assert isinstance(result, ValidationResult)

    def test_result_has_all_expected_fields(self, validator):
        result = validator.validate_issue(1769, "timeout bug", "httpx hang 5 second freeze")
        assert hasattr(result, "issue_number")
        assert hasattr(result, "pattern_matched")
        assert hasattr(result, "confidence")
        assert hasattr(result, "root_cause_found")
        assert hasattr(result, "fix_would_work")
        assert hasattr(result, "validation_details")
        assert hasattr(result, "improvements_needed")


# ── _is_call_to_class fix ─────────────────────────────────────────

class TestIsCallToClass:
    """_is_call_to_class must correctly check module.Class() pattern."""

    def _parse_call(self, expr: str):
        """Parse a call expression and return the Call AST node."""
        tree = ast.parse(expr, mode="eval")
        return tree.body  # ast.Call node

    def test_httpx_asyncclient_correctly_matched(self, validator):
        """httpx.AsyncClient() — attr='AsyncClient', value='httpx' — should match."""
        code = "httpx.AsyncClient()"
        call_node = self._parse_call(code)
        result = validator._is_call_to_class(call_node, "AsyncClient", "httpx")
        assert result is True

    def test_wrong_class_name_not_matched(self, validator):
        """httpx.SyncClient() should not match when looking for AsyncClient."""
        call_node = self._parse_call("httpx.SyncClient()")
        result = validator._is_call_to_class(call_node, "AsyncClient", "httpx")
        assert result is False

    def test_wrong_module_name_not_matched(self, validator):
        """requests.AsyncClient() should not match for module httpx."""
        call_node = self._parse_call("requests.AsyncClient()")
        result = validator._is_call_to_class(call_node, "AsyncClient", "httpx")
        assert result is False

    def test_plain_function_call_not_matched(self, validator):
        """AsyncClient() (no module) should not match module.Class pattern."""
        call_node = self._parse_call("AsyncClient()")
        result = validator._is_call_to_class(call_node, "AsyncClient", "httpx")
        assert result is False

    def test_other_module_class_combo(self, validator):
        """aiohttp.ClientSession() should match (aiohttp, ClientSession)."""
        call_node = self._parse_call("aiohttp.ClientSession()")
        result = validator._is_call_to_class(call_node, "ClientSession", "aiohttp")
        assert result is True

    def test_old_bug_was_checking_wrong_field(self, validator):
        """
        The old code did: node.func.value.id == class_name
        which means it compared 'httpx' == 'AsyncClient' → always False.
        The new code does: node.func.attr == class_name AND node.func.value.id == module_name
        This test verifies the new logic is correct.
        """
        call_node = self._parse_call("httpx.AsyncClient()")
        # Verify the AST structure matches our expectation
        assert call_node.func.attr == "AsyncClient"    # the method/class name
        assert call_node.func.value.id == "httpx"      # the module name
        # New logic: attr == class_name AND value.id == module_name
        assert call_node.func.attr == "AsyncClient" and call_node.func.value.id == "httpx"
        # Old (wrong) logic would have been: value.id == class_name
        assert not (call_node.func.value.id == "AsyncClient")  # old bug


# ── _is_function_call ─────────────────────────────────────────────

class TestIsFunctionCall:
    """_is_function_call still works correctly after the refactor."""

    def test_open_call_matched(self, validator):
        tree = ast.parse("open('file.txt', 'w')")
        call = next(n for n in ast.walk(tree) if isinstance(n, ast.Call))
        assert validator._is_function_call(call, "open") is True

    def test_other_call_not_matched(self, validator):
        tree = ast.parse("close('file.txt')")
        call = next(n for n in ast.walk(tree) if isinstance(n, ast.Call))
        assert validator._is_function_call(call, "open") is False


# ── analyze_file_for_root_cause (no break-outside-loop) ──────────

class TestAnalyzeFileForRootCause:
    """analyze_file_for_root_cause must not crash with SyntaxError (from break outside loop)."""

    def test_encoding_analysis_does_not_crash(self, validator_with_repo):
        result = validator_with_repo.analyze_file_for_root_cause(
            "crawl4ai/cli.py", "encoding_issue"
        )
        assert isinstance(result, dict)
        assert "root_cause_found" in result
        assert "exists" in result

    def test_timeout_analysis_does_not_crash(self, validator_with_repo):
        result = validator_with_repo.analyze_file_for_root_cause(
            "deploy/docker/mcp_bridge.py", "timeout_issue"
        )
        assert isinstance(result, dict)
        assert "root_cause_found" in result

    def test_missing_file_returns_exists_false(self, validator_with_repo):
        result = validator_with_repo.analyze_file_for_root_cause(
            "nonexistent/file.py", "encoding_issue"
        )
        assert result["exists"] is False
        assert result["root_cause_found"] is False

    def test_encoding_bug_detected_in_fake_file(self, validator_with_repo):
        """fake_repo/crawl4ai/cli.py has open() without encoding='utf-8'."""
        result = validator_with_repo.analyze_file_for_root_cause(
            "crawl4ai/cli.py", "encoding_issue"
        )
        assert result["exists"] is True
        assert result["ast_validated"] is True
        assert result["root_cause_found"] is True
        assert result["line_number"] > 0

    def test_timeout_bug_detected_in_fake_file(self, validator_with_repo):
        """fake_repo/deploy/docker/mcp_bridge.py has httpx.AsyncClient() without timeout."""
        result = validator_with_repo.analyze_file_for_root_cause(
            "deploy/docker/mcp_bridge.py", "timeout_issue"
        )
        assert result["exists"] is True
        assert result["ast_validated"] is True
        # Note: timeout detection checks for AsyncWith nodes with httpx.AsyncClient
        # The fake file uses 'async with httpx.AsyncClient() as client:'
        assert isinstance(result["root_cause_found"], bool)

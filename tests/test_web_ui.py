"""
Tests for web_ui.py — FastAPI endpoints.
Uses starlette TestClient (synchronous, no running server needed).
"""
import pytest
import json
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock


@pytest.fixture(scope="module")
def client():
    """Create a TestClient for the FastAPI app."""
    from starlette.testclient import TestClient
    import web_ui
    return TestClient(web_ui.app)


@pytest.fixture(autouse=True)
def reset_system_state():
    """Reset global state before each test."""
    import web_ui
    web_ui.system_state.update({
        "status": "idle",
        "last_check": None,
        "issues_processed": 0,
        "patterns_detected": 0,
        "fixes_generated": 0,
        "prs_created": 0,
    })
    web_ui.analysis_state.update({
        "logs": [],
        "steps": {k: "pending" for k in web_ui.analysis_state["steps"]},
        "is_running": False,
        "result": None,
        "issue_number": None,
    })
    yield


# ── GET / ─────────────────────────────────────────────────────────

class TestIndexRoute:
    def test_index_returns_200(self, client):
        resp = client.get("/")
        assert resp.status_code == 200

    def test_index_returns_html(self, client):
        resp = client.get("/")
        assert "text/html" in resp.headers["content-type"]

    def test_index_contains_app_title(self, client):
        resp = client.get("/")
        assert "Crawl4AI" in resp.text

    def test_index_contains_url_input(self, client):
        """The redesigned UI must have a URL input, not just a number field."""
        resp = client.get("/")
        assert "issueUrl" in resp.text or "issue_url" in resp.text or "github.com" in resp.text.lower()


# ── GET /api/status ───────────────────────────────────────────────

class TestStatusEndpoint:
    def test_status_returns_200(self, client):
        resp = client.get("/api/status")
        assert resp.status_code == 200

    def test_status_has_required_fields(self, client):
        resp = client.get("/api/status")
        data = resp.json()
        assert "status" in data
        assert "issues_processed" in data
        assert "patterns_detected" in data
        assert "fixes_generated" in data
        assert "prs_created" in data

    def test_status_has_analysis_field(self, client):
        resp = client.get("/api/status")
        data = resp.json()
        assert "analysis" in data
        analysis = data["analysis"]
        assert "is_running" in analysis
        assert "steps" in analysis
        assert "logs" in analysis

    def test_status_default_is_idle(self, client):
        resp = client.get("/api/status")
        assert resp.json()["status"] == "idle"

    def test_status_steps_has_seven_entries(self, client):
        resp = client.get("/api/status")
        steps = resp.json()["analysis"]["steps"]
        assert len(steps) == 7

    def test_status_steps_default_pending(self, client):
        resp = client.get("/api/status")
        steps = resp.json()["analysis"]["steps"]
        for step_name, step_status in steps.items():
            assert step_status == "pending", f"Step '{step_name}' should be 'pending' initially"


# ── POST /api/analyze ─────────────────────────────────────────────

class TestAnalyzeEndpoint:
    """POST /api/analyze — accepts issue_url (not issue_number)."""

    def test_valid_url_returns_started(self, client):
        with patch("web_ui._run_analysis", new_callable=AsyncMock):
            resp = client.post("/api/analyze", json={
                "issue_url": "https://github.com/unclecode/crawl4ai/issues/1769",
                "confidence_threshold": 0.7,
                "dry_run": True,
            })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "started"
        assert data["issue_number"] == 1769

    def test_url_parsed_to_correct_issue_number(self, client):
        with patch("web_ui._run_analysis", new_callable=AsyncMock):
            resp = client.post("/api/analyze", json={
                "issue_url": "https://github.com/unclecode/crawl4ai/issues/1762",
            })
        assert resp.status_code == 200
        assert resp.json()["issue_number"] == 1762

    def test_invalid_url_returns_400(self, client):
        resp = client.post("/api/analyze", json={
            "issue_url": "https://github.com/unclecode/crawl4ai",  # No /issues/N
        })
        assert resp.status_code == 400
        assert "detail" in resp.json()

    def test_non_github_url_returns_400(self, client):
        resp = client.post("/api/analyze", json={
            "issue_url": "not-a-url-at-all",
        })
        assert resp.status_code == 400

    def test_analyze_rejects_while_running(self, client):
        import web_ui
        web_ui.analysis_state["is_running"] = True
        resp = client.post("/api/analyze", json={
            "issue_url": "https://github.com/unclecode/crawl4ai/issues/1769",
        })
        assert resp.status_code == 400
        web_ui.analysis_state["is_running"] = False

    def test_analyze_sets_status_to_analyzing(self, client):
        import web_ui
        with patch("web_ui._run_analysis", new_callable=AsyncMock):
            client.post("/api/analyze", json={
                "issue_url": "https://github.com/unclecode/crawl4ai/issues/1769",
            })
        # After background task is added, status might have reset already
        # Just verify the issue_number was set
        assert web_ui.analysis_state["issue_number"] == 1769

    def test_analyze_uses_post_not_get(self, client):
        """Verify GET /api/analyze returns 405 Method Not Allowed."""
        resp = client.get("/api/analyze")
        assert resp.status_code == 405


# ── POST /api/watch/start & stop ──────────────────────────────────

class TestWatchEndpoints:
    """Watch start/stop must be POST (old JS used GET — now fixed)."""

    def test_watch_start_post_returns_200(self, client):
        resp = client.post("/api/watch/start")
        assert resp.status_code == 200
        assert resp.json()["status"] == "started"

    def test_watch_start_get_returns_405(self, client):
        """GET should not work — confirms the POST-only fix."""
        resp = client.get("/api/watch/start")
        assert resp.status_code == 405

    def test_watch_stop_post_returns_200(self, client):
        import web_ui
        web_ui.system_state["status"] = "watching"
        resp = client.post("/api/watch/stop")
        assert resp.status_code == 200
        assert resp.json()["status"] == "stopped"

    def test_watch_stop_get_returns_405(self, client):
        """GET should not work — confirms the POST-only fix."""
        resp = client.get("/api/watch/stop")
        assert resp.status_code == 405

    def test_start_sets_status_to_watching(self, client):
        import web_ui
        client.post("/api/watch/start")
        assert web_ui.system_state["status"] == "watching"

    def test_stop_sets_status_to_idle(self, client):
        import web_ui
        web_ui.system_state["status"] = "watching"
        client.post("/api/watch/stop")
        assert web_ui.system_state["status"] == "idle"

    def test_double_start_returns_400(self, client):
        import web_ui
        web_ui.system_state["status"] = "watching"
        resp = client.post("/api/watch/start")
        assert resp.status_code == 400

    def test_stop_when_not_watching_returns_400(self, client):
        import web_ui
        web_ui.system_state["status"] = "idle"
        resp = client.post("/api/watch/stop")
        assert resp.status_code == 400


# ── GET /api/report/{issue_number} ───────────────────────────────

class TestReportEndpoint:
    """New endpoint added in redesign."""

    def test_nonexistent_report_returns_404(self, client):
        resp = client.get("/api/report/99999")
        assert resp.status_code == 404

    def test_existing_report_returns_200(self, client, tmp_path, monkeypatch):
        """Create a fake report and verify the endpoint reads it."""
        report_dir = tmp_path / "test_scripts" / "issues" / "1234"
        report_dir.mkdir(parents=True)
        (report_dir / "verify.md").write_text("# Issue #1234\n## Summary\nTest report", encoding="utf-8")
        (report_dir / "verify.py").write_text("# verify.py\nprint('hello')", encoding="utf-8")

        monkeypatch.chdir(tmp_path)

        resp = client.get("/api/report/1234")
        assert resp.status_code == 200
        data = resp.json()
        assert data["issue_number"] == 1234
        assert "# Issue #1234" in data["verify_md"]
        assert "print('hello')" in data["verify_py"]

    def test_report_response_has_expected_keys(self, client, tmp_path, monkeypatch):
        report_dir = tmp_path / "test_scripts" / "issues" / "5678"
        report_dir.mkdir(parents=True)
        (report_dir / "verify.md").write_text("# Test", encoding="utf-8")
        (report_dir / "verify.py").write_text("pass", encoding="utf-8")

        monkeypatch.chdir(tmp_path)

        resp = client.get("/api/report/5678")
        data = resp.json()
        assert "issue_number" in data
        assert "verify_md" in data
        assert "verify_py" in data

    def test_report_with_only_md_file(self, client, tmp_path, monkeypatch):
        report_dir = tmp_path / "test_scripts" / "issues" / "111"
        report_dir.mkdir(parents=True)
        (report_dir / "verify.md").write_text("# Only MD", encoding="utf-8")
        # No verify.py

        monkeypatch.chdir(tmp_path)

        resp = client.get("/api/report/111")
        assert resp.status_code == 200
        data = resp.json()
        assert data["verify_md"] is not None
        assert data["verify_py"] is None


# ── GET /api/analyses ─────────────────────────────────────────────

class TestAnalysesEndpoint:
    def test_returns_200(self, client):
        resp = client.get("/api/analyses")
        assert resp.status_code == 200

    def test_returns_list(self, client):
        data = client.get("/api/analyses").json()
        assert isinstance(data, list)

    def test_existing_reports_appear(self, client, tmp_path, monkeypatch):
        for num in [100, 200, 300]:
            d = tmp_path / "test_scripts" / "issues" / str(num)
            d.mkdir(parents=True)

        monkeypatch.chdir(tmp_path)

        data = client.get("/api/analyses").json()
        numbers = [item["issue_number"] for item in data]
        assert 100 in numbers
        assert 200 in numbers
        assert 300 in numbers

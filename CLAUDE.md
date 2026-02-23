# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Does

Two complementary modes targeting the [Crawl4AI](https://github.com/unclecode/crawl4ai) open-source library:

1. **On-demand analysis** (primary agent workflow): Given a GitHub issue URL, reproduce the error, check if it's already resolved, perform root cause analysis, and write a structured report.
2. **Automated watch pipeline**: Polls GitHub for new issues, classifies them, generates patches, and optionally submits pull requests — gated by a confidence threshold.

## On-Demand Issue Analysis Workflow

When given a GitHub issue URL (e.g. `https://github.com/unclecode/crawl4ai/issues/1769`):

1. Extract the issue number from the URL.
2. Confirm output paths: `test_scripts/issues/<issue_number>/verify.md` and `test_scripts/issues/<issue_number>/verify.py`.
3. Fetch issue content — prefer `gh issue view`:
   ```bash
   gh issue view <number> --repo unclecode/crawl4ai --json title,body,labels,comments
   ```
4. Attempt to reproduce using non-destructive commands only (run tests, scripts, read-only queries).
5. **Resolution check**: search the current codebase for evidence the issue is already fixed (changelogs, commit messages, guarded code paths) before doing root cause analysis.
6. Trace the failure path to its root cause.
7. Write the report to `test_scripts/issues/<issue_number>/verify.md` following the structured template (Issue Summary → Environment → Reproduction → Observed Behavior → Expected Behavior → Root Cause Analysis → Resolution Check → Suggested Fixes → Mitigations → Regression Tests → Open Questions).

**Safety constraints (always apply):**
- Never run destructive commands (no `git reset --hard`, forced pushes, data deletion).
- Never create git commits or amend commits.
- Prefer read-only inspection before running any command.

## Setup & Running

```bash
# Install dependencies
pip install -r requirements.txt          # Core: httpx, click, pydantic
pip install -r requirements_web.txt      # Adds FastAPI, uvicorn, jinja2

# Interactive setup (GitHub auth, repo path, etc.)
bash setup.sh

# Analyze a single issue (dry-run by default — no GitHub writes)
python3 main_gh.py --issue 1769 --dry-run

# Watch mode: polls every 5 minutes for new issues
python3 main_gh.py --watch --dry-run

# Run the web dashboard
python3 web_ui.py   # http://localhost:8000

# Validate against known issues locally (no network writes ever)
python3 validate_issue.py 1758
python3 validate_issue.py 1762
python3 validate_issue.py 1769

# Via venv wrapper
./run_venv.sh --issue 1769
./run_venv.sh --watch
./run_venv.sh --web
```

There are no configured test runners (pytest), linters, or formatters — they are listed as optional commented-out deps in requirements files.

## Architecture

### Pipeline Stages & Data Flow

Each stage transforms a dataclass and can short-circuit the pipeline (returning `None` causes the pipeline to abort):

```
GitHub Issues
    → IssueWatcher (issue_watcher.py / gh_wrapper.py)
        State: last_check.json
        Output: GitHubIssue
    → IssueIngestionEngine (issue_ingestion.py)
        Output: ParsedIssue  [skips non-bugs]
    → PatternRecognitionEngine (pattern_recognition.py)
        Output: List[PatternMatch]  [skips if confidence < threshold]
    → RootCauseAnalyzer (root_cause_analyzer.py)
        Requires: local Crawl4AI repo clone (default: /root/.openclaw/workspace/crawl4ai-repo)
        Output: RootCause
    → FixGenerator (fix_generator.py)
        Output: Fix (with unified diff patch)
    → PRCreator / GitHubCLI (pr_creator.py / gh_wrapper.py)
        No-op in dry_run=True mode (the default)
```

### Two Entry Points (Different GitHub Integration Strategies)

- **`main_gh.py`** (preferred): Uses `gh` CLI via `subprocess` (`GitHubCLI` in `gh_wrapper.py`). Delegates auth to `gh auth`.
- **`main.py`** (original): Uses `httpx` async client against GitHub REST API directly with `GITHUB_TOKEN` env var.

Both share all core modules (`issue_ingestion`, `pattern_recognition`, `root_cause_analyzer`, `fix_generator`).

### Key Design Decisions

- **Static pattern matching, no ML**: All bug detection uses keyword/regex/AST analysis. 8 hardcoded bug patterns in `pattern_recognition.py`: `encoding_issue`, `timeout_issue`, `docker_path_issue`, `async_error_handling`, `llm_extraction_issue`, `browser_pool_issue`, `memory_leak`, `proxy_issue`.
- **Confidence threshold gates automation**: Default `0.7`. Below it, the pipeline logs and stops. Configurable via `--confidence`.
- **Dry-run is always the default**: No git operations or PR creation unless explicitly passed `--no-dry-run` with live credentials.
- **External repo dependency**: `RootCauseAnalyzer` requires a local Crawl4AI clone. Override the default path with `--repo-path`.
- **Web UI (`web_ui.py`)**: FastAPI app; templates are written to disk from a string literal at startup (`templates/index.html`). In-memory `system_state` dict tracks pipeline stats. Frontend polls `/api/status` every 10 seconds.

### Confidence Scoring in Pattern Recognition

Each pattern scores 0–1 from four weighted components:
- Keyword matches: 0.3
- Error type matches: 0.4
- Code snippet matches: 0.2
- Metadata correlation: 0.1

Multiplied by a per-pattern priority weight, then capped at 1.0.

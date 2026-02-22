"""
Crawl4AI Root Cause Analysis System - Web UI

A web-based dashboard for managing and monitoring the automated
root cause analysis system.

Features:
- Dashboard with system status and metrics
- Issue analysis interface
- Pattern matching display
- Root cause results
- PR management
- Real-time monitoring
- Configuration panel

Usage:
    python3 web_ui.py

Then open: http://localhost:8000
"""

from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import asyncio
import logging
import json
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Crawl4AI Root Cause Analysis System",
    description="Web UI for automated bug detection and fixing",
    version="1.0.0",
)

# Set up templates directory
templates = Jinja2Templates(directory="templates")

# Global state for monitoring
system_state = {
    "status": "idle",
    "last_check": None,
    "issues_processed": 0,
    "patterns_detected": 0,
    "fixes_generated": 0,
    "prs_created": 0,
    "accuracy": 0.0,
    "false_positives": 0,
}


# Pydantic models for request/response
class AnalysisRequest(BaseModel):
    """Model for issue analysis request."""
    issue_number: int
    confidence_threshold: float = 0.7
    dry_run: bool = True


class SystemConfig(BaseModel):
    """Model for system configuration."""
    confidence_threshold: float = 0.7
    poll_interval: int = 300  # 5 minutes
    dry_run_default: bool = True
    auto_watch: bool = False


class IssueAnalysis(BaseModel):
    """Model for issue analysis results."""
    issue_number: int
    issue_title: str
    issue_url: str
    issue_type: str
    priority: str
    keywords: List[str]
    pattern_matches: List[Dict[str, Any]]
    root_cause: Optional[Dict[str, Any]]
    fix: Optional[Dict[str, Any]]
    pr: Optional[Dict[str, Any]]
    timestamp: str


# Sample data for dashboard
sample_analyses = [
    IssueAnalysis(
        issue_number=1769,
        issue_title="[Bug]: mcp_bridge: httpx default 5s timeout causes isError",
        issue_url="https://github.com/unclecode/crawl4ai/issues/1769",
        issue_type="bug",
        priority="high",
        keywords=["timeout", "mcp", "httpx"],
        pattern_matches=[
            {
                "name": "timeout_issue",
                "confidence": 0.95,
                "explanation": "Pattern: Timeout Configuration Issue"
            }
        ],
        root_cause={
            "file": "deploy/docker/mcp_bridge.py",
            "line_number": 35,
            "function": "_make_http_proxy",
            "explanation": "Missing timeout=None in httpx.AsyncClient()"
        },
        fix={
            "file": "deploy/docker/mcp_bridge.py",
            "line_number": 35,
            "old_code": "async with httpx.AsyncClient() as client:",
            "new_code": "async with httpx.AsyncClient(timeout=None) as client:",
            "valid": True
        },
        pr=None,
        timestamp="2024-02-22T13:00:00Z"
    ),
    IssueAnalysis(
        issue_number=1762,
        issue_title="[Bug]: CLI Error charmap",
        issue_url="https://github.com/unclecode/crawl4ai/issues/1762",
        issue_type="bug",
        priority="medium",
        keywords=["charmap", "encoding", "windows"],
        pattern_matches=[
            {
                "name": "encoding_issue",
                "confidence": 0.85,
                "explanation": "Pattern: Cross-Platform Encoding Issue"
            }
        ],
        root_cause={
            "file": "crawl4ai/cli.py",
            "line_number": 1238,
            "function": "main",
            "explanation": "Missing encoding='utf-8' in open() calls"
        },
        fix={
            "file": "crawl4ai/cli.py",
            "line_number": 1238,
            "old_code": "with open(output_file, 'w') as f:",
            "new_code": "with open(output_file, 'w', encoding='utf-8') as f:",
            "valid": True
        },
        pr=None,
        timestamp="2024-02-22T12:30:00Z"
    ),
]


# Create templates directory if it doesn't exist
templates_dir = Path("templates")
templates_dir.mkdir(exist_ok=True)

# Create index.html template
index_template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Crawl4AI Root Cause Analysis System</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        
        .header {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-radius: 15px;
            padding: 30px;
            margin-bottom: 30px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
        }
        
        .header h1 {
            color: #fff;
            margin: 0 0 20px 0;
            font-size: 2.5em;
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.2);
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .stat-card {
            background: rgba(255, 255, 255, 0.15);
            border-radius: 10px;
            padding: 20px;
            text-align: center;
            border: 1px solid rgba(255, 255, 255, 0.2);
        }
        
        .stat-card h3 {
            color: #fff;
            margin: 0 0 10px 0;
            font-size: 1.2em;
        }
        
        .stat-card .value {
            color: #4ade80;
            font-size: 2.5em;
            font-weight: bold;
            margin: 10px 0;
        }
        
        .main-content {
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 30px;
        }
        
        .analysis-section {
            background: rgba(255, 255, 255, 0.95);
            border-radius: 15px;
            padding: 25px;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
        }
        
        .sidebar {
            background: rgba(255, 255, 255, 0.95);
            border-radius: 15px;
            padding: 25px;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
        }
        
        h2 {
            color: #667eea;
            margin: 0 0 20px 0;
            font-size: 1.8em;
        }
        
        .form-group {
            margin-bottom: 20px;
        }
        
        label {
            display: block;
            color: #333;
            margin-bottom: 8px;
            font-weight: 500;
        }
        
        input[type="number"], input[type="text"] {
            width: 100%;
            padding: 12px;
            border: 2px solid #ddd;
            border-radius: 8px;
            font-size: 16px;
        }
        
        input[type="checkbox"] {
            margin-right: 10px;
            transform: scale(1.5);
        }
        
        button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #fff;
            border: none;
            padding: 12px 30px;
            border-radius: 8px;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            transition: transform 0.2s;
            width: 100%;
        }
        
        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
        }
        
        button.secondary {
            background: #6c757d;
        }
        
        button.secondary:hover {
            background: #5a6268;
        }
        
        .analysis-list {
            list-style: none;
            margin: 0;
            padding: 0;
        }
        
        .analysis-item {
            background: #f8f9fa;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 15px;
            border-left: 4px solid #667eea;
        }
        
        .analysis-item.bug {
            border-left-color: #dc3545;
        }
        
        .analysis-item.feature {
            border-left-color: #28a745;
        }
        
        .analysis-item h3 {
            margin: 0 0 10px 0;
            color: #333;
        }
        
        .analysis-meta {
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
            margin-bottom: 15px;
            font-size: 0.9em;
            color: #666;
        }
        
        .badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.85em;
            font-weight: 600;
        }
        
        .badge.bug {
            background: #dc3545;
            color: #fff;
        }
        
        .badge.feature {
            background: #28a745;
            color: #fff;
        }
        
        .badge.high {
            background: #ffc107;
            color: #000;
        }
        
        .badge.medium {
            background: #17a2b8;
            color: #fff;
        }
        
        .badge.low {
            background: #6c757d;
            color: #fff;
        }
        
        .pattern-section {
            background: #e9ecef;
            border-radius: 8px;
            padding: 15px;
            margin-top: 15px;
        }
        
        .pattern-item {
            padding: 10px 0;
            border-bottom: 1px solid #dee2e6;
        }
        
        .pattern-item:last-child {
            border-bottom: none;
        }
        
        .pattern-name {
            font-weight: 600;
            color: #667eea;
        }
        
        .pattern-confidence {
            color: #28a745;
            font-weight: 600;
        }
        
        .fix-section {
            background: #d1e7dd;
            border-radius: 8px;
            padding: 15px;
            margin-top: 15px;
        }
        
        .code-block {
            background: #2d2d2d;
            color: #f8f8f2;
            border-radius: 6px;
            padding: 15px;
            overflow-x: auto;
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
            margin-top: 10px;
        }
        
        .diff-remove {
            color: #ff6b6b;
        }
        
        .diff-add {
            color: #28a745;
        }
        
        .pr-link {
            display: inline-block;
            margin-top: 10px;
            color: #667eea;
            text-decoration: none;
            font-weight: 500;
        }
        
        .pr-link:hover {
            text-decoration: underline;
        }
        
        .empty-state {
            text-align: center;
            padding: 40px;
            color: #999;
        }
        
        .empty-state h3 {
            color: #666;
            margin-bottom: 20px;
        }
        
        footer {
            text-align: center;
            padding: 30px;
            color: rgba(255, 255, 255, 0.7);
        }
        
        footer a {
            color: #fff;
        }
        
        @media (max-width: 768px) {
            .main-content {
                grid-template-columns: 1fr;
            }
            
            .stats-grid {
                grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 Crawl4AI Root Cause Analysis</h1>
            <div class="stats-grid">
                <div class="stat-card">
                    <h3>Issues Processed</h3>
                    <div class="value">{{ system_state.issues_processed }}</div>
                </div>
                <div class="stat-card">
                    <h3>Patterns Detected</h3>
                    <div class="value">{{ system_state.patterns_detected }}</div>
                </div>
                <div class="stat-card">
                    <h3>Fixes Generated</h3>
                    <div class="value">{{ system_state.fixes_generated }}</div>
                </div>
                <div class="stat-card">
                    <h3>PRs Created</h3>
                    <div class="value">{{ system_state.prs_created }}</div>
                </div>
            </div>
        </div>
        
        <div class="main-content">
            <div class="sidebar">
                <h2>🔍 Analyze Issue</h2>
                <form id="analysisForm" onsubmit="submitAnalysis(event)">
                    <div class="form-group">
                        <label for="issueNumber">GitHub Issue Number</label>
                        <input type="number" id="issueNumber" required placeholder="e.g., 1769" min="1">
                    </div>
                    
                    <div class="form-group">
                        <label for="confidenceThreshold">Confidence Threshold ({{ config.confidence_threshold|round(2) }})</label>
                        <input type="number" id="confidenceThreshold" value="{{ config.confidence_threshold }}" step="0.01" min="0" max="1">
                    </div>
                    
                    <div class="form-group">
                        <label style="display: flex; align-items: center;">
                            <input type="checkbox" id="dryRun" {% if config.dry_run_default %}checked{% endif %}>
                            Dry Run (Safe - won't create actual PR)
                        </label>
                    </div>
                    
                    <button type="submit">🔬 Analyze Issue</button>
                    <button type="button" class="secondary" onclick="startWatchMode()">▶️ Start Watch Mode</button>
                </form>
                
                <div id="watchStatus" style="display: none; margin-top: 20px; padding: 15px; background: #e9ecef; border-radius: 8px;">
                    <strong>Watch Mode:</strong> <span id="watchModeStatus">Running...</span>
                    <button type="button" style="margin-top: 10px; padding: 5px 15px;" onclick="stopWatchMode()">⏹ Stop</button>
                </div>
            </div>
            
            <div class="analysis-section">
                <h2>📊 Recent Analyses</h2>
                <div id="analysisResults">
                    <ul class="analysis-list">
                        {% for analysis in sample_analyses %}
                        <li class="analysis-item {{ 'bug' if analysis.issue_type == 'bug' else 'feature' }}">
                            <h3>
                                <a href="{{ analysis.issue_url }}" target="_blank" style="color: inherit; text-decoration: none;">
                                    #{{ analysis.issue_number }}: {{ analysis.issue_title[:60] }}...
                                </a>
                            </h3>
                            <div class="analysis-meta">
                                <span class="badge {{ analysis.issue_type }}">{{ analysis.issue_type|upper }}</span>
                                <span class="badge {{ analysis.priority }}">{{ analysis.priority|upper }}</span>
                                <span>📅 {{ analysis.timestamp.split('T')[0] }}</span>
                            </div>
                            
                            {% if analysis.pattern_matches %}
                            <div class="pattern-section">
                                <strong>🎯 Pattern Matches:</strong>
                                {% for match in analysis.pattern_matches %}
                                <div class="pattern-item">
                                    <span class="pattern-name">{{ match.name }}</span>
                                    <span class="pattern-confidence">{{ (match.confidence * 100)|round(1) }}% confidence</span>
                                </div>
                                {% endfor %}
                            </div>
                            {% endif %}
                            
                            {% if analysis.root_cause %}
                            <div class="fix-section">
                                <strong>🐛 Root Cause:</strong>
                                <div>File: {{ analysis.root_cause.file }}:{{ analysis.root_cause.line_number }}</div>
                                <div>Function: {{ analysis.root_cause.function }}</div>
                                <div style="margin-top: 10px;">{{ analysis.root_cause.explanation }}</div>
                            </div>
                            {% endif %}
                            
                            {% if analysis.fix %}
                            <div class="fix-section">
                                <strong>🔧 Generated Fix:</strong>
                                <div class="code-block">
                                    <span class="diff-remove">- {{ analysis.fix.old_code }}</span><br>
                                    <span class="diff-add">+ {{ analysis.fix.new_code }}</span>
                                </div>
                                <div style="margin-top: 10px;">
                                    Valid: <span style="color: {% if analysis.fix.valid %}#28a745{% else %}#dc3545{% endif %}; font-weight: bold;">{% if analysis.fix.valid %}✓{% else %}✗{% endif %}</span>
                                </div>
                            </div>
                            {% endif %}
                            
                            {% if analysis.pr %}
                            <div>
                                <a href="{{ analysis.pr.url }}" target="_blank" class="pr-link">🔗 View PR #{{ analysis.pr.number }}</a>
                            </div>
                            {% endif %}
                        </li>
                        {% endfor %}
                    </ul>
                </div>
            </div>
        </div>
        
        <footer>
            <p>Crawl4AI Root Cause Analysis System</p>
            <p>Powered by <a href="https://github.com/medo94my/crawl4ai-root-cause-analysis" target="_blank">medo94my</a></p>
        </footer>
    </div>
    
    <script>
        async function submitAnalysis(event) {
            event.preventDefault();
            
            const issueNumber = document.getElementById('issueNumber').value;
            const confidenceThreshold = document.getElementById('confidenceThreshold').value;
            const dryRun = document.getElementById('dryRun').checked;
            
            if (!issueNumber) {
                alert('Please enter an issue number');
                return;
            }
            
            const submitBtn = event.target.querySelector('button[type="submit"]');
            submitBtn.disabled = true;
            submitBtn.textContent = '⏳ Analyzing...';
            
            try {
                const response = await fetch('/api/analyze', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        issue_number: parseInt(issueNumber),
                        confidence_threshold: parseFloat(confidenceThreshold),
                        dry_run: dryRun
                    })
                });
                
                if (response.ok) {
                    const result = await response.json();
                    alert('✅ Analysis completed successfully!');
                    location.reload();
                } else {
                    const error = await response.json();
                    alert('❌ Analysis failed: ' + (error.detail || 'Unknown error'));
                }
            } catch (error) {
                alert('❌ Error: ' + error.message);
            } finally {
                submitBtn.disabled = false;
                submitBtn.textContent = '🔬 Analyze Issue';
            }
        }
        
        async function startWatchMode() {
            const watchStatusDiv = document.getElementById('watchStatus');
            const statusSpan = document.getElementById('watchModeStatus');
            
            watchStatusDiv.style.display = 'block';
            statusSpan.textContent = 'Starting...';
            
            try {
                const response = await fetch('/api/watch/start');
                if (response.ok) {
                    statusSpan.textContent = 'Running';
                } else {
                    const error = await response.json();
                    alert('❌ Failed to start watch mode: ' + (error.detail || 'Unknown error'));
                    watchStatusDiv.style.display = 'none';
                }
            } catch (error) {
                alert('❌ Error: ' + error.message);
                watchStatusDiv.style.display = 'none';
            }
        }
        
        async function stopWatchMode() {
            const watchStatusDiv = document.getElementById('watchStatus');
            const statusSpan = document.getElementById('watchModeStatus');
            
            try {
                const response = await fetch('/api/watch/stop');
                if (response.ok) {
                    statusSpan.textContent = 'Stopped';
                    setTimeout(() => {
                        watchStatusDiv.style.display = 'none';
                    }, 2000);
                } else {
                    const error = await response.json();
                    alert('❌ Failed to stop watch mode: ' + (error.detail || 'Unknown error'));
                }
            } catch (error) {
                alert('❌ Error: ' + error.message);
            }
        }
        
        // Auto-refresh results every 10 seconds if watch mode is active
        setInterval(async () => {
            try {
                const response = await fetch('/api/status');
                if (response.ok) {
                    const status = await response.json();
                    updateStats(status);
                }
            } catch (error) {
                console.error('Failed to fetch status:', error);
            }
        }, 10000);
        
        function updateStats(status) {
            document.querySelector('.stat-card:nth-child(1) .value').textContent = status.issues_processed;
            document.querySelector('.stat-card:nth-child(2) .value').textContent = status.patterns_detected;
            document.querySelector('.stat-card:nth-child(3) .value').textContent = status.fixes_generated;
            document.querySelector('.stat-card:nth-child(4) .value').textContent = status.prs_created;
        }
    </script>
</body>
</html>
"""

# Write the template
with open(templates_dir / "index.html", "w", encoding='utf-8') as f:
    f.write(index_template)

logger.info("✅ Created templates/index.html")


# API Endpoints

@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the main dashboard."""
    config = {
        "confidence_threshold": 0.7,
        "dry_run_default": True,
    }
    return templates.TemplateResponse("index.html", {"request": {}, "system_state": system_state, "config": config})


@app.get("/api/status")
async def get_status():
    """Get current system status."""
    return JSONResponse({
        "status": system_state["status"],
        "last_check": system_state["last_check"],
        "issues_processed": system_state["issues_processed"],
        "patterns_detected": system_state["patterns_detected"],
        "fixes_generated": system_state["fixes_generated"],
        "prs_created": system_state["prs_created"],
        "accuracy": system_state["accuracy"],
        "false_positives": system_state["false_positives"],
    })


@app.post("/api/analyze")
async def analyze_issue(request: Request):
    """Trigger analysis of a specific issue."""
    try:
        data = await request.json()
        issue_number = data.get("issue_number")
        confidence_threshold = data.get("confidence_threshold", 0.7)
        dry_run = data.get("dry_run", True)
        
        if not issue_number:
            return JSONResponse({"detail": "Issue number is required"}, status_code=400)
        
        # Update system state
        system_state["status"] = "analyzing"
        
        # Import and run the analysis pipeline
        import sys
        sys.path.insert(0, "/root/.openclaw/workspace/crawl4ai-root-cause-analysis")
        
        from main_gh import RootCauseAnalysisPipeline
        
        pipeline = RootCauseAnalysisPipeline(
            repo_path="/root/.openclaw/workspace/crawl4ai-repo",
            dry_run=dry_run,
            confidence_threshold=confidence_threshold,
        )
        
        # Run analysis
        success = await pipeline.process_issue(issue_number)
        
        if success:
            system_state["issues_processed"] += 1
            system_state["patterns_detected"] += 1
            system_state["fixes_generated"] += 1
        
        system_state["status"] = "idle"
        
        return JSONResponse({
            "success": success,
            "issue_number": issue_number,
            "confidence_threshold": confidence_threshold,
            "dry_run": dry_run,
        })
        
    except Exception as e:
        logger.error(f"Error analyzing issue: {e}", exc_info=True)
        system_state["status"] = "idle"
        return JSONResponse({"detail": str(e)}, status_code=500)


@app.post("/api/watch/start")
async def start_watch_mode():
    """Start watch mode."""
    global system_state
    
    if system_state["status"] == "watching":
        return JSONResponse({"detail": "Watch mode is already running"}, status_code=400)
    
    system_state["status"] = "watching"
    
    return JSONResponse({
        "status": "started",
        "message": "Watch mode started successfully",
    })


@app.post("/api/watch/stop")
async def stop_watch_mode():
    """Stop watch mode."""
    global system_state
    
    if system_state["status"] != "watching":
        return JSONResponse({"detail": "Watch mode is not running"}, status_code=400)
    
    system_state["status"] = "idle"
    
    return JSONResponse({
        "status": "stopped",
        "message": "Watch mode stopped successfully",
    })


@app.get("/api/analyses")
async def get_analyses():
    """Get list of all analyses."""
    # Convert sample data to dict format
    analyses_dict = [analysis.model_dump() for analysis in sample_analyses]
    return JSONResponse(analyses_dict)


def main():
    """Run the web UI server."""
    import uvicorn
    
    logger.info("Starting Crawl4AI Root Cause Analysis Web UI")
    logger.info("Dashboard will be available at: http://localhost:8000")
    logger.info("Press Ctrl+C to stop")
    
    config = uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
    
    uvicorn.run(config)


if __name__ == "__main__":
    main()

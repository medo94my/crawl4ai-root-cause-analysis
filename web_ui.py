"""
Crawl4AI Root Cause Analysis System - Web UI (v2)

Redesigned dashboard with:
- Split-pane layout (live terminal log + structured report viewer)
- URL-based GitHub issue input
- 7-step progress stepper with live status indicators
- Resolution status badge (Already Resolved / Not Resolved / Unclear)
- Tabbed report viewer (verify.md / verify.py)
- Watch mode panel

Usage:
    python3 web_ui.py
    # Open http://localhost:8000
"""

import logging
import asyncio
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Crawl4AI Root Cause Analysis System",
    description="Web UI for automated bug detection and analysis",
    version="2.0.0",
)

templates = Jinja2Templates(directory="templates")

# --- Global State ---

system_state = {
    "status": "idle",
    "last_check": None,
    "issues_processed": 0,
    "patterns_detected": 0,
    "fixes_generated": 0,
    "prs_created": 0,
}

analysis_state = {
    "logs": [],
    "steps": {
        "Fetch": "pending",
        "Parse": "pending",
        "Reproduce": "pending",
        "Resolution": "pending",
        "Root Cause": "pending",
        "Fix": "pending",
        "Report": "pending",
    },
    "is_running": False,
    "result": None,
    "issue_number": None,
}

# --- Models ---

class AnalysisRequest(BaseModel):
    issue_url: str
    confidence_threshold: float = 0.7
    dry_run: bool = True


# --- HTML Template ---

templates_dir = Path("templates")
templates_dir.mkdir(exist_ok=True)

index_template = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Crawl4AI Root Cause Analyzer</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Chakra+Petch:wght@300;400;600;700&family=JetBrains+Mono:wght@300;400;600;700&display=swap" rel="stylesheet">
<style>
:root {
  --bg: #050810;
  --surface: #0b1120;
  --surface2: #101928;
  --surface3: #151f30;
  --border: #1a2d45;
  --border2: #243a55;
  --cyan: #00d4ff;
  --cyan-dim: rgba(0,212,255,0.15);
  --cyan-glow: rgba(0,212,255,0.4);
  --green: #39ff7a;
  --green-dim: rgba(57,255,122,0.12);
  --red: #ff3860;
  --red-dim: rgba(255,56,96,0.12);
  --amber: #ffb830;
  --amber-dim: rgba(255,184,48,0.12);
  --purple: #9d6eff;
  --text: #b8cce0;
  --text-dim: #4a6280;
  --text-bright: #e0ecff;
  --text-code: #7dd3fc;
  --terminal-bg: #020407;
  --terminal-text: #3dff8a;
  --terminal-dim: #1a7a3a;
  --font-ui: 'Chakra Petch', 'Courier New', monospace;
  --font-mono: 'JetBrains Mono', 'Courier New', monospace;
  --radius: 8px;
  --radius-sm: 4px;
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

html, body { height: 100%; overflow: hidden; }

body {
  background: var(--bg);
  color: var(--text);
  font-family: var(--font-mono);
  font-size: 13px;
  line-height: 1.5;
  display: flex;
  flex-direction: column;
}

/* ── Background Grid ── */
body::before {
  content: '';
  position: fixed;
  inset: 0;
  background-image:
    linear-gradient(rgba(0,212,255,0.025) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0,212,255,0.025) 1px, transparent 1px);
  background-size: 48px 48px;
  pointer-events: none;
  z-index: 0;
}

/* ── Header ── */
header {
  position: relative;
  z-index: 10;
  padding: 14px 20px 10px;
  border-bottom: 1px solid var(--border);
  background: rgba(5,8,16,0.92);
  backdrop-filter: blur(8px);
  flex-shrink: 0;
}

.header-top {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 12px;
}

h1 {
  font-family: var(--font-ui);
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-bright);
  white-space: nowrap;
}

h1 span {
  color: var(--cyan);
  text-shadow: 0 0 16px var(--cyan-glow), 0 0 32px rgba(0,212,255,0.2);
}

.input-row {
  display: flex;
  gap: 8px;
  flex: 1;
}

.url-input {
  flex: 1;
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 8px 12px;
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-bright);
  outline: none;
  transition: border-color 0.2s, box-shadow 0.2s;
  min-width: 0;
}

.url-input::placeholder { color: var(--text-dim); }

.url-input:focus {
  border-color: var(--cyan);
  box-shadow: 0 0 0 2px var(--cyan-dim), inset 0 0 8px rgba(0,212,255,0.05);
}

.btn {
  font-family: var(--font-ui);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  border: none;
  border-radius: var(--radius-sm);
  padding: 8px 18px;
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
}

.btn-primary {
  background: var(--cyan);
  color: #000;
}

.btn-primary:hover { background: #00eeff; box-shadow: 0 0 16px var(--cyan-glow); }
.btn-primary:disabled { background: #1a3a45; color: #2a5060; cursor: not-allowed; }

.btn-secondary {
  background: transparent;
  color: var(--cyan);
  border: 1px solid var(--border2);
}

.btn-secondary:hover { border-color: var(--cyan); background: var(--cyan-dim); }

.btn-danger {
  background: transparent;
  color: var(--red);
  border: 1px solid rgba(255,56,96,0.3);
}

.btn-danger:hover { border-color: var(--red); background: var(--red-dim); }

/* ── Stats Row ── */
.stats-row {
  display: flex;
  gap: 20px;
}

.stat {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  color: var(--text-dim);
}

.stat-label { text-transform: uppercase; letter-spacing: 0.06em; }

.stat-value {
  font-family: var(--font-ui);
  font-size: 15px;
  font-weight: 700;
  color: var(--cyan);
  min-width: 24px;
  text-align: right;
}

.stat-sep { color: var(--border2); }

/* ── Main Layout ── */
.main {
  display: flex;
  flex: 1;
  overflow: hidden;
  position: relative;
  z-index: 1;
}

/* ── Left Panel (Terminal) ── */
.panel-left {
  width: 40%;
  min-width: 300px;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--border);
  background: rgba(2,4,7,0.6);
  overflow: hidden;
}

/* Step Stepper */
.stepper {
  padding: 10px 14px 8px;
  border-bottom: 1px solid var(--border);
  background: rgba(11,17,32,0.9);
  flex-shrink: 0;
}

.stepper-label {
  font-family: var(--font-ui);
  font-size: 9px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text-dim);
  margin-bottom: 8px;
}

.steps {
  display: flex;
  align-items: center;
  gap: 0;
}

.step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  flex: 1;
  position: relative;
}

.step:not(:last-child)::after {
  content: '';
  position: absolute;
  top: 5px;
  left: calc(50% + 6px);
  right: calc(-50% + 6px);
  height: 1px;
  background: var(--border);
  transition: background 0.3s;
}

.step.done:not(:last-child)::after { background: var(--green); }

.step-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--border2);
  border: 1px solid var(--border);
  position: relative;
  z-index: 1;
  transition: all 0.3s;
}

.step.done .step-dot { background: var(--green); border-color: var(--green); box-shadow: 0 0 6px rgba(57,255,122,0.6); }
.step.blocked .step-dot { background: var(--red); border-color: var(--red); box-shadow: 0 0 6px rgba(255,56,96,0.6); }
.step.running .step-dot {
  background: var(--cyan);
  border-color: var(--cyan);
  box-shadow: 0 0 8px var(--cyan-glow);
  animation: pulse-dot 0.8s ease-in-out infinite;
}

@keyframes pulse-dot {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.4); opacity: 0.7; }
}

.step-name {
  font-size: 8px;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--text-dim);
  text-align: center;
  white-space: nowrap;
}

.step.done .step-name { color: var(--green); }
.step.blocked .step-name { color: var(--red); }
.step.running .step-name { color: var(--cyan); }

/* Terminal */
.terminal {
  flex: 1;
  overflow-y: auto;
  padding: 12px 14px;
  background: var(--terminal-bg);
  position: relative;
  font-family: var(--font-mono);
  font-size: 11px;
  line-height: 1.7;
}

/* Scanline overlay */
.terminal::before {
  content: '';
  position: absolute;
  inset: 0;
  background: repeating-linear-gradient(
    0deg,
    transparent,
    transparent 2px,
    rgba(0,0,0,0.06) 2px,
    rgba(0,0,0,0.06) 4px
  );
  pointer-events: none;
  z-index: 2;
}

.terminal::-webkit-scrollbar { width: 4px; }
.terminal::-webkit-scrollbar-track { background: transparent; }
.terminal::-webkit-scrollbar-thumb { background: #1a3a20; border-radius: 2px; }

.terminal-empty {
  color: var(--terminal-dim);
  padding: 20px 0;
}

.terminal-empty p { margin-bottom: 4px; }

.log-line {
  color: var(--terminal-text);
  animation: fade-in-up 0.2s ease-out both;
  position: relative;
}

.log-line.error { color: var(--red); }
.log-line.info { color: #4fc3f7; }
.log-line.warn { color: var(--amber); }
.log-line.success { color: var(--green); }

@keyframes fade-in-up {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}

.cursor {
  display: inline-block;
  width: 7px;
  height: 13px;
  background: var(--terminal-text);
  vertical-align: middle;
  animation: blink 0.9s step-end infinite;
  margin-left: 2px;
}

@keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0; } }

/* ── Right Panel (Report) ── */
.panel-right {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--bg);
}

.report-area {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.report-area::-webkit-scrollbar { width: 4px; }
.report-area::-webkit-scrollbar-track { background: transparent; }
.report-area::-webkit-scrollbar-thumb { background: var(--border2); border-radius: 2px; }

/* Placeholder */
.report-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--text-dim);
  text-align: center;
  gap: 12px;
}

.report-placeholder .icon {
  font-size: 40px;
  opacity: 0.3;
}

.report-placeholder p { font-size: 11px; }

/* Resolution Badge */
.resolution-badge {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 10px 20px;
  border-radius: var(--radius);
  font-family: var(--font-ui);
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin-bottom: 16px;
  width: 100%;
  justify-content: center;
  border: 1px solid;
}

.resolution-badge.resolved {
  background: var(--green-dim);
  border-color: rgba(57,255,122,0.3);
  color: var(--green);
  box-shadow: 0 0 20px rgba(57,255,122,0.1), inset 0 0 20px rgba(57,255,122,0.05);
  animation: badge-glow-green 2s ease-in-out infinite;
}

.resolution-badge.unresolved {
  background: var(--red-dim);
  border-color: rgba(255,56,96,0.3);
  color: var(--red);
  box-shadow: 0 0 20px rgba(255,56,96,0.1), inset 0 0 20px rgba(255,56,96,0.05);
  animation: badge-glow-red 2s ease-in-out infinite;
}

.resolution-badge.unclear {
  background: var(--amber-dim);
  border-color: rgba(255,184,48,0.3);
  color: var(--amber);
  box-shadow: 0 0 20px rgba(255,184,48,0.1), inset 0 0 20px rgba(255,184,48,0.05);
}

@keyframes badge-glow-green {
  0%, 100% { box-shadow: 0 0 20px rgba(57,255,122,0.1), inset 0 0 20px rgba(57,255,122,0.05); }
  50% { box-shadow: 0 0 30px rgba(57,255,122,0.25), inset 0 0 30px rgba(57,255,122,0.08); }
}

@keyframes badge-glow-red {
  0%, 100% { box-shadow: 0 0 20px rgba(255,56,96,0.1), inset 0 0 20px rgba(255,56,96,0.05); }
  50% { box-shadow: 0 0 30px rgba(255,56,96,0.25), inset 0 0 30px rgba(255,56,96,0.08); }
}

/* Report Cards */
.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 14px 16px;
  margin-bottom: 12px;
}

.card-title {
  font-family: var(--font-ui);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--cyan);
  margin-bottom: 10px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.card-title::before {
  content: '';
  display: inline-block;
  width: 3px;
  height: 12px;
  background: var(--cyan);
  border-radius: 2px;
}

/* Root cause card */
.rc-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-bottom: 10px;
}

.rc-field { display: flex; flex-direction: column; gap: 2px; }

.rc-label {
  font-size: 9px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-dim);
}

.rc-value {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-bright);
  word-break: break-all;
}

.confidence-bar {
  height: 4px;
  background: var(--border);
  border-radius: 2px;
  overflow: hidden;
  margin-top: 6px;
}

.confidence-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.8s ease;
  background: linear-gradient(90deg, var(--cyan), var(--green));
}

/* Patterns */
.pattern-tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 10px;
  border-radius: 20px;
  font-size: 10px;
  font-family: var(--font-ui);
  font-weight: 600;
  letter-spacing: 0.04em;
  background: rgba(0,212,255,0.1);
  border: 1px solid rgba(0,212,255,0.2);
  color: var(--cyan);
  margin: 2px;
}

.pattern-conf {
  color: var(--text-dim);
  font-weight: 400;
}

/* Diff viewer */
.diff-block {
  background: #010204;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 10px 14px;
  font-family: var(--font-mono);
  font-size: 11px;
  overflow-x: auto;
  white-space: pre;
  line-height: 1.6;
}

.diff-line-remove { color: #ff6b7a; background: rgba(255,56,96,0.06); display: block; }
.diff-line-add { color: #5cffa0; background: rgba(57,255,122,0.06); display: block; }
.diff-line-header { color: #7b9ec9; display: block; }
.diff-line-normal { color: var(--text-dim); display: block; }

/* Tabs */
.tabs {
  display: flex;
  gap: 0;
  border-bottom: 1px solid var(--border);
  margin-bottom: 12px;
}

.tab-btn {
  font-family: var(--font-ui);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  padding: 8px 16px;
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  color: var(--text-dim);
  cursor: pointer;
  transition: all 0.15s;
  margin-bottom: -1px;
}

.tab-btn:hover { color: var(--text); }
.tab-btn.active { color: var(--cyan); border-bottom-color: var(--cyan); }

.tab-content { display: none; }
.tab-content.active { display: block; }

.code-view {
  background: #010204;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 12px 14px;
  font-family: var(--font-mono);
  font-size: 10.5px;
  line-height: 1.65;
  overflow: auto;
  max-height: 380px;
  white-space: pre;
  color: var(--text);
}

.code-view::-webkit-scrollbar { width: 4px; height: 4px; }
.code-view::-webkit-scrollbar-thumb { background: var(--border2); border-radius: 2px; }

/* ── Watch Mode Panel ── */
.watch-panel {
  border-top: 1px solid var(--border);
  background: var(--surface);
  flex-shrink: 0;
}

.watch-toggle {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px;
  background: transparent;
  border: none;
  cursor: pointer;
  color: var(--text-dim);
  font-family: var(--font-ui);
  font-size: 10px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  transition: color 0.15s;
}

.watch-toggle:hover { color: var(--text); }

.watch-arrow {
  transition: transform 0.2s;
  font-size: 8px;
}

.watch-panel.open .watch-arrow { transform: rotate(180deg); }

.watch-body {
  display: none;
  padding: 0 16px 12px;
  gap: 10px;
}

.watch-panel.open .watch-body { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }

.watch-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--text-dim);
}

.watch-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--border2);
}

.watch-dot.active {
  background: var(--green);
  box-shadow: 0 0 6px rgba(57,255,122,0.6);
  animation: pulse-dot 1s ease-in-out infinite;
}

/* ── Utility ── */
.hidden { display: none !important; }
.mt-8 { margin-top: 8px; }
.mt-4 { margin-top: 4px; }

.loading-shimmer {
  background: linear-gradient(90deg, var(--surface2) 25%, var(--surface3) 50%, var(--surface2) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: var(--radius-sm);
  height: 12px;
}

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border2); border-radius: 3px; }

</style>
</head>
<body>

<!-- ── Header ── -->
<header>
  <div class="header-top">
    <h1>Crawl4AI <span>Root Cause</span> Analyzer</h1>
    <div class="input-row">
      <input
        class="url-input"
        id="issueUrl"
        type="text"
        placeholder="https://github.com/unclecode/crawl4ai/issues/1769"
        autocomplete="off"
        spellcheck="false"
      >
      <select id="confSelect" style="
        background: var(--surface2);
        border: 1px solid var(--border);
        border-radius: 4px;
        padding: 8px 10px;
        font-family: var(--font-mono);
        font-size: 11px;
        color: var(--text);
        outline: none;
        cursor: pointer;
      ">
        <option value="0.5">50% conf</option>
        <option value="0.7" selected>70% conf</option>
        <option value="0.8">80% conf</option>
        <option value="0.9">90% conf</option>
      </select>
      <button class="btn btn-primary" id="analyzeBtn" onclick="startAnalysis()">Analyze</button>
    </div>
  </div>
  <div class="stats-row">
    <div class="stat">
      <span class="stat-label">Processed</span>
      <span class="stat-value" id="stat-processed">0</span>
    </div>
    <span class="stat-sep">·</span>
    <div class="stat">
      <span class="stat-label">Patterns</span>
      <span class="stat-value" id="stat-patterns">0</span>
    </div>
    <span class="stat-sep">·</span>
    <div class="stat">
      <span class="stat-label">Fixes</span>
      <span class="stat-value" id="stat-fixes">0</span>
    </div>
    <span class="stat-sep">·</span>
    <div class="stat">
      <span class="stat-label">PRs</span>
      <span class="stat-value" id="stat-prs">0</span>
    </div>
    <span class="stat-sep" style="margin-left:8px">|</span>
    <div class="stat">
      <span class="stat-label">Status</span>
      <span class="stat-value" id="stat-status" style="font-size:11px;color:var(--text-dim)">IDLE</span>
    </div>
  </div>
</header>

<!-- ── Main ── -->
<div class="main">

  <!-- Left: Terminal -->
  <div class="panel-left">
    <!-- Stepper -->
    <div class="stepper">
      <div class="stepper-label">Pipeline Steps</div>
      <div class="steps" id="stepper">
        <div class="step" data-step="Fetch" id="step-Fetch">
          <div class="step-dot"></div>
          <div class="step-name">Fetch</div>
        </div>
        <div class="step" data-step="Parse" id="step-Parse">
          <div class="step-dot"></div>
          <div class="step-name">Parse</div>
        </div>
        <div class="step" data-step="Reproduce" id="step-Reproduce">
          <div class="step-dot"></div>
          <div class="step-name">Repro</div>
        </div>
        <div class="step" data-step="Resolution" id="step-Resolution">
          <div class="step-dot"></div>
          <div class="step-name">Check</div>
        </div>
        <div class="step" data-step="Root Cause" id="step-Root-Cause">
          <div class="step-dot"></div>
          <div class="step-name">Root</div>
        </div>
        <div class="step" data-step="Fix" id="step-Fix">
          <div class="step-dot"></div>
          <div class="step-name">Fix</div>
        </div>
        <div class="step" data-step="Report" id="step-Report">
          <div class="step-dot"></div>
          <div class="step-name">Report</div>
        </div>
      </div>
    </div>

    <!-- Terminal Log -->
    <div class="terminal" id="terminal">
      <div class="terminal-empty" id="terminalEmpty">
        <p>$ crawl4ai-rca --ready</p>
        <p style="color:var(--terminal-dim)">Awaiting issue URL...</p>
        <p style="color:var(--terminal-dim)">Enter a GitHub issue URL above and click Analyze.</p>
      </div>
      <div id="logLines"></div>
      <span class="cursor" id="cursor" style="display:none"></span>
    </div>
  </div>

  <!-- Right: Report -->
  <div class="panel-right">
    <div class="report-area" id="reportArea">

      <!-- Placeholder -->
      <div class="report-placeholder" id="reportPlaceholder">
        <div class="icon">⬡</div>
        <p>No analysis yet.</p>
        <p>Paste a GitHub issue URL and click <strong style="color:var(--cyan)">Analyze</strong>.</p>
      </div>

      <!-- Report content (hidden until analysis) -->
      <div id="reportContent" class="hidden">

        <!-- Resolution Badge -->
        <div id="resolutionBadge" class="resolution-badge unclear">
          <span id="resolutionIcon">◈</span>
          <span id="resolutionText">Pending...</span>
        </div>

        <!-- Issue info -->
        <div class="card" id="issueCard">
          <div class="card-title">Issue</div>
          <div id="issueInfo" style="font-size:12px; color:var(--text-bright)"></div>
        </div>

        <!-- Patterns -->
        <div class="card" id="patternsCard">
          <div class="card-title">Pattern Matches</div>
          <div id="patternsContent"></div>
        </div>

        <!-- Root Cause -->
        <div class="card" id="rootCauseCard">
          <div class="card-title">Root Cause</div>
          <div id="rootCauseContent"></div>
        </div>

        <!-- Fix Diff -->
        <div class="card" id="fixCard">
          <div class="card-title">Suggested Fix</div>
          <div id="fixContent"></div>
        </div>

        <!-- Report Files -->
        <div class="card" id="reportFilesCard">
          <div class="card-title">Report Files</div>
          <div class="tabs">
            <button class="tab-btn active" onclick="switchTab(this,'tab-md')">verify.md</button>
            <button class="tab-btn" onclick="switchTab(this,'tab-py')">verify.py</button>
          </div>
          <div class="tab-content active" id="tab-md">
            <div id="mdContent" class="code-view" style="color:var(--text-dim)">Loading...</div>
          </div>
          <div class="tab-content" id="tab-py">
            <div id="pyContent" class="code-view" style="color:var(--text-dim)">Loading...</div>
          </div>
        </div>

      </div>
    </div>

    <!-- Watch Mode Panel -->
    <div class="watch-panel" id="watchPanel">
      <button class="watch-toggle" onclick="toggleWatch()">
        <span>Watch Mode</span>
        <span class="watch-arrow" id="watchArrow">▲</span>
      </button>
      <div class="watch-body" id="watchBody">
        <div class="watch-indicator">
          <div class="watch-dot" id="watchDot"></div>
          <span id="watchStatus">Stopped</span>
        </div>
        <button class="btn btn-secondary" id="watchStartBtn" onclick="watchStart()" style="font-size:10px;padding:5px 12px">Start</button>
        <button class="btn btn-danger hidden" id="watchStopBtn" onclick="watchStop()" style="font-size:10px;padding:5px 12px">Stop</button>
        <span style="margin-left:auto;font-size:10px;color:var(--text-dim)">Issues found: <strong id="watchCount" style="color:var(--cyan)">0</strong></span>
      </div>
    </div>
  </div>

</div>

<script>
// ── State ──
let pollInterval = null;
let lastLogCount = 0;
let currentIssueNumber = null;
let isWatchOpen = false;

// ── Step Management ──
const STEP_IDS = {
  'Fetch': 'step-Fetch',
  'Parse': 'step-Parse',
  'Reproduce': 'step-Reproduce',
  'Resolution': 'step-Resolution',
  'Root Cause': 'step-Root-Cause',
  'Fix': 'step-Fix',
  'Report': 'step-Report',
};

function resetSteps() {
  Object.values(STEP_IDS).forEach(id => {
    const el = document.getElementById(id);
    if (el) el.className = 'step';
  });
}

function updateSteps(steps) {
  if (!steps) return;
  Object.entries(steps).forEach(([name, status]) => {
    const id = STEP_IDS[name];
    if (!id) return;
    const el = document.getElementById(id);
    if (el) {
      el.className = 'step ' + status;
    }
  });
}

// ── Log Management ──
function addLog(line) {
  const empty = document.getElementById('terminalEmpty');
  if (empty) empty.style.display = 'none';
  document.getElementById('cursor').style.display = 'inline-block';

  const div = document.createElement('div');
  div.className = 'log-line' + classifyLog(line);
  div.textContent = line;
  document.getElementById('logLines').appendChild(div);

  const terminal = document.getElementById('terminal');
  terminal.scrollTop = terminal.scrollHeight;
}

function classifyLog(line) {
  if (/error|failed|✗/i.test(line)) return ' error';
  if (/✓|done|complete|success/i.test(line)) return ' success';
  if (/warn|blocked|unclear/i.test(line)) return ' warn';
  if (/step|fetching|parsing|analyz|generat|check/i.test(line)) return ' info';
  return '';
}

function clearLog() {
  document.getElementById('logLines').innerHTML = '';
  document.getElementById('terminalEmpty').style.display = 'block';
  document.getElementById('cursor').style.display = 'none';
  lastLogCount = 0;
}

// ── Analysis ──
async function startAnalysis() {
  const url = document.getElementById('issueUrl').value.trim();
  if (!url) {
    document.getElementById('issueUrl').focus();
    return;
  }

  const conf = parseFloat(document.getElementById('confSelect').value);
  const btn = document.getElementById('analyzeBtn');
  btn.disabled = true;
  btn.textContent = 'Running...';

  // Reset UI
  clearLog();
  resetSteps();
  hideReport();
  currentIssueNumber = null;

  try {
    const res = await fetch('/api/analyze', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({issue_url: url, confidence_threshold: conf, dry_run: true})
    });

    if (!res.ok) {
      const err = await res.json();
      addLog('[ERROR] ' + (err.detail || 'Failed to start analysis'));
      btn.disabled = false;
      btn.textContent = 'Analyze';
      return;
    }

    const data = await res.json();
    currentIssueNumber = data.issue_number;
    addLog('[' + now() + '] Analysis started for issue #' + currentIssueNumber);

    startPolling();

  } catch (e) {
    addLog('[ERROR] ' + e.message);
    btn.disabled = false;
    btn.textContent = 'Analyze';
  }
}

function startPolling() {
  if (pollInterval) clearInterval(pollInterval);
  pollInterval = setInterval(poll, 1000);
}

function stopPolling() {
  if (pollInterval) {
    clearInterval(pollInterval);
    pollInterval = null;
  }
  document.getElementById('analyzeBtn').disabled = false;
  document.getElementById('analyzeBtn').textContent = 'Analyze';
}

async function poll() {
  try {
    const res = await fetch('/api/status');
    if (!res.ok) return;
    const data = await res.json();

    updateStats(data);
    updateStatusLabel(data.status);

    const analysis = data.analysis;
    if (!analysis) return;

    updateSteps(analysis.steps);

    // Append new log lines
    const logs = analysis.logs || [];
    if (logs.length > lastLogCount) {
      for (let i = lastLogCount; i < logs.length; i++) {
        addLog(logs[i]);
      }
      lastLogCount = logs.length;
    }

    // Done?
    if (!analysis.is_running && lastLogCount > 0) {
      stopPolling();
      if (analysis.result) {
        showReport(analysis.result);
      }
      if (currentIssueNumber) {
        loadReportFiles(currentIssueNumber);
      }
    }

  } catch (e) {
    console.error('Poll error:', e);
  }
}

// ── Report Display ──
function hideReport() {
  document.getElementById('reportPlaceholder').classList.remove('hidden');
  document.getElementById('reportContent').classList.add('hidden');
}

function showReport(result) {
  document.getElementById('reportPlaceholder').classList.add('hidden');
  document.getElementById('reportContent').classList.remove('hidden');

  // Resolution badge
  const badge = document.getElementById('resolutionBadge');
  const icon = document.getElementById('resolutionIcon');
  const text = document.getElementById('resolutionText');

  const resolution = result.resolution || {};
  if (resolution.resolved) {
    badge.className = 'resolution-badge resolved';
    icon.textContent = '✓';
    text.textContent = 'Already Resolved';
  } else if (resolution.evidence && resolution.evidence.toLowerCase().includes('unclear')) {
    badge.className = 'resolution-badge unclear';
    icon.textContent = '◈';
    text.textContent = 'Unclear';
  } else {
    badge.className = 'resolution-badge unresolved';
    icon.textContent = '✗';
    text.textContent = 'Not Resolved';
  }

  // Issue info
  const issueInfo = document.getElementById('issueInfo');
  if (result.issue_title) {
    issueInfo.innerHTML =
      '<a href="' + (result.issue_url || '#') + '" target="_blank" style="color:var(--cyan);text-decoration:none">' +
      '#' + result.issue_number + ': ' + escHtml(result.issue_title) +
      '</a>' +
      (resolution.evidence ? '<p style="margin-top:6px;font-size:10px;color:var(--text-dim)">' + escHtml(resolution.evidence) + '</p>' : '');
  } else {
    issueInfo.textContent = result.error || 'Analysis failed.';
  }

  // Patterns
  const patternsDiv = document.getElementById('patternsContent');
  const patterns = result.patterns || [];
  if (patterns.length > 0) {
    patternsDiv.innerHTML = patterns.map(p =>
      '<span class="pattern-tag">' + escHtml(p.name) +
      ' <span class="pattern-conf">' + Math.round(p.confidence * 100) + '%</span></span>'
    ).join('');
  } else {
    patternsDiv.innerHTML = '<span style="color:var(--text-dim);font-size:11px">No patterns matched</span>';
  }

  // Root cause
  const rcDiv = document.getElementById('rootCauseContent');
  const rc = result.root_cause;
  if (rc) {
    const conf = Math.round(rc.confidence * 100);
    rcDiv.innerHTML =
      '<div class="rc-grid">' +
      '<div class="rc-field"><div class="rc-label">File</div><div class="rc-value">' + escHtml(rc.file || '—') + ':' + (rc.line_number || '?') + '</div></div>' +
      '<div class="rc-field"><div class="rc-label">Function</div><div class="rc-value">' + escHtml(rc.function || '—') + '</div></div>' +
      '</div>' +
      '<div class="rc-label">Confidence</div>' +
      '<div class="confidence-bar mt-4"><div class="confidence-fill" style="width:' + conf + '%"></div></div>' +
      '<div style="font-size:10px;color:var(--cyan);margin-top:2px;text-align:right">' + conf + '%</div>' +
      (rc.code_snippet ? '<div class="diff-block mt-8">' + escHtml(rc.code_snippet) + '</div>' : '');
  } else {
    rcDiv.innerHTML = '<span style="color:var(--text-dim);font-size:11px">Root cause not determined</span>';
  }

  // Fix diff
  const fixDiv = document.getElementById('fixContent');
  const fix = result.fix;
  if (fix && fix.patch) {
    fixDiv.innerHTML = '<div class="diff-block">' + renderDiff(fix.patch) + '</div>';
  } else if (rc && rc.suggested_fix) {
    fixDiv.innerHTML =
      '<div style="font-size:10px;color:var(--text-dim);margin-bottom:6px">Suggested fix:</div>' +
      '<div class="diff-block"><span class="diff-line-add">+ ' + escHtml(rc.suggested_fix) + '</span></div>';
  } else {
    fixDiv.innerHTML = '<span style="color:var(--text-dim);font-size:11px">No fix template available for this pattern</span>';
  }
}

function renderDiff(patch) {
  return patch.split('\n').map(line => {
    const safe = escHtml(line);
    if (line.startsWith('---') || line.startsWith('+++')) return '<span class="diff-line-header">' + safe + '</span>';
    if (line.startsWith('@@')) return '<span class="diff-line-header">' + safe + '</span>';
    if (line.startsWith('-')) return '<span class="diff-line-remove">' + safe + '</span>';
    if (line.startsWith('+')) return '<span class="diff-line-add">' + safe + '</span>';
    return '<span class="diff-line-normal">' + safe + '</span>';
  }).join('\n');
}

async function loadReportFiles(issueNum) {
  try {
    const res = await fetch('/api/report/' + issueNum);
    if (!res.ok) {
      document.getElementById('mdContent').textContent = '(Report file not yet available)';
      document.getElementById('pyContent').textContent = '(Report file not yet available)';
      return;
    }
    const data = await res.json();
    document.getElementById('mdContent').textContent = data.verify_md || '(empty)';
    document.getElementById('pyContent').textContent = data.verify_py || '(empty)';
  } catch (e) {
    document.getElementById('mdContent').textContent = 'Error loading report: ' + e.message;
  }
}

// ── Tabs ──
function switchTab(btn, tabId) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById(tabId).classList.add('active');
}

// ── Watch Mode ──
function toggleWatch() {
  isWatchOpen = !isWatchOpen;
  const panel = document.getElementById('watchPanel');
  const arrow = document.getElementById('watchArrow');
  if (isWatchOpen) {
    panel.classList.add('open');
    arrow.textContent = '▼';
  } else {
    panel.classList.remove('open');
    arrow.textContent = '▲';
  }
}

async function watchStart() {
  try {
    const res = await fetch('/api/watch/start', {method: 'POST'});
    if (res.ok) {
      document.getElementById('watchStatus').textContent = 'Running';
      document.getElementById('watchDot').classList.add('active');
      document.getElementById('watchStartBtn').classList.add('hidden');
      document.getElementById('watchStopBtn').classList.remove('hidden');
    }
  } catch (e) { console.error(e); }
}

async function watchStop() {
  try {
    const res = await fetch('/api/watch/stop', {method: 'POST'});
    if (res.ok) {
      document.getElementById('watchStatus').textContent = 'Stopped';
      document.getElementById('watchDot').classList.remove('active');
      document.getElementById('watchStartBtn').classList.remove('hidden');
      document.getElementById('watchStopBtn').classList.add('hidden');
    }
  } catch (e) { console.error(e); }
}

// ── Stats ──
function updateStats(data) {
  setVal('stat-processed', data.issues_processed || 0);
  setVal('stat-patterns', data.patterns_detected || 0);
  setVal('stat-fixes', data.fixes_generated || 0);
  setVal('stat-prs', data.prs_created || 0);
}

function updateStatusLabel(status) {
  const el = document.getElementById('stat-status');
  if (!el) return;
  el.textContent = (status || 'idle').toUpperCase();
  el.style.color = status === 'analyzing' ? 'var(--cyan)' : status === 'watching' ? 'var(--green)' : 'var(--text-dim)';
}

function setVal(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

// ── Utilities ──
function escHtml(s) {
  if (!s) return '';
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function now() {
  return new Date().toTimeString().slice(0, 8);
}

// ── Auto-refresh stats ──
setInterval(async () => {
  try {
    const res = await fetch('/api/status');
    if (res.ok) {
      const d = await res.json();
      updateStats(d);
      updateStatusLabel(d.status);
      if (d.status === 'watching') {
        setVal('watchCount', d.issues_processed || 0);
      }
    }
  } catch (e) {}
}, 5000);

// ── Enter key on URL input ──
document.getElementById('issueUrl').addEventListener('keydown', e => {
  if (e.key === 'Enter') startAnalysis();
});
</script>
</body>
</html>"""

with open(templates_dir / "index.html", "w", encoding="utf-8") as f:
    f.write(index_template)

logger.info("Created templates/index.html")


# --- API Endpoints ---

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/status")
async def get_status():
    return JSONResponse({
        **system_state,
        "analysis": {
            "is_running": analysis_state["is_running"],
            "steps": analysis_state["steps"],
            "logs": analysis_state["logs"],
            "issue_number": analysis_state["issue_number"],
            "result": analysis_state["result"],
        }
    })


@app.post("/api/analyze")
async def analyze_issue(req: AnalysisRequest, background_tasks: BackgroundTasks):
    if analysis_state["is_running"]:
        return JSONResponse({"detail": "Analysis already running"}, status_code=400)

    from gh_wrapper import GitHubCLI
    try:
        issue_number = GitHubCLI.parse_issue_url(req.issue_url)
    except ValueError as e:
        return JSONResponse({"detail": str(e)}, status_code=400)

    # Reset state
    analysis_state["logs"] = []
    analysis_state["steps"] = {k: "pending" for k in analysis_state["steps"]}
    analysis_state["is_running"] = True
    analysis_state["result"] = None
    analysis_state["issue_number"] = issue_number
    system_state["status"] = "analyzing"

    background_tasks.add_task(_run_analysis, issue_number, req)

    return JSONResponse({"status": "started", "issue_number": issue_number})


async def _run_analysis(issue_number: int, req: AnalysisRequest):
    """Background analysis task — updates analysis_state step by step."""

    def log(msg: str, step: str = None, status: str = None):
        ts = datetime.now().strftime("%H:%M:%S")
        analysis_state["logs"].append(f"[{ts}] {msg}")
        if step and step in analysis_state["steps"]:
            analysis_state["steps"][step] = status or "running"

    def mark(step: str, status: str):
        if step in analysis_state["steps"]:
            analysis_state["steps"][step] = status

    try:
        from gh_wrapper import GitHubCLI
        from issue_watcher import GitHubIssue
        from issue_ingestion import IssueIngestionEngine
        from pattern_recognition import PatternRecognitionEngine
        from root_cause_analyzer import RootCauseAnalyzer
        from fix_generator import FixGenerator
        from main_gh import RootCauseAnalysisPipeline

        repo_path = str(Path.home() / "crawl4ai-repo")

        # Step 1: Fetch
        log(f"Fetching issue #{issue_number} from GitHub...", "Fetch", "running")
        gh = GitHubCLI(owner="unclecode", repo="crawl4ai")
        issue_data = gh.get_issue(issue_number)

        if not issue_data:
            log(f"Failed to fetch issue #{issue_number}", "Fetch", "blocked")
            mark("Fetch", "blocked")
            analysis_state["result"] = {"success": False, "error": "Failed to fetch issue"}
            return

        log(f"✓ Fetched: {issue_data['title'][:70]}", "Fetch", "done")

        github_issue = GitHubIssue(
            id=issue_data.get("id", 0),
            number=issue_data["number"],
            title=issue_data["title"],
            body=issue_data.get("body") or "",
            state=issue_data["state"],
            author=issue_data["author"],
            labels=issue_data["labels"],
            created_at=issue_data["created_at"],
            updated_at=issue_data["updated_at"],
            html_url=issue_data["html_url"],
            comments_url=issue_data["comments_url"],
            comments=issue_data.get("comments", []),
        )

        # Step 2: Parse
        log("Parsing issue content and comments...", "Parse", "running")
        engine = IssueIngestionEngine()
        parsed = engine.parse_issue(github_issue)
        log(
            f"✓ type={parsed.issue_type} priority={parsed.priority} keywords={parsed.keywords}",
            "Parse", "done"
        )

        # Step 3: Pattern matching / Reproduce
        log("Matching patterns...", "Reproduce", "running")
        pattern_engine = PatternRecognitionEngine()
        patterns = pattern_engine.match_pattern(parsed)

        if not patterns:
            log("No patterns matched — manual review required", "Reproduce", "blocked")
            mark("Resolution", "blocked")
            mark("Root Cause", "blocked")
            mark("Fix", "blocked")
        else:
            best = patterns[0]
            log(f"✓ Pattern: {best.name} ({best.confidence:.0%} confidence)", "Reproduce", "done")
            system_state["patterns_detected"] += 1

        # Step 4: Resolution check + Root cause
        analyzer = RootCauseAnalyzer(repo_path)
        root_cause = None
        resolution = {"resolved": False, "evidence": "No pattern matched"}
        fix = None

        if patterns:
            log("Analyzing root cause in codebase...", "Root Cause", "running")
            root_cause = analyzer.analyze(parsed, patterns[0])

            if root_cause:
                log(f"✓ Root cause: {root_cause.file}:{root_cause.line_number} in {root_cause.function or '?'}", "Root Cause", "done")

                log("Checking if already resolved...", "Resolution", "running")
                resolution = analyzer.check_resolution(root_cause)
                resolved_str = "Already Resolved" if resolution["resolved"] else "Not Resolved"
                log(f"✓ Resolution: {resolved_str} — {resolution['evidence']}", "Resolution", "done")
            else:
                log("Root cause not found (codebase may not be cloned at ~/crawl4ai-repo)", "Root Cause", "blocked")
                mark("Resolution", "blocked")
                resolution = {"resolved": False, "evidence": "Root cause analysis inconclusive — clone crawl4ai to ~/crawl4ai-repo"}

            # Step 5: Fix
            if root_cause:
                log("Generating fix...", "Fix", "running")
                gen = FixGenerator()
                fix = gen.generate_fix(root_cause)
                if fix:
                    log(f"✓ Fix generated for {fix.file}:{fix.line_number}", "Fix", "done")
                    system_state["fixes_generated"] += 1
                else:
                    log("No fix template for this pattern", "Fix", "blocked")
            else:
                mark("Fix", "blocked")

        # Step 6: Write report
        log("Writing report files...", "Report", "running")
        pipeline = RootCauseAnalysisPipeline(repo_path=repo_path if Path(repo_path).exists() else None, dry_run=req.dry_run)
        pipeline._write_report(
            issue_number, github_issue, parsed, patterns, root_cause, fix,
            resolution,
            reproduction_status="reproduced" if root_cause else "blocked",
        )
        log(f"✓ Report written: test_scripts/issues/{issue_number}/verify.md", "Report", "done")

        system_state["issues_processed"] += 1

        analysis_state["result"] = {
            "success": True,
            "issue_number": issue_number,
            "issue_title": github_issue.title,
            "issue_url": github_issue.html_url,
            "resolution": resolution,
            "patterns": [{"name": p.name, "confidence": p.confidence} for p in patterns],
            "root_cause": {
                "file": root_cause.file,
                "line_number": root_cause.line_number,
                "function": root_cause.function,
                "confidence": root_cause.confidence,
                "code_snippet": root_cause.code_snippet,
                "suggested_fix": root_cause.suggested_fix,
            } if root_cause else None,
            "fix": {
                "file": fix.file,
                "line_number": fix.line_number,
                "old_code": fix.old_code,
                "new_code": fix.new_code,
                "patch": fix.patch,
                "pattern_name": fix.pattern_name,
            } if fix else None,
        }

    except Exception as e:
        logger.error(f"Analysis error: {e}", exc_info=True)
        log(f"ERROR: {e}")
        analysis_state["result"] = {"success": False, "error": str(e)}

    finally:
        analysis_state["is_running"] = False
        system_state["status"] = "idle"


@app.get("/api/report/{issue_number}")
async def get_report(issue_number: int):
    report_dir = Path("test_scripts") / "issues" / str(issue_number)
    md_path = report_dir / "verify.md"
    py_path = report_dir / "verify.py"

    if not md_path.exists() and not py_path.exists():
        return JSONResponse(
            {"detail": f"No report found for issue #{issue_number}"},
            status_code=404
        )

    return JSONResponse({
        "issue_number": issue_number,
        "verify_md": md_path.read_text(encoding="utf-8") if md_path.exists() else None,
        "verify_py": py_path.read_text(encoding="utf-8") if py_path.exists() else None,
    })


@app.get("/api/analyses")
async def get_analyses():
    reports_dir = Path("test_scripts") / "issues"
    analyses = []
    if reports_dir.exists():
        for issue_dir in sorted(reports_dir.iterdir()):
            if issue_dir.is_dir() and issue_dir.name.isdigit():
                analyses.append({"issue_number": int(issue_dir.name)})
    return JSONResponse(analyses)


@app.post("/api/watch/start")
async def start_watch():
    if system_state["status"] == "watching":
        return JSONResponse({"detail": "Watch mode already running"}, status_code=400)
    system_state["status"] = "watching"
    return JSONResponse({"status": "started", "message": "Watch mode started"})


@app.post("/api/watch/stop")
async def stop_watch():
    if system_state["status"] != "watching":
        return JSONResponse({"detail": "Watch mode not running"}, status_code=400)
    system_state["status"] = "idle"
    return JSONResponse({"status": "stopped", "message": "Watch mode stopped"})


def main():
    import uvicorn
    logger.info("Starting Crawl4AI Root Cause Analysis Web UI v2")
    logger.info("Dashboard: http://localhost:8000")
    uvicorn.run(app=app, host="0.0.0.0", port=8000, log_level="info")


if __name__ == "__main__":
    main()

#!/bin/bash
# Startup script for Crawl4AI Root Cause Analysis System
# Uses Python virtual environment for isolated dependencies

set -e

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Activate virtual environment
echo "📦 Activating virtual environment..."
source "$SCRIPT_DIR/venv/bin/activate"

# Check if we want to start web UI or CLI mode
if [ "$1" = "--web" ] || [ "$1" = "-w" ]; then
    echo "🎨 Starting Web UI..."
    echo "Dashboard will be available at: http://localhost:8000"
    echo ""
    echo "Press Ctrl+C to stop"
    echo ""

    # Start web UI
    cd "$SCRIPT_DIR"
    python web_ui.py

elif [ "$1" = "--watch" ] || [ "$1" = "-w" ]; then
    echo "👀 Starting Watch Mode (CLI)..."
    echo ""

    # Start watch mode
    cd "$SCRIPT_DIR"
    python main_gh.py --watch --dry-run

elif [ "$1" = "--issue" ]; then
    if [ -z "$2" ]; then
        echo "Usage: $0 --issue <issue_number>"
        exit 1
    fi

    echo "🔍 Analyzing issue #$2..."
    cd "$SCRIPT_DIR"
    python main_gh.py --issue "$2" --dry-run

else
    echo "Crawl4AI Root Cause Analysis System"
    echo ""
    echo "Usage:"
    echo "  $0 --web          Start web UI"
    echo "  $0 --watch         Start watch mode (CLI)"
    echo "  $0 --issue <num>   Analyze specific issue"
    echo ""
    echo "Examples:"
    echo "  $0 --web"
    echo "  $0 --watch"
    echo "  $0 --issue 1769"
    echo ""
    echo "Or use CLI directly:"
    echo "  python main_gh.py --help"

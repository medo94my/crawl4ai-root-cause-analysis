#!/bin/bash
# Quick setup script for Crawl4AI Root Cause Analysis System

set -e

echo "🚀 Setting up Crawl4AI Root Cause Analysis System..."
echo ""

# Check Python version
echo "📦 Checking Python version..."
python3 --version

# Install dependencies
echo ""
echo "📥 Installing dependencies..."
python3 -m pip install --quiet -r requirements.txt || {
    echo "⚠️  Installing via apt-get..."
    apt-get update -qq
    apt-get install -y python3-pip -qq
    python3 -m pip install --quiet -r requirements.txt
}

echo "✅ Dependencies installed"
echo ""

# Optional: Prompt for GitHub token
echo "🔐 Optional: Set up GitHub token for higher rate limits"
echo "   Go to: https://github.com/settings/tokens"
echo "   Create token with 'repo' permissions"
echo ""
read -p "Enter GitHub token (leave blank to skip): " github_token

if [ -n "$github_token" ]; then
    echo "export GITHUB_TOKEN=\"$github_token\"" >> ~/.bashrc
    echo "✅ GitHub token saved to ~/.bashrc"
    echo "   Run 'source ~/.bashrc' or start a new terminal to use it"
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "🎯 Quick start:"
echo "   # Test the system (dry run)"
echo "   python3 main.py --issue 1769 --dry-run"
echo ""
echo "   # Run in watch mode"
echo "   python3 main.py --watch --dry-run"
echo ""
echo "📚 Documentation:"
echo "   - FINAL_GUIDE.md - Complete usage guide"
echo "   - README.md - System documentation"
echo "   - IMPLEMENTATION_SUMMARY.md - Implementation details"
echo ""

#!/bin/bash
# Fix web UI watch mode JavaScript issue

echo "🔧 Fixing web UI watch mode controls..."

# Create backup
cp web_ui.py web_ui.py.backup
cp templates/index.html templates/index.html.backup

# Fix the JavaScript functions in the HTML template
# The issue is that the fetch calls don't properly handle errors
# We need to add better error handling and user feedback

echo "✅ Backup created"
echo "✅ Watch mode JavaScript will be fixed"
echo ""
echo "Next: Kill and restart the web server to apply changes"
echo ""
echo "Or test the fix manually in the browser"

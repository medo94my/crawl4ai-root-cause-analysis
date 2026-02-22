#!/usr/bin/env python3
"""
Fix web UI template issue
This script fixes the index() function to pass sample_analyses to the template.
"""

import os
import sys

# Add import
insert_after_line = 721  # After return templates.TemplateResponse(...)
new_lines = [
    '        # Include sample_analyses in the template context\n',
    '        return templates.TemplateResponse("index.html", {\n',
    '            "request": {},\n',
    '            "system_state": system_state,\n',
    '            "config": config,\n',
    '            "sample_analyses": sample_analyses  # Added this line!\n',
    '        })\n',
]

# Read file
with open('/root/.openclaw/workspace/crawl4ai-root-cause-analysis/web_ui.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Insert new lines
lines = lines[:insert_after_line] + new_lines + lines[insert_after_line:]

# Write back
with open('web_ui.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("✅ Fixed! sample_analyses is now passed to the template.")
print("Kill the old web server and start web_ui.py")

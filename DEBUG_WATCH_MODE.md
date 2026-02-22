## 🔧 Fix Watch Mode JavaScript Error

### Problem
The "start watch mode is not a method" error indicates a JavaScript runtime issue.

### Root Cause
The JavaScript functions `startWatchMode()` and `stopWatchMode()` are defined, but the error suggests they're not being found or called correctly when the button is clicked.

### Possible Causes
1. **Script loading order** - Functions defined before they're called
2. **Scope issues** - Functions not in global scope
3. **Syntax errors** - Preventing functions from being parsed
4. **Template rendering** - Jinja2 syntax interfering with JavaScript

### Current Status
✅ Functions ARE defined in template
✅ Template is being rendered by FastAPI
✅ No Jinja2 syntax showing in rendered HTML
✅ Button onclick attributes are correct

### What to Try

1. **Open Browser DevTools:**
   - Press F12
   - Go to Console tab
   - Click "Start Watch Mode" button
   - Look for red error messages

2. **Check JavaScript Errors:**
   - See exact error message
   - Check line number
   - See if it's a syntax or runtime error

3. **Test in Different Browser:**
   - Try Chrome
   - Try Firefox
   - See if error persists

4. **Check Page Source:**
   - Right-click → View Page Source
   - Ctrl+F for "startWatchMode"
   - Verify function is defined

### Temporary Workaround

If watch mode doesn't work via UI, use CLI instead:

```bash
cd /root/.openclaw/workspace/crawl4ai-root-cause-analysis
venv/bin/python main_gh.py --watch --dry-run
```

### Need More Help?

To debug properly, I need to see:
1. The exact error message from browser console
2. The line number where error occurs
3. The full JavaScript code from rendered page

Can you open http://localhost:8000, press F12 for DevTools, click "Start Watch Mode", and tell me what error appears in the console?

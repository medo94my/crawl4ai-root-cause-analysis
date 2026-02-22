# Virtual Environment Setup Guide

## ✅ Virtual Environment Created!

The system now runs in an isolated Python virtual environment (venv) to avoid dependency conflicts.

---

## 📁 What Was Created

```
venv/                          # Python virtual environment
run_venv.sh                  # Startup script (executable)
VENV_README.md               # This file
```

---

## 🚀 Quick Start

### Option 1: Use the Startup Script (Easiest!)

```bash
cd /root/.openclaw/workspace/crawl4ai-root-cause-analysis

# Start web UI
./run_venv.sh --web

# Start watch mode
./run_venv.sh --watch

# Analyze specific issue
./run_venv.sh --issue 1769
```

### Option 2: Manual Activation

```bash
# Activate venv
source venv/bin/activate

# Then run commands normally
python main_gh.py --issue 1769 --dry-run

# Or start web UI
python web_ui.py

# Deactivate when done
deactivate
```

### Option 3: One-Liners

```bash
# Start web UI (one line)
venv/bin/python web_ui.py

# Analyze issue (one line)
venv/bin/python main_gh.py --issue 1769 --dry-run

# Start watch mode (one line)
venv/bin/python main_gh.py --watch --dry-run
```

---

## 📦 What's Installed in venv

### Core Dependencies:
- ✅ httpx >= 0.24.0
- ✅ click >= 8.0.0
- ✅ pydantic >= 2.0.0

### Web UI Dependencies:
- ✅ fastapi >= 0.104.0
- ✅ uvicorn[standard] >= 0.24.0
- ✅ jinja2 >= 3.1.2
- ✅ python-multipart >= 0.0.6

### System-Wide:
- ✅ gh (GitHub CLI) - Already installed on system

---

## 🎯 Usage Examples

### 1. Start Web UI

**Using startup script:**
```bash
./run_venv.sh --web
```

**Manual:**
```bash
source venv/bin/activate
python web_ui.py
```

**Then open:** http://localhost:8000

### 2. Analyze Issue #1769

**Using startup script:**
```bash
./run_venv.sh --issue 1769
```

**Manual:**
```bash
source venv/bin/activate
python main_gh.py --issue 1769 --dry-run
```

### 3. Start Watch Mode

**Using startup script:**
```bash
./run_venv.sh --watch
```

**Manual:**
```bash
source venv/bin/activate
python main_gh.py --watch --dry-run
```

### 4. Create Actual PR (no dry run)

```bash
source venv/bin/activate
python main_gh.py --issue 1769 --no-dry-run
```

---

## 🔧 Troubleshooting

### Issue: "venv/bin/python: not found"

**Solution:**
```bash
# Recreate venv
rm -rf venv
python3.10 -m venv venv
```

### Issue: "No module named 'fastapi'"

**Solution:**
```bash
# Reinstall web dependencies
venv/bin/pip install -r requirements_web.txt
```

### Issue: "ModuleNotFoundError: No module named 'httpx'"

**Solution:**
```bash
# Reinstall core dependencies
venv/bin/pip install -r requirements.txt
```

### Issue: "GitHub CLI not working"

**Solution:**
```bash
# gh is installed system-wide, no need for venv
gh --version
```

---

## 📋 Startup Script Reference

```bash
./run_venv.sh --web       # Start web UI (FastAPI dashboard)
./run_venv.sh --watch      # Start watch mode (CLI)
./run_venv.sh --issue <num> # Analyze specific issue
./run_venv.sh              # Show help
```

---

## 🎨 What's Different with venv?

### Before:
- Dependencies installed system-wide
- Potential conflicts with other projects
- Hard to manage versions

### After:
- ✅ Isolated environment
- ✅ Predictable dependency versions
- ✅ No conflicts with other Python projects
- ✅ Easy to recreate or upgrade
- ✅ Consistent environment across sessions

---

## 🔄 Updating Dependencies

### Update All Dependencies

```bash
source venv/bin/activate
pip install --upgrade -r requirements.txt
pip install --upgrade -r requirements_web.txt
```

### Update Specific Package

```bash
source venv/bin/activate
pip install --upgrade fastapi
```

---

## 🧪 Testing Installation

```bash
# Test core dependencies
venv/bin/python -c "import httpx, click, pydantic; print('✅ Core OK')"

# Test web UI dependencies
venv/bin/python -c "import fastapi, uvicorn, jinja2; print('✅ Web UI OK')"

# Test GitHub CLI
gh --version
```

---

## 📁 Virtual Environment Structure

```
venv/
├── bin/
│   ├── python          # Python interpreter
│   ├── pip            # Package installer
│   └── activate        # Activation script
├── lib/
│   └── python3.10/
│       └── site-packages/
│           ├── fastapi/
│           ├── httpx/
│           ├── click/
│           ├── pydantic/
│           └── [all other packages]
└── pyvenv.cfg
```

---

## 🎯 Best Practices

### 1. Always Activate venv First

```bash
source venv/bin/activate
# Then run all commands
```

### 2. Use One-Liners When Possible

```bash
# Better than activating manually
venv/bin/python web_ui.py
```

### 3. Use Startup Script for Common Tasks

```bash
# Easy to remember
./run_venv.sh --web
./run_venv.sh --watch
```

### 4. Deactivate When Done

```bash
# Good practice to deactivate when finished
deactivate
```

---

## ✅ Summary

**Status:** 🎉 VENV SETUP COMPLETE

**Available:**
- ✅ Isolated Python virtual environment
- ✅ All dependencies installed
- ✅ Web UI dependencies installed
- ✅ Easy startup script
- ✅ No dependency conflicts

**Quick Start:**
```bash
./run_venv.sh --web
# Or
source venv/bin/activate
python web_ui.py
```

---

## 📞 Support

If you encounter issues:

1. Check this guide's troubleshooting section
2. Verify venv is activated (`which python` should show venv path)
3. Reinstall dependencies if needed
4. Check Python version (`python --version` should be 3.10+)

---

**🎉 You're ready to use the system with a clean virtual environment!**

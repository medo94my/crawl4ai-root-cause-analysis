# Hetzner VPS Setup Guide

Complete end-to-end instructions for deploying the Crawl4AI Root Cause Analysis System
on a Hetzner Cloud VPS, from a fresh server to a running web dashboard.

---

## Table of Contents

1. [Recommended VPS Specs](#1-recommended-vps-specs)
2. [Initial Server Setup](#2-initial-server-setup)
3. [Install System Dependencies](#3-install-system-dependencies)
4. [Install GitHub CLI (gh)](#4-install-github-cli-gh)
5. [Clone the Repository](#5-clone-the-repository)
6. [Python Virtual Environment & Dependencies](#6-python-virtual-environment--dependencies)
7. [GitHub Authentication](#7-github-authentication)
8. [Clone the Crawl4AI Repo (for Static Analysis)](#8-clone-the-crawl4ai-repo-for-static-analysis)
9. [Run the App — Quick Test](#9-run-the-app--quick-test)
10. [Run the Web UI](#10-run-the-web-ui)
11. [Persist with systemd](#11-persist-with-systemd)
12. [Nginx Reverse Proxy (Optional)](#12-nginx-reverse-proxy-optional)
13. [Firewall Rules](#13-firewall-rules)
14. [Run Tests](#14-run-tests)
15. [Troubleshooting](#15-troubleshooting)

---

## 1. Recommended VPS Specs

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| Type     | CX21    | CX31        |
| vCPU     | 2       | 2           |
| RAM      | 4 GB    | 8 GB        |
| Disk     | 40 GB   | 80 GB       |
| OS       | Ubuntu 22.04 LTS | Ubuntu 22.04 LTS |
| Location | Any     | Closest to you |

The Crawl4AI repo clone (`~/crawl4ai-repo`) is ~200 MB. Reports are written to disk under
`test_scripts/issues/`. 8 GB RAM is comfortable; 4 GB is workable.

Create the server in the [Hetzner Cloud Console](https://console.hetzner.cloud/):

1. **New Project** → **Add Server**
2. Choose **Ubuntu 22.04** image
3. Add your SSH public key (paste from `~/.ssh/id_ed25519.pub` on your local machine)
4. Click **Create & Buy Now**

---

## 2. Initial Server Setup

```bash
# SSH into the server (replace IP with your server's IP)
ssh root@<YOUR_SERVER_IP>

# Update packages
apt-get update && apt-get upgrade -y

# Create a non-root user (optional but recommended)
adduser deploy
usermod -aG sudo deploy

# Copy SSH key to new user
rsync --archive --chown=deploy:deploy ~/.ssh /home/deploy/

# Switch to non-root user for the rest
su - deploy
```

> **Note:** The rest of this guide runs as the `deploy` user. If you prefer to stay as
> `root`, all commands still work — just skip the `su` step.

---

## 3. Install System Dependencies

```bash
# Install Python 3.11+, git, curl, and build tools
sudo apt-get install -y \
    python3.11 \
    python3.11-venv \
    python3-pip \
    git \
    curl \
    wget \
    unzip \
    build-essential

# Verify Python version (must be 3.8+; 3.11 recommended)
python3 --version
```

---

## 4. Install GitHub CLI (gh)

The `gh` CLI is the core mechanism used to fetch GitHub issues, comments, and optionally
create PRs. It must be installed and authenticated before the pipeline can run.

```bash
# Add the GitHub CLI apt repository
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
    | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] \
    https://cli.github.com/packages stable main" \
    | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null

sudo apt-get update
sudo apt-get install -y gh

# Verify
gh --version
```

Expected output: `gh version 2.x.x (...)`.

---

## 5. Clone the Repository

```bash
# Clone the analysis tool
git clone https://github.com/medo94my/crawl4ai-root-cause-analysis.git ~/rca

# Enter the project directory — all commands below run from here
cd ~/rca

# Check out the main branch (or the feature branch if still in review)
git checkout master
# Or: git checkout feature/pipeline-fixes-webui-redesign
```

---

## 6. Python Virtual Environment & Dependencies

```bash
cd ~/rca

# Create a virtual environment
python3.11 -m venv .venv

# Activate it
source .venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install core dependencies
pip install -r requirements.txt

# Install web UI dependencies (FastAPI, uvicorn, jinja2)
pip install -r requirements_web.txt

# Verify
python3 -c "import fastapi, uvicorn, jinja2; print('OK')"
```

The venv must be **activated** (`source .venv/bin/activate`) in every shell session
before running any `python3` or `pytest` command.

---

## 7. GitHub Authentication

The pipeline calls `gh` under the hood. You must authenticate once.

### Option A — Interactive browser login (easiest)

```bash
gh auth login
# Choose: GitHub.com → HTTPS → Login with a web browser
# Copy the one-time code shown, open the URL, paste the code
```

### Option B — Personal Access Token (headless server)

If the server has no browser access:

1. On your local machine, go to
   [https://github.com/settings/tokens/new](https://github.com/settings/tokens/new)
2. Create a **Fine-grained token** or **Classic token** with `repo` scope (read-only
   access is enough for analysis; `repo` write is only needed for PR creation)
3. Copy the token

```bash
# On the server
gh auth login --with-token <<< "ghp_YOUR_TOKEN_HERE"
```

### Verify authentication

```bash
gh auth status
# Expected: ✓ Logged in to github.com as <your-username>

# Quick smoke test — fetch a real issue
gh issue view 1769 --repo unclecode/crawl4ai --json number,title
```

---

## 8. Clone the Crawl4AI Repo (for Static Analysis)

The pipeline performs AST-based static analysis on the actual Crawl4AI source code.
Without this clone, static analysis steps are skipped (the pipeline still runs and
produces reports, but marks those steps as "blocked").

```bash
# Clone into the expected default location
gh repo clone unclecode/crawl4ai ~/crawl4ai-repo

# Verify
ls ~/crawl4ai-repo/crawl4ai/
```

To use a custom path instead, pass `--repo-path /your/path` to `main_gh.py` or set it
in the systemd service file.

---

## 9. Run the App — Quick Test

With the venv activated and `cd ~/rca`:

```bash
source .venv/bin/activate
cd ~/rca

# Analyze a single issue by URL (dry-run: no GitHub writes)
python3 main_gh.py --url https://github.com/unclecode/crawl4ai/issues/1769 --dry-run

# Same with issue number
python3 main_gh.py --issue 1769 --dry-run

# Check the generated report
cat test_scripts/issues/1769/verify.md
python3 test_scripts/issues/1769/verify.py

# Run the validation helper (local-only, no network writes)
python3 validate_issue.py 1769
```

You should see log lines like:
```
INFO - Fetching issue #1769 from GitHub...
INFO - Pattern detected: timeout_issue (confidence: 0.95)
INFO - Report written: test_scripts/issues/1769/verify.md
INFO - Reproduction script written: test_scripts/issues/1769/verify.py
```

---

## 10. Run the Web UI

The web dashboard runs on **port 8000** by default.

```bash
cd ~/rca
source .venv/bin/activate

python3 web_ui.py
# Open http://<YOUR_SERVER_IP>:8000 in your browser
```

The dashboard provides:
- **URL input** — paste any `https://github.com/unclecode/crawl4ai/issues/<N>` URL
- **7-step live progress** — Fetch → Parse → Reproduce → Resolution → Root Cause → Fix → Report
- **Terminal log panel** — streams step-by-step output in real time
- **Report card** — shows the resolution badge, root cause summary, and tabbed
  `verify.md` / `verify.py` viewer
- **Watch mode panel** — start/stop continuous polling for new issues

> **Note:** Make sure port 8000 is open in the Hetzner firewall (see §13).

---

## 11. Persist with systemd

Create two services: one for the web UI and one optional watch-mode daemon.

### 11.1 Web UI service

```bash
sudo nano /etc/systemd/system/rca-web.service
```

Paste:

```ini
[Unit]
Description=Crawl4AI Root Cause Analysis — Web UI
After=network.target

[Service]
Type=simple
User=deploy
WorkingDirectory=/home/deploy/rca
ExecStart=/home/deploy/rca/.venv/bin/python3 web_ui.py
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

# Optional: point to a custom Crawl4AI repo path
# Environment=RCA_REPO_PATH=/home/deploy/crawl4ai-repo

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable rca-web
sudo systemctl start rca-web

# Check status
sudo systemctl status rca-web

# Live logs
sudo journalctl -u rca-web -f
```

### 11.2 Watch-mode daemon (optional)

Creates a daemon that polls GitHub every 5 minutes for new issues and runs the
analysis pipeline automatically.

```bash
sudo nano /etc/systemd/system/rca-watch.service
```

```ini
[Unit]
Description=Crawl4AI Root Cause Analysis — Watch Daemon
After=network.target

[Service]
Type=simple
User=deploy
WorkingDirectory=/home/deploy/rca
ExecStart=/home/deploy/rca/.venv/bin/python3 main_gh.py --watch --dry-run
Restart=on-failure
RestartSec=30
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable rca-watch
sudo systemctl start rca-watch
sudo journalctl -u rca-watch -f
```

---

## 12. Nginx Reverse Proxy (Optional)

If you want the web UI accessible on port 80/443 without exposing port 8000, set up
Nginx as a reverse proxy.

```bash
sudo apt-get install -y nginx

sudo nano /etc/nginx/sites-available/rca
```

```nginx
server {
    listen 80;
    server_name <YOUR_SERVER_IP>;   # or your domain name

    location / {
        proxy_pass         http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header   Upgrade $http_upgrade;
        proxy_set_header   Connection "upgrade";
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_read_timeout 120s;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/rca /etc/nginx/sites-enabled/rca
sudo nginx -t && sudo systemctl reload nginx
```

With Nginx in front, the app is reachable at `http://<YOUR_SERVER_IP>` (port 80).

### Optional: HTTPS with Let's Encrypt

```bash
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com
```

---

## 13. Firewall Rules

### Hetzner Cloud Firewall (recommended)

In the Hetzner Cloud Console → **Firewalls** → **Create Firewall**:

| Direction | Protocol | Port | Source      | Purpose           |
|-----------|----------|------|-------------|-------------------|
| Inbound   | TCP      | 22   | Your IP     | SSH               |
| Inbound   | TCP      | 80   | Any         | Nginx HTTP        |
| Inbound   | TCP      | 443  | Any         | Nginx HTTPS       |
| Inbound   | TCP      | 8000 | Your IP     | Direct FastAPI access (dev only) |

Assign the firewall to your server.

### UFW (OS-level, optional additional layer)

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 8000/tcp   # remove after Nginx is set up
sudo ufw enable
sudo ufw status
```

---

## 14. Run Tests

```bash
cd ~/rca
source .venv/bin/activate

# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run the full automated test suite (134 tests)
python3 -m pytest tests/ -v

# Run just one module
python3 -m pytest tests/test_web_ui.py -v

# Run the standalone manual test script (no pytest required)
python3 tests/manual_test.py
```

All 134 tests should pass. If any fail, check:
- The venv is active
- You are inside `~/rca` (some tests write to the CWD)
- `gh auth status` shows you are logged in

---

## 15. Troubleshooting

### `gh: command not found`
The GitHub CLI was not installed or is not on PATH. Re-run §4.

### `gh auth status` says "not logged in"
Run `gh auth login` again. If on a headless server use the token method (§7 Option B).

### `FileNotFoundError: [Errno 2] No such file or directory: 'templates'`
You are not running `python3 web_ui.py` from inside the `~/rca` directory. Always
`cd ~/rca` first — the template directory is created relative to the working directory.

### Static analysis steps show "blocked" / "File not found"
The Crawl4AI repo is not cloned at `~/crawl4ai-repo`. Run:
```bash
gh repo clone unclecode/crawl4ai ~/crawl4ai-repo
```
Or pass `--repo-path /your/custom/path` to `main_gh.py`.

### Port 8000 not reachable from browser
Check the Hetzner Cloud Firewall allows TCP 8000 from your IP.
Also verify the service is running:
```bash
sudo systemctl status rca-web
curl http://localhost:8000/api/status
```

### Web UI shows "Analysis already running"
A previous analysis is still in progress (or the server restarted mid-run).
Restart the service to reset in-memory state:
```bash
sudo systemctl restart rca-web
```

### `UnicodeEncodeError` in logs on Linux
Set the locale before running:
```bash
export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8
```
Add these to `/etc/environment` to persist across reboots.

### Seeing old `root/.openclaw/...` path warnings
These come from an older version of the code. Make sure you are on the
`feature/pipeline-fixes-webui-redesign` or `master` branch (after merge):
```bash
git pull
git log --oneline -5
```
The fix replaced that hardcoded path with `~/crawl4ai-repo` in commit `a79d62f`.

---

## Quick Reference

```bash
# Activate venv (required in every new shell)
cd ~/rca && source .venv/bin/activate

# Analyze an issue
python3 main_gh.py --url https://github.com/unclecode/crawl4ai/issues/1769 --dry-run

# Start web UI (foreground)
python3 web_ui.py

# Service management
sudo systemctl status  rca-web
sudo systemctl restart rca-web
sudo journalctl -u rca-web -f

# Update the app
cd ~/rca && git pull && sudo systemctl restart rca-web

# Update the Crawl4AI repo used for static analysis
cd ~/crawl4ai-repo && git pull
```

# Crawl4AI Root Cause Analysis System - Web UI

A modern web-based dashboard for the automated root cause analysis system.

## 🚀 Features

- **Beautiful Dashboard** - Modern gradient UI with real-time stats
- **Issue Analysis** - Analyze specific GitHub issues
- **Pattern Detection** - Visual display of pattern matches with confidence scores
- **Root Cause Display** - Show exact file, line, and function of bugs
- **Fix Visualization** - Side-by-side diff of old vs new code
- **PR Management** - Track and view generated pull requests
- **Watch Mode** - Start/stop continuous monitoring
- **Real-time Updates** - Auto-refresh every 10 seconds
- **Responsive Design** - Works on desktop and mobile

## 📸 Screenshots

The UI features:
- Gradient purple/blue theme
- Card-based statistics display
- Pattern matching badges
- Code diff visualization
- Status indicators
- Form controls with validation

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd /root/.openclaw/workspace/crawl4ai-root-cause-analysis

# Install web UI dependencies
pip3 install -r requirements_web.txt
```

### 2. Run Web UI

```bash
python3 web_ui.py
```

### 3. Open Dashboard

Open your browser and navigate to:
```
http://localhost:8000
```

## 🎯 How to Use

### Analyze a Specific Issue

1. Enter GitHub issue number (e.g., 1769)
2. Adjust confidence threshold (default: 0.7)
3. Check/uncheck "Dry Run" (safe mode - won't create PRs)
4. Click "🔬 Analyze Issue"
5. View results below (pattern matches, root cause, fix, PR)

### Start Watch Mode

1. Click "▶️ Start Watch Mode"
2. System will continuously monitor for new issues
3. Watch real-time status updates
4. Click "⏹ Stop" to stop

### View Results

The dashboard shows:
- **Issue Details**: Number, title, type, priority
- **Pattern Matches**: Name and confidence for each pattern
- **Root Cause**: File location and explanation
- **Generated Fix**: Code diff with syntax highlighting
- **PR Link**: Direct link to created pull request

## 📊 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Main dashboard UI |
| `/api/status` | GET | Current system status |
| `/api/analyze` | POST | Trigger issue analysis |
| `/api/watch/start` | POST | Start watch mode |
| `/api/watch/stop` | POST | Stop watch mode |
| `/api/analyses` | GET | List all analyses |

### Example API Usage

```bash
# Analyze issue #1769
curl -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "issue_number": 1769,
    "confidence_threshold": 0.7,
    "dry_run": true
  }'

# Get system status
curl http://localhost:8000/api/status

# Start watch mode
curl -X POST http://localhost:8000/api/watch/start

# Stop watch mode
curl -X POST http://localhost:8000/api/watch/stop
```

## 🎨 UI Features

### Dashboard
- System statistics cards (issues processed, patterns detected, fixes generated)
- Real-time status indicator
- Beautiful gradient background
- Responsive layout

### Analysis Form
- Issue number input with validation
- Confidence threshold slider (0.0 to 1.0)
- Dry run checkbox (default: checked)
- Submit button with loading state

### Results Display
- Issue metadata (type, priority, keywords)
- Pattern matches with confidence scores
- Root cause details (file, line, function)
- Code diff with syntax highlighting
- PR links when available
- Status badges (bug/feature, high/medium/low)

### Watch Mode
- Start/stop controls
- Status indicator (running/stopped)
- Auto-refresh every 10 seconds

## 🛠️ Configuration

Edit `web_ui.py` to customize:

```python
# Change port
uvicorn.run(host="0.0.0.0", port=8000)

# Change host (for remote access)
uvicorn.run(host="0.0.0.0", port=8000)

# Enable debug mode
uvicorn.run(host="0.0.0.0", port=8000, log_level="debug")
```

## 🔐 Security

- No authentication required (for local use)
- Add authentication for production deployment
- Input validation on all endpoints
- Error handling with proper HTTP status codes

## 📋 Production Deployment

For production use, consider:

1. **Add Authentication**
   ```python
   from fastapi import Depends, HTTPException, status
   from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
   
   security = HTTPBearer()
   
   @app.get("/api/status", dependencies=[Depends(security)])
   async def get_status(credentials: HTTPAuthorizationCredentials = Depends(security)):
       # Validate token
       pass
   ```

2. **Use Production Server**
   ```bash
   uvicorn web_ui:app --host 0.0.0.0 --port 8000 --workers 4
   ```

3. **Add HTTPS**
   ```bash
   uvicorn web_ui:app --host 0.0.0.0 --port 8443 --ssl-keyfile key.pem --ssl-certfile cert.pem
   ```

4. **Set Up Reverse Proxy (Nginx)**
   ```nginx
   location / {
       proxy_pass http://localhost:8000;
       proxy_set_header Host $host;
       proxy_set_header X-Real-IP $remote_addr;
   }
   ```

## 🧪 Testing

```bash
# Start server
python3 web_ui.py

# In another terminal, test endpoints
curl http://localhost:8000/api/status
curl -X POST http://localhost:8000/api/analyze -H "Content-Type: application/json" -d '{"issue_number": 1769}'
```

## 📁 File Structure

```
crawl4ai-root-cause-analysis/
├── web_ui.py              # FastAPI web server (27KB)
├── requirements_web.txt    # Web UI dependencies
├── templates/
│   └── index.html      # Jinja2 template (auto-created)
└── [existing modules...]
```

## 🎯 Use Cases

1. **Manual Issue Analysis**
   - User enters issue number
   - System analyzes issue
   - Results displayed in dashboard

2. **Continuous Monitoring**
   - Start watch mode
   - System automatically processes new issues
   - Dashboard updates in real-time

3. **API Integration**
   - Use API endpoints from other applications
   - Build custom dashboards
   - Integrate with CI/CD

## 📈 What's Next?

Potential enhancements:
- [ ] User authentication
- [ ] Historical analysis search
- [ ] Export results (CSV/JSON)
- [ ] Email notifications
- [ ] Dark/light theme toggle
- [ ] Real-time WebSocket updates
- [ ] Integration with GitHub webhooks

## 📞 Support

For issues or questions:
- Check documentation in `README.md`
- Review code comments in `web_ui.py`
- Test with dry run first
- Check system logs

---

**Start using the web UI:**

```bash
python3 web_ui.py
```

Then open: http://localhost:8000

**🎉 Enjoy the beautiful dashboard!**

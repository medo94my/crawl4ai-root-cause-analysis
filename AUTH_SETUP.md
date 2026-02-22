# GitHub Authentication Setup Guide

## Option 1: Fork Crawl4AI (Recommended for Testing)

If you want to test the system on your own fork first:

### Step 1: Fork the Repository
1. Go to https://github.com/unclecode/crawl4ai
2. Click **Fork** button (top right)
3. Choose your account

### Step 2: Create GitHub Personal Access Token
1. Go to https://github.com/settings/tokens
2. Click **Generate new token** → **Generate new token (classic)**
3. Set these permissions:
   - ✅ `repo` (Full control of private repositories)
   - ✅ `public_repo` (Access public repositories)
4. Click **Generate token**
5. **Copy the token** (you won't see it again!)

### Step 3: Set Up the System

```bash
# Clone YOUR fork (replace YOUR_USERNAME with your GitHub username)
cd /root/.openclaw/workspace
git clone https://github.com/YOUR_USERNAME/crawl4ai.git crawl4ai-fork
cd crawl4ai-fork

# Configure git
git config user.name "Your Name"
git config user.email "your.email@example.com"

# Set GitHub token
export GITHUB_TOKEN="your_token_here"

# Add to ~/.bashrc for persistence
echo 'export GITHUB_TOKEN="your_token_here"' >> ~/.bashrc
source ~/.bashrc
```

### Step 4: Update System Configuration

Edit `/root/.openclaw/workspace/crawl4ai-root-cause-analysis/main.py`:

```python
# Change these lines:
self.owner = "YOUR_USERNAME"  # Your GitHub username
self.repo = "crawl4ai"      # Your fork name
```

And in `pr_creator.py`:

```python
# Change:
self.owner = "YOUR_USERNAME"
self.repo = "crawl4ai"
```

### Step 5: Test

```bash
cd /root/.openclaw/workspace/crawl4ai-root-cause-analysis

# Test on a real issue (dry run)
python3 main.py --issue 1769 --dry-run

# If dry run works, try real PR
python3 main.py --issue 1769 --no-dry-run
```

---

## Option 2: Use Upstream Repository (For Direct Contributions)

If you want to contribute directly to Crawl4AI:

### Step 1: Create GitHub Personal Access Token
Same as Option 1, Step 2 above.

### Step 2: Clone and Configure

```bash
# Clone the main repository
cd /root/.openclaw/workspace
git clone https://github.com/unclecode/crawl4ai.git crawl4ai-repo
cd crawl4ai-repo

# Configure git
git config user.name "Your Name"
git config user.email "your.email@example.com"

# Set GitHub token
export GITHUB_TOKEN="your_token_here"
```

### Step 3: Test

Same as Option 1, Step 5.

---

## Quick Setup Script

I'll create a script to help you set up authentication:
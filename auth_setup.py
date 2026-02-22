#!/usr/bin/env python3
"""
Interactive GitHub Authentication Setup

This script guides you through setting up GitHub authentication
without storing or transmitting sensitive information.
"""

import os
import subprocess
import getpass
from pathlib import Path


def print_header(text):
    """Print a formatted header."""
    print("\n" + "=" * 60)
    print(text)
    print("=" * 60 + "\n")


def run_command(cmd, check=False):
    """Run a shell command and return output."""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            check=check
        )
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)


def main():
    """Main setup routine."""
    print_header("GitHub Authentication Setup")

    # Step 1: Get GitHub username
    print("Step 1: GitHub Username")
    username = input("Enter your GitHub username: ").strip()

    if not username:
        print("❌ Username is required!")
        return

    print(f"✅ Username: {username}\n")

    # Step 2: Repository info
    print("Step 2: Repository Information")
    print("Choose an option:")
    print("  1. Use your fork of Crawl4AI (recommended for testing)")
    print("  2. Use the upstream Crawl4AI repository (for direct contributions)")

    choice = input("\nEnter choice (1 or 2): ").strip()

    if choice == "1":
        repo_owner = username
        repo_name = "crawl4ai"
        repo_url = f"https://github.com/{username}/crawl4ai.git"
        repo_path = "/root/.openclaw/workspace/crawl4ai-fork"
    elif choice == "2":
        repo_owner = "unclecode"
        repo_name = "crawl4ai"
        repo_url = "https://github.com/unclecode/crawl4ai.git"
        repo_path = "/root/.openclaw/workspace/crawl4ai-repo"
    else:
        print("❌ Invalid choice!")
        return

    print(f"✅ Repository: {repo_owner}/{repo_name}\n")

    # Step 3: Clone or verify repository
    print("Step 3: Repository Setup")

    if os.path.exists(repo_path):
        print(f"✅ Repository already exists at: {repo_path}")
        verify = input("Would you like to verify and update it? (y/n): ").strip().lower()
        if verify == 'y':
            success, _, _ = run_command(f"cd {repo_path} && git fetch origin")
            if success:
                print("✅ Repository updated successfully")
            else:
                print("⚠️  Failed to update repository")
    else:
        print(f"Cloning repository to: {repo_path}")
        success, _, error = run_command(f"git clone {repo_url} {repo_path}")

        if success:
            print(f"✅ Repository cloned successfully")
        else:
            print(f"❌ Failed to clone repository: {error}")
            return

    # Step 4: Configure git
    print("\nStep 4: Git Configuration")

    name = input("Enter your git name (or press Enter to skip): ").strip()
    email = input("Enter your git email (or press Enter to skip): ").strip()

    if name or email:
        if name:
            success, _, _ = run_command(
                f"cd {repo_path} && git config user.name '{name}'"
            )
            if success:
                print(f"✅ Git name configured: {name}")

        if email:
            success, _, _ = run_command(
                f"cd {repo_path} && git config user.email '{email}'"
            )
            if success:
                print(f"✅ Git email configured: {email}")

    # Step 5: GitHub Personal Access Token
    print("\nStep 5: GitHub Personal Access Token")
    print("=" * 60)
    print("You need to create a GitHub Personal Access Token:")
    print()
    print("1. Go to: https://github.com/settings/tokens")
    print("2. Click 'Generate new token' → 'Generate new token (classic)'")
    print("3. Select these permissions:")
    print("   ✅ repo (Full control of private repositories)")
    print("   ✅ public_repo (Access public repositories)")
    print("4. Click 'Generate token'")
    print("5. **Copy the token** (you won't see it again!)")
    print("=" * 60)

    print("\n⚠️  SECURITY NOTICE:")
    print("   - Your token will be stored locally only")
    print("   - It will be added to your ~/.bashrc file")
    print("   - Never share your token with anyone")
    print()

    token = getpass.getpass("Enter your GitHub token (input hidden): ").strip()

    if not token:
        print("❌ Token is required for PR creation!")
        print("   You can still use the system in --dry-run mode")
        return

    print("✅ Token received\n")

    # Step 6: Save configuration
    print("Step 6: Saving Configuration")

    # Add to ~/.bashrc
    bashrc_path = Path.home() / ".bashrc"
    token_line = f'\nexport GITHUB_TOKEN="{token}"\n'

    # Check if token already exists
    try:
        with open(bashrc_path, 'r') as f:
            bashrc_content = f.read()
    except FileNotFoundError:
        bashrc_content = ""

    if 'export GITHUB_TOKEN=' in bashrc_content:
        overwrite = input("GITHUB_TOKEN already exists. Overwrite? (y/n): ").strip().lower()
        if overwrite != 'y':
            print("⚠️  Skipping token update")
            token_line = ""
        else:
            # Remove old token line
            bashrc_content = '\n'.join(
                line for line in bashrc_content.split('\n')
                if not line.startswith('export GITHUB_TOKEN=')
            )

    if token_line:
        with open(bashrc_path, 'a') as f:
            f.write(token_line)
        print(f"✅ Token saved to {bashrc_path}")

    # Update system configuration files
    print("\nStep 7: Updating System Configuration")

    # Update pr_creator.py
    pr_creator_path = Path("/root/.openclaw/workspace/crawl4ai-root-cause-analysis/pr_creator.py")
    if pr_creator_path.exists():
        try:
            with open(pr_creator_path, 'r') as f:
                content = f.read()

            # Replace owner and repo
            content = content.replace(
                'self.owner = "unclecode"',
                f'self.owner = "{repo_owner}"'
            )
            content = content.replace(
                'self.repo = "crawl4ai"',
                f'self.repo = "{repo_name}"'
            )

            with open(pr_creator_path, 'w') as f:
                f.write(content)

            print(f"✅ Updated pr_creator.py")
        except Exception as e:
            print(f"⚠️  Failed to update pr_creator.py: {e}")

    # Final summary
    print_header("Setup Complete!")

    print("✅ GitHub Authentication Configured")
    print()
    print("Repository Information:")
    print(f"  Owner: {repo_owner}")
    print(f"  Repo: {repo_name}")
    print(f"  Path: {repo_path}")
    print()
    print("Next Steps:")
    print(f"  1. Run: source ~/.bashrc")
    print(f"  2. Test: cd /root/.openclaw/workspace/crawl4ai-root-cause-analysis")
    print(f"  3. Run: python3 main.py --issue 1769 --dry-run")
    print()
    print("To activate the token in this session:")
    print("  export GITHUB_TOKEN=\"your_token_here\"")
    print()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Setup cancelled by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")

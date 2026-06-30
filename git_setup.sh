#!/usr/bin/env bash
# Create the GitHub repo and push over HTTPS (uses gh CLI)
set -e
cd "$(dirname "$0")"
REPO="mea-backlog-tracker-from-pdfs-python"

command -v git >/dev/null 2>&1 || { echo "git not installed."; exit 1; }
command -v gh  >/dev/null 2>&1 || { echo "gh (GitHub CLI) not installed: https://cli.github.com/"; exit 1; }

# Use HTTPS for git operations (avoids SSH publickey errors)
gh config set git_protocol https >/dev/null 2>&1 || true

# Init repo + first commit if needed
if [ ! -d .git ]; then
    git init -b main
    git add -A
    git commit -m "Initial commit: KTU Grade Card Extractor"
else
    git add -A
    git commit -m "Update" 2>/dev/null || true
fi

# Resolve GitHub owner for the HTTPS URL
OWNER="$(gh api user --jq .login 2>/dev/null)"
if [ -z "$OWNER" ]; then
    echo "Could not determine GitHub user. Run: gh auth login"
    exit 1
fi

# Create repo if it doesn't exist
if ! gh repo view "$OWNER/$REPO" >/dev/null 2>&1; then
    echo "Creating GitHub repo '$REPO'..."
    gh repo create "$REPO" --private --source=. --remote=origin
fi

# Force HTTPS remote (overwrites any SSH remote from a previous run)
git remote remove origin >/dev/null 2>&1 || true
git remote add origin "https://github.com/$OWNER/$REPO.git"

echo "Pushing to https://github.com/$OWNER/$REPO ..."
git push -u origin main

echo "Done. Repo: https://github.com/$OWNER/$REPO  (private; 'gh repo edit --visibility public' to publish)"

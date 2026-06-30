#!/usr/bin/env bash
# Create the GitHub repo and push (uses gh CLI)
set -e
cd "$(dirname "$0")"
REPO="mea-backlog-tracker-from-pdfs-python"

command -v git >/dev/null 2>&1 || { echo "git not installed."; exit 1; }
command -v gh  >/dev/null 2>&1 || { echo "gh (GitHub CLI) not installed: https://cli.github.com/"; exit 1; }

# Remove any half-created repo
[ -d .git ] && rm -rf .git

git init -b main
git add -A
git commit -m "Initial commit: KTU Grade Card Extractor"

# Create repo (private) from current dir, add remote 'origin', and push
gh repo create "$REPO" --private --source=. --remote=origin --push

echo "Done. Repo: $REPO  (private; 'gh repo edit --visibility public' to publish)"

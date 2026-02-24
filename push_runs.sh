#!/usr/bin/env bash
# push_runs.sh — Commit and push all new run logs to GitHub.
#
# Usage:
#   ./push_runs.sh              # commit & push any new/changed run logs
#   ./push_runs.sh "my note"    # include a custom note in the commit message

set -euo pipefail

cd "$(dirname "$0")"

RUNS_DIR="runs"

if [ ! -d "$RUNS_DIR" ]; then
    echo "No runs/ directory found. Run the pipeline first."
    exit 1
fi

# Count new/changed files in runs/
CHANGED=$(git status --porcelain "$RUNS_DIR" | wc -l | tr -d ' ')

if [ "$CHANGED" -eq 0 ]; then
    echo "No new run logs to push."
    exit 0
fi

# Stage all run log files
git add "$RUNS_DIR"/*.json "$RUNS_DIR"/INDEX.md 2>/dev/null || true

# Build commit message
COUNT=$(git diff --cached --name-only "$RUNS_DIR" | grep -c '\.json$' || true)
NOTE="${1:-}"
MSG="Add ${COUNT} pipeline run log(s)"
if [ -n "$NOTE" ]; then
    MSG="$MSG — $NOTE"
fi

echo "Committing $COUNT run log(s)..."
git commit -m "$MSG"

echo "Pushing to GitHub..."
git push origin main

echo "✓ Run logs pushed to GitHub"
echo "  View at: https://github.com/$(git remote get-url origin | sed 's|.*github.com[:/]||;s|\.git$||')/tree/main/runs"

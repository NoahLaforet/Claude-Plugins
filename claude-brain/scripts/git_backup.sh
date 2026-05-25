#!/bin/bash
# Auto-backup the Claude Brain vault to its private GitHub repo.
# Runs every 15 minutes via launchd (see templates/com.claude-brain.gitbackup.plist).
#
# Setup: git init your vault folder, add a remote, and ensure SSH keys are configured.
# The vault path is read from the CLAUDE_BRAIN_VAULT env var, or auto-detected as the
# directory containing this scripts/ folder.

SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -n "$CLAUDE_BRAIN_VAULT" ]; then
    VAULT="$CLAUDE_BRAIN_VAULT"
else
    VAULT="$(dirname "$SCRIPTS_DIR")"
fi

LOG="$VAULT/_meta/gitbackup.log"
mkdir -p "$VAULT/_meta"

cd "$VAULT" || exit 0
[ -n "$(git status --porcelain 2>/dev/null)" ] || exit 0

git add -A
git commit -q -m "auto-backup $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG" 2>&1
if git push -q origin main >> "$LOG" 2>&1; then
    echo "$(date '+%F %T') pushed ok" >> "$LOG"
else
    echo "$(date '+%F %T') PUSH FAILED" >> "$LOG"
fi

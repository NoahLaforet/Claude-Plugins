#!/usr/bin/env bash
#
# run_weekly.sh - launchd entry point for the weekly Claude setup audit.
# Runs the linter (applying safe auto-fixes), then notifies Noah with the result.
#
set -uo pipefail

DIR="$HOME/.claude/claude-audit"
LOG="$DIR/run.log"
PY="$(command -v python3 || echo /usr/bin/python3)"

ts="$(date '+%Y-%m-%d %H:%M:%S')"
summary="$("$PY" "$DIR/weekly_audit.py" 2>>"$LOG")"
echo "[$ts] $summary" >>"$LOG"

# Notify. afplay only on ATTENTION so a clean week stays quiet.
title="Claude setup audit"
if printf '%s' "$summary" | grep -qi "need attention"; then
  osascript -e "display notification \"$summary. See claude-audit/reports/latest.md\" with title \"$title\" sound name \"Submarine\"" 2>>"$LOG" || true
  afplay /System/Library/Sounds/Submarine.aiff 2>/dev/null || true
else
  osascript -e "display notification \"$summary\" with title \"$title\"" 2>>"$LOG" || true
fi
exit 0

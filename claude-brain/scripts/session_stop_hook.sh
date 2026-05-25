#!/bin/bash
# Stop hook -- fires when Claude Code finishes responding (end of every chat turn).
#
# Two jobs:
#   1. Ingest the just-finished session into the vault (extract_code.py).
#   2. Run a heuristic classifier so the new chat lands with a cluster and
#      tags instead of empty frontmatter. SessionStart on the next session
#      can upgrade these via classify_pending.py.
#
# Always exits 0 -- the chat-finish flow must never be blocked.
# Logs to _meta/code_sync.log.
#
# Wire up in ~/.claude/settings.json:
#   "hooks": {
#     "Stop": [{
#       "matcher": "",
#       "hooks": [{"type": "command",
#                  "command": "/path/to/scripts/session_stop_hook.sh"}]
#     }]
#   }
set -u

SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -n "${CLAUDE_BRAIN_VAULT:-}" ]; then
    META="$CLAUDE_BRAIN_VAULT/_meta"
else
    META="$(dirname "$SCRIPTS_DIR")/_meta"
fi
LOG="$META/code_sync.log"
PY="$(command -v python3 || echo python3)"

mkdir -p "$META"

{
    echo "=== $(date) session_stop_hook ==="
    "$PY" "$SCRIPTS_DIR/extract_code.py" --no-classify 2>&1
    "$PY" "$SCRIPTS_DIR/auto_classify.py" 2>&1
    "$PY" "$SCRIPTS_DIR/sync_memory.py" 2>&1
    "$PY" "$SCRIPTS_DIR/extract_memory_candidates.py" 2>&1
} >> "$LOG" 2>&1

# Back up the vault to its private GitHub repo right after each session.
bash "$SCRIPTS_DIR/git_backup.sh" 2>&1 || true

exit 0

#!/bin/bash
# SessionStart hook -- runs at the start of every Claude Code session.
#
# Three jobs:
#   1. Ingest any new Claude Code sessions into the vault.
#   2. Surface "where you left off" -- most recent PreCompact checkpoint +
#      pending classifications + memory-update candidates.
#   3. Surface project context if cwd matches a known project.
#
# Always exits 0 (failures must not block session start). Stdout is a JSON
# object consumed by the harness; logs go to _meta/code_sync.log.
#
# Wire up in ~/.claude/settings.json:
#   "hooks": {
#     "SessionStart": [{
#       "matcher": "",
#       "hooks": [{"type": "command",
#                  "command": "/path/to/scripts/session_start_hook.sh"}]
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
CHECKPOINTS="$HOME/.claude/checkpoints"
PY="$(command -v python3 || echo python3)"
CWD="${PWD:-$HOME}"

mkdir -p "$META"

{
    echo "=== $(date) session_start_hook (cwd=$CWD) ==="
    "$PY" "$SCRIPTS_DIR/extract_code.py" --no-classify 2>&1
    "$PY" "$SCRIPTS_DIR/extract_memory_candidates.py" 2>&1
} >> "$LOG" 2>&1

PENDING=$("$PY" "$SCRIPTS_DIR/classify_pending.py" --count 2>/dev/null | tr -d ' ')
PENDING=${PENDING:-0}

# Compute candidate count (live, may be 0)
CANDS=0
if [ -f /tmp/claude_brain_memory_candidates.json ]; then
    CANDS=$("$PY" -c "import json; print(len(json.load(open('/tmp/claude_brain_memory_candidates.json'))))" 2>/dev/null || echo 0)
fi

# Latest checkpoint freshness (in hours)
CKPT_AGE=999999
if [ -f "$CHECKPOINTS/latest.md" ]; then
    CKPT_AGE=$(( ( $(date +%s) - $(stat -f %m "$CHECKPOINTS/latest.md" 2>/dev/null || stat -c %Y "$CHECKPOINTS/latest.md" 2>/dev/null || echo 0) ) / 3600 ))
fi

"$PY" - "$PENDING" "$CANDS" "$CKPT_AGE" "$CWD" "$SCRIPTS_DIR" <<'PY'
import json, os, sys
from pathlib import Path

pending, cands, ckpt_age_hr, cwd, scripts_dir = (
    sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4], sys.argv[5]
)
parts: list[str] = []

# 1. Recent checkpoint (PreCompact / stale-resume continuity)
ckpt = Path.home() / '.claude' / 'checkpoints' / 'latest.md'
if ckpt.exists() and ckpt_age_hr < 72:
    parts.append(
        f"Resume context (last checkpoint, {ckpt_age_hr}h ago)\n"
        f"  Read `{ckpt}` first if this session is resuming an in-flight task. "
        "It captures the last 20 user requests, files touched, and recent decisions "
        "from before the previous compaction or session end."
    )

# 2. Pending chat classifications
if int(pending) > 0:
    parts.append(
        f"{pending} unclassified chat(s)\n"
        f"  When the user pauses, run: python3 {scripts_dir}/classify_pending.py --list\n"
        "  Decide clusters/tags/entities, write to /tmp/claude_brain_classifications.json, then:\n"
        f"  python3 {scripts_dir}/classify_pending.py --apply /tmp/claude_brain_classifications.json\n"
        "  No API key needed -- you are the classifier."
    )

# 3. Memory-update candidates
if int(cands) > 0:
    parts.append(
        f"{cands} memory-update candidate(s) queued\n"
        f"  At a natural pause, read `/tmp/claude_brain_memory_candidates.json`. "
        "Each entry is a high-signal phrase caught from recent chats. "
        "Triage: confirm real signals, update memory files in "
        "`~/.claude/projects/<slug>/memory/`, add to MEMORY.md, then clear the queue."
    )

# 4. Project context -- if cwd looks project-specific, surface its memory file
# Customize this dict for your own projects:
#   key = substring to match in cwd (case-insensitive)
#   value = filename in ~/.claude/projects/<slug>/memory/ (or None)
project_files: dict[str, str | None] = {
    'my-project-name': 'project_myproject.md',   # example entry
}

# Auto-detect memory dir (most recently modified)
import os as _os
projects_dir = Path.home() / '.claude' / 'projects'
mem_dir = None
if projects_dir.exists():
    candidates = sorted(projects_dir.glob('*/memory'),
                        key=lambda p: p.stat().st_mtime, reverse=True)
    if candidates:
        mem_dir = candidates[0]

if mem_dir:
    for keyword, fname in project_files.items():
        if keyword.lower() in cwd.lower():
            if fname and (mem_dir / fname).exists():
                parts.append(
                    f"Project context for `{keyword}`: read "
                    f"`{mem_dir / fname}` for current state and open items."
                )
            break

if not parts:
    sys.exit(0)

print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": "\n\n".join(parts)
    }
}))
PY

exit 0

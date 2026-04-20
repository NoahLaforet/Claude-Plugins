#!/usr/bin/env bash
# Install /usage-today for Claude Code.
# Copies the aggregator script and the slash-command template into ~/.claude/.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="$HOME/.claude"
CMD_DIR="$CLAUDE_DIR/commands"

mkdir -p "$CLAUDE_DIR" "$CMD_DIR"

install -m 0755 "$HERE/usage_today.py"   "$CLAUDE_DIR/usage_today.py"
install -m 0644 "$HERE/usage-today.md"   "$CMD_DIR/usage-today.md"

echo "Installed:"
echo "  $CLAUDE_DIR/usage_today.py"
echo "  $CMD_DIR/usage-today.md"
echo
echo "Reload Claude Code (or just open a new session) and run  /usage-today"

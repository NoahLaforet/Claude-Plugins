#!/usr/bin/env bash
#
# setup/install.sh - install the portable Claude Code setup into ~/.claude.
#
# Prompts for the few private values it needs, auto-detects your home directory,
# templates everything, and wires in the hooks, skills, and weekly auto-audit.
# Nothing private is hardcoded; you (or anyone) just answer the prompts.
#
# Safe to re-run. It never overwrites an existing settings.json or CLAUDE.md; it
# writes a .new file next to them and tells you to merge.
#
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE="$HOME/.claude"
PURPLE=$'\033[35m'; GREEN=$'\033[32m'; DIM=$'\033[2m'; RST=$'\033[0m'
say() { printf '%s[setup]%s %s\n' "$PURPLE" "$RST" "$1"; }
ok()  { printf '%s[ok]%s %s\n' "$GREEN" "$RST" "$1"; }

say "Installing the portable Claude Code setup into $CLAUDE"
echo

# --- prompts (home and username come from the environment, never typed) ---
read -r -p "Your full name (for commit author + CLAUDE.md): " FULL_NAME
read -r -p "Your git email: " EMAIL
read -r -p "Your GitHub username: " GITHUB_USER
read -r -p "Path to your Obsidian vault for second-brain (blank to skip): " VAULT_PATH
echo

render() {
  # render <src> <dst>: substitute placeholders into a copy
  sed -e "s|{{FULL_NAME}}|${FULL_NAME}|g" \
      -e "s|{{EMAIL}}|${EMAIL}|g" \
      -e "s|{{GITHUB_USER}}|${GITHUB_USER}|g" \
      -e "s|{{VAULT_PATH}}|${VAULT_PATH}|g" \
      -e "s|__HOME__|${HOME}|g" \
      "$1" > "$2"
}

mkdir -p "$CLAUDE/hooks" "$CLAUDE/skills" "$CLAUDE/claude-audit/reports"

# --- hooks ---
cp "$DIR/hooks/skill_router.py" "$CLAUDE/hooks/skill_router.py"
ok "hook: skill_router.py"

# --- skills ---
mkdir -p "$CLAUDE/skills/claude-audit"
cp "$DIR/skills/claude-audit/SKILL.md" "$CLAUDE/skills/claude-audit/SKILL.md"
ok "skill: claude-audit"
if [ -n "$VAULT_PATH" ]; then
  mkdir -p "$CLAUDE/skills/second-brain"
  render "$DIR/skills/second-brain/SKILL.md" "$CLAUDE/skills/second-brain/SKILL.md"
  ok "skill: second-brain (vault: $VAULT_PATH)"
else
  say "no vault path given, skipping the second-brain skill"
fi

# --- weekly auto-audit ---
cp "$DIR/claude-audit/weekly_audit.py" "$CLAUDE/claude-audit/weekly_audit.py"
cp "$DIR/claude-audit/run_weekly.sh" "$CLAUDE/claude-audit/run_weekly.sh"
chmod +x "$CLAUDE/claude-audit/run_weekly.sh" "$CLAUDE/claude-audit/weekly_audit.py"
mkdir -p "$HOME/Library/LaunchAgents"
render "$DIR/claude-audit/com.claude.weekly-audit.plist" "$HOME/Library/LaunchAgents/com.claude.weekly-audit.plist"
if launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/com.claude.weekly-audit.plist" 2>/dev/null; then
  ok "weekly auto-audit installed and scheduled (Sundays 10:00)"
else
  say "weekly audit plist installed; load it with:"
  printf '%s  launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.claude.weekly-audit.plist%s\n' "$DIM" "$RST"
fi

# --- CLAUDE.md (never clobber) ---
if [ -e "$CLAUDE/CLAUDE.md" ]; then
  render "$DIR/CLAUDE.example.md" "$CLAUDE/CLAUDE.md.new"
  say "you already have a CLAUDE.md; wrote $CLAUDE/CLAUDE.md.new for you to merge"
else
  render "$DIR/CLAUDE.example.md" "$CLAUDE/CLAUDE.md"
  ok "global CLAUDE.md installed"
fi

# --- settings.json (never clobber) ---
if [ -e "$CLAUDE/settings.json" ]; then
  render "$DIR/settings.example.json" "$CLAUDE/settings.example.rendered.json"
  say "you already have settings.json; wrote settings.example.rendered.json to merge by hand"
else
  render "$DIR/settings.example.json" "$CLAUDE/settings.json"
  ok "settings.json installed"
fi

echo
say "Done. Next steps:"
echo "  1. Status line and other components: see the top-level README and ../statusbar/."
echo "  2. Third-party skills and MCP servers: see setup/SKILLS.md (install from source)."
echo "  3. Review the merged CLAUDE.md / settings.json if you already had them."
echo "  4. The weekly audit report lands in ~/.claude/claude-audit/reports/latest.md."

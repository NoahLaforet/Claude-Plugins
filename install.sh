#!/usr/bin/env bash
# Top-level one-shot installer for the Claude Code Apps & Plugins repo.
# Installs any subset of: summon, statusbar, usage-today, claude-brain.
# Idempotent and safe to re-run; it never overwrites your real settings.json.
#
# Usage:
#   ./install.sh                 # prints usage and exits
#   ./install.sh --help          # prints usage and exits
#   ./install.sh --all           # install everything
#   ./install.sh --summon        # menu-bar companion (Homebrew + venv + whisper)
#   ./install.sh --statusbar     # three-line status line + busy hook
#   ./install.sh --usage-today   # /usage-today slash command
#   ./install.sh --brain         # Claude Second Brain Obsidian vault bootstrap
#   ./install.sh --no-model      # passed through to summon (skips whisper download)
set -euo pipefail

# Repo dir is wherever this script lives. Never hard-code a home path.
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="$HOME/.claude"

say()  { printf "\033[1;36m[plugins]\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m[plugins]\033[0m %s\n" "$*" >&2; }
die()  { printf "\033[1;31m[plugins]\033[0m %s\n" "$*" >&2; exit 1; }

usage() {
  cat <<USAGE
Claude Code Apps & Plugins installer.

Usage:
  ./install.sh [flags]

Flags:
  --all           Install summon, statusbar, usage-today, and brain.
  --summon        Install the menu-bar companion (runs summon/install.sh).
  --statusbar     Install the three-line status line and busy hook.
  --usage-today   Install the /usage-today slash command.
  --brain         Bootstrap the Claude Second Brain Obsidian vault.
  --no-model      Forwarded to summon; skips the ~1.6 GB whisper model download.
  --help          Print this help and exit.

No flags prints this help and exits.

Targets install under "\$HOME/.claude". Repo dir is derived from the script
location, so you can run this from anywhere and from any clone path.
USAGE
}

# ==== parse flags ==========================================================
DO_SUMMON=0
DO_STATUSBAR=0
DO_USAGE=0
DO_BRAIN=0
NO_MODEL=0

if [[ $# -eq 0 ]]; then
  usage
  exit 0
fi

for arg in "$@"; do
  case "$arg" in
    --all)         DO_SUMMON=1; DO_STATUSBAR=1; DO_USAGE=1; DO_BRAIN=1 ;;
    --summon)      DO_SUMMON=1 ;;
    --statusbar)   DO_STATUSBAR=1 ;;
    --usage-today) DO_USAGE=1 ;;
    --brain)       DO_BRAIN=1 ;;
    --no-model)    NO_MODEL=1 ;;
    -h|--help)     usage; exit 0 ;;
    *) die "unknown flag: $arg (try --help)" ;;
  esac
done

# --no-model on its own is not a component to install.
if [[ "$DO_SUMMON$DO_STATUSBAR$DO_USAGE$DO_BRAIN" == "0000" ]]; then
  warn "No component selected. Did you mean --all? Showing usage."
  usage
  exit 0
fi

# ==== settings.json safety reminder ========================================
SETTINGS="$CLAUDE_DIR/settings.json"
if [[ -f "$SETTINGS" ]]; then
  say "Reminder: you have an existing $SETTINGS."
  say "This installer will NOT modify it. Back it up yourself if you like:"
  say "  cp \"$SETTINGS\" \"$SETTINGS.bak\""
fi

# Track what got installed and what still needs a human.
INSTALLED=()
FOLLOWUPS=()

# ==== summon ===============================================================
if [[ "$DO_SUMMON" == "1" ]]; then
  say "Installing summon"
  SUMMON_INSTALLER="$REPO_DIR/summon/install.sh"
  [[ -f "$SUMMON_INSTALLER" ]] || die "missing $SUMMON_INSTALLER"
  if [[ "$NO_MODEL" == "1" ]]; then
    say "Forwarding --no-model to summon (skips whisper download)"
    bash "$SUMMON_INSTALLER" --no-model
  else
    bash "$SUMMON_INSTALLER"
  fi
  INSTALLED+=("summon")
  FOLLOWUPS+=("summon: grant Microphone, Input Monitoring, and Accessibility in System Settings (see summon output above).")
fi

# ==== statusbar (manual steps inline) ======================================
if [[ "$DO_STATUSBAR" == "1" ]]; then
  say "Installing statusbar"
  STATUSBAR_DIR="$REPO_DIR/statusbar"
  [[ -f "$STATUSBAR_DIR/statusline.py" ]] || die "missing $STATUSBAR_DIR/statusline.py"
  [[ -f "$STATUSBAR_DIR/busy_tool.sh" ]]  || die "missing $STATUSBAR_DIR/busy_tool.sh"

  mkdir -p "$CLAUDE_DIR/hooks"

  cp "$STATUSBAR_DIR/statusline.py" "$CLAUDE_DIR/statusline.py"
  chmod +x "$CLAUDE_DIR/statusline.py"
  say "Copied statusline.py to $CLAUDE_DIR/statusline.py"

  cp "$STATUSBAR_DIR/busy_tool.sh" "$CLAUDE_DIR/hooks/busy_tool.sh"
  chmod +x "$CLAUDE_DIR/hooks/busy_tool.sh"
  say "Copied busy_tool.sh to $CLAUDE_DIR/hooks/busy_tool.sh"

  INSTALLED+=("statusbar")

  # The status line and busy hook need settings.json wired up, which we do not
  # touch automatically because it is your live config.
  warn "statusbar needs a manual settings.json step. The files are in place, but"
  warn "the status line will not show until you merge the example into your settings."
  cat <<MANUAL

  Manual statusbar steps (do NOT let any script overwrite your real settings.json):

    1. Merge the contents of:
         $STATUSBAR_DIR/settings.example.json
       into:
         $SETTINGS
       If you have no settings.json yet, copy the example over as a starting point:
         cp "$STATUSBAR_DIR/settings.example.json" "$SETTINGS"
       If you already have hooks or a statusLine block, merge by hand. Do not clobber.

    2. Swap the home-path placeholder for your real home path:
         sed -i '' "s|/Users/YOURNAME|\$HOME|g" "$SETTINGS"

    3. Reload Claude Code (or open the /hooks menu once) so the busy hook re-reads.

MANUAL
  FOLLOWUPS+=("statusbar: merge $STATUSBAR_DIR/settings.example.json into $SETTINGS, then run the sed home-path swap (see above). Your settings.json was NOT modified.")
fi

# ==== usage-today ==========================================================
if [[ "$DO_USAGE" == "1" ]]; then
  say "Installing usage-today"
  USAGE_INSTALLER="$REPO_DIR/usage-today/install.sh"
  [[ -f "$USAGE_INSTALLER" ]] || die "missing $USAGE_INSTALLER"
  bash "$USAGE_INSTALLER"
  INSTALLED+=("usage-today")
  FOLLOWUPS+=("usage-today: open a new Claude session and run /usage-today.")
fi

# ==== claude-brain =========================================================
if [[ "$DO_BRAIN" == "1" ]]; then
  say "Bootstrapping claude-brain"
  BRAIN_BOOTSTRAP="$REPO_DIR/claude-brain/bootstrap.sh"
  [[ -f "$BRAIN_BOOTSTRAP" ]] || die "missing $BRAIN_BOOTSTRAP"
  warn "claude-brain is interactive; it will prompt for vault path, API key, and name."
  bash "$BRAIN_BOOTSTRAP"
  INSTALLED+=("claude-brain")
  FOLLOWUPS+=("claude-brain: make sure Obsidian is running with the Local REST API plugin enabled, then restart Claude Code.")
fi

# ==== summary ==============================================================
echo
say "================================================================"
say "  done"
say "================================================================"
if [[ ${#INSTALLED[@]} -gt 0 ]]; then
  say "Installed: ${INSTALLED[*]}"
else
  say "Installed: nothing"
fi

if [[ ${#FOLLOWUPS[@]} -gt 0 ]]; then
  echo
  say "Manual follow-ups:"
  for f in "${FOLLOWUPS[@]}"; do
    say "  - $f"
  done
fi
echo

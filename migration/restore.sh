#!/usr/bin/env bash
# restore.sh — run this on the NEW MacBook after Apple Migration Assistant finishes.
#
# Migration Assistant will have copied your home dir, apps, and settings.
# This script rebuilds the things that are binary/architecture/OS-version sensitive
# and verifies the rest is in place.
#
# Idempotent. Safe to re-run. Will prompt before anything destructive.

set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SNAP="$HERE/snapshot"

if [ ! -d "$SNAP" ]; then
  echo "✗ No snapshot/ folder here. Did you copy ~/Desktop/migration/ from the old laptop?"
  exit 1
fi

pause() { read -r -p "  Press ENTER to continue, Ctrl-C to abort…" _; }
ok()    { echo "  ✓ $*"; }
warn()  { echo "  ⚠  $*"; }
step()  { echo ""; echo "━━ $* ━━"; }

# ---------- 0. Preflight ----------
step "0. Preflight"
echo "This will:"
echo "  - Install Xcode Command Line Tools"
echo "  - Reinstall Homebrew from your Brewfile"
echo "  - Reinstall pyenv Python versions + rustup toolchains"
echo "  - Reinstall VS Code extensions"
echo "  - Reload user LaunchAgents"
echo "  - Print a checklist of things requiring manual re-auth (OAuth, 1Password, etc.)"
pause

# ---------- 1. Xcode CLT ----------
step "1. Xcode Command Line Tools"
if ! xcode-select -p >/dev/null 2>&1; then
  xcode-select --install || true
  echo "  → Click through the installer dialog, then re-run this script."
  exit 0
else
  ok "already installed"
fi

# ---------- 2. Homebrew ----------
step "2. Homebrew"
if ! command -v brew >/dev/null; then
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi
eval "$(/opt/homebrew/bin/brew shellenv)"
ok "brew available"

if [ -f "$SNAP/Brewfile" ]; then
  echo "  → brew bundle install"
  brew bundle --file="$SNAP/Brewfile" || warn "some packages failed — check output"
fi

# ---------- 3. pyenv / Python ----------
step "3. Python (pyenv)"
if grep -q "pyenv" "$SNAP/toolchains.txt"; then
  if ! command -v pyenv >/dev/null; then
    brew install pyenv
  fi
  # parse pyenv versions (skip 'system' line and the header)
  awk '/^## pyenv/{p=1; next} /^##/{p=0} p && $1!="system" && $1!="*" && NF>0 {print $1}' "$SNAP/toolchains.txt" | while read -r v; do
    [ -z "$v" ] && continue
    echo "  → pyenv install $v"
    pyenv install -s "$v" || warn "pyenv install $v failed"
  done
fi

# ---------- 4. Rust ----------
step "4. Rust"
if grep -q "rustup" "$SNAP/toolchains.txt" && grep -A5 "^## rustup" "$SNAP/toolchains.txt" | grep -q "stable\|nightly\|beta"; then
  if ! command -v rustup >/dev/null; then
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
  fi
  ok "rustup installed — toolchains listed in snapshot/toolchains.txt"
else
  ok "rust is managed via brew (or not installed) — skipping rustup"
fi

# ---------- 5. VS Code extensions ----------
step "5. VS Code"
if [ -f "$SNAP/vscode_extensions.txt" ] && command -v code >/dev/null; then
  while read -r ext; do
    [ -z "$ext" ] && continue
    code --install-extension "$ext" --force >/dev/null 2>&1 && ok "$ext" || warn "failed: $ext"
  done < "$SNAP/vscode_extensions.txt"
else
  warn "code CLI not on PATH — open VS Code → Cmd-Shift-P → 'Shell Command: Install code in PATH', then re-run"
fi

# ---------- 6. LaunchAgents ----------
step "6. LaunchAgents"
if [ -d "$SNAP/launchagents" ]; then
  mkdir -p "$HOME/Library/LaunchAgents"
  for p in "$SNAP/launchagents"/*.plist; do
    [ -f "$p" ] || continue
    base="$(basename "$p")"
    dest="$HOME/Library/LaunchAgents/$base"
    cp -p "$p" "$dest"
    # bootout any stale version, then bootstrap
    launchctl bootout "gui/$UID/${base%.plist}" 2>/dev/null || true
    launchctl bootstrap "gui/$UID" "$dest" 2>/dev/null && ok "$base loaded" || warn "$base failed to load — check paths inside the plist"
  done
fi

# ---------- 7. SSH ----------
step "7. SSH"
if [ -d "$HOME/.ssh" ]; then
  chmod 700 "$HOME/.ssh"
  chmod 600 "$HOME/.ssh"/* 2>/dev/null || true
  chmod 644 "$HOME/.ssh"/*.pub 2>/dev/null || true
  ok "permissions fixed"
  if [ -f "$SNAP/ssh/PRIVATE_KEYS_TO_COPY.txt" ]; then
    echo "  → check these keys exist in ~/.ssh/:"
    while read -r k; do
      [ -z "$k" ] && continue
      if [ -f "$HOME/.ssh/$k" ]; then ok "  $k"; else warn "  MISSING: $k — copy from old laptop"; fi
    done < "$SNAP/ssh/PRIVATE_KEYS_TO_COPY.txt"
  fi
fi

# ---------- 8. Manual re-auth checklist ----------
step "8. Manual re-auth checklist"
cat <<'EOF'
  The following need your hands — script can't do them:

  [ ] 1Password desktop app: sign in (account auto-syncs vaults)
  [ ] gh auth login                           — GitHub CLI
  [ ] op signin                               — 1Password CLI (if installed)
  [ ] gcloud auth login                       — Google Cloud (if installed)
  [ ] aws sso login / aws configure           — AWS (if installed)
  [ ] Claude Code MCPs (Gmail, Calendar, Drive, Obsidian, claude-in-chrome):
      open Claude Code, each MCP will prompt for OAuth re-auth on first use
  [ ] Chrome: sign into Google (extensions + bookmarks sync)
  [ ] VS Code: sign in to Settings Sync (GitHub) if extensions didn't restore
  [ ] Obsidian: open the Claude Brain vault once, confirm it loads
  [ ] Docker Desktop: sign in (if you use it)
  [ ] Messages / FaceTime / iCloud Drive: sign into Apple ID
  [ ] Zoom, Discord, Spotify: sign in

  Also verify:
  [ ] LaunchAgents actually running:  launchctl list | grep -E 'claude-brain|noah'
  [ ] Brew services:                  brew services list
  [ ] Git identity works:             git -C <any repo> fetch
  [ ] Claude Code launches:           claude --version
EOF

echo ""
echo "✓ Restore script complete."
echo "  Snapshot date: $(cat "$SNAP/captured_at.txt" 2>/dev/null || echo unknown)"

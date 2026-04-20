#!/usr/bin/env bash
# capture.sh — run this on the OLD MacBook Pro.
# Snapshots every piece of state that Migration Assistant might miss or
# that is worth having as a belt-and-suspenders record.
#
# Safe to re-run. Overwrites previous snapshot in this folder.

set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SNAP="$HERE/snapshot"
mkdir -p "$SNAP"

echo "→ Capturing to $SNAP"
echo "  ($(date))" > "$SNAP/captured_at.txt"

# ---------- 1. Homebrew ----------
if command -v brew >/dev/null; then
  echo "→ brew bundle dump"
  brew bundle dump --file="$SNAP/Brewfile" --describe --force
  brew list --versions > "$SNAP/brew_versions.txt"
  brew services list > "$SNAP/brew_services.txt" 2>/dev/null || true
fi

# ---------- 2. Language toolchains ----------
echo "→ language toolchains"
{
  echo "## pyenv"
  pyenv versions 2>/dev/null || echo "(none)"
  echo ""
  echo "## rustup"
  rustup toolchain list 2>/dev/null || echo "(no rustup — rust is via brew)"
  echo ""
  echo "## cargo installed"
  ls ~/.cargo/bin 2>/dev/null || echo "(none)"
  echo ""
  echo "## global npm (if any)"
  npm list -g --depth=0 2>/dev/null || echo "(no npm)"
  echo ""
  echo "## global gems (user-installed)"
  gem list --local --no-default 2>/dev/null | grep -v "^$" || true
  echo ""
  echo "## pipx"
  pipx list 2>/dev/null || echo "(no pipx)"
} > "$SNAP/toolchains.txt"

# ---------- 3. VS Code ----------
if command -v code >/dev/null; then
  echo "→ VS Code extensions"
  code --list-extensions > "$SNAP/vscode_extensions.txt"
  # settings.json and keybindings are synced via GitHub Settings Sync,
  # but we snapshot a copy in case sync is stale.
  mkdir -p "$SNAP/vscode"
  cp -f "$HOME/Library/Application Support/Code/User/settings.json" "$SNAP/vscode/" 2>/dev/null || true
  cp -f "$HOME/Library/Application Support/Code/User/keybindings.json" "$SNAP/vscode/" 2>/dev/null || true
  cp -rf "$HOME/Library/Application Support/Code/User/snippets" "$SNAP/vscode/" 2>/dev/null || true
fi

# ---------- 4. Dotfiles (idempotent copy, preserves perms) ----------
echo "→ dotfiles"
mkdir -p "$SNAP/dotfiles"
for f in .zshrc .zprofile .zshenv .bashrc .bash_profile .gitconfig .gitignore_global .vimrc .tmux.conf .inputrc .editorconfig; do
  if [ -f "$HOME/$f" ]; then
    cp -p "$HOME/$f" "$SNAP/dotfiles/$f"
  fi
done

# ~/.config — capture but be mindful of size
if [ -d "$HOME/.config" ]; then
  # tar excluding caches
  tar --exclude='*/Cache/*' --exclude='*/cache/*' --exclude='*/logs/*' \
      -czf "$SNAP/dotfiles/config.tar.gz" -C "$HOME" .config 2>/dev/null || true
fi

# ---------- 5. SSH — keys + config (sensitive! ) ----------
echo "→ ssh"
mkdir -p "$SNAP/ssh"
chmod 700 "$SNAP/ssh"
if [ -d "$HOME/.ssh" ]; then
  cp -p "$HOME/.ssh/config" "$SNAP/ssh/" 2>/dev/null || true
  cp -p "$HOME/.ssh/known_hosts" "$SNAP/ssh/" 2>/dev/null || true
  cp -p "$HOME/.ssh/authorized_keys" "$SNAP/ssh/" 2>/dev/null || true
  # Private keys: list, do NOT copy here — prompt user to handle manually.
  ls -1 "$HOME/.ssh" | grep -Ev '^(config|known_hosts|authorized_keys|.*\.pub)$' > "$SNAP/ssh/PRIVATE_KEYS_TO_COPY.txt" || true
fi
echo "⚠  Private SSH keys are NOT auto-copied. See snapshot/ssh/PRIVATE_KEYS_TO_COPY.txt" >&2

# ---------- 6. GPG ----------
if command -v gpg >/dev/null; then
  echo "→ gpg"
  mkdir -p "$SNAP/gpg"
  gpg --list-secret-keys --keyid-format=long > "$SNAP/gpg/keys.txt" 2>/dev/null || true
  # export is interactive if keys have passphrases; user runs manually.
  echo "# To export secret keys, run:"        > "$SNAP/gpg/EXPORT_ME.sh"
  echo "gpg --export-secret-keys --armor > secret.asc"  >> "$SNAP/gpg/EXPORT_ME.sh"
  echo "gpg --export-ownertrust > ownertrust.txt"       >> "$SNAP/gpg/EXPORT_ME.sh"
fi

# ---------- 7. Git repos (find all + note dirty ones) ----------
echo "→ scanning git repos"
{
  echo "# Git repos under common code dirs"
  echo "# Checked: $(date)"
  # Only scan directories likely to contain repos. Avoid Steam/games/Library.
  SCAN_DIRS=(
    "$HOME/Desktop/Github"
    "$HOME/Desktop/Claude Brain"
    "$HOME/Desktop/CSE 220"
    "$HOME/Desktop/Job Apps"
    "$HOME/Developer"
    "$HOME/code"
    "$HOME/Projects"
    "$HOME/src"
  )
  for d in "${SCAN_DIRS[@]}"; do
    [ -d "$d" ] || continue
    find "$d" -name .git -type d -maxdepth 5 \
      -not -path '*/node_modules/*' \
      -not -path '*/.venv/*' \
      -not -path '*/venv/*' \
      2>/dev/null | while read -r g; do
      r="$(dirname "$g")"
      cd "$r" || continue
      dirty=""
      if [ -n "$(git status --porcelain 2>/dev/null)" ]; then dirty=" [DIRTY]"; fi
      unpushed=""
      if git log @{u}.. --oneline 2>/dev/null | grep -q .; then unpushed=" [UNPUSHED]"; fi
      echo "$r$dirty$unpushed"
    done
  done
} > "$SNAP/git_repos.txt"

# ---------- 8. Claude Code config ----------
echo "→ Claude Code"
if [ -d "$HOME/.claude" ]; then
  tar --exclude='*/cache/*' --exclude='*/sessions/*' --exclude='*/backups/*' \
      --exclude='*/file-history/*' --exclude='*/chrome/*' \
      -czf "$SNAP/claude.tar.gz" -C "$HOME" .claude
fi

# ---------- 9. LaunchAgents (Noah's own automations) ----------
echo "→ LaunchAgents"
mkdir -p "$SNAP/launchagents"
if [ -d "$HOME/Library/LaunchAgents" ]; then
  # Only copy user-owned (non-vendor) agents. Vendor ones (Google/Razer/Steam/Perplexity) reinstall themselves.
  for p in "$HOME/Library/LaunchAgents"/*.plist; do
    [ -f "$p" ] || continue
    base="$(basename "$p")"
    case "$base" in
      com.google.*|com.razer.*|com.valvesoftware.*|ai.perplexity.*) continue ;;
    esac
    cp -p "$p" "$SNAP/launchagents/"
  done
  ls "$SNAP/launchagents" > "$SNAP/launchagents/README.txt"
fi

# ---------- 10. crontab ----------
crontab -l > "$SNAP/crontab.txt" 2>/dev/null || echo "(no crontab)" > "$SNAP/crontab.txt"

# ---------- 11. Installed apps inventory ----------
echo "→ /Applications inventory"
ls /Applications > "$SNAP/applications.txt"
ls "$HOME/Applications" 2>/dev/null >> "$SNAP/applications.txt" || true

# ---------- 12. macOS defaults (selected) ----------
echo "→ macOS defaults"
{
  echo "## Dock persistent-apps"
  defaults read com.apple.dock persistent-apps 2>/dev/null | head -100 || true
  echo ""
  echo "## Finder preferences"
  defaults read com.apple.finder 2>/dev/null | head -50 || true
} > "$SNAP/macos_defaults.txt"

# ---------- 13. CLI auth status (for reminder during restore) ----------
echo "→ CLI auth status"
{
  echo "## gh"; command -v gh && gh auth status 2>&1 | head -10 || echo "(no gh)"
  echo ""
  echo "## 1password"; command -v op && op account list 2>&1 | head -5 || echo "(no op)"
  echo ""
  echo "## aws"; command -v aws && aws configure list-profiles 2>&1 | head -5 || echo "(no aws)"
  echo ""
  echo "## gcloud"; command -v gcloud && gcloud config configurations list 2>&1 | head -10 || echo "(no gcloud)"
} > "$SNAP/cli_auth.txt"

# ---------- 14. Disk usage summary ----------
du -sh "$HOME/Desktop" "$HOME/Documents" "$HOME/Downloads" "$HOME/.claude" 2>/dev/null > "$SNAP/disk_usage.txt" || true

echo ""
echo "✓ Snapshot complete: $SNAP"
echo "  Total size: $(du -sh "$SNAP" | cut -f1)"
echo ""
echo "Next:"
echo "  1. Review $SNAP/git_repos.txt — commit & push anything DIRTY or UNPUSHED"
echo "  2. Review $SNAP/ssh/PRIVATE_KEYS_TO_COPY.txt — copy private keys via secure channel"
echo "  3. Re-run this script before your Migration Assistant session for a fresh snapshot"

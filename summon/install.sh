#!/bin/bash
# Summon installer for macOS.
# Usage:
#   ./install.sh             # full install (Homebrew deps + venv + whisper model)
#   ./install.sh --no-model  # skip the 1.6 GB whisper model download
#   ./install.sh --force     # nuke + rebuild the venv
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SUMMON_HOME="$HOME/.claude/summon"
PLIST_LABEL="com.summon"
PLIST_PATH="$HOME/Library/LaunchAgents/$PLIST_LABEL.plist"
MODEL_FILE="ggml-large-v3-turbo.bin"
MODEL_URL="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/$MODEL_FILE"

SKIP_MODEL=0
FORCE=0
for arg in "$@"; do
  case "$arg" in
    --no-model) SKIP_MODEL=1 ;;
    --force)    FORCE=1 ;;
    -h|--help)
      sed -n '2,6p' "${BASH_SOURCE[0]}"
      exit 0
      ;;
    *) echo "unknown arg: $arg" >&2; exit 2 ;;
  esac
done

say()  { printf "\033[1;34m[summon]\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m[summon]\033[0m %s\n" "$*" >&2; }
die()  { printf "\033[1;31m[summon]\033[0m %s\n" "$*" >&2; exit 1; }

[[ "$(uname)" == "Darwin" ]] || die "Summon is macOS-only."
command -v brew >/dev/null 2>&1 || die "Homebrew is required. Install from https://brew.sh"

# 1. Homebrew deps
say "Checking Homebrew deps (python, whisper-cpp)"
brew list python@3 >/dev/null 2>&1 || brew list python >/dev/null 2>&1 || brew install python
brew list whisper-cpp >/dev/null 2>&1 || brew install whisper-cpp

WHISPER_CLI="$(command -v whisper-cli || true)"
[[ -n "$WHISPER_CLI" ]] || die "whisper-cli not on PATH after brew install. Restart your shell and re-run."

# 2. Copy source
say "Installing source to $SUMMON_HOME"
mkdir -p "$SUMMON_HOME"
cp "$REPO_DIR"/summon.py           "$SUMMON_HOME/"
cp "$REPO_DIR"/dictate.py          "$SUMMON_HOME/"
cp "$REPO_DIR"/launch_claude.sh    "$SUMMON_HOME/"
cp "$REPO_DIR"/requirements.txt    "$SUMMON_HOME/"
[[ -f "$REPO_DIR/gen_icons.py" ]]    && cp "$REPO_DIR/gen_icons.py"    "$SUMMON_HOME/"
[[ -f "$REPO_DIR/gen_app_icon.py" ]] && cp "$REPO_DIR/gen_app_icon.py" "$SUMMON_HOME/"
[[ -f "$REPO_DIR/icon.icns" ]]       && cp "$REPO_DIR/icon.icns"       "$SUMMON_HOME/"
chmod +x "$SUMMON_HOME/launch_claude.sh"
rm -rf "$SUMMON_HOME/icons"
cp -R "$REPO_DIR/icons" "$SUMMON_HOME/icons"

# 3. venv + Python deps
if [[ ! -x "$SUMMON_HOME/venv/bin/python" ]] || [[ "$FORCE" == "1" ]]; then
  say "Creating Python virtualenv"
  rm -rf "$SUMMON_HOME/venv"
  python3 -m venv "$SUMMON_HOME/venv"
fi
say "Installing Python requirements"
"$SUMMON_HOME/venv/bin/python" -m pip install --quiet --upgrade pip
"$SUMMON_HOME/venv/bin/python" -m pip install --quiet -r "$SUMMON_HOME/requirements.txt"

# 4. Whisper model
if [[ "$SKIP_MODEL" == "0" ]]; then
  mkdir -p "$SUMMON_HOME/models"
  if [[ -f "$SUMMON_HOME/models/$MODEL_FILE" ]]; then
    say "Whisper model already present ($(du -h "$SUMMON_HOME/models/$MODEL_FILE" | cut -f1))"
  else
    say "Downloading whisper model (~1.6 GB, one-time)"
    curl -L --fail --progress-bar -o "$SUMMON_HOME/models/$MODEL_FILE" "$MODEL_URL"
  fi
else
  warn "--no-model: skipping model download. Dictate won't transcribe until ~/.claude/summon/models/$MODEL_FILE exists."
fi

# 5. LaunchAgent
say "Installing LaunchAgent $PLIST_LABEL"
# Migrate from the old com.noah.summon label if present
if launchctl print "gui/$(id -u)/com.noah.summon" >/dev/null 2>&1; then
  warn "Removing legacy agent com.noah.summon"
  launchctl bootout "gui/$(id -u)/com.noah.summon" 2>/dev/null || true
  rm -f "$HOME/Library/LaunchAgents/com.noah.summon.plist"
fi
mkdir -p "$HOME/Library/LaunchAgents"
sed -e "s|__PYTHON__|$SUMMON_HOME/venv/bin/python|g" \
    -e "s|__SUMMON__|$SUMMON_HOME|g" \
    -e "s|__LABEL__|$PLIST_LABEL|g" \
    "$REPO_DIR/com.summon.plist.template" > "$PLIST_PATH"
launchctl bootout "gui/$(id -u)/$PLIST_LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST_PATH"
launchctl kickstart "gui/$(id -u)/$PLIST_LABEL" >/dev/null 2>&1 || true

# 6. Desktop launcher (Summon.app)
APP_ROOT="$HOME/Desktop/Summon.app"
mkdir -p "$APP_ROOT/Contents/MacOS" "$APP_ROOT/Contents/Resources"
cat > "$APP_ROOT/Contents/MacOS/Summon" <<APPEOF
#!/bin/bash
# Revive the Summon menu-bar agent if it's dead, then open a new Claude session.
PLIST="$PLIST_PATH"
UID_=\$(id -u)
if ! launchctl print "gui/\${UID_}/$PLIST_LABEL" >/dev/null 2>&1; then
  launchctl bootstrap "gui/\${UID_}" "\$PLIST" 2>/dev/null || true
fi
launchctl kickstart "gui/\${UID_}/$PLIST_LABEL" >/dev/null 2>&1 || true
exec "$SUMMON_HOME/launch_claude.sh"
APPEOF
chmod +x "$APP_ROOT/Contents/MacOS/Summon"
cat > "$APP_ROOT/Contents/Info.plist" <<PLEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleExecutable</key><string>Summon</string>
  <key>CFBundleIdentifier</key><string>$PLIST_LABEL</string>
  <key>CFBundleName</key><string>Summon</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleIconFile</key><string>icon</string>
</dict></plist>
PLEOF
[[ -f "$REPO_DIR/icon.icns" ]] && cp "$REPO_DIR/icon.icns" "$APP_ROOT/Contents/Resources/icon.icns"

# 7. Permissions reminder — show the exact Python.app path to add
PY_APP="$(ls -d /opt/homebrew/Cellar/python@*/*/Frameworks/Python.framework/Versions/*/Resources/Python.app 2>/dev/null | head -1 || true)"

cat <<DONE

================================================================
  Summon installed.
================================================================

Grant these in System Settings -> Privacy & Security:
  * Microphone         (prompted on first clap / dictation)
  * Input Monitoring   (needed for the Caps Lock hotkey)
  * Accessibility      (needed to simulate Cmd+V for paste)

Drag this binary into Input Monitoring AND Accessibility:
  ${PY_APP:-/opt/homebrew/Cellar/python@<version>/.../Python.app}

Then restart Summon:
  launchctl kickstart -k "gui/\$(id -u)/$PLIST_LABEL"

Usage:
  * Double-clap to open a new Claude session.
  * Caps Lock        -> dictate into focused window.
  * Shift+Caps Lock  -> dictate into Claude (auto-launches one if needed).

Desktop/Summon.app -> double-click to revive the menu-bar agent.

DONE

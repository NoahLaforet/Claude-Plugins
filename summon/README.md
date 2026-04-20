# Summon

A macOS menu-bar companion for Claude Code. Two integrated features:

1. **Double-clap launcher** — opens a new iTerm2 Claude Code session when you double-clap.
2. **Dictate** — hold-to-talk voice-to-text powered by whisper.cpp (local, offline).
   - Right Ctrl + `'` → "Dictate Now": transcribe and paste into focused window.
   - Right Ctrl + `;` → "Dictate for Claude": queue transcription, auto-paste next time iTerm2 is frontmost.

Toggle everything from the menu bar; no clap / no hotkey = no mic usage.

## What's in this bundle

```
summon-bundle/
├── summon/                   source code, icons, doc (this folder)
│   ├── summon.py             main menu-bar app + clap detector + dictate integration
│   ├── dictate.py            whisper + hotkey + paste pipeline
│   ├── launch_claude.sh      AppleScript launcher (new iTerm → claude)
│   ├── icons/                radar animation frames + disabled state
│   ├── icon.icns             .app icon
│   ├── models/               whisper ggml model (not in zip — ~1.6GB, download separately)
│   ├── tools/test_dictate_mvp.sh   shell MVP for transcription pipeline
│   ├── gen_icons.py          regenerates menu-bar PNGs
│   ├── gen_preview.py        icon-comparison preview sheet
│   └── gen_app_icon.py       rebuilds icon.icns from a scaled radar
├── Summon.app/               double-click to trigger a new Claude session + ensure menu bar service is alive
└── LaunchAgents/
    └── com.noah.summon.plist auto-start at login
```

`venv/` and `models/` are intentionally **not** included — native deps + 1.6GB model must be pulled per machine.

## Install

```bash
# 1. Copy source into its permanent home
mkdir -p ~/.claude
cp -R summon ~/.claude/summon

# 2. Rebuild the Python venv
python3 -m venv ~/.claude/summon/venv
~/.claude/summon/venv/bin/pip install rumps sounddevice numpy scipy \
  pyobjc-core pyobjc-framework-Cocoa pyobjc-framework-Quartz Pillow

# 3. Install whisper.cpp + model
brew install whisper-cpp sox
mkdir -p ~/.claude/summon/models
curl -L -o ~/.claude/summon/models/ggml-large-v3-turbo.bin \
  https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo.bin

# 4. Drop the .app on Desktop
cp -R Summon.app ~/Desktop/Summon.app

# 5. Install LaunchAgent
cp LaunchAgents/com.noah.summon.plist ~/Library/LaunchAgents/
launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/com.noah.summon.plist
```

The launchd plist hard-codes `/Users/noah/...`. On a different user, open it and swap `noah` for the correct username.

## First-run permissions

Summon needs **three** macOS permissions. All granted under System Settings → Privacy & Security.

1. **Microphone** — prompted on first clap + first dictation.
2. **Input Monitoring** — required for the global dictation hotkey. Add the real Python.app bundle:
   `/opt/homebrew/Cellar/python@3.14/<version>/Frameworks/Python.framework/Versions/3.14/Resources/Python.app`
3. **Accessibility** — required to inject ⌘V when pasting transcriptions. Add the same Python.app.

After granting, restart Summon:
```bash
launchctl kickstart -k "gui/$(id -u)/com.noah.summon"
```

## How to use

### Menu bar states
- **Radar pulses** → clap detector is listening.
- **Radar with a slash** → disabled (mic closed).
- **Title shows `🔴`** → dictation recording in progress.
- **Title shows `📋N`** → N items queued, will paste on next iTerm focus.

### Menu items
- **Enabled** — master toggle for clap detector.
- **Skip if Claude already running** — off by default; when on, a clap is ignored if Claude Code is already alive.
- **Open Claude now** — fires the launcher directly.
- **Dictate ▸** — submenu:
  - **Dictate Now (⌃')** — enable/disable the immediate-paste hotkey.
  - **Dictate for Claude (⌃;)** — enable/disable the queue hotkey.
  - **Queue: N items** — status line; shows "will paste on iTerm focus" when non-empty.
  - **Paste queue into iTerm now** — manual flush.
  - **Clear queue** — drops queued items.
  - **Audio feedback** — toggle Pop/Tink/Glass blips.
  - **Auto-paste (Dictate Now)** — off = copy to clipboard only, no ⌘V injection.
  - **Open transcription log** — opens `logs/transcriptions.jsonl`.
- **View log** — opens `summon.log` in Console.
- **Quit Summon** — fully stops the app.

### Dictate hotkeys
Press and **hold** Right Ctrl + `'` (or `;`), speak, release. Minimum 0.4s recording; anything shorter is dropped as an accidental tap. Cap at 120s per clip. Queue auto-expires after 10 min of inactivity.

## Tuning clap detection

Edit constants at the top of `summon.py`:

```python
PEAK_DB_OVER_BASELINE = 18.0   # peak vs rolling 30s median
SHARPNESS_RISE_DB     = 14.0   # current block vs previous
MIN_ABSOLUTE_PEAK_DB  = -22.0  # absolute loudness floor
DOUBLE_CLAP_MIN_MS    = 150    # min gap between claps
DOUBLE_CLAP_MAX_MS    = 700    # max gap
COOLDOWN_SEC          = 3.0    # lockout after trigger
```

Tail the log while clapping to calibrate:
```bash
tail -f ~/.claude/summon/summon.log
```

## Uninstall

```bash
launchctl bootout "gui/$(id -u)/com.noah.summon"
rm ~/Library/LaunchAgents/com.noah.summon.plist
rm -rf ~/.claude/summon
rm -rf ~/Desktop/Summon.app
```

Then remove Microphone + Input Monitoring + Accessibility entries under System Settings → Privacy & Security.

## Notes

- The orange mic indicator is a macOS privacy feature — it appears whenever the clap detector is listening **or** a dictation is recording. Toggle the detector off (via menu) to free the mic when not in use.
- `Summon.app` on Desktop is a one-click trigger that (a) ensures the menu bar service is running via `launchctl kickstart` and (b) opens a new Claude Code session. Use it to revive the menu bar app after an accidental Quit.
- `launch_claude.sh` auto-sends `1` three seconds after Claude boots to accept `--dangerously-skip-permissions`.
- Any edit to `summon.py` or `dictate.py` is picked up after a kickstart:
  ```bash
  launchctl kickstart -k "gui/$(id -u)/com.noah.summon"
  ```

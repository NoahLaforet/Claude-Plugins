# Summon

![Summon menu-bar states](docs/demo.gif)

A macOS menu-bar companion for Claude Code. Two integrated features:

1. **Double-clap launcher** — opens a new iTerm2 Claude Code session when you double-clap.
2. **Dictate** — tap-to-start / tap-to-stop voice-to-text powered by whisper.cpp (local, offline).
   - **Caps Lock** → "Dictate Now": transcribe and paste into the focused window.
   - **⇧+Caps Lock** → "Dictate for Claude": queue transcription; if Claude is already running, bring iTerm forward and paste; otherwise launch a fresh Claude session and paste once it boots.

Toggle everything from the menu bar; no clap / no hotkey = no mic usage.

## Install

One command:

```bash
./install.sh
```

That script does everything:

- Installs Homebrew deps (`python`, `whisper-cpp`)
- Copies source to `~/.claude/summon/`
- Builds a Python venv from `requirements.txt`
- Downloads the whisper model (~1.6 GB, one-time) to `~/.claude/summon/models/`
- Renders `com.summon.plist.template` with your absolute paths and loads it via `launchctl`
- Creates `~/Desktop/Summon.app` — a one-click revive + launch button

Flags:

- `./install.sh --no-model` — skip the whisper download (you'll need to supply `ggml-large-v3-turbo.bin` yourself before Dictate works)
- `./install.sh --force` — rebuild the venv from scratch

## First-run permissions

Summon needs **three** macOS permissions. All granted under System Settings → Privacy & Security.

1. **Microphone** — prompted on first clap + first dictation.
2. **Input Monitoring** — required for the Caps Lock hotkey. Add the real Python.app bundle (the installer prints the exact path to add at the end of its run, e.g. `/opt/homebrew/Cellar/python@3.14/<version>/Frameworks/Python.framework/Versions/3.14/Resources/Python.app`).
3. **Accessibility** — required to inject ⌘V when pasting transcriptions. Add the same Python.app.

After granting, restart Summon:

```bash
launchctl kickstart -k "gui/$(id -u)/com.summon"
```

## What gets installed

```
~/.claude/summon/
├── summon.py             main menu-bar app + clap detector
├── dictate.py            whisper + hotkey + paste pipeline
├── launch_claude.sh      AppleScript: new iTerm window → claude
├── requirements.txt      pinned-floor Python deps
├── venv/                 built by install.sh
├── icons/                radar / mic / super animation frames + disabled
├── models/               whisper ggml-large-v3-turbo.bin (~1.6 GB)
├── icon.icns             Summon.app icon
└── summon.log            app log (also mirrored to summon.stdout.log / .stderr.log)

~/Library/LaunchAgents/com.summon.plist   launchd agent (auto-start at login)
~/Desktop/Summon.app                      one-click revive + launch
```

## How to use

### Menu bar states

- **Radar pulses** → double-clap detector is listening.
- **Mic pulses** → Dictate is armed (hotkeys live).
- **"Super" rings + sparkle** → both features on.
- **Slashed radar** → everything off.
- **Title shows `🔴`** → dictation is recording.
- **Title shows `📋N`** → N items queued, will paste on iTerm focus.

### Menu items

- **Double-clap launcher** — master toggle for the clap detector.
- **Skip if Claude already running** — off by default; when on, a clap is ignored if Claude Code is already alive.
- **Open Claude now** — fires the launcher directly.
- **Dictate** — master toggle for voice dictation.
- **Dictate settings** — submenu:
  - **Dictate Now (Caps Lock)** — enable/disable the immediate-paste hotkey.
  - **Dictate for Claude (⇧+Caps Lock)** — enable/disable the queue hotkey.
  - **Queue: N items** — status; shows "will paste on iTerm focus" when non-empty.
  - **Paste queue into iTerm now** — manual flush.
  - **Clear queue** — drops queued items.
  - **Audio feedback** — toggle Pop/Tink/Glass blips.
  - **Auto-paste (Dictate Now)** — off = copy to clipboard only, no ⌘V injection.
  - **Open transcription log** — opens `logs/transcriptions.jsonl`.
- **View log** — opens `summon.log` in Console.
- **Quit Summon** — fully stops the app.

### Dictate hotkeys

Caps Lock is a **toggle**: tap to start, tap again to stop and paste. macOS has a built-in ~200 ms debounce on Caps Lock, so give it a firm press rather than a lightning-quick tap. Recordings under 0.4 s are dropped as accidental taps. The cap is 120 s per clip. The Claude queue auto-expires after 10 min of inactivity.

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
launchctl bootout "gui/$(id -u)/com.summon"
rm ~/Library/LaunchAgents/com.summon.plist
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
  launchctl kickstart -k "gui/$(id -u)/com.summon"
  ```

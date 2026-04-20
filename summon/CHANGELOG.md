# Summon Changelog

Reverse-chronological log of changes.

## 2026-04-19 — Summon rename + Dictate feature + separate toggles

- **Renamed** the whole project from **Jarvis → Summon**. Files, folders, LaunchAgent, logs, zip, memory, README all updated. Old LaunchAgent `com.jarvis` unloaded; new `com.summon` loaded under `~/.claude/summon/`.
- **New feature: Dictate** — hold-to-talk voice-to-text via whisper.cpp, integrated as a submenu on the Summon icon (no second app):
  - **Right Ctrl + `'`** → *Dictate Now*: transcribe and paste into the currently focused window.
  - **Right Ctrl + `;`** → *Dictate for Claude*: queue transcription, auto-paste the next time iTerm2 becomes frontmost.
  - Local + offline (ggml-large-v3-turbo, 1.6GB). Audio cues on start/stop/done (toggleable). Auto-paste toggleable. 0.4s minimum clip, 120s cap, 10-min queue TTL.
- **Separate enables** for the two features: Double-clap launcher and Dictate each have their own master toggle. Menu-bar icon animates if *either* is on; shows the disabled state only when *both* are off.
- **New icon sets** for the three states: radar (double-clap only), microphone pulse (dictate only), super-powered combo (both on).
- **Menu labels clarified:** hotkeys show `Right ⌃+'` / `Right ⌃+;` instead of bare `⌃`, so the exact binding is unambiguous.
- **Desktop Summon.app upgraded:** now revives the menu-bar LaunchAgent via `launchctl kickstart` before opening a new Claude session. Previously it only ran the launcher script, so if the menu-bar app had been quit, the icon stayed missing.

## 2026-04-19 — pre-rename (Jarvis era)

- **Renamed** `~/Desktop/Jarvis.app` → `~/Desktop/Summon.app` and rewired it to run `launch_claude.sh` directly (was a no-op when launchd already had jarvis running).
- **Tightened clap sensitivity** in jarvis.py:
  - `SHARPNESS_RISE_DB`: 10 → 14
  - `MIN_ABSOLUTE_PEAK_DB`: −28 → −22
  - Blocks soft false triggers (db ≈ −24, rise ≈ 11–20) while real claps (db −3 to −12, rise 25–55) still fire.
- **Auto-accept permissions prompt** in `launch_claude.sh`: after `claude --dangerously-skip-permissions`, waits 3s and sends `1` to accept the first-run prompt.

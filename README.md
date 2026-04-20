# Claude Code Apps & Plugins

A personal toolkit of macOS customizations for [Claude Code](https://claude.com/claude-code) — the things I built to make my own workflow faster, and because Claude Code was missing the UI polish I wanted. Everything is Python / shell, all drop-in, all independent.

Three plugins, one repo:

| Tool | What it does | Primary files |
|---|---|---|
| **[summon/](summon/)** | Menu-bar companion: opens a new Claude session on **double-clap**, and Caps Lock **voice dictation** to paste transcripts into the focused window (or auto-launch Claude for the queue) | `summon.py`, `dictate.py`, launchd plist, AppleScript launcher |
| **[statusbar/](statusbar/)** | A three-line Claude Code status line showing live context usage, session cost, plan-budget tracking, burn rate, and a spinner that surfaces the active tool | `statusline.py`, `busy_tool.sh`, `settings.example.json` |
| **[usage-today/](usage-today/)** | A `/usage-today` slash command that prints a full-day readout: cost, active time, tokens, cache-reuse %, per-project breakdown, and top tools — aggregated across every session you opened today | `usage_today.py`, `usage-today.md`, `install.sh` |

Each folder has its own `README.md` with install steps, tuning knobs, and screenshots where relevant.

---

## Why this exists

Claude Code is a CLI. It's fast, but out of the box it's a terminal and nothing else — no way to see context usage without asking for it, no way to start a new session without opening a terminal, no way to dictate into it while my hands are on something else. These plugins fix that.

Everything here is deliberately small and deliberately separate. They share a home under `~/.claude/` but none of them depend on each other. Install one, all, or mix-and-match.

---

## Quick install (all three)

```bash
# Clone the repo
git clone https://github.com/NoahLaforet/Claude-Plugins.git ~/Code/claude-plugins
cd ~/Code/claude-plugins

# 1. Summon menu bar app — one-command installer
cd summon
./install.sh         # use --no-model to skip the 1.6 GB whisper download
cd ..

# 2. Status line (see statusbar/README.md for full steps)
cp statusbar/statusline.py ~/.claude/statusline.py
chmod +x ~/.claude/statusline.py
mkdir -p ~/.claude/hooks
cp statusbar/busy_tool.sh ~/.claude/hooks/busy_tool.sh
# Then merge statusbar/settings.example.json into ~/.claude/settings.json

# 3. /usage-today slash command — one-command installer
cd ../usage-today
./install.sh
cd ..
```

What `summon/install.sh` does:

- Installs Homebrew deps (`python`, `whisper-cpp`)
- Builds a Python venv from [`summon/requirements.txt`](summon/requirements.txt)
- Downloads the whisper model (~1.6 GB, one-time)
- Loads the launchd agent and drops a `Summon.app` revive-button on the Desktop
- Prints the exact Python binary to add under Input Monitoring + Accessibility

The statusbar is pure stdlib Python — no `requirements.txt` needed.

Per-plugin READMEs contain full permission, tuning, and troubleshooting docs.

---

## Requirements

- **macOS 13+** (tested on Sequoia / Darwin 25.x). Summon is macOS-only (menu bar, Quartz event taps, `pbcopy`, `osascript`). The statusbar and usage-today are portable — they'll work on any Unix with Python.
- **Python 3.10+** — everything uses stdlib-only code but with modern type syntax.
- **Homebrew** for Summon's `whisper-cpp` dep.
- **Claude Code** — the whole point; grab it at https://claude.com/claude-code.

---

## Layout

```
claude-plugins/
├── README.md                  (this file)
├── LICENSE                    MIT
├── .gitignore                 excludes venv/, models, logs, build artifacts
├── summon/                    menu bar app — double-clap + dictate
├── statusbar/                 Claude Code three-line status line
└── usage-today/               /usage-today slash command — full-day stats
```

---

## Hardcoded paths

The Summon and usage-today installers handle paths automatically. Only
`statusbar/settings.example.json` has a `/Users/YOURNAME/` placeholder that
needs swapping for your home path:

```bash
sed -i '' "s|/Users/YOURNAME|$HOME|g" ~/.claude/settings.json
```

Do that *after* you've merged the example into your own `settings.json` — see
`statusbar/README.md` for the full walkthrough.

---

## License

MIT. See [LICENSE](LICENSE). Do whatever you want with it.

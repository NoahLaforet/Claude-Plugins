# Claude Code Apps & Plugins

A personal toolkit of macOS customizations for [Claude Code](https://claude.com/claude-code) — the things I built to make my own workflow faster, and because Claude Code was missing the UI polish I wanted. Everything is Python / shell / HTML, all drop-in, all independent.

Four tools, one repo:

| Tool | What it does | Primary files |
|---|---|---|
| **[summon/](summon/)** | Menu-bar companion: opens a new Claude session on **double-clap**, and hold-to-talk **voice dictation** to paste transcripts into the focused window (or queue for Claude) | `summon.py`, `dictate.py`, launchd plist, AppleScript launcher |
| **[statusbar/](statusbar/)** | A three-line Claude Code status line showing live context usage, session cost, plan-budget tracking, burn rate, and a spinner that surfaces the active tool | `statusline.py`, `busy_tool.sh`, `settings.example.json` |
| **[migration/](migration/)** | One-shot Mac-to-Mac migration kit — snapshots everything Apple's Migration Assistant misses (Brewfile, dotfiles, LaunchAgents, toolchains, dirty git repos) and rebuilds it on the new machine | `capture.sh`, `restore.sh`, `RESTORE.md` |
| **[terminal-guide/](terminal-guide/)** | Single-page HTML cheat sheet for shell / git / SSH / tmux | `noahs_terminal_guide.html` |

Each folder has its own `README.md` with install steps, tuning knobs, and screenshots where relevant. Pre-built zips are in `dist/` for drag-and-drop installs.

---

## Why this exists

Claude Code is a CLI. It's fast, but out of the box it's a terminal and nothing else — no way to see context usage without asking for it, no way to start a new session without opening a terminal, no way to dictate into it while my hands are on something else. These plugins fix that.

Everything here is deliberately small and deliberately separate. They share a home under `~/.claude/` but none of them depend on each other. Install one, all, or mix-and-match.

---

## Quick install (all four)

```bash
# Clone the repo
git clone <this-repo-url> ~/Code/claude-plugins
cd ~/Code/claude-plugins

# 1. Status line (see statusbar/README.md for full steps)
cp statusbar/statusline.py ~/.claude/statusline.py
chmod +x ~/.claude/statusline.py
mkdir -p ~/.claude/hooks
cp statusbar/busy_tool.sh ~/.claude/hooks/busy_tool.sh
# Then merge statusbar/settings.example.json into ~/.claude/settings.json

# 2. Summon menu bar app (see summon/README.md for full steps)
mkdir -p ~/.claude/summon
cp -R summon/* ~/.claude/summon/
python3 -m venv ~/.claude/summon/venv
~/.claude/summon/venv/bin/pip install \
  rumps sounddevice numpy scipy \
  pyobjc-core pyobjc-framework-Cocoa pyobjc-framework-Quartz Pillow
brew install whisper-cpp sox
mkdir -p ~/.claude/summon/models
curl -L -o ~/.claude/summon/models/ggml-large-v3-turbo.bin \
  https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo.bin

# 3. Migration kit — nothing to install; copy the folder to ~/Desktop/migration
#    and run capture.sh on the old Mac, restore.sh on the new one.
cp -R migration ~/Desktop/migration

# 4. Terminal guide — open the HTML in any browser
open terminal-guide/noahs_terminal_guide.html
```

Per-project READMEs contain full permission, tuning, and troubleshooting docs.

---

## Requirements

- **macOS 13+** (tested on Sequoia / Darwin 25.x). Most tools are macOS-specific (menu bar, Quartz event taps, `pbcopy`, `osascript`). The status line is the only portable piece.
- **Python 3.10+** for statusline.py and Summon.
- **Homebrew** for Summon's whisper.cpp + sox deps.
- **Claude Code** — the whole point; grab it at https://claude.com/claude-code.

---

## Layout

```
claude-plugins/
├── README.md                  (this file)
├── LICENSE                    MIT
├── .gitignore                 excludes venv/, models, logs, migration/snapshot
├── dist/                      pre-built zips for drag-install
│   ├── summon.zip
│   ├── statusbar.zip
│   └── Summon.app.zip         desktop trigger that revives menu-bar + opens Claude
├── summon/                    menu bar app — double-clap + dictate
├── statusbar/                 Claude Code three-line status line
├── migration/                 Mac-to-Mac migration scripts
└── terminal-guide/            static HTML cheat sheet
```

---

## Hardcoded paths — important

Several files (LaunchAgent plist, desktop launcher shell script, statusline cost-ledger) reference `/Users/noah/...` directly. On a fresh machine, sed-replace the username:

```bash
find . -type f \( -name '*.plist' -o -name '*.sh' -o -name '*.json' -o -name '*.py' \) \
  -exec sed -i '' "s|/Users/noah|$HOME|g" {} +
```

Or just open the files flagged in each subproject README and swap it by hand — there are ~5 total.

---

## License

MIT. See [LICENSE](LICENSE). Do whatever you want with it.

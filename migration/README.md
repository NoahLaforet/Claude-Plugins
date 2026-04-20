# Migration kit — read me first

Everything you need to move from this MacBook Pro to a new Mac without losing any terminal, dev, or automation setup.

## What's in this folder

| File | Purpose |
|---|---|
| **README.md** | This file — start here |
| **RESTORE.md** | Full step-by-step plan (phases 1 → 3), detailed checklist |
| **capture.sh** | Run on the OLD laptop. Snapshots every dev/automation thing Migration Assistant might miss |
| **restore.sh** | Run on the NEW laptop (after Migration Assistant). Rebuilds everything from the snapshot |
| **snapshot/** | Created by `capture.sh`. The actual saved state (Brewfile, dotfiles, configs, etc.) |

---

## TL;DR — three things to remember

1. **Run `./capture.sh` the night before you migrate.** Idempotent — safe to run any time, overwrites the snapshot.
2. **On new-laptop day**: run Apple Migration Assistant first (Thunderbolt cable, Mac-to-Mac is fastest). It copies this entire folder along with everything else.
3. **After Migration Assistant finishes**: open Claude Code in this folder and say *"Run restore.sh and walk me through the re-auth checklist."*

That's it. The rest of this file is the detail under those three steps.

---

## How to use it

### On the OLD laptop (now, and again right before migrating)

```bash
cd ~/Desktop/migration
./capture.sh
```

Takes ~1 min. Creates / refreshes `snapshot/` with:

- Every Homebrew formula + cask (→ `Brewfile`)
- Your `~/.claude` config, MCPs, memory, CLAUDE.md (→ `claude.tar.gz`)
- Your custom LaunchAgents like `com.noah.claude-brain.sync` (→ `launchagents/`)
- All VS Code extensions (→ `vscode_extensions.txt`)
- Dotfiles: `.zshrc`, `.zprofile`, `.gitconfig`, `.config/` (→ `dotfiles/`)
- SSH `config` + `known_hosts` (private keys listed but NOT auto-copied)
- pyenv Python versions, rustup toolchains, gems, pipx (→ `toolchains.txt`)
- Every git repo under `~/Desktop/Github`, etc. flagged `[DIRTY]` / `[UNPUSHED]` (→ `git_repos.txt`)
- CLI auth status, crontab, macOS defaults, installed apps inventory

**Before you actually migrate:**
1. Re-run `./capture.sh` for a fresh snapshot.
2. Open `snapshot/git_repos.txt` — commit + push anything `[DIRTY]` or `[UNPUSHED]`.
3. Open `snapshot/ssh/PRIVATE_KEYS_TO_COPY.txt` — plan a secure transfer for those private keys (Migration Assistant will copy them too, but good to know what's there).
4. Take a full **Time Machine backup** to an external SSD as a safety net.

### On the NEW laptop

**Step 1 — Apple Migration Assistant** (Setup Assistant runs it on first boot, or Applications → Utilities → Migration Assistant):

- Choose **Mac → Mac over Thunderbolt 4 cable** (30-60 min for ~600GB).
- Fallback: restore from the Time Machine SSD.
- Select everything: Users + Applications + Settings + Other files and folders.

Migration Assistant copies this whole `~/Desktop/migration/` folder over.

**Step 2 — restore:**

```bash
cd ~/Desktop/migration
./restore.sh
```

It will:
- Install Xcode Command Line Tools (if missing)
- Reinstall Homebrew from the Brewfile
- Rebuild pyenv Pythons + rustup toolchains
- Reinstall all VS Code extensions
- Load your custom LaunchAgents
- Fix SSH key permissions
- Print a re-auth checklist for OAuth / accounts

**Step 3 — re-auth pass.** The script prints a checklist: 1Password, `gh auth login`, gcloud, Claude Code MCPs (Gmail, Calendar, Drive, Obsidian, claude-in-chrome), Chrome sign-in, etc. These need your hands — script can't do them.

---

## The easy mode: hand it to Claude

On new-laptop day, open Claude Code in this folder and say exactly this:

> **"I just finished Apple Migration Assistant. Run `./restore.sh` and walk me through the re-auth checklist. Pause on anything that needs my password or a browser sign-in."**

Claude will execute the script, catch and explain any errors, and stop on each manual item so you can fill them in.

---

## What's already handled vs. what needs your hands

| Automated by the scripts | Needs you (OAuth / passwords) |
|---|---|
| Homebrew + all packages | 1Password sign-in |
| VS Code extensions | GitHub CLI (`gh auth login`) |
| pyenv / rustup toolchains | Google Cloud, AWS |
| LaunchAgents | Claude Code MCPs re-auth on first use |
| Dotfiles (via Migration Assistant) | Chrome Google sign-in |
| `~/.claude` config | Docker Desktop sign-in |
| SSH config + permissions | Zoom / Discord / Spotify |
| git repo inventory | Apple ID / iCloud / Messages |

---

## If something goes wrong

- **Brewfile has a package that fails to install** → note it, continue, install manually after. Usually architecture-specific or renamed formulas.
- **LaunchAgent fails to load** → check absolute paths inside the `.plist` file; user home is the same, so it should work, but double-check any hardcoded paths outside `$HOME`.
- **`code` command not found** → open VS Code → Cmd-Shift-P → "Shell Command: Install code in PATH" → re-run `restore.sh`.
- **pyenv install fails** → usually missing build deps; `brew install openssl readline sqlite3 xz zlib tcl-tk`, then retry.
- **Claude Code MCPs can't auth** → each MCP (Gmail, GCal, GDrive, Obsidian, claude-in-chrome) has its own OAuth flow that triggers on first use in a new Claude Code session.

---

## After 2 weeks on the new laptop

If everything's working and you're confident:
1. On old laptop: System Settings → General → Transfer or Reset → **Erase All Content and Settings**.
2. Before that: sign out of iCloud, Apple ID, Messages, App Store. Turn off Find My Mac.
3. Keep this `migration/` folder on the new laptop for reference — it's also a nice reproducible record of your setup.

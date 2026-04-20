# Migration plan — old MacBook Pro M1 Max → new MacBook Pro

Run this plan in three phases. The scripts do the heavy lifting; this doc is the human checklist.

---

## Phase 1 — On the OLD laptop (do BEFORE the new one arrives)

### 1.1 Initial snapshot (any time)
```bash
cd ~/Desktop/migration
./capture.sh
```
Creates `~/Desktop/migration/snapshot/` with everything Migration Assistant might miss.

### 1.2 Review the snapshot
- `snapshot/git_repos.txt` — push anything marked `[DIRTY]` or `[UNPUSHED]`.
- `snapshot/ssh/PRIVATE_KEYS_TO_COPY.txt` — these keys will NOT be auto-copied; plan a secure transfer (encrypted USB, or let Migration Assistant handle them via full-user copy).
- `snapshot/gpg/EXPORT_ME.sh` — run manually if you use GPG (interactive passphrase prompts).

### 1.3 Housekeeping while you have time
- [ ] Commit + push every WIP git branch.
- [ ] Push `Claude Brain` vault to a git remote (belt-and-suspenders — Migration Assistant will also copy it).
- [ ] Turn on **VS Code Settings Sync** (Cmd-Shift-P → "Settings Sync: Turn On") — picks account: GitHub.
- [ ] Confirm Chrome / Edge signed into Google account (sync enabled).
- [ ] Confirm 1Password account is signed in and vaults show as "synced."
- [ ] Deauthorize any seat-licensed software (Adobe, JetBrains, etc. if used).
- [ ] Note any app with a hardware-locked license (Logic, Final Cut usually fine; Pro Tools / KLayout licenses may need re-issuing).

### 1.4 Final snapshot — the night before you migrate
```bash
cd ~/Desktop/migration && ./capture.sh
```
Then take a **full Time Machine backup** to an external SSD. This is your ultimate fallback.

---

## Phase 2 — New laptop arrives

### 2.1 Initial boot
- Sign into Apple ID during setup.
- When prompted, run **Migration Assistant**. Best method:
  - **Mac-to-Mac over Thunderbolt 4 cable** (fastest; ~30-60 min for ~600GB).
  - Fallback: restore from Time Machine SSD.
- Select: **Users + Applications + Settings + Other files and folders**. All of them.

Migration Assistant will copy `/Users/noah/*`, including `~/Desktop/migration/`, so the snapshot comes with you.

### 2.2 After MA finishes — run the restore
```bash
cd ~/Desktop/migration
./restore.sh
```
This handles:
- Xcode Command Line Tools
- Homebrew reinstall + `brew bundle` from Brewfile
- pyenv Python versions
- rustup toolchains
- VS Code extensions
- Loading your custom LaunchAgents (including `com.noah.claude-brain.sync`)
- SSH permission fixes
- Prints a re-auth checklist

### 2.3 Re-auth pass (script prints the checklist — work through it)
The OAuth / account logins can't be automated. Claude-managed MCPs (Gmail, Google Calendar, Google Drive, Obsidian, claude-in-chrome) will each prompt for OAuth on first use inside Claude Code.

### 2.4 Smoke tests
- [ ] Open Claude Code → run `claude` → confirm MCPs reconnect.
- [ ] Open Obsidian → load `Claude Brain` vault → confirm Dataview queries still render.
- [ ] `cd` into one git repo → `git fetch` works (SSH auth OK).
- [ ] Open KLayout, a Verilog project, verify OpenROAD flow runs.
- [ ] `launchctl list | grep claude-brain` — confirms the sync agent is alive.
- [ ] Chrome extensions present; 1Password browser extension signed in.

---

## Phase 3 — Wind down the old laptop (do after 2 weeks of new-laptop confidence)

- [ ] Copy anything from `~/Desktop/migration/snapshot/` that you haven't verified on the new machine.
- [ ] Sign out of iCloud, Apple ID, Messages, App Store, Music.
- [ ] Turn off Find My Mac.
- [ ] System Settings → General → Transfer or Reset → **Erase All Content and Settings**.
- [ ] Sell, trade in, or keep as backup.

---

## What to hand Claude on new-laptop day

Open Claude Code in `~/Desktop/migration/` and say:

> "I just finished Apple Migration Assistant on my new MacBook. Run `./restore.sh` and walk me through the re-auth checklist."

Claude will execute the script, report each step's outcome, and pause on the manual items (OAuth logins, password prompts) so you can fill them in.

---

## Known quirks / gotchas

- **Homebrew on new macOS versions**: sometimes copied binaries don't run cleanly across OS majors. `restore.sh` reinstalls from Brewfile rather than trusting the copied `/opt/homebrew`.
- **pyenv Pythons**: the compiled CPython binaries are architecture + macOS SDK dependent. `restore.sh` rebuilds them.
- **Docker Desktop**: often cleaner to download fresh than to trust the migrated version.
- **LaunchAgents with absolute paths**: if `com.noah.claude-brain.sync.plist` references paths that changed (unlikely since user dir is identical), edit the plist before `launchctl bootstrap`.
- **Keychain**: Migration Assistant copies the login keychain. Safari passwords, wifi, and app credentials come across. Some apps (Slack desktop, occasionally) still prompt for re-auth.
- **SSH agent / 1Password SSH agent**: if you use 1Password's SSH agent, re-enable it in 1Password → Settings → Developer after signing in.

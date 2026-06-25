# Set up this Claude Code config (for Claude to follow)

If someone hands you (Claude) this repository and asks you to set it up, follow these steps.
The goal is a working `~/.claude` configuration with nothing private hardcoded.

## 1. Gather the private values

Ask the user for these (do not guess, do not invent). Home directory and username come from
`$HOME`, never ask for those.

- Full name (for commit author and CLAUDE.md)
- Git email
- GitHub username
- Obsidian vault path for the `second-brain` skill (optional; skip if they do not use one)

## 2. Run the installer

The simplest path is the interactive installer, which prompts for the same values:

```bash
bash setup/install.sh
```

If you are running non-interactively, render the templates yourself instead: copy
`setup/hooks/`, `setup/skills/`, and `setup/claude-audit/` into `~/.claude/`, then substitute
`{{FULL_NAME}}`, `{{EMAIL}}`, `{{GITHUB_USER}}`, `{{VAULT_PATH}}`, and `__HOME__` in
`CLAUDE.example.md`, `settings.example.json`, the second-brain skill, and the LaunchAgent plist.
Never overwrite an existing `~/.claude/settings.json` or `~/.claude/CLAUDE.md`; write a `.new`
file and tell the user to merge.

## 3. Wire up the rest

- Install the other components from the top-level README (summon, statusbar, usage-today, claude-brain).
- Point the user at `setup/SKILLS.md` for the third-party skills and MCP servers (install from source; never commit keys).
- Load the weekly auto-audit if the installer could not: `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.claude.weekly-audit.plist`.

## 4. Verify

- `python3 ~/.claude/claude-audit/weekly_audit.py --dry-run` should run and write `reports/latest.md`.
- Confirm `~/.claude/CLAUDE.md` has the user's real name and no leftover `{{placeholders}}`.
- Confirm no secret or personal path was written into any file that is tracked by git.

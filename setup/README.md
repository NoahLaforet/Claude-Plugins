# Portable Claude Code configuration (setup/)

This folder turns the repo into a setup anyone can clone and run, including you on a new
machine. Nothing private is hardcoded. The installer prompts for the few personal values it
needs (your name, email, GitHub user, and an optional vault path); your home directory and
username come from `$HOME`.

## Two ways to install

**Interactive installer** (technical users):

```bash
bash setup/install.sh
```

**Hand it to Claude** (anyone): open the repo with Claude Code and say "set this up for me."
Claude follows [SETUP.md](SETUP.md), asks you for the private values, and does the rest.

## What it installs into ~/.claude

| Item | Destination |
|---|---|
| `hooks/skill_router.py` | `~/.claude/hooks/` (suggests skills on high-precision prompt signals) |
| `skills/second-brain` | `~/.claude/skills/` (search an Obsidian vault before historical questions) |
| `skills/claude-audit` | `~/.claude/skills/` (deep on-demand setup audit, `/claude-audit`) |
| `claude-audit/` | `~/.claude/claude-audit/` + a weekly LaunchAgent that lints the setup and notifies |
| `CLAUDE.example.md` | `~/.claude/CLAUDE.md` (templated; never overwrites an existing one) |
| `settings.example.json` | `~/.claude/settings.json` (templated; never overwrites an existing one) |

## What it does NOT do

- It does not commit or read any secret. The example settings ship `deny` rules for `.env`
  and credential files, and the repo has a gitleaks pre-commit hook plus a guard that blocks
  any private path from being staged (see [../SANITIZATION.md](../SANITIZATION.md)).
- It does not re-publish third-party skills. See [SKILLS.md](SKILLS.md) to install those from
  their own sources.

## The weekly auto-audit

`claude-audit/weekly_audit.py` runs every Sunday via launchd, auto-detects your memory
directory, fixes the safe things (broken wikilinks), and flags the rest (oversized MEMORY.md,
naming duplicates, stale entries, config drift) with a macOS notification. Reports land in
`~/.claude/claude-audit/reports/`. This is what keeps long-running setups from going stale.

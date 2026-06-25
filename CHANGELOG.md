# Changelog

All notable changes to this repo. Dates are when the work landed on `main`. This is a
personal toolkit, so entries are grouped by date rather than by semantic version.

## 2026-06-24

### Added
- `setup/`, a portable `~/.claude` configuration anyone can clone and run. `setup/install.sh`
  prompts for name, email, GitHub user, and an optional vault path (home and username are
  auto-detected), then templates `settings.example.json` and `CLAUDE.example.md` into place.
- `setup/SETUP.md` so you can hand the repo to Claude and have it do the install for you.
- A `second-brain` skill (search an Obsidian vault before historical questions) and a
  `claude-audit` skill (deep setup cleanup), plus a weekly auto-audit (`setup/claude-audit/`)
  that lints the setup for buildup and notifies via launchd.
- `setup/SKILLS.md`, a manifest of third-party skills listed by source rather than vendored.
- A top-level one-shot `install.sh` with per-component flags (`--all`, `--summon`, and so on).
- Privacy enforcement: a gitleaks pre-commit hook, a GitHub Action, and a `precommit-guard.sh`
  that blocks the private vault, real home paths, emails, keys, and Tailscale IPs from a commit.
- `SANITIZATION.md`, the pre-publish checklist that keeps the repo clean.

### Changed
- Rewrote the top-level README to document `claude-brain` as the fourth component and fixed a
  broken `cd` in the quick-install block.
- Hardened `.gitignore` to exclude Claude Code local and state files by name.

## 2026-05-28

### Added
- Effort-level support in the status line: it reads the live effort and shows `max`.
- Summon launches Claude at max effort.

## 2026-05-25

### Added
- `claude-brain`, a self-hosted kit that extracts and classifies Claude chat history into an
  Obsidian knowledge vault, then lets Claude Code cite past conversations through the Obsidian MCP.

## 2026-05-04

### Added
- AFK-aware active time tracking in the status line, plus a "time week" column.

## 2026-04-19

### Added
- Initial release: `summon` (menu-bar double-clap launcher and Caps Lock dictation),
  `statusbar` (three-line context, cost, and burn-rate status line), and `usage-today`
  (the `/usage-today` full-day stats slash command).
- One-command installers for summon and usage-today.

### Security
- Scoped the repo to public tooling only and removed personal content. Genericized the example
  usage figures in the status line README.

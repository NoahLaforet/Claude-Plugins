---
name: claude-audit
description: Audit and clean up Noah's whole Claude Code setup (memory files, MEMORY.md index, the two CLAUDE.md files, skills, hooks, settings, and the public Claude-Plugins repo). Use when Noah says /claude-audit, "audit my setup", "clean up my claude", "my sessions feel dumb", or when the weekly auto-audit flags issues that need a judgment pass. Runs the fast deterministic linter, then a deeper LLM pass for overlaps, contradictions, staleness, and index bloat.
---

# Claude setup audit

Keeps Noah's Claude Code setup lean so sessions stay sharp. There are two layers: a
fast deterministic linter that also runs automatically every week, and this deeper
on-demand pass for the things only judgment can catch.

## Step 1: run the fast linter first

```bash
python3 ~/.claude/claude-audit/weekly_audit.py --dry-run   # report only
python3 ~/.claude/claude-audit/weekly_audit.py             # also applies safe wikilink fixes
```

It checks: MEMORY.md size against the 25 KB / 200-line session-load ceiling, the 1:1
match between MEMORY.md bullets and files on disk, broken wikilinks (auto-fixes the
underscore-normalizable ones), naming duplicates (collapsed-letter collisions like
`cataanbot`/`catanbot`), stale dated memories (old dates plus deadline language), em-dashes
in the CLAUDE.md files, and settings.json health. Read the report at
`~/.claude/claude-audit/reports/latest.md`.

The weekly launchd job (`com.claude.weekly-audit`, Sundays 10:00) runs this same linter,
applies the safe fixes, and notifies Noah. This skill is the deeper follow-up when it flags
something or when Noah asks directly.

## Step 2: deep pass (what the linter cannot judge)

Spawn parallel read-only agents (or a Workflow) over these domains, then fix in three
buckets: safe-auto (apply now), propose-first (ask Noah), sensitive (privacy/outward, explicit go).

- **Memory bodies**: contradictions between files, superseded feedback, overlapping
  clusters that fragment (for example the writing-voice files), oversized files (>10 KB)
  that should split. Archive elapsed dated files by MOVING them to
  `~/.claude/projects/-Users-noah/memory/archive/` (never hard-delete), update
  `archive/INDEX.md`, and keep MEMORY.md 1:1 with the remaining active files.
- **Core CLAUDE.md** (`~/.claude/CLAUDE.md` global and `~/CLAUDE.md` project): dead path or
  file references, bloat, anything that should be a skill or rule instead of always loaded.
- **Skills** (`~/.claude/skills/`): description overlaps that cause mis-routing (fix with
  sharper, mutually-exclusive descriptions, not deletions), broken internal references,
  duplicates of built-in skills.
- **Hooks + settings**: referenced scripts that no longer exist, fragile hard-coded paths,
  duplicate keys, stale permissions.
- **Public repo** (`~/Desktop/Github/Claude Plugins`): README accuracy, and run the privacy
  guard before any commit: `bash scripts/precommit-guard.sh` plus `gitleaks detect` if installed.

## Rules

- Memory archival and renames are non-destructive: move, do not delete; keep `archive/INDEX.md` current.
- After any memory change, re-verify MEMORY.md is 1:1 with the files and has zero broken wikilinks
  (the linter does both; re-run it).
- Never commit anything private to the public repo (the vault, personal home paths, API keys, private IPs).
- Honor the no-em-dash and no-Claude-in-git rules in everything written.
- The full audit history and reports live in `~/.claude/claude-audit/reports/`.

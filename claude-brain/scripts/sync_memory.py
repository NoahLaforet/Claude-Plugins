#!/usr/bin/env python3
"""Mirror ~/.claude/projects/<project-slug>/memory/ into 03 - Memories/.

The vault's 03 - Memories/ folder holds snapshots from the claude.ai
export pipeline. This script keeps the vault copy fresh so Obsidian can
wikilink to memory files like any other note.

Behavior:
- Source files are copied 1:1 with their original markdown content.
- A short header is prepended noting auto-sync and the source path.
- Filenames are preserved (e.g. user_work_style.md).
- MEMORY.md is copied as-is (it's the index).
- Files removed from the source are deleted from the destination on sync.
- Older snapshot files (Conversations memory.md, Project memory - *) are
  preserved untouched.

Configuration:
  Set CLAUDE_BRAIN_MEMORY_SOURCE env var to override the default source path.
  Default: ~/.claude/projects/ (auto-detects the most-recently-modified
  memory/ folder if multiple project slugs exist).

Usage:
    python3 scripts/sync_memory.py
"""
from __future__ import annotations
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from _vault_path import VAULT  # noqa

DEST = VAULT / '03 - Memories'
LEGACY_PATTERNS = ('Conversations memory.md', 'Project memory - ')

HEADER_TPL = (
    '> [!info] Auto-synced from Claude Code auto-memory\n'
    '> Edits should go to the source -- this copy is rewritten on every sync.\n'
    '> Source: `{src}`\n\n'
)


def find_source() -> Path | None:
    """Find the memory directory to sync from."""
    env = os.environ.get('CLAUDE_BRAIN_MEMORY_SOURCE', '').strip()
    if env:
        p = Path(env).expanduser()
        return p if p.exists() else None

    # Auto-detect: find all memory/ directories under ~/.claude/projects/
    projects_dir = Path.home() / '.claude' / 'projects'
    if not projects_dir.exists():
        return None

    candidates = sorted(projects_dir.glob('*/memory'), key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def is_legacy(name: str) -> bool:
    return any(name == p or name.startswith(p) for p in LEGACY_PATTERNS)


def sync() -> None:
    source = find_source()
    if source is None:
        print('No memory source found. Set CLAUDE_BRAIN_MEMORY_SOURCE or use Claude Code.')
        return

    DEST.mkdir(parents=True, exist_ok=True)
    src_files = {p.name: p for p in source.glob('*.md')}

    written = 0
    for name, src in src_files.items():
        body = src.read_text(encoding='utf-8')
        header = HEADER_TPL.format(src=src)
        # Don't double-prepend the header on subsequent runs
        if body.startswith('> [!info] Auto-synced'):
            body = body.split('\n\n', 1)[-1] if '\n\n' in body else body
        out = header + body
        (DEST / name).write_text(out, encoding='utf-8')
        written += 1

    # Drop synced files no longer in source (keep legacy snapshots)
    removed = 0
    for p in DEST.glob('*.md'):
        if is_legacy(p.name) or p.name.startswith('_'):
            continue
        if p.name not in src_files:
            p.unlink()
            removed += 1

    print(f'Synced {written} memory file(s) from {source}; removed {removed} stale.')


if __name__ == '__main__':
    sync()

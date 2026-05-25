#!/usr/bin/env python3
"""Heuristic classifier for pending Claude Code chats.

Runs at Stop-hook time when the live model is no longer available. Uses
keyword + cwd rules to assign a best-effort cluster/tags/entities so newly
ingested chats stop sitting with empty frontmatter. SessionStart on the
next session can upgrade these via classify_pending.py if a human-quality
read is needed.

Idempotent -- only touches chats with no cluster: line in their frontmatter.
Exits 0 on no-op.

Usage:
    python3 scripts/auto_classify.py            # apply heuristics
    python3 scripts/auto_classify.py --dry-run  # report only

To customize: edit the RULES list below. Each rule matches on either
cwd_contains (substring of the working directory path) or kw_any (keywords
in title + cwd + first turns). First matching rule wins.
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _vault_path import VAULT  # noqa
from classify_pending import _fm_and_body, _get, _first_turns  # noqa
from sync import patch_frontmatter, update_meta_files  # noqa

CHATS = VAULT / '01 - Chats'


def find_pending() -> list[dict]:
    """Find every chat with no cluster line (regardless of source)."""
    out = []
    for p in sorted(CHATS.glob('*.md')):
        text = p.read_text(encoding='utf-8', errors='replace')
        if not text.startswith('---'):
            continue
        fm, body = _fm_and_body(text)
        if re.search(r'(?m)^cluster: ".+"', fm):
            continue
        out.append({
            'uuid': _get(fm, 'uuid'),
            'filename': p.name,
            'title': _get(fm, 'title').strip('"'),
            'cwd': _get(fm, 'cwd').strip('"'),
            'first_turns': _first_turns(body),
        })
    return out


# Order matters -- first matching rule wins.
# Customize this list for your own projects and interests.
# Each rule has at most one of: cwd_contains, kw_any
# and requires: cluster, tags, (optional) entities
RULES: list[dict] = [
    # keyword: VLSI / chip design
    {'kw_any': ['sky130', 'openroad', 'tinytapeout', 'vlsi', 'magic vlsi',
                'logical effort', 'spice'],
     'cluster': 'VLSI & Digital Circuits',
     'tags': ['domain/vlsi', 'tool/sky130']},

    # keyword: job search / career
    {'kw_any': ['cover letter', 'resume', 'linkedin', 'job application',
                'recruiter'],
     'cluster': 'Job Search & Career',
     'tags': ['type/writing']},

    # keyword: gaming / personal
    {'kw_any': ['valorant', 'fortnite', 'minecraft', 'spotify',
                'gaming', 'soccer', 'golf'],
     'cluster': 'Personal & Entertainment',
     'tags': ['topic/personal']},

    # keyword: web dev
    {'kw_any': ['next.js', 'nextjs', 'react component', 'tailwind',
                'web portal', 'fastapi', 'frontend', 'backend'],
     'cluster': 'Web Development',
     'tags': ['domain/webdev']},

    # keyword: Claude / AI tooling
    {'kw_any': ['claude code', 'status bar', 'session limit', 'hook',
                'mcp server', 'slash command', 'skill', 'obsidian',
                'second brain', 'memory file', 'plugin'],
     'cluster': 'Claude & AI Tooling',
     'tags': ['tool/claude-code']},

    # keyword: writing / research papers
    {'kw_any': ['research paper', 'literature review', 'essay', 'manuscript'],
     'cluster': 'Writing & Research',
     'tags': ['type/writing', 'topic/research']},

    # keyword: automation / scripts
    {'kw_any': ['automation', 'applescript', 'google drive', 'tailscale',
                'ssh', 'workflow', 'cron', 'launchd'],
     'cluster': 'Productivity & Automation',
     'tags': ['topic/programming']},
]


def classify_one(chat: dict) -> dict:
    haystack = ' '.join([
        chat.get('title', ''),
        chat.get('cwd', ''),
        chat.get('first_turns', ''),
    ]).lower()
    cwd = chat.get('cwd', '').lower()

    for rule in RULES:
        if 'cwd_contains' in rule and rule['cwd_contains'].lower() in cwd:
            return _make(rule, chat)
        if 'kw_any' in rule and any(k in haystack for k in rule['kw_any']):
            return _make(rule, chat)

    # Empty / trivial chats -> archive
    body = chat.get('first_turns', '').strip()
    if len(body) < 60:
        return {
            'uuid': chat['uuid'],
            'cluster': 'Archive & Unsorted',
            'themes': ['Trivial/empty chat'],
            'tags': ['type/archived', 'status/archived'],
            'entities': [],
        }

    # Fallback: unsorted, will be flagged at next SessionStart
    return {
        'uuid': chat['uuid'],
        'cluster': 'Archive & Unsorted',
        'themes': [],
        'tags': ['status/imported'],
        'entities': [],
    }


def _make(rule: dict, chat: dict) -> dict:
    return {
        'uuid': chat['uuid'],
        'cluster': rule['cluster'],
        'themes': [],
        'tags': rule.get('tags', []) + ['status/auto-classified'],
        'entities': rule.get('entities', []),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    pending = find_pending()
    if not pending:
        print('No pending chats.')
        return 0

    classifications = [classify_one(p) for p in pending]

    if args.dry_run:
        for c, p in zip(classifications, pending):
            print(f"  {c['cluster']:24s} {p['filename']}")
        return 0

    by_uuid = {p['uuid']: p for p in pending}
    meta_entries = []
    applied = 0
    for cls in classifications:
        chat = by_uuid[cls['uuid']]
        fpath = CHATS / chat['filename']
        patch_frontmatter(fpath, {
            'cluster': cls['cluster'],
            'themes': cls['themes'],
            'tags': cls['tags'],
            'entities': cls['entities'],
        })
        text = fpath.read_text(encoding='utf-8')
        text = re.sub(r'(?m)^status: imported$',
                      'status: auto-classified', text)
        fpath.write_text(text, encoding='utf-8')
        meta_entries.append({
            'uuid': cls['uuid'], 'filename': chat['filename'], 'summary': '',
            'themes': cls['themes'], 'tags': cls['tags'],
            'entities': cls['entities'], 'cluster': cls['cluster'],
        })
        applied += 1
        print(f"  ok {cls['cluster']:24s} {chat['filename']}")

    if meta_entries:
        update_meta_files(meta_entries)
    print(f'\nAuto-classified {applied} chat(s).')
    return 0


if __name__ == '__main__':
    sys.exit(main())

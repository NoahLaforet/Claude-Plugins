#!/usr/bin/env python3
"""Classify pending Claude Code chats via the current Claude Code session.

Two modes:

    python3 scripts/classify_pending.py --list
        Print JSON describing every unclassified claude-code chat, plus the
        existing cluster list and tag families. The LLM reads this and
        produces a classifications JSON file.

    python3 scripts/classify_pending.py --apply path/to/classifications.json
        Apply the classifications: patch frontmatter, update
        chat_metadata.json and clusters.json.

The apply-input schema is a JSON array of objects:
    {
      "uuid": "<chat uuid>",
      "cluster": "<one existing cluster name or 'Miscellaneous'>",
      "themes": ["..."],
      "tags":   ["type/...", "topic/...", "tool/...", ...],
      "entities": ["..."]
    }

No ANTHROPIC_API_KEY required -- the Claude Code session *is* the classifier.
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _vault_path import VAULT  # noqa
from sync import patch_frontmatter, update_meta_files, CLUSTERS  # noqa

CHATS = VAULT / '01 - Chats'


def _fm_and_body(text: str) -> tuple[str, str]:
    end = text.find('\n---', 3)
    return text[3:end], text[end + 4:]


def _get(fm: str, field: str) -> str:
    m = re.search(rf'(?m)^{field}:\s*(.*)$', fm)
    return (m.group(1) if m else '').strip()


def _first_turns(body: str, max_turns: int = 4, per_turn: int = 400) -> str:
    parts: list[str] = []
    for m in re.finditer(r'### (Human|Assistant).*?\n\n(.*?)\n\n---',
                         body, re.S):
        role = 'user' if 'Human' in m.group(1) else 'assistant'
        text = m.group(2).strip()
        if not text or text.startswith((
            '<system-reminder>', '<local-command-caveat>',
            '<command-message>', '<command-name>',
            '<command-stdout>', '<command-stderr>',
            '<ide_opened_file>', '<ide_selection>',
            '> [!warning]', '> [!success]',
        )):
            continue
        parts.append(f'[{role}] {text[:per_turn]}')
        if len(parts) >= max_turns:
            break
    return '\n'.join(parts)


def find_pending() -> list[dict]:
    out = []
    for p in sorted(CHATS.glob('*.md')):
        text = p.read_text(encoding='utf-8', errors='replace')
        if not text.startswith('---'):
            continue
        fm, body = _fm_and_body(text)
        if 'source: claude-code' not in fm:
            continue
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


def cmd_list() -> int:
    clusters = json.loads(CLUSTERS.read_text()) if CLUSTERS.exists() else {}
    payload = {
        'clusters': sorted(clusters.keys()),
        'tag_families': {
            'type/':   ['debug', 'learning', 'homework', 'brainstorm',
                        'code-review', 'writing', 'planning', 'research',
                        'personal', 'archived'],
            'topic/':  ['programming', 'engineering', 'academics', 'science',
                        'writing', 'research', 'business', 'personal'],
            'domain/': ['vlsi', 'webdev', 'electronics', 'circuits', 'ml',
                        'gaming', 'entertainment'],
            'tool/':   ['claude-code', 'claude', 'obsidian', 'git', 'verilog',
                        'sky130', 'openroad', 'tinytapeout'],
            'status/': ['resolved', 'ongoing', 'archived', 'pending', 'imported'],
            'project/': 'free-form (e.g. project/my-project-name)',
        },
        'pending': find_pending(),
    }
    json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
    print()
    return 0


def cmd_apply(path: Path) -> int:
    data = json.loads(path.read_text(encoding='utf-8'))
    by_uuid = {c['uuid']: c for c in find_pending()}
    meta_entries: list[dict] = []
    applied = 0
    for item in data:
        uuid = item.get('uuid')
        if uuid not in by_uuid:
            print(f'  ? skipping {uuid}: not in pending list', file=sys.stderr)
            continue
        fname = by_uuid[uuid]['filename']
        cls = {
            'cluster':  item.get('cluster', 'Miscellaneous'),
            'themes':   item.get('themes') or [],
            'tags':     item.get('tags') or [],
            'entities': item.get('entities') or [],
        }
        fpath = CHATS / fname
        patch_frontmatter(fpath, cls)
        # flip status imported -> classified
        t = fpath.read_text(encoding='utf-8')
        t = re.sub(r'(?m)^status: imported$', 'status: classified', t)
        fpath.write_text(t, encoding='utf-8')
        meta_entries.append({
            'uuid': uuid, 'filename': fname, 'summary': '',
            'themes': cls['themes'], 'tags': cls['tags'],
            'entities': cls['entities'], 'cluster': cls['cluster'],
        })
        applied += 1
        print(f'  ok {cls["cluster"]:28s} {fname}')
    if meta_entries:
        update_meta_files(meta_entries)
    print(f'\nApplied {applied} classification(s).')
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--list', action='store_true',
                   help='emit JSON of pending chats + taxonomy to stdout')
    g.add_argument('--apply', type=Path, metavar='FILE',
                   help='apply classifications from a JSON file')
    g.add_argument('--count', action='store_true',
                   help='print the number of pending chats')
    args = ap.parse_args()
    if args.list:
        return cmd_list()
    if args.apply:
        return cmd_apply(args.apply)
    if args.count:
        print(len(find_pending()))
        return 0
    return 0


if __name__ == '__main__':
    sys.exit(main())

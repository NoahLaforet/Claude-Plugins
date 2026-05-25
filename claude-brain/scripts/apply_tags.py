#!/usr/bin/env python3
"""Phase 3: Apply synthesized tags/themes/project/status to chat frontmatter.

Idempotent -- re-runnable. Reads _meta/chat_metadata.json and rewrites the
frontmatter block of each chat .md file, preserving body content.

Usage:
    python3 scripts/apply_tags.py
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _vault_path import VAULT  # noqa

CHATS = VAULT / '01 - Chats'
META = VAULT / '_meta'

meta_path = META / 'chat_metadata.json'
if not meta_path.exists():
    print(f'Missing: {meta_path}')
    print('Run synthesize.py first.')
    sys.exit(1)

with open(meta_path) as f:
    meta_by_uuid = {m['uuid']: m for m in json.load(f)}


def derive_status(tags: list[str]) -> str:
    for t in tags:
        if t.startswith('status/'):
            return t.split('/', 1)[1]
    return 'imported'


def rewrite_frontmatter(path: Path, meta: dict) -> bool:
    text = path.read_text(encoding='utf-8')
    m = re.match(r'^---\n(.*?)\n---\n', text, re.DOTALL)
    if not m:
        print(f'  no frontmatter: {path.name}')
        return False
    original_fm = m.group(1)
    body = text[m.end():]

    # Preserve uuid/title/created/updated/message_count/claude_url from original
    preserved: dict[str, str] = {}
    for line in original_fm.splitlines():
        mm = re.match(r'^([a-z_]+):\s*(.*)$', line)
        if mm:
            preserved[mm.group(1)] = mm.group(2)

    tags = meta.get('proposed_tags', [])
    themes = meta.get('proposed_themes', [])
    cluster = meta.get('cluster', 'Miscellaneous')
    project = meta.get('project_guess', '') or ''
    status = derive_status(tags)
    summary = meta.get('summary', '').replace('"', "'").replace('\n', ' ').strip()

    def fmt_list(items: list[str]) -> str:
        if not items:
            return '[]'
        return '[' + ', '.join(items) + ']'

    def fmt_wikilink_list(items: list[str]) -> str:
        if not items:
            return '[]'
        return '[' + ', '.join(f'"[[{x}]]"' for x in items) + ']'

    new_fm_lines = [
        f'uuid: {preserved.get("uuid", meta["uuid"])}',
        f'title: {preserved.get("title", "")}',
        f'created: {preserved.get("created", "")}',
        f'updated: {preserved.get("updated", "")}',
        f'message_count: {preserved.get("message_count", 0)}',
        f'claude_url: {preserved.get("claude_url", f"https://claude.ai/chat/{meta["uuid"]}")}',
        f'cluster: "[[{cluster}]]"',
        f'themes: {fmt_wikilink_list([cluster] + themes)}',
        'sub_themes: [' + ', '.join('"' + t + '"' for t in themes) + ']',
        f'tags: {fmt_list(tags)}',
        f'project: {"[[" + project + "]]" if project else ""}',
        f'status: {status}',
        f'summary: "{summary[:300]}"',
    ]
    new_fm = '---\n' + '\n'.join(new_fm_lines) + '\n---\n'
    path.write_text(new_fm + body, encoding='utf-8')
    return True


updated = 0
missing = 0
for path in sorted(CHATS.glob('*.md')):
    text = path.read_text(encoding='utf-8')
    m = re.search(r'uuid:\s*([0-9a-f-]+)', text)
    if not m:
        continue
    uuid = m.group(1)
    if uuid not in meta_by_uuid:
        print(f'No metadata for {path.name} ({uuid})')
        missing += 1
        continue
    if rewrite_frontmatter(path, meta_by_uuid[uuid]):
        updated += 1

print(f'\nUpdated {updated} chat files, {missing} missing metadata.')

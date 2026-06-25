#!/usr/bin/env python3
"""Phase 0: Deterministic extraction of Claude export -> Obsidian vault.

Creates per-chat .md files preserving full transcripts (text, thinking,
tool_use, tool_result blocks), projects, and memories.

Usage:
    python3 scripts/extract.py

Before running, set CLAUDE_BRAIN_VAULT to your vault path, or place the
scripts/ folder inside <vault>/_meta/ so auto-detection works.

Expected export layout (drop the unzipped Claude export into the vault):
    <vault>/Claude Data <date>/
        conversations.json
        projects.json
        memories.json
"""
import json
import os
import re
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
from _vault_path import VAULT  # noqa

# Find the most recent export folder (sorted lexicographically)
_exports = sorted(VAULT.glob('Claude Data *'), reverse=True)
SRC = _exports[0] if _exports else VAULT / 'Claude Data'

CHATS_DIR = VAULT / '01 - Chats'
PROJECTS_DIR = VAULT / '02 - Projects'
MEMORIES_DIR = VAULT / '03 - Memories'
MOC_DIR = VAULT / '00 - Maps of Content'
TAGS_DIR = VAULT / '04 - Tags'
ENTITIES_DIR = VAULT / '05 - Entities'
META_DIR = VAULT / '_meta'

for d in [CHATS_DIR, PROJECTS_DIR, MEMORIES_DIR, MOC_DIR, TAGS_DIR, ENTITIES_DIR, META_DIR]:
    d.mkdir(parents=True, exist_ok=True)


def safe_filename(name: str, fallback: str) -> str:
    """Obsidian-safe filename. Strips illegal chars and trims length."""
    if not name or not name.strip():
        name = fallback
    # Obsidian forbids: \ / : * ? " < > | ^ # [ ]
    name = re.sub(r'[\\/:*?"<>|^#\[\]]', '-', name)
    name = re.sub(r'\s+', ' ', name).strip(' .-')
    return name[:120] or fallback


def fmt_date(iso: str) -> str:
    """2025-11-24T01:22:18Z -> 2025-11-24"""
    return iso[:10] if iso else ''


def fmt_ts(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso.replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M UTC')
    except Exception:
        return iso


def render_block(block: dict) -> str:
    """Render one content block as markdown."""
    btype = block.get('type', 'unknown')
    if btype == 'text':
        return block.get('text', '')
    if btype == 'thinking':
        t = block.get('thinking', '') or block.get('text', '')
        return f'> [!note]- Thinking\n> {t.replace(chr(10), chr(10) + "> ")}'
    if btype == 'tool_use':
        name = block.get('name', 'tool')
        inp = block.get('input', {})
        try:
            inp_str = json.dumps(inp, indent=2, ensure_ascii=False)
        except Exception:
            inp_str = str(inp)
        return f'> [!example]- Tool use: {name}\n```json\n{inp_str}\n```'
    if btype == 'tool_result':
        content = block.get('content', '')
        if isinstance(content, list):
            parts = []
            for sub in content:
                if isinstance(sub, dict):
                    parts.append(sub.get('text', json.dumps(sub, ensure_ascii=False)))
                else:
                    parts.append(str(sub))
            content = '\n'.join(parts)
        return f'> [!success]- Tool result\n```\n{content}\n```'
    if btype == 'token_budget':
        return ''  # metadata, not content
    # Unknown block type: dump raw
    return f'> [!warning]- Unknown block ({btype})\n```json\n{json.dumps(block, ensure_ascii=False, indent=2)}\n```'


def render_message(msg: dict) -> str:
    sender = msg.get('sender', 'unknown')
    ts = fmt_ts(msg.get('created_at', ''))
    icon = 'Human' if sender == 'human' else 'Assistant'
    header = f'### {icon} · {ts}'

    # Prefer content blocks (rich); fall back to text
    content = msg.get('content') or []
    body_parts = []
    if isinstance(content, list) and content:
        for block in content:
            if isinstance(block, dict):
                rendered = render_block(block)
                if rendered:
                    body_parts.append(rendered)
    if not body_parts and msg.get('text'):
        body_parts.append(msg['text'])

    # Files
    files = msg.get('files') or []
    if files:
        file_lines = [f'- `{f.get("file_name", f.get("file_uuid", "?"))}`' for f in files]
        body_parts.append('**Files attached:**\n' + '\n'.join(file_lines))

    attachments = msg.get('attachments') or []
    if attachments:
        att_lines = []
        for a in attachments:
            if isinstance(a, dict):
                att_lines.append(f'- `{a.get("file_name", "?")}`: {a.get("extracted_content", "")[:500]}')
            else:
                att_lines.append(f'- {a}')
        body_parts.append('**Attachments:**\n' + '\n'.join(att_lines))

    return header + '\n\n' + '\n\n'.join(body_parts)


def write_chat(conv: dict, project_name_by_uuid: dict) -> Path:
    uuid = conv['uuid']
    name = conv.get('name', '').strip()
    created = conv.get('created_at', '')
    updated = conv.get('updated_at', '')
    date = fmt_date(created)
    msgs = conv.get('chat_messages', [])

    fallback_title = f'Untitled chat {uuid[:8]}'
    title = name or fallback_title
    fname = safe_filename(f'{date} - {title}', f'{date} - {fallback_title}')
    path = CHATS_DIR / f'{fname}.md'
    if path.exists():
        path = CHATS_DIR / f'{fname} ({uuid[:8]}).md'

    fm_lines = [
        '---',
        f'uuid: {uuid}',
        f'title: "{title.replace(chr(34), chr(39))}"',
        f'created: {created}',
        f'updated: {updated}',
        f'message_count: {len(msgs)}',
        f'claude_url: https://claude.ai/chat/{uuid}',
        'tags: []',
        'themes: []',
        'project:',
        'status: imported',
        '---',
        '',
    ]

    body = [f'# {title}', '']
    summary = conv.get('summary') or ''
    if summary:
        body.append(f'> **Summary:** {summary}')
        body.append('')
    body.append(f'**Messages:** {len(msgs)} | **Created:** {fmt_ts(created)} | [Open in Claude](https://claude.ai/chat/{uuid})')
    body.append('')
    body.append('---')
    body.append('')

    for m in msgs:
        body.append(render_message(m))
        body.append('')
        body.append('---')
        body.append('')

    path.write_text('\n'.join(fm_lines) + '\n'.join(body), encoding='utf-8')
    return path


def write_project(p: dict) -> Path:
    uuid = p['uuid']
    name = p.get('name', '') or f'Project {uuid[:8]}'
    fname = safe_filename(name, f'Project-{uuid[:8]}')
    path = PROJECTS_DIR / f'{fname}.md'
    docs = p.get('docs', []) or []
    fm = [
        '---',
        f'uuid: {uuid}',
        f'name: "{name.replace(chr(34), chr(39))}"',
        f'created: {p.get("created_at", "")}',
        f'updated: {p.get("updated_at", "")}',
        f'is_private: {p.get("is_private", False)}',
        f'doc_count: {len(docs)}',
        'tags: [project]',
        '---',
        '',
    ]
    body = [f'# {name}', '']
    if p.get('description'):
        body += ['## Description', p['description'], '']
    if p.get('prompt_template'):
        body += ['## System prompt', '```', p['prompt_template'], '```', '']
    if docs:
        body += ['## Documents', '']
        for d in docs:
            body.append(f'### {d.get("filename", "(untitled)")}')
            body.append('```')
            body.append(d.get('content', ''))
            body.append('```')
            body.append('')
    body += ['## Related chats', '', '```dataview', 'LIST',
             'FROM "01 - Chats"', f'WHERE project = "{name}"', 'SORT created DESC', '```']
    path.write_text('\n'.join(fm) + '\n'.join(body), encoding='utf-8')
    return path


def write_memories(mem_bundle: list) -> None:
    if not mem_bundle:
        return
    bundle = mem_bundle[0] if isinstance(mem_bundle, list) else mem_bundle
    conv_mem = bundle.get('conversations_memory') or ''
    proj_mems = bundle.get('project_memories') or []
    (MEMORIES_DIR / 'Conversations memory.md').write_text(
        '---\ntags: [memory/conversations]\n---\n\n# Conversations memory\n\n' + str(conv_mem),
        encoding='utf-8',
    )
    for i, pm in enumerate(proj_mems):
        if isinstance(pm, dict):
            name = pm.get('project_name') or pm.get('name') or f'project-{i}'
            content = pm.get('memory') or pm.get('content') or json.dumps(pm, indent=2)
        else:
            name = f'project-{i}'
            content = str(pm)
        fname = safe_filename(f'Project memory - {name}', f'Project-memory-{i}')
        (MEMORIES_DIR / f'{fname}.md').write_text(
            f'---\ntags: [memory/project]\nproject: "{name}"\n---\n\n# Memory: {name}\n\n{content}',
            encoding='utf-8',
        )


def main():
    if not SRC.exists():
        print(f'Export folder not found: {SRC}')
        print('Drop an unzipped Claude export into your vault as "Claude Data <date>/".')
        sys.exit(1)

    with open(SRC / 'conversations.json') as f:
        conversations = json.load(f)
    with open(SRC / 'projects.json') as f:
        projects = json.load(f)
    memories_path = SRC / 'memories.json'
    memories = json.loads(memories_path.read_text()) if memories_path.exists() else []

    project_map = {p['uuid']: p.get('name', '') for p in projects}

    n_chats = 0
    for conv in conversations:
        try:
            write_chat(conv, project_map)
            n_chats += 1
        except Exception as e:
            print(f'Failed chat {conv.get("uuid")}: {e}')

    n_proj = 0
    for p in projects:
        try:
            write_project(p)
            n_proj += 1
        except Exception as e:
            print(f'Failed project {p.get("uuid")}: {e}')

    write_memories(memories)
    print(f'Wrote {n_chats} chats, {n_proj} projects, memories bundle')


if __name__ == '__main__':
    main()

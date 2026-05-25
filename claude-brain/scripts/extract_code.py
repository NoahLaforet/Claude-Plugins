#!/usr/bin/env python3
"""Ingest Claude Code terminal sessions into the Obsidian vault.

Walks ~/.claude/projects/<slug>/<session-uuid>.jsonl, renders each
session into 01 - Chats/ with the same frontmatter schema as claude.ai
chats. Dedup keys off session UUID via auto_save.existing_chat_uuids(),
so reruns are idempotent and safe for cron/launchd.

Usage:
  python3 scripts/extract_code.py                 # one-shot
  python3 scripts/extract_code.py --dry-run       # list new sessions
  python3 scripts/extract_code.py --min-turns 2   # skip tiny sessions
"""
from __future__ import annotations
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from extract import (  # noqa
    CHATS_DIR,
    fmt_date,
    fmt_ts,
    render_block,
    safe_filename,
)
from auto_save import existing_chat_uuids  # noqa
from sync import (  # noqa
    _config_api_key,
    classify_chat,
    load_taxonomy_context,
    patch_frontmatter,
    update_meta_files,
)

CLAUDE_PROJECTS = Path.home() / '.claude' / 'projects'

# Record types that are pure harness bookkeeping and never carry user-visible
# content. Everything else (user, assistant, attachment) is inspected.
SKIP_TYPES = {
    'queue-operation',
    'file-history-snapshot',
    'last-prompt',
    'ai-title',
    'summary',
}


def load_session(path: Path) -> list[dict]:
    records = []
    with path.open(encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def session_metadata(records: list[dict]) -> dict:
    """Pull title, timestamps, cwd, git branch from the record stream."""
    title = ''
    first_ts = ''
    last_ts = ''
    cwd = ''
    git_branch = ''
    version = ''
    slug = ''
    first_user_text = ''

    for r in records:
        ts = r.get('timestamp', '')
        if ts and not first_ts:
            first_ts = ts
        if ts:
            last_ts = ts
        if r.get('type') == 'ai-title' and r.get('aiTitle'):
            title = r['aiTitle']
        if not cwd and r.get('cwd'):
            cwd = r['cwd']
        if not git_branch and r.get('gitBranch'):
            git_branch = r['gitBranch']
        if not version and r.get('version'):
            version = r['version']
        if not slug and r.get('slug'):
            slug = r['slug']
        if not first_user_text and r.get('type') == 'user':
            msg = r.get('message') or {}
            content = msg.get('content')
            candidate = ''
            if isinstance(content, list):
                for b in content:
                    if isinstance(b, dict) and b.get('type') == 'text':
                        candidate = (b.get('text') or '').strip()
                        if candidate:
                            break
            elif isinstance(content, str):
                candidate = content.strip()
            # Skip harness-injected wrappers when looking for a title source.
            if candidate and not candidate.startswith((
                '<system-reminder>',
                '<local-command-caveat>',
                '<command-message>',
                '<command-name>',
                '<command-stdout>',
                '<command-stderr>',
            )):
                first_user_text = candidate

    if not title:
        if first_user_text:
            title = first_user_text.splitlines()[0][:80]
        else:
            title = f'Code session {slug or "untitled"}'

    return {
        'title': title,
        'first_ts': first_ts,
        'last_ts': last_ts,
        'cwd': cwd,
        'git_branch': git_branch,
        'version': version,
        'slug': slug,
    }


def is_real_turn(record: dict) -> bool:
    """True if this record contains user-visible content worth rendering."""
    rtype = record.get('type')
    if rtype in SKIP_TYPES:
        return False
    if rtype == 'attachment':
        # Attachments are harness-injected context. Not real turns.
        return False
    if rtype not in ('user', 'assistant'):
        return False
    msg = record.get('message') or {}
    content = msg.get('content')
    if not content:
        return False
    return True


def render_turn(record: dict) -> str:
    rtype = record.get('type')
    ts = fmt_ts(record.get('timestamp', ''))
    sidechain = ' | sub-agent' if record.get('isSidechain') else ''
    icon = 'Human' if rtype == 'user' else 'Assistant'
    header = f'### {icon} — {ts}{sidechain}'

    msg = record.get('message') or {}
    content = msg.get('content') or []
    body_parts: list[str] = []
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict):
                rendered = render_block(block)
                if rendered:
                    body_parts.append(rendered)
            elif isinstance(block, str):
                body_parts.append(block)
    elif isinstance(content, str):
        body_parts.append(content)

    if not body_parts:
        return ''
    return header + '\n\n' + '\n\n'.join(body_parts)


def write_session(session_path: Path, dry_run: bool = False) -> Path | None:
    session_uuid = session_path.stem
    records = load_session(session_path)
    if not records:
        return None

    turns = [r for r in records if is_real_turn(r)]
    if not turns:
        return None

    meta = session_metadata(records)
    date = fmt_date(meta['first_ts'])
    title = meta['title']
    fallback = f'Code session {session_uuid[:8]}'
    fname = safe_filename(f'{date} - {title}', f'{date} - {fallback}')
    path = CHATS_DIR / f'{fname}.md'
    if path.exists():
        path = CHATS_DIR / f'{fname} ({session_uuid[:8]}).md'

    if dry_run:
        return path

    fm_lines = [
        '---',
        f'uuid: {session_uuid}',
        f'title: "{title.replace(chr(34), chr(39))}"',
        f'created: {meta["first_ts"]}',
        f'updated: {meta["last_ts"]}',
        f'message_count: {len(turns)}',
        'source: claude-code',
        f'cwd: "{meta["cwd"]}"',
        f'git_branch: "{meta["git_branch"]}"',
        f'slug: "{meta["slug"]}"',
        f'cli_version: "{meta["version"]}"',
        'tags: []',
        'themes: []',
        'project:',
        'status: imported',
        '---',
        '',
    ]

    body = [f'# {title}', '']
    body.append(
        f'**Source:** Claude Code CLI | **Turns:** {len(turns)} | '
        f'**Started:** {fmt_ts(meta["first_ts"])}'
    )
    if meta['cwd']:
        body.append(f'**Working dir:** `{meta["cwd"]}`')
    if meta['git_branch']:
        body.append(f'**Branch:** `{meta["git_branch"]}`')
    body.append('')
    body.append('---')
    body.append('')

    for r in turns:
        rendered = render_turn(r)
        if not rendered:
            continue
        body.append(rendered)
        body.append('')
        body.append('---')
        body.append('')

    path.write_text('\n'.join(fm_lines) + '\n'.join(body), encoding='utf-8')
    return path


def first_turns_excerpt(records: list[dict], max_turns: int = 4,
                        per_turn_chars: int = 400) -> str:
    """Build a short '[role] text' excerpt for classification prompts."""
    parts: list[str] = []
    for r in records:
        if r.get('type') not in ('user', 'assistant'):
            continue
        msg = r.get('message') or {}
        content = msg.get('content')
        text = ''
        if isinstance(content, list):
            for b in content:
                if isinstance(b, dict) and b.get('type') == 'text':
                    text += b.get('text', '')
        elif isinstance(content, str):
            text = content
        text = text.strip()
        if not text or text.startswith((
            '<system-reminder>', '<local-command-caveat>',
            '<command-message>', '<command-name>',
            '<command-stdout>', '<command-stderr>',
        )):
            continue
        parts.append(f'[{r["type"]}] {text[:per_turn_chars]}')
        if len(parts) >= max_turns:
            break
    return '\n'.join(parts)


def find_sessions() -> list[Path]:
    if not CLAUDE_PROJECTS.exists():
        return []
    return sorted(CLAUDE_PROJECTS.glob('*/*.jsonl'))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--no-classify', action='store_true',
                    help='skip auto-classification even if API key is set')
    ap.add_argument('--min-turns', type=int, default=1,
                    help='skip sessions with fewer than N real turns')
    args = ap.parse_args()

    have = existing_chat_uuids()
    sessions = find_sessions()
    if not sessions:
        print(f'No sessions found under {CLAUDE_PROJECTS}.')
        return 0

    classify = not args.no_classify and (
        os.environ.get('ANTHROPIC_API_KEY') or _config_api_key()
    )
    taxonomy = load_taxonomy_context() if classify else None
    if not classify and not args.no_classify and not args.dry_run:
        print('  (no ANTHROPIC_API_KEY -- chats will ingest unclassified)')

    new_count = 0
    skipped_small = 0
    meta_entries: list[dict] = []
    for sp in sessions:
        session_uuid = sp.stem
        if session_uuid in have:
            continue

        records = load_session(sp)
        turn_count = sum(1 for r in records if is_real_turn(r))
        if turn_count < args.min_turns:
            skipped_small += 1
            continue

        meta = session_metadata(records)

        if args.dry_run:
            print(f'  + {fmt_date(meta["first_ts"])} {meta["title"][:60]!r} '
                  f'({turn_count} turns) [{session_uuid[:8]}]')
            new_count += 1
            continue

        try:
            path = write_session(sp)
        except Exception as e:
            print(f'  ! {sp.name}: {e}', file=sys.stderr)
            continue
        if not path:
            continue

        classification = None
        if classify:
            excerpt = first_turns_excerpt(records)
            classification = classify_chat(
                meta['title'], '', excerpt, taxonomy
            )
            if classification:
                tags = classification.get('tags') or []
                if not any(t.startswith('tool/') for t in tags):
                    tags.append('tool/claude-code')
                    classification['tags'] = tags
                patch_frontmatter(path, classification)
                meta_entries.append({
                    'uuid': session_uuid,
                    'filename': path.name,
                    'summary': '',
                    'themes': classification.get('themes') or [],
                    'tags': tags,
                    'entities': classification.get('entities') or [],
                    'cluster': classification.get('cluster', 'Miscellaneous'),
                })
        print(f'  + {path.name}'
              f'{"  -> " + classification["cluster"] if classification else ""}')
        new_count += 1

    if meta_entries:
        update_meta_files(meta_entries)
        print(f'\nClassified + linked {len(meta_entries)} sessions into MOCs.')

    tag = '[dry-run] ' if args.dry_run else ''
    print(f'{tag}{new_count} new code sessions ingested, '
          f'{skipped_small} skipped (below --min-turns).')
    return 0


if __name__ == '__main__':
    sys.exit(main())

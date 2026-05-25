#!/usr/bin/env python3
"""Auto-save: ingest new Claude exports without re-processing old chats.

Scans the vault root for any "Claude Data *" folder (so you can drop a new
export next to the old one) and only extracts conversations whose UUID is
not already present in 01 - Chats/ frontmatter. Idempotent -- safe to run
repeatedly, safe to run from cron/launchd.

Usage:
  python3 scripts/auto_save.py              # one-shot scan
  python3 scripts/auto_save.py --watch N    # poll every N seconds
  python3 scripts/auto_save.py --dry-run    # report what would change
"""
from __future__ import annotations
import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _vault_path import VAULT  # noqa
from extract import write_chat, write_project, write_memories, CHATS_DIR, PROJECTS_DIR  # noqa

META = VAULT / '_meta'
STATE = META / 'auto_save_state.json'
EXPORT_GLOB = 'Claude Data *'

UUID_RE = re.compile(r'^uuid:\s*([a-f0-9-]{36})', re.M)


def existing_chat_uuids() -> set[str]:
    uuids = set()
    for md in CHATS_DIR.glob('*.md'):
        try:
            head = md.read_text(encoding='utf-8', errors='ignore')[:1200]
        except OSError:
            continue
        m = UUID_RE.search(head)
        if m:
            uuids.add(m.group(1))
    return uuids


def existing_project_uuids() -> set[str]:
    uuids = set()
    for md in PROJECTS_DIR.glob('*.md'):
        try:
            head = md.read_text(encoding='utf-8', errors='ignore')[:1200]
        except OSError:
            continue
        m = UUID_RE.search(head)
        if m:
            uuids.add(m.group(1))
    return uuids


def load_state() -> dict:
    if STATE.exists():
        try:
            return json.loads(STATE.read_text())
        except json.JSONDecodeError:
            pass
    return {'exports_seen': {}}


def save_state(state: dict) -> None:
    STATE.write_text(json.dumps(state, indent=2))


def find_exports() -> list[Path]:
    return sorted(p for p in VAULT.glob(EXPORT_GLOB) if p.is_dir())


def export_fingerprint(folder: Path) -> str:
    """Cheap change-detector -- mtime of conversations.json."""
    conv = folder / 'conversations.json'
    if not conv.exists():
        return ''
    return f'{conv.stat().st_mtime_ns}:{conv.stat().st_size}'


def ingest_export(folder: Path, dry_run: bool = False) -> tuple[int, int]:
    conv_path = folder / 'conversations.json'
    proj_path = folder / 'projects.json'
    mem_path = folder / 'memories.json'
    if not conv_path.exists():
        return (0, 0)

    with conv_path.open() as f:
        conversations = json.load(f)
    projects = json.loads(proj_path.read_text()) if proj_path.exists() else []
    memories = json.loads(mem_path.read_text()) if mem_path.exists() else []

    have_chats = existing_chat_uuids()
    have_projects = existing_project_uuids()

    new_convs = [c for c in conversations if c.get('uuid') not in have_chats]
    new_projects = [p for p in projects if p.get('uuid') not in have_projects]

    if dry_run:
        return (len(new_convs), len(new_projects))

    project_map = {p['uuid']: p.get('name', '') for p in projects}
    n_chat = 0
    for conv in new_convs:
        try:
            write_chat(conv, project_map)
            n_chat += 1
        except Exception as e:
            print(f'  ! chat {conv.get("uuid")}: {e}', file=sys.stderr)

    n_proj = 0
    for p in new_projects:
        try:
            write_project(p)
            n_proj += 1
        except Exception as e:
            print(f'  ! project {p.get("uuid")}: {e}', file=sys.stderr)

    # Memories are a bundle -- only rewrite when something new arrived, to
    # avoid clobbering hand-edited memory files on every poll.
    if memories and (n_chat or n_proj):
        try:
            write_memories(memories)
        except Exception as e:
            print(f'  ! memories: {e}', file=sys.stderr)

    return (n_chat, n_proj)


def run_once(dry_run: bool = False) -> int:
    state = load_state()
    exports = find_exports()
    if not exports:
        print('No "Claude Data *" folders found in vault root.')
        return 0

    total_chats = total_projects = 0
    changed = False
    for folder in exports:
        fp = export_fingerprint(folder)
        prior = state['exports_seen'].get(folder.name)
        if prior == fp and not dry_run:
            continue
        n_chat, n_proj = ingest_export(folder, dry_run=dry_run)
        total_chats += n_chat
        total_projects += n_proj
        if not dry_run:
            state['exports_seen'][folder.name] = fp
            changed = True
        tag = '[dry-run] ' if dry_run else ''
        print(f'{tag}{folder.name}: +{n_chat} chats, +{n_proj} projects')

    if changed and not dry_run:
        save_state(state)

    if total_chats and not dry_run:
        print(f'\nIngested {total_chats} new chats. Run synthesize + apply_tags '
              f'to classify them:\n  python3 {META}/synthesize.py\n  python3 {META}/apply_tags.py')
    return total_chats


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--watch', type=int, metavar='SECONDS',
                    help='poll every N seconds instead of exiting')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    if args.watch:
        print(f'Watching {VAULT} every {args.watch}s. Ctrl-C to stop.')
        try:
            while True:
                run_once(dry_run=args.dry_run)
                time.sleep(args.watch)
        except KeyboardInterrupt:
            print('\nstopped')
        return 0

    run_once(dry_run=args.dry_run)
    return 0


if __name__ == '__main__':
    sys.exit(main())

#!/usr/bin/env python3
"""PreCompact hook -- write a checkpoint before Claude Code compacts context.

Reads the live transcript JSONL passed by the hook event and emits a
markdown checkpoint to ~/.claude/checkpoints/<session-uuid>.md. The
checkpoint captures what the next post-compact (or post-resume) Claude
session needs to pick up the thread:

    - the original user request (slug + first user turn)
    - cwd + git branch
    - the last ~20 user requests verbatim
    - files modified during the session (with last-touch order)
    - the last few non-trivial assistant decisions / tool calls
    - any in-flight TODO / Task list state we can find

Always exits 0 -- never blocks compaction.
Logs to ~/.claude/checkpoints/checkpoint.log.

Wire this up in ~/.claude/settings.json:
    "hooks": {
        "PreCompact": [
            {
                "matcher": "",
                "hooks": [{"type": "command",
                           "command": "python3 /path/to/scripts/precompact_checkpoint.py"}]
            }
        ]
    }
"""
from __future__ import annotations
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

CHECKPOINTS = Path.home() / '.claude' / 'checkpoints'
LOG = CHECKPOINTS / 'checkpoint.log'
MAX_REQUESTS = 20
MAX_DECISIONS = 8
MAX_FILES = 30
MAX_BODY = 800  # per-turn truncation for readability


def log(msg: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open('a') as f:
        f.write(f'{datetime.now().isoformat()} {msg}\n')


def load_jsonl(path: Path) -> list[dict]:
    records = []
    if not path.exists():
        return records
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


def session_meta(records: list[dict]) -> dict:
    meta = {'cwd': '', 'git_branch': '', 'slug': '', 'title': '',
            'first_user': '', 'first_ts': '', 'last_ts': ''}
    for r in records:
        ts = r.get('timestamp', '')
        if ts and not meta['first_ts']:
            meta['first_ts'] = ts
        if ts:
            meta['last_ts'] = ts
        if not meta['cwd'] and r.get('cwd'):
            meta['cwd'] = r['cwd']
        if not meta['git_branch'] and r.get('gitBranch'):
            meta['git_branch'] = r['gitBranch']
        if not meta['slug'] and r.get('slug'):
            meta['slug'] = r['slug']
        if r.get('type') == 'ai-title' and r.get('aiTitle'):
            meta['title'] = r['aiTitle']
        if not meta['first_user'] and r.get('type') == 'user':
            meta['first_user'] = extract_user_text(r)[:MAX_BODY]
    return meta


def extract_user_text(r: dict) -> str:
    msg = r.get('message') or {}
    content = msg.get('content', '')
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        out = []
        for b in content:
            if isinstance(b, dict) and b.get('type') == 'text':
                out.append(b.get('text', ''))
        return '\n'.join(out).strip()
    return ''


def extract_assistant_text(r: dict) -> str:
    msg = r.get('message') or {}
    content = msg.get('content', '')
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        out = []
        for b in content:
            if isinstance(b, dict) and b.get('type') == 'text':
                out.append(b.get('text', ''))
        return '\n'.join(out).strip()
    return ''


def is_system_text(s: str) -> bool:
    s = s.strip()
    return s.startswith((
        '<system-reminder>', '<local-command-stdout>',
        '<local-command-stderr>', '<local-command-caveat>',
        '<command-message>', '<command-name>',
        '<command-stdout>', '<command-stderr>',
        '<ide_opened_file>', '<ide_selection>',
    ))


def collect_user_requests(records: list[dict]) -> list[tuple[str, str]]:
    """Return (timestamp, text) pairs for human-typed user turns."""
    out = []
    for r in records:
        if r.get('type') != 'user':
            continue
        text = extract_user_text(r)
        if not text or is_system_text(text):
            continue
        msg = r.get('message') or {}
        content = msg.get('content')
        if isinstance(content, list):
            if any(isinstance(b, dict) and b.get('type') == 'tool_result'
                   for b in content):
                continue
        out.append((r.get('timestamp', ''), text))
    return out


def collect_files_touched(records: list[dict]) -> list[tuple[str, str]]:
    """Order-preserving (path, last-action) for Edit/Write tool calls."""
    last_touch: dict[str, str] = {}
    order: list[str] = []
    for r in records:
        msg = r.get('message') or {}
        content = msg.get('content')
        if not isinstance(content, list):
            continue
        for b in content:
            if not (isinstance(b, dict) and b.get('type') == 'tool_use'):
                continue
            tool = b.get('name', '')
            inp = b.get('input', {}) or {}
            if tool not in ('Edit', 'Write', 'NotebookEdit'):
                continue
            path = inp.get('file_path') or inp.get('notebook_path') or ''
            if not path:
                continue
            if path not in last_touch:
                order.append(path)
            last_touch[path] = tool
    return [(p, last_touch[p]) for p in order]


def collect_decisions(records: list[dict]) -> list[str]:
    """Pull the last few substantial assistant text turns as decisions."""
    out = []
    for r in records:
        if r.get('type') != 'assistant':
            continue
        text = extract_assistant_text(r)
        if not text or len(text) < 80:
            continue
        out.append(text[:MAX_BODY])
    return out[-MAX_DECISIONS:]


def render_checkpoint(session_id: str, trigger: str, meta: dict,
                      requests: list, files: list, decisions: list) -> str:
    now = datetime.now(timezone.utc).isoformat()
    lines = [
        '---',
        f'type: checkpoint',
        f'session_id: {session_id}',
        f'trigger: {trigger}',
        f'created: {now}',
        f'cwd: "{meta["cwd"]}"',
        f'branch: "{meta["git_branch"]}"',
        f'slug: "{meta["slug"]}"',
        f'title: "{meta["title"]}"',
        '---',
        '',
        f'# Checkpoint -- {meta["title"] or session_id[:8]}',
        '',
        f'> Compaction trigger: **{trigger}**. Generated {now}.',
        '',
    ]

    if meta.get('first_user'):
        lines += [
            '## Original ask',
            '',
            '> ' + meta['first_user'].replace('\n', '\n> '),
            '',
        ]

    if requests:
        recent = requests[-MAX_REQUESTS:]
        lines += [f'## Last {len(recent)} user requests', '']
        for ts, txt in recent:
            short = txt.replace('\n', ' ')
            if len(short) > 220:
                short = short[:220] + '...'
            lines.append(f'- `{ts[:19]}` -- {short}')
        lines.append('')

    if files:
        lines += [f'## Files touched ({len(files)})', '']
        for path, action in files[-MAX_FILES:]:
            lines.append(f'- {action} -> `{path}`')
        lines.append('')

    if decisions:
        lines += [f'## Recent assistant decisions (last {len(decisions)})', '']
        for d in decisions:
            short = d.replace('\n', '\n  ')
            lines.append(f'- {short[:600]}')
            lines.append('')

    lines += [
        '## How to resume',
        '',
        'After compaction (or in a new session), the SessionStart hook will surface this checkpoint. Read it first, then continue where the user left off.',
        '',
    ]
    return '\n'.join(lines)


def main() -> int:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as e:
        log(f'bad stdin json: {e}')
        return 0

    transcript_path = Path(payload.get('transcript_path', ''))
    session_id = payload.get('session_id', 'unknown')
    trigger = payload.get('trigger', 'unknown')

    log(f'fired: session={session_id[:8]} trigger={trigger} transcript={transcript_path}')

    if not transcript_path.exists():
        log(f'transcript missing: {transcript_path}')
        return 0

    records = load_jsonl(transcript_path)
    if not records:
        log('empty transcript, skipping')
        return 0

    meta = session_meta(records)
    requests = collect_user_requests(records)
    files = collect_files_touched(records)
    decisions = collect_decisions(records)
    body = render_checkpoint(session_id, trigger, meta, requests, files, decisions)

    CHECKPOINTS.mkdir(parents=True, exist_ok=True)
    out = CHECKPOINTS / f'{session_id}.md'
    out.write_text(body, encoding='utf-8')

    # Also write a "latest" pointer for fast SessionStart lookup
    latest = CHECKPOINTS / 'latest.md'
    latest.write_text(body, encoding='utf-8')

    log(f'wrote checkpoint to {out} ({len(records)} records, {len(requests)} requests, {len(files)} files)')
    return 0


if __name__ == '__main__':
    sys.exit(main())

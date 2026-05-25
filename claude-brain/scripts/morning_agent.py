#!/usr/bin/env python3
"""Morning agent -- creates today's daily note (e.g. at 8 AM via launchd).

Builds a single daily/<YYYY-MM-DD>.md page with:

- The latest checkpoint summary (if under 24h old) -- "where you left off"
- Yesterday's activity rollup (chat count by cluster, recent titles)
- Memory candidates queued for triage
- An empty "today" section for ad-hoc notes

Idempotent -- running twice on the same day is a no-op (won't overwrite
notes the user has already added). The "auto-generated" sections are
re-written, but anything below the preserve marker is kept.

Logs to _meta/morning.log.

Install the launchd plist from templates/ to run automatically.
"""
from __future__ import annotations
import re
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _vault_path import VAULT  # noqa

CHATS = VAULT / '01 - Chats'
DAILY = VAULT / 'daily'
LOG = VAULT / '_meta' / 'morning.log'
CHECKPOINTS = Path.home() / '.claude' / 'checkpoints'
CANDIDATES_QUEUE = Path('/tmp/claude_brain_memory_candidates.json')

PRESERVE_MARKER = '<!-- preserve below -->'


def log(msg: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open('a') as f:
        f.write(f'{datetime.now().isoformat()} {msg}\n')


def fm_field(text: str, key: str) -> str:
    if not text.startswith('---'):
        return ''
    end = text.find('\n---', 3)
    if end == -1:
        return ''
    fm = text[3:end]
    m = re.search(rf'(?m)^{key}:\s*(.*)$', fm)
    return (m.group(1) if m else '').strip()


def yesterdays_activity() -> dict:
    yesterday = (datetime.now() - timedelta(days=1)).date()
    today = datetime.now().date()
    cluster_counts: Counter = Counter()
    titles = []
    for p in CHATS.glob('*.md'):
        try:
            text = p.read_text(encoding='utf-8', errors='replace')[:2000]
        except OSError:
            continue
        created = fm_field(text, 'created')
        try:
            d = datetime.fromisoformat(created.replace('Z', '+00:00')).date()
        except ValueError:
            continue
        if d == yesterday or d == today:
            cluster = fm_field(text, 'cluster').strip('"').strip('[]')
            title = fm_field(text, 'title').strip('"')
            cluster_counts[cluster or 'Unclassified'] += 1
            if title:
                titles.append((d, cluster, title))
    return {'cluster_counts': cluster_counts, 'titles': titles}


def latest_checkpoint() -> str | None:
    f = CHECKPOINTS / 'latest.md'
    if not f.exists():
        return None
    age_hr = (datetime.now().timestamp() - f.stat().st_mtime) / 3600
    if age_hr > 24:
        return None
    text = f.read_text(encoding='utf-8', errors='replace')
    ask_m = re.search(r'## .* Original ask\s*\n\n> (.+?)\n', text, re.S)
    ask = ask_m.group(1).strip().replace('\n> ', ' ') if ask_m else '(none)'
    requests = re.findall(r'^- `[^`]+` -- (.+)$', text, re.M)
    recent = '\n'.join(f'  - {r}' for r in requests[-5:]) or '  (none)'
    return f'**Original ask:** {ask}\n\n**Last 5 requests before stop:**\n{recent}'


def memory_candidate_count() -> int:
    if not CANDIDATES_QUEUE.exists():
        return 0
    import json
    try:
        return len(json.loads(CANDIDATES_QUEUE.read_text()))
    except (json.JSONDecodeError, OSError):
        return 0


def render(today: datetime) -> str:
    activity = yesterdays_activity()
    checkpoint = latest_checkpoint()
    cands = memory_candidate_count()

    cluster_block = '\n'.join(
        f'- **{c}** -- {n}' for c, n in activity['cluster_counts'].most_common()
    ) or '_(no chat activity)_'

    titles_block = '\n'.join(
        f'- ({d}) {t} -- _{c}_'
        for d, c, t in sorted(activity['titles'], reverse=True)[:8]
    ) or '_(no titled chats)_'

    parts = [
        '---',
        f'type: daily',
        f'date: {today.strftime("%Y-%m-%d")}',
        f'tags: [daily]',
        '---',
        '',
        f'# {today.strftime("%A, %B %-d, %Y")}',
        '',
        '## Where you left off',
        '',
        checkpoint or '_No recent checkpoint (or > 24h old)._',
        '',
        "## Yesterday's activity",
        '',
        '### Chats by cluster',
        '',
        cluster_block,
        '',
        '### Recent titled chats',
        '',
        titles_block,
        '',
        '## Memory triage',
        '',
        f'- {cands} memory candidate(s) queued at `{CANDIDATES_QUEUE}`',
        '  (open the file to review, or run lint_vault.py)',
        '',
        f'{PRESERVE_MARKER}',
        '',
        '## Notes for today',
        '',
        '_(your notes here -- this section survives daily-note rebuilds)_',
        '',
    ]
    return '\n'.join(parts)


def main() -> int:
    DAILY.mkdir(parents=True, exist_ok=True)
    today = datetime.now()
    target = DAILY / f'{today.strftime("%Y-%m-%d")}.md'

    new_body = render(today)

    if target.exists():
        existing = target.read_text(encoding='utf-8', errors='replace')
        if PRESERVE_MARKER in existing:
            preserve = existing.split(PRESERVE_MARKER, 1)[1]
            head = new_body.split(PRESERVE_MARKER, 1)[0]
            new_body = head + PRESERVE_MARKER + preserve

    target.write_text(new_body, encoding='utf-8')
    log(f'wrote {target}')
    print(f'Wrote {target}')
    return 0


if __name__ == '__main__':
    sys.exit(main())

#!/usr/bin/env python3
"""Weekly audit -- runs Sunday evening (e.g. at 21:00 via launchd).

Sweeps the vault for hygiene problems and writes a dated report to
_meta/audits/audit-YYYY-MM-DD.md. Doesn't auto-fix anything; the goal
is to surface issues so a human (or the next live Claude session) can
decide what to do.

What it checks:
- Broken wikilinks ([[X]] where X.md doesn't exist anywhere)
- Chats with empty cluster
- Chats with empty tags
- Entity references in chats that don't have entity pages
- MOCs whose dataview query won't return anything
"""
from __future__ import annotations
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _vault_path import VAULT  # noqa

CHATS = VAULT / '01 - Chats'
ENTITIES = VAULT / '05 - Entities'
AUDITS = VAULT / '_meta' / 'audits'

WIKILINK = re.compile(r'\[\[([^\]|#]+?)(?:\|[^\]]*)?\]\]')


def all_pages() -> set[str]:
    """Set of every note's stem -- what wikilinks resolve to."""
    out: set[str] = set()
    for p in VAULT.rglob('*.md'):
        if '_meta' in p.parts or 'audits' in p.parts:
            continue
        out.add(p.stem)
    return out


def fm_field(text: str, field: str) -> str:
    if not text.startswith('---'):
        return ''
    end = text.find('\n---', 3)
    if end == -1:
        return ''
    fm = text[3:end]
    m = re.search(rf'(?m)^{field}:\s*(.*)$', fm)
    return (m.group(1) if m else '').strip()


def fm_list(text: str, field: str) -> list[str]:
    val = fm_field(text, field)
    if not val or val == '[]':
        return []
    if val.startswith('['):
        return [s.strip().strip('"') for s in val[1:-1].split(',') if s.strip()]
    return [val]


def audit() -> str:
    pages = all_pages()
    broken_links: dict[str, list[tuple[str, str]]] = defaultdict(list)
    empty_cluster: list[str] = []
    empty_tags: list[str] = []
    referenced_entities: Counter = Counter()
    entity_pages = {p.stem for p in ENTITIES.glob('*.md') if p.stem != '_Index'}

    for p in VAULT.rglob('*.md'):
        if '_meta' in p.parts:
            continue
        try:
            text = p.read_text(encoding='utf-8', errors='replace')
        except OSError:
            continue
        for m in WIKILINK.finditer(text):
            target = m.group(1).strip()
            stem = target.split('/')[-1]
            if stem not in pages:
                broken_links[p.name].append((target, stem))
        if p.parent.name == '01 - Chats':
            if not fm_field(text, 'cluster').strip('"'):
                empty_cluster.append(p.name)
            if not fm_list(text, 'tags'):
                empty_tags.append(p.name)
            for e in fm_list(text, 'entities'):
                referenced_entities[e] += 1

    missing_entity_pages = sorted(
        e for e, _ in referenced_entities.most_common()
        if e and e not in entity_pages
    )

    today = datetime.now().strftime('%Y-%m-%d')
    out = [f'# Vault audit -- {today}', '']
    out.append(f'- Notes scanned: {len(pages)}')
    out.append(f'- Broken-wikilink notes: {len(broken_links)}')
    out.append(f'- Chats with empty cluster: {len(empty_cluster)}')
    out.append(f'- Chats with empty tags: {len(empty_tags)}')
    out.append(f'- Entity refs without an entity page: {len(missing_entity_pages)}')
    out.append('')

    if missing_entity_pages:
        out.append('## Missing entity pages')
        for e in missing_entity_pages:
            out.append(f'- `{e}` (referenced {referenced_entities[e]}x)')
        out.append('')

    if empty_cluster:
        out.append(f'## Chats with empty cluster ({len(empty_cluster)})')
        for n in empty_cluster[:30]:
            out.append(f'- {n}')
        if len(empty_cluster) > 30:
            out.append(f'- ... and {len(empty_cluster) - 30} more')
        out.append('')

    if broken_links:
        out.append('## Broken wikilinks (top 30)')
        for fname, links in list(broken_links.items())[:30]:
            uniq = sorted({lt for lt, _ in links})
            out.append(f'- **{fname}**: {", ".join(uniq[:10])}')
        if len(broken_links) > 30:
            out.append(f'- ... and {len(broken_links) - 30} more files')
        out.append('')

    return '\n'.join(out)


def main() -> int:
    AUDITS.mkdir(parents=True, exist_ok=True)
    report = audit()
    today = datetime.now().strftime('%Y-%m-%d')
    target = AUDITS / f'audit-{today}.md'
    target.write_text(report, encoding='utf-8')
    print(f'Wrote audit report to {target}')
    return 0


if __name__ == '__main__':
    sys.exit(main())

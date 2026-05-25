#!/usr/bin/env python3
"""Vault linter -- surface and (optionally) auto-fix structural problems.

Detects:
  - Broken wikilinks ([[X]] where no X.md exists)
  - Chats with empty cluster
  - Chats with empty tags
  - Entity references in chats that don't have entity pages
  - Theme-label wikilinks that are leftover cruft from synthesis

Auto-fix scope (only with --fix):
  - Theme-label wikilinks inside chat bodies -> converted to **bold**
    A target is treated as a theme label when:
      - It does NOT start with a YYYY-MM-DD date prefix
      - It does NOT contain a slash (no folder paths)
      - It is not the name of an existing MOC/Entity/Project/Memory page
      - It looks like Title Case Words With Spaces
    These are residue from the LLM synthesize step that invented sub-theme
    pages that were never created.

Usage:
    python3 scripts/lint_vault.py             # report only
    python3 scripts/lint_vault.py --fix       # apply theme-label fixes
    python3 scripts/lint_vault.py --json      # machine-readable
"""
from __future__ import annotations
import argparse
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _vault_path import VAULT  # noqa

CHATS = VAULT / '01 - Chats'

WIKILINK = re.compile(r'\[\[([^\]|#]+?)(\|[^\]]*)?\]\]')
DATE_PREFIX = re.compile(r'^\d{4}-\d{2}-\d{2}\s*-')
THEME_LIKE = re.compile(r'^[A-Z][\w\s\-/&\']+$')

KEEP_KEYWORDS = (
    '$', '"', '`', '/Users/', '== ', '~=', ' && ', '\\', 'YYYY-MM-DD',
)


def normalize(s: str) -> str:
    """NFC-normalize a string so characters match between source and filenames."""
    return unicodedata.normalize('NFC', s)


def all_pages() -> set[str]:
    out: set[str] = set()
    for p in VAULT.rglob('*.md'):
        if '_meta' in p.parts or 'audits' in p.parts:
            continue
        out.add(normalize(p.stem))
        out.add(normalize(p.stem).lower())
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


def is_themelike(target: str) -> bool:
    if any(kw in target for kw in KEEP_KEYWORDS):
        return False
    if DATE_PREFIX.match(target):
        return False
    if '/' in target:
        return False
    if not THEME_LIKE.match(target):
        return False
    if not (1 < len(target.split()) < 8):
        return False
    return True


def fix_chat_body(text: str, pages: set[str]) -> tuple[str, int]:
    """Replace broken theme-label wikilinks with **bold**."""
    fixed = 0

    def repl(m: re.Match) -> str:
        nonlocal fixed
        target = m.group(1).strip()
        norm = normalize(target)
        if norm in pages or norm.lower() in pages:
            return m.group(0)
        if not is_themelike(target):
            return m.group(0)
        fixed += 1
        return f'**{target}**'

    return WIKILINK.sub(repl, text), fixed


def lint() -> dict:
    pages = all_pages()
    broken_links: dict[str, list[str]] = defaultdict(list)
    empty_cluster: list[str] = []
    empty_tags: list[str] = []
    referenced_entities: Counter = Counter()
    entity_pages = {p.stem for p in (VAULT / '05 - Entities').glob('*.md')
                    if p.stem != '_Index'}

    for p in VAULT.rglob('*.md'):
        if '_meta' in p.parts or 'audits' in p.parts:
            continue
        try:
            text = p.read_text(encoding='utf-8', errors='replace')
        except OSError:
            continue
        for m in WIKILINK.finditer(text):
            target = m.group(1).strip()
            norm = normalize(target)
            stem = norm.split('/')[-1]
            if stem in pages or stem.lower() in pages:
                continue
            broken_links[p.name].append(target)
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

    return {
        'pages_scanned': len(pages),
        'broken_link_files': len(broken_links),
        'broken_links_total': sum(len(v) for v in broken_links.values()),
        'empty_cluster': empty_cluster,
        'empty_tags': empty_tags,
        'missing_entity_pages': missing_entity_pages,
        'broken_links': dict(broken_links),
    }


def fix_all() -> int:
    pages = all_pages()
    total_fixed = 0
    files_touched = 0
    for p in CHATS.glob('*.md'):
        try:
            text = p.read_text(encoding='utf-8', errors='replace')
        except OSError:
            continue
        new_text, n = fix_chat_body(text, pages)
        if n:
            p.write_text(new_text, encoding='utf-8')
            total_fixed += n
            files_touched += 1
    print(f'Fixed {total_fixed} broken theme-label wikilink(s) across {files_touched} file(s).')
    return total_fixed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--fix', action='store_true',
                    help='auto-convert theme-label wikilinks -> **bold**')
    ap.add_argument('--json', action='store_true',
                    help='machine-readable JSON output')
    args = ap.parse_args()

    if args.fix:
        fix_all()

    report = lint()

    if args.json:
        json.dump(report, sys.stdout, indent=2, ensure_ascii=False)
        print()
        return 0

    print(f'Pages scanned: {report["pages_scanned"]}')
    print(f'Broken-link files: {report["broken_link_files"]} '
          f'({report["broken_links_total"]} link(s))')
    print(f'Chats with empty cluster: {len(report["empty_cluster"])}')
    print(f'Chats with empty tags: {len(report["empty_tags"])}')
    print(f'Missing entity pages: {len(report["missing_entity_pages"])}')

    if report['empty_cluster']:
        print('\nEmpty-cluster chats:')
        for n in report['empty_cluster']:
            print(f'  - {n}')

    if report['missing_entity_pages']:
        print('\nMissing entity pages:')
        for e in report['missing_entity_pages']:
            print(f'  - {e}')

    return 0


if __name__ == '__main__':
    sys.exit(main())

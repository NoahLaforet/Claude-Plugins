#!/usr/bin/env python3
"""Populate the entities: frontmatter field in chat files.

For every chat in 01 - Chats/ this script:
  1. Builds the candidate entity set from:
       - 05 - Entities/*.md filenames (stems)
       - 02 - Projects/*.md filenames (stems)
       - tool/* and project/* tags already in the chat's frontmatter
       - the project: frontmatter field
  2. Matches candidate names whole-word, case-insensitive against the
     chat's title + summary + themes fields.
  3. Writes a deduped entities: [...] YAML line immediately after the
     tags: line (creates it if absent; merges if already present).

Safe to run repeatedly -- merges rather than clobbers. Existing entity
entries that don't match the auto-detection are preserved.

Usage:
  python3 scripts/populate_entities.py           # update all chats
  python3 scripts/populate_entities.py --dry-run # report changes only
  python3 scripts/populate_entities.py --verbose # show per-chat detail
"""
from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _vault_path import VAULT  # noqa

CHATS = VAULT / '01 - Chats'
ENTITIES_DIR = VAULT / '05 - Entities'
PROJECTS_DIR = VAULT / '02 - Projects'


def entity_names_from_vault() -> list[str]:
    """Return all entity page stems (skipping _Index)."""
    return [p.stem for p in ENTITIES_DIR.glob('*.md') if p.stem != '_Index']


def project_names_from_vault() -> list[str]:
    """Return all project page stems (skipping _Index)."""
    return [p.stem for p in PROJECTS_DIR.glob('*.md') if p.stem != '_Index']


def fm_and_body(text: str) -> tuple[str, str] | None:
    """Split YAML frontmatter from body. Returns None if no frontmatter."""
    if not text.startswith('---'):
        return None
    end = text.find('\n---', 3)
    if end < 0:
        return None
    return text[3:end], text[end + 4:]


def get_field(fm: str, key: str) -> str:
    m = re.search(rf'(?m)^{re.escape(key)}:\s*(.*)$', fm)
    return (m.group(1) if m else '').strip()


def get_list_field(fm: str, key: str) -> list[str]:
    raw = get_field(fm, key)
    if not raw or raw in ('[]', ''):
        return []
    if raw.startswith('['):
        return [s.strip().strip('"').strip("'") for s in raw[1:-1].split(',') if s.strip()]
    return [raw.strip('"').strip("'")]


def build_word_pattern(name: str) -> re.Pattern:
    """Whole-word case-insensitive regex for a candidate name."""
    escaped = re.escape(name)
    return re.compile(rf'(?<![a-zA-Z0-9_]){escaped}(?![a-zA-Z0-9_])', re.IGNORECASE)


def tag_to_name(tag: str) -> str | None:
    """Convert a tool/ or project/ tag to a display name, or return None."""
    for prefix in ('tool/', 'project/'):
        if tag.startswith(prefix):
            raw = tag[len(prefix):]
            return raw.replace('-', ' ').replace('_', ' ').strip()
    return None


def fmt_entities_line(names: list[str]) -> str:
    inner = ', '.join(f'"{n}"' for n in names)
    return f'entities: [{inner}]'


def detect_entities(fm: str, entity_vocab: list[str]) -> list[str]:
    """Return entity names that appear in title/summary/themes of this chat."""
    title = get_field(fm, 'title').strip('"').strip("'")
    summary = get_field(fm, 'summary').strip('"').strip("'")
    themes_raw = get_field(fm, 'themes')
    themes = re.sub(r'\[\[|\]\]|\*\*', '', themes_raw)
    haystack = ' '.join([title, summary, themes])

    found: list[str] = []
    for name in entity_vocab:
        pat = build_word_pattern(name)
        if pat.search(haystack):
            found.append(name)
    return found


def extra_names_from_tags(fm: str) -> list[str]:
    """Collect entity-like names from tool/* and project/* tags and project: field."""
    tags = get_list_field(fm, 'tags')
    names: list[str] = []
    for t in tags:
        n = tag_to_name(t)
        if n:
            names.append(n)
    proj_field = get_field(fm, 'project').strip('"').strip("'")
    proj_field = re.sub(r'\[\[|\]\]|\*\*', '', proj_field).strip()
    if proj_field:
        names.append(proj_field)
    return names


def merge_entities(existing: list[str], detected: list[str]) -> list[str]:
    """Merge two entity lists, preserving existing order and deduplicating."""
    seen: set[str] = set()
    out: list[str] = []
    for n in existing + detected:
        key = n.lower()
        if key not in seen:
            seen.add(key)
            out.append(n)
    return out


def patch_entities(path: Path, new_entities: list[str], dry_run: bool) -> bool:
    """Rewrite or insert the entities: line in the chat's frontmatter."""
    text = path.read_text(encoding='utf-8', errors='replace')
    parts = fm_and_body(text)
    if parts is None:
        return False
    fm, body = parts

    new_line = fmt_entities_line(new_entities)
    entities_pat = re.compile(r'(?m)^entities:.*$')

    if entities_pat.search(fm):
        current_line = entities_pat.search(fm).group(0)
        if current_line == new_line:
            return False  # already correct
        new_fm = entities_pat.sub(new_line, fm, count=1)
    else:
        # Insert after the tags: line
        tags_pat = re.compile(r'(?m)^(tags:.*)$')
        if tags_pat.search(fm):
            new_fm = tags_pat.sub(r'\1\n' + new_line, fm, count=1)
        else:
            # No tags: line -- append at end of frontmatter
            new_fm = fm.rstrip('\n') + f'\n{new_line}'

    if new_fm == fm:
        return False

    if not dry_run:
        path.write_text(f'---{new_fm}\n---{body}', encoding='utf-8')
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--dry-run', action='store_true',
                    help='report changes without writing files')
    ap.add_argument('--verbose', action='store_true',
                    help='print per-chat detail even when unchanged')
    args = ap.parse_args()

    entity_vocab = entity_names_from_vault()
    project_vocab = project_names_from_vault()
    all_vocab = entity_vocab + [p for p in project_vocab if p not in entity_vocab]

    changed = skipped = errors = 0
    for path in sorted(CHATS.glob('*.md')):
        try:
            text = path.read_text(encoding='utf-8', errors='replace')
        except OSError as e:
            print(f'  ! read error {path.name}: {e}', file=sys.stderr)
            errors += 1
            continue

        parts = fm_and_body(text)
        if parts is None:
            skipped += 1
            continue
        fm, _ = parts

        existing = get_list_field(fm, 'entities')
        detected = detect_entities(fm, all_vocab)
        from_tags = extra_names_from_tags(fm)

        vocab_lower = {n.lower(): n for n in all_vocab}
        validated_from_tags = [
            vocab_lower[n.lower()] for n in from_tags
            if n.lower() in vocab_lower
        ]

        merged = merge_entities(existing, detected + validated_from_tags)
        merged.sort()

        was_changed = patch_entities(path, merged, dry_run=args.dry_run)
        if was_changed:
            changed += 1
            if args.dry_run or args.verbose:
                print(f'  {"[dry]" if args.dry_run else "[upd]"} {path.name[:70]}')
                print(f'       was: {existing}')
                print(f'       now: {merged}')
        elif args.verbose:
            print(f'  [ok]  {path.name[:70]}  {merged}')

    tag = '[dry-run] ' if args.dry_run else ''
    print(f'{tag}Entities populated: {changed} chats updated, '
          f'{skipped} skipped (no frontmatter), {errors} errors.')
    return 0


if __name__ == '__main__':
    sys.exit(main())

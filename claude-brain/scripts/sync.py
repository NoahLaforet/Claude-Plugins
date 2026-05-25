#!/usr/bin/env python3
"""One-command sync: claude.ai -> vault.

Usage:
    python3 scripts/sync.py            # fetch + ingest + classify new chats
    python3 scripts/sync.py --no-classify   # skip the classification step
    python3 scripts/sync.py --dry-run       # list new chats without writing

First-time setup:
    1. cp scripts/sync_config.example.json scripts/sync_config.json
    2. Edit sync_config.json -- paste your claude.ai sessionKey cookie.
    3. (optional) export ANTHROPIC_API_KEY=sk-ant-... for auto-classification.
"""
from __future__ import annotations
import argparse
import gzip
import io
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _vault_path import VAULT  # noqa
from extract import write_chat, CHATS_DIR  # noqa
from auto_save import existing_chat_uuids  # noqa

META = VAULT / '_meta'
CONFIG = Path(__file__).parent / 'sync_config.json'
CHAT_META = META / 'chat_metadata.json'
CLUSTERS = META / 'clusters.json'

API_BASE = 'https://claude.ai'
USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36'


# ---------- config ----------

def load_config() -> dict:
    if not CONFIG.exists():
        print(f'Missing config: {CONFIG}', file=sys.stderr)
        print('', file=sys.stderr)
        print('Run:', file=sys.stderr)
        print(f'  cp {Path(__file__).parent}/sync_config.example.json {CONFIG}', file=sys.stderr)
        print('  (then edit it and paste your claude.ai sessionKey cookie)', file=sys.stderr)
        sys.exit(1)
    cfg = json.loads(CONFIG.read_text())
    key = (cfg.get('session_key') or '').strip()
    if not key or 'PASTE' in key:
        print(f'Edit {CONFIG} and paste a real sessionKey value.', file=sys.stderr)
        sys.exit(1)
    return cfg


def save_config(cfg: dict) -> None:
    CONFIG.write_text(json.dumps(cfg, indent=2))


def _config_api_key() -> str | None:
    if not CONFIG.exists():
        return None
    try:
        return (json.loads(CONFIG.read_text()).get('anthropic_api_key') or '').strip() or None
    except Exception:
        return None


# ---------- claude.ai API ----------

def api_get(path: str, session_key: str):
    url = f'{API_BASE}{path}'
    req = urllib.request.Request(url, headers={
        'Cookie': f'sessionKey={session_key}',
        'User-Agent': USER_AGENT,
        'Accept': 'application/json',
        'Accept-Encoding': 'gzip',
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            if resp.headers.get('Content-Encoding') == 'gzip':
                raw = gzip.decompress(raw)
            return json.loads(raw.decode('utf-8'))
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            print('\n401/403 from claude.ai -- your sessionKey cookie expired.', file=sys.stderr)
            print('Open claude.ai in a browser, copy a fresh sessionKey from DevTools', file=sys.stderr)
            print(f'(Application -> Cookies), paste it into {CONFIG}, rerun.', file=sys.stderr)
            sys.exit(2)
        body = e.read().decode('utf-8', errors='replace')[:400]
        print(f'HTTP {e.code} for {url}\n{body}', file=sys.stderr)
        sys.exit(2)


def discover_org(session_key: str) -> str:
    orgs = api_get('/api/organizations', session_key)
    if not orgs:
        print('No organizations returned for this account.', file=sys.stderr)
        sys.exit(2)
    if len(orgs) > 1:
        print('Multiple orgs found; picking the first. Override in sync_config.json:', file=sys.stderr)
        for o in orgs:
            print(f'  {o.get("uuid")}  {o.get("name")}', file=sys.stderr)
    return orgs[0]['uuid']


def list_conversations(session_key: str, org_uuid: str) -> list[dict]:
    return api_get(f'/api/organizations/{org_uuid}/chat_conversations', session_key)


def fetch_conversation(session_key: str, org_uuid: str, chat_uuid: str) -> dict:
    return api_get(
        f'/api/organizations/{org_uuid}/chat_conversations/{chat_uuid}'
        '?tree=True&rendering_mode=messages&render_all_tools=true',
        session_key,
    )


# ---------- classification ----------

def load_taxonomy_context() -> dict:
    clusters = json.loads(CLUSTERS.read_text()) if CLUSTERS.exists() else {}
    cluster_names = sorted(clusters.keys())
    return {
        'clusters': cluster_names,
        'cluster_examples': {
            name: [e.get('summary', '')[:80] for e in entries[:2]]
            for name, entries in clusters.items() if entries
        },
    }


CLASSIFY_SYSTEM = """You classify a Claude.ai chat into an existing taxonomy.

Output strict JSON only -- no prose, no markdown fences -- matching this schema:
{
  "cluster": "<one of the existing cluster names, or 'Miscellaneous' if none fit>",
  "themes": ["<1-3 short theme phrases, title case>"],
  "tags": ["<2-5 tags from the existing tag families: type/, topic/, domain/, tool/, status/, project/>"],
  "entities": ["<0-8 named entities: people, tools, courses, projects>"]
}

Prefer existing cluster names over creating new ones. Only use 'Miscellaneous' if genuinely none fit."""


def classify_chat(title: str, summary: str, first_turns: str, taxonomy: dict) -> dict | None:
    try:
        import anthropic
    except ImportError:
        return None
    key = os.environ.get('ANTHROPIC_API_KEY') or _config_api_key()
    if not key:
        return None

    client = anthropic.Anthropic(api_key=key)
    user_msg = (
        f'Existing clusters:\n- ' + '\n- '.join(taxonomy['clusters']) + '\n\n'
        f'Chat title: {title}\n'
        f'Summary: {summary}\n\n'
        f'First messages (excerpt):\n{first_turns[:2000]}\n\n'
        'Classify as JSON.'
    )
    try:
        resp = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=400,
            system=CLASSIFY_SYSTEM,
            messages=[{'role': 'user', 'content': user_msg}],
        )
        text = ''.join(b.text for b in resp.content if hasattr(b, 'text')).strip()
        text = re.sub(r'^```(?:json)?\s*|\s*```$', '', text, flags=re.M)
        return json.loads(text)
    except Exception as e:
        print(f'  ! classify failed: {e}', file=sys.stderr)
        return None


# ---------- metadata + frontmatter patching ----------

def summary_and_first_turns(conv: dict) -> tuple[str, str]:
    summary = (conv.get('summary') or '').strip()
    parts = []
    for m in conv.get('chat_messages', [])[:4]:
        sender = m.get('sender', '?')
        content = m.get('content') or []
        text = ''
        if isinstance(content, list):
            for b in content:
                if isinstance(b, dict) and b.get('type') == 'text':
                    text += b.get('text', '')
        if not text:
            text = m.get('text', '')
        parts.append(f'[{sender}] {text[:400]}')
    return summary, '\n'.join(parts)


def patch_frontmatter(chat_path: Path, classification: dict) -> None:
    """Rewrite tags / themes / cluster in the chat file's frontmatter."""
    text = chat_path.read_text(encoding='utf-8')
    if not text.startswith('---'):
        return
    end = text.find('\n---', 3)
    if end < 0:
        return
    fm = text[3:end]
    body = text[end + 4:]

    cluster = classification.get('cluster', 'Miscellaneous')
    themes = classification.get('themes') or []
    tags = classification.get('tags') or []

    def set_field(fm_text: str, field: str, value: str) -> str:
        pat = re.compile(rf'^{field}:.*$', re.M)
        if pat.search(fm_text):
            return pat.sub(f'{field}: {value}', fm_text, count=1)
        return fm_text + f'\n{field}: {value}'

    def fmt_list(items: list[str]) -> str:
        return '[' + ', '.join(f'"{i}"' for i in items) + ']'

    fm = set_field(fm, 'tags', fmt_list(tags))
    fm = set_field(fm, 'themes', fmt_list([cluster] + themes))
    fm = set_field(fm, 'cluster', f'"[[{cluster}]]"')
    chat_path.write_text(f'---{fm}\n---{body}', encoding='utf-8')


def update_meta_files(entries: list[dict]) -> None:
    """Append new entries to chat_metadata.json and clusters.json."""
    meta_list = json.loads(CHAT_META.read_text()) if CHAT_META.exists() else []
    meta_by_uuid = {d['uuid']: d for d in meta_list}
    clusters = json.loads(CLUSTERS.read_text()) if CLUSTERS.exists() else {}

    for e in entries:
        meta_by_uuid[e['uuid']] = {
            'uuid': e['uuid'],
            'filename': e['filename'],
            'summary': e['summary'],
            'proposed_themes': e['themes'],
            'proposed_tags': e['tags'],
            'entities': e['entities'],
            'project_guess': '',
            'cluster': e['cluster'],
        }
        cluster_name = e['cluster']
        clusters.setdefault(cluster_name, [])
        if not any(x['uuid'] == e['uuid'] for x in clusters[cluster_name]):
            clusters[cluster_name].append({
                'uuid': e['uuid'],
                'filename': e['filename'],
                'summary': e['summary'],
                'themes': e['themes'],
            })

    CHAT_META.write_text(json.dumps(list(meta_by_uuid.values()), indent=2, ensure_ascii=False))
    CLUSTERS.write_text(json.dumps(clusters, indent=2, ensure_ascii=False))


# ---------- main ----------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--no-classify', action='store_true', help='skip auto-classification')
    ap.add_argument('--dry-run', action='store_true', help='list new chats, do not write')
    args = ap.parse_args()

    cfg = load_config()
    session = cfg['session_key']

    if not cfg.get('org_uuid'):
        cfg['org_uuid'] = discover_org(session)
        save_config(cfg)
        print(f'Discovered org_uuid: {cfg["org_uuid"]}')
    org = cfg['org_uuid']

    print('Listing conversations from claude.ai...')
    convs = list_conversations(session, org)
    print(f'  {len(convs)} total on server')

    have = existing_chat_uuids()
    new = [c for c in convs if c['uuid'] not in have]
    if not new:
        print('Up to date. No new chats.')
        return 0

    print(f'  {len(new)} new')
    if args.dry_run:
        for c in new:
            print(f'    - {c.get("name") or "(untitled)"}  [{c["uuid"][:8]}]')
        return 0

    taxonomy = load_taxonomy_context()
    classify = not args.no_classify and (os.environ.get('ANTHROPIC_API_KEY') or _config_api_key())
    if not classify and not args.no_classify:
        print('  (no ANTHROPIC_API_KEY -- skipping classification; chats will ingest raw)')

    meta_entries = []
    for c in new:
        print(f'  fetching {c.get("name") or c["uuid"][:8]!r}...')
        try:
            full = fetch_conversation(session, org, c['uuid'])
        except SystemExit:
            raise
        except Exception as e:
            print(f'  ! fetch failed: {e}', file=sys.stderr)
            continue

        path = write_chat(full, project_name_by_uuid={})

        classification = None
        if classify:
            summary, first_turns = summary_and_first_turns(full)
            classification = classify_chat(full.get('name', ''), summary, first_turns, taxonomy)
            if classification:
                patch_frontmatter(path, classification)

        if classification:
            meta_entries.append({
                'uuid': full['uuid'],
                'filename': path.name,
                'summary': full.get('summary') or '',
                'themes': classification.get('themes') or [],
                'tags': classification.get('tags') or [],
                'entities': classification.get('entities') or [],
                'cluster': classification.get('cluster', 'Miscellaneous'),
            })

    if meta_entries:
        update_meta_files(meta_entries)
        print(f'\nClassified + linked {len(meta_entries)} chats into MOCs via Dataview.')

    # Populate entities field for any chats that landed without one.
    try:
        result = subprocess.run(
            [sys.executable, str(Path(__file__).parent / 'populate_entities.py')],
            capture_output=True, text=True, timeout=60,
        )
        if result.stdout.strip():
            print(result.stdout.strip())
        if result.stderr.strip():
            print(f'  (populate_entities stderr: {result.stderr.strip()})', file=sys.stderr)
    except Exception as _e:
        print(f'  (populate_entities warning: {_e})', file=sys.stderr)

    print(f'Done. Ingested {len(new)} chats.')
    return 0


if __name__ == '__main__':
    sys.exit(main())

#!/usr/bin/env python3
"""Phase 2: Synthesize discovery results into final taxonomy + cluster list.

Run this after you have batch-classified chats (e.g. by running the Anthropic
batch API or manually annotating). Reads intermediate JSON files, assigns each
chat to a cluster, and writes:
  - _meta/chat_metadata.json  (full per-chat metadata)
  - _meta/clusters.json       (chats grouped by cluster)
  - _meta/entities.json       (entities mentioned in 2+ chats)

Usage:
    python3 scripts/synthesize.py

Input: _meta/chat_metadata.json must already exist with proposed_tags,
proposed_themes, entities, and uuid fields per entry. If you are starting
from a batch-API run, merge your batch output files into chat_metadata.json
first, then run this script.
"""
import json
import re as _re
from pathlib import Path
from collections import Counter, defaultdict
import sys

sys.path.insert(0, str(Path(__file__).parent))
from _vault_path import VAULT  # noqa

META = VAULT / '_meta'
META.mkdir(parents=True, exist_ok=True)

CHAT_META_PATH = META / 'chat_metadata.json'
if not CHAT_META_PATH.exists():
    print(f'Missing: {CHAT_META_PATH}')
    print('Run extract.py (and optionally classify via the Anthropic batch API) first.')
    sys.exit(1)

all_chats = json.loads(CHAT_META_PATH.read_text(encoding='utf-8'))

UUID_RE = _re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
all_chats = [c for c in all_chats if UUID_RE.match(c.get('uuid', ''))]
print(f'Total chats: {len(all_chats)}')

# Tag normalization -- collapse common variants
TAG_NORMALIZE: dict[str, str] = {
    'type/programming': 'topic/programming',
    'domain/engineering': 'topic/engineering',
}


def normalize_tag(t: str) -> str:
    t = t.strip().lower().replace(' ', '-')
    return TAG_NORMALIZE.get(t, t)


for c in all_chats:
    c['proposed_tags'] = sorted({normalize_tag(t) for t in c.get('proposed_tags', [])})
    c['proposed_themes'] = [t.strip() for t in c.get('proposed_themes', []) if t.strip()]


# -----------------------------------------------------------------------
# Cluster rules -- customize this section for your own interests/projects.
# Order matters: first match wins.
# Each rule has a name plus any of: tags (match on tag prefixes),
# theme_keywords (match anywhere in theme text), entity_keywords.
# -----------------------------------------------------------------------
CLUSTER_RULES = [
    ('VLSI & Digital Circuits', {
        'tags': ['domain/vlsi', 'domain/circuits', 'domain/electronics'],
        'theme_keywords': ['vlsi', 'cmos', 'transistor', 'timing', 'circuit', 'logical effort',
                           'gate sizing', 'spice', 'sky130', 'ic layout', 'digital logic',
                           'digital design', 'tinytapeout', 'verilog', 'eda', 'openroad'],
    }),
    ('Claude & AI Tooling', {
        'tags': ['tool/claude-code', 'tool/claude'],
        'theme_keywords': ['claude', 'skill', 'ai', 'mcp', 'agent', 'obsidian', 'second brain'],
        'entity_keywords': ['claude', 'claude.ai', 'obsidian'],
    }),
    ('Web Development', {
        'tags': ['domain/webdev'],
        'theme_keywords': ['api', 'webdev', 'fastapi', 'http', 'frontend', 'backend', 'server'],
    }),
    ('Job Search & Career', {
        'theme_keywords': ['job application', 'job search', 'application pipeline',
                           'resume', 'cover letter', 'interview'],
    }),
    ('Academics & Coursework', {
        'tags': ['topic/academics', 'type/homework'],
        'theme_keywords': ['exam preparation', 'homework', 'lecture', 'study guide'],
    }),
    ('Writing & Research', {
        'theme_keywords': ['writing', 'research paper', 'essay', 'outline', 'manuscript'],
    }),
    ('Personal & Entertainment', {
        'tags': ['domain/entertainment', 'domain/gaming', 'topic/gaming'],
        'theme_keywords': ['gaming', 'minecraft', 'music', 'entertainment', 'golf'],
    }),
    ('Productivity & Automation', {
        'tags': ['tool/applescript', 'tool/google-drive'],
        'theme_keywords': ['automation', 'applescript', 'google drive', 'ssh', 'workflow'],
    }),
    ('Debugging & Troubleshooting', {
        'tags': ['type/debug'],
        'theme_keywords': ['debug', 'troubleshoot', 'error', 'fix'],
    }),
]


def assign_cluster(chat: dict) -> str:
    tags = set(chat.get('proposed_tags', []))
    themes_lower = ' '.join(chat.get('proposed_themes', [])).lower()
    entities_lower = ' '.join(chat.get('entities', [])).lower()
    for name, rule in CLUSTER_RULES:
        if any(t in tags for t in rule.get('tags', [])):
            return name
        if any(k in themes_lower for k in rule.get('theme_keywords', [])):
            return name
        if any(k in entities_lower for k in rule.get('entity_keywords', [])):
            return name
    return 'Miscellaneous'


# Assign clusters
cluster_chats: dict[str, list] = defaultdict(list)
for c in all_chats:
    cluster = assign_cluster(c)
    c['cluster'] = cluster
    cluster_chats[cluster].append(c)

# Build final taxonomy
all_tags: Counter = Counter()
for c in all_chats:
    for t in c.get('proposed_tags', []):
        all_tags[t] += 1

# Write outputs
CHAT_META_PATH.write_text(json.dumps(all_chats, indent=2, ensure_ascii=False), encoding='utf-8')

clusters_out = {
    name: [{'uuid': c['uuid'], 'filename': c.get('filename', ''),
            'summary': c.get('summary', ''),
            'themes': c.get('proposed_themes', [])} for c in chats]
    for name, chats in cluster_chats.items()
}
(META / 'clusters.json').write_text(json.dumps(clusters_out, indent=2, ensure_ascii=False), encoding='utf-8')

# Collect all unique entities appearing 2+ times
ent_c: Counter = Counter()
for c in all_chats:
    for e in c.get('entities', []):
        ent_c[e] += 1
top_entities = {e: n for e, n in ent_c.items() if n >= 2}
(META / 'entities.json').write_text(json.dumps(top_entities, indent=2, ensure_ascii=False), encoding='utf-8')

print('\n=== Cluster distribution ===')
for name in [r[0] for r in CLUSTER_RULES] + ['Miscellaneous']:
    print(f'  {len(cluster_chats.get(name, [])):3d}  {name}')

print(f'\n=== Final tag count: {len(all_tags)} ===')
print(f'Entities with 2+ mentions: {len(top_entities)}')
print('\nWrote:')
print(f'  {CHAT_META_PATH}')
print(f'  {META}/clusters.json')
print(f'  {META}/entities.json')

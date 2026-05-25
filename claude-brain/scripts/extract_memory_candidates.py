#!/usr/bin/env python3
"""Scan recent chats for memory-worthy signals and queue them for triage.

Looks for high-signal phrases (preferences, corrections, repeated patterns,
project state changes) in chat content since the last run, and writes a queue
to /tmp/claude_brain_memory_candidates.json that the SessionStart hook surfaces
for the live Claude to triage.

Why deterministic: this runs at Stop time (no live model) and from launchd
(no live model). The live model does the actual judgment call at SessionStart
by reading the queue.

State file: ~/.claude/checkpoints/.memory_extract_state.json
    {"last_seen_mtime": <unix-time>}

Output: /tmp/claude_brain_memory_candidates.json
    [{"chat": "<filename>", "type": "feedback|user|project|reference",
      "snippet": "<verbatim line>", "context": "<surrounding turn>"}]
"""
from __future__ import annotations
import json
import re
import time
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from _vault_path import VAULT  # noqa

CHATS = VAULT / '01 - Chats'
STATE = Path.home() / '.claude' / 'checkpoints' / '.memory_extract_state.json'
QUEUE = Path('/tmp/claude_brain_memory_candidates.json')

# Phrase patterns that signal memory-worthy content. Tuned to be high-precision
# rather than high-recall -- a missed signal is fine; a wrong one wastes
# the user's attention at SessionStart.
PATTERNS: list[tuple[str, re.Pattern]] = [
    # Direct preference statements
    ('feedback', re.compile(
        r"\b(don\'t|do not|never|stop) (?:do|use|create|write|add|run|make|tell|mention|reference|bring up)\b",
        re.I)),
    ('feedback', re.compile(
        r'\b(always|every time|from now on|going forward) (?:do|use|run|create|make|prefer|use)\b',
        re.I)),
    ('feedback', re.compile(
        r"\bi (?:hate|love|prefer|want|like|don\'t want|need) (?:you|claude|that|when|the)\b",
        re.I)),
    ('feedback', re.compile(
        r'\b(stop|wait) (?:doing|saying|writing)\b', re.I)),

    # Project state changes
    ('project', re.compile(
        r'\b(?:we|i) (?:finished|shipped|deployed|merged|completed|paused|killed)\b',
        re.I)),
    ('project', re.compile(
        r'\b(?:next step|next up|tomorrow|this week|by friday|deadline)\b', re.I)),

    # Identity / self-knowledge
    ('user', re.compile(
        r"\bi (?:am|'m) (?:a|an|the|currently)\b", re.I)),
    ('user', re.compile(
        r'\bmy (?:role|job|favorite|preferred|usual) ', re.I)),
    ('user', re.compile(
        r'\bi (?:graduate|graduated|interned|work)\b', re.I)),

    # External resources to remember
    ('reference', re.compile(
        r'\b(?:github\.com|gitlab\.com|drive\.google\.com|notion\.so|linear\.app)\S+',
        re.I)),
    ('reference', re.compile(
        r'\b(?:lives at|see|check) [`"]?(/[^`"\s]+|~/[^`"\s]+)', re.I)),
]

# Phrases that almost always indicate noise -- drop matches containing these.
NOISE = re.compile(
    r'<system-reminder>|<local-command|<command-message>|'
    r'> \[!example\]|> \[!success\]|^```|tool_use|tool_result',
    re.I)

SNIPPET_MAX = 280
CONTEXT_MAX = 600
MAX_CANDIDATES = 50


def load_state() -> dict:
    if STATE.exists():
        try:
            return json.loads(STATE.read_text())
        except json.JSONDecodeError:
            pass
    return {'last_seen_mtime': 0.0}


def save_state(d: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(d, indent=2))


def fm_field(text: str, key: str) -> str:
    m = re.search(rf'(?m)^{key}:\s*(.+)$', text)
    return m.group(1).strip() if m else ''


def split_turns(body: str) -> list[tuple[str, str, str]]:
    """Yield (role, timestamp, text) per turn from a chat body."""
    out = []
    for m in re.finditer(
        r'### (Human|Assistant) -- ([0-9T:\- UTC]+)\n\n(.*?)\n\n---',
        body, re.S,
    ):
        role = 'user' if 'Human' in m.group(1) else 'assistant'
        out.append((role, m.group(2).strip(), m.group(3).strip()))
    return out


def extract_from_chat(path: Path) -> list[dict]:
    text = path.read_text(encoding='utf-8', errors='replace')
    body = text.split('\n---\n', 1)[-1] if text.startswith('---') else text
    candidates: list[dict] = []
    for role, ts, content in split_turns(body):
        if NOISE.search(content):
            continue
        # Limit signal mining to user turns + concise assistant statements
        if role == 'assistant' and len(content) > 1500:
            continue
        for kind, pat in PATTERNS:
            for hit in pat.finditer(content):
                start = max(0, hit.start() - 120)
                end = min(len(content), hit.end() + 120)
                ctx = content[start:end]
                if NOISE.search(ctx):
                    continue
                candidates.append({
                    'chat': path.name,
                    'role': role,
                    'timestamp': ts,
                    'type': kind,
                    'match': hit.group(0)[:SNIPPET_MAX],
                    'context': ctx[:CONTEXT_MAX],
                })
    return candidates


def main() -> int:
    state = load_state()
    last_seen = float(state.get('last_seen_mtime', 0))
    now = time.time()

    candidates: list[dict] = []
    newest_mtime = last_seen
    for p in sorted(CHATS.glob('*.md'), key=lambda x: x.stat().st_mtime):
        m = p.stat().st_mtime
        if m <= last_seen:
            continue
        try:
            candidates.extend(extract_from_chat(p))
        except OSError:
            continue
        if m > newest_mtime:
            newest_mtime = m
        if len(candidates) >= MAX_CANDIDATES:
            break

    candidates = candidates[:MAX_CANDIDATES]
    QUEUE.parent.mkdir(parents=True, exist_ok=True)
    QUEUE.write_text(json.dumps(candidates, indent=2, ensure_ascii=False))

    # Always advance state to "now" -- even if no candidates this run, we
    # don't want to re-scan the same chats next time.
    save_state({'last_seen_mtime': max(newest_mtime, now)})
    print(f'Queued {len(candidates)} memory candidate(s) -> {QUEUE}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

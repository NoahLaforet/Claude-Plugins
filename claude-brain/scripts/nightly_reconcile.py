#!/usr/bin/env python3
"""Nightly reconcile -- runs every night (e.g. at 23:00 via launchd).

Job: heuristically classify any chats that landed without a cluster
during the day and refresh the memory mirror. Catches anything missed
by the Stop hook (extract failures, race conditions, manual drops).
Idempotent.

Logs to _meta/nightly.log.

Install the launchd plist from templates/ to run automatically.
"""
from __future__ import annotations
import subprocess
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
from _vault_path import VAULT  # noqa

META = VAULT / '_meta'
LOG = META / 'nightly.log'
PY = sys.executable  # use the same python3 that launched this script


def run(label: str, args: list[str]) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open('a') as f:
        f.write(f'\n--- {label} ---\n')
        result = subprocess.run([PY] + args, capture_output=True, text=True)
        f.write(result.stdout)
        if result.stderr:
            f.write('STDERR: ' + result.stderr)


def main() -> int:
    scripts = Path(__file__).parent
    with LOG.open('a') as f:
        f.write(f'\n=== {datetime.now().isoformat()} nightly_reconcile ===\n')
    run('extract_code',      [str(scripts / 'extract_code.py'), '--no-classify'])
    run('auto_save',         [str(scripts / 'auto_save.py')])
    run('auto_classify',     [str(scripts / 'auto_classify.py')])
    run('populate_entities', [str(scripts / 'populate_entities.py')])
    run('sync_memory',       [str(scripts / 'sync_memory.py')])
    return 0


if __name__ == '__main__':
    sys.exit(main())

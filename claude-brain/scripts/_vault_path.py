"""Shared vault-path resolver for claude-brain pipeline scripts.

Priority order:
  1. Environment variable CLAUDE_BRAIN_VAULT (user sets this once)
  2. Auto-detect: parent directory of the scripts/ folder that contains this file

Usage inside any pipeline script:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))
    from _vault_path import VAULT
"""
import os
from pathlib import Path

def _resolve() -> Path:
    env = os.environ.get('CLAUDE_BRAIN_VAULT', '').strip()
    if env:
        return Path(env).expanduser()
    # Auto-detect: scripts/ lives directly inside the vault's _meta/ folder,
    # or the kit was placed at <vault>/_meta/. Walk up two levels to find vault.
    here = Path(__file__).resolve().parent   # scripts/ (or _meta/)
    parent = here.parent                      # presumed vault root
    return parent

VAULT = _resolve()

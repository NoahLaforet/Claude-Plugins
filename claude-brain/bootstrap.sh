#!/usr/bin/env bash
# Claude Second Brain bootstrap -- creates vault, registers MCP, writes CLAUDE.md.
# Safe to re-run: skips steps that are already done, never overwrites silently.
set -euo pipefail

say()  { printf "\033[1;36m==>\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m!!\033[0m  %s\n" "$*" >&2; }
die()  { printf "\033[1;31mxx\033[0m  %s\n" "$*" >&2; exit 1; }

# -- prereqs -----------------------------------------------------------------
command -v python3 >/dev/null || die "python3 not found. Install Python 3.10+."
command -v mcp-obsidian >/dev/null || die "mcp-obsidian not found. Run: pipx install mcp-obsidian"
MCP_PATH="$(command -v mcp-obsidian)"

# -- prompts -----------------------------------------------------------------
DEFAULT_VAULT="$HOME/Desktop/Claude Brain"
read -r -p "Vault path [$DEFAULT_VAULT]: " VAULT
VAULT="${VAULT:-$DEFAULT_VAULT}"

read -r -p "Obsidian Local REST API key: " API_KEY
[[ -n "$API_KEY" ]] || die "API key is required."

read -r -p "Your first name (for CLAUDE.md): " USER_NAME
USER_NAME="${USER_NAME:-you}"

# -- vault folders -----------------------------------------------------------
say "Creating vault structure at: $VAULT"
mkdir -p "$VAULT"/{"00 - Maps of Content","01 - Chats","02 - Projects","03 - Memories","04 - Tags","05 - Entities",_meta}

HOME_MD="$VAULT/Home.md"
if [[ ! -f "$HOME_MD" ]]; then
  cat > "$HOME_MD" <<'EOF'
# Home

Your second brain. Drop Claude exports into this folder, run the extraction
pipeline in `_meta/scripts/`, and Claude Code will be able to search everything.

- `00 - Maps of Content/` -- big-idea landing pages
- `01 - Chats/` -- individual chat transcripts (YYYY-MM-DD - Title.md)
- `02 - Projects/` -- Claude Projects with system prompts
- `03 - Memories/` -- persistent memory extracts
- `04 - Tags/` -- tag taxonomy
- `05 - Entities/` -- per-person / per-thing pages
- `_meta/` -- extraction + sync scripts
EOF
fi

# -- copy scripts -----------------------------------------------------------
SCRIPTS_SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/scripts"
SCRIPTS_DEST="$VAULT/_meta/scripts"
if [[ -d "$SCRIPTS_SRC" ]]; then
  say "Copying pipeline scripts to: $SCRIPTS_DEST"
  mkdir -p "$SCRIPTS_DEST"
  cp -n "$SCRIPTS_SRC"/*.py "$SCRIPTS_DEST"/ 2>/dev/null || true
  cp -n "$SCRIPTS_SRC"/*.sh "$SCRIPTS_DEST"/ 2>/dev/null || true
  cp -n "$SCRIPTS_SRC/sync_config.example.json" "$SCRIPTS_DEST"/ 2>/dev/null || true
  chmod +x "$SCRIPTS_DEST"/*.sh 2>/dev/null || true
  # Set CLAUDE_BRAIN_VAULT in each shell script
  for sh in "$SCRIPTS_DEST"/*.sh; do
    [[ -f "$sh" ]] || continue
    sed -i '' "s|/path/to/vault|$VAULT|g" "$sh" 2>/dev/null || \
    sed -i  "s|/path/to/vault|$VAULT|g" "$sh" 2>/dev/null || true
  done
fi

# -- MCP registration (~/.claude.json) --------------------------------------
CLAUDE_JSON="$HOME/.claude.json"
say "Registering Obsidian MCP server in $CLAUDE_JSON"
python3 - "$CLAUDE_JSON" "$MCP_PATH" "$API_KEY" <<'PY'
import json, os, sys
path, mcp_path, api_key = sys.argv[1], sys.argv[2], sys.argv[3]
data = {}
if os.path.exists(path):
    with open(path) as f:
        try: data = json.load(f)
        except json.JSONDecodeError: data = {}
data.setdefault("mcpServers", {})
data["mcpServers"]["obsidian"] = {
    "type": "stdio",
    "command": mcp_path,
    "args": [],
    "env": {
        "OBSIDIAN_API_KEY": api_key,
        "OBSIDIAN_HOST": "127.0.0.1",
        "OBSIDIAN_PORT": "27124",
    },
}
with open(path, "w") as f:
    json.dump(data, f, indent=2)
print(f"  wrote mcpServers.obsidian -> {mcp_path}")
PY

# -- CLAUDE.md ---------------------------------------------------------------
CLAUDE_MD="$HOME/.claude/CLAUDE.md"
mkdir -p "$HOME/.claude"
if [[ -f "$CLAUDE_MD" ]]; then
  warn "$CLAUDE_MD already exists. Appending brain section if missing."
  if ! grep -q "Claude Second Brain" "$CLAUDE_MD" 2>/dev/null; then
    printf "\n\n" >> "$CLAUDE_MD"
    APPEND=1
  else
    APPEND=0
  fi
else
  APPEND=1
  : > "$CLAUDE_MD"
fi

if [[ "$APPEND" == "1" ]]; then
  cat >> "$CLAUDE_MD" <<EOF
## Claude Second Brain (Obsidian vault)

A long-term knowledge vault lives at \`$VAULT/\` and is exposed to Claude Code
through the \`obsidian\` MCP server (tools prefixed \`mcp__obsidian__*\`). The
vault contains $USER_NAME's Claude chat history, Projects, memories, and curated
"Map of Content" landing pages.

### When to consult the brain

Before answering questions that touch past work, prior decisions, or recurring
topics -- anything framed as "what did I...", "last time...", "remember when...",
"my notes on..." -- search the vault *first*.

### How to consult it

1. Use \`mcp__obsidian__obsidian_simple_search\` or
   \`mcp__obsidian__obsidian_complex_search\`.
2. Start with \`00 - Maps of Content/\` -- highest-signal entry points.
3. Read individual chats under \`01 - Chats/\` (filenames are
   \`YYYY-MM-DD - Title.md\`).
4. **Cite chat filenames inline** so $USER_NAME can click to open them, e.g.
   \`see [[2026-04-09 - Example chat title]]\`.

### When NOT to consult it

- Fresh questions with no historical dimension.
- Live-only info (current date, file system state, external APIs).
- Simple syntax/how-to questions that don't depend on $USER_NAME's history.
EOF
  say "Wrote brain instructions to $CLAUDE_MD"
fi

# -- .gitignore --------------------------------------------------------------
GITIGNORE="$VAULT/.gitignore"
if [[ ! -f "$GITIGNORE" ]]; then
  TEMPLATES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/templates"
  if [[ -f "$TEMPLATES_DIR/vault.gitignore" ]]; then
    cp "$TEMPLATES_DIR/vault.gitignore" "$GITIGNORE"
    say "Copied .gitignore to vault"
  fi
fi

# -- hooks snippet reminder ---------------------------------------------------
HOOKS_SNIPPET="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/templates/settings_hooks_snippet.json"

# -- done --------------------------------------------------------------------
say "Done."
cat <<EOF

Next steps:
  1. Make sure Obsidian is running with your vault open, and the
     "Local REST API" community plugin is ENABLED.
  2. Fully quit and relaunch Claude Code so it picks up the new MCP server.
  3. Test in a new Claude Code session:
       "Search my Obsidian vault for anything."
     You should see a mcp__obsidian__obsidian_simple_search call.
  4. Build your personal profile:
       Open a fresh Claude Code session and paste profile-interview.md.
  5. (Optional) Drop a Claude export into:
       $VAULT/Claude Data <date>/
     Then run:
       python3 "$VAULT/_meta/scripts/extract.py"
  6. (Optional) Wire up hooks for automatic ingestion. See:
       $HOOKS_SNIPPET

Enjoy.
EOF

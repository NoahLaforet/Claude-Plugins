# claude-brain

A self-hosted Obsidian vault that auto-ingests your Claude chat history,
classifies it, builds entities + Maps of Content, and backs up automatically.
Claude Code reads the vault through the Obsidian MCP server so it can cite
your past conversations during future sessions.

---

## What it does

1. **Ingests** your claude.ai exports and Claude Code session transcripts into
   per-chat Obsidian notes with structured YAML frontmatter.
2. **Classifies** each chat into a cluster (Hardware Projects, Web Dev,
   Academics, etc.) and tags it with a shared taxonomy.
3. **Builds entities and Maps of Content** so you can navigate your history
   by topic, project, or person.
4. **Syncs** your Claude Code auto-memory files into the vault so Obsidian can
   wikilink to them.
5. **Backs up** the vault to a private git repo automatically.
6. **Wires into Claude Code** via SessionStart, Stop, and PreCompact hooks so
   each session starts with "where you left off" context.

---

## Folder structure

```
<your-vault>/
├── Home.md                      dashboard
├── 00 - Maps of Content/        big-idea landing pages (auto-generated)
├── 01 - Chats/                  chat transcripts -- YYYY-MM-DD - Title.md
├── 02 - Projects/               Claude Projects with system prompts
├── 03 - Memories/               auto-memory mirror + claude.ai snapshots
├── 04 - Tags/                   tag taxonomy
├── 05 - Entities/               per-person / per-tool pages (optional)
├── _meta/
│   ├── scripts/                 pipeline scripts (from this repo)
│   ├── chat_metadata.json       per-chat metadata index
│   ├── clusters.json            chats grouped by cluster
│   └── audits/                  weekly audit reports
└── daily/                       morning daily notes (optional)
```

---

## Setup

### Prerequisites

- macOS (Linux works with path tweaks -- swap launchd for cron).
- [Obsidian](https://obsidian.md) (free).
- Claude Code (already installed if you're reading this).
- Python 3.10+: `python3 --version`
- pipx: `brew install pipx && pipx ensurepath`

### Step 1 -- Obsidian + Local REST API plugin

1. Install Obsidian. Create a new vault anywhere (e.g. `~/Desktop/Claude Brain`).
2. Settings -> Community plugins -> turn on Community plugins.
3. Browse -> search **"Local REST API"** (by Adam Coddington) -> Install -> Enable.
4. Open its settings -> copy the **API key**. Leave the HTTPS port as `27124`.
5. Keep Obsidian running whenever you want Claude to access the vault.

### Step 2 -- Install the Obsidian MCP server

```sh
pipx install mcp-obsidian
```

Confirm it's on your PATH: `which mcp-obsidian` should print something like
`/Users/you/.local/bin/mcp-obsidian`.

### Step 3 -- Run the bootstrap

```sh
git clone https://github.com/NoahLaforet/Claude-Plugins.git
cd Claude-Plugins/claude-brain
./bootstrap.sh
```

It asks for:
- Where to put your vault (default: `~/Desktop/Claude Brain`)
- Your Obsidian API key (from Step 1)
- Your first name (for the CLAUDE.md)

It then:
- Creates the vault folder structure
- Copies the pipeline scripts into `<vault>/_meta/scripts/`
- Registers the Obsidian MCP server in `~/.claude.json`
- Writes a starter `~/.claude/CLAUDE.md` with brain-consult instructions

### Step 4 -- Export your Claude history (optional)

1. Go to https://claude.ai -> Settings -> **Data privacy controls** -> **Export data**.
2. Wait for the email (minutes to hours), download and unzip it.
3. Move the unzipped folder into your vault, e.g.:
   `~/Desktop/Claude Brain/Claude Data 2026-05-01/`
4. Run the extraction pipeline:
   ```sh
   python3 <vault>/_meta/scripts/extract.py
   ```

### Step 5 -- Build your personal profile (don't skip)

The vault gives Claude your *history*. The profile gives Claude *you*.

Open a new Claude Code session and paste the contents of `profile-interview.md`
as your first message. Claude will interview you across 15 topic clusters and
save memory files as you answer. Read `PROFILE-GUIDE.md` for the full
explanation.

### Step 6 -- Verify

Restart Claude Code. In a new session, ask:

> Search my Obsidian vault for anything.

If it calls `mcp__obsidian__obsidian_simple_search` and returns results, you're
wired up. If you get "tool not available," check that Obsidian is running and
the API key in `~/.claude.json` matches the plugin's key.

---

## Pipeline scripts (scripts/)

| Script | Purpose |
|--------|---------|
| `extract.py` | Turn a claude.ai export into per-chat .md files |
| `extract_code.py` | Ingest Claude Code CLI session transcripts |
| `auto_save.py` | Incremental ingest -- only processes new chats |
| `sync.py` | Live pull from claude.ai via session cookie |
| `synthesize.py` | Assign clusters + build taxonomy from classified data |
| `apply_tags.py` | Write synthesized tags/themes to chat frontmatter |
| `classify_pending.py` | Classify unclassified chats using the live Claude session |
| `auto_classify.py` | Heuristic keyword classifier (runs at Stop time) |
| `sync_memory.py` | Mirror Claude Code auto-memory files into the vault |
| `populate_entities.py` | Auto-populate entities: frontmatter fields |
| `lint_vault.py` | Surface broken links, empty clusters, missing entity pages |
| `extract_memory_candidates.py` | Queue high-signal phrases for memory triage |
| `precompact_checkpoint.py` | Write checkpoint before context compaction |
| `nightly_reconcile.py` | Nightly catch-all: re-classify, sync, populate |
| `morning_agent.py` | Write daily note with activity rollup + checkpoint |
| `weekly_audit.py` | Weekly hygiene report -> _meta/audits/ |
| `git_backup.sh` | Push vault to private GitHub repo |
| `session_start_hook.sh` | SessionStart hook: ingest + surface context |
| `session_stop_hook.sh` | Stop hook: ingest + auto-classify |
| `sync_config.example.json` | Template for sync.py configuration |

---

## Automation (launchd on macOS)

Templates for all scheduled jobs live in `templates/`. Each plist has
`/path/to/vault` placeholders -- replace them with your actual vault path,
then install:

```sh
# Example: install the hourly sync agent
cp templates/com.claude-brain.sync.plist ~/Library/LaunchAgents/
# Edit the plist to set your vault path, then:
launchctl load ~/Library/LaunchAgents/com.claude-brain.sync.plist
```

Available plists:
- `com.claude-brain.sync.plist` -- hourly claude.ai sync
- `com.claude-brain.code-sync.plist` -- hourly Claude Code session ingest
- `com.claude-brain.autosave.plist` -- every 15 min export watcher
- `com.claude-brain.nightly.plist` -- nightly reconcile at 23:00
- `com.claude-brain.morning.plist` -- daily note at 08:00
- `com.claude-brain.weekly-audit.plist` -- audit on Sunday at 21:00
- `com.claude-brain.gitbackup.plist` -- git backup every 15 min

---

## Claude Code hooks

To have Claude Code automatically ingest sessions and surface context, add
the hooks from `templates/settings_hooks_snippet.json` to your
`~/.claude/settings.json`. Replace `/path/to/scripts` with the actual path.

Hooks wired:
- **SessionStart** -- ingest new sessions, surface pending classifications,
  memory candidates, and last checkpoint.
- **Stop** -- ingest session, heuristic-classify, sync memory.
- **PreCompact** -- write a checkpoint before context is compacted.

---

## Customization

- **Clusters**: edit `CLUSTER_RULES` in `scripts/synthesize.py` and
  `RULES` in `scripts/auto_classify.py` to match your interests/projects.
- **Tag families**: edit `cmd_list()` in `scripts/classify_pending.py`.
- **Project context in hooks**: edit the `project_files` dict in
  `scripts/session_start_hook.sh` to map cwd substrings to memory files.
- **CLAUDE.md**: edit `~/.claude/CLAUDE.md` freely -- it's your prompt.
  Adding bullet lists of active projects, recurring people, and key entities
  makes Claude's retrieval much sharper.

---

## Troubleshooting

**"Tool not available: mcp__obsidian__*"**
Obsidian isn't running, or the Local REST API plugin is disabled, or the API
key in `~/.claude.json` doesn't match the plugin.

**MCP server registered but no tools appear**
Fully quit and relaunch Claude Code (not just a new session -- the process).

**Obsidian API works in curl but not from Claude**
The plugin uses a self-signed cert on port 27124. `mcp-obsidian` handles this,
but custom clients need `-k` in curl. Verify with:

```sh
curl -k -H "Authorization: Bearer YOUR_KEY" https://127.0.0.1:27124/vault/
```

**Session start hook not firing**
`~/.claude/settings.json` needs the hook entry. See
`templates/settings_hooks_snippet.json` for the exact shape.

**sync.py returns 401**
Your sessionKey cookie expired. Open claude.ai in a browser, copy a fresh
sessionKey from DevTools (Application -> Cookies), paste it into
`scripts/sync_config.json`, rerun.

---

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `CLAUDE_BRAIN_VAULT` | auto-detected (parent of scripts/) | Override vault path |
| `CLAUDE_BRAIN_MEMORY_SOURCE` | auto-detected (~/.claude/projects/*/memory) | Override memory sync source |
| `ANTHROPIC_API_KEY` | (none) | Enable API-based chat classification |

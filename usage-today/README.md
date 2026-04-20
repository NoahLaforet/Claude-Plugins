# /usage-today — daily Claude Code usage readout

A single slash command that prints a one-screen summary of **everything you did
in Claude Code today**: cost, active time, tokens, cache-reuse %, which
projects you spent the most on, and your most-used tools.

It's a companion to the [statusbar](../statusbar) plugin — same visual style,
same pricing math, but aggregated across every session you've opened today
instead of just the current one.

## What it looks like

```
Usage — YYYY-MM-DD  (all Claude Code sessions, local time)
cost: $XX.XX │ active: XhYYm │ $X.X/hr │ sessions: N │ you: NN  claude: NNN │ span: HH:MM–HH:MM
input: XXM │ output: XM │ cache-read: XXM │ cache-write: XM │ reused: XX%
tool calls: NNN
by model: opus $XX.XX (XX%, NNNmsg)  sonnet $X.XX (XX%, NNmsg)
── by project ─────────────────────────────
  ███████░░░  $XX.XX  XX%  …/project-a  · XhYYm · NNNmsg · Nsess
  ███░░░░░░░  $XX.XX  XX%  …/project-b  · XhYYm · NNmsg · Nsess
top tools: Bash×NNN Edit×NN Read×NN Write×NN Grep×NN …
```

Bars, colors, and label thresholds mirror the statusbar so the two read as one
system.

## What each field means

**Header row — today at a glance**
- `cost: $X.XX` — total API-equivalent spend for today. Green <$20, yellow
  <$50, orange beyond.
- `active: XhYYm` — time actually spent working. Sums the gaps between events
  in each transcript; gaps longer than 5 minutes are treated as idle and
  skipped. Same method the statusbar uses for `time:`.
- `$X.X/hr` — burn rate (today's cost ÷ today's active hours).
- `sessions: N` — count of distinct Claude Code sessions with activity today.
- `you: N  claude: M` — prompts you sent / replies Claude sent back.
- `span: HH:MM–HH:MM` — first and last event timestamps of the day.

**Token row**
- `input` — tokens sent TO Claude (all sessions combined). Includes fresh
  input + cache reads + cache writes.
- `output` — tokens Claude wrote BACK (replies + tool arguments).
- `cache-read` / `cache-write` — prompt-cache traffic. Reads are ~90% cheaper
  than fresh input; writes are ~25% pricier but pay for themselves on reuse.
- `reused: XX%` — share of input that came from the cache. Green ≥90%,
  yellow ≥70%, red below. Low numbers = context is churning and costs are
  climbing.

**Tool row**
- `tool calls: N` — total Bash / Edit / Read / MCP / etc. invocations today.

**By-model row**
Cost and message count per model family (Opus / Sonnet / Haiku). Handy if
you're mixing models and want to see which one is driving the bill.

**By-project block**
Top 6 projects by spend, each with a proportional bar, dollar amount, share
of the day, active time, message count, and session count. "Project" here
means the per-directory folder Claude Code keeps under
`~/.claude/projects/<slug>/`.

**Top tools**
Most-used tool names with their call counts. Useful for noticing when a
session spent half its budget in `Bash` loops or `WebSearch` queries.

## How the math works

The script walks every `~/.claude/projects/*/*.jsonl` transcript whose mtime
falls within today, then for each event:

- Filters by the event's own timestamp being between local midnight and now.
- Counts prompts (user events with text content) and tool uses (assistant
  events containing a `tool_use` block).
- Sums `input_tokens`, `output_tokens`, `cache_read_input_tokens`, and
  `cache_creation_input_tokens` from each turn's `usage` field.
- Computes cost per turn from the model ID using the same pricing table as
  the statusbar (per 1M tokens):

| Model  | Input | Output | Cache read | Cache write |
|--------|------:|-------:|-----------:|------------:|
| Opus   | $15   | $75    | $1.50      | $18.75      |
| Sonnet | $3    | $15    | $0.30      | $3.75       |
| Haiku  | $1    | $5     | $0.10      | $1.25       |

Active time uses the same gap-accumulator as the statusbar's `time:` field:
sort event timestamps per session, sum gaps ≤ 5 minutes as working time.

Nothing gets written to disk — this is a pure read of your existing
transcripts, so it's safe to run as often as you want.

## Install

### One-command

```bash
./install.sh
```

That copies the two files into `~/.claude/` (script) and
`~/.claude/commands/` (slash-command template), makes them the right mode,
and tells you what to do next.

### Manual

```bash
mkdir -p ~/.claude/commands
cp usage_today.py   ~/.claude/usage_today.py
cp usage-today.md   ~/.claude/commands/usage-today.md
chmod +x ~/.claude/usage_today.py
```

Then reload Claude Code (or open a new session) and run:

```
/usage-today
```

## Requirements

- **Python 3.10+** — stdlib only, no external deps.
- **Claude Code** with session transcripts under `~/.claude/projects/`.
  That's the default install layout.
- Works on macOS and Linux. Windows not tested.

## Customization

**Different pricing or a new model family** — edit the `PRICING_PER_M` dict
and the `model_family()` matcher at the top of `usage_today.py`. Same
pattern as the statusbar.

**Change the idle gap** — the `300` seconds in `collect_today()` controls
what counts as "active time." Longer = more forgiving, shorter = stricter.

**Show more/fewer projects** — the `projects_sorted[:6]` slice in `render()`
caps the by-project list at 6. Raise or lower as you like.

**Hide the top-tools line** — delete the final `if d["tool_counts"]:` block
in `render()`.

## Files

- `usage_today.py` — the aggregator. Reads `~/.claude/projects/*/*.jsonl`,
  prints ANSI-colored text to stdout.
- `usage-today.md` — the Claude Code slash-command template. The `!` line
  inside it is what actually runs the script.
- `install.sh` — two-file copier.

## License

Do whatever you want with it.

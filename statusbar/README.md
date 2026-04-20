# Claude Code Rich Statusline

A three-line statusline for [Claude Code](https://claude.com/claude-code) with
live context usage, session cost, plan budget tracking, and a spinner that
shows what Claude is doing in real time.

## What it looks like

```
Opus 4.7  effort: xhigh │ context: [████░░] 70% 281K left │ month: $557/$100 557% │ ⠧ Bash
$2.150 $5.2/hr 25m │ input: 20.4M output: 445K reused: 95% │ ⎇ main ●3 │ you: 24 claude: 209
today: $66 │ time: 3h48m │ week: $557 │ all-time: $558 │ avg-session: $18 │ 7d-tokens: 154M
```

Everything updates live — the spinner (`⠏`) cycles every second and shows the
current tool name (`Edit`, `Bash`, `Grep`…) or `thinking` when between tools.
When idle it shows `○ idle`.

## What each field means

**Line 1 — live state**
- `Opus 4.7` — the active model
- `effort:xhigh` — reasoning depth (set via `effortLevel` in settings.json)
- `context:[bar] 70% 281K left` — context window REMAINING. Bar fills with
  how much you have left; green when healthy, red when running out.
  Denominator is 400K for Opus 4.x, 200K otherwise. This is NOT the 5-hour
  rate-limit session the Claude app shows — that's not exposed to statusline
  scripts.
- `month: $X/$100 N%` — this-month spend vs your plan budget. Both the
  dollar amount and the percentage are colored by spend tier: green <50%,
  yellow <80%, orange <100%, red at/over budget. Resets on your
  plan-renewal day (set `plan_renewal_day` in `.cost_ledger.json`, 1–28;
  defaults to 1).
- `⠧ Bash` / `⠋ thinking` / `○ idle` — live activity indicator

**Line 2 — this session** (everything here is since this chat started)
- `$X.XXX` — session cost (from Claude Code's own `cost.total_cost_usd`)
- `$X.X/hr` — burn rate (session cost / session hours); green <$3, yellow
  <$10, red above. Catches a runaway turn in real time.
- `Xm` — session wall-clock
- `input:XM` — tokens sent TO Claude this session: your prompts + attached
  files + tool results + prior conversation re-sent as context.
- `output:XK` — tokens Claude wrote BACK this session: reply text + tool
  call arguments. Output is 5× the price of input per token on Opus.
- `reused:N%` — how much of your input came from Anthropic's prompt cache
  instead of fresh reads (caching makes repeat context ~90% cheaper). Green
  ≥90%, yellow ≥70%, red below. A drop means context is churning.
- `⎇ main ●3` — git branch, `●N` = count of dirty files, `↑/↓` = ahead/behind
- `you:N claude:M` — number of prompts you sent / replies Claude sent back

**Line 3 — broader tracking**
- `today:$X` — spend since local midnight
- `time:XhYYm` — total active time across ALL of today's sessions. Sums
  gaps between events shorter than 5 minutes; longer gaps are treated as
  idle and skipped. Green <4h, yellow <8h, orange beyond. Cached 30s.
- `week:$X` — rolling 7-day spend
- `all-time:$X` — lifetime spend across all Claude Code sessions
- `avg-session:$X` — average cost per tracked session. Compare to line 2's
  session cost to see if this chat is running hotter/colder than typical.
- `7d-tokens:XM` — raw token volume over the last 7 days

## Why this is cool

Claude Pro/Max is a flat-rate subscription, but every session still has an
API-equivalent cost. This tracker shows how much API value you're extracting
from your subscription — the `month:$550/$100 (551%)` reading means 5.5× the
plan price in API-equivalent usage. It's a way to feel the scale of what
you're getting and catch unusual burn rates early.

## Install

### 1. Copy the files into your `~/.claude/` directory

```bash
# From the folder containing this README
cp statusline.py ~/.claude/statusline.py
chmod +x ~/.claude/statusline.py

mkdir -p ~/.claude/hooks
cp busy_tool.sh ~/.claude/hooks/busy_tool.sh
chmod +x ~/.claude/hooks/busy_tool.sh
```

### 2. Edit `~/.claude/settings.json`

Open `~/.claude/settings.json` and merge the contents of
`settings.example.json` into it. If that file doesn't exist yet, just copy
`settings.example.json` to `~/.claude/settings.json` and edit.

**Important:** replace every `/Users/YOURNAME/` with your actual home path:

```bash
# Quick way to get it right:
sed -i '' "s|/Users/YOURNAME|$HOME|g" ~/.claude/settings.json
```

If you already have hooks or a statusLine defined, merge manually — don't
overwrite.

### 3. Reload Claude Code

The statusline hot-reloads as soon as settings.json is saved. For the busy
indicator hooks, open the `/hooks` menu inside Claude Code once (it re-reads
the hook config) or restart your session.

### 4. Tune your budget

The cost ledger auto-creates at `~/.claude/.cost_ledger.json` on first run. It
defaults to **$100/month** (the Claude Pro plan). If you're on Max ($200) or
something else, edit that file:

```json
{
  "budget_month_usd": 200,
  "sessions": { ... }
}
```

Or just delete the ledger file — it'll re-seed on the next refresh using your
historical transcripts.

## How the cost math works

**Live sessions:** Claude Code hands the statusline `cost.total_cost_usd`
every refresh. That's the authoritative value.

**Historical sessions:** On first run with no ledger, the script scans every
`~/.claude/projects/*/*.jsonl` transcript and estimates cost per turn using
Anthropic's public API pricing (per 1M tokens):

| Model  | Input | Output | Cache read | Cache write |
|--------|------:|-------:|-----------:|------------:|
| Opus   | $15   | $75    | $1.50      | $18.75      |
| Sonnet | $3    | $15    | $0.30      | $3.75       |
| Haiku  | $1    | $5     | $0.10      | $1.25       |

The seed uses the max event timestamp from each transcript (not file mtime)
so the 7-day / 30-day filters are accurate.

## Customization

**Change the budget:** edit `budget_month_usd` in `~/.claude/.cost_ledger.json`.

**Change bar colors:** the `context_bar()` and `money_bar()` functions in
`statusline.py` use green / yellow / orange / red at 50 / 70 / 80 / 90%
thresholds. Tweak the ANSI color constants at the top.

**Disable the busy indicator:** remove the four hooks from settings.json.
The statusline keeps working, it just always shows `○ idle`.

**Different pricing or new model:** update the `PRICING_PER_M` dict and the
`price_for_model()` matcher in `statusline.py`.

**Reset spend tracking:** delete `~/.claude/.cost_ledger.json`. The next
refresh re-seeds from your transcripts.

## Troubleshooting

**Statusline shows nothing / plain text fallback**
- Check `python3 ~/.claude/statusline.py < /dev/null` — if it errors,
  you need Python 3.8+
- Verify `settings.json` is valid JSON (`python3 -m json.tool settings.json`)

**Spinner never animates**
- Make sure `"refreshInterval": 1` is set in the statusLine block
- Without that, it only refreshes on events, not on a ticking clock

**Busy indicator stuck on a tool name**
- The Stop hook didn't run — this happens if Claude Code crashed mid-turn
- Fix: `rm ~/.claude/.busy` to clear the stuck flag

**Cost number looks way too high**
- That's the API-equivalent value, not what you're actually being charged
- If you're on a subscription plan, this number exceeding your plan price
  just means you're getting good value from the subscription

**Weekly bar pegged at 2000%+**
- Weekly budget = monthly ÷ 4 = very small ($25 default). Heavy users blow
  through this easily. The bar is an alarm, not a limit. Consider raising
  `budget_month_usd` or reinterpreting it as "monthly API-equivalent cap"
  rather than a hard ceiling.

## Files

- `statusline.py` — the renderer (stdin JSON → three ANSI lines on stdout)
- `busy_tool.sh` — one-line helper for the `PreToolUse` hook
- `settings.example.json` — paste this into `~/.claude/settings.json`

## License

Do whatever you want with it.

---
description: Full-day usage stats: cost, tokens, time, per-project, per-tool
allowed-tools: Bash(python3 ~/.claude/usage_today.py)
---

!`python3 ~/.claude/usage_today.py`

The block above is today's aggregated Claude Code usage (all sessions, local time). Do not stay silent and do not just restate numbers the user can already see. Give them a short, sharp read:

- **Where the dollars actually went.** Decompose total cost by token type and name the bucket that dominates with its share. Per-million pricing: Opus in $15 / out $75 / cache-read $1.50 / cache-write $18.75; Sonnet $3 / $15 / $0.30 / $3.75; Haiku $1 / $5 / $0.10 / $1.25. Note: the displayed "input" figure already bundles cache-read + cache-write, so fresh input = displayed input minus those two.
- **Burn rate and cache health.** Is the $/hr high or normal for the work? Cache-reuse above 90% is great, below 70% is wasteful. Flag a large cache-write number as context churn (context grew or kept changing, forcing re-caching).
- **Anything anomalous** in the tool mix, the user/assistant message ratio, or the per-project split.
- **The single biggest lever** to cut spend, when there is an obvious one (e.g. clearing or compacting context between tasks when per-turn cache-reads are large).

Keep it to roughly four tight lines, no filler, no em-dashes. If a number looks fine, say so plainly rather than padding.

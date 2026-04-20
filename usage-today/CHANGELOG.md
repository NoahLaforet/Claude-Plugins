# Changelog

## 2026-04-19

- Initial release. `/usage-today` slash command + `usage_today.py` aggregator.
- Reads every transcript under `~/.claude/projects/` with today's activity.
- Reports: total cost, active time, burn rate, session count, prompt/reply
  count, first/last event span, full token breakdown, cache-reuse %, tool
  call total, per-model cost split, top-6 by-project bars with active time,
  and top-8 tool call counts.
- ANSI styling matches the statusbar plugin.

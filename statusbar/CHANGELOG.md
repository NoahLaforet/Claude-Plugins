# Changelog

## 2026-04-19

- Added `time: XhYYm` to line 3 — total active time across all of today's
  Claude Code sessions. Counts gaps shorter than 5 min; longer gaps treated
  as idle. Green <4h, yellow <8h, orange beyond. Cached 30s.
- Dropped the month progress bar; month block is now plain text with the
  dollar amount AND percentage both colored by spend tier (green/yellow/
  orange/red at 50/80/100%).
- Added a space after every label colon (`context: `, `month: `, `input: `,
  `output: `, `reused: `, `you: `, `claude: `, `today: `, `time: `, etc.)
  for readability.

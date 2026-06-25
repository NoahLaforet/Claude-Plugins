# Skills manifest

This repo ships only original skills (under `setup/skills/`). The third-party skills
below are installed from their own marketplaces, so they stay attributed to and updated by
their authors. Install the ones you want; none are required.

## Original skills in this repo

| Skill | What it does |
|---|---|
| `second-brain` | Search an Obsidian knowledge vault before answering historical questions. Pairs with the `claude-brain/` component. |
| `claude-audit` | Audit and clean up your Claude Code setup (memory, CLAUDE.md, skills, hooks, settings). Backed by the weekly auto-audit in `setup/claude-audit/`. |

The installer copies these into `~/.claude/skills/`.

## Third-party skills (install from source, not vendored here)

Install with `/plugin marketplace add <repo>` then `/plugin install <name>`, or follow each
author's instructions. Verify the source before installing.

| Skill or pack | Source | Use |
|---|---|---|
| superpowers (writing-plans, subagent-driven-development, dispatching-parallel-agents, systematic-debugging, TDD, verification) | obra/superpowers | Agent orchestration and process gates |
| swiftui-pro | twostraws | SwiftUI code review |
| ios-simulator-skill | conorluddy | Drive the iOS Simulator |
| obsidian skills (markdown, bases, json-canvas, defuddle) | kepano/obsidian-skills | Obsidian file types and clean web-to-markdown |
| impeccable | pbakaus | Frontend design and audit |
| embedded-systems, cpp-pro | Jeffallan/claude-skills | Firmware/RTOS and modern C++ |
| python-testing | affaan-m/everything-claude-code | pytest strategy |
| writing-anti-ai | Galaxy-Dawn/claude-scholar | Scrub AI tells from existing text |
| docx, pdf | anthropics/skills | Office document and PDF handling |

## MCP servers (configure in your own ~/.claude.json, never commit keys)

context7 (live library docs), playwright, sequential-thinking, chrome-devtools, firecrawl
(needs an API key, store it in your gitignored config). The obsidian MCP backs `second-brain`.

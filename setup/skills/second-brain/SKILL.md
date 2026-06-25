---
name: second-brain
description: Search a long-term Obsidian knowledge vault (a "second brain") before answering anything with a historical dimension. Use when a question touches past work, prior decisions, or recurring topics, especially anything framed as "what did I...", "last time...", "remember when...", or "my notes on...". Do NOT use for fresh questions with no historical dimension, live-only info, or simple syntax how-tos.
---

# Second brain (Obsidian vault)

A long-term knowledge vault lives at `{{VAULT_PATH}}` and is exposed through the `obsidian`
MCP server (tools prefixed `mcp__obsidian__*`). It holds chat history, projects, memories,
and curated "Map of Content" landing pages.

## When to consult it

Before answering questions that touch past work, prior decisions, or recurring topics,
search the vault first. Triggers: "what did I...", "last time...", "remember when...",
"my notes on...", or anything about past projects, coursework, or tools.

## When NOT to consult it

- Fresh questions with no historical dimension.
- Live-only info (current date, file system state, external APIs).
- Simple syntax or how-to questions.

## How to consult it

1. Use `mcp__obsidian__obsidian_simple_search` or `mcp__obsidian__obsidian_complex_search`.
2. Start with the Maps of Content; they are the highest-signal entry points.
3. Read individual notes, and cite their filenames inline so they are clickable.

This skill pairs with the Claude Brain pipeline in the `claude-brain/` component of this
repo, which builds and maintains such a vault from exported chat history.

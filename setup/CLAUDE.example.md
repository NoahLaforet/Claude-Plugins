# Global instructions

<!-- This is a template. The installer fills in {{FULL_NAME}}, {{EMAIL}}, {{VAULT_PATH}},
     and {{GITHUB_USER}}. Keep this file small; it loads in full every session, so only
     put stable "always" rules here. Move procedures into skills, deterministic actions
     into hooks, and path-specific guidance into .claude/rules/. -->

## Who I am

I am {{FULL_NAME}}. My git email is {{EMAIL}} and my GitHub is {{GITHUB_USER}}.

## Git commits

Author every commit as {{FULL_NAME}} only. Do not add a `Co-Authored-By` trailer or any
AI attribution to commit messages or PR descriptions.

## Writing

Do not use em-dashes or "--" as a sentence separator in anything written under my name.
Use commas, semicolons, or parentheses instead.

## Second brain (optional)

I keep a long-term Obsidian knowledge vault at `{{VAULT_PATH}}`, exposed through the
`obsidian` MCP server. Before answering anything with a historical dimension (past work,
prior decisions, "what did I..."), use the `second-brain` skill. Skip it for fresh
questions, live state, or simple how-tos. Remove this section if you do not use a vault.

## Weekly self-audit

A weekly launchd job at `~/.claude/claude-audit/` lints this setup for buildup (oversized
MEMORY.md, broken wikilinks, naming duplicates, stale files, config drift) and notifies on
issues. When it flags something, run `/claude-audit` for the full pass.

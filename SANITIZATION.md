# Sanitization and Contribution Guide

This repository is public. It ships original tooling (`summon/`, `statusbar/`, `usage-today/`, `claude-brain/`) and nothing else. No personal data, no live state, no secrets. This document explains the model that keeps it that way and the exact steps to verify before every push.

If you are about to push and only read one section, read the [Pre-publish checklist](#pre-publish-checklist).

---

## Two-tier model

Everything in this repo falls into one of two tiers.

**Tier 1: tracked and published.** Sanitized, original tooling only. These are the components anyone can clone and run. Templates carry placeholders, never real values. Examples of intentionally tracked files:

- `summon/`, `statusbar/`, `usage-today/` source
- `claude-brain/scripts/` pipeline and `claude-brain/templates/`
- `statusbar/settings.example.json` (placeholder settings, the `.example.` suffix is the tell)
- `claude-brain/scripts/sync_config.example.json` (placeholder sync config, again `.example.`)

**Tier 2: gitignored and never published.** Anything personal or stateful. This lives on disk but is excluded by `.gitignore` and must never be committed:

- The live Obsidian vault at `Claude Brain/` (full chat history, memories, entities)
- `~/.claude` memory, real `settings.json` / `settings.local.json`, `history.jsonl`
- The real `sync_config.json` (the non-`.example.` one), credentials, tokens, API keys
- Runtime state: `summon/state.json`, `summon/dictate_state.json`, models, logs, `dist/`
- Personal-only folders: `migration/`, `terminal-guide/`

The rule of thumb: if a file is the tool, it is Tier 1. If a file is about Noah, his machine, his accounts, or a captured run, it is Tier 2 and stays off the remote.

---

## Pre-publish checklist

Run this before every push to the public remote. Copy the box, work top to bottom, do not skip step 5.

- [ ] **1. Grep the tree for personal data.** Scan tracked content for: hardcoded `/Users/<name>` paths, the real email address, the full name, Tailscale `100.x.x.x` IPs, `sk-ant-` API keys, and any numeric security code. One pass:

  ```bash
  git ls-files -z | xargs -0 grep -nIE \
    '/Users/[a-z]|sk-ant-|100\.(6[4-9]|[7-9][0-9]|1[0-1][0-9]|12[0-7])\.[0-9]+\.[0-9]+' \
    2>/dev/null
  ```

  Run the name / email / security-code scans separately so the patterns stay out of this file (substitute the real values locally, never commit them):

  ```bash
  git ls-files -z | xargs -0 grep -nIiF 'REAL_EMAIL_HERE'        2>/dev/null
  git ls-files -z | xargs -0 grep -nIiF 'REAL FULL NAME HERE'    2>/dev/null
  git ls-files -z | xargs -0 grep -nIE  'REAL_SECURITY_CODE'     2>/dev/null
  ```

  Any hit that is not an intentional placeholder is a blocker.

- [ ] **2. Replace every hit with a placeholder.** Swap real values for `$HOME`, `${USER}`, `<your-email>`, `<your-name>`, `<TAILSCALE_IP>`, `<API_KEY>`, or a clearly fake sample. Paths should resolve from the environment, not from a literal home directory. Re-run step 1 until it returns nothing but known-good placeholders.

- [ ] **3. Confirm no local or state file is tracked.** This must return nothing:

  ```bash
  git ls-files | grep -E 'local|credential|history|\.jsonl|sync_config'
  ```

  One expected exception: `claude-brain/scripts/sync_config.example.json` is the sanitized template and is allowed. The real `sync_config.json` (without `.example.`) must never appear. If anything other than the `.example.` file shows up, it is tracked and must be removed (see step 5 on why `.gitignore` alone will not fix it).

- [ ] **4. Run gitleaks on the full history.** Not just the working tree, the whole history, since a secret committed once and deleted later still lives in old commits:

  ```bash
  gitleaks detect --no-banner
  ```

  Zero leaks is the only pass. A finding means rewrite history (for example `git filter-repo`) before the remote ever sees it, rotate the exposed credential, and re-run.

- [ ] **5. Verify with `git ls-files`, not `.gitignore`.** A file added to `.gitignore` *after* it was already committed stays tracked. `.gitignore` only stops *new, untracked* files from being added. So trusting the ignore list is not enough. For any path you expect to be excluded, confirm Git is not tracking it:

  ```bash
  git ls-files | grep -iE 'Claude Brain/|settings\.local|settings\.json|history\.jsonl'
  ```

  Expected result: nothing. If a file you meant to exclude is listed, it was committed before the ignore rule existed. Remove it from tracking while keeping it on disk:

  ```bash
  git rm --cached <path>
  ```

  then commit the removal. Re-run step 5 to confirm it is gone from the index.

When all five boxes are checked and steps 1, 3, 4, and 5 each return clean, the push is safe.

---

## Automation: pre-commit hook and CI

Steps 1 and 4 are also enforced by tooling so a tired push cannot slip a secret through.

- **`.pre-commit-config.yaml`** runs the secret and personal-data scans locally on every `git commit`, blocking the commit if anything matches.
- **`.github/workflows/gitleaks.yml`** re-runs `gitleaks` in CI on every push and pull request, scanning history server-side as a backstop.

These automate the catching, they do not replace the manual checklist. Steps 2, 3, and 5 still need a human, because deciding what is a real leak versus an intended placeholder, and un-tracking already-committed files, is judgment work.

Install the local hook once after cloning:

```bash
pip install pre-commit && pre-commit install
```

After that the hook fires automatically on each commit. To scan the whole tree on demand:

```bash
pre-commit run --all-files
```

CI needs no setup, the workflow runs on its own once `.github/workflows/gitleaks.yml` is present on the default branch.

---

## What NEVER goes public

A blunt list. None of these may ever land on the remote, in any commit, in any history:

- The live `Claude Brain/` Obsidian vault (chat history, memories, entities, MOCs)
- Real `~/.claude` memory, `settings.json`, `settings.local.json`, `history.jsonl`
- The real `sync_config.json` (only the `.example.` template is public)
- API keys (`sk-ant-` and any other), tokens, credentials, secrets of any kind
- The numeric security code
- Tailscale `100.x.x.x` IPs or any private network address
- Hardcoded `/Users/<name>` paths, the real full name, or personal email addresses
- Captured runtime state, logs, models, `dist/`, and the `migration/` and `terminal-guide/` folders

When in doubt, leave it out and ask. A missing file is fixable. A leaked one is forever in the history.

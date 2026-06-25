#!/usr/bin/env bash
#
# precommit-guard.sh
#
# Blocks a commit if any staged change would leak private information into this
# public repo. Checks the staged file PATHS and the staged file CONTENT.
#
# This is a fast, dependency-free first line of defense (git, grep, sed only).
# It runs alongside gitleaks, which does the deep secret scanning. The unique
# job here is blocking the private Obsidian vault and other personal folders,
# which a content-only scanner will not catch.
#
# Exit codes:
#   0  clean
#   1  a violation was found (commit blocked)
#
set -euo pipefail

fail() {
  echo ""
  echo "############################################################"
  echo "# PRIVACY GUARD BLOCKED THIS COMMIT"
  echo "#"
  echo "# $1"
  echo "#"
  echo "# Nothing was committed. Unstage the offending change and try"
  echo "# again. Override only after reviewing the change by hand."
  echo "############################################################"
  echo ""
  exit 1
}

staged="$(git diff --cached --name-only --diff-filter=ACMR || true)"
[ -z "$staged" ] && exit 0

# --------------------------------------------------------------------------
# 1. Blocked PATHS: private folders that must never be staged, in any form.
#    Matches the folder whether git stages it with a trailing slash, as a
#    nested path, or as a bare gitlink (the vault carries its own .git).
# --------------------------------------------------------------------------
bad_path="$(printf '%s\n' "$staged" \
  | grep -E '(^|/)(Claude Brain|01 - Chats|02 - Projects|03 - Memories|migration|terminal-guide)($|/)' \
  | head -n 1 || true)"
if [ -n "$bad_path" ]; then
  fail "Staged path is private and must never be committed: $bad_path"
fi

# --------------------------------------------------------------------------
# 2. Blocked CONTENT: scan staged added lines for real personal data.
#    Skip the two meta files that legitimately document these patterns
#    (this guard and the sanitization guide). gitleaks still scans them.
# --------------------------------------------------------------------------
scan_files="$(printf '%s\n' "$staged" \
  | grep -Ev '^(scripts/precommit-guard\.sh|SANITIZATION\.md)$' || true)"
[ -z "$scan_files" ] && exit 0

# Added lines only (strip the leading '+'), restricted to the scanned files.
added="$(git diff --cached --diff-filter=ACMR -U0 -- $scan_files 2>/dev/null \
  | grep -E '^\+' | grep -Ev '^\+\+\+' | sed -E 's/^\+//' || true)"
[ -z "$added" ] && exit 0

first_hit() { printf '%s\n' "$added" | grep -E "$1" | head -n 1 || true; }

# 2a. A real /Users/<name>/ home path. Placeholders (YOURNAME, USERNAME, you,
#     user, example) are allowed so example configs and docs do not trip.
home_hit="$(printf '%s\n' "$added" \
  | grep -E '/Users/[a-z][A-Za-z0-9._-]*' \
  | grep -Eiv '/Users/(you|your|yourname|username|user|example|me|home|name)' \
  | head -n 1 || true)"
[ -n "$home_hit" ] && fail "Real /Users/ home path in staged content: $home_hit"

# 2b. An email address (placeholders and noreply/example allowed).
email_hit="$(printf '%s\n' "$added" \
  | grep -E '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}' \
  | grep -Eiv '(noreply@|@example\.|you@|user@|name@)' \
  | head -n 1 || true)"
[ -n "$email_hit" ] && fail "Email address in staged content: $email_hit"

# 2c. An Anthropic API key (sk-ant-) with real key characters.
key_hit="$(printf '%s\n' "$added" \
  | grep -E 'sk-ant-[A-Za-z0-9_-]{12,}' \
  | grep -Eiv 'sk-ant-(sid01-)?(paste|your|xxxx|example|replace|todo|placeholder)' \
  | head -n 1 || true)"
[ -n "$key_hit" ] && fail "Anthropic API key (sk-ant-) in staged content: $key_hit"

# 2d. A Tailscale CGNAT IP (100.64.0.0 .. 100.127.255.255).
ip_hit="$(first_hit '(^|[^0-9])100\.(6[4-9]|[7-9][0-9]|1[01][0-9]|12[0-7])\.[0-9]{1,3}\.[0-9]{1,3}')"
[ -n "$ip_hit" ] && fail "Tailscale 100.x IP address in staged content: $ip_hit"

exit 0

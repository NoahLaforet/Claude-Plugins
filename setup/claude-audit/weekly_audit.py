#!/usr/bin/env python3
"""
weekly_audit.py - automatic health check for a Claude Code setup.

Catches the buildup that makes sessions go "dumb": an oversized always-loaded
MEMORY.md, broken wikilinks, naming duplicates, stale dated memories, and config
drift. Auto-fixes only the safe, deterministic things (broken wikilinks whose
target exists under the underscore spelling); everything else is reported.

Portable: it auto-detects your memory directory under ~/.claude/projects/*/memory
so it works on any machine. Writes a markdown report to reports/ and prints a
SUMMARY: line for a notification wrapper. Always exits 0.
"""
import os, re, json, sys, glob, datetime

HOME = os.path.expanduser("~")
SELF_DIR = os.path.dirname(os.path.abspath(__file__))
GLOBAL_CLAUDE = os.path.join(HOME, ".claude/CLAUDE.md")
SETTINGS = os.path.join(HOME, ".claude/settings.json")
REPORTS = os.path.join(SELF_DIR, "reports")

SIZE_WARN_KB = 18      # session-load ceiling is 25 KB; warn with headroom
LINE_WARN = 180        # ceiling is 200 lines
STALE_DAYS = 60

APPLY_FIXES = "--dry-run" not in sys.argv
issues, fixes, notes = [], [], []


def find_memory_dir():
    hits = glob.glob(os.path.join(HOME, ".claude/projects/*/memory/MEMORY.md"))
    return os.path.dirname(hits[0]) if hits else None


MEM_DIR = find_memory_dir()
MEMORY_MD = os.path.join(MEM_DIR, "MEMORY.md") if MEM_DIR else None


def md_files():
    return sorted(f for f in os.listdir(MEM_DIR)
                  if f.endswith(".md") and f != "MEMORY.md")


def check_index_size():
    data = open(MEMORY_MD, encoding="utf-8").read()
    kb = len(data.encode("utf-8")) / 1024
    lines = data.count("\n") + 1
    notes.append(f"MEMORY.md index: {kb:.1f} KB, {lines} lines (ceiling 25 KB / 200 lines).")
    if kb > SIZE_WARN_KB or lines > LINE_WARN:
        issues.append(f"MEMORY.md is {kb:.1f} KB / {lines} lines, near the 25 KB / 200-line "
                      "session-load ceiling. Compress glosses or archive stale entries.")


def check_index_integrity():
    data = open(MEMORY_MD, encoding="utf-8").read()
    targets = set(re.findall(r"\]\(([a-zA-Z0-9_]+)\.md\)", data))
    targets.discard("slug")
    files = {f[:-3] for f in md_files()}
    orphans = sorted(files - targets)
    danglers = sorted(targets - files)
    if orphans:
        issues.append(f"{len(orphans)} memory file(s) missing from MEMORY.md: " + ", ".join(orphans[:8]))
    if danglers:
        issues.append(f"{len(danglers)} MEMORY.md bullet(s) point to a missing file: " + ", ".join(danglers[:8]))
    if not orphans and not danglers:
        notes.append("MEMORY.md index is 1:1 with the files on disk.")


def check_wikilinks():
    files = {f[:-3] for f in md_files()} | {"MEMORY"}
    link_re = re.compile(r"\[\[([a-zA-Z0-9_-]+)\]\]")
    fixed, broken = 0, []
    for fn in md_files():
        path = os.path.join(MEM_DIR, fn)
        text = open(path, encoding="utf-8").read()
        new = text
        for slug in set(link_re.findall(text)):
            if slug in files or "slnc" in slug:
                continue
            norm = slug.replace("-", "_")
            if norm in files:
                new = new.replace(f"[[{slug}]]", f"[[{norm}]]")
                fixed += 1
            else:
                broken.append(f"[[{slug}]] in {fn}")
        if new != text and APPLY_FIXES:
            open(path, "w", encoding="utf-8").write(new)
    if fixed:
        fixes.append(f"Normalized {fixed} broken wikilink(s) to their underscore filenames.")
    if broken:
        issues.append(f"{len(broken)} wikilink(s) point nowhere and need a manual fix: " + "; ".join(broken[:6]))


def collapse(s):
    return re.sub(r"(.)\1+", r"\1", s)


def check_naming_dupes():
    seen = {}
    for f in (x[:-3] for x in md_files()):
        seen.setdefault(collapse(f), []).append(f)
    for group in seen.values():
        if len(group) > 1:
            issues.append("Possible naming duplicate (same after collapsing repeated letters): "
                          + ", ".join(group) + ". Pick one spelling.")


def check_stale_dated():
    today = datetime.date.today()
    kw = re.compile(r"\b(this week|deadline|due |runway|midterm|today'?s meeting|next week)\b", re.I)
    date_re = re.compile(r"(20\d\d)-(\d\d)-(\d\d)")
    cands = []
    for fn in md_files():
        head = "".join(open(os.path.join(MEM_DIR, fn), encoding="utf-8").readlines()[:40])
        dates = []
        for y, m, d in date_re.findall(fn + " " + head):
            try:
                dates.append(datetime.date(int(y), int(m), int(d)))
            except ValueError:
                pass
        if dates and (today - max(dates)).days > STALE_DAYS and kw.search(head):
            cands.append(f"{fn} (newest {max(dates)})")
    if cands:
        issues.append(f"{len(cands)} memory file(s) look stale; consider archiving: " + "; ".join(cands[:6]))


def check_em_dashes():
    for path, label in [(GLOBAL_CLAUDE, "~/.claude/CLAUDE.md"), (os.path.join(HOME, "CLAUDE.md"), "~/CLAUDE.md")]:
        if os.path.exists(path):
            bad = [i + 1 for i, ln in enumerate(open(path, encoding="utf-8")) if "\u2014" in ln]
            if bad:
                issues.append(f"{label} has em-dashes on line(s) {bad}.")


def check_settings():
    try:
        d = json.loads(open(SETTINGS, encoding="utf-8").read())
    except Exception as e:
        issues.append(f"settings.json is not valid JSON: {e}")
        return
    if "voice" in d and "voiceEnabled" in d:
        issues.append("settings.json has both `voice` and `voiceEnabled` (redundant).")


def main():
    if not MEM_DIR:
        notes.append("No memory directory found under ~/.claude/projects/*/memory; skipped memory checks.")
        checks = [check_em_dashes, check_settings]
    else:
        checks = [check_index_size, check_index_integrity, check_wikilinks,
                  check_naming_dupes, check_stale_dated, check_em_dashes, check_settings]
    for chk in checks:
        try:
            chk()
        except Exception as e:
            notes.append(f"{chk.__name__} errored: {e}")

    today = datetime.date.today().isoformat()
    verdict = "ATTENTION" if issues else "CLEAN"
    out = [f"# Claude setup audit, {today}", "", f"Verdict: **{verdict}**", ""]
    if fixes:
        out += ["## Auto-fixed (safe)"] + [f"- {x}" for x in fixes] + [""]
    if issues:
        out += ["## Needs attention"] + [f"- {x}" for x in issues] + [""]
    out += ["## Notes"] + [f"- {x}" for x in notes] + [""]
    os.makedirs(REPORTS, exist_ok=True)
    open(os.path.join(REPORTS, f"audit-{today}.md"), "w", encoding="utf-8").write("\n".join(out))
    open(os.path.join(REPORTS, "latest.md"), "w", encoding="utf-8").write("\n".join(out))

    print(f"SUMMARY: {len(issues)} issue(s) need attention" + (f", {len(fixes)} auto-fixed" if fixes else "")
          if issues else "SUMMARY: setup is healthy" + (f", {len(fixes)} wikilink(s) auto-fixed" if fixes else ""))


if __name__ == "__main__":
    main()

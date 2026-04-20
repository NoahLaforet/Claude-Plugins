#!/usr/bin/env python3
"""Claude Code statusline — two-line rich display.

Line 1: model · effort │ context-bar % tokens/window │ busy/idle
Line 2: $cost │ ↑in ↓out │ branch · │ week │ +added -removed │ session-time
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

HOME = Path.home()
CLAUDE_DIR = HOME / ".claude"
BUSY_FLAG = CLAUDE_DIR / ".busy"
WEEK_CACHE = CLAUDE_DIR / ".week_cache.json"
TODAY_TIME_CACHE = CLAUDE_DIR / ".today_time_cache.json"
COST_LEDGER = CLAUDE_DIR / ".cost_ledger.json"
SETTINGS = CLAUDE_DIR / "settings.json"
PROJECTS_ROOT = CLAUDE_DIR / "projects"

CONTEXT_WINDOW = 200_000
OPUS_4X_CONTEXT_WINDOW = 400_000  # Opus 4.x has extended context headroom before auto-compact
DEFAULT_MONTH_BUDGET_USD = 100.0


def context_window_for(model_id: str) -> int:
    if model_id and "opus-4" in model_id.lower():
        return OPUS_4X_CONTEXT_WINDOW
    return CONTEXT_WINDOW

PRICING_PER_M = {
    "opus": {"in": 15.0, "out": 75.0, "cr": 1.5, "cc": 18.75},
    "sonnet": {"in": 3.0, "out": 15.0, "cr": 0.3, "cc": 3.75},
    "haiku": {"in": 1.0, "out": 5.0, "cr": 0.1, "cc": 1.25},
}


def price_for_model(model_id: str) -> dict | None:
    if not model_id:
        return None
    m = model_id.lower()
    if "opus" in m:
        return PRICING_PER_M["opus"]
    if "sonnet" in m:
        return PRICING_PER_M["sonnet"]
    if "haiku" in m:
        return PRICING_PER_M["haiku"]
    return None


def cost_from_usage(model_id: str, u: dict) -> float:
    p = price_for_model(model_id)
    if not p:
        return 0.0
    inp = (u.get("input_tokens") or 0) / 1e6
    out = (u.get("output_tokens") or 0) / 1e6
    cr = (u.get("cache_read_input_tokens") or 0) / 1e6
    cc = (u.get("cache_creation_input_tokens") or 0) / 1e6
    return inp * p["in"] + out * p["out"] + cr * p["cr"] + cc * p["cc"]

RESET = "\033[0m"
BOLD = "\033[1m"
# DIM is used for all labels/separators — upgraded from ANSI dim (\033[2m) to an
# explicit light-gray so it stays subordinate without getting hard to read.
DIM = "\033[38;5;248m"
ITALIC = "\033[3m"
RED = "\033[38;5;203m"
GREEN = "\033[38;5;114m"
YELLOW = "\033[38;5;221m"
BLUE = "\033[38;5;110m"
MAGENTA = "\033[38;5;176m"
CYAN = "\033[38;5;116m"
GREY = "\033[38;5;244m"
ORANGE = "\033[38;5;208m"
TEAL = "\033[38;5;115m"
PINK = "\033[38;5;211m"
PURPLE = "\033[38;5;141m"
LIME = "\033[38;5;156m"
CREAM = "\033[38;5;229m"


def fmt_tok(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 10_000:
        return f"{n / 1_000:.0f}K"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def fmt_dur(ms: int) -> str:
    s = ms / 1000
    if s < 60:
        return f"{s:.0f}s"
    if s < 3600:
        return f"{s / 60:.0f}m"
    return f"{s / 3600:.1f}h"


def context_bar(pct: float, width: int = 12) -> str:
    pct = max(0.0, min(100.0, pct))
    filled = int(round(pct * width / 100))
    if pct >= 90:
        color = RED
    elif pct >= 70:
        color = YELLOW
    else:
        color = GREEN
    return f"{color}{'█' * filled}{GREY}{'░' * (width - filled)}{RESET}"


def context_bar_remaining(pct_rem: float, width: int = 6) -> str:
    """Bar renders REMAINING context right-justified: empty cells on the LEFT,
    filled cells on the RIGHT. As context drains, the filled segment shrinks
    toward the right edge, making "running out" visually obvious."""
    pct = max(0.0, min(100.0, pct_rem))
    filled = int(round(pct * width / 100))
    empty = width - filled
    if pct <= 10:
        color = RED
    elif pct <= 30:
        color = YELLOW
    else:
        color = GREEN
    return f"{GREY}{'░' * empty}{color}{'█' * filled}{RESET}"


def parse_transcript(path: str | None) -> tuple[int, int, int, int, int, int]:
    """Return (last_ctx, sess_in, sess_out, sess_cr, assistant_msgs, user_prompts).

    last_ctx = tokens SENT to the model on the most recent turn (input + cache
    reads + cache creation). Output is excluded.
    sess_cr = cache-read tokens for this session; used to compute cache hit %.
    """
    if not path or not os.path.exists(path):
        return 0, 0, 0, 0, 0, 0
    last_ctx = 0
    sess_in = 0
    sess_out = 0
    sess_cr = 0
    assistant = 0
    prompts = 0
    try:
        with open(path) as f:
            for line in f:
                try:
                    evt = json.loads(line)
                except Exception:
                    continue
                if evt.get("type") == "user":
                    c = (evt.get("message") or {}).get("content")
                    if isinstance(c, str) and c.strip():
                        prompts += 1
                    elif isinstance(c, list):
                        if any(
                            isinstance(x, dict) and x.get("type") == "text"
                            for x in c
                        ):
                            prompts += 1
                usage = (evt.get("message") or {}).get("usage") or {}
                if not usage:
                    continue
                inp = usage.get("input_tokens", 0) or 0
                cr = usage.get("cache_read_input_tokens", 0) or 0
                cc = usage.get("cache_creation_input_tokens", 0) or 0
                out = usage.get("output_tokens", 0) or 0
                last_ctx = inp + cr + cc
                sess_in += inp + cr + cc
                sess_cr += cr
                sess_out += out
                assistant += 1
    except Exception:
        pass
    return last_ctx, sess_in, sess_out, sess_cr, assistant, prompts


def last_assistant_text(path: str | None) -> str:
    """Return the most recent chat text Claude sent this session (truncated caller-side).

    Scans the transcript for `type:"assistant"` events and keeps the latest one
    whose content includes a non-empty text block (skipping tool_use-only turns).
    """
    if not path or not os.path.exists(path):
        return ""
    last = ""
    try:
        with open(path) as f:
            for line in f:
                try:
                    evt = json.loads(line)
                except Exception:
                    continue
                if evt.get("type") != "assistant":
                    continue
                content = (evt.get("message") or {}).get("content")
                text = ""
                if isinstance(content, str):
                    text = content
                elif isinstance(content, list):
                    pieces = [
                        b.get("text", "")
                        for b in content
                        if isinstance(b, dict) and b.get("type") == "text"
                    ]
                    text = " ".join(t for t in pieces if t and t.strip())
                if text.strip():
                    last = text.strip()
    except Exception:
        pass
    return last


def git_info(cwd: str) -> tuple[str | None, bool, int, int, int]:
    """Return (branch, dirty, dirty_count, ahead, behind)."""
    try:
        r = subprocess.run(
            ["git", "-C", cwd, "symbolic-ref", "--short", "HEAD"],
            capture_output=True, text=True, timeout=0.5,
        )
        if r.returncode != 0:
            return None, False, 0, 0, 0
        branch = r.stdout.strip()
        r2 = subprocess.run(
            ["git", "-C", cwd, "status", "--porcelain"],
            capture_output=True, text=True, timeout=0.5,
        )
        dirty_lines = [ln for ln in r2.stdout.splitlines() if ln.strip()]
        dirty = bool(dirty_lines)
        dirty_count = len(dirty_lines)
        ahead = behind = 0
        r3 = subprocess.run(
            ["git", "-C", cwd, "rev-list", "--left-right", "--count",
             f"{branch}...@{{upstream}}"],
            capture_output=True, text=True, timeout=0.5,
        )
        if r3.returncode == 0:
            parts = r3.stdout.strip().split()
            if len(parts) == 2:
                ahead, behind = int(parts[0]), int(parts[1])
        return branch, dirty, dirty_count, ahead, behind
    except Exception:
        return None, False, 0, 0, 0


def weekly_tokens() -> int:
    """Sum tokens across all transcripts from the last 7 days (cached 60s)."""
    try:
        if WEEK_CACHE.exists() and (time.time() - WEEK_CACHE.stat().st_mtime) < 60:
            return int(json.loads(WEEK_CACHE.read_text()).get("total", 0))
    except Exception:
        pass
    cutoff = time.time() - 7 * 86400
    total = 0
    try:
        for p in PROJECTS_ROOT.glob("*/*.jsonl"):
            try:
                if p.stat().st_mtime < cutoff:
                    continue
                with open(p) as f:
                    for line in f:
                        try:
                            evt = json.loads(line)
                        except Exception:
                            continue
                        u = (evt.get("message") or {}).get("usage") or {}
                        if not u:
                            continue
                        ts = evt.get("timestamp")
                        if ts:
                            try:
                                from datetime import datetime
                                t = datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
                                if t < cutoff:
                                    continue
                            except Exception:
                                pass
                        total += (u.get("input_tokens") or 0)
                        total += (u.get("cache_read_input_tokens") or 0)
                        total += (u.get("cache_creation_input_tokens") or 0)
                        total += (u.get("output_tokens") or 0)
            except Exception:
                continue
    except Exception:
        pass
    try:
        WEEK_CACHE.write_text(json.dumps({"total": total, "ts": time.time()}))
    except Exception:
        pass
    return total


def today_work_ms(idle_gap_s: int = 300) -> int:
    """Sum active time across ALL transcripts with activity today.

    For each session, walk events in timestamp order and accumulate gaps
    shorter than `idle_gap_s` (default 5 min). Gaps longer than that are
    treated as idle (not working) and skipped. Only event timestamps on
    today's local date contribute.

    Cached for 30s since scanning every JSONL is expensive at 1s refresh.
    """
    try:
        if TODAY_TIME_CACHE.exists() and (time.time() - TODAY_TIME_CACHE.stat().st_mtime) < 30:
            cache = json.loads(TODAY_TIME_CACHE.read_text())
            from datetime import datetime
            today_str = datetime.now().strftime("%Y-%m-%d")
            if cache.get("date") == today_str:
                return int(cache.get("ms", 0))
    except Exception:
        pass

    from datetime import datetime
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    today_end = today_start + 86400
    total_ms = 0
    try:
        for p in PROJECTS_ROOT.glob("*/*.jsonl"):
            try:
                if p.stat().st_mtime < today_start:
                    continue
                stamps: list[float] = []
                with open(p) as f:
                    for line in f:
                        try:
                            evt = json.loads(line)
                        except Exception:
                            continue
                        ts = evt.get("timestamp")
                        if not ts:
                            continue
                        try:
                            t = datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
                        except Exception:
                            continue
                        if today_start <= t < today_end:
                            stamps.append(t)
                if len(stamps) < 2:
                    continue
                stamps.sort()
                for a, b in zip(stamps, stamps[1:]):
                    gap = b - a
                    if 0 < gap <= idle_gap_s:
                        total_ms += int(gap * 1000)
            except Exception:
                continue
    except Exception:
        pass

    try:
        TODAY_TIME_CACHE.write_text(json.dumps({
            "date": now.strftime("%Y-%m-%d"),
            "ms": total_ms,
            "ts": time.time(),
        }))
    except Exception:
        pass
    return total_ms


def fmt_worktime(ms: int) -> str:
    s = ms // 1000
    h, rem = divmod(s, 3600)
    m, _ = divmod(rem, 60)
    if h:
        return f"{h}h{m:02d}m"
    return f"{m}m"


def load_ledger() -> dict:
    if COST_LEDGER.exists():
        try:
            return json.loads(COST_LEDGER.read_text())
        except Exception:
            pass
    return {"version": 1, "budget_month_usd": DEFAULT_MONTH_BUDGET_USD, "sessions": {}}


def save_ledger(led: dict) -> None:
    try:
        tmp = COST_LEDGER.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(led))
        tmp.replace(COST_LEDGER)
    except Exception:
        pass


def seed_ledger_if_new(led: dict) -> bool:
    """If ledger has no sessions, estimate historical cost from all transcripts.

    Uses actual event timestamps from the transcript (not file mtime) so that
    week/month windows filter correctly — a session from 3 months ago stays
    outside the 30-day window even if its file was touched recently.
    """
    if led.get("sessions"):
        return False
    from datetime import datetime
    sessions: dict[str, dict] = {}
    try:
        for fp in PROJECTS_ROOT.glob("*/*.jsonl"):
            session_id = fp.stem
            total = 0.0
            max_ts = 0.0
            try:
                with open(fp) as f:
                    for line in f:
                        try:
                            e = json.loads(line)
                        except Exception:
                            continue
                        msg = e.get("message") or {}
                        u = msg.get("usage") or {}
                        if u:
                            total += cost_from_usage(msg.get("model", ""), u)
                        ts = e.get("timestamp")
                        if ts:
                            try:
                                t = datetime.fromisoformat(
                                    ts.replace("Z", "+00:00")
                                ).timestamp()
                                if t > max_ts:
                                    max_ts = t
                            except Exception:
                                pass
            except Exception:
                continue
            if total > 0:
                sessions[session_id] = {
                    "cost": round(total, 6),
                    "updated": max_ts or fp.stat().st_mtime,
                    "seeded": True,
                }
    except Exception:
        pass
    led["sessions"] = sessions
    return True


def record_session_cost(led: dict, session_id: str, cost_usd: float,
                        transcript_path: str | None) -> None:
    if not session_id:
        return
    sess = led.setdefault("sessions", {}).get(session_id, {})
    # Live cost from Claude Code is authoritative — overwrites seeded estimate.
    if cost_usd and cost_usd > 0:
        sess["cost"] = round(float(cost_usd), 6)
        sess["seeded"] = False
    elif "cost" not in sess and transcript_path and os.path.exists(transcript_path):
        # No live cost yet — estimate from transcript so it shows up immediately.
        est = 0.0
        try:
            with open(transcript_path) as f:
                for line in f:
                    try:
                        e = json.loads(line)
                    except Exception:
                        continue
                    msg = e.get("message") or {}
                    u = msg.get("usage") or {}
                    if u:
                        est += cost_from_usage(msg.get("model", ""), u)
        except Exception:
            pass
        sess["cost"] = round(est, 6)
        sess["seeded"] = True
    sess["updated"] = time.time()
    led["sessions"][session_id] = sess


def month_anchor_cut(anchor_day: int) -> float:
    """Return the UNIX timestamp of most-recent occurrence of day-of-month `anchor_day`
    at local midnight. If the day hasn't occurred yet this month, rolls back one month."""
    from datetime import datetime
    now = datetime.now()
    day = max(1, min(28, int(anchor_day or 1)))  # cap at 28 to avoid Feb edge cases
    candidate = now.replace(day=day, hour=0, minute=0, second=0, microsecond=0)
    if candidate > now:
        # Anchor day is later this month → use last month's anchor
        year = candidate.year
        month = candidate.month - 1
        if month == 0:
            month = 12
            year -= 1
        candidate = candidate.replace(year=year, month=month)
    return candidate.timestamp()


def ledger_totals(led: dict) -> tuple[float, float, float, float]:
    """Return (today_usd, week_usd, month_usd, lifetime_usd).

    - today: since local midnight
    - week:  rolling 7 days
    - month: since most recent plan-renewal anchor (default day 1; override via
             `plan_renewal_day` in the ledger JSON)
    - lifetime: all tracked sessions
    """
    from datetime import datetime
    now = time.time()
    week_cut = now - 7 * 86400
    anchor_day = int(led.get("plan_renewal_day") or 1)
    month_cut = month_anchor_cut(anchor_day)
    today_cut = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    td = wk = mo = life = 0.0
    for s in (led.get("sessions") or {}).values():
        c = float(s.get("cost", 0) or 0)
        u = float(s.get("updated", 0) or 0)
        life += c
        if u >= month_cut:
            mo += c
        if u >= week_cut:
            wk += c
        if u >= today_cut:
            td += c
    return td, wk, mo, life


def money_bar(pct: float, width: int = 10) -> str:
    pct = max(0.0, min(100.0, pct))
    filled = int(round(pct * width / 100))
    if pct >= 100:
        color = RED
    elif pct >= 80:
        color = ORANGE
    elif pct >= 50:
        color = YELLOW
    else:
        color = GREEN
    return f"{color}{'█' * filled}{GREY}{'░' * (width - filled)}{RESET}"


def fmt_money(v: float) -> str:
    if v >= 1000:
        return f"${v:,.0f}"
    if v >= 100:
        return f"${v:.1f}"
    return f"${v:.2f}"


def busy_indicator() -> str:
    if not BUSY_FLAG.exists():
        return f"{DIM}○ idle{RESET}"
    frames = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    idx = int(time.time() * 10) % len(frames)
    try:
        label = BUSY_FLAG.read_text().strip() or "thinking"
    except Exception:
        label = "thinking"
    color = CYAN if label == "thinking" else ORANGE
    return f"{color}{frames[idx]} {label}{RESET}"


def effort_from_settings() -> str | None:
    try:
        if SETTINGS.exists():
            data = json.loads(SETTINGS.read_text())
            eff = data.get("effortLevel")
            fast = data.get("fastMode")
            if fast:
                return "fast"
            return eff
    except Exception:
        pass
    return None


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}

    model = data.get("model", {}) or {}
    mname = model.get("display_name") or "Claude"
    cwd = (data.get("workspace") or {}).get("current_dir") or data.get("cwd") or os.getcwd()
    cost = data.get("cost") or {}
    cost_usd = cost.get("total_cost_usd") or 0
    dur_ms = cost.get("total_duration_ms") or 0
    added = cost.get("total_lines_added") or 0
    removed = cost.get("total_lines_removed") or 0
    transcript = data.get("transcript_path")
    exceeds = data.get("exceeds_200k_tokens")

    last_ctx, sess_in, sess_out, sess_cr, msgs, prompts = parse_transcript(transcript)
    model_id = model.get("id") or ""
    window = 1_000_000 if exceeds else context_window_for(model_id)
    pct = 100 * last_ctx / window if window else 0
    pct_remaining = max(0.0, 100.0 - pct)
    tokens_remaining = max(0, window - last_ctx)

    branch, dirty, dirty_count, ahead, behind = git_info(cwd)
    week = weekly_tokens()
    effort = effort_from_settings()

    session_id = data.get("session_id") or ""
    ledger = load_ledger()
    did_seed = seed_ledger_if_new(ledger)
    record_session_cost(ledger, session_id, cost_usd, transcript)
    save_ledger(ledger)
    today_usd, week_usd, month_usd, life_usd = ledger_totals(ledger)
    budget = float(ledger.get("budget_month_usd") or DEFAULT_MONTH_BUDGET_USD)
    month_pct = 100 * month_usd / budget if budget else 0

    # Derived session metrics
    burn = (cost_usd / (dur_ms / 3.6e6)) if dur_ms and dur_ms > 60_000 else 0.0
    cache_pct = (sess_cr / sess_in * 100) if sess_in else 0.0

    sep = f" {DIM}│{RESET} "

    # Line 1 — model · effort │ context-remaining bar │ month-budget bar │ busy
    head = f"{MAGENTA}{BOLD}{mname}{RESET}"
    if effort:
        head += f"  {DIM}effort: {RESET}{ORANGE}{effort}{RESET}"
    context_block = (
        f"{DIM}context: {RESET}{context_bar_remaining(pct_remaining, width=6)} "
        f"{BOLD}{pct_remaining:.0f}%{RESET} "
        f"{DIM}{fmt_tok(tokens_remaining)} left{RESET}"
    )
    if month_pct >= 100:
        mo_color = RED
    elif month_pct >= 80:
        mo_color = ORANGE
    elif month_pct >= 50:
        mo_color = YELLOW
    else:
        mo_color = GREEN
    month_block = (
        f"{DIM}month: {RESET}{mo_color}{BOLD}{fmt_money(month_usd)}{RESET}"
        f"{DIM}/{fmt_money(budget)} {RESET}{mo_color}{month_pct:.0f}%{RESET}"
    )
    line1 = sep.join([head, context_block, month_block, busy_indicator()])

    # Line 2 — session-scoped stats (cost trio · token trio · git · turns)
    cost_bits = [f"{GREEN}${cost_usd:.3f}{RESET}"]
    if burn > 0:
        bc = RED if burn >= 10 else (YELLOW if burn >= 3 else LIME)
        cost_bits.append(f"{bc}${burn:.1f}/hr{RESET}")
    if dur_ms:
        cost_bits.append(f"{TEAL}{fmt_dur(dur_ms)}{RESET}")

    tok_bits = [
        f"{DIM}input: {RESET}{PURPLE}{fmt_tok(sess_in)}{RESET}",
        f"{DIM}output: {RESET}{PINK}{fmt_tok(sess_out)}{RESET}",
    ]
    if sess_in:
        cc = LIME if cache_pct >= 90 else (YELLOW if cache_pct >= 70 else RED)
        tok_bits.append(f"{DIM}reused: {RESET}{cc}{cache_pct:.0f}%{RESET}")

    parts = [" ".join(cost_bits), " ".join(tok_bits)]

    if branch:
        g_bits = [f"{BLUE}⎇ {branch}{RESET}"]
        if dirty:
            g_bits.append(f"{YELLOW}●{dirty_count}{RESET}")
        if ahead:
            g_bits.append(f"{GREEN}↑{ahead}{RESET}")
        if behind:
            g_bits.append(f"{RED}↓{behind}{RESET}")
        parts.append(" ".join(g_bits))

    if added or removed:
        parts.append(
            f"{GREEN}+{added}{RESET}{DIM}/{RESET}{RED}-{removed}{RESET}"
        )
    if prompts or msgs:
        parts.append(
            f"{DIM}you: {RESET}{CYAN}{prompts}{RESET} "
            f"{DIM}claude: {RESET}{CYAN}{msgs}{RESET}"
        )
    line2 = sep.join(parts)

    # Line 3 — broader tracking (today · week · all-time · avg-session · 7d tokens).
    td_color = LIME if today_usd < 20 else (YELLOW if today_usd < 50 else ORANGE)
    wk_color = LIME if week_usd < 25 else (YELLOW if week_usd < 100 else ORANGE)
    paid_sessions = [
        s for s in (ledger.get("sessions") or {}).values()
        if float(s.get("cost", 0) or 0) > 0
    ]
    avg_session = life_usd / len(paid_sessions) if paid_sessions else 0.0
    work_ms = today_work_ms()
    wt_color = LIME if work_ms < 4 * 3_600_000 else (YELLOW if work_ms < 8 * 3_600_000 else ORANGE)
    plan_parts = [
        f"{DIM}today: {RESET}{td_color}{fmt_money(today_usd)}{RESET}",
        f"{DIM}time: {RESET}{wt_color}{fmt_worktime(work_ms)}{RESET}",
        f"{DIM}week: {RESET}{wk_color}{fmt_money(week_usd)}{RESET}",
        f"{DIM}all-time: {RESET}{MAGENTA}{fmt_money(life_usd)}{RESET}",
        f"{DIM}avg-session: {RESET}{TEAL}{fmt_money(avg_session)}{RESET}",
        f"{DIM}7d-tokens: {RESET}{CYAN}{fmt_tok(week)}{RESET}",
    ]
    line3 = sep.join(plan_parts)

    # Lines 4+ — last chat text Claude sent, word-wrapped so you can read it
    # even after a long tool-use burst scrolls the chat itself off-screen.
    last_txt = last_assistant_text(transcript)
    if last_txt:
        import shutil
        import textwrap
        try:
            term_w = shutil.get_terminal_size((120, 20)).columns
        except Exception:
            term_w = 120
        body_w = max(60, term_w)
        flat = " ".join(last_txt.split())
        wrapper = textwrap.TextWrapper(
            width=body_w,
            break_long_words=True,
            break_on_hyphens=False,
        )
        wrapped = wrapper.wrap(flat) or [""]
        # Preview is capped at 4 wrapped lines; longer responses get an ellipsis.
        max_lines = 4
        if len(wrapped) > max_lines:
            wrapped = wrapped[:max_lines]
            wrapped[-1] = (wrapped[-1][:-1] + "…") if wrapped[-1] else "…"
        colored = "\n".join(f"{ITALIC}{TEAL}{ln}{RESET}" for ln in wrapped)
        # Labeled dim rule separates the status rows from the preview.
        label = " latest response "
        dashes = "─" * max(8, body_w - len(label) - 2)
        rule = f"{DIM}──{label}{dashes}{RESET}"
        sys.stdout.write(f"{line1}\n{line2}\n{line3}\n{rule}\n{colored}\n")
    else:
        # Leading blank line separates the statusline from the chat response
        # above it when there's no preview to do it visually.
        sys.stdout.write(f"\n{line1}\n{line2}\n{line3}\n")


if __name__ == "__main__":
    main()

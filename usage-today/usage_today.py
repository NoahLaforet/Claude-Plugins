#!/usr/bin/env python3
"""Daily usage summary — aggregates today's activity across every Claude Code
session, then renders a multi-line readout styled to match statusline.py."""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

HOME = Path.home()
CLAUDE_DIR = HOME / ".claude"
PROJECTS_ROOT = CLAUDE_DIR / "projects"

PRICING_PER_M = {
    "opus": {"in": 15.0, "out": 75.0, "cr": 1.5, "cc": 18.75},
    "sonnet": {"in": 3.0, "out": 15.0, "cr": 0.3, "cc": 3.75},
    "haiku": {"in": 1.0, "out": 5.0, "cr": 0.1, "cc": 1.25},
}

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[38;5;248m"
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


def model_family(model_id: str) -> str:
    if not model_id:
        return "other"
    m = model_id.lower()
    if "opus" in m:
        return "opus"
    if "sonnet" in m:
        return "sonnet"
    if "haiku" in m:
        return "haiku"
    return "other"


def cost_from_usage(model_id: str, u: dict) -> float:
    p = price_for_model(model_id)
    if not p:
        return 0.0
    inp = (u.get("input_tokens") or 0) / 1e6
    out = (u.get("output_tokens") or 0) / 1e6
    cr = (u.get("cache_read_input_tokens") or 0) / 1e6
    cc = (u.get("cache_creation_input_tokens") or 0) / 1e6
    return inp * p["in"] + out * p["out"] + cr * p["cr"] + cc * p["cc"]


def fmt_tok(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 10_000:
        return f"{n / 1_000:.0f}K"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def fmt_money(v: float) -> str:
    if v >= 1000:
        return f"${v:,.0f}"
    if v >= 100:
        return f"${v:.1f}"
    return f"${v:.2f}"


def fmt_worktime(ms: int) -> str:
    s = ms // 1000
    h, rem = divmod(s, 3600)
    m, _ = divmod(rem, 60)
    if h:
        return f"{h}h{m:02d}m"
    return f"{m}m"


def bar(pct: float, width: int = 12, color: str = GREEN) -> str:
    pct = max(0.0, min(100.0, pct))
    filled = int(round(pct * width / 100))
    return f"{color}{'█' * filled}{GREY}{'░' * (width - filled)}{RESET}"


def project_label(project_dir: str) -> str:
    # Directory names under ~/.claude/projects/ encode the original cwd with
    # every "/" replaced by "-". Render a compact form that highlights the
    # final path segment.
    name = project_dir.strip("-")
    if not name:
        return project_dir
    segs = name.split("-")
    if len(segs) <= 2:
        return "/" + "/".join(segs)
    tail = segs[-1]
    # Collapse long paths down to "…/<leaf>" so the row stays readable.
    if len(segs) > 4:
        return f"…/{tail}"
    return "/" + "/".join(segs[-3:])


def collect_today():
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    today_end = today_start + 86400
    today_str = now.strftime("%Y-%m-%d")

    totals = {
        "input": 0, "output": 0, "cache_read": 0, "cache_create": 0,
        "cost": 0.0, "assistant_msgs": 0, "user_prompts": 0,
        "tool_uses": 0,
    }
    by_model = defaultdict(lambda: {"cost": 0.0, "msgs": 0})
    by_project = defaultdict(lambda: {
        "cost": 0.0, "msgs": 0, "sessions": set(), "work_ms": 0,
    })
    tool_counts = defaultdict(int)
    sessions_today: set[str] = set()
    work_ms_total = 0
    first_ts = None
    last_ts = None

    try:
        projects = list(PROJECTS_ROOT.glob("*/*.jsonl"))
    except Exception:
        projects = []

    for p in projects:
        try:
            if p.stat().st_mtime < today_start - 600:
                # File wasn't touched today — skip. (600s slack for clock skew.)
                continue
        except Exception:
            continue

        project_dir = p.parent.name
        session_id = p.stem
        stamps: list[float] = []
        session_touched = False

        try:
            with open(p) as f:
                for line in f:
                    try:
                        evt = json.loads(line)
                    except Exception:
                        continue
                    ts_raw = evt.get("timestamp")
                    t = None
                    if ts_raw:
                        try:
                            t = datetime.fromisoformat(
                                ts_raw.replace("Z", "+00:00")
                            ).timestamp()
                        except Exception:
                            t = None
                    if t is None or not (today_start <= t < today_end):
                        continue
                    stamps.append(t)
                    session_touched = True
                    if first_ts is None or t < first_ts:
                        first_ts = t
                    if last_ts is None or t > last_ts:
                        last_ts = t

                    etype = evt.get("type")
                    msg = evt.get("message") or {}
                    if etype == "user":
                        c = msg.get("content")
                        if isinstance(c, str) and c.strip():
                            totals["user_prompts"] += 1
                        elif isinstance(c, list) and any(
                            isinstance(x, dict) and x.get("type") == "text"
                            for x in c
                        ):
                            totals["user_prompts"] += 1

                    if etype == "assistant":
                        content = msg.get("content")
                        if isinstance(content, list):
                            for b in content:
                                if isinstance(b, dict) and b.get("type") == "tool_use":
                                    totals["tool_uses"] += 1
                                    name = b.get("name") or "?"
                                    tool_counts[name] += 1

                    u = msg.get("usage") or {}
                    if u:
                        inp = u.get("input_tokens", 0) or 0
                        out = u.get("output_tokens", 0) or 0
                        cr = u.get("cache_read_input_tokens", 0) or 0
                        cc = u.get("cache_creation_input_tokens", 0) or 0
                        model_id = msg.get("model") or ""
                        fam = model_family(model_id)
                        c_usd = cost_from_usage(model_id, u)

                        totals["input"] += inp
                        totals["output"] += out
                        totals["cache_read"] += cr
                        totals["cache_create"] += cc
                        totals["cost"] += c_usd
                        totals["assistant_msgs"] += 1

                        by_model[fam]["cost"] += c_usd
                        by_model[fam]["msgs"] += 1

                        by_project[project_dir]["cost"] += c_usd
                        by_project[project_dir]["msgs"] += 1
        except Exception:
            continue

        if session_touched:
            sessions_today.add(session_id)
            by_project[project_dir]["sessions"].add(session_id)

        # Active-time accumulator (gaps ≤5min count as work).
        if len(stamps) >= 2:
            stamps.sort()
            project_ms = 0
            for a, b in zip(stamps, stamps[1:]):
                gap = b - a
                if 0 < gap <= 300:
                    project_ms += int(gap * 1000)
            work_ms_total += project_ms
            by_project[project_dir]["work_ms"] += project_ms

    return {
        "today_str": today_str,
        "totals": totals,
        "by_model": dict(by_model),
        "by_project": dict(by_project),
        "tool_counts": dict(tool_counts),
        "sessions": sessions_today,
        "work_ms": work_ms_total,
        "first_ts": first_ts,
        "last_ts": last_ts,
    }


def render(d: dict) -> str:
    t = d["totals"]
    sep = f" {DIM}│{RESET} "
    lines: list[str] = []

    # Header
    header = (
        f"{MAGENTA}{BOLD}Usage — {d['today_str']}{RESET}"
        f"{DIM}  (all Claude Code sessions, local time){RESET}"
    )
    lines.append(header)

    # Line 1 — cost / time / sessions / messages
    work_ms = d["work_ms"]
    wt_color = LIME if work_ms < 4 * 3_600_000 else (
        YELLOW if work_ms < 8 * 3_600_000 else ORANGE
    )
    td_color = LIME if t["cost"] < 20 else (YELLOW if t["cost"] < 50 else ORANGE)
    span_txt = ""
    if d["first_ts"] and d["last_ts"] and d["last_ts"] > d["first_ts"]:
        f_str = datetime.fromtimestamp(d["first_ts"]).strftime("%H:%M")
        l_str = datetime.fromtimestamp(d["last_ts"]).strftime("%H:%M")
        span_txt = f"{DIM}span: {RESET}{BLUE}{f_str}–{l_str}{RESET}"

    burn = 0.0
    if work_ms > 60_000:
        burn = t["cost"] / (work_ms / 3_600_000)
    burn_color = RED if burn >= 10 else (YELLOW if burn >= 3 else LIME)

    line1_parts = [
        f"{DIM}cost: {RESET}{td_color}{BOLD}{fmt_money(t['cost'])}{RESET}",
        f"{DIM}active: {RESET}{wt_color}{fmt_worktime(work_ms)}{RESET}",
    ]
    if burn > 0:
        line1_parts.append(f"{burn_color}{fmt_money(burn)}/hr{RESET}")
    line1_parts.append(
        f"{DIM}sessions: {RESET}{CYAN}{len(d['sessions'])}{RESET}"
    )
    line1_parts.append(
        f"{DIM}you: {RESET}{CYAN}{t['user_prompts']}{RESET} "
        f"{DIM}claude: {RESET}{CYAN}{t['assistant_msgs']}{RESET}"
    )
    if span_txt:
        line1_parts.append(span_txt)
    lines.append(sep.join(line1_parts))

    # Line 2 — tokens
    total_in = t["input"] + t["cache_read"] + t["cache_create"]
    cache_pct = (t["cache_read"] / total_in * 100) if total_in else 0.0
    cc = LIME if cache_pct >= 90 else (YELLOW if cache_pct >= 70 else RED)
    tok_parts = [
        f"{DIM}input: {RESET}{PURPLE}{fmt_tok(total_in)}{RESET}",
        f"{DIM}output: {RESET}{PINK}{fmt_tok(t['output'])}{RESET}",
        f"{DIM}cache-read: {RESET}{CYAN}{fmt_tok(t['cache_read'])}{RESET}",
        f"{DIM}cache-write: {RESET}{TEAL}{fmt_tok(t['cache_create'])}{RESET}",
    ]
    if total_in:
        tok_parts.append(f"{DIM}reused: {RESET}{cc}{cache_pct:.0f}%{RESET}")
    lines.append(sep.join(tok_parts))

    # Line 3 — tool use + per-model cost split
    if t["tool_uses"]:
        lines.append(
            f"{DIM}tool calls: {RESET}{ORANGE}{t['tool_uses']}{RESET}"
        )

    if d["by_model"]:
        models_sorted = sorted(
            d["by_model"].items(), key=lambda kv: -kv[1]["cost"]
        )
        model_colors = {
            "opus": MAGENTA, "sonnet": BLUE, "haiku": GREEN, "other": GREY,
        }
        bits = []
        total_cost = t["cost"] or 1.0
        for fam, v in models_sorted:
            if v["cost"] <= 0 and v["msgs"] == 0:
                continue
            pct = 100 * v["cost"] / total_cost
            col = model_colors.get(fam, GREY)
            bits.append(
                f"{col}{fam}{RESET} {BOLD}{fmt_money(v['cost'])}{RESET}"
                f"{DIM} ({pct:.0f}%, {v['msgs']}msg){RESET}"
            )
        if bits:
            lines.append(f"{DIM}by model: {RESET}" + "  ".join(bits))

    # Line 4+ — per-project breakdown (top 6 by cost)
    projects_sorted = sorted(
        d["by_project"].items(), key=lambda kv: -kv[1]["cost"]
    )
    projects_sorted = [
        (k, v) for k, v in projects_sorted
        if v["cost"] > 0 or v["msgs"] > 0
    ]
    if projects_sorted:
        lines.append(f"{DIM}── by project ─────────────────────────────{RESET}")
        total_cost = t["cost"] or 1.0
        for proj, v in projects_sorted[:6]:
            pct = 100 * v["cost"] / total_cost
            wt = fmt_worktime(v["work_ms"])
            label = project_label(proj)
            bar_str = bar(pct, width=10, color=_bar_color(pct))
            lines.append(
                f"  {bar_str} {BOLD}{fmt_money(v['cost']):>7}{RESET} "
                f"{DIM}{pct:4.0f}%{RESET}  "
                f"{CYAN}{label}{RESET} "
                f"{DIM}· {wt} · {v['msgs']}msg · "
                f"{len(v['sessions'])}sess{RESET}"
            )
        if len(projects_sorted) > 6:
            extra = len(projects_sorted) - 6
            rest_cost = sum(v["cost"] for _, v in projects_sorted[6:])
            lines.append(
                f"  {DIM}…and {extra} more ({fmt_money(rest_cost)}){RESET}"
            )

    # Line X — top tools
    if d["tool_counts"]:
        tools_sorted = sorted(
            d["tool_counts"].items(), key=lambda kv: -kv[1]
        )[:8]
        parts = [
            f"{ORANGE}{name}{RESET}{DIM}×{RESET}{CYAN}{cnt}{RESET}"
            for name, cnt in tools_sorted
        ]
        lines.append(f"{DIM}top tools: {RESET}" + " ".join(parts))

    return "\n".join(lines)


def _bar_color(pct: float) -> str:
    if pct >= 50:
        return ORANGE
    if pct >= 25:
        return YELLOW
    if pct >= 10:
        return GREEN
    return BLUE


def main() -> None:
    data = collect_today()
    sys.stdout.write(render(data) + "\n")


if __name__ == "__main__":
    main()

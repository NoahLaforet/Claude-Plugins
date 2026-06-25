#!/usr/bin/env python3
"""
skill_router.py - UserPromptSubmit hook.

Scans the user's prompt for HIGH-PRECISION signals (file extensions, specific
URLs, distinctive keywords) and injects a short reminder suggesting matching
skills. Claude still decides whether to actually use them.

Design rules (keep it this way so it stays useful, not noisy):
  - Anchor every rule to a hard signal: a file extension, a known URL shape, a
    literal syntax token, or a keyword that is unambiguous in Noah's context.
    NEVER match on vague intent words ("design", "debug", "build", "review") -
    those fire on everything and belong to description-based auto-invocation.
  - Stay SILENT when nothing matches. No output = no mess.
  - Cap at 3 suggestions per prompt.
  - Never block the prompt: any error exits 0 with no output.
  - Skip entirely if the user already typed a /slash-command.

To add a rule: append to RULES. `inc` must be a tight regex. `exc` (optional)
suppresses the rule if it also matches. Order = priority (first wins the cap).
"""
import sys, json, re

# (skill, why, include-regex, exclude-regex|None)
RULES = [
    # ---- documents & files (extension / syntax anchored) ----
    ("watch", "download it, extract frames + transcript, and actually view it",
     r"(https?://(www\.|m\.)?(youtube\.com/watch|youtu\.be/|vimeo\.com/\d|"
     r"tiktok\.com/|twitch\.tv/\S+/clip|streamable\.com/|dailymotion\.com/video)"
     r"|\b[\w./~+-]+\.(mp4|mov|mkv|webm|avi|m4v|flv|wmv|mpg|mpeg)\b)", None),
    ("pdf", "read/extract/merge/split/fill-forms/OCR on the PDF",
     r"(\b[\w./~ +-]*\.pdf\b|\bmerge (the )?pdfs?\b|\bfill (out )?(the )?pdf)", None),
    ("docx", "create/read/edit the Word document",
     r"(\b[\w./~ +-]*\.docx\b|\bword doc(ument)?s?\b)", None),
    ("json-canvas", "create/edit the Obsidian Canvas file",
     r"\b[\w./~ +-]*\.canvas\b", None),
    ("obsidian-bases", "create/edit the Obsidian .base file",
     r"\b[\w./~ +-]*\.base\b", None),
    ("obsidian-markdown", "Obsidian-flavored markdown (wikilinks, callouts, frontmatter, embeds)",
     r"(\[\[[^\[\s\]]|\bwikilink|\bobsidian\b[\s\S]{0,30}(note|callout|frontmatter|embed|tag))", None),
    ("agent-browser", "token-efficient browser automation (nav/click/fill/scrape via accessibility-tree refs)",
     r"(scrape [\s\S]{0,30}(page|site|url|data)|fill out the form|automate the browser|"
     r"log ?in to [\s\S]{0,30}(site|page)|click the [\s\S]{0,30}button on|navigate to [\s\S]{0,20}and (click|fill|extract))", None),
    ("defuddle", "extract clean markdown from the web page (cheaper than WebFetch); skip for .md URLs",
     r"((read|summari[sz]e|tl;?dr|what'?s? (in|does)|extract|analy[sz]e|article|blog ?post)"
     r"[\s\S]{0,80}https?://\S+|https?://\S+[\s\S]{0,80}(read|summari[sz]e|tl;?dr|article))",
     r"(youtube\.com|youtu\.be|vimeo\.com|tiktok\.com|twitch\.tv|\.pdf\b|\.md\b|greenhouse|lever\.co|myworkdayjobs|ashbyhq)"),

    # ---- code domains (keyword / extension anchored) ----
    ("embedded-systems", "firmware/RTOS/peripheral work",
     r"\b(stm32|esp32|freertos|\brtos\b|bare.?metal|firmware|microcontroller|"
     r"interrupt handler|dma transfer|\bi2c\b|\bspi\b|\buart\b)\b", None),
    ("cpp-pro", "modern C++ authoring/optimizing/debugging",
     r"(\b[\w./~+-]+\.(cpp|cc|cxx|hpp|hh)\b|\bc\+\+\b|template metaprogram|\bstd::|cmakelists)", None),
    ("swiftui-pro / swiftui-design-skill / animation-patterns",
     "SwiftUI: code review (pro), visual design (design-skill), motion (animation-patterns)",
     r"(\b[\w./~+-]+\.swift\b|\bswiftui\b)", None),
    ("claude-api", "Anthropic SDK / Claude API work (include prompt caching)",
     r"(anthropic sdk|claude api|anthropic api|prompt cach|@anthropic-ai/sdk|import anthropic)",
     r"(openai|\-openai\.py|\-generic\.py)"),
    ("mcp-builder", "building an MCP server",
     r"(\bmcp server\b[\s\S]{0,40}(build|creat|writ|implement|make)|fastmcp|@modelcontextprotocol)", None),
    ("python-testing", "pytest strategy / fixtures / mocking / coverage",
     r"(\bpytest\b|\btest\b[\s\S]{0,20}\bpython\b|\bpython\b[\s\S]{0,20}\bunit ?test)", None),
    ("ios-simulator-skill", "drive the iOS Simulator (build/boot/UI test/screenshot)",
     r"(ios simulator|\bsimulator\b[\s\S]{0,25}(xcode|iphone|ipad|\.app|boot|launch))", None),

    # ---- Noah's projects (tight intent) ----
    ("sentinel-status", "read current Sentinel project state",
     r"(sentinel[\s\S]{0,25}(status|what'?s left|where am i|todo|catch me up|update)"
     r"|(status|what'?s left|where am i|catch me up)[\s\S]{0,25}sentinel)", None),
    ("cse-220", "CSE 220 computer architecture help",
     r"(\bcse ?220\b|\brisc-?v\b|\bisa\b|pipelin|cache (miss|hit)|\bscarab\b)", None),
    ("sky130-flow", "sky130 / OpenROAD / TinyTapeout RTL-to-GDS",
     r"\b(sky130|openroad|openlane|tinytapeout|rtl-?to-?gds|klayout|\.gds\b)\b", None),

    # ---- job search (proficiently-*) ----
    ("proficiently-apply", "fill out the job application",
     r"(boards\.greenhouse\.io|greenhouse\.io|jobs\.lever\.co|lever\.co|"
     r"myworkdayjobs\.com|\.ashbyhq\.com|apply (to|for) (this|the) (job|role|position))", None),
    ("proficiently-cover-letter", "write a tailored cover letter",
     r"\bcover letter\b", None),
    ("proficiently-tailor-resume", "tailor the resume to a posting",
     r"(tailor[\s\S]{0,12}resume|resume[\s\S]{0,15}(for this|to this|to the) (job|role|posting))", None),
    ("proficiently-job-search", "search jobs matching resume + prefs",
     r"\b(job search|find (me )?jobs|search for (jobs|roles)|jobs matching)\b", None),

    # ---- config / meta ----
    ("update-config", "edit settings.json (hooks, permissions, env, automated behaviors)",
     r"(settings\.json|add (a )?permission|permission rule|set env\b|"
     r"from now on[\s\S]{0,15}(when|after|before)|each time (i|you)|whenever (i|you) (write|edit|run)|"
     r"(after|before) (i|you) (write|edit|run|commit)[\s\S]{0,20}(run|do|format))", None),
    ("keybindings-help", "customize keyboard shortcuts / keybindings.json",
     r"(keybinding|rebind|keyboard shortcut|chord (binding|shortcut))", None),
    ("graphify", "build/update a knowledge graph from inputs",
     r"\b(knowledge graph|graphify)\b", None),
]


def main():
    raw = sys.stdin.read()
    if not raw.strip():
        return
    try:
        data = json.loads(raw)
    except Exception:
        return
    prompt = (data.get("prompt") or "").strip()
    if not prompt or prompt.startswith("/"):
        return

    low = prompt.lower()
    hits = []
    for skill, why, inc, exc in RULES:
        if re.search(inc, low):
            if exc and re.search(exc, low):
                continue
            hits.append(f"  - `{skill}` - {why}")
        if len(hits) >= 3:
            break

    if not hits:
        return

    msg = (
        "[skill-router] High-precision signals detected in the prompt. "
        "Consider these skills if they actually fit the task (ignore if not):\n"
        + "\n".join(hits)
    )
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": msg,
        }
    }))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # never block the user's prompt

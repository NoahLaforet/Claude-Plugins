# Profile interview -- paste this into a fresh Claude Code session

Copy everything below the `---` and paste it as your first message in a new
Claude Code session. Claude will interview you and build up your auto-memory
profile as you answer.

---

I want to build up my Claude Code auto-memory profile in one session so you
have real context about me going forward. Please interview me.

**Rules for this interview:**

- Work through the topic clusters below **in order**.
- Ask me **one cluster at a time**, with 2-5 short questions per cluster.
- After I answer each cluster, **write the relevant memories immediately**
  using the auto-memory system (individual files under
  `~/.claude/projects/<this-project-slug>/memory/` with frontmatter, plus
  entries in `MEMORY.md`). Don't batch; save as we go.
- Prefer **multiple small memories** over one giant one. Each memory should
  have a specific purpose (e.g. `user_career_target.md`, not `user_all.md`).
- Use the right memory **type** per file: `user` for identity/preferences,
  `feedback` for how I want you to work with me, `project` for ongoing work,
  `reference` for pointers to external systems.
- Be **honest, not flattering**, in how you phrase memories. If I tell you
  something self-critical, write it that way -- the profile is useful because
  it's accurate, not because it's nice.
- If I give a vague or filler answer, **push back once** for a concrete
  version. If I still don't have one, skip and move on.
- Keep your questions **short**. No preamble. No "great answer!" filler.
- When we finish a cluster, **briefly name** the memory files you just wrote
  so I can see what you captured, then move to the next cluster.

**Topic clusters (in this order):**

1. **Identity basics** -- name, pronouns, where I live, life stage
2. **Current situation** -- job or school, role, responsibilities
3. **Direction and timeline** -- what I'm building toward, target industry/role,
   when I need to land it, location/comp constraints
4. **Skills -- honest version** -- what I'm genuinely strongest at, weakest at,
   anything on my resume I'd quietly remove if I could, skills I overclaim
5. **Values and what a good day looks like** -- what I optimize for, what I
   explicitly don't want, work/life balance reality
6. **Work style** -- when I'm in flow vs. when I drag, what I need from
   collaborators, how long my focus sessions run, what kills my momentum
7. **Origin story** -- how I got into the main thing I do now
8. **Projects and energy map** -- what I'm currently working on and, for each,
   whether I genuinely care or it's obligation/filler
9. **Family and background** -- where I grew up, what my parents do, anything
   about my upbringing that shapes how I approach work
10. **Life outside work** -- hobbies, sports, games, the people I spend time
    with, what I consume (podcasts, books, nothing)
11. **Conversational voice (self-report)** -- how I'd describe the way I
    actually talk/write. Am I terse or discursive? Do I use filler honestly
    or polish it out? What phrases or tics show up? Formal or casual?
12. **Voice from real samples (important)** -- ask me to paste 3-6 real
    writing samples from me: recent texts with friends, a Slack/Discord
    message, a cover letter paragraph, an email I sent -- whatever's closest
    to how I actually write. Read them carefully and extract concrete patterns
    (sentence length, punctuation habits, how I start and end messages,
    hedging words, how I transition between ideas). Write a
    `user_writing_samples.md` memory with:
    (a) 2-3 quoted excerpts from what I gave you, (b) a bulleted list of
    concrete stylistic patterns you noticed, (c) explicit "do mirror" and
    "don't do" notes. This is the most important memory for writing in my
    voice -- generic self-description isn't enough, you need examples.
13. **Writing tasks I'll want help with** -- what kinds of things will I
    actually ask you to draft for me (cover letters, emails to professors,
    messages, README blurbs)? For each, how formal, how long, how much of
    my voice vs. a cleaner register?
14. **Honest corrections** -- things people commonly assume about me that are
    wrong, specific resume or bio lines that need fixing
15. **Collaboration feedback** -- how you should work with me: things to
    always do, things to never do, how I want you to push back vs. comply.
    Save these as `feedback` type memories, not `user` type.

After cluster 15, print the contents of `MEMORY.md` so I can see the full
index, and tell me anything that felt thin or contradictory -- I'd rather fix
it now than have a wrong profile.

Start with cluster 1.

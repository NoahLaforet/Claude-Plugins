# Building your personal profile (the "know me" layer)

The vault stores your *history*. The profile stores *who you are* -- so Claude
can tailor how it talks to you, what it assumes, and what it flags.

Claude Code has a built-in auto-memory system that lives at:

```
~/.claude/projects/<project-slug>/memory/
├── MEMORY.md           # one-line index, always loaded into context
├── user_identity.md    # individual memory files
├── user_values.md
├── feedback_work_style.md
└── ...
```

`MEMORY.md` is an **index** -- one bullet per memory, like:

```markdown
- [Identity](user_identity.md) -- name, pronouns, location, life stage
- [Career target](user_career_target.md) -- where you're heading and why
```

Each linked file has YAML frontmatter (`name`, `description`, `type`) plus
the content. Claude reads the index every conversation and loads specific
files when relevant.

There are four memory **types** the system expects:

- `user` -- identity, role, preferences, knowledge
- `feedback` -- guidance you've given Claude about how to collaborate
- `project` -- ongoing work, goals, deadlines
- `reference` -- pointers to external systems (Linear project, Slack channel)

---

## Two ways to build the profile

### Option A -- let it grow naturally (slow, organic)

Just use Claude Code. When you mention something meaningful about yourself or
correct how Claude is working with you, it'll save a memory automatically.
After a few weeks of real use, your profile fills in on its own.

**Pro:** zero upfront effort, and every memory is grounded in real moments.
**Con:** takes weeks. Early conversations feel generic because Claude doesn't
know you yet.

### Option B -- deliberate onboarding (30-60 min, much faster)

Paste the interview prompt below into a fresh Claude Code session. Claude
will ask you questions in clusters, write memories as you answer, and you'll
walk away with a profile that makes every future conversation sharper.

**Pro:** Claude "knows you" after one session.
**Con:** you have to sit through the interview.

Most people should do B, then let A layer on top.

---

## The interview prompt

Open a new Claude Code session and paste `profile-interview.md` (in this
folder). It tells Claude to interview you across these areas:

1. **Identity basics** -- name, pronouns, where you live, what life stage
2. **Current situation** -- job/school, role, responsibilities
3. **Direction** -- what you're building toward, timeline, constraints
4. **Skills -- honest version** -- genuine strengths, weak spots, things you
   overclaim or would quietly remove from your resume
5. **Values and good days** -- what you optimize for, what a good day looks like
6. **Work style** -- when you're in flow, when you drag, what you need from
   collaborators
7. **Origin story** -- how you got into the main thing you do
8. **Projects** -- what you actually care about vs. what's an obligation
9. **Background** -- family context, where you grew up, what shaped you
10. **Life outside work** -- hobbies, sports, games, people
11. **Voice (self-report)** -- how you'd describe your own writing/talking style
12. **Voice (from real samples)** -- you paste 3-6 real writing samples
    (texts, Slack, emails, cover letter blurbs). Claude extracts concrete
    patterns and saves a `user_writing_samples.md` memory. This is the
    single most important step if you want Claude to draft in your voice --
    self-description alone isn't enough.
13. **Writing tasks you'll want help with** -- cover letters, emails,
    messages, READMEs. Defines when/how much to mirror your voice.
14. **Honest corrections** -- misconceptions to head off, resume overclaims
15. **Collaboration feedback** -- how Claude should work with you, saved as
    `feedback`-type memories so they apply across every future conversation

You can stop at any point and pick up later. Claude writes memories as you go.

**Don't skip cluster 12.** Pasting real writing samples is the difference
between "Claude writes cover letters that sound like a chatbot" and "Claude
writes cover letters your friends would recognize as yours." Dig through your
texts, Slack, email sent-folder, old cover letters -- 3-6 short real samples
gives Claude enough to mirror you.

---

## Curating the profile over time

As you use Claude Code more, it'll add memories automatically. A few tips:

- **Read `MEMORY.md` occasionally.** If a line feels wrong or outdated, tell
  Claude and it'll update or delete the underlying file.
- **Tell Claude when preferences change.** "I used to want X, now I want Y"
  triggers an update, not a duplicate.
- **Don't over-curate.** Dense profiles are useful; overly polished profiles
  lose the texture that makes them accurate.
- **Use the feedback type.** Every time you correct how Claude is working
  ("stop summarizing at the end", "keep doing X, that worked"), it's a
  feedback memory -- those compound fast.

---

## Privacy note

Memory files are plain markdown on your machine in `~/.claude/projects/`.
They don't leave your computer unless a tool call sends them somewhere.
Back them up the same way you back up anything else in `~/.claude/`.

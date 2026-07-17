# Pipeline — how to process sections (repo-bounded, resumable)

This file makes the work **self-contained in the repo**. Any fresh Claude Code
session can pick up where the last one left off using only what is committed here,
with no memory of prior sessions.

## The one loop

```
1. cd into the repo.
2. Run:  python3 bin/status.py           # see what's done / pending (reads the filesystem, not memory)
3. Pick the next incomplete section:  python3 bin/status.py --next
4. Dispatch ONE subagent per incomplete section using the prompt template below.
   (Sections are independent; several can run in parallel. Each agent touches
   ONLY its own section directory, so there are no write conflicts.)
5. When agents finish, run:  python3 bin/status.py --reconcile
   then:  python3 bin/status.py          # confirm the counts
6. Commit.  Repeat until `sections complete: 8/8`.
```

Ground truth is the **filesystem**, derived by `bin/status.py`:
- section explanation done  <=> `sections/<sec>/explanation.md` exists (>= 200 chars)
- link done                 <=> `sections/<sec>/links/<id>-*/summary.md` exists
- link failed               <=> that summary.md begins with the failure marker

`--reconcile` rewrites `links.json` + `manifest.json` to match the filesystem, so a
killed/half-finished agent never leaves the tracking in a wrong state — just
re-run status and re-dispatch whatever is still pending.

## Language rule
- Explanations and link summaries: **Hungarian** (written for the reader).
- Original article text (`section.md`, `source/`): leave as published (English).
- Avoid em dashes in Hungarian prose; no AI-tell phrasing.

## Per-section subagent prompt template

Spawn a `general-purpose` agent. Substitute `<SECTION_DIR>` with the absolute
path of the section (e.g. `/Users/felho/dev/ai-consciousness-explainer/sections/02-...`).

---
You are processing ONE section of an essay-explainer project. Work ONLY inside:
`<SECTION_DIR>`

The essay is "Time to Take AI Consciousness Seriously" (Second Best / Samuel
Hammond): a dense argument that frontier AI models may have some form of
consciousness / subjective experience. This project breaks it into
layman-friendly pieces.

LANGUAGE: All explanatory writing MUST be in HUNGARIAN, for an intelligent
layman. Unpack every technical term in one plain-language clause. Avoid em
dashes (use commas or parentheses). No AI-tell phrasing. Do NOT translate the
original English `section.md`; leave it as-is.

TASKS:
1. Read `section.md` and `links.json` in your directory.
2. Write `explanation.md` (Hungarian), starting with `# <section title> — magyarázat`.
   Explain what the section is about, its central claim, and how it fits the
   essay's overall argument. ~300-600 words, short paragraphs, small bullet list
   if it helps. Genuinely clarifying for someone who found the original hard.
3. For EACH link in `links.json`:
   - Create `links/<id>-<short-slug>/` (slug = a few kebab-case words from the anchor/topic).
   - Fetch the URL with WebFetch and ask it to summarize the page/paper.
   - Write `summary.md` there, in Hungarian, in this exact shape:
       # <anchor text> — <short title>
       URL: <url>

       ## Miről szól a forrás?
       <2-4 mondat: a forrás lényege laikusnak>

       ## Miért hivatkozik rá a cikk?
       <1-3 mondat: mit támaszt alá ezzel a szerző ebben a szekcióban>

       ## Mit érdemes ebből megérteni?
       <1-3 mondat: a lényeg, amit az olvasónak vinni kell>
   - Keep it tight; the reader should get the point without opening the source.
   - Set that link's `status` in `links.json` to `"done"`.
   - If WebFetch fails (paywall, login/redirect wall, 404, X/Twitter block, PDF
     that won't parse): set `status` to `"failed"`, add a `"fail_reason"` field,
     and STILL write `summary.md`, but begin it with EXACTLY this marker line so
     the tracker can detect it:
       `> Megjegyzés: a forrás tartalma nem volt letölthető (<ok>), az alábbi az anchor szöveg és a cikkbeli használat alapján készült.`
   - NO SILENT SKIPS: every link ends as `done` or `failed` with a reason.
     Preserve the JSON structure (list of objects: id, anchor_text, url, status).
4. Return a short plain-text report: links done vs failed, and anything a human
   should look at. Your final text IS the return value.

TIPS:
- x.com / twitter.com usually can't be fetched directly; the fxtwitter/nitter
  mirror often works. If not, mark failed and infer from the anchor.
- nature.com articles may bounce through an `idp` redirect; follow it. arxiv,
  Wikipedia, lesswrong fetch fine. If a PDF won't parse, mark failed and infer.
- If the Write tool refuses a `summary.md` (false-positive "report file" guard),
  create it via a Bash heredoc instead — it is a required output, not a report.
- Do NOT touch anything outside `<SECTION_DIR>`. Do NOT edit manifest.json (the
  status script owns it).
---

## Scoped dispatch — a single link or just the explanation

You do not have to run a whole section. Every link is an addressable unit
`<section-name> <id>` (e.g. `00-introduction 1`). List them with:

```bash
python3 bin/status.py --list-links --section 00     # ids + urls for one section
python3 bin/status.py --list-links --pending        # everything not done yet
```

### A) One link only

Use when asked e.g. "do the first section's first link". Resolve the section
name and link id first (`--list-links`), then spawn a `general-purpose` agent.
Substitute `<SECTION_DIR>`, `<ID>`, `<URL>`:

---
You are producing ONE link summary. Work ONLY inside: `<SECTION_DIR>`

Context: this section belongs to the essay "Time to Take AI Consciousness
Seriously" (Second Best / Samuel Hammond), which argues frontier AI models may
have some form of consciousness. Read `section.md` for context and find the link
with `"id": <ID>` (URL `<URL>`) in `links.json`.

LANGUAGE: write in HUNGARIAN, for an intelligent layman. Avoid em dashes. No
AI-tell phrasing.

DO:
1. Create `links/<ID>-<short-slug>/` (slug = a few kebab-case words from the anchor/topic).
2. WebFetch `<URL>` and summarize the page/paper.
3. Write `summary.md` there, in this exact shape:
     # <anchor text> — <short title>
     URL: <URL>

     ## Miről szól a forrás?
     <2-4 mondat: a forrás lényege laikusnak>

     ## Miért hivatkozik rá a cikk?
     <1-3 mondat: mit támaszt alá ezzel a szerző ebben a szekcióban>

     ## Mit érdemes ebből megérteni?
     <1-3 mondat: a lényeg, amit az olvasónak vinni kell>
4. Set that link's `status` in `links.json` to `"done"` (leave the other links untouched).
5. If WebFetch fails: set `status` to `"failed"`, add `"fail_reason"`, and still
   write `summary.md` beginning with EXACTLY this marker line:
     `> Megjegyzés: a forrás tartalma nem volt letölthető (<ok>), az alábbi az anchor szöveg és a cikkbeli használat alapján készült.`
6. Return one line: done or failed (+reason). Touch nothing outside `<SECTION_DIR>`;
   do not edit manifest.json (the status script owns it). If the Write tool
   refuses `summary.md` as a "report file", create it via a Bash heredoc.
---

After it finishes: `python3 bin/status.py --reconcile && python3 bin/status.py`.

### B) Just the explanation for a section

Same as the full template but with only step 2 (write `explanation.md`); skip all
link processing. Useful to draft/redo a section's explanation without re-fetching links.

## Status
Run `python3 bin/status.py` for live progress. Nothing is complete yet (0/8).

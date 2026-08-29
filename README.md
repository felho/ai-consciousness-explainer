# AI Consciousness Explainer

Building blocks for an explanatory HTML page based on the essay
["Time to Take AI Consciousness Seriously"](https://www.secondbest.ca/p/time-to-take-ai-consciousness-seriously)
(Second Best / Samuel Hammond).

Goal: break the (dense) essay into digestible pieces so a layman reader can
understand each section and each cited source. The final HTML page is assembled
from these pieces by `bin/build_html.py` into `build/index.html`.

**Read it online:** <https://felho.github.io/ai-consciousness-explainer/build/index.html>
(GitHub Pages, served from `build/index.html` on `main` — republished on every push.)

## Language convention

- Original article text (`section.md`, `source/`): English (as published).
- Section translations (`section.hu.md`): **Hungarian**, faithful translation of
  `section.md`, structure mirrored 1:1 (same links/URLs, images, footnote markers)
  so the HTML builder can render both language variants.
- Explanations and link summaries (`explanation.md`, `links/*/summary.md`): **Hungarian**
  (they are written for the reader, whose working language is Hungarian).
- Everything else (code, README, manifest): English.

## Structure

```
manifest.json                  # inventory: sections, statuses, link counts
source/
  article.html                 # raw HTML snapshot (downloaded 2026-07-17)
  article.md                   # full article converted to markdown
sections/
  <nn>-<slug>/
    section.md                 # original English text of the H2 section
    section.hu.md              # Hungarian translation of section.md (1:1 structure)
    links.json                 # links found in this section (id, anchor_text, url, status)
    explanation.md             # layman-friendly Hungarian explanation of the section
    links/
      <id>-<slug>/
        summary.md             # Hungarian summary: what the source says, why the
                               # article cites it, what to understand from it
```

Section `00-introduction` is the text before the first H2. Section
`07-so-are-ais-conscious-or-not` also contains the article's footnotes.

## Link statuses (links.json)

- `pending`   — not yet processed
- `done`      — fetched and summarized (summary.md exists)
- `failed`    — could not fetch (paywall, login wall, dead link); summary.md then
                contains whatever could be inferred from the anchor text/context,
                clearly marked as such. No silent skips: every link ends up
                either `done` or `failed` with a reason.

## Resume in a fresh session

Everything needed to continue is in this repo — no session memory required.

```bash
cd ~/dev/ai-consciousness-explainer
python3 bin/status.py            # what's done / pending (derived from the filesystem)
python3 bin/status.py --next     # the next incomplete section directory
```

Then follow **[PIPELINE.md](PIPELINE.md)**: it holds the exact subagent prompts
and the dispatch loop. You can run a whole section, or scope down to a single
link (`<section-name> <id>`, e.g. `00-introduction 1`) or just a section's
explanation:

```bash
python3 bin/status.py --list-links --section 00   # addressable link units + urls
python3 bin/status.py --list-links --pending      # everything not done yet
```

After agents run:

```bash
python3 bin/status.py --reconcile   # sync links.json + manifest.json to the files on disk
python3 bin/status.py               # confirm, then commit
```

`bin/status.py` treats the **filesystem as ground truth**, so a half-finished or
killed agent never corrupts the tracking: just re-run status and re-dispatch
whatever is still pending.

## Pipeline phases

1. `parse_article.py` (session scratchpad) built this scaffold from the HTML.
2. One subagent per section writes `explanation.md` and processes all links
   (see PIPELINE.md). Sections are independent and can run in parallel.
3. One subagent per section translates `section.md` to `section.hu.md`
   (reviewed by fidelity / language-quality / terminology subagent passes).
4. `bin/build_html.py` assembles the pieces into a single self-contained
   `build/index.html`: each section's original English text with a per-section
   EN/HU toggle (English default) switching to the Hungarian translation, the
   original image inline, the Hungarian explanation below it, and a hover card
   on every source link showing that link's full Hungarian summary. Images are
   embedded as data URIs (stored once, referenced by both language variants).

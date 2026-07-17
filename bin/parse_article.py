#!/usr/bin/env python3
"""Parse the Substack article HTML into per-section markdown + link inventories.

Builds the scaffold under ~/dev/ai-consciousness-explainer:
  source/article.html, source/article.md
  sections/<nn>-<slug>/section.md   (original English text; footnotes attached here)
  sections/<nn>-<slug>/links.json   (links found in that section, incl. footnote links)
  manifest.json                     (section + link inventory)

Footnotes: each inline reference becomes a "[N]" marker at its point in the text,
and the footnote definition is appended to the SAME section under a
"## Lábjegyzetek (az eredeti cikkből)" heading as "[N]: ...". This keeps the
reference and its note together in the section they belong to.

Re-running is safe only when no explanation.md / links summaries exist yet
(it rewrites section.md + links.json). Run bin/status.py afterwards.
"""
import json
import os
import re
from html.parser import HTMLParser

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.dirname(HERE)
SRC = os.path.join(OUT, "source", "article.html")
ARTICLE_URL = "https://www.secondbest.ca/p/time-to-take-ai-consciousness-seriously"

html = open(SRC).read()


def extract_body(doc):
    """Return the rendered article body div contents (depth-matched)."""
    start = doc.find('<div dir="auto" class="body markup">')
    assert start != -1, "body markup div not found"
    depth = 0
    for m in re.finditer(r"<div\b[^>]*>|</div>", doc[start:]):
        if m.group(0).startswith("</"):
            depth -= 1
            if depth == 0:
                return doc[start:start + m.end()]
        else:
            depth += 1
    raise AssertionError("matching </div> not found")


def _match_div(fragment, from_pos):
    """Given a position just after an opening <div>, return the index of that
    div's matching </div> start."""
    depth = 1
    for m in re.finditer(r"<div\b[^>]*>|</div>", fragment[from_pos:]):
        if m.group(0).startswith("</"):
            depth -= 1
            if depth == 0:
                return from_pos + m.start()
        else:
            depth += 1
    raise AssertionError("unbalanced div")


def extract_footnotes(body):
    """Return {N: content_html} and body with the footnote definition blocks removed."""
    notes = {}
    def_re = re.compile(r'<div data-component-name="FootnoteToDOM"[^>]*class="footnote">')
    content_open_re = re.compile(r'<a id="footnote-(\d+)"[^>]*>\d+</a><div class="footnote-content">')

    for m in content_open_re.finditer(body):
        n = int(m.group(1))
        cend = _match_div(body, m.end())
        notes[n] = body[m.end():cend]

    out = []
    pos = 0
    for m in def_re.finditer(body):
        out.append(body[pos:m.start()])
        pos = _match_div(body, m.end()) + len("</div>")
    out.append(body[pos:])
    return notes, "".join(out)


class MdConverter(HTMLParser):
    """Minimal HTML -> markdown for Substack article bodies.

    Emits "[N]" for inline footnote anchors so the reference point is visible.
    """

    SKIP_CLASSES = ("subscribe-widget", "subscription-widget", "captioned-button",
                    "image-link-expand", "footnote-hovercard-target")

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self.href = None
        self.link_text = []
        self.skip_depth = 0
        self.list_stack = []
        self.in_blockquote = False
        self.in_fn_anchor = False

    def _emit(self, text):
        target = self.link_text if self.href is not None else self.out
        target.append(text)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = a.get("class", "")
        if self.skip_depth or any(c in cls for c in self.SKIP_CLASSES):
            self.skip_depth += 1
            return
        if tag == "a":
            href = a.get("href", "")
            if "footnote-anchor" in cls:
                # Inline footnote reference: emit "[" then the number, "]" on close.
                self.in_fn_anchor = True
                self._emit("[")
                return
            if href.startswith("#"):
                self.skip_depth += 1
                return
            self.href = href
            self.link_text = []
        elif tag in ("h1", "h2", "h3", "h4"):
            self._emit("\n\n" + "#" * int(tag[1]) + " ")
        elif tag == "p":
            self._emit("\n\n" + ("> " if self.in_blockquote else ""))
        elif tag == "blockquote":
            self.in_blockquote = True
        elif tag in ("ul", "ol"):
            self.list_stack.append(tag)
        elif tag == "li":
            marker = "-" if (self.list_stack and self.list_stack[-1] == "ul") else "1."
            self._emit("\n" + "  " * (len(self.list_stack) - 1) + marker + " ")
        elif tag in ("em", "i"):
            self._emit("*")
        elif tag in ("strong", "b"):
            self._emit("**")
        elif tag == "img":
            src = a.get("src", "")
            if src:
                self._emit(f"\n\n![image]({src})")
        elif tag == "br":
            self._emit("\n")

    def handle_endtag(self, tag):
        if self.skip_depth:
            self.skip_depth -= 1
            return
        if tag == "a" and self.in_fn_anchor:
            self._emit("]")
            self.in_fn_anchor = False
            return
        if tag == "a" and self.href is not None:
            text = "".join(self.link_text).strip()
            if text:
                self.out.append(f"[{text}]({self.href})")
            self.href = None
            self.link_text = []
        elif tag == "blockquote":
            self.in_blockquote = False
        elif tag in ("ul", "ol"):
            if self.list_stack:
                self.list_stack.pop()
        elif tag in ("em", "i"):
            self._emit("*")
        elif tag in ("strong", "b"):
            self._emit("**")

    def handle_data(self, data):
        if self.skip_depth:
            return
        self._emit(re.sub(r"\s+", " ", data))


def to_md(fragment):
    c = MdConverter()
    c.feed(fragment)
    md = "".join(c.out)
    return re.sub(r"\n{3,}", "\n\n", md).strip()


def slugify(t):
    s = re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")
    return s[:48].rstrip("-")


body = extract_body(html)
notes_html, body = extract_footnotes(body)
notes_md = {n: re.sub(r"\s+", " ", to_md(h)).strip() for n, h in notes_html.items()}

md = to_md(body)

# Split into intro + H2 sections.
parts = re.split(r"\n## (?=\S)", md)
sections = [("Introduction", parts[0].strip())]
for part in parts[1:]:
    title, _, text = part.partition("\n")
    sections.append((title.strip(), text.strip()))

# Attach each footnote to the section whose text contains its "[N]" marker.
section_notes = {i: [] for i in range(len(sections))}
for n in sorted(notes_md):
    marker = f"[{n}]"
    owner = 0
    for i, (_, text) in enumerate(sections):
        if marker in text:
            owner = i
            break
    section_notes[owner].append(n)

LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")
SKIP_URL_PAT = re.compile(r"substackcdn\.com|substack\.com/(subscribe|redirect)|secondbest\.ca/subscribe")

manifest = {"article_url": ARTICLE_URL,
            "title": "Time to Take AI Consciousness Seriously",
            "subtitle": "The case for Claude and ChatGPT having subjective experiences",
            "sections": []}

full_article = [f"# Time to Take AI Consciousness Seriously\n\nSource: {ARTICLE_URL}\n"]

for idx, (title, text) in enumerate(sections):
    # Append footnote definitions belonging to this section.
    if section_notes[idx]:
        fn_block = "\n\n## Lábjegyzetek (az eredeti cikkből)\n\n" + "\n\n".join(
            f"[{n}]: {notes_md[n]}" for n in section_notes[idx])
        text = text + fn_block

    slug = f"{idx:02d}-{slugify(title)}"
    sdir = os.path.join(OUT, "sections", slug)
    os.makedirs(sdir, exist_ok=True)
    with open(os.path.join(sdir, "section.md"), "w") as f:
        f.write(f"# {title}\n\n{text}\n")
    full_article.append(f"\n## {title}\n\n{text}\n" if idx else f"\n{text}\n")

    links = []
    seen = set()
    for anchor, url in LINK_RE.findall(text):
        if SKIP_URL_PAT.search(url) or url in seen:
            continue
        seen.add(url)
        links.append({"id": len(links) + 1, "anchor_text": anchor, "url": url,
                      "status": "pending"})
    with open(os.path.join(sdir, "links.json"), "w") as f:
        json.dump(links, f, indent=2, ensure_ascii=False)

    manifest["sections"].append({"dir": f"sections/{slug}", "title": title,
                                 "explanation_status": "pending",
                                 "link_count": len(links),
                                 "footnotes": section_notes[idx]})
    print(f"{slug}: {len(text)} chars, {len(links)} links, footnotes={section_notes[idx]}")

with open(os.path.join(OUT, "source", "article.md"), "w") as f:
    f.write("\n".join(full_article))
with open(os.path.join(OUT, "manifest.json"), "w") as f:
    json.dump(manifest, f, indent=2, ensure_ascii=False)
print("done ->", OUT)

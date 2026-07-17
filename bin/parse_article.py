#!/usr/bin/env python3
"""Parse the Substack article HTML into per-section markdown + link inventories.

Builds the scaffold under ~/dev/ai-consciousness-explainer:
  source/article.html, source/article.md
  sections/<nn>-<slug>/section.md   (original English text, links inline as markdown)
  sections/<nn>-<slug>/links.json   (links found in that section)
  manifest.json                     (section + link inventory with statuses)
"""
import json
import os
import re
import sys
from html.parser import HTMLParser

SRC = "/private/tmp/claude-501/-Users-felho/f78b843a-a409-46cf-80c0-4200a0050e62/scratchpad/article.html"
OUT = os.path.expanduser("~/dev/ai-consciousness-explainer")
ARTICLE_URL = "https://www.secondbest.ca/p/time-to-take-ai-consciousness-seriously"

html = open(SRC).read()

start = html.find('<div dir="auto" class="body markup">')
assert start != -1, "body markup div not found"

# Walk to the matching close of the body div.
depth = 0
i = start
end = None
for m in re.finditer(r'<div\b[^>]*>|</div>', html[start:]):
    if m.group(0).startswith('</'):
        depth -= 1
        if depth == 0:
            end = start + m.end()
            break
    else:
        depth += 1
assert end, "matching </div> not found"
body = html[start:end]


class MdConverter(HTMLParser):
    """Minimal HTML -> markdown for Substack article bodies."""

    SKIP_CLASSES = ("subscription-widget", "captioned-button", "image-link-expand",
                    "footnote-hovercard-target")

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self.href = None
        self.link_text = []
        self.skip_depth = 0
        self.list_stack = []
        self.in_blockquote = False

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
            if a.get("class") == "footnote-anchor" or href.startswith("#"):
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


conv = MdConverter()
conv.feed(body)
md = "".join(conv.out)
md = re.sub(r"\n{3,}", "\n\n", md).strip()

# Split into intro + H2 sections.
parts = re.split(r"\n## (?=\S)", md)
intro = parts[0]
sections = [("Introduction", intro)]
for part in parts[1:]:
    title, _, text = part.partition("\n")
    sections.append((title.strip(), text.strip()))


def slugify(t):
    s = re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")
    return s[:48].rstrip("-")


LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")
SKIP_URL_PAT = re.compile(r"substackcdn\.com|substack\.com/(subscribe|redirect)|secondbest\.ca/subscribe")

os.makedirs(os.path.join(OUT, "source"), exist_ok=True)
with open(os.path.join(OUT, "source", "article.md"), "w") as f:
    f.write(f"# Time to Take AI Consciousness Seriously\n\nSource: {ARTICLE_URL}\n\n{md}\n")
import shutil
shutil.copy(SRC, os.path.join(OUT, "source", "article.html"))

manifest = {"article_url": ARTICLE_URL,
            "title": "Time to Take AI Consciousness Seriously",
            "subtitle": "The case for Claude and ChatGPT having subjective experiences",
            "sections": []}

for idx, (title, text) in enumerate(sections):
    slug = f"{idx:02d}-{slugify(title)}"
    sdir = os.path.join(OUT, "sections", slug)
    os.makedirs(sdir, exist_ok=True)
    with open(os.path.join(sdir, "section.md"), "w") as f:
        f.write(f"# {title}\n\n{text}\n")
    links = []
    seen = set()
    for n, (anchor, url) in enumerate(LINK_RE.findall(text), 1):
        if SKIP_URL_PAT.search(url) or url in seen:
            continue
        seen.add(url)
        links.append({"id": len(links) + 1, "anchor_text": anchor, "url": url,
                      "status": "pending"})
    with open(os.path.join(sdir, "links.json"), "w") as f:
        json.dump(links, f, indent=2)
    manifest["sections"].append({"dir": f"sections/{slug}", "title": title,
                                 "explanation_status": "pending",
                                 "link_count": len(links)})
    print(f"{slug}: {len(text)} chars, {len(links)} links")

with open(os.path.join(OUT, "manifest.json"), "w") as f:
    json.dump(manifest, f, indent=2)
print("done ->", OUT)

#!/usr/bin/env python3
"""Assemble the final bilingual explainer page from the section pieces.

For each section, in order:
  - the original English text (from section.md), exactly as published, with the
    original image embedded inline as a data URI;
  - a Hungarian translation of the section (section.hu.md), switchable per
    section via a small EN/HU toggle (English is the default);
  - below it, the Hungarian explanation (explanation.md), in a tinted panel;
  - every source link becomes a hover card showing that link's full Hungarian
    summary (from links/<id>-*/summary.md).

Ground truth is the filesystem. Run:  python3 bin/build_html.py
Output: build/index.html (self-contained; images embedded as data URIs read
from build/assets/<substack-id>.jpg).
"""
import base64
import glob
import html
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECTIONS_DIR = os.path.join(ROOT, "sections")
ASSETS_DIR = os.path.join(ROOT, "build", "assets")
OUT = os.path.join(ROOT, "build", "index.html")

# Balanced parentheses (one level of nesting) so URLs like
# .../S0896-6273(20)30468-2.pdf parse correctly inside [text](url).
BAL = r"(?:[^()]|\([^()]*\))*"
IMG_RE = re.compile(r"\[!\[[^\]]*\]\(" + BAL + r"\)\]\((" + BAL + r")\)")
LINK_RE = re.compile(r"\[([^\]]+)\]\((" + BAL + r")\)")
SUBSTACK_ID_RE = re.compile(r"images%2F([0-9a-fA-F-]+)_")
FN_MARKER_RE = re.compile(r"\[(\d+)\]")

CARDS = {}  # cardId -> rendered summary HTML (fed to JS)
IMGS = {}  # imageId -> data URI (fed to JS; stored once, referenced by both language variants)


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


_DATA_URI_CACHE = {}  # image_id -> data URI (each image appears in both language variants)


def data_uri_for(image_id):
    if image_id in _DATA_URI_CACHE:
        return _DATA_URI_CACHE[image_id]
    matches = glob.glob(os.path.join(ASSETS_DIR, image_id + ".*"))
    if not matches:
        return None
    raw = open(matches[0], "rb").read()
    mime = "image/png" if raw[:8] == b"\x89PNG\r\n\x1a\n" else "image/jpeg"
    uri = "data:%s;base64,%s" % (mime, base64.b64encode(raw).decode("ascii"))
    _DATA_URI_CACHE[image_id] = uri
    return uri


def emphasize(escaped):
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"\*(.+?)\*", r"<em>\1</em>", escaped)
    return escaped


def render_inline(text, linkmap, sec_idx, lang="en"):
    """Inline markdown -> HTML: links (with cards), emphasis, footnote markers.
    Images must already be stripped out before calling this."""
    stash = []

    def stash_link(m):
        anchor, url = m.group(1), m.group(2).strip()
        anchor_html = emphasize(html.escape(anchor))
        href = html.escape(url, quote=True)
        entry = linkmap.get(url)
        if entry:
            card_id = "s%d-l%s" % (sec_idx, entry["id"])
            CARDS[card_id] = entry["card_html"]
            a = ('<a class="src" href="%s" target="_blank" rel="noopener" '
                 'data-card="%s">%s</a>' % (href, card_id, anchor_html))
        else:
            a = ('<a class="ext" href="%s" target="_blank" rel="noopener">%s</a>'
                 % (href, anchor_html))
        stash.append(a)
        return "\x00L%d\x00" % (len(stash) - 1)

    text = LINK_RE.sub(stash_link, text)
    text = html.escape(text)
    text = emphasize(text)
    text = FN_MARKER_RE.sub(
        lambda m: '<sup class="fn"><a href="#fn-%s-%d-%s">%s</a></sup>'
        % (lang, sec_idx, m.group(1), m.group(1)),
        text,
    )
    text = re.sub(r"\x00L(\d+)\x00", lambda m: stash[int(m.group(1))], text)
    return text


def render_body(body, linkmap, sec_idx, lang="en"):
    """Render a section body (paragraphs, inline images, subheadings)."""
    out = []
    for block in re.split(r"\n\s*\n", body.strip()):
        block = block.strip()
        if not block:
            continue
        if block.startswith("## "):
            out.append("<h3>%s</h3>" % render_inline(block[3:], linkmap, sec_idx, lang))
            continue
        figures = []

        def take_image(m):
            url = m.group(1)
            sid = SUBSTACK_ID_RE.search(url)
            src = data_uri_for(sid.group(1)) if sid else None
            if src:
                IMGS[sid.group(1)] = src
                figures.append('<figure><img data-img="%s" alt=""></figure>' % sid.group(1))
            return ""

        block = IMG_RE.sub(take_image, block)
        block = block.strip()
        if block:
            out.append("<p>%s</p>" % render_inline(block, linkmap, sec_idx, lang))
        out.extend(figures)
    return "\n".join(out)


def render_explanation(md):
    """Render explanation.md: headings, bullet lists, paragraphs, emphasis."""
    out = []
    lines = md.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if line.startswith("# "):
            out.append('<h3 class="exp-title">%s</h3>' % emphasize(html.escape(line[2:].strip())))
        elif line.startswith("## "):
            out.append("<h4>%s</h4>" % emphasize(html.escape(line[3:].strip())))
        elif line.lstrip().startswith("- "):
            items = []
            while i < len(lines) and lines[i].lstrip().startswith("- "):
                items.append("<li>%s</li>" % emphasize(html.escape(lines[i].lstrip()[2:].strip())))
                i += 1
            out.append("<ul>%s</ul>" % "".join(items))
            continue
        else:
            out.append("<p>%s</p>" % emphasize(html.escape(line.strip())))
        i += 1
    return "\n".join(out)


def render_card(summary_md, url):
    """Render a link summary.md into card HTML shown on hover."""
    parts = []
    for raw in summary_md.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        if line.startswith("# "):
            head = line[2:].strip()
            bits = re.split(r"\s+[—–-]\s+", head, maxsplit=1)
            anchor = html.escape(bits[0])
            sub = emphasize(html.escape(bits[1])) if len(bits) > 1 else ""
            parts.append('<div class="card-head"><span class="card-anchor">%s</span>'
                         '<span class="card-sub">%s</span></div>' % (anchor, sub))
        elif line.startswith("## "):
            parts.append("<h5>%s</h5>" % emphasize(html.escape(line[3:].strip())))
        elif line.startswith(">"):
            parts.append('<p class="card-note">%s</p>'
                         % emphasize(html.escape(line.lstrip("> ").strip())))
        elif line.startswith("URL:"):
            continue
        else:
            parts.append("<p>%s</p>" % emphasize(html.escape(line.strip())))
    href = html.escape(url, quote=True)
    parts.append('<a class="card-src" href="%s" target="_blank" rel="noopener">Forrás megnyitása ↗</a>' % href)
    return "".join(parts)


def build_linkmap(section_dir):
    links = json.loads(read(os.path.join(section_dir, "links.json")))
    linkmap = {}
    for link in links:
        matches = glob.glob(os.path.join(section_dir, "links", "%s-*" % link["id"], "summary.md"))
        card = render_card(read(matches[0]), link["url"]) if matches else ""
        linkmap[link["url"].strip()] = {"id": link["id"], "card_html": card}
    return linkmap


def parse_section(section_dir, fname="section.md"):
    md = read(os.path.join(section_dir, fname))
    body, footnotes = md, ""
    m = re.search(r"^##\s*Lábjegyzetek.*$", md, re.MULTILINE)
    if m:
        body, footnotes = md[: m.start()], md[m.end():]
    first_nl = body.index("\n") if "\n" in body else len(body)
    title_line = body[:first_nl].strip()
    title = title_line.lstrip("#").strip().strip("*").strip()
    body = body[first_nl:]
    return title, body, footnotes


def parse_footnotes(text):
    notes = []
    for m in re.finditer(r"^\[(\d+)\]:\s*(.+?)(?=\n\[\d+\]:|\Z)", text.strip(), re.S | re.M):
        notes.append((m.group(1), " ".join(m.group(2).split())))
    return notes


FN_TITLES = {"en": "Footnotes (from the original article)",
             "hu": "Lábjegyzetek (az eredeti cikkből)"}


def render_variant(sdir, fname, linkmap, si, lang):
    """Render one language variant of a section -> (title, article inner HTML)."""
    title, body, fn_text = parse_section(sdir, fname)
    body_html = render_body(body, linkmap, si, lang)

    fn_html = ""
    notes = parse_footnotes(fn_text)
    if notes:
        items = []
        for num, txt in notes:
            items.append('<li id="fn-%s-%d-%s"><span class="fn-num">%s</span> %s</li>'
                         % (lang, si, num, num, render_inline(txt, linkmap, si, lang)))
        fn_html = ('<div class="footnotes"><h4>%s</h4>'
                   '<ol class="fn-list">%s</ol></div>' % (FN_TITLES[lang], "".join(items)))

    return title, "<h2>%s</h2>%s%s" % (html.escape(title), body_html, fn_html)


def main():
    section_dirs = sorted(
        d for d in glob.glob(os.path.join(SECTIONS_DIR, "*")) if os.path.isdir(d)
    )
    toc = []
    sections_html = []
    for si, sdir in enumerate(section_dirs):
        linkmap = build_linkmap(sdir)
        anchor_id = "sec-%d" % si

        title, en_html = render_variant(sdir, "section.md", linkmap, si, "en")
        toc.append('<li><a href="#%s">%s</a></li>' % (anchor_id, html.escape(title)))

        toggle = ""
        articles = '<article class="orig lang-en">%s</article>' % en_html
        if os.path.exists(os.path.join(sdir, "section.hu.md")):
            _, hu_html = render_variant(sdir, "section.hu.md", linkmap, si, "hu")
            toggle = (
                '<div class="lang-toggle" role="group" aria-label="Nyelv">'
                '<button class="lang-btn active" data-lang="en">EN</button>'
                '<button class="lang-btn" data-lang="hu">HU</button></div>'
            )
            articles += '<article class="orig lang-hu" hidden>%s</article>' % hu_html

        exp_html = render_explanation(read(os.path.join(sdir, "explanation.md")))
        sections_html.append(
            '<section id="%s" class="sec">'
            '<div class="sec-head"><div class="sec-num">%02d</div>%s</div>'
            '%s'
            '<aside class="exp"><div class="exp-tag">Magyarázat</div>%s</aside>'
            "</section>"
            % (anchor_id, si, toggle, articles, exp_html)
        )

    cards_json = json.dumps(CARDS, ensure_ascii=False).replace("</", "<\\/")
    imgs_json = json.dumps(IMGS, ensure_ascii=False).replace("</", "<\\/")
    page = PAGE_TEMPLATE.format(
        toc="\n".join(toc),
        sections="\n".join(sections_html),
        cards=cards_json,
        imgs=imgs_json,
    )
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(page)
    print("Wrote %s (%d sections, %d link cards, %d images)"
          % (OUT, len(section_dirs), len(CARDS), len(IMGS)))


PAGE_TEMPLATE = r"""<!doctype html>
<html lang="hu">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Time to Take AI Consciousness Seriously — kétnyelvű magyarázat</title>
<style>
:root{{
  --bg:#faf9f6; --fg:#1c1b19; --muted:#6b6862; --rule:#e5e2db;
  --exp-bg:#f0f4f8; --exp-fg:#17242e; --exp-tag:#2a6f97; --exp-rule:#cfe0ea;
  --link:#8a5a00; --card-bg:#ffffff; --card-rule:#e0ddd5; --note:#9a3b2f;
  --accent:#2a6f97;
}}
@media (prefers-color-scheme:dark){{
  :root{{
    --bg:#171614; --fg:#e9e6df; --muted:#9c988e; --rule:#302e2a;
    --exp-bg:#141d24; --exp-fg:#dbe7ef; --exp-tag:#6fb2d6; --exp-rule:#26333d;
    --link:#e0a24a; --card-bg:#1e1d1a; --card-rule:#343128; --note:#e0836f;
    --accent:#6fb2d6;
  }}
}}
:root[data-theme="dark"]{{
  --bg:#171614; --fg:#e9e6df; --muted:#9c988e; --rule:#302e2a;
  --exp-bg:#141d24; --exp-fg:#dbe7ef; --exp-tag:#6fb2d6; --exp-rule:#26333d;
  --link:#e0a24a; --card-bg:#1e1d1a; --card-rule:#343128; --note:#e0836f;
  --accent:#6fb2d6;
}}
:root[data-theme="light"]{{
  --bg:#faf9f6; --fg:#1c1b19; --muted:#6b6862; --rule:#e5e2db;
  --exp-bg:#f0f4f8; --exp-fg:#17242e; --exp-tag:#2a6f97; --exp-rule:#cfe0ea;
  --link:#8a5a00; --card-bg:#ffffff; --card-rule:#e0ddd5; --note:#9a3b2f;
  --accent:#2a6f97;
}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--fg);
  font-family:Georgia,"Iowan Old Style",Cambria,"Times New Roman",serif;
  line-height:1.62;font-size:19px;-webkit-font-smoothing:antialiased}}
header.top{{max-width:820px;margin:0 auto;padding:56px 24px 8px}}
header.top h1{{font-size:30px;line-height:1.25;margin:0 0 10px}}
header.top p.lede{{color:var(--muted);font-size:17px;margin:0}}
header.top p.byline{{color:var(--muted);font-size:15px;margin:14px 0 0}}
nav.toc{{max-width:820px;margin:24px auto 0;padding:16px 24px;border-top:1px solid var(--rule);border-bottom:1px solid var(--rule)}}
nav.toc ol{{margin:0;padding-left:1.2em;columns:2;column-gap:32px;font-size:15px}}
nav.toc a{{color:var(--accent);text-decoration:none}}
nav.toc a:hover{{text-decoration:underline}}
main{{max-width:820px;margin:0 auto;padding:8px 24px 80px}}
.sec{{padding:40px 0;border-bottom:1px solid var(--rule);position:relative}}
.sec-head{{display:flex;align-items:center;justify-content:space-between;margin-bottom:6px}}
.sec-num{{font-family:ui-monospace,Menlo,monospace;font-size:13px;letter-spacing:.12em;color:var(--muted)}}
.lang-toggle{{display:inline-flex;border:1px solid var(--rule);border-radius:16px;overflow:hidden}}
.lang-btn{{border:0;background:transparent;color:var(--muted);padding:3px 12px;font-size:12px;
  font-weight:600;letter-spacing:.06em;cursor:pointer;
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}}
.lang-btn.active{{background:var(--accent);color:var(--bg)}}
.orig h2{{font-size:25px;line-height:1.25;margin:0 0 18px}}
.orig p{{margin:0 0 18px}}
.orig h3{{font-size:19px;margin:26px 0 12px}}
figure{{margin:22px 0;text-align:center}}
figure img{{max-width:100%;height:auto;border:1px solid var(--rule);border-radius:6px}}
a.src,a.ext{{color:var(--link);text-decoration:none;border-bottom:1px solid color-mix(in srgb,var(--link) 45%,transparent)}}
a.src{{border-bottom-style:dotted;border-bottom-width:2px;cursor:help}}
a.src:hover,a.ext:hover{{border-bottom-color:var(--link)}}
sup.fn a{{color:var(--accent);text-decoration:none;font-size:.7em;padding:0 1px}}
.footnotes{{margin-top:30px;padding-top:14px;border-top:1px dashed var(--rule);font-size:15px;color:var(--muted)}}
.footnotes h4{{font-size:14px;text-transform:uppercase;letter-spacing:.08em;margin:0 0 10px}}
.fn-list{{margin:0;padding-left:0;list-style:none}}
.fn-list li{{margin:0 0 10px;padding-left:26px;position:relative;line-height:1.5}}
.fn-num{{position:absolute;left:0;font-family:ui-monospace,Menlo,monospace;color:var(--accent)}}
aside.exp{{margin-top:28px;background:var(--exp-bg);color:var(--exp-fg);
  border:1px solid var(--exp-rule);border-left:4px solid var(--exp-tag);
  border-radius:8px;padding:20px 24px 22px;
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  font-size:16.5px;line-height:1.6}}
.exp-tag{{display:inline-block;font-size:12px;font-weight:700;text-transform:uppercase;
  letter-spacing:.1em;color:var(--exp-tag);margin-bottom:10px}}
aside.exp .exp-title{{font-size:18px;margin:0 0 12px;line-height:1.3}}
aside.exp h4{{font-size:16px;margin:18px 0 8px}}
aside.exp p{{margin:0 0 12px}}
aside.exp ul{{margin:0 0 12px;padding-left:1.2em}}
aside.exp li{{margin:0 0 6px}}
/* hover card */
#tip{{position:absolute;z-index:50;max-width:420px;width:max-content;
  background:var(--card-bg);color:var(--fg);border:1px solid var(--card-rule);
  border-radius:10px;box-shadow:0 10px 34px rgba(0,0,0,.22);
  padding:16px 18px;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  font-size:14.5px;line-height:1.5;opacity:0;visibility:hidden;transition:opacity .12s;
  max-height:70vh;overflow:auto}}
#tip.show{{opacity:1;visibility:visible}}
#tip .card-head{{margin-bottom:8px}}
#tip .card-anchor{{display:block;font-weight:700;font-size:15.5px}}
#tip .card-sub{{display:block;color:var(--muted);font-size:13.5px;margin-top:2px}}
#tip h5{{margin:12px 0 3px;font-size:13px;text-transform:uppercase;letter-spacing:.05em;color:var(--accent)}}
#tip p{{margin:0 0 8px}}
#tip .card-note{{color:var(--note);font-style:italic}}
#tip .card-src{{display:inline-block;margin-top:6px;color:var(--accent);text-decoration:none;font-size:13.5px}}
.themebtn{{position:fixed;top:14px;right:14px;z-index:60;border:1px solid var(--rule);
  background:var(--card-bg);color:var(--fg);border-radius:20px;padding:6px 12px;font-size:13px;cursor:pointer;
  font-family:-apple-system,system-ui,sans-serif}}
</style>
</head>
<body>
<button class="themebtn" id="themebtn" title="Világos/sötét">◐ téma</button>
<header class="top">
  <h1>Time to Take AI Consciousness Seriously</h1>
  <p class="lede">Az esszé (Second Best / Samuel Hammond) szakaszonként: eredeti angol szöveg (az EN/HU kapcsolóval szakaszonként magyar fordításra váltható), alatta magyar magyarázat. A forráshivatkozások fölé húzva a linkhez tartozó teljes magyar összefoglaló jelenik meg.</p>
  <p class="byline">Eredeti: <a class="ext" href="https://www.secondbest.ca/p/time-to-take-ai-consciousness-seriously" target="_blank" rel="noopener">secondbest.ca</a></p>
</header>
<nav class="toc"><ol>{toc}</ol></nav>
<main>
{sections}
</main>
<div id="tip"></div>
<script>
const CARDS = {cards};
const IMGS = {imgs};
(function(){{
  document.querySelectorAll('img[data-img]').forEach(function(img){{
    const src = IMGS[img.getAttribute('data-img')];
    if (src) img.src = src;
  }});
  document.querySelectorAll('.sec').forEach(function(sec){{
    const btns = sec.querySelectorAll('.lang-btn');
    if (!btns.length) return;
    btns.forEach(function(btn){{
      btn.addEventListener('click', function(){{
        const lang = btn.getAttribute('data-lang');
        btns.forEach(function(b){{ b.classList.toggle('active', b === btn); }});
        sec.querySelectorAll('article.orig').forEach(function(art){{
          art.hidden = !art.classList.contains('lang-' + lang);
        }});
      }});
    }});
  }});
  const tip = document.getElementById('tip');
  let hideTimer = null, overTip = false, curr = null;
  function place(el){{
    const r = el.getBoundingClientRect();
    const sx = window.scrollX, sy = window.scrollY;
    tip.style.left = '0px'; tip.style.top = '0px';
    tip.classList.add('show');
    const tw = tip.offsetWidth, th = tip.offsetHeight;
    let left = sx + r.left;
    left = Math.min(left, sx + document.documentElement.clientWidth - tw - 12);
    left = Math.max(left, sx + 8);
    let top = sy + r.bottom + 8;
    if (r.bottom + th + 16 > window.innerHeight && r.top - th - 8 > 0){{
      top = sy + r.top - th - 8;
    }}
    tip.style.left = left + 'px';
    tip.style.top = top + 'px';
  }}
  function show(el){{
    const id = el.getAttribute('data-card');
    if (!CARDS[id]) return;
    clearTimeout(hideTimer);
    if (curr !== el){{ tip.innerHTML = CARDS[id]; curr = el; }}
    place(el);
  }}
  function scheduleHide(){{
    clearTimeout(hideTimer);
    hideTimer = setTimeout(function(){{
      if (!overTip){{ tip.classList.remove('show'); curr = null; }}
    }}, 180);
  }}
  document.querySelectorAll('a.src[data-card]').forEach(function(el){{
    el.addEventListener('mouseenter', function(){{ show(el); }});
    el.addEventListener('mouseleave', scheduleHide);
    el.addEventListener('focus', function(){{ show(el); }});
    el.addEventListener('blur', scheduleHide);
  }});
  tip.addEventListener('mouseenter', function(){{ overTip = true; clearTimeout(hideTimer); }});
  tip.addEventListener('mouseleave', function(){{ overTip = false; scheduleHide(); }});
  // theme toggle
  const btn = document.getElementById('themebtn');
  btn.addEventListener('click', function(){{
    const root = document.documentElement;
    const cur = root.getAttribute('data-theme');
    const next = cur === 'dark' ? 'light' : (cur === 'light' ? 'dark'
      : (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'light' : 'dark'));
    root.setAttribute('data-theme', next);
  }});
}})();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()

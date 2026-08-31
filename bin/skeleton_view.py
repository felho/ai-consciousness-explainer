#!/usr/bin/env python3
"""Turn skeleton/skeleton.yaml into the "erwaz" (argument-skeleton) reading aid.

Everything derivable is derived here, in Python, at build time. The browser
gets pre-ordered rows, pre-computed chunk adjacency and a small JSON blob; the
page JS only moves things around and highlights text. Nothing about the
skeleton is recomputed in the browser.

Vocabulary
  chunk    a unit of the argument map. Usually one physical section, but
           section 06 is mapped as two virtual chunks, "06a" and "06b".
  node     a claim in the map. level 0 = thesis, 1 = a chunk's key claim,
           2 = a supporting claim inside a chunk.
  local    an edge whose two endpoints sit in the same chunk (and neither is
           the thesis). Local edges form a rooted in-tree at the key claim.
  cross    everything else; surfaced as chunk chips, never as tree rows.

Reader-facing strings are Hungarian on purpose (the page chrome is Hungarian);
node labels stay in the mapper's English.
"""

import html
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_REPO, "skeleton"))

from yamlsubset import ParseError, load  # noqa: E402

SKELETON_PATH = os.path.join(_REPO, "skeleton", "skeleton.yaml")

# The Toulmin "warrant on the arrow" view - drawing an interpolated warrant as
# a label on the edge it licenses instead of as a row of its own - was
# considered and deliberately not implemented: it needs a second visual grammar
# for four nodes out of seventy-nine. The eligibility predicate is kept so the
# decision can be revisited without re-deriving it.
WARRANT_ON_ARROW = False

# Local edge types, in the order the row encoding treats them. `presupposes`
# is absent on purpose: every presupposes edge in the map is cross-chunk.
ROW_GLYPHS = {"supports": "", "elaborates": "+", "qualifies": "±", "rebuts": "✕"}

# One sentence per argumentation scheme, shown in the hover card.
SCHEME_LABELS = {
    "analogy": "analógia",
    "authority": "tekintély",
    "precaution": "elővigyázatosság",
}
SCHEME_GLOSSES = {
    "analogy": "Analógia: a lépés két dolog hasonlóságán nyugszik, és pontosan "
               "annyit bír el, amennyire a hasonlóság a lényeges pontokon fennáll.",
    "authority": "Tekintély: az állítás súlyát egy szakértő vagy forrás állásfoglalása "
                 "adja, nem a helyben bemutatott bizonyíték.",
    "precaution": "Elővigyázatosság: nem logikai következtetés — abból, hogy a dolog elég "
                  "valószínű és a tét nagy, jut oda, hogy már most tenni kell valamit.",
}

MAX_CHUNK_CHIPS = 3

_TAG_RE = re.compile(r"<[^>]*>")
_WS_RE = re.compile(r"\s+")


class SkeletonError(Exception):
    """The skeleton could not be loaded or does not have the expected shape."""


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------

def _tidy(text):
    return _WS_RE.sub(" ", (text or "").strip())


def shorten(text, limit=118):
    """Trim to a word boundary. Used for every 'compact restatement'."""
    text = _tidy(text)
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut.rstrip(" ,;:.—-") + "…"


def text_nodes(fragment):
    """The text nodes a browser would build from this HTML fragment.

    Splitting on tags is exact here because the builder emits no comments and
    no CDATA, so every gap between two tags is one text node.
    """
    return [html.unescape(part) for part in _TAG_RE.split(fragment)]


def _esc(text):
    return html.escape(_tidy(text))


def phys_section(chunk):
    """Physical section id of a chunk: "06a" -> "06"."""
    return chunk[:2]


# --------------------------------------------------------------------------
# view model
# --------------------------------------------------------------------------

class SkeletonView(object):
    def __init__(self, doc, section_index):
        """section_index: physical section id -> index of the rendered section."""
        self.section_index = section_index
        text = doc.get("text") or {}
        self.chunks = list(text.get("sections") or [])
        nodes = doc.get("nodes") or []
        edges = doc.get("edges") or []
        if not self.chunks or not nodes or not edges:
            raise SkeletonError("skeleton.yaml has no text.sections / nodes / edges")

        self.by_id = {}
        self.order = {}  # node id -> position in the file, used for row order
        for pos, node in enumerate(nodes):
            nid = node.get("id")
            if not nid:
                raise SkeletonError("a node has no id")
            self.by_id[nid] = node
            self.order[nid] = pos
        self.edges = edges

        level0 = [n for n in nodes if n.get("level") == 0]
        if len(level0) != 1:
            raise SkeletonError("expected exactly one level-0 thesis node")
        self.thesis = level0[0]

        self.key_of = {}
        for node in nodes:
            if node.get("level") == 1:
                self.key_of[node.get("section")] = node
        missing = [c for c in self.chunks if c not in self.key_of]
        if missing:
            raise SkeletonError("chunks without a key claim: %s" % ", ".join(missing))

        for chunk in self.chunks:
            if phys_section(chunk) not in section_index:
                raise SkeletonError("chunk %r has no rendered section %r"
                                    % (chunk, phys_section(chunk)))

        self._derive()

    # ---- derivations ---------------------------------------------------

    def _chunk_of(self, nid):
        return self.by_id[nid].get("section")

    def _derive(self):
        thesis_id = self.thesis["id"]
        rank = {c: i for i, c in enumerate(self.chunks)}

        local_out = {}   # node -> [(target, type, scheme)] within its own chunk
        cross = []       # (src, dst, type, scheme)
        for edge in self.edges:
            src, dst = edge.get("from"), edge.get("to")
            etype, scheme = edge.get("type"), edge.get("scheme")
            if src not in self.by_id or dst not in self.by_id:
                raise SkeletonError("edge references an unknown node: %s -> %s" % (src, dst))
            if dst == thesis_id or src == thesis_id:
                continue  # the is->ought step lives on the thesis card
            if self._chunk_of(src) == self._chunk_of(dst):
                local_out.setdefault(src, []).append((dst, etype, scheme))
            else:
                cross.append((src, dst, etype, scheme))
        self.cross_edges = cross

        # Chunk dependency: X depends on Y when X presupposes something in Y,
        # or when Y's material supports a claim of X. Supports into the
        # descriptive backbone (s00-key) are excluded - every chunk feeds it,
        # so listing it would say nothing.
        backbone = self.key_of[self.chunks[0]]["id"]
        depends = {c: [] for c in self.chunks}
        for src, dst, etype, _scheme in cross:
            csrc, cdst = self._chunk_of(src), self._chunk_of(dst)
            if etype == "presupposes":
                dep, base = csrc, cdst
            elif etype == "supports" and dst != backbone:
                dep, base = cdst, csrc
            else:
                continue
            if rank[base] < rank[dep] and base not in depends[dep]:
                depends[dep].append(base)

        used_by = {c: [] for c in self.chunks}
        for dep, bases in depends.items():
            for base in bases:
                used_by[base].append(dep)
        # nearest first in both directions
        self.builds_on = {c: sorted(v, key=lambda x: -rank[x]) for c, v in depends.items()}
        self.used_by = {c: sorted(v, key=lambda x: rank[x]) for c, v in used_by.items()}

        # Local in-trees, one per chunk.
        self.rows = {}
        self.d1 = {}
        self.also_nodes = {}
        for chunk in self.chunks:
            key = self.key_of[chunk]["id"]
            members = [n["id"] for n in self.by_id.values()
                       if n.get("section") == chunk and n.get("level") == 2]
            self.d1[chunk] = len(members)

            children = {}  # parent -> [child ids]
            for nid in members:
                for dst, _t, _s in local_out.get(nid, []):
                    children.setdefault(dst, []).append(nid)

            # Distance to the key over local edges; the primary parent of a
            # node is the parent that sits closest to the key, so the extra
            # edge of an out-degree-2 node becomes an "also" chip.
            dist = {key: 0}
            frontier = [key]
            while frontier:
                nxt = []
                for parent in frontier:
                    for child in children.get(parent, []):
                        if child not in dist:
                            dist[child] = dist[parent] + 1
                            nxt.append(child)
                frontier = nxt

            primary = {}
            extras = {}
            for nid in members:
                outs = local_out.get(nid, [])
                if not outs:
                    continue
                ranked = sorted(outs, key=lambda e: dist.get(e[0], 99))
                primary[nid] = ranked[0]
                if len(ranked) > 1:
                    extras[nid] = ranked[1:]
                    for dst, _t, _s in ranked[1:]:
                        self.also_nodes[dst] = self.by_id[dst]

            tree = {}
            for nid, (dst, etype, scheme) in primary.items():
                tree.setdefault(dst, []).append((nid, etype, scheme))
            for kids in tree.values():
                kids.sort(key=lambda k: self.order[k[0]])

            rows = []

            def walk(nid, etype, scheme, depth):
                rows.append({
                    "id": nid, "depth": depth, "etype": etype, "scheme": scheme,
                    "extras": extras.get(nid, []),
                })
                for child, ctype, cscheme in tree.get(nid, []):
                    walk(child, ctype, cscheme, depth + 1)

            walk(key, None, None, 0)
            orphans = [n for n in members if n not in {r["id"] for r in rows}]
            if orphans:
                raise SkeletonError("chunk %s: nodes outside the local tree: %s"
                                    % (chunk, ", ".join(sorted(orphans))))
            self.rows[chunk] = rows

        # The one edge into the thesis carries the is->ought step.
        self.thesis_edge = None
        for edge in self.edges:
            if edge.get("to") == thesis_id:
                self.thesis_edge = edge
                break
        self.backbone_id = backbone

        # Anchors, flattened for the build-time verifier.
        self.anchor_index = {}
        for node in self.by_id.values():
            entries = []
            for anchor in node.get("anchors") or []:
                sec = anchor.get("section")
                if sec not in self.section_index:
                    raise SkeletonError("%s: anchor names unknown section %r"
                                        % (node["id"], sec))
                entries.append({
                    "sec": self.section_index[sec],
                    "q": anchor.get("quote") or "",
                    "fn": anchor.get("footnote"),
                    "ok": True,
                })
            if entries:
                self.anchor_index[node["id"]] = entries

    # ---- warrant-on-arrow eligibility (kept, not used) ------------------

    def warrant_on_arrow_eligible(self, node):
        """True when a node could be drawn as a label on the edge it licenses.

        Requires an interpolated warrant with exactly one outgoing local edge
        and at least one incoming one, so the arrow it would ride is unique.
        """
        if not WARRANT_ON_ARROW:
            return False
        if node.get("interpolated") is not True or node.get("kind") != "warrant":
            return False
        outs = [e for e in self.edges if e.get("from") == node["id"]]
        ins = [e for e in self.edges if e.get("to") == node["id"]]
        return len(outs) == 1 and len(ins) >= 1

    # ---- anchor verification -------------------------------------------

    def verify_anchors(self, article_html_by_index):
        """Check every anchor quote against the rendered EN articles.

        Mirrors what the page JS does at run time: the quote must occur in
        exactly one text node, exactly once. Anything else is reported and the
        row's quote affordance is disabled rather than left to fail silently.
        """
        nodes_cache = {}
        total = 0
        failures = []
        for nid, entries in sorted(self.anchor_index.items()):
            for pos, entry in enumerate(entries, 1):
                total += 1
                si = entry["sec"]
                if si not in nodes_cache:
                    nodes_cache[si] = text_nodes(article_html_by_index.get(si, ""))
                hits = sum(chunk.count(entry["q"]) for chunk in nodes_cache[si])
                if hits != 1:
                    entry["ok"] = False
                    failures.append("%s anchor #%d in section %02d: %d match(es) - %s"
                                    % (nid, pos, si, hits, shorten(entry["q"], 70)))
        return total, failures

    # ---- rendering ------------------------------------------------------

    def _chunk_chips(self, chunk_ids, role):
        """Inner HTML of a chunk-chip run; the caller owns the .skel-chips row."""
        if not chunk_ids:
            return ""
        shown, rest = chunk_ids[:MAX_CHUNK_CHIPS], chunk_ids[MAX_CHUNK_CHIPS:]
        chips = ['<span class="skel-role">%s</span>' % _esc(role)]
        for cid in shown:
            chips.append('<button type="button" class="skel-chip skel-chunk" '
                         'data-skel-peek="%s">%s</button>' % (_esc(cid), _esc(cid)))
        if rest:
            chips.append('<span class="skel-chip skel-more">+%d</span>' % len(rest))
        return "".join(chips)

    def _chips_row(self, inner):
        return ('<div class="skel-chips">%s</div>' % inner) if inner else ""

    def _gloss_chip(self, scheme):
        if scheme not in SCHEME_LABELS:
            return ""
        return ('<button type="button" class="skel-chip skel-gloss" '
                'data-skel-gloss="%s">%s</button>'
                % (_esc(scheme), _esc(SCHEME_LABELS[scheme])))

    def thesis_html(self):
        backbone = self.by_id[self.backbone_id]
        scheme = (self.thesis_edge or {}).get("scheme")
        return (
            '<div class="skel-thesis" data-skel-block hidden>'
            '<div class="skel-tag">A teljes érv</div>'
            '<p class="skel-thesis-claim">%s</p>'
            '<p class="skel-thesis-line">'
            '<span class="skel-thesis-step">%s</span>'
            '<span class="skel-arrow">→</span>%s<span class="skel-arrow">→</span>'
            '<span class="skel-thesis-step">%s</span></p>'
            '<p class="skel-thesis-note">A leíró gerinctől egyetlen lépés vezet a '
            'normatív tézisig — és ez a lépés nem bizonyítás.</p>'
            '</div>'
            % (_esc(self.thesis["label"]),
               _esc(shorten(backbone["label"], 96)),
               self._gloss_chip(scheme),
               _esc(shorten(self.thesis["label"], 76)))
        )

    def legend_html(self):
        interp = sum(1 for n in self.by_id.values() if n.get("interpolated") is True)
        return (
            '<div class="skel-legend" id="skel-legend" data-skel-block hidden>'
            '<button type="button" class="skel-legend-x" id="skel-legend-x" '
            'aria-label="Bezárás" title="Bezárás">×</button>'
            '<ul>'
            '<li>Minden szakasz előtt egy doboz mondja meg, mi az adott '
            'gondolategység kulcsállítása és mire épül; a szakasz után '
            'lenyitható, miből áll.</li>'
            '<li><span class="skel-legend-interp">Szaggatott, dőlt sor</span> = a '
            'térkép %d állításából %d-et a feltérképezés adott hozzá — a '
            'szöveg ezeket nem mondja ki.</li>'
            '<li>A címkék egyelőre angolul vannak, mint az eredeti szöveg.</li>'
            '<li><span class="skel-legend-q">❝</span> = ugrás a pontos mondatra '
            'az angol szövegben.</li>'
            '</ul></div>'
            % (len(self.by_id), interp)
        )

    def close_html(self):
        return (
            '<div class="skel-close" data-skel-block hidden>'
            '<div class="skel-tag">Ide tartott az érvelés</div>'
            '<p>%s</p></div>' % _esc(self.thesis["label"])
        )

    def pre_html(self, phys):
        """The advance organizer that precedes one physical section."""
        chunks = [c for c in self.chunks if phys_section(c) == phys]
        if not chunks:
            return ""
        head = "%s / %d" % (phys, len(self.chunks))
        if len(chunks) > 1:
            head += " · %d gondolategység" % len(chunks)
        blocks = []
        for chunk in chunks:
            key = self.key_of[chunk]
            scheme = None
            for src, dst, etype, sch in self.cross_edges:
                if src == key["id"] and dst == self.backbone_id and sch:
                    scheme = sch
            chips = [self._chips_row(
                self._chunk_chips(self.builds_on[chunk], "épül erre:")
                + self._gloss_chip(scheme))]
            blocks.append(
                '<div class="skel-keyblock" data-skel-chunk="%s">'
                '<button type="button" class="skel-dot" data-skel-goto="%s" '
                'aria-label="Ugrás: %s gondolategység"></button>'
                '%s<p class="skel-key">%s</p>%s</div>'
                % (_esc(chunk), _esc(chunk), _esc(chunk),
                   ('<div class="skel-sub">%s</div>' % _esc(chunk)) if len(chunks) > 1 else "",
                   _esc(key["label"]), "".join(chips))
            )
        return (
            '<div class="skel-pre" id="skel-pre-%s" data-skel-block data-skel-box="%s" hidden>'
            '<div class="skel-pre-inner"><div class="skel-pre-head">%s</div>%s</div></div>'
            % (_esc(phys), _esc(" ".join(chunks)), _esc(head), "".join(blocks))
        )

    def _row_html(self, chunk, row):
        node = self.by_id[row["id"]]
        classes = ["skel-row"]
        if row["etype"]:
            classes.append("skel-e-" + row["etype"])
        if node.get("interpolated") is True:
            classes.append("skel-interp")
        anchors = self.anchor_index.get(row["id"], [])
        fn_numbers = sorted({a["fn"] for a in anchors if a["fn"] is not None})
        # D3: every anchor of the node sits below the line.
        footnote_only = bool(anchors) and all(a["fn"] is not None for a in anchors)

        bits = []
        glyph = ROW_GLYPHS.get(row["etype"] or "", "")
        if glyph:
            bits.append('<span class="skel-glyph" aria-hidden="true">%s</span>' % glyph)
        bits.append('<span class="skel-label">%s</span>' % _esc(node["label"]))

        if anchors:
            usable = [a for a in anchors if a["ok"]]
            count = ('<span class="skel-qn">%d</span>' % len(anchors)) if len(anchors) > 1 else ""
            disabled = "" if usable else " disabled"
            title = "Ugrás a mondatra" if usable else "A mondat nem található a szövegben"
            bits.append('<button type="button" class="skel-quote" data-skel-quote="%s" '
                        'title="%s" aria-label="%s"%s>❝%s</button>'
                        % (_esc(row["id"]), _esc(title), _esc(title), disabled, count))
        if footnote_only:
            bits.append('<span class="skel-chip skel-fn">lábjegyzet [%s]</span>'
                        % _esc(", ".join(str(n) for n in fn_numbers)))
        if node.get("interpolated") is True:
            bits.append('<span class="skel-chip skel-add">kiegészítés — a szöveg '
                        'ezt nem mondja ki</span>')
        gloss = self._gloss_chip(row["scheme"])
        if gloss:
            bits.append(gloss)
        for dst, _etype, _scheme in row["extras"]:
            target = self.by_id[dst]
            tchunk = target.get("section")
            label = tchunk if tchunk != chunk else shorten(target["label"], 46)
            bits.append('<button type="button" class="skel-chip skel-also" '
                        'data-skel-peek-node="%s">↗ továbbá: %s</button>'
                        % (_esc(dst), _esc(label)))

        kids = "".join(bits)
        return '<li class="%s">%s' % (" ".join(classes), kids)

    def _tree_html(self, chunk):
        """Nested <ul>/<li> from the pre-ordered rows; nesting reads '...because'."""
        rows = self.rows[chunk]
        out = []
        prev = -1
        for row in rows:
            depth = row["depth"]
            if depth > prev:
                out.append('<ul class="skel-tree-list">')
            else:
                out.append("</li>")
                while prev > depth:
                    out.append("</ul></li>")
                    prev -= 1
            out.append(self._row_html(chunk, row))
            prev = depth
        out.append("</li>")
        while prev > 0:
            out.append("</ul></li>")
            prev -= 1
        out.append("</ul>")
        return "".join(out)

    def post_html(self, phys):
        """The end-of-section consolidation strips, one per chunk."""
        chunks = [c for c in self.chunks if phys_section(c) == phys]
        strips = []
        for chunk in chunks:
            key = self.key_of[chunk]
            used = self._chips_row(
                self._chunk_chips(self.used_by[chunk], "ezt használja:"))
            strips.append(
                '<div class="skel-post" data-skel-block hidden>'
                '<div class="skel-post-inner">'
                '<p class="skel-restate"><span class="skel-post-num">%s</span>%s</p>'
                '<div class="skel-post-bar">'
                '<button type="button" class="skel-expand" aria-expanded="false" '
                'data-skel-expand="skel-tree-%s">Alállítások (%d)</button>%s</div>'
                '<div class="skel-tree" id="skel-tree-%s" hidden>%s</div>'
                '</div></div>'
                % (_esc(chunk), _esc(shorten(key["label"], 150)),
                   _esc(chunk), self.d1[chunk], used,
                   _esc(chunk), self._tree_html(chunk))
            )
        return "".join(strips)

    def json_blob(self):
        chunks = {}
        for chunk in self.chunks:
            chunks[chunk] = {
                "sec": self.section_index[phys_section(chunk)],
                "box": "skel-pre-%s" % phys_section(chunk),
                "label": _tidy(self.key_of[chunk]["label"]),
            }
        nodes = {nid: {"label": _tidy(n["label"]), "chunk": n.get("section")}
                 for nid, n in self.also_nodes.items()}
        data = {
            "order": self.chunks,
            "chunks": chunks,
            "nodes": nodes,
            "anchors": self.anchor_index,
            "glosses": SCHEME_GLOSSES,
            "up": self.builds_on,
            "down": self.used_by,
        }
        return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


def load_view(section_index, path=SKELETON_PATH):
    try:
        doc = load(path)
    except (ParseError, OSError) as exc:
        raise SkeletonError("%s: %s" % (os.path.relpath(path, _REPO), exc))
    return SkeletonView(doc, section_index)


# --------------------------------------------------------------------------
# CSS / JS, passed to the page template as format arguments (single braces)
# --------------------------------------------------------------------------

SKEL_CSS = r"""
/* --- erwaz (argument skeleton) ------------------------------------------ */
/* Lengths only; every colour is an existing var or a color-mix over one. */
:root{
  --skel-linex:-32px;    /* spine offset from the text column's left edge */
  --skel-inset:20px;     /* .skel-pre-inner padding-left + border-left */
  --skel-dot:11px;
}
@media (max-width:1199px){ :root{ --skel-linex:-16px; --skel-dot:8px; } }
.skel-sans{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.skel-thesis,.skel-legend,.skel-pre,.skel-post,.skel-close{
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.skel-tag{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.11em;
  color:var(--muted);margin-bottom:8px}
/* thesis card */
.skel-thesis{max-width:820px;margin:22px auto 0;padding:18px 24px;
  border:1px solid var(--rule);border-radius:10px;
  background:color-mix(in srgb,var(--accent) 5%,var(--bg))}
.skel-thesis-claim{margin:0 0 12px;font-size:17px;line-height:1.45;font-weight:600}
.skel-thesis-line{margin:0;display:flex;flex-wrap:wrap;align-items:center;gap:8px;
  font-size:14px;color:var(--muted);line-height:1.4}
.skel-thesis-step{flex:1 1 220px;min-width:160px}
.skel-arrow{color:var(--accent);font-size:15px}
.skel-thesis-note{margin:10px 0 0;font-size:13px;color:var(--muted);font-style:italic}
/* legend */
.skel-legend{position:relative;max-width:820px;margin:12px auto 0;padding:14px 44px 14px 24px;
  border:1px dashed var(--rule);border-radius:10px;font-size:13.5px;color:var(--muted)}
.skel-legend ul{margin:0;padding-left:1.1em}
.skel-legend li{margin:0 0 5px;line-height:1.5}
.skel-legend-interp{font-style:italic;border-left:2px dashed var(--muted);padding-left:6px}
.skel-legend-q{color:var(--accent)}
.skel-legend-x{position:absolute;top:4px;right:4px;width:44px;height:44px;
  border:0;background:transparent;color:var(--muted);font-size:20px;line-height:1;cursor:pointer}
.skel-legend-x:hover{color:var(--fg)}
/* pre-section box */
.skel-pre{position:relative;margin:34px 0 0}
.skel-pre-inner{border-left:3px solid color-mix(in srgb,var(--accent) 55%,var(--rule));
  padding:14px 18px 14px 17px;background:color-mix(in srgb,var(--accent) 4%,var(--bg));
  border-radius:0 8px 8px 0}
.skel-pre-head{font-family:ui-monospace,Menlo,monospace;font-size:12px;letter-spacing:.1em;
  color:var(--muted);margin-bottom:8px}
.skel-keyblock{position:relative}
.skel-keyblock + .skel-keyblock{margin-top:14px;padding-top:14px;border-top:1px dotted var(--rule)}
.skel-sub{font-family:ui-monospace,Menlo,monospace;font-size:11px;color:var(--muted);margin-bottom:3px}
.skel-key{margin:0;font-size:16px;line-height:1.45;font-weight:600}
.skel-chips{display:flex;flex-wrap:wrap;align-items:center;gap:8px;row-gap:12px;margin-top:8px}
.skel-role{font-size:12px;color:var(--muted);letter-spacing:.02em}
.skel-chip{display:inline-flex;align-items:center;min-height:26px;padding:4px 10px;
  border:1px solid var(--rule);border-radius:13px;background:var(--card-bg);
  color:var(--muted);font-size:12px;line-height:1.2;font-family:inherit}
button.skel-chip{cursor:pointer;position:relative}
/* keep the visual pill small but the touch target >=44px */
button.skel-chip::after{content:'';position:absolute;left:0;right:0;top:50%;
  height:44px;transform:translateY(-50%)}
button.skel-chip:hover{color:var(--fg);border-color:color-mix(in srgb,var(--accent) 50%,var(--rule))}
.skel-chip.skel-more{opacity:.7}
.skel-chip.skel-chunk{font-family:ui-monospace,Menlo,monospace;letter-spacing:.04em;
  min-width:44px;justify-content:center}
.skel-chip.skel-add,.skel-chip.skel-fn{border-style:dashed}
/* spine */
.skel-dot{display:none}
:root.skel-on .skel-pre::before,:root.skel-on .skel-post::before,:root.skel-on .sec::before{
  content:'';position:absolute;left:var(--skel-linex);top:0;bottom:0;width:1px;
  background:color-mix(in srgb,var(--rule) 90%,var(--muted));pointer-events:none}
:root.skel-on .skel-dot{display:block;position:absolute;top:-8px;
  left:calc(var(--skel-linex) - var(--skel-inset) - 22px);
  width:44px;height:44px;border:0;background:transparent;cursor:pointer;padding:0}
.skel-dot::before{content:'';position:absolute;left:50%;top:50%;
  width:var(--skel-dot);height:var(--skel-dot);margin:calc(var(--skel-dot) / -2) 0 0 calc(var(--skel-dot) / -2);
  border-radius:50%;background:var(--bg);
  border:2px solid color-mix(in srgb,var(--accent) 70%,var(--rule))}
.skel-dot:hover::before{background:var(--accent)}
@media (max-width:899px){
  :root.skel-on .skel-pre::before,:root.skel-on .skel-post::before,
  :root.skel-on .sec::before,:root.skel-on .skel-dot{display:none;content:none}
}
/* end-of-section strip */
.skel-post{position:relative;margin:0 0 6px;padding-top:18px}
.skel-post-inner{border-top:1px solid var(--rule);padding-top:14px}
.skel-restate{margin:0 0 10px;font-size:14.5px;line-height:1.5;color:var(--muted)}
.skel-post-num{font-family:ui-monospace,Menlo,monospace;font-size:12px;letter-spacing:.1em;
  color:var(--muted);margin-right:10px}
.skel-post-bar{display:flex;flex-wrap:wrap;align-items:center;gap:12px}
.skel-expand{min-height:44px;padding:8px 16px;border:1px solid var(--rule);border-radius:22px;
  background:var(--card-bg);color:var(--muted);font-size:13px;font-family:inherit;cursor:pointer}
.skel-expand:hover{color:var(--fg);border-color:color-mix(in srgb,var(--accent) 50%,var(--rule))}
.skel-expand[aria-expanded="true"]{color:var(--fg);
  border-color:color-mix(in srgb,var(--accent) 60%,var(--rule))}
/* rows */
.skel-tree{margin-top:14px}
.skel-tree-list{list-style:none;margin:0;padding:0}
.skel-tree-list .skel-tree-list{margin:6px 0 6px 14px}
.skel-row{position:relative;margin:0 0 16px;padding:2px 0 2px 12px;
  border-left:2px solid var(--rule);font-size:14.5px;line-height:1.5}
.skel-e-elaborates{border-left-style:dashed}
.skel-e-qualifies{border-left-style:dotted;
  border-left-color:color-mix(in srgb,var(--note) 55%,transparent)}
.skel-e-rebuts{border-left-style:dotted;border-left-color:var(--note)}
.skel-interp{border-left-style:dashed}
/* italic marks the interpolated claim itself, never the rows nested under it */
.skel-interp > .skel-label{font-style:italic}
.skel-glyph{font-family:ui-monospace,Menlo,monospace;color:var(--muted);
  font-size:12px;margin-right:6px;font-style:normal}
.skel-label{margin-right:6px}
.skel-quote{display:inline-flex;align-items:center;justify-content:center;
  border:0;background:transparent;color:var(--accent);cursor:pointer;font-family:inherit;
  font-size:15px;line-height:1;padding:0 12px;min-width:44px;min-height:44px;
  margin:-11px -2px;vertical-align:middle}
.skel-quote[disabled]{color:var(--muted);opacity:.5;cursor:default}
.skel-quote .skel-qn{font-size:10px;vertical-align:super;margin-left:1px}
.skel-row .skel-chip{margin-left:4px;vertical-align:middle}
.skel-row button.skel-chip::after{height:44px}
/* closing restatement */
.skel-close{max-width:820px;margin:26px auto 0;padding:16px 20px;
  border:1px solid var(--rule);border-radius:10px;
  background:color-mix(in srgb,var(--accent) 5%,var(--bg))}
.skel-close p{margin:0;font-size:15.5px;line-height:1.45;font-weight:600}
/* highlight + flash */
mark.skel-hit{background:color-mix(in srgb,var(--accent) 26%,transparent);
  color:inherit;border-radius:3px;padding:1px 0}
.skel-flash{animation:skel-flash 1.2s ease-out 1}
@keyframes skel-flash{
  0%{background:color-mix(in srgb,var(--accent) 24%,transparent)}
  100%{background:transparent}
}
.skel-pulse{animation:skel-pulse .9s ease-out 2}
@keyframes skel-pulse{0%{opacity:1}50%{opacity:.35}100%{opacity:1}}
/* hover dependency highlight (desktop only) */
:root.skel-hov .skel-pre{opacity:.4;transition:opacity .12s}
:root.skel-hov .skel-pre.skel-self,:root.skel-hov .skel-pre.skel-up,
:root.skel-hov .skel-pre.skel-down{opacity:1}
.skel-pre.skel-up .skel-pre-inner{background:color-mix(in srgb,var(--accent) 12%,var(--bg));
  border-left-color:var(--accent)}
.skel-pre.skel-down .skel-pre-inner{outline:1px dashed color-mix(in srgb,var(--muted) 60%,transparent);
  outline-offset:2px}
/* floating, always-dismissible affordances */
#skel-back,#skel-clear{position:fixed;left:14px;z-index:70;display:flex;align-items:center;gap:4px;
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
/* display:flex above would beat the UA [hidden] rule, so restate it */
#skel-back[hidden],#skel-clear[hidden]{display:none}
#skel-back{bottom:14px}
#skel-clear{bottom:66px}
.skel-float-btn,.skel-float-x{min-height:44px;padding:8px 14px;border:1px solid var(--rule);
  border-radius:22px;background:var(--card-bg);color:var(--fg);font-size:13px;cursor:pointer;
  box-shadow:0 6px 20px rgba(0,0,0,.18);font-family:inherit}
.skel-float-x{padding:8px 14px;color:var(--muted)}
/* peek card inside the shared #tip */
#tip .skel-peek-num{display:block;font-family:ui-monospace,Menlo,monospace;font-size:11px;
  letter-spacing:.1em;color:var(--muted);margin-bottom:4px}
#tip .skel-peek-label{display:block;font-size:14.5px;line-height:1.45;margin-bottom:10px}
#tip .skel-goto{min-height:40px;padding:8px 14px;border:1px solid var(--rule);border-radius:20px;
  background:var(--card-bg);color:var(--accent);font-size:13px;cursor:pointer;font-family:inherit}
/* the erwaz toggle shares .themebtn's look; only the on-state differs */
.skelbtn.on{background:var(--accent);color:var(--bg);border-color:var(--accent)}
"""


SKEL_JS = r"""
(function(){
  if (typeof SKEL === 'undefined' || !SKEL) return;
  var root = document.documentElement;
  var btn = document.getElementById('skelbtn');
  var blocks = document.querySelectorAll('[data-skel-block]');
  var backBar = document.getElementById('skel-back');
  var backBtn = document.getElementById('skel-back-btn');
  var backX = document.getElementById('skel-back-x');
  var clearBar = document.getElementById('skel-clear');
  var clearBtn = document.getElementById('skel-clear-btn');
  var tip = document.getElementById('tip');
  var on = false;                 // default OFF on every load; never persisted
  var backTarget = null;

  function setOn(next){
    on = next;
    root.classList.toggle('skel-on', on);
    btn.classList.toggle('on', on);
    btn.setAttribute('aria-pressed', on ? 'true' : 'false');
    for (var i = 0; i < blocks.length; i++){
      // a dismissed block drops the attribute and stays gone for this load
      if (blocks[i].hasAttribute('data-skel-block')) blocks[i].hidden = !on;
    }
    if (!on){ clearMarks(); hideBack(); clearHover(); closeTip(); }
  }

  /* ---- shared hover card ------------------------------------------- */
  function openTip(el, inner){
    if (window.SKEL_TIP) window.SKEL_TIP.open(el, inner);
  }
  function closeTip(){ if (window.SKEL_TIP) window.SKEL_TIP.close(); }

  function glossCard(key){
    var text = SKEL.glosses[key] || '';
    return '<p>' + escapeHtml(text) + '</p>';
  }
  function peekCard(num, label, goto){
    var out = '<span class="skel-peek-num">' + escapeHtml(num) + '</span>' +
              '<span class="skel-peek-label">' + escapeHtml(label) + '</span>';
    if (goto){
      out += '<button type="button" class="skel-goto" data-skel-travel="' +
             escapeHtml(goto) + '">→ odaugrás</button>';
    }
    return out;
  }
  function escapeHtml(s){
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  /* ---- travel between boxes ---------------------------------------- */
  function boxOf(chunk){
    var meta = SKEL.chunks[chunk];
    return meta ? document.getElementById(meta.box) : null;
  }
  function flash(el){
    if (!el) return;
    el.classList.remove('skel-flash');
    void el.offsetWidth;
    el.classList.add('skel-flash');
    setTimeout(function(){ el.classList.remove('skel-flash'); }, 1300);
  }
  function currentChunk(el){
    if (!el.closest) return null;
    // a physical section can hold two chunks, so ask the key block first
    var block = el.closest('[data-skel-chunk]');
    if (block) return block.getAttribute('data-skel-chunk');
    var post = el.closest('.skel-post');
    if (post){
      var num = post.querySelector('.skel-post-num');
      if (num) return num.textContent.trim();
    }
    return null;
  }
  function travel(chunk, from){
    var box = boxOf(chunk);
    if (!box) return;
    closeTip();
    box.scrollIntoView({block: 'start', behavior: 'smooth'});
    var inner = box.querySelector('.skel-pre-inner') || box;
    flash(inner);
    if (from && from !== chunk) showBack(from);
  }
  function showBack(chunk){
    backTarget = chunk;
    backBtn.textContent = '← vissza ' + chunk;
    backBar.hidden = false;
  }
  function hideBack(){ backTarget = null; backBar.hidden = true; }

  /* ---- anchor highlight -------------------------------------------- */
  function clearMarks(){
    var marks = document.querySelectorAll('mark.skel-hit');
    for (var i = 0; i < marks.length; i++){
      var m = marks[i], p = m.parentNode;
      while (m.firstChild) p.insertBefore(m.firstChild, m);
      p.removeChild(m);
      p.normalize();            // mandatory: mark residue would split text nodes
    }
    clearBar.hidden = true;
  }
  function findInNode(node, quote){
    var i = node.data.indexOf(quote);
    if (i >= 0) return [i, i + quote.length];
    // whitespace-normalised fallback, mapped back to original offsets
    var map = [], norm = '', prevWs = false;
    for (var k = 0; k < node.data.length; k++){
      var ch = node.data[k];
      if (/\s/.test(ch)){
        if (prevWs) continue;
        prevWs = true; norm += ' '; map.push(k);
      } else {
        prevWs = false; norm += ch; map.push(k);
      }
    }
    var nq = quote.replace(/\s+/g, ' ').trim();
    var j = norm.indexOf(nq);
    if (j < 0) return null;
    var start = map[j];
    var endIdx = j + nq.length - 1;
    var end = (endIdx < map.length ? map[endIdx] : node.data.length - 1) + 1;
    return [start, end];
  }
  function markQuote(article, quote){
    var walker = document.createTreeWalker(article, NodeFilter.SHOW_TEXT, null);
    var node;
    while ((node = walker.nextNode())){
      if (!node.data || node.data.length < 3) continue;
      var span = findInNode(node, quote);
      if (!span) continue;
      try {
        var range = document.createRange();
        range.setStart(node, span[0]);
        range.setEnd(node, span[1]);
        var mark = document.createElement('mark');
        mark.className = 'skel-hit';
        range.surroundContents(mark);
        return mark;
      } catch (err) {
        return null;
      }
    }
    return null;
  }
  function showEnglish(sec){
    var btns = sec.querySelectorAll('.lang-btn');
    for (var i = 0; i < btns.length; i++){
      if (btns[i].getAttribute('data-lang') === 'en'){
        btns[i].click();
        var group = sec.querySelector('.lang-toggle');
        if (group){
          group.classList.remove('skel-pulse');
          void group.offsetWidth;
          group.classList.add('skel-pulse');
          setTimeout(function(){ group.classList.remove('skel-pulse'); }, 2000);
        }
        return true;
      }
    }
    return false;
  }
  function jump(nodeId){
    var list = SKEL.anchors[nodeId];
    if (!list || !list.length) return;
    var usable = [];
    for (var i = 0; i < list.length; i++) if (list[i].ok) usable.push(list[i]);
    if (!usable.length) return;
    var seen = jump.seen || (jump.seen = {});
    var idx = (seen[nodeId] || 0) % usable.length;
    seen[nodeId] = idx + 1;
    var anchor = usable[idx];
    clearMarks();
    var sec = document.getElementById('sec-' + anchor.sec);
    if (!sec) return;
    var article = sec.querySelector('article.orig.lang-en');
    if (!article) return;
    if (article.hidden) showEnglish(sec);
    // hidden articles measure as zero, so wait for the layout to settle
    requestAnimationFrame(function(){
      // clear again inside the frame: two taps in quick succession would
      // otherwise both mark, and the first would survive the second's clear
      clearMarks();
      var mark = markQuote(article, anchor.q);
      if (mark){
        try { mark.scrollIntoView({block: 'center', behavior: 'smooth'}); } catch (e) {
          mark.scrollIntoView();
        }
        clearBar.hidden = false;
        return;
      }
      var fallback = null;
      if (anchor.fn != null){
        fallback = document.getElementById('fn-en-' + anchor.sec + '-' + anchor.fn);
      }
      var target = fallback || sec.querySelector('.sec-head') || sec;
      target.scrollIntoView({block: fallback ? 'center' : 'start', behavior: 'smooth'});
      flash(fallback || sec.querySelector('.sec-head'));
    });
  }

  /* ---- hover dependency highlight (desktop pointers only) ----------- */
  var finePointer = window.matchMedia &&
    window.matchMedia('(hover:hover) and (pointer:fine)').matches;
  function clearHover(){
    root.classList.remove('skel-hov');
    var boxes = document.querySelectorAll('.skel-pre');
    for (var i = 0; i < boxes.length; i++){
      boxes[i].classList.remove('skel-self', 'skel-up', 'skel-down');
    }
  }
  function applyHover(box){
    var chunks = (box.getAttribute('data-skel-box') || '').split(' ');
    var up = {}, down = {};
    for (var i = 0; i < chunks.length; i++){
      (SKEL.up[chunks[i]] || []).forEach(function(c){ up[c] = 1; });
      (SKEL.down[chunks[i]] || []).forEach(function(c){ down[c] = 1; });
    }
    clearHover();
    root.classList.add('skel-hov');
    box.classList.add('skel-self');
    Object.keys(up).forEach(function(c){
      var b = boxOf(c); if (b && b !== box) b.classList.add('skel-up');
    });
    Object.keys(down).forEach(function(c){
      var b = boxOf(c); if (b && b !== box) b.classList.add('skel-down');
    });
  }

  /* ---- wiring ------------------------------------------------------- */
  btn.addEventListener('click', function(){ setOn(!on); });

  document.addEventListener('click', function(ev){
    var t = ev.target;
    if (!t || !t.closest) return;

    var expand = t.closest('.skel-expand');
    if (expand){
      var tree = document.getElementById(expand.getAttribute('data-skel-expand'));
      if (tree){
        var open = tree.hidden;
        tree.hidden = !open;
        expand.setAttribute('aria-expanded', open ? 'true' : 'false');
      }
      return;
    }
    var quote = t.closest('.skel-quote');
    if (quote && !quote.disabled){ jump(quote.getAttribute('data-skel-quote')); return; }

    var gloss = t.closest('.skel-gloss');
    if (gloss){ openTip(gloss, glossCard(gloss.getAttribute('data-skel-gloss'))); return; }

    var peek = t.closest('[data-skel-peek]');
    if (peek){
      var cid = peek.getAttribute('data-skel-peek');
      var meta = SKEL.chunks[cid];
      if (meta) openTip(peek, peekCard(cid, meta.label, cid));
      return;
    }
    var peekNode = t.closest('[data-skel-peek-node]');
    if (peekNode){
      var nid = peekNode.getAttribute('data-skel-peek-node');
      var nmeta = SKEL.nodes[nid];
      if (nmeta) openTip(peekNode, peekCard(nmeta.chunk, nmeta.label, null));
      return;
    }
    var dot = t.closest('.skel-dot');
    if (dot){ travel(dot.getAttribute('data-skel-goto'), null); return; }

    var travelBtn = t.closest('[data-skel-travel]');
    if (travelBtn){
      var to = travelBtn.getAttribute('data-skel-travel');
      var origin = window.SKEL_LAST_ORIGIN || null;
      travel(to, origin);
      return;
    }
  });

  // Remember which box a chunk chip was tapped from, for the single back slot.
  document.addEventListener('pointerdown', function(ev){
    var t = ev.target;
    if (!t || !t.closest) return;
    var chip = t.closest('[data-skel-peek]');
    if (chip) window.SKEL_LAST_ORIGIN = currentChunk(chip);
  }, true);

  // Any pointer press outside a mark, the clear chip or a quote button
  // dismisses the highlight. Namespaced so the existing #tip handlers are
  // untouched.
  document.addEventListener('pointerdown', function(ev){
    if (clearBar.hidden) return;
    var t = ev.target;
    if (t && t.closest && (t.closest('mark.skel-hit') || t.closest('#skel-clear') ||
        t.closest('.skel-quote'))) return;
    clearMarks();
  }, true);

  document.addEventListener('keydown', function(ev){
    if (ev.key !== 'Escape') return;
    if (!clearBar.hidden) clearMarks();
    hideBack();
  });

  clearBtn.addEventListener('click', function(){ clearMarks(); });
  backBtn.addEventListener('click', function(){
    if (backTarget){ var to = backTarget; hideBack(); travel(to, null); }
  });
  backX.addEventListener('click', hideBack);

  var legendX = document.getElementById('skel-legend-x');
  if (legendX){
    legendX.addEventListener('click', function(){
      var box = document.getElementById('skel-legend');
      if (box){ box.hidden = true; box.removeAttribute('data-skel-block'); }
    });
  }

  if (finePointer){
    var boxes = document.querySelectorAll('.skel-pre');
    for (var i = 0; i < boxes.length; i++){
      (function(box){
        box.addEventListener('mouseenter', function(){ if (on) applyHover(box); });
        box.addEventListener('mouseleave', clearHover);
      })(boxes[i]);
    }
  }

  if (tip){
    tip.addEventListener('click', function(ev){
      var g = ev.target.closest && ev.target.closest('[data-skel-travel]');
      if (g) travel(g.getAttribute('data-skel-travel'), window.SKEL_LAST_ORIGIN || null);
    });
  }

  setOn(false);
})();
"""

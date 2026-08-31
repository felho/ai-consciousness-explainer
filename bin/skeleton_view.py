#!/usr/bin/env python3
"""Turn skeleton/skeleton.yaml into the "ervvaz" (argument-skeleton) reading aid.

Everything derivable is derived here, in Python, at build time. The browser gets
pre-computed SVG geometry, pre-ordered rows and a small JSON blob; the page JS
only swaps class strings, moves the viewport around and highlights text. Nothing
about the skeleton's shape is recomputed in the browser.

The aid has exactly two visual components (v2 - structure is visible as a graph):

  1. The CHAPTER MINIMAP, a reading-order arc diagram with a lifted roof. One
     static geometry, rendered 17 times: once as a viewpoint-less overview at the
     top of the page, then once before ("pre") and once after ("post") each of
     the 8 physical sections. Only the class strings differ between instances -
     position IS the type, so the reader learns one picture and then only reads
     its ink.
  2. The CHAPTER DETAIL, a lane-based argument graph of one chunk's local
     in-tree. Lanes are depth; the marker vocabulary is the claim's status and
     the stroke vocabulary is the edge's role. Below 700px the v1 nested list is
     kept as the fallback, because lanes need horizontal room to mean anything.

Vocabulary
  chunk    a unit of the argument map. Usually one physical section, but
           section 06 is mapped as two virtual chunks, "06a" and "06b".
  node     a claim in the map. level 0 = thesis, 1 = a chunk's key claim,
           2 = a supporting claim inside a chunk.
  local    an edge whose two endpoints sit in the same chunk (and neither is
           the thesis). Local edges form a rooted in-tree at the key claim.
  cross    everything else; the minimap's arcs, fan and carries.
  rail     the eight chunks 01..07 (06 counts twice), in reading order.
  roof     chunk 00, the descriptive backbone; an in-degree-8 sink.

Page chrome is Hungarian. Node labels exist in both languages: the skeleton
carries the mapper's English, skeleton/labels.hu.yaml is the thin Hungarian
overlay (SCHEMA.md, "Localization overlay"). Anchors are English-only by
construction - they are verbatim quotes of the original.
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
LABELS_HU_PATH = os.path.join(_REPO, "skeleton", "labels.hu.yaml")

# Local edge types, in the order the row encoding treats them. `presupposes` is
# absent on purpose: every presupposes edge in the map is cross-chunk.
LOCAL_EDGE_TYPES = ("supports", "elaborates", "qualifies", "rebuts")

# v1 carried a WARRANT_ON_ARROW eligibility predicate for the Toulmin picture -
# an interpolated warrant drawn as a label on the arrow it licenses instead of
# as a node of its own. It is gone: SCHEMA.md ("The bridge, at three
# explicitness levels") already settles that this picture is a DERIVED VIEW and
# never the stored shape, so a dormant predicate here only duplicated a decision
# that lives there. The lane view draws warrants as ordinary rows with a hollow
# dashed diamond, which says the same thing in the one visual grammar the rest
# of the graph already uses.

# The argumentation schemes' names ("sch-<id>") and their one-sentence glosses
# ("schg-<id>") live in UI_STRINGS below, with every other string that sits on a
# card next to a node label. Each sentence carries the scheme's critical
# question - what the step would have to survive to hold - so a translation has
# to keep that clause, not just the name. _check_schemes() fails the build if a
# scheme the map actually uses has no name or no sentence in some language.

# The only strings that follow the label language rather than the page chrome:
# they sit inside the diagram or on a card next to labels, and a Hungarian
# caption over an English label reads as a bug. `%1`, `%2`, ... are positional
# arguments, substituted by _fmt() here and by T() in the page JS.
#
# Number agreement is the reason a few English strings are phrased loosely:
# every count that reaches a plural noun is provably >= 2 (the smallest chunk
# carries 4 claims; a multi-quote gloss only fires above 1), but the
# interpolation count is 1 in every chunk that has any, so the English
# composition line says "added" rather than a noun that would need a plural.
UI_STRINGS = {
    "hu": {
        "thesis-cap": "TÉZIS",
        "pre": "mire épül",
        "post": "mit adott hozzá",
        "overview": "a gondolatmenet váza",
        "graphtag": "AZ ÉRVELÉS ÁBRÁJA",
        "comp": "%1 állítás · %2 szint",
        "comp-add": "%1 állítás · %2 szint · ◇ %3 kiegészítés",
        "n-claims": "%1 állítás",
        "builds-on": "mire épül:",
        "built-on-by": "építenek rá:",
        "to-start": "→ elejére",
        "details": "⋮ részletei",
        "quote-n": "idézet %1/%2",
        "mg-key": "a fejezet kulcsállítása",
        "mg-anchored": "állítás — a szöveg kimondja",
        "mg-anchored-n": "állítás — a szöveg kimondja (%1 idézet)",
        "mg-fn": "állítás — csak lábjegyzetben él",
        "mg-interp": "kiegészítés — a térkép tette hozzá, a szöveg ezt nem mondja ki",
        "bp-also": "továbbá alátámasztja: %1",
        "thesis-note": "A leíró gerinctől egyetlen lépés vezet a normatív tézisig — "
                       "és ez a lépés nem bizonyítás.",
        "sch-analogy": "analógia",
        "sch-authority": "tekintély",
        "sch-precaution": "elővigyázatosság",
        "schg-analogy": "Analógia: a lépés két dolog hasonlóságán nyugszik, és pontosan "
                        "annyit bír el, amennyire a hasonlóság a lényeges pontokon fennáll.",
        "schg-authority": "Tekintély: az állítás súlyát egy szakértő vagy forrás "
                          "állásfoglalása adja, nem a helyben bemutatott bizonyíték.",
        "schg-precaution": "Elővigyázatosság: nem logikai következtetés — abból, hogy a "
                           "dolog elég valószínű és a tét nagy, jut oda, hogy már most "
                           "tenni kell valamit.",
    },
    "en": {
        "thesis-cap": "THESIS",
        "pre": "what it builds on",
        "post": "what it added",
        "overview": "the shape of the argument",
        "graphtag": "THE ARGUMENT, DRAWN",
        "comp": "%1 claims · %2 levels",
        "comp-add": "%1 claims · %2 levels · ◇ %3 added",
        "n-claims": "%1 claims",
        "builds-on": "builds on:",
        "built-on-by": "built on by:",
        "to-start": "→ to its start",
        "details": "⋮ details",
        "quote-n": "quote %1/%2",
        "mg-key": "the chapter's key claim",
        "mg-anchored": "claim — stated by the text",
        "mg-anchored-n": "claim — stated by the text (%1 quotes)",
        "mg-fn": "claim — lives only in a footnote",
        "mg-interp": "addition — supplied by the map, the text never states it",
        "bp-also": "also supports: %1",
        "thesis-note": "One step leads from the descriptive backbone to the normative "
                       "thesis — and that step is not a proof.",
        "sch-analogy": "analogy",
        "sch-authority": "authority",
        "sch-precaution": "precaution",
        "schg-analogy": "Analogy: the step rests on two things being alike, and holds "
                        "exactly as far as the likeness holds at the points that matter.",
        "schg-authority": "Authority: the claim's weight comes from an expert's or a "
                          "source's stance on it, not from evidence presented here.",
        "schg-precaution": "Precaution: not a logical inference — it goes from the thing "
                           "being likely enough and the stakes being high to something "
                           "having to be done now.",
    },
}


_TAG_RE = re.compile(r"<[^>]*>")
_WS_RE = re.compile(r"\s+")
_ARG_RE = re.compile(r"%(\d)")


class SkeletonError(Exception):
    """The skeleton could not be loaded or does not have the expected shape."""


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------

def _tidy(text):
    return _WS_RE.sub(" ", (text or "").strip())


def shorten(text, limit=118):
    """Trim to a word boundary. Used for every 'compact restatement'.

    Mirrored by shorten() in the page JS, which has to redo this after a
    language switch; keep the two in step.
    """
    text = _tidy(text)
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut.rstrip(" ,;:.—-") + "…"


def _fmt(template, args):
    """Substitute %1, %2, ... Mirrored by T() in the page JS; keep the two in
    step, because the same string is rendered here at build time and again in
    the browser after a language switch."""
    return _ARG_RE.sub(lambda m: str(args[int(m.group(1)) - 1]), template)


def _i18n_span(cls, key, args=()):
    """A span whose text follows the EN|HU label pill rather than page chrome."""
    attr = (' data-i18n-args="%s"' % _esc("|".join(str(a) for a in args))) if args else ""
    return ('<span class="%s" data-i18n="%s"%s>%s</span>'
            % (cls, key, attr, _esc(_fmt(UI_STRINGS["hu"][key], args))))


def text_nodes(fragment):
    """The text nodes a browser would build from this HTML fragment.

    Splitting on tags is exact here because the builder emits no comments and
    no CDATA, so every gap between two tags is one text node.
    """
    return [html.unescape(part) for part in _TAG_RE.split(fragment)]


def _esc(text):
    return html.escape(_tidy(text))


def _n(value):
    """Round a geometry number for the SVG output (bytes matter: 17 copies)."""
    return ("%.1f" % value).rstrip("0").rstrip(".")


def phys_section(chunk):
    """Physical section id of a chunk: "06a" -> "06"."""
    return chunk[:2]


# --------------------------------------------------------------------------
# the marker vocabulary, drawn once
# --------------------------------------------------------------------------

def marker_ink(kind, x, y):
    """The SVG ink for one marker kind, centred on (x, y).

    The lane row draws its marker with this and the gloss card's sign is built
    from it, so "this explains THAT sign" holds by construction: there is no
    second place where a glyph could drift away from the one on the row.
    """
    if kind == "key":
        return ('<circle class="sk-mkey-ring" cx="%s" cy="%s" r="8"/>'
                '<circle class="sk-mkey" cx="%s" cy="%s" r="6"/>'
                % (_n(x), _n(y), _n(x), _n(y)))
    if kind == "interp":
        return ('<path class="sk-minterp" d="M%s %s l6 6 l-6 6 l-6 -6 Z"/>'
                % (_n(x), _n(y - 6)))
    ink = '<circle class="sk-mdot" cx="%s" cy="%s" r="4.5"/>' % (_n(x), _n(y))
    if kind == "fn":
        ink += ('<path class="sk-mfn" d="M%s %s L%s %s"/>'
                % (_n(x - 3.5), _n(y + 8.5), _n(x + 3.5), _n(y + 8.5)))
    return ink


# The gloss card's sign: a small standalone SVG, sized so the widest glyph (the
# key ring) and the lowest one (the footnote dash) both fit.
SIGN_W, SIGN_H, SIGN_CX, SIGN_CY = 22, 24, 11, 10


def _sign(inner):
    return ('<svg class="sk-sign" viewBox="0 0 %d %d" width="%d" height="%d" '
            'aria-hidden="true" focusable="false">%s</svg>'
            % (SIGN_W, SIGN_H, SIGN_W, SIGN_H, inner))


def _build_signs():
    """gloss key -> the sign that gloss explains, as drawn on the row."""
    cx, cy = SIGN_CX, SIGN_CY
    marks = {k: _sign(marker_ink(k, cx, cy))
             for k in ("key", "anchored", "fn", "interp")}
    return {
        "mg-key": marks["key"],
        "mg-anchored": marks["anchored"],
        "mg-anchored-n": marks["anchored"],
        "mg-fn": marks["fn"],
        "mg-interp": marks["interp"],
        "scheme": _sign('<path class="sk-scheme" d="M%d %d l5 5 l-5 5 l-5 -5 Z"/>'
                        % (cx, cy - 5)),
        # the bypass's own idiom, drawn the way the row draws it: a dashed run
        # in its own band, ending in an up-arrow on the claim it also supports.
        # Sat one band lower than the other signs, which put their ink around
        # SIGN_CY; the run and arrow are placed so their combined mass lands
        # there too, or the sign reads as slipping off the first text line.
        "bypass": _sign('<path class="sk-ed sk-ed-bypass" d="M2 13 L15 13"/>'
                        '<path class="sk-term sk-term-bypass" '
                        'd="M15 8 L12.5 13 L17.5 13 Z"/>'),
    }


SIGNS = _build_signs()


# --------------------------------------------------------------------------
# minimap geometry, in user units of the 760x252 viewBox
# --------------------------------------------------------------------------

VB_W, VB_H = 760, 252
CELL_W, CELL_H, PITCH, CELL_X0 = 62, 24, 98, 6
RAIL_T, RAIL_B = 102, 126
ROOF_T, ROOF_B, ROOF_X, ROOF_W = 52, 76, 6, 748
CAP_T, CAP_H, CAP_W = 4, 24, 72
GLYPH_Y, GLYPH_R = 89, 7
BAR_Y, BAR_W = 123, 54
# The arc band is everything below RAIL_B. Its depth function is 3x the v2
# original (was 6.0/4.4 in a 168-unit box): sixteen nested arcs in a ~42-unit
# band read as a tangle and cannot be hover-targeted one by one, so the band
# gets ~126 units instead and the seven nesting levels land 13.2 units apart.
# Deepest arc: RAIL_B + BASE + SPAN*7 = 236.4, inside VB_H with room to spare.
ARC_DEPTH_BASE, ARC_DEPTH_SPAN = 18.0, 13.2
HIT_H = 44  # every node's invisible hit rect is at least 44 units tall


def _cell_cx(i):
    return CELL_X0 + PITCH * i + CELL_W / 2.0


# The detail view's lane model. Lane 0 sits at LANE_X0; a bypass edge (a second
# parent) runs in its own lane to the LEFT of lane 0, so it never collides with
# the tree.
LANE_X0, LANE_PITCH, BYPASS_X = 30, 26, 10
MARK_Y, HEAD_H = 14, 40
# The bypass gets a band of its own, BYPASS_DY below the tree's elbow line.
# v2.2 drew it AT MARK_Y, which put two different edges on one line: on the one
# row that carries both a scheme diamond and a bypass endpoint, the diamond's
# opaque fill landed exactly on the bypass arrowhead and swallowed it, so the
# bypass arrived headless and the diamond read as its terminal ornament. The
# sign belongs to the solid elbow; separating the lines is what says so.
# The band sits below EVERY glyph the elbow line carries: the diamond's lowest
# point is MARK_Y+5 and the key ring's is MARK_Y+8, so at MARK_Y+12 the bypass
# and its arrowhead cross nothing and hide nothing.
BYPASS_DY = 12
BYPASS_Y = MARK_Y + BYPASS_DY
# The bypass turns toward the row this far left of the marker - right of the
# diamond (which ends at x-8) and left of the row's own child lane (at x).
BYPASS_TURN = 6
THUMB_W, THUMB_PITCH, THUMB_LANE, THUMB_PAD = 124, 6, 9, 6


# --------------------------------------------------------------------------
# view model
# --------------------------------------------------------------------------

class SkeletonView(object):
    def __init__(self, doc, labels_hu, section_index):
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

        self.label_en = {nid: _tidy(n.get("label")) for nid, n in self.by_id.items()}
        self.label_hu = self._check_labels(labels_hu)

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

        self.rank = {c: i for i, c in enumerate(self.chunks)}
        self.roof = self.chunks[0]
        self.rail = self.chunks[1:]
        if len(self.rail) != 8:
            raise SkeletonError("the minimap rail expects 8 chunks, got %d"
                                % len(self.rail))

        self._derive()
        self._derive_minimap()
        self._derive_lanes()
        self._check_schemes()

    # ---- labels ---------------------------------------------------------

    def _check_labels(self, labels_hu):
        """The overlay must cover exactly the skeleton's node ids - no more, no
        fewer. A silently partial overlay would show a mixed-language graph."""
        if not isinstance(labels_hu, dict):
            raise SkeletonError("labels.hu.yaml has no top-level `labels:` mapping")
        have, want = set(labels_hu), set(self.by_id)
        extra, gone = sorted(have - want), sorted(want - have)
        if extra or gone:
            parts = []
            if gone:
                parts.append("missing %d: %s" % (len(gone), ", ".join(gone[:6])
                                                 + ("…" if len(gone) > 6 else "")))
            if extra:
                parts.append("unknown %d: %s" % (len(extra), ", ".join(extra[:6])
                                                 + ("…" if len(extra) > 6 else "")))
            raise SkeletonError(
                "skeleton/labels.hu.yaml must carry exactly the %d skeleton node "
                "ids (%s). Re-translate the changed `label:` fields, or build "
                "without the reading aid." % (len(want), "; ".join(parts)))
        return {nid: _tidy(labels_hu[nid]) for nid in want}

    def _schemes_used(self):
        """Every scheme the page can put a gloss card on: the fan's glyphs, the
        detail rows' diamonds, and the one on the step into the thesis."""
        used = {s for s in self.fan.values() if s}
        for chunk in self.chunks:
            for m in self.lanes[chunk]["meta"]:
                if m["row"]["scheme"] and m["depth"]:
                    used.add(m["row"]["scheme"])
        used.add((self.thesis_edge or {}).get("scheme") or "precaution")
        return used

    def _check_schemes(self):
        """A scheme with no name or no sentence in some language would open a
        card in the wrong language, or an empty one. Same failure _check_labels()
        guards against for node labels, so it fails the build the same way."""
        missing = []
        for scheme in sorted(self._schemes_used()):
            for lang in sorted(UI_STRINGS):
                for prefix in ("sch-", "schg-"):
                    if not UI_STRINGS[lang].get(prefix + scheme):
                        missing.append("%s/%s%s" % (lang, prefix, scheme))
        if missing:
            raise SkeletonError(
                "argumentation schemes the map uses but UI_STRINGS does not "
                "carry: %s. Add the name and the gloss sentence (keep the "
                "scheme's critical question) to UI_STRINGS in "
                "bin/skeleton_view.py." % ", ".join(missing))

    # ---- derivations ---------------------------------------------------

    def _chunk_of(self, nid):
        return self.by_id[nid].get("section")

    def _derive(self):
        thesis_id = self.thesis["id"]
        rank = self.rank

        local_out = {}   # node -> [(target, type, scheme)] within its own chunk
        cross = []       # (src, dst, type, scheme)
        for edge in self.edges:
            src, dst = edge.get("from"), edge.get("to")
            etype, scheme = edge.get("type"), edge.get("scheme")
            if src not in self.by_id or dst not in self.by_id:
                raise SkeletonError("edge references an unknown node: %s -> %s" % (src, dst))
            if dst == thesis_id or src == thesis_id:
                continue  # the is->ought step lives on the thesis capsule
            if self._chunk_of(src) == self._chunk_of(dst):
                local_out.setdefault(src, []).append((dst, etype, scheme))
            else:
                cross.append((src, dst, etype, scheme))
        self.cross_edges = cross
        self.backbone_id = self.key_of[self.roof]["id"]

        # Chunk dependency: X depends on Y when X presupposes something in Y, or
        # when Y's material supports a claim of X. Supports into the descriptive
        # backbone are excluded - every chunk feeds it, so listing it says nothing.
        depends = {c: [] for c in self.chunks}
        for src, dst, etype, _scheme in cross:
            csrc, cdst = self._chunk_of(src), self._chunk_of(dst)
            if etype == "presupposes":
                dep, base = csrc, cdst
            elif etype == "supports" and dst != self.backbone_id:
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
        self.interp_count = {}
        for chunk in self.chunks:
            key = self.key_of[chunk]["id"]
            members = [n["id"] for n in self.by_id.values()
                       if n.get("section") == chunk and n.get("level") == 2]
            self.d1[chunk] = len(members)
            self.interp_count[chunk] = sum(
                1 for m in members if self.by_id[m].get("interpolated") is True)

            children = {}  # parent -> [child ids]
            for nid in members:
                for dst, _t, _s in local_out.get(nid, []):
                    children.setdefault(dst, []).append(nid)

            # Distance to the key over local edges; the primary parent of a node
            # is the parent that sits closest to the key, so the extra edge of an
            # out-degree-2 node becomes the drawn bypass.
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

            primary, extras = {}, {}
            for nid in members:
                outs = local_out.get(nid, [])
                if not outs:
                    continue
                ranked = sorted(outs, key=lambda e: dist.get(e[0], 99))
                primary[nid] = ranked[0]
                if len(ranked) > 1:
                    extras[nid] = ranked[1:]

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

        # Anchors, flattened for the build-time verifier and the page JS.
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

    def footnote_only(self, nid):
        """D3: every anchor of this node sits below the line. Derived, never stored."""
        anchors = self.anchor_index.get(nid, [])
        return bool(anchors) and all(a["fn"] is not None for a in anchors)

    # ---- minimap geometry ------------------------------------------------

    def _derive_minimap(self):
        """Compute the one static geometry the 17 instances all share."""
        rank, rail = self.rank, self.rail
        idx = {c: i for i, c in enumerate(rail)}
        self.rail_index = idx

        # Fan: every rail chunk's key claim supports the roof's key claim.
        fan = {}
        for src, dst, etype, scheme in self.cross_edges:
            if dst == self.backbone_id and etype == "supports":
                fan[self._chunk_of(src)] = scheme
        missing = [c for c in rail if c not in fan]
        if missing:
            raise SkeletonError("rail chunks with no support into the backbone: %s"
                                % ", ".join(missing))
        self.fan = fan

        # Arcs: backward `presupposes`, collapsed to chunk pairs. Multiplicity is
        # the number of node-level edges behind the chunk-level arc; an arc that
        # only ever lands on sub-claims gets a hollow head (a deep link, not a
        # dependency on the chapter's headline claim).
        arcs = {}
        for src, dst, etype, _scheme in self.cross_edges:
            if etype != "presupposes":
                continue
            a, b = self._chunk_of(src), self._chunk_of(dst)
            if rank[a] <= rank[b]:
                raise SkeletonError("forward presupposes edge %s -> %s" % (src, dst))
            key = "%s>%s" % (a, b)
            rec = arcs.setdefault(key, {"a": a, "b": b, "edges": [], "deep": True})
            rec["edges"].append([src, dst])
            if self.by_id[dst].get("level") == 1:
                rec["deep"] = False

        # Forward cross-chunk supports: the two carries that reading order makes
        # but no arc can show (an arc band holds backward edges only).
        carries = []
        for src, dst, etype, _scheme in self.cross_edges:
            a, b = self._chunk_of(src), self._chunk_of(dst)
            if rank[a] < rank[b] and dst != self.backbone_id:
                carries.append({"a": a, "b": b, "edges": [[src, dst]]})

        # Attachment spreading: several arcs meet at one cell, so their endpoints
        # fan out across the cell's width instead of stacking into one blob.
        att = {c: [] for c in rail}
        for key in sorted(arcs, key=lambda k: (idx[arcs[k]["a"]], idx[arcs[k]["b"]])):
            rec = arcs[key]
            att[rec["a"]].append((idx[rec["b"]], key, "tail"))
            att[rec["b"]].append((idx[rec["a"]], key, "head"))
        slot = {}
        for chunk, items in att.items():
            items.sort()
            n = len(items)
            step = 0 if n < 2 else min(9.0, 44.0 / (n - 1))
            for k, (_partner, key, role) in enumerate(items):
                slot[(key, role)] = _cell_cx(idx[chunk]) + (k - (n - 1) / 2.0) * step

        self.arcs = []
        for key in sorted(arcs, key=lambda k: (idx[arcs[k]["b"]], idx[arcs[k]["a"]])):
            rec = arcs[key]
            span = idx[rec["a"]] - idx[rec["b"]]
            depth = ARC_DEPTH_BASE + ARC_DEPTH_SPAN * span
            x1, x2 = slot[(key, "tail")], slot[(key, "head")]
            self.arcs.append({
                "key": key, "a": rec["a"], "b": rec["b"],
                "n": len(rec["edges"]), "edges": rec["edges"], "deep": rec["deep"],
                "d": "M%s %d Q%s %s %s %d" % (_n(x1), RAIL_B, _n((x1 + x2) / 2.0),
                                              _n(RAIL_B + 2 * depth), _n(x2), RAIL_B),
                "hx": x2,  # the earlier end: where the arrowhead sits
            })
        self.carries = []
        for rec in carries:
            ia, ib = idx[rec["a"]], idx[rec["b"]]
            gap_l = CELL_X0 + PITCH * min(ia, ib) + CELL_W
            gap_r = CELL_X0 + PITCH * max(ia, ib)
            rec["x"] = (gap_l + gap_r) / 2.0
            self.carries.append(rec)

        # Load bars: solid length is the chunk's D1 count, the dashed tail is the
        # part of that load the text never states (D2).
        top = max(self.d1[c] for c in rail)
        self.bars = {}
        for chunk in rail:
            total = BAR_W * self.d1[chunk] / float(top)
            interp = self.interp_count[chunk]
            dash = 0.0 if not interp else max(6.0, BAR_W * interp / float(top))
            self.bars[chunk] = (max(0.0, total - dash), dash)

        self.cap_cx = _cell_cx(len(rail) - 1)

    # ---- lane model for the detail view ----------------------------------

    def _derive_lanes(self):
        """Per chunk: row depth, parent, sibling continuation lanes, bypass edges.

        The row geometry has to survive labels of unknown height, so it is split:
        the verticals are plain full-height CSS divs (trivial), and only the
        elbow/marker/arrowhead head - which is text-line-height dependent and
        therefore fixed at HEAD_H - is an SVG.
        """
        self.lanes = {}
        for chunk in self.chunks:
            rows = self.rows[chunk]
            index_of = {r["id"]: i for i, r in enumerate(rows)}
            maxdepth = max(r["depth"] for r in rows)

            parent = [None] * len(rows)
            stack = {}
            for i, row in enumerate(rows):
                stack[row["depth"]] = i
                if row["depth"] > 0:
                    parent[i] = stack[row["depth"] - 1]

            kids = {}
            for i, p in enumerate(parent):
                if p is not None:
                    kids.setdefault(p, []).append(i)
            last = [True] * len(rows)
            for p, group in kids.items():
                for i in group[:-1]:
                    last[i] = False

            # bypass: the second parent of an out-degree-2 node, drawn as a real
            # edge in its own lane rather than as a chip of prose.
            bypass_role = [None] * len(rows)
            bypass_idx = [None] * len(rows)   # which bypass the row's lane part belongs to
            bypass_dst = [None] * len(rows)   # what the bypass additionally supports
            bypasses = []
            for i, row in enumerate(rows):
                for dst, etype, scheme in row["extras"]:
                    j = index_of[dst]
                    bypasses.append({"src": i, "dst": j, "etype": etype,
                                     "scheme": scheme, "down": j > i})
            for k, bp in enumerate(bypasses):
                lo, hi = min(bp["src"], bp["dst"]), max(bp["src"], bp["dst"])
                bypass_role[bp["src"]] = ("start-down" if bp["down"] else "start-up")
                bypass_role[bp["dst"]] = ("end-down" if bp["down"] else "end-up")
                for end in (bp["src"], bp["dst"]):
                    bypass_idx[end] = k
                    bypass_dst[end] = rows[bp["dst"]]["id"]
                for m in range(lo + 1, hi):
                    if bypass_role[m] is None:
                        bypass_role[m] = "mid"
                        bypass_idx[m] = k

            # One parent->child run has to read as ONE line, and it is drawn by
            # three different rows, so each row states which part of its lane it
            # owns ("up" = row top down to the marker line, "down" = marker line
            # down to the row's bottom edge, "full" = both):
            #   the parent row owns "down" in its OWN column, from its marker to
            #     its bottom edge - without it the run started below the parent;
            #   every row in between owns "full";
            #   each child owns "up" in the parent's column, meeting its elbow -
            #     without it the run stopped short of the last child's elbow.
            # Rows abut exactly (no margins), so the three parts join seamlessly
            # whatever a multi-line label does to the row heights.
            #
            # A child that has a LATER sibling used to own one "full" segment in
            # the parent's column, which is two runs glued together: the top half
            # closes the parent->this-child run, the bottom half carries the
            # parent->next-sibling run onwards. One element cannot belong to one
            # chain and not the other, so a highlighted chain would either stop
            # short or bleed into a sibling's branch. It is therefore emitted as
            # the same two parts every other row already uses - "up" plus "down",
            # which abut at the marker line and draw exactly what "full" drew.
            cont = {}
            meta = []
            for i, row in enumerate(rows):
                d = row["depth"]
                cont[d] = not last[i]
                verticals = [(LANE_X0 + LANE_PITCH * (a - 1), "full")
                             for a in range(1, d) if cont.get(a)]
                if d:
                    verticals.append((LANE_X0 + LANE_PITCH * (d - 1), "up"))
                    if cont[d]:
                        verticals.append((LANE_X0 + LANE_PITCH * (d - 1), "down"))
                if kids.get(i):
                    verticals.append((LANE_X0 + LANE_PITCH * d, "down"))
                meta.append({
                    "row": row, "i": i, "depth": d, "parent": parent[i],
                    "last": last[i], "verticals": verticals,
                    "bypass": bypass_role[i], "bp": bypass_idx[i],
                    "bp_dst": bypass_dst[i],
                    "x": LANE_X0 + LANE_PITCH * d,
                })
            self.lanes[chunk] = {
                "meta": meta, "maxdepth": maxdepth,
                "gutter": 28 + LANE_PITCH * maxdepth + 12,
                "bypasses": bypasses,
            }

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

    # ======================================================================
    # component 1: the chapter minimap
    # ======================================================================

    def _states(self, view):
        """Node and edge ink for one viewpoint. Geometry never changes; only ink.

        `view` is the set of chunks the instance stands in (section 06 stands in
        both of its virtual chunks), or empty for the viewpoint-less overview.
        """
        if not view:
            return {}, {}
        vrank = min(self.rank[c] for c in view)
        deps, uses = set(), set()
        for c in view:
            deps.update(self.builds_on.get(c, []))
            uses.update(self.used_by.get(c, []))
        deps -= view
        uses -= view

        nodes = {}
        for chunk in self.chunks:
            if chunk in view:
                nodes[chunk] = "self"
            elif chunk in deps:
                nodes[chunk] = "dep"
            elif chunk in uses:
                nodes[chunk] = "used"
            elif self.rank[chunk] < vrank:
                nodes[chunk] = "past"
            else:
                nodes[chunk] = "ahead"
        # Every rail chunk supports the roof, so from a rail viewpoint the roof
        # is always "used". From the roof's own viewpoint the rail is genuinely
        # unread, so it stays "ahead" - the reading-progress signal wins over the
        # (true but useless) statement that all eight feed it.
        if self.roof not in view:
            nodes[self.roof] = "used"
        return nodes, {"vrank": vrank, "view": view}

    def _edge_state(self, later, earlier, ctx):
        if not ctx:
            return ""
        if later in ctx["view"] or earlier in ctx["view"]:
            return " sk-live"
        return " sk-epast" if self.rank[later] < ctx["vrank"] else " sk-eahead"

    def minimap_html(self, view, phase, delivered):
        """One instance of the map. `view` is a set of chunks (possibly empty),
        `phase` is "ov" | "pre" | "post", `delivered` counts read sections (0..8).
        """
        node_state, ctx = self._states(view)
        st = lambda c: (" sk-" + node_state[c]) if node_state else ""  # noqa: E731
        out = ["<svg class=\"skel-map sk-%s\" viewBox=\"0 0 %d %d\" "
               "preserveAspectRatio=\"xMidYMid meet\" role=\"img\" "
               "aria-hidden=\"true\" focusable=\"false\">" % (phase, VB_W, VB_H)]
        add = out.append

        # --- arc band (drawn first so the rail sits on top of it) ---
        add('<g class="sk-arcs">')
        for arc in self.arcs:
            live = self._edge_state(arc["a"], arc["b"], ctx)
            width = {1: "1", 2: "1.6"}.get(arc["n"], "2.2")
            head = "sk-head sk-hollow" if arc["deep"] else "sk-head"
            add('<g class="sk-arc%s" data-arc="%s">'
                '<path class="sk-arcline" d="%s" stroke-width="%s"/>'
                '<path class="sk-hit-e sk-hit-a" d="%s"/>'
                '<path class="%s" d="M%s 127 L%s 133 L%s 133 Z"/></g>'
                % (live, arc["key"], arc["d"], width, arc["d"], head,
                   _n(arc["hx"]), _n(arc["hx"] - 2.8), _n(arc["hx"] + 2.8)))
        add("</g>")

        # --- fan gap: eight vertical supports, rail -> roof ---
        add('<g class="sk-fans">')
        for chunk in self.rail:
            cx = _cell_cx(self.rail_index[chunk])
            live = self._edge_state(chunk, self.roof, ctx)
            add('<g class="sk-fan%s" data-fan="%s">'
                '<path class="sk-fanline" d="M%s %d L%s %d"/>'
                '<path class="sk-hit-e" d="M%s %d L%s %d"/>'
                '<path class="sk-head" d="M%s %d L%s %d L%s %d Z"/></g>'
                % (live, chunk, _n(cx), RAIL_T, _n(cx), ROOF_B,
                   _n(cx), RAIL_T, _n(cx), ROOF_B,
                   _n(cx), ROOF_B, _n(cx - 3.6), ROOF_B + 7, _n(cx + 3.6), ROOF_B + 7))
        add("</g>")

        # --- scheme glyphs on the fan ---
        add('<g class="sk-glyphs">')
        for chunk in self.rail:
            scheme = self.fan.get(chunk)
            if not scheme:
                continue
            cx = _cell_cx(self.rail_index[chunk])
            live = self._edge_state(chunk, self.roof, ctx)
            add('<g class="sk-gl%s"><circle class="sk-gl-c" cx="%s" cy="%d" r="%d"/>'
                '<text class="sk-gl-t" x="%s" y="%s">≈</text>'
                '<rect class="sk-hit sk-glyphhit skel-keep" x="%s" y="%s" width="44" '
                'height="44" data-skel-gloss="%s"/></g>'
                % (live, _n(cx), GLYPH_Y, GLYPH_R, _n(cx), _n(GLYPH_Y + 3.6),
                   _n(cx - 22), _n(GLYPH_Y - 22), _esc(scheme)))
        add("</g>")

        # --- forward carries ---
        for carry in self.carries:
            live = self._edge_state(carry["b"], carry["a"], ctx)
            x = carry["x"]
            add('<path class="sk-chev%s" d="M%s 110 L%s 114 L%s 118 Z"/>'
                % (live, _n(x - 3), _n(x + 4), _n(x - 3)))

        # --- roof plate (chunk 00) ---
        prog = ROOF_W * delivered / 8.0
        add('<g class="sk-node sk-roofg%s" data-node="%s">'
            '<rect class="sk-roof" x="%d" y="%d" width="%d" height="%d" rx="5"/>'
            '<rect class="sk-prog" x="%d" y="%d" width="%s" height="%d" rx="5"/>'
            '<text class="sk-id sk-roofid" x="%s" y="%s">%s</text>'
            '<rect class="sk-hit skel-keep" x="%d" y="%s" width="%d" height="%d" '
            'data-skel-node="%s"/></g>'
            % (st(self.roof), _esc(self.roof),
               ROOF_X, ROOF_T, ROOF_W, ROOF_B - ROOF_T,
               ROOF_X, ROOF_T, _n(prog), ROOF_B - ROOF_T,
               _n(ROOF_X + 14), _n(ROOF_T + 16), _esc(self.roof),
               ROOF_X, _n((ROOF_T + ROOF_B) / 2.0 - HIT_H / 2.0), ROOF_W, HIT_H,
               _esc(self.roof)))

        # --- thesis capsule + precaution arrow ---
        done = " sk-done" if (phase == "post" and self.rail[-1] in view) else ""
        cap_state = "dep" if (self.roof in view or done) else "ahead"
        cx = self.cap_cx
        add('<g class="sk-prec%s%s">'
            '<path class="sk-precline" d="M%s %d L%s %d"/>'
            '<path class="sk-head" d="M%s %d L%s %d L%s %d Z"/>'
            '<circle class="sk-gl-c" cx="%s" cy="40" r="%d"/>'
            '<text class="sk-gl-t" x="%s" y="43.6">!</text>'
            '<rect class="sk-hit sk-glyphhit skel-keep" x="%s" y="18" width="44" '
            'height="44" data-skel-gloss="%s"/></g>'
            % (done, self._edge_state(self.roof, self.roof, ctx) if ctx else "",
               _n(cx), ROOF_T - 2, _n(cx), CAP_T + CAP_H + 8,
               _n(cx), CAP_T + CAP_H + 1, _n(cx - 3.6), CAP_T + CAP_H + 8,
               _n(cx + 3.6), CAP_T + CAP_H + 8,
               _n(cx - 23), GLYPH_R, _n(cx - 23), _n(cx - 45),
               _esc((self.thesis_edge or {}).get("scheme") or "precaution")))
        add('<g class="sk-node sk-capg sk-%s" data-node="thesis">'
            '<rect class="sk-cap" x="%s" y="%d" width="%d" height="%d" rx="12"/>'
            '<text class="sk-captext" x="%s" y="%s" data-i18n="thesis-cap">%s</text>'
            '<rect class="sk-hit skel-keep" x="%s" y="%s" width="%d" height="%d" '
            'data-skel-node="thesis"/></g>'
            % (cap_state, _n(cx - CAP_W / 2.0), CAP_T, CAP_W, CAP_H,
               _n(cx), _n(CAP_T + CAP_H / 2.0 + 3.6),
               _esc(UI_STRINGS["hu"]["thesis-cap"]),
               _n(cx - CAP_W / 2.0), _n(CAP_T + CAP_H / 2.0 - HIT_H / 2.0),
               CAP_W, HIT_H, ))

        # --- rail ---
        for chunk in self.rail:
            i = self.rail_index[chunk]
            x, cx = CELL_X0 + PITCH * i, _cell_cx(i)
            solid, dash = self.bars[chunk]
            bar = ('<path class="sk-bar" d="M%s %d L%s %d"/>'
                   % (_n(cx - BAR_W / 2.0), BAR_Y, _n(cx - BAR_W / 2.0 + solid), BAR_Y))
            if dash:
                bar += ('<path class="sk-bar sk-bard" d="M%s %d L%s %d"/>'
                        % (_n(cx - BAR_W / 2.0 + solid), BAR_Y,
                           _n(cx - BAR_W / 2.0 + solid + dash), BAR_Y))
            add('<g class="sk-node%s" data-node="%s">'
                '<rect class="sk-cell" x="%d" y="%d" width="%d" height="%d" rx="4"/>'
                '%s<text class="sk-id" x="%s" y="%s">%s</text>'
                '<rect class="sk-hit skel-keep" x="%d" y="%s" width="%d" height="%d" '
                'data-skel-node="%s"/></g>'
                % (st(chunk), _esc(chunk), x, RAIL_T, CELL_W, CELL_H, bar,
                   _n(cx), _n(RAIL_T + 14), _esc(chunk),
                   x, _n((RAIL_T + RAIL_B) / 2.0 - HIT_H / 2.0), CELL_W, HIT_H,
                   _esc(chunk)))

        add("</svg>")
        return "".join(out)

    def _map_block(self, view, phase, delivered, caption_num, caption_key, extra=""):
        return (
            '<div class="skel-mapwrap" data-view="%s" data-phase="%s">%s'
            '<div class="skel-cap"><span class="skel-cap-num">%s</span>'
            '<span class="skel-cap-txt" data-i18n="%s">%s</span>%s</div></div>'
            % (_esc(" ".join(sorted(view))), phase,
               self.minimap_html(view, phase, delivered),
               _esc(caption_num), caption_key,
               _esc(UI_STRINGS["hu"][caption_key]), extra))

    def overview_html(self):
        legend_btn = ('<button type="button" class="skel-dbtn skel-keep" '
                      'data-skel-legend>mit jelentenek a jelek?</button>')
        return ('<div class="skel-overview" id="skel-overview" data-skel-block hidden>'
                '%s</div>'
                % self._map_block(set(), "ov", 0, "00–07", "overview", legend_btn))

    # ======================================================================
    # page blocks
    # ======================================================================

    def _view_of(self, phys):
        return {c for c in self.chunks if phys_section(c) == phys}

    def pre_html(self, phys):
        """The advance organizer that precedes one physical section."""
        view = self._view_of(phys)
        if not view:
            return ""
        si = self.section_index[phys]
        blocks = []
        for chunk in sorted(view, key=lambda c: self.rank[c]):
            key = self.key_of[chunk]["id"]
            sub = ('<div class="skel-sub">%s</div>' % _esc(chunk)) if len(view) > 1 else ""
            blocks.append('<div class="skel-keyblock" data-skel-chunk="%s">%s'
                          '<p class="skel-key" data-skel-label="%s">%s</p></div>'
                          % (_esc(chunk), sub, _esc(key), _esc(self.label_hu[key])))
        return ('<div class="skel-pre" id="skel-pre-%s" data-skel-block '
                'data-skel-box="%s" hidden><div class="skel-pre-inner">%s%s</div></div>'
                % (_esc(phys), _esc(" ".join(sorted(view))),
                   self._map_block(view, "pre", si, phys, "pre"), "".join(blocks)))

    def post_html(self, phys):
        """The end-of-section consolidation: the close map, then one detail per chunk."""
        view = self._view_of(phys)
        if not view:
            return ""
        si = self.section_index[phys]
        strips = [self._map_block(view, "post", si + 1, phys, "post")]
        for chunk in sorted(view, key=lambda c: self.rank[c]):
            strips.append(self._detail_block(chunk))
        return ('<div class="skel-post" id="skel-post-%s" data-skel-block hidden>'
                '<div class="skel-post-inner">%s</div></div>'
                % (_esc(phys), "".join(strips)))

    # ======================================================================
    # component 2: the chapter detail (lane-based argument graph)
    # ======================================================================

    def _composition(self, chunk):
        """The card's one-line composition. Card chrome, so it follows the label
        pill rather than the (always Hungarian) page chrome."""
        args = [self.d1[chunk], self.lanes[chunk]["maxdepth"] + 1]
        key = "comp"
        if self.interp_count[chunk]:
            key, args = "comp-add", args + [self.interp_count[chunk]]
        return _i18n_span("skel-card-comp", key, args)

    def _thumb_svg(self, chunk):
        """A real thumbnail: the same lane model at 1/4 scale, not a decoration."""
        meta = self.lanes[chunk]["meta"]
        h = THUMB_PAD * 2 + THUMB_PITCH * (len(meta) - 1)
        out = ['<svg class="skel-thumb" viewBox="0 0 %d %d" '
               'preserveAspectRatio="xMinYMid meet" aria-hidden="true" '
               'focusable="false">' % (THUMB_W, h)]

        def px(m):
            return THUMB_PAD + THUMB_LANE * m["depth"]

        def py(m):
            return THUMB_PAD + THUMB_PITCH * m["i"]

        for m in meta:
            if m["parent"] is None:
                continue
            p = meta[m["parent"]]
            out.append('<path class="sk-tline" d="M%s %s L%s %s L%s %s"/>'
                       % (_n(px(m)), _n(py(m)), _n(px(p)), _n(py(m)),
                          _n(px(p)), _n(py(p))))
        for bp in self.lanes[chunk]["bypasses"]:
            s, d = meta[bp["src"]], meta[bp["dst"]]
            out.append('<path class="sk-tline sk-tbypass" d="M%s %s L2 %s L2 %s L%s %s"/>'
                       % (_n(px(s)), _n(py(s)), _n(py(s)), _n(py(d)), _n(px(d)), _n(py(d))))
        for m in meta:
            # the label column, as a rule: without it the thumbnail is a stack of
            # dots in the left 30px and reads as decoration rather than as rows
            out.append('<path class="sk-tlabel" d="M%s %s L%d %s"/>'
                       % (_n(px(m) + 5), _n(py(m)), THUMB_W - 4, _n(py(m))))
        for m in meta:
            node = self.by_id[m["row"]["id"]]
            if m["i"] == 0:
                out.append('<circle class="sk-tkey" cx="%s" cy="%s" r="2.4"/>'
                           % (_n(px(m)), _n(py(m))))
            elif node.get("interpolated") is True:
                out.append('<path class="sk-tinterp" d="M%s %s l2.4 2.4 l-2.4 2.4 '
                           'l-2.4 -2.4 Z"/>' % (_n(px(m)), _n(py(m) - 2.4)))
            else:
                out.append('<circle class="sk-tdot" cx="%s" cy="%s" r="1.5"/>'
                           % (_n(px(m)), _n(py(m))))
        out.append("</svg>")
        return "".join(out)

    def _head_svg(self, chunk, m):
        """The fixed-height head layer of one row: elbow, terminal, marker, diamond."""
        gut = self.lanes[chunk]["gutter"]
        etype = m["row"]["etype"] or "supports"
        x, d = m["x"], m["depth"]
        out = ['<svg class="skel-lhead" viewBox="0 0 %d %d" width="%d" height="%d" '
               'aria-hidden="true" focusable="false">' % (gut, HEAD_H, gut, HEAD_H)]

        if d:
            lane_x = LANE_X0 + LANE_PITCH * (d - 1)
            out.append('<path class="sk-ed sk-ed-%s" d="M%s %d L%s %d L%s 6"/>'
                       % (etype, _n(x), MARK_Y, _n(lane_x), MARK_Y, _n(lane_x)))
            if etype == "rebuts":
                # inhibitory-synapse idiom: a crossbar, not an arrowhead
                out.append('<path class="sk-term sk-term-bar" d="M%s 5 L%s 5"/>'
                           % (_n(lane_x - 4.5), _n(lane_x + 4.5)))
            else:
                out.append('<path class="sk-term sk-term-%s" d="M%s 3 L%s 8 L%s 8 Z"/>'
                           % (etype, _n(lane_x), _n(lane_x - 2.5), _n(lane_x + 2.5)))

        # The bypass keeps its own ink vocabulary (sk-*-bypass) so it can be held
        # faint by default and lit as one whole edge - across all three of the
        # rows that draw parts of it - when an endpoint row goes live. It also
        # keeps its own BAND: it runs BYPASS_DY below the elbow line and turns
        # into the marker from lower-left, so it crosses no other edge and hides
        # no other sign. Its arrowhead is the same shape the tree's terminals
        # use, which is what makes "this arrow lands on that claim" readable.
        role, bp = m["bypass"], m["bp"]
        turn = x - BYPASS_TURN
        if role and role.startswith("start"):
            out.append('<path class="sk-ed sk-ed-bypass" data-bp="%d" '
                       'd="M%s %d L%s %d L%d %d"/>'
                       % (bp, _n(x), MARK_Y, _n(turn), BYPASS_Y, BYPASS_X, BYPASS_Y))
        elif role and role.startswith("end"):
            out.append('<path class="sk-ed sk-ed-bypass" data-bp="%d" d="M%d %d L%s %d"/>'
                       % (bp, BYPASS_X, BYPASS_Y, _n(turn), BYPASS_Y))
            # the same 5x5 up-arrow the tree's terminals use, so "this edge
            # lands on this claim" reads the same way everywhere
            out.append('<path class="sk-term sk-term-bypass" data-bp="%d" '
                       'd="M%s %d L%s %d L%s %d Z"/>'
                       % (bp, _n(turn), BYPASS_Y - 5, _n(turn - 2.5), BYPASS_Y,
                          _n(turn + 2.5), BYPASS_Y))

        if m["row"]["scheme"] and d:
            dx = LANE_X0 + LANE_PITCH * (d - 1) + LANE_PITCH / 2.0
            out.append('<path class="sk-scheme" d="M%s %s l5 5 l-5 5 l-5 -5 Z"/>'
                       % (_n(dx), MARK_Y - 5))

        out.append(marker_ink(self._mark_kind(m), x, MARK_Y))
        out.append("</svg>")
        return "".join(out)

    def _quote_btn(self, nid):
        anchors = self.anchor_index.get(nid, [])
        if not anchors:
            return ""
        usable = [a for a in anchors if a["ok"]]
        disabled = "" if usable else " disabled"
        title = "Ugrás a mondatra" if usable else "A mondat nem található a szövegben"
        count = ('<span class="skel-qn">%d</span>' % len(anchors)) if len(anchors) > 1 else ""
        return ('<button type="button" class="skel-quote skel-keep" data-skel-quote="%s" '
                'title="%s" aria-label="%s"%s>❝%s</button>'
                % (_esc(nid), _esc(title), _esc(title), disabled, count))

    def _mark_kind(self, m):
        """Which of the four marker kinds this row draws.

        Single source of truth: _head_svg() draws through marker_ink() with this
        kind, the gloss picks its sentence from it, and the gloss card's sign is
        marker_ink() again. A row cannot draw one glyph and explain another.
        """
        nid = m["row"]["id"]
        if m["i"] == 0:
            return "key"
        if self.by_id[nid].get("interpolated") is True:
            return "interp"
        if self.footnote_only(nid):
            return "fn"
        return "anchored"

    def _mark_gloss(self, m):
        """The row's marker gloss, as a key plus its positional arguments."""
        kind = self._mark_kind(m)
        if kind != "anchored":
            return "mg-" + kind, []
        count = len(self.anchor_index.get(m["row"]["id"], []))
        return ("mg-anchored-n", [count]) if count > 1 else ("mg-anchored", [])

    def _lane_rows_html(self, chunk):
        lane = self.lanes[chunk]
        out = []
        for m in lane["meta"]:
            nid = m["row"]["id"]
            node = self.by_id[nid]
            classes = ["skel-lrow", "sk-e-" + (m["row"]["etype"] or "root")]
            if node.get("interpolated") is True:
                classes.append("sk-interp")
            # The kind travels in the class, and the column in the inline `left`
            # the segment already needed; the page JS reads both back to light
            # one chain's lane parts without a byte of extra markup.
            verticals = "".join(
                '<i class="skel-lane%s" style="left:%dpx"></i>'
                % ("" if kind == "full" else " sk-l-" + kind, x)
                for x, kind in m["verticals"])
            role, bp = m["bypass"], m["bp"]
            bpx = ""
            if role:
                cls = {"start-down": "sk-bp-down", "end-up": "sk-bp-down",
                       "start-up": "sk-bp-up", "end-down": "sk-bp-up",
                       "mid": "sk-bp-mid"}[role]
                verticals += ('<i class="skel-lane %s" data-bp="%d" style="left:%dpx"></i>'
                              % (cls, bp, BYPASS_X))
                if role != "mid":
                    # A gloss target over the stub that leaves the marker, on
                    # both endpoint rows: a dashed line into the far left gutter
                    # says nothing on its own about what it feeds. It spans the
                    # gutter lane through to just past the arrowhead at
                    # x - BYPASS_TURN, so every pixel of the stub answers.
                    bpx = ('<button type="button" class="skel-bpx skel-keep" '
                           'data-skel-bp="%s" style="left:%dpx;width:%dpx" '
                           'aria-label="%s"></button>'
                           % (_esc(m["bp_dst"]), BYPASS_X - 11,
                              max(24, m["x"] - BYPASS_TURN + 15 - BYPASS_X),
                              _esc(_fmt(UI_STRINGS["hu"]["bp-also"],
                                        [shorten(self.label_hu[m["bp_dst"]], 74)]))))
            gkey, gargs = self._mark_gloss(m)
            out.append(
                '<div class="%s" data-row="%d" data-depth="%d" data-parent="%s" '
                'data-node="%s"%s>'
                '<button type="button" class="skel-mark skel-keep" data-skel-mg="%s"%s '
                'style="left:%dpx" aria-label="%s"></button>'
                '%s%s%s%s'
                '<span class="skel-llabel" data-skel-label="%s">%s</span>%s</div>'
                % (" ".join(classes), m["i"], m["depth"],
                   "" if m["parent"] is None else m["parent"], _esc(nid),
                   "" if (role in (None, "mid")) else ' data-bpend="%d"' % bp,
                   _esc(gkey),
                   (' data-i18n-args="%s"' % _esc("|".join(str(a) for a in gargs)))
                   if gargs else "",
                   m["x"] - 13,
                   _esc(_fmt(UI_STRINGS["hu"][gkey], gargs)),
                   self._scheme_hit(chunk, m), bpx, verticals,
                   self._head_svg(chunk, m),
                   _esc(nid), _esc(self.label_hu[nid]), self._quote_btn(nid)))
        return "".join(out)

    def _scheme_hit(self, chunk, m):
        if not (m["row"]["scheme"] and m["depth"]):
            return ""
        dx = LANE_X0 + LANE_PITCH * (m["depth"] - 1) + LANE_PITCH / 2.0
        return ('<button type="button" class="skel-dia skel-keep" data-skel-gloss="%s" '
                'style="left:%spx" aria-label="%s"></button>'
                % (_esc(m["row"]["scheme"]), _n(dx - 11),
                   _esc(UI_STRINGS["hu"].get("sch-" + m["row"]["scheme"],
                                             m["row"]["scheme"]))))

    # ---- v1 nested list, kept as the below-700px fallback ----------------

    def _list_row_html(self, row):
        nid = row["id"]
        node = self.by_id[nid]
        classes = ["skel-row"]
        if row["etype"]:
            classes.append("skel-e-" + row["etype"])
        if node.get("interpolated") is True:
            classes.append("skel-interp")
        bits = ['<span class="skel-label" data-skel-label="%s">%s</span>'
                % (_esc(nid), _esc(self.label_hu[nid]))]
        bits.append(self._quote_btn(nid))
        if self.footnote_only(nid):
            fns = sorted({a["fn"] for a in self.anchor_index.get(nid, [])
                          if a["fn"] is not None})
            bits.append('<span class="skel-chip skel-fn">lábjegyzet [%s]</span>'
                        % _esc(", ".join(str(n) for n in fns)))
        if node.get("interpolated") is True:
            bits.append('<span class="skel-chip skel-add">kiegészítés — a szöveg '
                        'ezt nem mondja ki</span>')
        for dst, _etype, _scheme in row["extras"]:
            gloss = _fmt(UI_STRINGS["hu"]["bp-also"],
                         [shorten(self.label_hu[dst], 74)])
            bits.append('<button type="button" class="skel-also skel-keep" '
                        'data-skel-bp="%s" title="%s" aria-label="%s">↗</button>'
                        % (_esc(dst), _esc(gloss), _esc(gloss)))
        return '<li class="%s">%s' % (" ".join(classes), "".join(bits))

    def _tree_html(self, chunk):
        """Nested <ul>/<li> from the pre-ordered rows; nesting reads '...because'."""
        out, prev = [], -1
        for row in self.rows[chunk]:
            depth = row["depth"]
            if depth > prev:
                out.append('<ul class="skel-tree-list">')
            else:
                out.append("</li>")
                while prev > depth:
                    out.append("</ul></li>")
                    prev -= 1
            out.append(self._list_row_html(row))
            prev = depth
        out.append("</li>")
        while prev > 0:
            out.append("</ul></li>")
            prev -= 1
        out.append("</ul>")
        return "".join(out)

    def _detail_block(self, chunk):
        key = self.key_of[chunk]["id"]
        lane = self.lanes[chunk]
        helper = ('<p class="skel-helper">Mi támaszt mit alá ebben a szakaszban.</p>'
                  if chunk == self.roof else "")
        return (
            '<div class="skel-strip" data-skel-chunk="%s">'
            '<p class="skel-restate"><span class="skel-post-num">%s</span>'
            '<span data-skel-label="%s">%s</span></p>%s'
            '<button type="button" class="skel-card skel-keep" data-skel-card="%s" '
            'aria-expanded="false" aria-controls="skel-detail-%s">'
            '<span class="skel-card-tag" data-i18n="graphtag">%s</span>'
            '<span class="skel-card-body">%s'
            '<span class="skel-card-txt">%s'
            '<span class="skel-card-key" data-skel-short="%s" data-skel-len="110">%s</span>'
            '</span></span></button>'
            '<div class="skel-detail" id="skel-detail-%s" data-chunk="%s" hidden>'
            '<div class="skel-dhead">'
            '<span class="skel-zoom" role="group" aria-label="Nagyítás">'
            '<button type="button" class="skel-keep on" data-skel-zoom="full">teljes szöveg</button>'
            '<button type="button" class="skel-keep" data-skel-zoom="bones">csak a váz</button>'
            '</span>'
            '<button type="button" class="skel-dbtn skel-keep" data-skel-legend>'
            'mit jelentenek a jelek?</button>'
            '<button type="button" class="skel-dbtn skel-keep" data-skel-collapse '
            'aria-label="Bezárás" title="Bezárás">×</button></div>'
            '<div class="skel-lanes" style="--sk-gut:%dpx">%s</div>'
            '<div class="skel-list">%s</div>'
            '</div></div>'
            % (_esc(chunk), _esc(chunk), _esc(key), _esc(self.label_hu[key]), helper,
               _esc(chunk), _esc(chunk), _esc(UI_STRINGS["hu"]["graphtag"]),
               self._thumb_svg(chunk), self._composition(chunk),
               _esc(key), _esc(shorten(self.label_hu[key], 110)),
               _esc(chunk), _esc(chunk),
               lane["gutter"], self._lane_rows_html(chunk), self._tree_html(chunk)))

    # ======================================================================
    # legend + payload
    # ======================================================================

    def legend_html(self):
        interp = sum(1 for n in self.by_id.values() if n.get("interpolated") is True)
        return (
            '<div class="skel-legend" id="skel-legend" role="dialog" '
            'aria-label="Jelmagyarázat" hidden>'
            '<button type="button" class="skel-legend-x skel-keep" id="skel-legend-x" '
            'aria-label="Bezárás" title="Bezárás">×</button>'
            '<h4>A térkép</h4><ul>'
            '<li>A sáv nyolc doboza a nyolc gondolategység, olvasási sorrendben. '
            'A 06-os szakasz két egységre esik szét (06a, 06b).</li>'
            '<li>A fölöttük fekvő teljes szélességű lap a leíró gerinc (00): mind a '
            'nyolc egység ezt támasztja alá. A lap kitöltése azt mutatja, hol tartasz.</li>'
            '<li>Legfelül a tézis. A hozzá vezető nyíl <b>!</b> jele: ez a lépés '
            'értékítélet, nem bizonyítás — a lap végéig halvány marad.</li>'
            '<li>A dobozok alatti pontozott ívek: „ez az egység feltételezi amazt”. '
            'A nyílhegy a <i>korábbi</i> egységre mutat; vastagabb ív = több '
            'hivatkozás; üres nyílhegy = nem a fejezet fő állítására hivatkozik, '
            'hanem egy alállítására.</li>'
            '<li><b>≈</b> = a lépés analógián nyugszik. Rákoppintva megmondja, mit jelent.</li>'
            '<li>Üres karika = még el nem olvasott egység, tele karika = már elolvasott. '
            '<b>►</b> = az érvelés előre visz egy szálat.</li>'
            '<li>A doboz alján a vonalka az egység terhelése: hány állítást kell '
            'egyszerre fejben tartani. A szaggatott vég a kiegészítés.</li>'
            '</ul><h4>Az ábra</h4><ul>'
            '<li>A nyíl arra mutat, amit a farka tart.</li>'
            '<li>Folytonos vonal = alátámasztja · halvány vékony = kifejti · '
            'szaggatott = szűkíti · vastag szaggatott, kereszttel a végén = cáfolja.</li>'
            '<li><b>⬤</b> a szakasz kulcsállítása · <b>●</b> a szövegből vett állítás · '
            '<b>◇</b> kiegészítés: a térkép %d állításából %d-et a feltérképezés tett '
            'hozzá, a szöveg ezeket nem mondja ki.</li>'
            '<li>Vízszintes vonalka a pont alatt = a szöveg ezt csak lábjegyzetben mondja ki.</li>'
            '<li>Gyémánt az élen = megnevezett következtetési séma; rákoppintva megmondja, melyik.</li>'
            '<li><span class="skel-legend-q">❝</span> = ugrás a pontos mondatra az '
            'angol szövegben. Ha a jel mellett szám áll, az állítás több mondaton '
            'nyugszik: újra rákoppintva a következőre lép, és a kiemeléstörlő sáv '
            'megmutatja, hányadiknál tartasz.</li>'
            '</ul></div>' % (len(self.by_id), interp))

    def json_blob(self):
        chunks = {}
        for chunk in self.chunks:
            chunks[chunk] = {
                "sec": self.section_index[phys_section(chunk)],
                "box": "skel-pre-%s" % phys_section(chunk),
                "post": "skel-post-%s" % phys_section(chunk),
                "key": self.key_of[chunk]["id"],
                "d1": self.d1[chunk],
                "scheme": self.fan.get(chunk),
                "up": self.builds_on[chunk],
                "down": self.used_by[chunk],
            }
        nodes = {}
        for nid, node in self.by_id.items():
            nodes[nid] = {"chunk": node.get("section"), "lvl": node.get("level")}
        parent = {}
        for chunk in self.chunks:
            meta = self.lanes[chunk]["meta"]
            for m in meta:
                if m["parent"] is not None:
                    parent[m["row"]["id"]] = meta[m["parent"]]["row"]["id"]
        arcs = {a["key"]: {"a": a["a"], "b": a["b"], "edges": a["edges"]}
                for a in self.arcs}
        for carry in self.carries:
            arcs["%s>%s" % (carry["a"], carry["b"])] = {
                "a": carry["a"], "b": carry["b"], "edges": carry["edges"]}
        fans = {}
        for src, dst, etype, _scheme in self.cross_edges:
            if dst == self.backbone_id and etype == "supports":
                fans[self._chunk_of(src)] = [[src, dst]]
        data = {
            "order": self.chunks,
            "roof": self.roof,
            "chunks": chunks,
            "nodes": nodes,
            "parent": parent,
            "anchors": self.anchor_index,
            "arcs": arcs,
            "fans": fans,
            "labels": {"en": self.label_en, "hu": self.label_hu},
            "ui": UI_STRINGS,
            # The lane grid, so the JS can name a run's column from a row's depth
            # instead of re-deriving the geometry it was handed.
            "lane": [LANE_X0, LANE_PITCH],
            # Each gloss carries the sign it explains, drawn by the same code
            # that draws the row - see marker_ink().
            "signs": SIGNS,
            "thesis": {"id": self.thesis["id"],
                       "scheme": (self.thesis_edge or {}).get("scheme")},
        }
        return json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def load_view(section_index, path=SKELETON_PATH, labels_path=LABELS_HU_PATH):
    try:
        doc = load(path)
    except (ParseError, OSError) as exc:
        raise SkeletonError("%s: %s" % (os.path.relpath(path, _REPO), exc))
    try:
        overlay = load(labels_path)
    except (ParseError, OSError) as exc:
        raise SkeletonError("%s: %s" % (os.path.relpath(labels_path, _REPO), exc))
    return SkeletonView(doc, (overlay or {}).get("labels"), section_index)


# --------------------------------------------------------------------------
# CSS / JS, passed to the page template as format arguments (single braces)
# --------------------------------------------------------------------------

SKEL_CSS = r"""
/* --- ervvaz (argument skeleton) v2 -------------------------------------- */
/* Lengths only; every colour is an existing var or a color-mix over one.    */
/* On dark, a bare --rule hairline disappears, so every hairline that has to */
/* stay visible is mixed toward --muted.                                     */
:root{
  --sk-line:color-mix(in srgb,var(--rule) 55%,var(--muted));
  --sk-mark:14px;
  --sk-bpy:26px;   /* the bypass's own band; mirrors BYPASS_Y in the builder */
}
.skel-overview,.skel-pre,.skel-post,.skel-legend{
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}

/* ---------- the map ---------- */
.skel-mapwrap{margin:0 0 14px}
svg.skel-map{display:block;width:100%;height:auto;overflow:visible}
.skel-cap{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin-top:2px;
  font-size:12.5px;color:var(--muted)}
.skel-cap-num{font-family:ui-monospace,Menlo,monospace;letter-spacing:.1em}
.skel-cap-num::after{content:'·';margin-left:8px;opacity:.6}
/* rail + roof + capsule */
.sk-cell,.sk-roof,.sk-cap{fill:var(--card-bg);stroke:var(--sk-line);stroke-width:1}
.sk-cap{stroke-width:1;paint-order:stroke}
.sk-capg .sk-cap{stroke-dasharray:none}
.sk-id{font-family:ui-monospace,Menlo,monospace;font-size:11px;letter-spacing:.06em;
  fill:var(--muted);text-anchor:middle}
.sk-roofid{text-anchor:start}
.sk-captext{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  font-size:10px;font-weight:700;letter-spacing:.14em;fill:var(--muted);text-anchor:middle}
.sk-prog{fill:color-mix(in srgb,var(--accent) 16%,transparent);stroke:none}
.sk-bar{stroke:color-mix(in srgb,var(--muted) 70%,transparent);stroke-width:2;fill:none}
.sk-bard{stroke-dasharray:2 2}
/* node states: ink only, geometry never moves */
.sk-node.sk-self .sk-cell,.sk-node.sk-self .sk-roof{stroke:var(--accent);stroke-width:1.6}
.sk-pre .sk-node.sk-self .sk-cell,.sk-pre .sk-node.sk-self .sk-roof{fill:var(--bg)}
.sk-post .sk-node.sk-self .sk-cell,.sk-post .sk-node.sk-self .sk-roof{fill:var(--accent)}
.sk-post .sk-node.sk-self .sk-id{fill:var(--bg)}
.sk-post .sk-node.sk-self .sk-bar{stroke:color-mix(in srgb,var(--bg) 75%,transparent)}
.sk-node.sk-dep .sk-cell,.sk-node.sk-dep .sk-roof,.sk-node.sk-dep .sk-cap{
  stroke:var(--accent);fill:color-mix(in srgb,var(--accent) 12%,var(--bg))}
.sk-node.sk-dep .sk-id,.sk-node.sk-dep .sk-captext{fill:var(--accent)}
.sk-node.sk-used .sk-cell,.sk-node.sk-used .sk-roof{
  stroke:color-mix(in srgb,var(--accent) 50%,var(--rule));stroke-dasharray:3 2}
.sk-node.sk-past .sk-cell,.sk-node.sk-past .sk-roof{fill:var(--card-bg)}
.sk-node.sk-ahead{opacity:.45}
/* edges */
.sk-arcline{fill:none;stroke:var(--sk-line);stroke-dasharray:1.5 2.5;stroke-linecap:round}
.sk-fanline,.sk-precline{fill:none;stroke:var(--sk-line);stroke-width:1}
.sk-precline{stroke-dasharray:3 3;stroke:color-mix(in srgb,var(--note) 40%,transparent)}
.sk-prec.sk-done .sk-precline{stroke-dasharray:none;stroke:var(--note)}
.sk-prec.sk-done .sk-head{fill:var(--note);stroke:none}
.sk-head{fill:var(--sk-line);stroke:none}
.sk-head.sk-hollow{fill:var(--bg);stroke:var(--sk-line);stroke-width:1}
.sk-chev{fill:color-mix(in srgb,var(--muted) 55%,transparent)}
.sk-gl-c{fill:var(--bg);stroke:var(--sk-line);stroke-width:1}
.sk-gl-t{font-size:10px;fill:var(--muted);text-anchor:middle;
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
.sk-arc.sk-live .sk-arcline,.sk-fan.sk-live .sk-fanline{stroke:var(--accent);stroke-width:1.4}
.sk-arc.sk-live .sk-head,.sk-fan.sk-live .sk-head{fill:var(--accent)}
.sk-arc.sk-live .sk-head.sk-hollow{fill:var(--bg);stroke:var(--accent)}
.sk-gl.sk-live .sk-gl-c{stroke:var(--accent)}
.sk-gl.sk-live .sk-gl-t{fill:var(--accent)}
.sk-chev.sk-live{fill:var(--accent)}
/* transient lighting: the edges incident to the node whose card is open */
svg.skel-map .sk-hot .sk-arcline,svg.skel-map .sk-hot .sk-fanline{
  stroke:var(--accent);stroke-width:1.6}
svg.skel-map .sk-hot .sk-head{fill:var(--accent)}
svg.skel-map .sk-hot .sk-head.sk-hollow{fill:var(--bg);stroke:var(--accent)}
svg.skel-map .sk-hot{opacity:1}
.sk-arc.sk-epast,.sk-fan.sk-epast{opacity:.7}
.sk-arc.sk-eahead,.sk-fan.sk-eahead,.sk-chev.sk-eahead{opacity:.35}
/* hit areas.
   Cursor rule, page-wide: an affordance that only EXPLAINS gets `help` - the
   precedent is a.src, the source links, which have used it since v1 for "hover
   tells you what this is". An affordance that NAVIGATES or changes state gets
   `pointer`. So the node cells and the capsule (a click travels to them) are
   pointer, while the scheme glyphs sharing the same .sk-hit class only ever
   open a gloss and are overridden below. */
.sk-hit{fill:transparent;stroke:none;cursor:pointer}
.sk-hit.sk-glyphhit{cursor:help}
.sk-hit-e{fill:none;stroke:transparent;stroke-width:14;pointer-events:none}
/* Arcs nest 13.2 units apart, so their hit stroke has to stay under that or
   two neighbouring nesting levels would share one hover target. */
.sk-hit-a{stroke-width:11}
svg.skel-map .sk-arc:hover .sk-arcline,svg.skel-map .sk-fan:hover .sk-fanline{
  stroke:var(--accent)}
@media (hover:hover) and (pointer:fine){
  .sk-hit-e{pointer-events:stroke;cursor:help}
}
@media (max-width:559px){
  .sk-id{font-size:17px}
  .sk-captext{font-size:15px;letter-spacing:.06em}
  .sk-gl-t{font-size:15px}
  .sk-glyphhit{display:none}
  svg.skel-map .sk-arc:not(.sk-live){display:none}
  svg.skel-map.sk-ov .sk-arcs{display:none}
}

/* ---------- pre box ---------- */
.skel-pre{margin:34px 0 0}
.skel-pre-inner{border-left:3px solid color-mix(in srgb,var(--accent) 55%,var(--rule));
  padding:14px 18px 14px 17px;background:color-mix(in srgb,var(--accent) 4%,var(--bg));
  border-radius:0 8px 8px 0}
.skel-keyblock + .skel-keyblock{margin-top:14px;padding-top:14px;
  border-top:1px dotted var(--rule)}
.skel-sub{font-family:ui-monospace,Menlo,monospace;font-size:11px;color:var(--muted);
  margin-bottom:3px}
.skel-key{margin:0;font-size:16px;line-height:1.45;font-weight:600}
.skel-overview{max-width:820px;margin:22px auto 0;padding:0 24px}

/* ---------- post block ---------- */
.skel-post{margin:0 0 6px;padding-top:18px}
.skel-post-inner{border-top:1px solid var(--rule);padding-top:14px}
.skel-strip + .skel-strip{margin-top:20px}
.skel-restate{margin:0 0 12px;font-size:14.5px;line-height:1.5;color:var(--muted)}
.skel-post-num{font-family:ui-monospace,Menlo,monospace;font-size:12px;letter-spacing:.1em;
  color:var(--muted);margin-right:10px}
.skel-helper{margin:0 0 10px;font-size:13px;color:var(--muted);font-style:italic}
/* collapsed card = a real thumbnail of the same graph */
.skel-card{display:block;width:100%;min-height:44px;text-align:left;cursor:pointer;
  border:1px solid var(--rule);border-left:3px solid var(--accent);border-radius:0 8px 8px 0;
  background:var(--card-bg);color:var(--fg);padding:12px 16px;font-family:inherit}
/* display:block above would beat the UA [hidden] rule, so restate it */
.skel-card[hidden]{display:none}
.skel-card:hover{border-color:color-mix(in srgb,var(--accent) 50%,var(--rule));
  border-left-color:var(--accent)}
.skel-card-tag{display:block;font-size:10.5px;font-weight:700;text-transform:uppercase;
  letter-spacing:.11em;color:var(--muted);margin-bottom:8px}
.skel-card-body{display:flex;align-items:flex-start;gap:16px}
svg.skel-thumb{flex:0 0 auto;width:124px;height:auto;max-height:86px}
.sk-tline{fill:none;stroke:var(--sk-line);stroke-width:.7}
.sk-tbypass{stroke-dasharray:1.5 1.5}
.sk-tlabel{stroke:color-mix(in srgb,var(--muted) 26%,transparent);stroke-width:1.6}
.sk-tdot{fill:color-mix(in srgb,var(--muted) 70%,transparent)}
.sk-tkey{fill:var(--accent)}
.sk-tinterp{fill:var(--bg);stroke:var(--muted);stroke-width:.7;stroke-dasharray:1.2 1.2}
.skel-card-txt{flex:1 1 auto;min-width:0}
.skel-card-comp{display:block;font-family:ui-monospace,Menlo,monospace;font-size:11.5px;
  color:var(--muted);margin-bottom:6px}
.skel-card-key{display:block;font-size:14px;line-height:1.45;color:var(--fg)}
/* detail header */
.skel-detail{border:1px solid var(--rule);border-left:3px solid var(--accent);
  border-radius:0 8px 8px 0;padding:10px 14px 14px;margin-top:0}
.skel-dhead{display:flex;flex-wrap:wrap;align-items:center;gap:10px;margin-bottom:12px}
.skel-zoom{display:inline-flex;border:1px solid var(--rule);border-radius:20px;overflow:hidden}
.skel-zoom button{border:0;background:transparent;color:var(--muted);min-height:36px;
  padding:6px 14px;font-size:12.5px;cursor:pointer;font-family:inherit}
.skel-zoom button.on{background:var(--accent);color:var(--bg)}
.skel-dbtn{min-height:36px;padding:6px 14px;border:1px solid var(--rule);border-radius:20px;
  background:var(--card-bg);color:var(--muted);font-size:12.5px;cursor:pointer;
  font-family:inherit}
.skel-dbtn:hover{color:var(--fg);border-color:color-mix(in srgb,var(--accent) 50%,var(--rule))}
.skel-dhead [data-skel-collapse]{margin-left:auto;min-width:40px;font-size:17px;line-height:1}

/* ---------- lanes (>=700px) ---------- */
.skel-lanes{display:none}
@media (min-width:700px){
  .skel-lanes{display:block}
  .skel-detail .skel-list{display:none}
}
/* the zoom pill only governs the lane view, so it goes with it */
@media (max-width:699px){ .skel-zoom{display:none} }
.skel-lrow{position:relative;display:grid;grid-template-columns:var(--sk-gut) 1fr 44px;
  align-items:start;min-height:40px;font-size:14.5px;line-height:1.5}
.skel-llabel{grid-column:2;padding:3px 8px 3px 0}
.skel-lrow .skel-quote{grid-column:3}
/* Width and offset mirror the SVG elbow's stroke-width:1.5 centred on the lane
   axis, so the CSS vertical and the elbow it joins are the same line. */
.skel-lane{position:absolute;top:0;bottom:0;width:1.5px;margin-left:-.75px;
  background:var(--sk-line);pointer-events:none}
/* the three parts of one parent->child run; see _derive_lanes() */
.skel-lane.sk-l-up{bottom:auto;height:var(--sk-mark)}
.skel-lane.sk-l-down{top:var(--sk-mark)}
/* The gutter lane meets the stub in the bypass's band, not on the elbow line. */
.skel-lane.sk-bp-down{top:var(--sk-bpy);bottom:0}
.skel-lane.sk-bp-up{top:0;height:var(--sk-bpy)}
.skel-lane.sk-bp-mid{top:0;bottom:0}
.skel-lane.sk-bp-down,.skel-lane.sk-bp-up,.skel-lane.sk-bp-mid{
  background:repeating-linear-gradient(to bottom,var(--sk-line) 0 2px,transparent 2px 4px)}
/* A second parent is a real edge but never the reading order's spine: at full
   strength it competes with the tree for the eye on every row it crosses. It
   stays faint until one of its two endpoint rows is the live one, and then it
   lights along its whole length - the three rows that draw its parts all carry
   the same data-bp. */
.sk-ed-bypass,.sk-term-bypass,.skel-lane.sk-bp-down,.skel-lane.sk-bp-up,
.skel-lane.sk-bp-mid{opacity:.3}
.sk-ed-bypass.sk-bp-on{opacity:1;stroke:var(--accent)}
.sk-term-bypass.sk-bp-on{opacity:1;fill:var(--accent)}
.skel-lane.sk-bp-on{opacity:1;
  background:repeating-linear-gradient(to bottom,var(--accent) 0 2px,transparent 2px 4px)}
/* Confined to the bypass's own band, where no other glyph reaches - so it can
   sit ON TOP without ever stealing a pixel that belongs to the marker or the
   diamond, and the stub answers for its whole length. */
.skel-bpx{position:absolute;top:calc(var(--sk-bpy) - 7px);height:20px;border:0;
  background:transparent;padding:0;cursor:help;z-index:4;border-radius:6px}
svg.skel-lhead{position:absolute;left:0;top:0;pointer-events:none;overflow:visible}
.sk-ed{fill:none;stroke:var(--sk-line);stroke-width:1.5}
.sk-ed-elaborates{stroke-width:1;opacity:.35}
.sk-ed-qualifies{stroke-dasharray:5 3;stroke:color-mix(in srgb,var(--note) 55%,var(--rule))}
.sk-ed-rebuts{stroke-width:2;stroke-dasharray:4 3;stroke:var(--note)}
.sk-ed-bypass{stroke-dasharray:2 2}
.sk-term{fill:var(--sk-line);stroke:none}
.sk-term-elaborates{opacity:.35}
.sk-term-qualifies{fill:color-mix(in srgb,var(--note) 55%,var(--rule))}
.sk-term-bar{fill:none;stroke:var(--note);stroke-width:2}
.sk-scheme{fill:var(--bg);stroke:var(--accent);stroke-width:1.2}
.sk-mdot{fill:color-mix(in srgb,var(--muted) 70%,transparent)}
.sk-mkey{fill:var(--accent)}
.sk-mkey-ring{fill:none;stroke:var(--accent);stroke-width:2;opacity:.45}
.sk-minterp{fill:var(--bg);stroke:var(--muted);stroke-width:1.5;stroke-dasharray:2.5 2}
.sk-mfn{stroke:var(--muted);stroke-width:1.4}
/* Three affordances share this strip of row, and which one answers must follow
   from WHICH VISUAL the pointer is on, not from paint order. So they stack
   smallest-and-innermost first - diamond over marker over bypass stub - and the
   diamond's box stops dead at x-8, the left edge of the marker's widest glyph
   (the key ring). Before this the marker's 26px box started at the diamond's
   CENTRE and the stub's box ran under all of it, so the diamond's own pixels
   answered with the marker's gloss on the right half and the bypass's on the
   left, and its own gloss was only reachable in a 6px strip beside it. */
/* `help`, not `pointer`: since v2.2 the marker's whole job is to explain its own
   glyph - the card it used to open is gone. Row highlighting rides along, but
   it is not what the reader is being offered. */
.skel-mark{position:absolute;top:calc(var(--sk-mark) - 15px);width:26px;height:30px;
  border:0;background:transparent;padding:0;cursor:help;z-index:2;border-radius:6px}
.skel-mark:focus-visible{outline:2px solid var(--accent);outline-offset:0}
/* 17px, not 16: the box is left-edge inclusive and right-edge exclusive, so 16
   would leave the diamond's own right vertex (and its 1.2px stroke) to the
   marker. It still stops 2.5px short of the dot, and a key row - the only
   marker wider than the dot - never carries a diamond. */
.skel-dia{position:absolute;top:calc(var(--sk-mark) - 13px);width:17px;height:26px;
  border:0;background:transparent;padding:0;cursor:help;z-index:3;border-radius:6px}
.skel-dia:focus-visible,.skel-bpx:focus-visible{outline:2px solid var(--accent)}
.skel-lanes.sk-bones .skel-llabel{display:-webkit-box;-webkit-line-clamp:1;
  line-clamp:1;-webkit-box-orient:vertical;overflow:hidden}
.skel-lanes.sk-bones .skel-lrow{min-height:40px}
/* row highlight (sticky; dismissed by a second tap, Esc, or the clear bar) */
.skel-lrow.sk-r-self{background:color-mix(in srgb,var(--accent) 10%,transparent);
  border-radius:6px}
.skel-lrow.sk-r-desc{background:color-mix(in srgb,var(--accent) 4%,transparent)}
/* The bypass is excluded here: its whole point is that it stays quiet unless it
   is the edge being asked about, and sk-bp-on is what says so. */
.skel-lrow.sk-r-anc .sk-ed:not(.sk-ed-bypass),
.skel-lrow.sk-r-self .sk-ed:not(.sk-ed-bypass){stroke:var(--accent)}
.skel-lrow.sk-r-anc .sk-term:not(.sk-term-bypass),
.skel-lrow.sk-r-self .sk-term:not(.sk-term-bypass){fill:var(--accent)}
.skel-lrow.sk-r-anc .sk-term-bar,.skel-lrow.sk-r-self .sk-term-bar{
  fill:none;stroke:var(--accent)}
.skel-lrow.sk-r-anc .sk-mdot,.skel-lrow.sk-r-anc .sk-mkey{fill:var(--accent)}
.skel-lrow.sk-r-anc .sk-minterp{stroke:var(--accent)}
/* The elbows are SVG and the verticals they meet are CSS divs owned by other
   rows, so accenting only the elbows leaves the chain broken between them.
   activateRow() adds sk-l-on to exactly the segments on the path to the root. */
.skel-lane.sk-l-on{background:var(--accent)}

/* ---------- nested-list fallback (<700px) ---------- */
.skel-list{margin-top:4px}
.skel-tree-list{list-style:none;margin:0;padding:0}
.skel-tree-list .skel-tree-list{margin:6px 0 6px 14px}
.skel-row{position:relative;margin:0 0 16px;padding:2px 0 2px 12px;
  border-left:2px solid var(--rule);font-size:14.5px;line-height:1.5}
.skel-e-elaborates{border-left-style:dashed}
.skel-e-qualifies{border-left-style:dotted;
  border-left-color:color-mix(in srgb,var(--note) 55%,transparent)}
.skel-e-rebuts{border-left-style:dotted;border-left-color:var(--note)}
.skel-interp{border-left-style:dashed}
.skel-interp > .skel-label{font-style:italic}
.skel-lrow.sk-interp .skel-llabel{font-style:italic}
.skel-label{margin-right:6px}
.skel-chip{display:inline-flex;align-items:center;min-height:26px;padding:4px 10px;
  border:1px solid var(--rule);border-radius:13px;background:var(--card-bg);
  color:var(--muted);font-size:12px;line-height:1.2;font-family:inherit}
.skel-chip.skel-add,.skel-chip.skel-fn{border-style:dashed}
/* the list fallback's second-parent chip: gloss-only, like the lane view's
   .skel-bpx it stands in for */
.skel-also{min-width:44px;min-height:44px;border:0;background:transparent;
  color:var(--muted);font-size:15px;cursor:help;font-family:inherit;
  margin:-11px 0;vertical-align:middle}
.skel-also:hover{color:var(--accent)}
.skel-quote{display:inline-flex;align-items:center;justify-content:center;
  border:0;background:transparent;color:var(--accent);cursor:pointer;font-family:inherit;
  font-size:15px;line-height:1;padding:0 12px;min-width:44px;min-height:44px;
  vertical-align:middle}
.skel-quote[disabled]{color:var(--muted);opacity:.5;cursor:default}
.skel-quote .skel-qn{font-size:10px;vertical-align:super;margin-left:1px}

/* ---------- legend (one panel, shared by both components) ---------- */
.skel-legend{position:fixed;left:50%;bottom:14px;transform:translateX(-50%);
  z-index:66;width:min(620px,calc(100vw - 28px));max-height:74vh;overflow:auto;
  background:var(--card-bg);color:var(--fg);border:1px solid var(--card-rule);
  border-radius:12px;box-shadow:0 12px 38px rgba(0,0,0,.26);
  padding:16px 44px 16px 20px;font-size:13.5px;line-height:1.55}
.skel-legend h4{margin:12px 0 6px;font-size:11.5px;text-transform:uppercase;
  letter-spacing:.1em;color:var(--accent)}
.skel-legend h4:first-of-type{margin-top:0}
.skel-legend ul{margin:0;padding-left:1.1em;color:var(--muted)}
.skel-legend li{margin:0 0 5px}
.skel-legend-q{color:var(--accent)}
.skel-legend-x{position:absolute;top:4px;right:4px;width:44px;height:44px;border:0;
  background:transparent;color:var(--muted);font-size:20px;line-height:1;cursor:pointer}
.skel-legend-x:hover{color:var(--fg)}

/* ---------- shared floating affordances + tip cards ---------- */
#skel-back,#skel-clear{position:fixed;left:14px;z-index:70;display:flex;align-items:center;
  gap:4px;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
#skel-back[hidden],#skel-clear[hidden]{display:none}
#skel-back{bottom:14px}
#skel-clear{bottom:66px}
.skel-float-btn,.skel-float-x{min-height:44px;padding:8px 14px;border:1px solid var(--rule);
  border-radius:22px;background:var(--card-bg);color:var(--fg);font-size:13px;cursor:pointer;
  box-shadow:0 6px 20px rgba(0,0,0,.18);font-family:inherit}
.skel-float-x{color:var(--muted)}
/* The counter that makes repeat-tap quote cycling discoverable: without it the
   second tap looks like the first one misfired. It rides the clear bar, which
   is on screen for exactly as long as a highlight is. */
.skel-qcount{display:inline-flex;align-items:center;min-height:44px;padding:8px 14px;
  border:1px solid var(--rule);border-radius:22px;background:var(--card-bg);
  color:var(--muted);font-size:13px;box-shadow:0 6px 20px rgba(0,0,0,.18);
  font-family:inherit}
.skel-qcount[hidden]{display:none}
mark.skel-hit{background:color-mix(in srgb,var(--accent) 26%,transparent);
  color:inherit;border-radius:3px;padding:1px 0}
.skel-flash{animation:skel-flash 1.2s ease-out 1}
@keyframes skel-flash{
  0%{background:color-mix(in srgb,var(--accent) 24%,transparent)}
  100%{background:transparent}
}
.skel-pulse{animation:skel-pulse .9s ease-out 2}
@keyframes skel-pulse{0%{opacity:1}50%{opacity:.35}100%{opacity:1}}
#tip .skel-peek-num{display:block;font-family:ui-monospace,Menlo,monospace;font-size:11px;
  letter-spacing:.1em;color:var(--muted);margin-bottom:4px}
#tip .skel-peek-label{display:block;font-size:14.5px;line-height:1.45;margin-bottom:10px}
#tip .skel-peek-note{display:block;font-size:13px;color:var(--muted);font-style:italic;
  margin-bottom:10px}
#tip .skel-peek-role{display:block;font-size:12px;color:var(--muted);margin:8px 0 4px}
#tip .skel-peek-row{display:flex;flex-wrap:wrap;gap:6px}
#tip .skel-goto,#tip .skel-chunkbtn{min-height:44px;padding:8px 14px;border:1px solid var(--rule);
  border-radius:22px;background:var(--card-bg);color:var(--accent);font-size:13px;
  cursor:pointer;font-family:inherit}
#tip .skel-chunkbtn{font-family:ui-monospace,Menlo,monospace;min-width:52px}
#tip .skel-actions{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}
#tip .skel-word{display:inline-flex;align-items:center;min-height:24px;padding:2px 9px;
  border:1px solid var(--rule);border-radius:12px;color:var(--muted);font-size:12px}
/* ---------- gloss tooltip ---------- */
/* A gloss says one thing about one mark. It gets a tooltip, not the full card
   chrome the source-link and chunk cards need: sign, sentence, and a × small
   enough to ride the same line. */
#tip.sk-mini{display:flex;align-items:flex-start;gap:9px;max-width:320px;
  padding:8px 10px;font-size:13px;line-height:1.45;border-radius:9px;
  box-shadow:0 6px 18px rgba(0,0,0,.2)}
#tip.sk-mini .tip-close{order:2;position:static;float:none;margin:0;padding:0;
  border:0;background:transparent;width:18px;height:18px;font-size:15px;
  line-height:1;flex:0 0 auto}
#tip.sk-mini .sk-g{order:1;display:flex;align-items:flex-start;gap:9px;min-width:0}
#tip.sk-mini .sk-gtxt{min-width:0}
/* The sign is the ROW's ink, drawn by the same builder - so it cannot drift
   from the mark it explains. It is shown at full strength even where the row
   holds that ink faint, because here it is the subject, not the background. */
svg.sk-sign{flex:0 0 auto;width:22px;height:24px;overflow:visible}
.sk-sign .sk-ed-bypass,.sk-sign .sk-term-bypass{opacity:1}
/* the ervvaz toggle shares .themebtn's look; only the on-state differs */
.skelbtn.on{background:var(--accent);color:var(--bg);border-color:var(--accent)}
.skel-langpill{display:inline-flex;border:1px solid var(--rule);border-radius:20px;
  overflow:hidden;background:var(--card-bg)}
.skel-langpill[hidden]{display:none}
.skel-langpill button{border:0;background:transparent;color:var(--muted);padding:6px 10px;
  font-size:12px;font-weight:600;letter-spacing:.06em;cursor:pointer;
  font-family:-apple-system,system-ui,sans-serif}
.skel-langpill button.on{background:var(--accent);color:var(--bg)}
"""


SKEL_JS = r"""
(function(){
  if (typeof SKEL === 'undefined' || !SKEL) return;
  var root = document.documentElement;
  var btn = document.getElementById('skelbtn');
  var langPill = document.getElementById('skel-lang');
  var blocks = document.querySelectorAll('[data-skel-block]');
  var backBar = document.getElementById('skel-back');
  var backBtn = document.getElementById('skel-back-btn');
  var backX = document.getElementById('skel-back-x');
  var clearBar = document.getElementById('skel-clear');
  var clearBtn = document.getElementById('skel-clear-btn');
  var qCount = document.getElementById('skel-qcount');
  var legend = document.getElementById('skel-legend');
  var tip = document.getElementById('tip');
  var on = false;                 // default OFF on every load; never persisted
  var lang = 'hu';                // label language; never persisted
  var backTarget = null;
  var cardKey = null;             // what the shared #tip currently shows
  var hoverTimer = null;
  var qNode = null, qIdx = 0;     // the node whose anchors are being cycled
  var finePointer = window.matchMedia &&
    window.matchMedia('(hover:hover) and (pointer:fine)').matches;

  function L(id){ var m = SKEL.labels[lang]; return (m && m[id]) || SKEL.labels.en[id] || id; }
  function U(key){ return (SKEL.ui[lang] || SKEL.ui.hu)[key] || ''; }
  // Mirror of _fmt() in skeleton_view.py: the same string is rendered once at
  // build time and again here after a language switch, so both have to agree.
  function T(key, args){
    var s = U(key);
    if (!args || !args.length) return s;
    return s.replace(/%(\d)/g, function(all, k){
      var v = args[k - 1];
      return v == null ? all : String(v);
    });
  }
  function argsOf(el){
    var a = el.getAttribute('data-i18n-args');
    return a ? a.split('|') : null;
  }
  function esc(s){
    return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }
  // Mirror of shorten() in skeleton_view.py; the two must agree or a language
  // switch would silently re-cut every compact restatement differently.
  function shorten(s, n){
    s = String(s || '').replace(/\s+/g, ' ').trim();
    if (s.length <= n) return s;
    var cut = s.slice(0, n), k = cut.lastIndexOf(' ');
    if (k > 0) cut = cut.slice(0, k);
    return cut.replace(/[ ,;:.—-]+$/, '') + '…';
  }

  /* ---- on/off + language ------------------------------------------- */
  function setOn(next){
    on = next;
    root.classList.toggle('skel-on', on);
    btn.classList.toggle('on', on);
    btn.setAttribute('aria-pressed', on ? 'true' : 'false');
    for (var i = 0; i < blocks.length; i++){
      if (blocks[i].hasAttribute('data-skel-block')) blocks[i].hidden = !on;
    }
    if (langPill) langPill.hidden = !on;
    if (!on){ dismiss(); hideBack(); closeTip(); clearRows(); hideLegend(); }
  }

  function applyLang(){
    var i, els = document.querySelectorAll('[data-skel-label]');
    for (i = 0; i < els.length; i++){
      els[i].textContent = L(els[i].getAttribute('data-skel-label'));
    }
    els = document.querySelectorAll('[data-skel-short]');
    for (i = 0; i < els.length; i++){
      var n = parseInt(els[i].getAttribute('data-skel-len'), 10) || 110;
      els[i].textContent = shorten(L(els[i].getAttribute('data-skel-short')), n);
    }
    els = document.querySelectorAll('[data-i18n]');
    for (i = 0; i < els.length; i++){
      els[i].textContent = T(els[i].getAttribute('data-i18n'), argsOf(els[i]));
    }
  }
  function setLang(next){
    if (next === lang) return;
    lang = next;
    if (langPill){
      var bs = langPill.querySelectorAll('button');
      for (var i = 0; i < bs.length; i++){
        bs[i].classList.toggle('on', bs[i].getAttribute('data-skel-lang') === lang);
      }
    }
    applyLang();
    closeTip();            // a stale card would keep the old language
  }

  /* ---- shared hover card ------------------------------------------- */
  // An empty card is always a bug in the caller, never a state worth showing:
  // #tip would render as a bare × floating over the page. Refuse to open, and
  // drop whatever was open, so the reader never sees a card with no content.
  function hasContent(inner){
    return !!inner && String(inner).replace(/<[^>]*>/g, '').trim() !== '';
  }
  // The corridor is the strip the reader crosses between the thing they hovered
  // and the card that answered. A card is placed about 8px from its trigger, and
  // for a minimap node that gap lands inside the arc band - so the corridor is
  // where a card used to be lost on the way to it. Two things consult it: the
  // hide timer (stay while the reader is still travelling) and the arc/fan hover
  // (do not hand the card to an edge the reader is only passing over).
  var corridor = null, keepFrom = 0, ptrX = -1, ptrY = -1;
  document.addEventListener('pointermove', function(ev){
    ptrX = ev.clientX; ptrY = ev.clientY;
  }, {passive: true});
  function setCorridor(el){
    if (!el || !tip){ corridor = null; return; }
    var a = el.getBoundingClientRect(), b = tip.getBoundingClientRect();
    corridor = {l: Math.min(a.left, b.left) - 8, r: Math.max(a.right, b.right) + 8,
                t: Math.min(a.top, b.top) - 8, bt: Math.max(a.bottom, b.bottom) + 8};
    keepFrom = 0;
  }
  // The card can also be taken down by the page itself - an outside press, or
  // the grace running out - and those paths do not go through closeTip(). So a
  // corridor only counts while its card is actually on screen; without this
  // check a stale corridor would go on swallowing arc hovers in that region
  // long after the card it belonged to was gone.
  function inCorridor(x, y){
    return !!corridor && !!tip && tip.classList.contains('show') &&
           x >= corridor.l && x <= corridor.r &&
           y >= corridor.t && y <= corridor.bt;
  }
  // Re-armed once per grace period, and capped: a pointer parked in the corridor
  // without ever arriving must not pin the card open for the rest of the visit.
  function keepAlive(){
    if (!corridor) return false;
    if (!keepFrom) keepFrom = Date.now();
    if (Date.now() - keepFrom > 1200 || !inCorridor(ptrX, ptrY)){
      keepFrom = 0;
      return false;
    }
    return true;
  }
  var TIP_OPTS = {grace: 420, keepAlive: keepAlive};

  function openTip(el, inner, key, variant){
    if (!hasContent(inner)){ closeTip(); return false; }
    cardKey = key || null;
    if (window.SKEL_TIP){
      window.SKEL_TIP.open(el, inner, variant, TIP_OPTS);
      setCorridor(el);
    }
    return true;
  }
  function closeTip(){
    cardKey = null; corridor = null; keepFrom = 0;
    if (window.SKEL_TIP) window.SKEL_TIP.close();
  }
  function tipShows(key){
    return cardKey === key && tip && tip.classList.contains('show');
  }

  /* ---- cards -------------------------------------------------------- */
  function chunkRow(role, list){
    if (!list || !list.length) return '';
    var out = '<span class="skel-peek-role">' + esc(role) + '</span>' +
              '<span class="skel-peek-row">';
    for (var i = 0; i < list.length; i++){
      out += '<button type="button" class="skel-chunkbtn skel-keep" ' +
             'data-skel-travel="' + esc(list[i]) + '">' + esc(list[i]) + '</button>';
    }
    return out + '</span>';
  }
  // Every gloss has the same two parts: the SIGN it is about, drawn by the same
  // builder that drew it on the row, and one sentence. The sign replaces v2.2's
  // text-character header, which could not show the footnote-only mark's
  // underline at all and so left "this explains THAT" to the reader's guess.
  function signCard(sign, text){
    if (!text) return '';
    return '<span class="sk-g">' + (sign || '') +
           '<span class="sk-gtxt">' + esc(text) + '</span></span>';
  }
  // Scheme names and sentences are UI strings like every other card string, so
  // they follow the EN|HU pill rather than sitting in one language beside a
  // label that switches.
  function schemeName(key){ return U('sch-' + key) || key; }
  function glossCard(key){
    return signCard(SKEL.signs.scheme, U('schg-' + key));
  }
  function nodeCard(chunk){
    if (chunk === 'thesis'){
      return '<span class="skel-peek-num">' + esc(U('thesis-cap')) + '</span>' +
             '<span class="skel-peek-label">' + esc(L(SKEL.thesis.id)) + '</span>' +
             '<span class="skel-peek-note">' + esc(U('thesis-note')) + '</span>' +
             (SKEL.thesis.scheme ? '<span class="skel-word">' +
               esc(schemeName(SKEL.thesis.scheme)) + '</span>' : '');
    }
    var meta = SKEL.chunks[chunk];
    if (!meta) return '';
    var out = '<span class="skel-peek-num">' + esc(chunk) + ' · ' +
              esc(T('n-claims', [meta.d1])) + '</span>' +
              '<span class="skel-peek-label">' + esc(L(meta.key)) + '</span>';
    if (meta.scheme){
      out += '<span class="skel-word">' + esc(schemeName(meta.scheme)) + '</span>';
    }
    // Both rows name the direction of dependence, from this chunk's point of
    // view: `up` is what it rests on, `down` is what rests on it. "ezt
    // használja" read as if THIS chunk used the listed ones - the arrow the
    // wrong way round.
    out += chunkRow(U('builds-on'), meta.up);
    out += chunkRow(U('built-on-by'), meta.down);
    out += '<span class="skel-actions">' +
           '<button type="button" class="skel-goto skel-keep" data-skel-travel="' +
           esc(chunk) + '">' + esc(U('to-start')) + '</button>' +
           '<button type="button" class="skel-goto skel-keep" data-skel-detail="' +
           esc(chunk) + '">' + esc(U('details')) + '</button></span>';
    return out;
  }
  function edgeCard(key){
    var rec = SKEL.arcs[key];
    if (!rec) return '';
    var out = '<span class="skel-peek-num">' + esc(rec.a) + ' → ' + esc(rec.b) +
              '</span>';
    for (var i = 0; i < rec.edges.length; i++){
      out += '<p>' + esc(shorten(L(rec.edges[i][0]), 74)) + ' → ' +
             esc(shorten(L(rec.edges[i][1]), 74)) + '</p>';
    }
    return out;
  }
  // v2.1 opened a card on every row marker, restating the row's own label, its
  // parent's label and its quote buttons - all three already on screen, one row
  // away. It is gone. A marker now says only what its GLYPH means, in the same
  // gloss the scheme diamond has always used; the row itself says the rest.
  function markGlossCard(key, args){
    return signCard(SKEL.signs[key], T(key, args));
  }
  // A second parent: the one edge whose meaning the picture cannot carry, since
  // its target sits rows away in a lane of its own.
  function bypassCard(nid){
    var label = L(nid);
    if (!label) return '';
    return signCard(SKEL.signs.bypass, T('bp-also', [shorten(label, 74)]));
  }
  // The three gloss families share one shape, so they share one lookup: the
  // attribute an element carries decides which sentence it gets.
  function glossOf(el){
    var k = el.getAttribute('data-skel-gloss');
    if (k) return [glossCard(k), 'gloss:' + k];
    k = el.getAttribute('data-skel-mg');
    if (k) return [markGlossCard(k, argsOf(el)), 'mg:' + k];
    k = el.getAttribute('data-skel-bp');
    if (k) return [bypassCard(k), 'bp:' + k];
    return null;
  }
  var GLOSS_SEL = '[data-skel-gloss],[data-skel-mg],[data-skel-bp]';

  /* ---- travel ------------------------------------------------------- */
  function flash(el){
    if (!el) return;
    el.classList.remove('skel-flash');
    void el.offsetWidth;
    el.classList.add('skel-flash');
    setTimeout(function(){ el.classList.remove('skel-flash'); }, 1300);
  }
  function originOf(el){
    var wrap = el && el.closest ? el.closest('[data-view]') : null;
    if (!wrap) return null;
    var v = (wrap.getAttribute('data-view') || '').split(' ')[0];
    return v || null;
  }
  function travel(chunk, from){
    var meta = SKEL.chunks[chunk];
    if (!meta) return;
    var box = document.getElementById(meta.box);
    if (!box) return;
    closeTip();
    box.scrollIntoView({block: 'start', behavior: 'smooth'});
    flash(box.querySelector('.skel-pre-inner') || box);
    if (from && from !== chunk) showBack(from);
  }
  function openDetail(chunk, scroll){
    var post = document.getElementById(SKEL.chunks[chunk].post);
    if (!post) return;
    var strip = post.querySelector('[data-skel-chunk="' + chunk + '"]');
    if (!strip) return;
    var card = strip.querySelector('.skel-card');
    var detail = strip.querySelector('.skel-detail');
    if (card && detail && detail.hidden) setExpanded(card, detail, true);
    if (scroll){
      closeTip();
      strip.scrollIntoView({block: 'start', behavior: 'smooth'});
      flash(strip.querySelector('.skel-restate'));
    }
  }
  // The card IS the collapsed state of the panel, so it steps aside when open.
  // Focus has to follow it, or a keyboard user is left on a hidden element.
  function setExpanded(card, detail, open, focus){
    detail.hidden = !open;
    card.hidden = open;
    card.setAttribute('aria-expanded', open ? 'true' : 'false');
    if (!focus) return;
    var next = open ? detail.querySelector('[data-skel-collapse]') : card;
    if (next) try { next.focus({preventScroll: true}); } catch (e) { next.focus(); }
  }
  function showBack(chunk){
    backTarget = chunk;
    backBtn.textContent = '← vissza ' + chunk;
    backBar.hidden = false;
  }
  function hideBack(){ backTarget = null; backBar.hidden = true; }

  /* ---- anchor highlight (unchanged behaviour from v1) --------------- */
  function clearMarks(){
    var marks = document.querySelectorAll('mark.skel-hit');
    for (var i = 0; i < marks.length; i++){
      var m = marks[i], p = m.parentNode;
      while (m.firstChild) p.insertBefore(m.firstChild, m);
      p.removeChild(m);
      p.normalize();            // mandatory: mark residue would split text nodes
    }
    clearBar.hidden = true;
    if (qCount) qCount.hidden = true;
  }
  // clearMarks() also runs mid-jump, twice, to guarantee a single mark; only
  // dismiss() means "the reader is done with this node", so only dismiss()
  // forgets where the quote cycle stood.
  function dismiss(){ qNode = null; qIdx = 0; clearMarks(); }
  function showQCount(i, n){
    if (!qCount) return;
    if (n < 2){ qCount.hidden = true; return; }
    qCount.setAttribute('data-i18n', 'quote-n');
    qCount.setAttribute('data-i18n-args', i + '|' + n);
    qCount.textContent = T('quote-n', [i, n]);
    qCount.hidden = false;
  }
  function findInNode(node, quote){
    var i = node.data.indexOf(quote);
    if (i >= 0) return [i, i + quote.length];
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
  // Repeated taps on one ❝ walk that node's anchors, 1 -> 2 -> 3 -> 1. v2.1 had
  // this too and it was undiscoverable, because nothing on screen said which of
  // the three you were looking at; the clear bar's counter is what fixes that,
  // so the two ship together or not at all.
  function nextQuoteIndex(nodeId){
    var list = SKEL.anchors[nodeId];
    if (!list || !list.length) return 0;
    return qNode === nodeId ? (qIdx + 1) % list.length : 0;
  }
  function jump(nodeId, index){
    var list = SKEL.anchors[nodeId];
    if (!list || !list.length) return;
    var n = list.length, at = (index || 0) % n, anchor = list[at], hops = 0;
    while (hops++ < n && (!anchor || !anchor.ok)){   // skip anchors that failed
      at = (at + 1) % n;                             // the build-time verifier
      anchor = list[at];
    }
    if (!anchor || !anchor.ok) return;
    clearMarks();
    qNode = nodeId; qIdx = at;
    var sec = document.getElementById('sec-' + anchor.sec);
    if (!sec) return;
    var article = sec.querySelector('article.orig.lang-en');
    if (!article) return;
    if (article.hidden) showEnglish(sec);
    requestAnimationFrame(function(){
      clearMarks();
      var mark = markQuote(article, anchor.q);
      if (mark){
        try { mark.scrollIntoView({block: 'center', behavior: 'smooth'}); } catch (e) {
          mark.scrollIntoView();
        }
        clearBar.hidden = false;
        showQCount(at + 1, n);
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

  /* ---- map: incident-edge lighting ---------------------------------- */
  function lightIncident(svg, chunk){
    dimAll(svg);
    if (!svg) return;
    var i, els = svg.querySelectorAll('[data-arc]');
    for (i = 0; i < els.length; i++){
      var k = els[i].getAttribute('data-arc').split('>');
      els[i].classList.toggle('sk-hot', k[0] === chunk || k[1] === chunk);
    }
    els = svg.querySelectorAll('[data-fan]');
    for (i = 0; i < els.length; i++){
      els[i].classList.toggle('sk-hot',
        els[i].getAttribute('data-fan') === chunk || chunk === SKEL.roof);
    }
  }
  function dimAll(svg){
    if (!svg) return;
    var els = svg.querySelectorAll('.sk-hot');
    for (var i = 0; i < els.length; i++) els[i].classList.remove('sk-hot');
  }

  /* ---- detail rows -------------------------------------------------- */
  function clearRows(){
    var i, els = document.querySelectorAll('.skel-lrow.sk-r-self,.skel-lrow.sk-r-anc,' +
                                           '.skel-lrow.sk-r-desc');
    for (i = 0; i < els.length; i++){
      els[i].classList.remove('sk-r-self', 'sk-r-anc', 'sk-r-desc');
    }
    els = document.querySelectorAll('.sk-l-on,.sk-bp-on');
    for (i = 0; i < els.length; i++) els[i].classList.remove('sk-l-on', 'sk-bp-on');
  }
  // Lane segments of one row in one column, named the way _derive_lanes() hands
  // them over: the column is the inline `left` the segment needed anyway, the
  // part is its class. A null `part` means every segment this row owns there.
  function lightLanes(row, x, part){
    if (!row) return;
    var els = row.querySelectorAll('.skel-lane');
    for (var i = 0; i < els.length; i++){
      var e = els[i];
      if (parseInt(e.style.left, 10) !== x) continue;
      var k = e.classList.contains('sk-l-up') ? 'up'
            : (e.classList.contains('sk-l-down') ? 'down' : 'full');
      if (!part || k === part) e.classList.add('sk-l-on');
    }
  }
  // The run from a child up to its parent is drawn by every row in between, in
  // the parent's column: the parent owns the half below its own marker, the
  // rows between own whatever they own there, and the child owns only the half
  // ABOVE its marker - the half below it belongs to the child's later siblings,
  // and lighting it would run the accent into a branch that is not on the path.
  // That one distinction is why a child's segment is split at all.
  function lightChain(rows, parentOf, from){
    var c = from;
    while (parentOf[c] != null){
      var p = parentOf[c];
      var d = parseInt(rows[c].getAttribute('data-depth'), 10);
      var x = SKEL.lane[0] + SKEL.lane[1] * (d - 1);
      lightLanes(rows[c], x, 'up');
      for (var k = p + 1; k < c; k++) lightLanes(rows[k], x, null);
      lightLanes(rows[p], x, 'down');
      c = p;
    }
  }
  function activateRow(row){
    var lanes = row.parentNode;
    var rows = lanes.querySelectorAll('.skel-lrow');
    var self = parseInt(row.getAttribute('data-row'), 10);
    if (row.classList.contains('sk-r-self')){ clearRows(); return; }
    clearRows();
    var parentOf = {}, i;
    for (i = 0; i < rows.length; i++){
      var p = rows[i].getAttribute('data-parent');
      parentOf[i] = p === '' ? null : parseInt(p, 10);
    }
    var anc = {}, cur = parentOf[self];
    while (cur != null){ anc[cur] = 1; cur = parentOf[cur]; }
    var desc = {};
    for (i = self + 1; i < rows.length; i++){
      var q = parentOf[i];
      if (q === self || desc[q]) desc[i] = 1;
    }
    row.classList.add('sk-r-self');
    for (i = 0; i < rows.length; i++){
      if (anc[i]) rows[i].classList.add('sk-r-anc');
      else if (desc[i]) rows[i].classList.add('sk-r-desc');
    }
    lightChain(rows, parentOf, self);
    // A bypass belongs to the two rows it joins, not to the chain, so it lights
    // only when one of those two is the live row.
    var bp = row.getAttribute('data-bpend');
    if (bp != null){
      var parts = lanes.querySelectorAll('.skel-lane[data-bp="' + bp + '"],' +
                                         'path[data-bp="' + bp + '"]');
      for (i = 0; i < parts.length; i++) parts[i].classList.add('sk-bp-on');
    }
  }

  /* ---- legend ------------------------------------------------------- */
  function showLegend(){ if (legend) legend.hidden = false; }
  function hideLegend(){ if (legend) legend.hidden = true; }

  /* ---- wiring ------------------------------------------------------- */
  btn.addEventListener('click', function(){ setOn(!on); });
  if (langPill){
    langPill.addEventListener('click', function(ev){
      var b = ev.target.closest && ev.target.closest('[data-skel-lang]');
      if (b) setLang(b.getAttribute('data-skel-lang'));
    });
  }

  // Desktop: hovering a node opens its card after a beat; clicking navigates.
  // Touch: the first tap opens the card, the second tap on the same node
  // navigates. Both paths go through the same two functions.
  // `data-skel-node` now means one thing only - a CHUNK id, inside the minimap.
  // The detail view's row markers and the list view's second-parent chips used
  // to share the attribute with a NODE id in it, which is how nodeCard() kept
  // being handed an unknown key; they carry their own gloss attributes instead.
  function mapOf(el){ return (el && el.closest) ? el.closest('svg.skel-map') : null; }
  function openNode(el, id){
    var opened = openTip(el, nodeCard(id), 'node:' + id);
    if (id !== 'thesis') lightIncident(mapOf(el), id);
    return opened;
  }
  function nodeActivate(el, chunk){
    if (chunk === 'thesis'){ openNode(el, chunk); return; }
    if (tipShows('node:' + chunk)){ travel(chunk, originOf(el)); return; }
    openNode(el, chunk);
  }

  if (finePointer){
    document.addEventListener('mouseover', function(ev){
      var t = ev.target;
      if (!on || !t || !t.closest) return;
      var hit = t.closest('[data-skel-node]');
      if (hit){
        clearTimeout(hoverTimer);
        hoverTimer = setTimeout(function(){
          openNode(hit, hit.getAttribute('data-skel-node'));
        }, 120);
        return;
      }
      // Glosses answer "what does this symbol mean", which is a question the
      // reader has while looking at the symbol - so on a fine pointer they
      // open on hover, on the same beat as everything else here.
      var gl = t.closest(GLOSS_SEL);
      if (gl){
        clearTimeout(hoverTimer);
        var g = glossOf(gl);
        if (g) hoverTimer = setTimeout(function(){
          openTip(gl, g[0], g[1], 'sk-mini');
        }, 120);
        return;
      }
      var edge = t.closest('[data-arc],[data-fan]');
      if (edge && edge.closest('svg.skel-map')){
        // An edge card used to open with NO delay, alone among the hover cards.
        // A node's card sits about 8px below it, which is inside the arc band,
        // so a single mousemove sample landing on an 11px-wide arc stroke swapped
        // the card out from under a reader walking toward it - and only a dart
        // fast enough to skip the stroke got through. Now it waits the same beat
        // as everything else, and inside an open card's corridor it does not
        // even start: those arcs are under the card anyway.
        if (inCorridor(ev.clientX, ev.clientY)) return;
        clearTimeout(hoverTimer);
        var key = edge.getAttribute('data-arc');
        if (!key){
          var c = edge.getAttribute('data-fan');
          key = c + '>' + SKEL.roof;
          if (!SKEL.arcs[key]){
            var f = SKEL.fans[c];
            if (f) SKEL.arcs[key] = {a: c, b: SKEL.roof, edges: f};
          }
        }
        hoverTimer = setTimeout(function(){
          if (openTip(edge, edgeCard(key), 'edge:' + key)) edge.classList.add('sk-hot');
        }, 120);
      }
    });
    document.addEventListener('mouseout', function(ev){
      var t = ev.target;
      if (!t || !t.closest) return;
      if (t.closest('[data-skel-node],[data-arc],[data-fan],' + GLOSS_SEL)) {
        clearTimeout(hoverTimer);
      }
    });
  }

  document.addEventListener('click', function(ev){
    var t = ev.target;
    if (!t || !t.closest) return;

    // Glosses come first: a row marker and a bypass stub both sit inside a row
    // that would otherwise swallow the click at the bottom of this handler.
    var gl = t.closest(GLOSS_SEL);
    if (gl){
      var g = glossOf(gl);
      if (g) openTip(gl, g[0], g[1], 'sk-mini');
      // The marker is still the row's own affordance, so it keeps highlighting
      // the row; that, plus keyboard focus, is all it does now.
      if (gl.classList.contains('skel-mark')){
        var mrow = gl.closest('.skel-lrow');
        if (mrow) activateRow(mrow);
      }
      return;
    }
    var nodeHit = t.closest('[data-skel-node]');
    if (nodeHit){
      var chunk = nodeHit.getAttribute('data-skel-node');
      if (finePointer){
        if (chunk === 'thesis') openNode(nodeHit, chunk);
        else travel(chunk, originOf(nodeHit));
        return;
      }
      nodeActivate(nodeHit, chunk);
      return;
    }
    var quote = t.closest('.skel-quote');
    if (quote && !quote.disabled){
      var qid = quote.getAttribute('data-skel-quote');
      jump(qid, nextQuoteIndex(qid));
      return;
    }
    var card = t.closest('.skel-card');
    if (card){
      var detail = document.getElementById('skel-detail-' + card.getAttribute('data-skel-card'));
      if (detail) setExpanded(card, detail, true, true);
      return;
    }
    var collapse = t.closest('[data-skel-collapse]');
    if (collapse){
      var det = collapse.closest('.skel-detail');
      var strip = det.parentNode;
      setExpanded(strip.querySelector('.skel-card'), det, false, true);
      clearRows();
      return;
    }
    var zoom = t.closest('[data-skel-zoom]');
    if (zoom){
      var lanes = zoom.closest('.skel-detail').querySelector('.skel-lanes');
      var mode = zoom.getAttribute('data-skel-zoom');
      lanes.classList.toggle('sk-bones', mode === 'bones');
      var sibs = zoom.parentNode.querySelectorAll('button');
      for (var i = 0; i < sibs.length; i++) sibs[i].classList.toggle('on', sibs[i] === zoom);
      return;
    }
    if (t.closest('[data-skel-legend]')){ showLegend(); return; }
    if (t.closest('#skel-legend-x')){ hideLegend(); return; }

    var travelBtn = t.closest('[data-skel-travel]');
    if (travelBtn){
      travel(travelBtn.getAttribute('data-skel-travel'), window.SKEL_LAST_ORIGIN || null);
      return;
    }
    var detailBtn = t.closest('[data-skel-detail]');
    if (detailBtn){ openDetail(detailBtn.getAttribute('data-skel-detail'), true); return; }

    var lrow = t.closest('.skel-lrow');
    if (lrow){ activateRow(lrow); return; }
  });

  // Remember which map a card was opened from, for the single back slot.
  document.addEventListener('pointerdown', function(ev){
    var t = ev.target;
    if (!t || !t.closest) return;
    var origin = originOf(t.closest('[data-skel-node]') || t);
    if (origin) window.SKEL_LAST_ORIGIN = origin;
  }, true);

  // Any pointer press outside a mark, the clear bar or a quote button dismisses
  // the highlight - and ends the quote cycle, since the reader has moved on.
  // Namespaced so the existing #tip handlers are untouched.
  document.addEventListener('pointerdown', function(ev){
    if (clearBar.hidden) return;
    var t = ev.target;
    if (t && t.closest && (t.closest('mark.skel-hit') || t.closest('#skel-clear') ||
        t.closest('.skel-quote'))) return;
    dismiss();
  }, true);

  document.addEventListener('keydown', function(ev){
    if (ev.key !== 'Escape') return;
    if (legend && !legend.hidden){ hideLegend(); return; }
    if (!clearBar.hidden) dismiss();
    clearRows();
    hideBack();
  });

  clearBtn.addEventListener('click', function(){ dismiss(); clearRows(); });
  backBtn.addEventListener('click', function(){
    if (backTarget){ var to = backTarget; hideBack(); travel(to, null); }
  });
  backX.addEventListener('click', hideBack);

  if (tip){
    tip.addEventListener('click', function(ev){
      var t = ev.target;
      if (!t || !t.closest) return;
      var g = t.closest('[data-skel-travel]');
      if (g){ travel(g.getAttribute('data-skel-travel'), window.SKEL_LAST_ORIGIN || null); return; }
      var d = t.closest('[data-skel-detail]');
      if (d){ openDetail(d.getAttribute('data-skel-detail'), true); return; }
    });
  }

  applyLang();
  setOn(false);
})();
"""

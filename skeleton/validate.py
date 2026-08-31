#!/usr/bin/env python3
"""Validate skeleton/skeleton.yaml against SCHEMA.md v0.

python3 stdlib only - PyYAML is deliberately not a dependency, so the skeleton
is written in a strict regular subset of YAML that yamlsubset.py (shared with
the page builder) reads deterministically:

    text:                       # mapping of scalars; `sections` is an inline list
    nodes:                      # list of block mappings
      - id: <id>
        level: <0|1|2>
        kind: <claim|ground|warrant|qualification|rebuttal|definition|implication>
        section: "<chunk id>"
        label: >-               # folded block scalar, one paragraph
          ...
        anchors: []             # or a list of block mappings with
          - section: "<physical section id>"
            footnote: <n>       # optional
            quote: "<verbatim substring of that section's section.md>"
        interpolated: <true|false>
    edges:
      - {from: <id>, to: <id>, type: <edge type>}          # optional , scheme: <name>

Anything outside that subset (aliases, multi-line flow, tags, inline comments
after a value) is not supported and is reported as a parse error rather than
silently mis-read.

Exit status: non-zero if any structural check or well-formedness rule
(R1/R2/R4/R5/R6/R7) fails. Diagnostics (D1/D2/D3) are reported about the text
and never affect the exit status.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from yamlsubset import ParseError, load  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SKELETON = os.path.join(HERE, "skeleton.yaml")
SECTIONS_DIR = os.path.join(REPO, "sections")

NODE_KINDS = {
    "claim", "ground", "warrant", "qualification",
    "rebuttal", "definition", "implication",
}
EDGE_TYPES = {"supports", "elaborates", "qualifies", "rebuts", "presupposes"}
LEVELS = {0, 1, 2}
D1_BAND = (3, 5)


# --------------------------------------------------------------------------
# Section files
# --------------------------------------------------------------------------

def section_files():
    out = {}
    for name in sorted(os.listdir(SECTIONS_DIR)):
        path = os.path.join(SECTIONS_DIR, name, "section.md")
        if os.path.isfile(path):
            out[name.split("-", 1)[0]] = path
    return out


# --------------------------------------------------------------------------
# Graph helpers
# --------------------------------------------------------------------------

def reachable(adj, start):
    seen, stack = set(), [start]
    while stack:
        cur = stack.pop()
        for nxt in adj.get(cur, ()):
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return seen


def find_cycle(ids, adj):
    WHITE, GREY, BLACK = 0, 1, 2
    colour = dict.fromkeys(ids, WHITE)
    parent = {}
    for root in ids:
        if colour[root] != WHITE:
            continue
        stack = [(root, iter(adj.get(root, ())))]
        colour[root] = GREY
        while stack:
            node, it = stack[-1]
            advanced = False
            for nxt in it:
                if colour[nxt] == GREY:
                    cycle = [nxt]
                    cur = node
                    while cur != nxt:
                        cycle.append(cur)
                        cur = parent[cur]
                    cycle.append(nxt)
                    return list(reversed(cycle))
                if colour[nxt] == WHITE:
                    colour[nxt] = GREY
                    parent[nxt] = node
                    stack.append((nxt, iter(adj.get(nxt, ()))))
                    advanced = True
                    break
            if not advanced:
                colour[node] = BLACK
                stack.pop()
    return None


# --------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------

def main():
    failures = []
    notes = []

    def fail(rule, message):
        failures.append("%s: %s" % (rule, message))

    try:
        doc = load(SKELETON)
    except ParseError as exc:
        print("PARSE FAILURE in %s\n  %s" % (SKELETON, exc))
        return 2

    text = doc.get("text") or {}
    nodes = doc.get("nodes") or []
    edges = doc.get("edges") or []
    sections = text.get("sections") or []

    # ---- structural integrity ------------------------------------------
    by_id = {}
    for node in nodes:
        nid = node.get("id")
        if not nid:
            fail("STRUCTURE", "a node has no id")
            continue
        if nid in by_id:
            fail("STRUCTURE", "duplicate node id %r" % nid)
        by_id[nid] = node
        if node.get("level") not in LEVELS:
            fail("STRUCTURE", "%s: level must be 0, 1 or 2 (got %r)"
                 % (nid, node.get("level")))
        if node.get("kind") not in NODE_KINDS:
            fail("STRUCTURE", "%s: unknown kind %r" % (nid, node.get("kind")))
        if not isinstance(node.get("interpolated"), bool):
            fail("STRUCTURE", "%s: interpolated must be true or false" % nid)
        label = (node.get("label") or "").strip()
        if not label:
            fail("STRUCTURE", "%s: empty label" % nid)
        if node.get("anchors") is None:
            fail("STRUCTURE", "%s: missing anchors field (use [] if none)" % nid)

    adj = {}
    for edge in edges:
        src, dst, etype = edge.get("from"), edge.get("to"), edge.get("type")
        if src not in by_id:
            fail("STRUCTURE", "edge from unknown node %r" % src)
        if dst not in by_id:
            fail("STRUCTURE", "edge to unknown node %r" % dst)
        if etype not in EDGE_TYPES:
            fail("STRUCTURE", "edge %s -> %s: unknown type %r" % (src, dst, etype))
        if src in by_id and dst in by_id:
            adj.setdefault(src, []).append(dst)

    # ---- R1 -------------------------------------------------------------
    level0 = [n["id"] for n in nodes if n.get("level") == 0]
    if len(level0) != 1:
        fail("R1", "expected exactly one level-0 thesis node, found %d%s"
             % (len(level0), (": " + ", ".join(level0)) if level0 else ""))
    thesis = level0[0] if len(level0) == 1 else None

    # ---- R2 -------------------------------------------------------------
    level1_by_section = {}
    for node in nodes:
        if node.get("level") == 1:
            level1_by_section.setdefault(node.get("section"), []).append(node["id"])
    for sec in sections:
        found = level1_by_section.get(sec, [])
        if len(found) != 1:
            fail("R2", "section %r: expected exactly one level-1 key claim, found %d%s"
                 % (sec, len(found), (": " + ", ".join(found)) if found else ""))
    for sec, ids in sorted(level1_by_section.items()):
        if sec not in sections:
            fail("R2", "level-1 node(s) %s belong to section %r, which is not "
                 "listed in text.sections" % (", ".join(ids), sec))

    # ---- R4 / R7 --------------------------------------------------------
    files = section_files()
    cache = {}

    def body(sec):
        if sec not in cache:
            path = files.get(sec)
            if path is None:
                cache[sec] = None
            else:
                with open(path, encoding="utf-8") as fh:
                    cache[sec] = fh.read()
        return cache[sec]

    for node in nodes:
        nid = node.get("id")
        anchors = node.get("anchors") or []
        if node.get("interpolated") is True:
            if anchors:
                fail("R7", "%s is interpolated but carries %d anchor(s)"
                     % (nid, len(anchors)))
            continue
        if not anchors:
            fail("R4", "%s is not interpolated but has no anchor" % nid)
        for pos, anchor in enumerate(anchors, 1):
            sec = anchor.get("section")
            quote = anchor.get("quote")
            if not isinstance(quote, str) or not quote:
                fail("R4", "%s anchor #%d: missing quote" % (nid, pos))
                continue
            source = body(sec)
            if source is None:
                fail("R4", "%s anchor #%d: no sections/%s-*/section.md for section %r"
                     % (nid, pos, sec, sec))
                continue
            if quote not in source:
                fail("R4", "%s anchor #%d: quote is not a verbatim substring of "
                     "sections/%s-*/section.md\n        quote: %s"
                     % (nid, pos, sec, quote))

    # ---- R5 -------------------------------------------------------------
    cycle = find_cycle(list(by_id), adj)
    if cycle:
        fail("R5", "edges are not a DAG; cycle: %s" % " -> ".join(cycle))

    # ---- R6 -------------------------------------------------------------
    if thesis and not cycle:
        for node in nodes:
            nid = node.get("id")
            if node.get("level") == 1:
                if thesis not in reachable(adj, nid):
                    fail("R6", "level-1 node %s does not reach the thesis %s"
                         % (nid, thesis))
            elif node.get("level") == 2:
                sec = node.get("section")
                keys = level1_by_section.get(sec, [])
                if len(keys) != 1:
                    continue  # already reported by R2
                if keys[0] not in reachable(adj, nid):
                    fail("R6", "level-2 node %s does not reach its section's "
                         "key claim %s" % (nid, keys[0]))
    elif cycle:
        notes.append("R6 skipped: reachability is not meaningful while the "
                     "graph contains a cycle.")

    # ---- report ---------------------------------------------------------
    print("Reasoning-skeleton validator - SCHEMA.md v0")
    print("  file:     %s" % os.path.relpath(SKELETON, REPO))
    print("  nodes:    %d (level 0: %d, level 1: %d, level 2: %d)"
          % (len(nodes),
             sum(1 for n in nodes if n.get("level") == 0),
             sum(1 for n in nodes if n.get("level") == 1),
             sum(1 for n in nodes if n.get("level") == 2)))
    print("  edges:    %d" % len(edges))
    print("  chunks:   %s" % ", ".join(sections))
    print()

    if failures:
        print("WELL-FORMEDNESS FAILURES (%d)" % len(failures))
        for item in failures:
            print("  - %s" % item)
    else:
        print("WELL-FORMEDNESS: R1, R2, R4, R5, R6, R7 all pass.")
    for note in notes:
        print("  note: %s" % note)
    print()

    # ---- diagnostics (never fail) ---------------------------------------
    print("DIAGNOSTICS (about the text, not constraints on the map)")

    print("  D1 - chunk load (level-2 nodes per chunk, interpolated included; "
          "comfortable band %d-%d):" % D1_BAND)
    for sec in sections:
        subs = [n for n in nodes if n.get("level") == 2 and n.get("section") == sec]
        interp = sum(1 for n in subs if n.get("interpolated") is True)
        flag = "" if D1_BAND[0] <= len(subs) <= D1_BAND[1] else "   <-- outside band"
        print("    %-4s %2d node(s)%s%s"
              % (sec, len(subs),
                 (" (%d interpolated)" % interp) if interp else "",
                 flag))
    counts = [len([n for n in nodes
                   if n.get("level") == 2 and n.get("section") == sec])
              for sec in sections]
    if counts:
        print("    total level-2 nodes: %d; min %d, max %d, mean %.1f"
              % (sum(counts), min(counts), max(counts),
                 float(sum(counts)) / len(counts)))

    interpolated = [n for n in nodes if n.get("interpolated") is True]
    print("  D2 - explicitness (spelled-out bridges the reader must supply; "
          "a floor, not an inventory):")
    print("    %d interpolated node(s)" % len(interpolated))
    for node in interpolated:
        print("      %-34s [%s, chunk %s]"
              % (node.get("id"), node.get("kind"), node.get("section")))

    def footnote_only(node):
        anchors = node.get("anchors") or []
        return bool(anchors) and all("footnote" in a for a in anchors)

    buried = [n for n in nodes if footnote_only(n)]
    print("  D3 - buried load (nodes whose every anchor sits below the line):")
    if not buried:
        print("    none")
    for node in buried:
        fns = sorted({a.get("footnote") for a in node["anchors"]})
        print("      %-34s [chunk %s, footnote %s]"
              % (node.get("id"), node.get("section"),
                 ", ".join(str(f) for f in fns)))

    if thesis and not cycle and buried:
        buried_ids = {n["id"] for n in buried}
        on_chain = {}
        for node in nodes:
            if node.get("level") != 1:
                continue
            downstream = reachable(adj, node["id"])
            for bid in buried_ids & downstream:
                if thesis in reachable(adj, bid):
                    on_chain.setdefault(bid, []).append(node["id"])
        print("    main chains through a footnote-only node "
              "(a level-1 node's path to the thesis):")
        if not on_chain:
            print("      none")
        for bid in sorted(on_chain):
            print("      %s <- reached by %s" % (bid, ", ".join(sorted(on_chain[bid]))))
        # Extra, informational: buried nodes feeding a key claim directly.
        direct = sorted({n["id"] for n in buried
                         for d in adj.get(n["id"], [])
                         if by_id.get(d, {}).get("level") in (0, 1)})
        print("    footnote-only nodes feeding a level-0/1 node directly: %s"
              % (", ".join(direct) if direct else "none"))

    print()
    if failures:
        print("RESULT: FAIL (%d well-formedness failure(s))" % len(failures))
        return 1
    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Minimal YAML-subset parser shared by the validator and the page builder.

python3 stdlib only - PyYAML is deliberately not a dependency, so the skeleton
is written in a strict regular subset of YAML that this parser reads
deterministically:

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
after a value) is not supported and is reported as a ParseError rather than
silently mis-read.

This module is pure: it never exits the process. Callers decide what a parse
failure means for them.
"""

import re


class ParseError(Exception):
    pass


def _scalar(raw, lineno):
    s = raw.strip()
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        body = s[1:-1]
        out, i = [], 0
        while i < len(body):
            c = body[i]
            if c == "\\" and i + 1 < len(body):
                out.append(body[i + 1])
                i += 2
            else:
                out.append(c)
                i += 1
        return "".join(out)
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1].strip()
        if not inner:
            return []
        return [_scalar(p, lineno) for p in inner.split(",")]
    if s in ("true", "false"):
        return s == "true"
    if re.fullmatch(r"-?\d+", s):
        return int(s)
    if s.startswith('"') or s.endswith('"'):
        raise ParseError("line %d: unbalanced quotes in scalar: %s" % (lineno, s))
    return s


def _flow_mapping(body, lineno):
    s = body.strip()
    if not (s.startswith("{") and s.endswith("}")):
        raise ParseError("line %d: expected a flow mapping, got: %s" % (lineno, s))
    out = {}
    for part in s[1:-1].split(","):
        part = part.strip()
        if not part:
            continue
        key, sep, val = part.partition(":")
        if not sep:
            raise ParseError("line %d: flow entry without ':': %s" % (lineno, part))
        out[key.strip()] = _scalar(val, lineno)
    return out


def _folded(lines, i, indent):
    """Fold the block scalar that follows a `key: >-` line into one string."""
    parts = []
    while i < len(lines) and lines[i][1] > indent:
        parts.append(lines[i][2].strip())
        i += 1
    return " ".join(parts), i


def _mapping(lines, i, indent):
    out = {}
    while i < len(lines):
        lineno, ind, text = lines[i]
        if ind < indent:
            break
        if ind > indent:
            raise ParseError("line %d: unexpected indentation" % lineno)
        stripped = text.strip()
        if stripped.startswith("- "):
            break
        key, sep, rest = stripped.partition(":")
        if not sep:
            raise ParseError("line %d: expected 'key: value', got: %s" % (lineno, stripped))
        key = key.strip()
        rest = rest.strip()
        if rest == ">-":
            value, i = _folded(lines, i + 1, indent)
        elif rest == "":
            if i + 1 < len(lines) and lines[i + 1][1] > indent:
                child_indent = lines[i + 1][1]
                if lines[i + 1][2].strip().startswith("- "):
                    value, i = _sequence(lines, i + 1, child_indent)
                else:
                    value, i = _mapping(lines, i + 1, child_indent)
            else:
                value, i = None, i + 1
        else:
            value, i = _scalar(rest, lineno), i + 1
        out[key] = value
    return out, i


def _sequence(lines, i, indent):
    out = []
    while i < len(lines):
        lineno, ind, text = lines[i]
        if ind < indent:
            break
        if ind > indent:
            raise ParseError("line %d: unexpected indentation in list" % lineno)
        stripped = text.strip()
        if not stripped.startswith("- "):
            break
        body = stripped[2:].strip()
        if body.startswith("{"):
            out.append(_flow_mapping(body, lineno))
            i += 1
            continue
        # Block mapping item: re-present the first key at the item's own
        # indentation so the whole item parses as one mapping.
        item_indent = indent + 2
        sub = [(lineno, item_indent, " " * item_indent + body)]
        j = i + 1
        while j < len(lines) and lines[j][1] >= item_indent:
            sub.append(lines[j])
            j += 1
        mapping, _ = _mapping(sub, 0, item_indent)
        out.append(mapping)
        i = j
    return out, i


def load(path):
    with open(path, encoding="utf-8") as fh:
        raw = fh.read().split("\n")
    lines = []
    for lineno, text in enumerate(raw, 1):
        if not text.strip() or text.lstrip().startswith("#"):
            continue
        lines.append((lineno, len(text) - len(text.lstrip(" ")), text.rstrip()))
    doc, i = _mapping(lines, 0, 0)
    if i != len(lines):
        raise ParseError("line %d: trailing content the parser could not place"
                         % lines[i][0])
    return doc

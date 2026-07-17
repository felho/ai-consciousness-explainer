#!/usr/bin/env python3
"""Repo-bounded progress tracker for the AI-consciousness explainer.

Ground truth is the FILESYSTEM, not a hand-maintained status field:
  - a section's explanation is done  <=> explanation.md exists and is non-trivial
  - a link is done                   <=> links/<id>-*/summary.md exists
  - a link is failed                 <=> that summary.md starts with the failure marker
Everything else is pending.

This makes progress independent of any single session: a fresh session runs
`python3 bin/status.py` and sees exactly what is left, regardless of which
session (or killed agent) produced the existing files.

Usage:
  python3 bin/status.py            # human-readable progress table
  python3 bin/status.py --json     # machine-readable state
  python3 bin/status.py --next     # print the next pending section dir (for dispatch)
  python3 bin/status.py --reconcile  # rewrite links.json + manifest.json to match the filesystem
"""
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECTIONS = os.path.join(ROOT, "sections")
FAIL_MARKER = "> Megjegyzés: a forrás tartalma nem volt letölthető"
MIN_EXPLANATION_CHARS = 200  # guard against an empty/stub explanation.md


def link_state(section_dir, link):
    """Return 'done' | 'failed' | 'pending' for one link, from the filesystem."""
    matches = glob.glob(os.path.join(section_dir, "links", f"{link['id']}-*", "summary.md"))
    if not matches:
        return "pending"
    text = open(matches[0]).read()
    if text.lstrip().startswith(FAIL_MARKER) or "fail_reason" in link and text.count(FAIL_MARKER):
        return "failed"
    return "failed" if FAIL_MARKER in text[:400] else "done"


def explanation_done(section_dir):
    p = os.path.join(section_dir, "explanation.md")
    return os.path.exists(p) and len(open(p).read().strip()) >= MIN_EXPLANATION_CHARS


def scan():
    state = []
    for links_path in sorted(glob.glob(os.path.join(SECTIONS, "*", "links.json"))):
        sdir = os.path.dirname(links_path)
        links = json.load(open(links_path))
        link_states = [(l, link_state(sdir, l)) for l in links]
        state.append({
            "dir": os.path.relpath(sdir, ROOT),
            "name": os.path.basename(sdir),
            "explanation_done": explanation_done(sdir),
            "links_total": len(links),
            "links_done": sum(1 for _, s in link_states if s == "done"),
            "links_failed": sum(1 for _, s in link_states if s == "failed"),
            "links_pending": sum(1 for _, s in link_states if s == "pending"),
            "link_states": link_states,
        })
    return state


def is_section_complete(s):
    return s["explanation_done"] and s["links_pending"] == 0


def reconcile(state):
    """Write filesystem-derived statuses back into links.json and manifest.json."""
    for s in state:
        links_path = os.path.join(ROOT, s["dir"], "links.json")
        links = json.load(open(links_path))
        by_id = {l["id"]: l for l in links}
        for link, st in s["link_states"]:
            by_id[link["id"]]["status"] = st
        json.dump(links, open(links_path, "w"), indent=2, ensure_ascii=False)

    manifest_path = os.path.join(ROOT, "manifest.json")
    manifest = json.load(open(manifest_path))
    by_dir = {s["dir"]: s for s in state}
    for sec in manifest["sections"]:
        s = by_dir.get(sec["dir"])
        if not s:
            continue
        sec["explanation_status"] = "done" if s["explanation_done"] else "pending"
        sec["links_done"] = s["links_done"]
        sec["links_failed"] = s["links_failed"]
        sec["links_pending"] = s["links_pending"]
        sec["complete"] = is_section_complete(s)
    json.dump(manifest, open(manifest_path, "w"), indent=2, ensure_ascii=False)
    print("Reconciled links.json (all sections) + manifest.json to filesystem state.")


def main():
    args = set(sys.argv[1:])
    state = scan()

    if "--reconcile" in args:
        reconcile(state)
        return

    if "--json" in args:
        for s in state:
            s.pop("link_states", None)
            s["complete"] = is_section_complete(s)
        print(json.dumps(state, indent=2, ensure_ascii=False))
        return

    if "--next" in args:
        for s in state:
            if not is_section_complete(s):
                print(s["dir"])
                return
        print("")  # nothing pending
        return

    # Human-readable table
    print(f"{'section':52s}  expl  links (done/failed/pending)")
    print("-" * 88)
    tot_done = tot_fail = tot_pend = 0
    complete_sections = 0
    for s in state:
        tot_done += s["links_done"]
        tot_fail += s["links_failed"]
        tot_pend += s["links_pending"]
        complete_sections += is_section_complete(s)
        flag = "OK " if is_section_complete(s) else "   "
        expl = " Y " if s["explanation_done"] else " . "
        print(f"{flag}{s['name']:49s}  {expl}  {s['links_done']:2d}/{s['links_failed']:2d}/{s['links_pending']:2d}"
              f"  of {s['links_total']}")
    print("-" * 88)
    print(f"sections complete: {complete_sections}/{len(state)}   "
          f"links done: {tot_done}  failed: {tot_fail}  pending: {tot_pend}")


if __name__ == "__main__":
    main()

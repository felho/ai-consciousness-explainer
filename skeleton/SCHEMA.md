# Reasoning-skeleton schema — v0

A structured intermediate representation of a text's reasoning: what each
section claims, what those claims rest on, and how they connect into the
text's overall argument. One representation, multiple consumers (arc
visualization, spaced-repetition cards, a voice tutor, a quality metric) —
this file defines the representation; consumers are out of scope.

**Status: v0 draft.** Deliberately cheap; it exists to be collided with the
AI-consciousness essay in this repo and revised by what that collision
teaches. Validation target: the owner can reconstruct and explain the
essay's argument from the skeleton alone.

## Design constraints (why the schema looks like this)

1. **Chunk-sized.** A section's key claim is the *label* of that section's
   chunk; the sub-claims are its contents. Substructures stay at 3–5 nodes
   (working-memory capacity is ~4±1, Cowan 2001) — a section that needs
   more is either two chunks or over-decomposed.
2. **Grounded.** Every node that the text actually states carries at least
   one verbatim quote anchor. A node the text *needs but never states*
   (a bridging assumption, an unstated warrant) is marked `interpolated` —
   permitted, but counted. The interpolation count is the future quality
   metric's raw signal, and the guard against an LLM hallucinating
   coherence into a text.
3. **DAG, not outline.** Reading order is linear; logical dependency is
   not. Nodes nest by section (the outline), edges cross sections freely
   (the argument).
4. **Self-contained labels.** A label must be understandable with the
   book closed: one sentence, no pointer-style references ("this", "the
   above principle"), no terms the label itself doesn't carry. Labels are
   what the visualization shows and what review cards are generated from.

## The model

A skeleton is one YAML document per text:

```yaml
text:
  title: "..."
  source: "https://..."
  sections: ["00", "01", ...]   # reading order; ids match sections/<id>-*/

nodes:
  - id: s01-claim               # unique; convention: <section>-<slug>, thesis: "thesis"
    level: 1                    # 0 thesis · 1 section key claim · 2 sub-claim
    kind: claim                 # claim | ground | warrant | qualification | rebuttal | definition | implication
    section: "01"               # owning section ("" for the level-0 thesis if global)
    label: >-
      One self-contained sentence stating the point.
    anchors:                    # verbatim substrings of that section's section.md
      - section: "01"
        quote: "exact text copied from the source"
    interpolated: false         # true = needed by the argument, absent from the text

edges:
  - {from: s01-genome, to: s01-claim, type: supports}
```

### Node kinds (Toulmin-derived, collapsed)

| kind | Toulmin | meaning |
|---|---|---|
| `claim` | claim | an assertion the argument advances |
| `ground` | grounds/data | evidence or fact offered in support |
| `warrant` | warrant | the bridge licensing ground→claim; *typically interpolated* |
| `qualification` | qualifier | scope limit ("mostly", "in this sense") |
| `rebuttal` | rebuttal | an objection the text raises or answers |
| `definition` | — | a term the argument depends on |
| `implication` | — | a consequence drawn, not itself defended |

### Edge types

`supports` (ground/claim → claim) · `elaborates` (adds detail, not force) ·
`qualifies` (limits scope) · `rebuts` (opposes) · `presupposes` (needs the
target already established — the cross-section dependency workhorse).

## Well-formedness rules (v0, all machine-checkable)

- R1 · Exactly one `level: 0` node (the thesis).
- R2 · Exactly one `level: 1` node per section — the key sentence.
- R3 · 3–5 `level: 2` nodes per section (soft: warn outside the range).
- R4 · Every node with `interpolated: false` has ≥1 anchor, and every
  anchor's `quote` is a verbatim substring of `sections/<id>-*/section.md`.
- R5 · Edges form a DAG over nodes.
- R6 · Every `level: 1` node reaches the thesis via edges (the arc is
  connected); every `level: 2` node reaches its section's `level: 1` node.
- R7 · `interpolated: true` nodes carry no anchors (if you can quote it,
  it isn't interpolated).

## Prior art, and where this deliberately diverges

- **AIF** (Argument Interchange Format): arguments as typed directed
  graphs of I-nodes (information) and S-nodes (reified inference/conflict/
  preference schemes). We keep the typed digraph, and **collapse S-nodes
  into typed edges**: AIF reifies schemes because it feeds inference
  engines; this schema feeds a human's reading and recall, where a
  first-class scheme node is ceremony. Revisit only if edge types prove
  too coarse in practice.
- **Toulmin** (claim–ground–warrant–backing–qualifier–rebuttal): the node
  `kind` vocabulary, minus `backing` (fold into `ground` at this grain).
  Toulmin's known lesson — warrants are usually unstated — is what the
  `interpolated` flag operationalizes.
- **Mnemonic medium** (Matuschak/Nielsen): not used in the schema itself;
  labels + anchors are designed to be sufficient input for prompt
  generation later, which is the point of R4 and constraint 4.
- **Divergence log** (anchoring guard): consumers may not add fields here
  casually — a consumer that needs more than labels, anchors, levels and
  edges must argue the field into this spec first.

## What each consumer reads (requirements trace)

| consumer | reads |
|---|---|
| arc visualization | section order + level-1 labels (the rail); level-2 + edges (the expansion) |
| card generation | labels + anchors (front/back material), edges (context) |
| voice tutor | labels (question targets), edges (follow-up probes) |
| quality metric | count of `interpolated` nodes + R4/R6 violations (scaffolding needed) |

## Open questions for the validation run

- Is one key sentence per section honest, or do some sections carry two
  irreducible claims (R2 stress test)?
- Are five edge types enough, or does the essay force distinctions
  (e.g. analogy — sections argue brain↔ANN parallels heavily)?
- Do footnotes need to be anchorable as first-class sources, or do they
  stay inside their section's anchor space?
- Where does the *Hungarian explanation layer* attach, if anywhere — the
  skeleton is of the original text, but the explainer page may want to
  render labels bilingually.

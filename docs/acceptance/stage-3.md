# Stage 3 Acceptance: Publication Compiler and SVG

Status: complete for the requested SVG/HTML milestone.

Stage 3 compiles one Exact Architecture IR into four provenance-preserving Publication Views, a
semantic VisualSpec, deterministic VisualScenes, canonical SVG, and self-contained read-only HTML.
The compiler never changes Architecture IR and excludes reference-only nodes from the executable
publication graph.

## Delivered contracts

- L1 preserves model identity, primary spine, branch/merge, repeat, memory, state, and condition
  relationships through canonical ID mappings.
- L2 retains module grouping and cross-module relationships.
- L3 exposes semantic operators and shape-bearing edge roles.
- L4 is exactly one visible node and edge per executable canonical node and edge.
- Direct L4 and progressive L1-L4 compilation expose identical canonical node, edge, tensor, and
  port sets.
- VisualSpec owns semantic glyph, fill, stroke, dash, and label choices; VisualScene alone owns
  geometry and routes.
- SVG contains no viewer chrome, gradients, filters, hover state, or external resources.
- HTML embeds that exact SVG and adds local pan/zoom, search, focus, upstream/downstream reachability,
  theme, canonical IDs, and evidence inspection without modifying graph semantics.

## Layout families

| Profile | Layout family |
| --- | --- |
| Transformer L3, Autoformer | `dual-lane` |
| iTransformer | `single-lane` |
| PatchTST | `dual-backbone` |
| TimeMixer | `multiscale-ladder` |
| Pattern-free and unknown models | `generic-dag` |

The generic compiler and renderer pass with all model-specific pattern packs disabled. Opaque
composites remain neutral closed boundaries with canonical provenance and are never visually
expanded with invented internals.

## Deterministic gates

Gate C checks exact canonical set equality, one-time visible/collapsed coverage, valid containment
and endpoints, input-to-output finger tracing, L4 one-to-one expansion, and exclusion of executable
duplicates. Gate D checks paper bounds, containment, node overlap, 125% node-label capacity,
collision-free edge-label placement, orthogonal port direction, route bounds, complete-route
ambiguity, semantic edge styles, and edges crossing unrelated opaque nodes.

Five specialized profiles pass Gate C and Gate D at L1-L4. The same five fixtures, re-analyzed with
`--no-pattern-packs`, pass Gate C and Gate D through `generic-dag` output. Mutation tests prove that a
missing canonical mapping, node overlap, and edge-through-opaque geometry fail their gates.

## Visual review record

Review date: 2026-09-23. Reviewer: image-capable Codex browser review. Result: passed for the SVG/HTML
scope below.

Reviewed artifacts included Transformer L1 and L4, Autoformer L1, PatchTST L1, TimeMixer L1, and
pattern-free Transformer L1. Browser checks covered 1440x900, 1280x800, a narrow viewport, and a
1024x640 layout equivalent to the CSS viewport available at 125% of 1280x800. Gate D independently
checks every label using 125% text metrics. Search selection, canonical/evidence inspector,
pan/zoom controls, responsive inspector overlay, and nonblank SVG rendering were exercised.

Two targeted corrections were made and all deterministic gates were rerun:

1. L1/L2 ordinary flow labels were suppressed while memory, condition, state, and parameter-share
   labels remain visible; L3/L4 labels gained collision-free placement and wider fact corridors.
2. The narrow toolbar was compacted so the document has no horizontal overflow and all controls
   remain accessible.

The render command intentionally records Gate E as `skipped`: artifact generation cannot claim a
human/image review. This acceptance record is the separate review evidence for the inspected build.

## Commands

```bash
archcanvas render build/model/architecture.json --view all --out build/model/publication --json
archcanvas validate build/model/architecture.json --quality publication --json
```

Each selected level emits `publication-view.json`, `visual-spec.json`, `visual-scene.json`,
`scene.svg`, and `view.html`, plus one machine-readable `render-receipt.json`.

PNG and PDF derivation, editable Studio behavior, and source transactions remain unavailable and are
not claimed by this milestone. Runtime evidence remains opt-in and is recorded as `skipped` unless
separately authorized.

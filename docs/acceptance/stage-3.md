# Stage 3 Acceptance: Publication Compiler and SVG

Status: complete for the requested SVG/HTML milestone.

Stage 3 compiles one Exact Architecture IR into a provenance-preserving, arbitrary-depth
PublicationHierarchy and deterministic frontier projections, VisualSpecs, VisualScenes, canonical
SVG, and self-contained read-only HTML.
The compiler never changes Architecture IR and excludes reference-only nodes from the executable
publication graph.

## Delivered contracts

- Collapsed frontier preserves model identity and cross-container relationships through canonical IDs.
- Each real or derived owner adds a containment level without a depth cap.
- Fully expanded frontier contains exactly one visible node and edge per executable canonical node
  and edge; every partial frontier preserves the same canonical node, edge, tensor, and port sets.
- VisualSpec owns semantic glyph, fill, stroke, dash, and label choices; VisualScene alone owns
  geometry and routes.
- SVG contains no viewer chrome, gradients, filters, hover state, or external resources.
- HTML embeds that exact SVG and adds local pan/zoom, search, focus, upstream/downstream reachability,
  theme, canonical IDs, and evidence inspection without modifying graph semantics.
- Studio left navigation provides two persisted projections of the same graph: `模块关系` follows
  Exact IR containment and producer outputs, while `源码关系` follows the source file tree, lexical
  definitions, control scopes, and callsites. Every row carries canonical/evidence bindings, so
  selecting an object in either projection selects the same canvas object. The tree is also the
  sole detail controller: its exact expanded-node set deterministically compiles the current scene.

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
and endpoints, input-to-output finger tracing, full-frontier one-to-one expansion, and exclusion of executable
duplicates. Gate D checks paper bounds, containment, node overlap, 125% node-label capacity,
collision-free edge-label placement, orthogonal port direction, route bounds, complete-route
ambiguity, semantic edge styles, and edges crossing unrelated opaque nodes.

Five specialized profiles pass Gate C and Gate D for collapsed and full frontiers. The same five fixtures, re-analyzed with
`--no-pattern-packs`, pass Gate C and Gate D through `generic-dag` output. Mutation tests prove that a
missing canonical mapping, node overlap, and edge-through-opaque geometry fail their gates.

## Visual review record

Review date: 2026-09-23. Reviewer: image-capable Codex browser review. Result: passed for the SVG/HTML
scope below.

Reviewed artifacts included collapsed and fully expanded Transformer plus collapsed Autoformer,
PatchTST, TimeMixer, and pattern-free Transformer projections. Browser checks covered 1440x900, 1280x800, a narrow viewport, and a
1024x640 layout equivalent to the CSS viewport available at 125% of 1280x800. Gate D independently
checks every label using 125% text metrics. Search selection, canonical/evidence inspector,
pan/zoom controls, responsive inspector overlay, and nonblank SVG rendering were exercised.

Two targeted corrections were made and all deterministic gates were rerun:

1. Collapsed ordinary flow labels were suppressed while memory, condition, state, and parameter-share
   labels remain visible; deeper frontiers gained collision-free placement and wider fact corridors.
2. The narrow toolbar was compacted so the document has no horizontal overflow and all controls
   remain accessible.

The render command intentionally records Gate E as `skipped`: artifact generation cannot claim a
human/image review. This acceptance record is the separate review evidence for the inspected build.

## Commands

```bash
archcanvas render build/model/architecture.json --view all --out build/model/publication --json
archcanvas validate build/model/architecture.json --quality publication --json
```

Each selected projection emits `publication-view.json`, `visual-spec.json`, `visual-scene.json`,
`scene.svg`, and `view.html`, plus one machine-readable `render-receipt.json`.

At this historical Stage 3 checkpoint, PNG/PDF derivation, editable Studio behavior, and source
transactions were not claimed. The current Stage 9 tree now derives PNG and PDF from the same
canonical SVG; later acceptance records own those capabilities. Runtime evidence remains opt-in and
is recorded as `skipped` unless separately authorized.

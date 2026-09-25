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

## Evidence-derived visual relations

Canonical `EdgeType` remains unchanged. Publication adds a separate `VisualRelation` projection so
diagram grammar cannot rewrite Exact IR semantics. The compiler derives `sequence`,
`parallel-branch`, `merge`, `residual`, `shape-transform`, `memory-reference`, `condition`,
`routing`, `state-update`, `parameter-share`, and `training-only` from canonical edge types,
fan-out/fan-in, target node kinds, and source-backed operation attributes.

The same relation, glyph, route, label, and shape data drives Studio and exported SVG. Containers
show containment; fan-out targets share a rank; merge events remain explicit; residual edges use an
outer corridor; tensor transforms use a separate glyph; projection, activation, normalization,
attention, condition, tensor, merge, repeat, state, I/O, and opaque nodes remain visually distinct.
Tensor shape stays attached to the corresponding edge label. Repeat stacks and counts are shown
only when an Exact IR `Repeat` exists. No reference architecture can create a module, edge, repeat,
or shape absent from source, configuration, runtime evidence, or Exact IR.

## Layout families

Layout is inferred from the compiled containment tree and the cross-stage producer/consumer
topology. `architecture_profile`, fixture names, entrypoint names, and Pattern Pack layout hints
are never used as model-specific switches. A linear two-stage topology uses `single-lane`; a
branched, fan-in, or multi-stage topology uses the reusable `dual-lane` swimlane grammar. The
same planner is applied to current Tier A models, cross-framework IR, pattern-free analysis, and
unseen holdouts. Pattern Packs still contribute semantic roles and glyph hints, but do not choose
the final layout family.

Studio also exposes a persisted presentation-only layout selector. `Auto` retains the inferred
topology above; users can instead choose `Dual swimlane`, `Single lane`, `Hierarchical DAG`, or
`Branch tree`, plus manual `Force directed`, `Radial`, and `Orthogonal` layouts. `Auto` remains
conservative and does not select force or radial placement for a directed model pipeline. A
selection recompiles only VisualScene geometry and never changes Exact IR,
PublicationView identity, evidence bindings, or canonical node/edge IDs. Existing visual patches
remain overlaid on the regenerated baseline, so layout history is not silently discarded.

The built-in set follows established graph-layout families rather than model-name profiles:

- Eclipse Layout Kernel's layered algorithm targets directed graphs, block diagrams, and explicit
  ports; this is the basis for the hierarchical DAG and swimlane choices.
- ELK's Mr. Tree algorithm provides the containment-oriented branch-tree precedent.
- Graphviz distinguishes layered `dot`, spring/force `neato` and `fdp`, circular `circo`, radial
  `twopi`, and clustered `osage` engines. ArchCanvas therefore exposes force and radial placement
  as explicit exploratory choices while keeping directed topology as the automatic default.
- The yWorks layout showcase describes orthogonal layout as compact and suitable for sparse
  small-to-medium graphs, and radial layout as concentric graph layers. ArchCanvas keeps nested
  compounds rigid in these modes, then reroutes cross-compound edges through stable boundary
  ports so a layout change cannot scramble a module's internal structure.
- Force placement uses a deterministic circular seed and fixed iteration count. Radial placement
  uses deterministic graph ranks and angular order. Orthogonal placement uses rank-aligned rows.
  All three preserve the exact scene node/edge identifiers and pass the same geometry gate.

Research references: <https://graphviz.org/docs/layouts/>,
<https://eclipse.dev/elk/reference/algorithms.html>, <https://github.com/kieler/elkjs>, and
<https://www.yworks.com/pages/interactive-showcase-of-graph-layouts>.

The root overview is also inferred rather than copied from a model profile. Input preparation,
normalization/embedding, processing backbones, decomposition/state branches, and output
postprocessing are grouped into a concise first frontier; the original modules remain available
as arbitrarily deep children in the expanded publication. Opaque composites remain neutral closed
boundaries with canonical provenance and are never visually expanded with invented internals.

## Deterministic gates

Gate C checks exact canonical set equality, one-time visible/collapsed coverage, valid containment
and endpoints, input-to-output finger tracing, full-frontier one-to-one expansion, and exclusion of executable
duplicates. Gate D checks paper bounds, containment, node overlap, 125% node-label capacity,
collision-free edge-label placement, orthogonal port direction, route bounds, complete-route
ambiguity, semantic edge styles, and edges crossing unrelated opaque nodes.

Five Tier A models pass Gate C and Gate D for collapsed and full frontiers. The same fixtures,
cross-framework fixtures, and a custom holdout pass with Pattern Packs disabled. Regression tests
also rename the root architecture and replace its profile value while requiring the same inferred
family and root-stage structure. Mutation tests prove that a missing canonical mapping, node
overlap, and edge-through-opaque geometry fail their gates.

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

Visual-relation addendum, 2026-09-25: the collapsed Transformer, expanded encoder, and expanded
encoder/key projection were checked in the live Studio against the supplied Transformer and hybrid
architecture references. Review covered containment, Q/K/V branching, merge and residual routes,
transform glyphs, shape labels, relation legend, tree/canvas synchronization, and reduced-motion
compatibility. The references supplied visual grammar only; source-unproven modules were not added.

Layout and control addendum, 2026-09-25: a collapsed and fully expanded iTransformer was inspected
in the live Studio with force-directed, radial, and orthogonal placement. Each mode retained its
compound hierarchy, routed arrows to the correct source and target, and reported zero geometry
problems from a clean layout baseline. The review also covered layout switching, fit and focus,
light/dark themes, English/Chinese interface switching with English edge labels, folder browsing,
folder selection, path/Scan alignment, auto-route response, and Auto layout recovery after a manual
node displacement. Disabled controls were limited to state-dependent actions such as undo, redo,
multi-selection alignment, and leaf expansion.

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

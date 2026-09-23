# Stage 4 Acceptance: Studio Visual Editing

Status: complete for visual-only editing.

Stage 4 delivers a React/TypeScript/Vite Studio over the same PublicationView, VisualSpec, and
VisualScene compiler used by canonical SVG export. It does not add a second graph model. Every
layout action is persisted as a validated VisualPatch in a CanvasDocument, while Exact IR and model
source remain authoritative and unchanged.

## Delivered Studio

- Three-column workbench with model/view/tensor navigation, central paper canvas, and Inspector.
- Top modes for Explore, Layout, and Model. Explore selects and expands, Layout edits geometry, and
  Model exposes the future semantic surface while keeping source changes hard-disabled.
- L1-L4 switching and `Open full` to the exact L4 canonical set.
- Node selection with a 2px selection boundary, visible ports, breadcrumb, and context controls.
- Inspect, Visual, Model, and Evidence tabs. Visual and Model fields are separate.
- Source-backed evidence records with paths, lines, claims, and confidence.
- Drag, numeric geometry, pin, collapse/expand, theme, zoom, validation, and canonical SVG export.
- Bottom Problems, Source Diff, Validation, and Activity surfaces.
- Responsive narrow layout with the Inspector as an overlay.

The Model tab reports `Source editing unavailable`; its `Prepare change` action is disabled. Stage 4
does not implement or imply Stage 6 source transactions.

## Persistence and history

CanvasDocument now carries base scene IDs, applied patches, a redo stack, and selection-independent
view state. Theme and per-scene camera state are derived from patch history and restored on reopen.
Patch application validates scene and target identities, finite numeric geometry, and
operation-specific values.
Undo moves the latest patch to the redo stack; redo restores it; a new patch clears redo. Documents
are written by atomic replacement under `.archcanvas/documents/`.

Materialization starts from the deterministic base VisualScene and applies only visual operations.
No-patch materialization preserves the base scene exactly. A position or size patch reroutes only
incident edges; explicit route hints remain authoritative. Export calls the same canonical
`render_svg()` function over that materialized scene.

On reopen, Studio rejects a document if its architecture ID, source snapshot ID, source-binding
digest, or base scene IDs are stale. The source-binding digest covers revision, entrypoint, task,
mode, config digest, source paths, and source file hashes.

## Local boundary

`archcanvas studio` prepares a self-contained frontend bundle and one machine-readable receipt.
`--serve` starts the persistence API only on `127.0.0.1`, `localhost`, or `::1`; non-loopback binds
are rejected. The API accepts VisualPatch, undo, redo, state, and SVG export operations only.

```bash
archcanvas studio build/model/architecture.json \
  --workspace build/model/.archcanvas \
  --serve \
  --host 127.0.0.1 \
  --port 4310 \
  --json
```

## Exit gates

Automated tests prove:

- visual patch, undo, and redo preserve the source digest;
- an unknown scene or target is rejected;
- persisted geometry is identical after reopening the CanvasDocument;
- the Studio API persists patch/undo/redo and exports canonical SVG;
- CLI preparation emits one receipt and a frontend with no external resources;
- all materialized L1-L4 scenes continue to pass Gate D;
- fixture source hashes are unchanged after the complete editing workflow.

Browser review on 2026-09-23 exercised the desktop workbench, selection, Evidence Inspector, Layout
drag persistence, Source Diff, undo/redo, `Open full`, and the locked Model Inspector. It also
verified theme, zoom, and pan recovery after reload; per-level selection recovery; and that dragging
in Model mode still creates only a visual position patch. A 390x844 viewport was checked with the
Inspector overlay active. The final desktop and narrow layouts were nonblank and had no incoherent
UI overlap or document-level horizontal overflow.

Runtime evidence, parameter editing, source diff generation, prepare/verify/commit transactions,
and structural transforms remain unavailable for their designated later stages.

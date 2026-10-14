# Studio preview integration

The preview is a complete local copy of `Summary_Merge`. All 230 catalog cases
(115 current and 115 historical), 666 source views, snapshots, source files and
audit evidence are shipped in this directory. Runtime URLs never reference the
original prototype checkout. `vendor-manifest.json` records the original bytes;
`integration-manifest.json` records the Studio-specific changes.

Open `yworks_edge_router_lab/index.html` to use the full standalone editor.
The Studio embeds `index.html?embed=1&surface=canvas`. This surface shows the
canvas and editing toolbar. The original catalog and routing controls remain
available as dismissible drawers, opened from the Studio's folded menus. Source
import and evidence dialogs also retain their original controls.

## Message contract

All messages use `{type: 'archcanvas:preview:<command>', requestId?, ...payload}`.
The child accepts commands only from `window.parent` on the same origin, and
sends replies to that exact origin. It serializes asynchronous commands.
Messages do not write Python source, change model parameters or approve edits.

| Command | Payload | Reply |
| --- | --- | --- |
| `hello`, `ping` | none | `ready` with version and capabilities, then `state` |
| `load` | `bundle`: verified source adapter or recursive editing JSON | `loaded`, then `state` |
| `snapshot` | none | `snapshot` with `document` |
| `request-source` | none | `source` with `source`, optional `bundle`, and `document` |
| `focus` | `nodeId`, `annotationId`, or `sourcePath` and `line` | `focused` with selection |
| `save` | none | `saved` after IndexedDB completes |
| `svg` | optional visible `nodeId` | `svg` with `svg` and `xml` strings |
| `export-svg`, `export-json` | none | starts existing download flow, then `exported` |
| `visual` | `operations` | `applied`, then `state` |
| `set-frontier` | `locations`/`sourceLocations`, `expanded` | `applied`, then `state` |
| `show-library`, `show-routing` | none | opens original drawer |
| `show-import`, `show-evidence` | none | opens original dialog |
| `undo`, `redo`, `fit`, `apply-layout`, `collapse-all`, `expand-all` | none | invokes original operation |
| `zoom` | `factor` | updates camera |
| `select-tool`, `connect-tool`, `bend-tool`, `pan-tool` | none | selects original editing tool |
| `show-ports`, `grid` | optional `visible`/`enabled` | updates display setting |

Replies retain `requestId`. Validation failures return `error` with `command`
and `message`. Cases without model source return `source-unavailable`; the
parent must retain their own identity and never reuse the previous model source.

The child also publishes `selection` and `state` when users operate it directly.
`selection` includes `caseId`, `nodeIds`, `edgeIds`, `selectedNodes`,
`selectedEdges`, `node`, `edge`, `annotationId`, `annotation`, `sourcePath`, `line`, `span` and source evidence.
Studio annotations support direct selection and dragging. One gesture adds one
undo step, persists through recursive rebuilds, and changes only presentation.
AST columns are UTF-8 byte offsets. `state.document` has schema
`summary-merge-recursive/1`, `caseId`, `title`, `collection`, `dirty`,
`canUndo`, `canRedo`, `sourceAvailable`, selection and the complete graph,
including its recursive authority. Imported source documents also include the
verified `adapter` bundle. The parent should keep the iframe mounted when the
source editor is displayed to retain camera and undo history.

Catalog source replies use this shape:

```json
{
  "schema": "archcanvas-preview-source/1",
  "caseId": "catalog case identity",
  "title": "model title",
  "entry": "project.model:ModelClass",
  "files": {"project/model.py": "Python source text"},
  "evidence": {"E001": {"file": "project/model.py", "line": 1,
      "endLine": 10, "expression": "source text", "column": 0, "endColumn": 0}},
  "profile": {}
}
```

File bytes are SHA256 checked against `data/catalog-sources.json` before sending.
This source index exposes 223 of 230 cases. The remaining cases are a routing
experiment and teaching-only residual SVGs, which do not claim a model binding.
Having source evidence does not enlarge either parser's supported semantics.

## Shared visual operations

The parent maps its formal object identities to preview identities using source
evidence and module instance identity. `visual.operations` accepts `title`,
`alias`, `nodeStyle`, `edgeStyle`, `nodeLayout`, `move`, `expand`, `pin`, `legend`,
`annotation`, `removeAnnotation`, `portLayout`, `syncPresentation` and `page`, using the formal Studio operation
field names. `nodeLayout.position.x/y` are world coordinates. `move` uses world
displacements. `current-frontier` moves affect the present frontier; other moves
also retain offsets for descendant frontiers. Every batch is atomic and shares
the original preview's undo history. Unknown identities and illegal layouts fail
without committing a batch. `portLayout` resets the matched visible owner's
incident physical ports when `layout` is null; explicit side/offset values must
pass the source interface, port spacing and routing constraints. Canonical
port fields and producer/consumer bindings remain unchanged. When distinct
semantic ports cannot share a requested position the batch fails; native
per-edge port controls remain available. Formal port names are not guessed
across different parser IRs.

`syncPresentation` receives mapped `nodes` and `edges` dictionaries plus a full
`title`, `legend`, `annotations` array and `page`. It replaces formal presentation
fields on the mapped objects, restoring original source edge defaults when an
override is cleared. It retains preview-only sizing, unmapped objects and draft
edge styles. This lets formal history and source editing update the same canvas.

Independent new connections and reconnected source connections remain visual
drafts. A source draft retains its original projection and canonical binding;
marking a forged connection as a draft cannot bypass source identity checks.
An un-routed visual draft may keep invalid geometry while being styled, saved,
exported or restored. It remains marked invalid in the preview and requires
Apply for legal routing. Original source edges, layout and source metadata are
always validated. Geometry edits still require the complete route checks.

Style and text changes are stored outside the audited source glyphs:

```json
{
  "version": 1,
  "nodes": {"previewId": {"alias": "Caption", "fill": "#ffffff",
    "stroke": "#334155", "glyph": "module", "pinned": false}},
  "edges": {"edgeId": {"stroke": "#64748b", "width": 2, "dashed": false}},
  "annotations": {"annotationId": {"id": "annotationId", "text": "Note",
    "x": 40, "y": 40, "width": 380}},
  "legend": [{"id": "legendId", "label": "Module", "color": "#ffffff",
    "glyph": "module"}],
  "page": {"widthMm": 180, "background": "#ffffff", "preset": "paper"}
}
```

The value is available as `graph.studioPresentation` and
`graph.recursive.state.studioPresentation`; the recursive state is authoritative
after an expansion rebuild. It persists in browser storage and editing JSON,
restores with undo/redo, and appears in SVG export. Binary source glyph aliases
replace their captions while preserving the actual `+`/`×` symbol. Their sizes
remain protected by source contracts. Layout changes undergo the original
source, containment, obstacle and route validation before committing.

## Verification

`studio/scripts/test-preview-bridge.mjs` launches an isolated browser and covers
ready/identity, drawer visibility, catalog source entry/evidence, full authority,
source immutability, overlays, undo/redo, selection navigation, SVG export,
save/restore, tampered JSON rejection and sender isolation. The browser module
and executable can be passed through `--playwright` and `--chromium`; `--base`
selects the development service. `--output` records the verification result.

`studio/scripts/vendor-summary-preview.py --source <Summary_Merge> --target
studio/public/preview` refreshes copied material and the source index. Existing
customized `app.js`, `index.html` and `graph-engine.js` are retained. No vendoring tool or original
prototype source is needed for runtime or distribution builds.

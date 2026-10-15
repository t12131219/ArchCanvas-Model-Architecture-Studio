# Studio preview integration

The preview is a complete local copy of `Summary_Merge`. All 230 catalog cases
(115 current and 115 historical), 666 source views, snapshots, source files and
audit evidence are shipped in this directory. Runtime URLs never reference the
original prototype checkout. `vendor-manifest.json` records the original bytes;
`integration-manifest.json` records the Studio-specific changes.

Open `yworks_edge_router_lab/index.html` to use the full standalone editor.
The Studio embeds `index.html?embed=1&surface=canvas`. This surface shows the
canvas; tools, history, reset, save and export use the retained Studio toolbar.
Middle-button dragging pans over nodes, connections, labels and empty canvas
without changing the editing tool, selection or undo history. The original
catalog and routing controls remain
available as dismissible drawers, opened from the Studio's folded menus. Source
import and evidence dialogs also retain their original controls. The drawer
retains the optional previous-route and obstacle overlays. Zoom buttons and
fit-to-width remain on the canvas; full fit uses Studio's single top control.

## Message contract

All messages use `{type: 'archcanvas:preview:<command>', requestId?, ...payload}`.
The child accepts commands only from `window.parent` on the same origin, and
sends replies to that exact origin. It serializes idle mutations; snapshots,
source reads and handshake replies can read committed state during a pending
load. Mutations reject while a load or gesture is busy.
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
| `undo`, `redo`, `reset`, `fit`, `apply-layout`, `collapse-all`, `expand-all` | none | invokes original operation; reset restores the initial view and is undoable |
| `zoom` | `factor` | updates camera |
| `select-tool`, `connect-tool`, `bend-tool` | none | selects the tool and publishes the actual tool state |
| `pan-tool` | none | available only on the standalone/non-canvas surface |
| `show-ports`, `grid` | optional `visible`/`enabled` | updates port or canvas-grid display; the routing candidate-grid setting remains independent |
| `arrange-selection` | `kind`: `left`, `hcenter`, `right`, `top`, `vcenter`, `bottom`, `distribute-x`, or `distribute-y`; optional `scope` | arranges actual selected visible sibling nodes as one validated undo step |
| `pin-selection` | optional boolean `pinned` (otherwise toggles the selected set) | fixes or unlocks direct movement of the actual selected visible nodes |

Replies retain `requestId`. Validation failures return `error` with `command`
and `message`. Cases without model source return `source-unavailable`; the
parent must retain their own identity and never reuse the previous model source.

The child also publishes `selection` and `state` when users operate it directly.
State and its document expose `tool`, `showPorts` and `gridVisible`; state also
exposes `busy` (including an active gesture) and `dragging`. V/C/B choose tools
and F fits the canvas from either toolbar focus context. Native Ctrl/Cmd+Z and
redo shortcuts operate the child history once and publish the resulting counts.
Ctrl/Cmd+S in the canvas surface emits `shortcut` with `{action: 'save'}` so the
parent's unified save workflow performs both browser and Studio persistence.
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

The toolbar arrangement commands use the preview's own selected node IDs and
world coordinates, including nodes without a formal source mapping. Alignment
requires two or more independent sibling nodes; equal-gap distribution requires
three or more. Branch junctions, mixed containers, overlaps, and unreachable
requested positions fail atomically. Alignment uses pinned nodes as anchors;
conflicting pinned anchors and distribution with pinned nodes are rejected.
An already satisfied arrangement or pin state does not add an undo step.
Pinning blocks direct dragging and arrangement of that node. It still follows
its parent container and recursive layout changes. Selected pinned nodes show
an editor-only lock badge; badges and tooltips are absent from exported SVG.

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
customized `app.js`, `index.html`, `graph-engine.js`, `recursive-graph.js`,
`router.js`, `semantic-constraints.js` and `routing-worker.js` are retained. The integration-only
`frontier-task.js` is also included in the standalone build. No vendoring tool or original
prototype source is needed for runtime or distribution builds.

Recursive expansion runs as one isolated Worker transaction: the transition,
frontier construction, routing and complete source/layout/edge validation finish
before the committed graph and undo history change. Worker-unavailable fallback
uses the same task helper. A no-op preserves both history stacks; a rejected
transaction leaves the prior graph intact. The renderer reuses that validation
instead of validating the graph again on the main thread. Studio projects the
completed snapshot into its panels and editor document without replaying the
legacy formal layout. The source authority remains immutable.

Presentation version 18 rebuilds old cached frontiers on load while retaining
the open tree, manual offsets, captions and visual drafts. Exact source views
and mixed-depth layouts normalize shared stems and licensed interface lanes
under the same constraints. Fully validated local route repairs are retained
instead of being sent through a second visibility search.

Expanded headings and glyph captions are route obstacles and validation
invariants, including for drag, saved-state recovery and explicit routing.
Mixed sibling columns retain centers explicitly shared by their source
templates. External leaf helpers follow an unambiguous common recorded owner
interface side when their current side is opposite; ambiguous interfaces and
colliding placements retain their source layout. Manual offsets apply last.
Mixed frontiers reserve frame corridors for the actual visible independent
source-backed boundary wires; shared values consume one lane. Registered
frontiers retain their original geometry.
A content axis overrides asymmetric frame centering only for an explicitly
recorded shared-value fanout across a centered boundary with an actual centered
terminal from a genuine producer. A frame's own input proxy cannot authorize
moving its outline. Single-wire pipelines and distinct tuple slots retain their
recorded frame alignment; source names and case IDs never select the rule.
Optional shortening and free-lane cleanup compare deduplicated contacts between
independent wires, including touches at internal bends. Segment subdivisions
do not change that count. Shared source values and licensed complete shared
presentations remain excluded; port contracts govern coincident true terminals.
Bounded blocker lanes and local doglegs retain licensed gate approaches.
Optional shortening and parallel separation require complete source, port,
gate, wire, caption, ordered waypoint and junction validation; they cannot add
unrelated crossings or worsen crowded parallel lanes. The optional cleanup
shares a graph-wide validation budget and caches its completed presentation.
After all normal lane shifts and shortening, at most 16 short-band candidates reuse neighboring
fixed value slots' terminal neighborhoods. A candidate must reduce crowding
without increasing contacts, crossings, bends or path length; the same complete
validation and waypoint guards apply. The number and total length of near-parallel
runs cannot increase, and their minimum gap cannot decrease. The follow-up
cannot interrupt the normal simplification of the same or a later wire.
These candidates share the existing
quality and validation budgets.
Invalid source containment and independent values forced onto the same fixed
target ray fail before route search. Visibility legs that attain a proven
obstacle-free cost bound return without building a grid.
Exact interior search legs share a bounded, route-local result cache keyed by
obstacle geometry and signed headings (and legacy terminal exemptions).
Coincident gate points retain their signed turn cost without constructing a grid.
An expanded frame with a source-proven aligned operand axis retains that
content axis when asymmetric routing margins change its outline. Node-move
transactions reserve settled peer routes and validate the complete final graph,
so an invalid temporary sibling route cannot block its own later repair.

Explicit producer/port evidence gives shared wires one key across recorded
views, retaining full return fields, tuple slots and call identities. Bare
canonical names remain opaque. Licensed perimeter ports and bounded exterior
candidates can resolve detours; independent values remain separate wires.
Recursive automatic geometry settles on a completely validated legal path;
explicit routing still optimizes path costs. Search caches wire-contact costs
for a geometric link across its arrival headings.

Catalog loads, source-adapter preflight and editing-JSON validation also run in
the Worker. Case identity, source authority, persistence key and graph publish
together after success. Invalid or cancelled node moves restore the complete
gesture baseline and both history stacks. Selection renders preserve existing
SVG parents so real browser clicks and double-clicks survive pointer capture.
The bridge serves snapshots and source reads while a load is pending; other
commands reject while busy instead of executing later against a different
model. Stored graphs must satisfy source, layout and non-draft edge checks
before publication; invalid saved data is archived without replacing authority.

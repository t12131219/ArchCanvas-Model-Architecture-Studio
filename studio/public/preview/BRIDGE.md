# Studio preview integration

## Mixed semantic frontiers (2026-10-28)

The current Summary model library contains 43 native semantic models and 3
registered preview cases. `semantic-view` accepts
`moduleCut: {ids: string[], level, depth?, reset?}`. Native levels are
`f0/f1/overview/modules/stages/semantic/roles/detailed/source`; registered cases
support their actual `f0/f1/source` authority. IDs refer to real canonical
containers, including independently matched runtime bridge containers in merged
mode. Source depth zero closes the container; an omitted depth exposes all its
descendants. More specific descendants override ancestor scopes deterministically.

The native inspector publishes `modules`, `moduleCuts`, `suggestedModules` and
`mixed.scopes`. Studio's Summary tab owns the controls; the child remains the
semantic authority. The original publication compiler supplies each scope's
policy before a single canonical dependency projection. No source facts are
rewritten. Requests for the other evidence mode remain dormant; they cannot
make source mode display runtime evidence or make CPU mode display source trees.

Native JSON/layout snapshots retain latent visual connections in
`sourceDraftEdges` and exact visual removals in `sourceDraftOperations`. Semantic
authoring rebinds surviving module targets and recompiles their openings rather
than reusing certificates from the previous IR. Global presets clear explicit
module cuts. Routing completion remains independent of semantic completeness:
pending/failed routes must remain visible and cannot certify publication.

See `docs/summary-mixed-frontier-integration-20261028.md` for all-case coverage,
panel interaction, editing contracts and current validation.

The preview contains the recursive assets migrated from `Summary_Merge` on
2026-10-14 and subsequent Studio integration patches. All 230 catalog cases
(115 current and 115 historical), 666 source views, snapshots, source files and
audit evidence are shipped in this directory. Runtime URLs never reference the
original prototype checkout. `vendor-manifest.json` records the original bytes;
`integration-manifest.json` records the Studio-specific changes.

## Authority boundary

This copied Summary runtime is the only authority for preview nodes, edges,
recursive frontiers (including F0/F1), physical ports, routes, gestures,
camera, selection, source evidence and preview history. React Studio components
must call this bridge and render the returned snapshot; they must not rebuild a
second graph, router, frontier or selection store from iframe DOM. The retained
Studio toolbar, hierarchy tree, object/legend/page panels and folded drawers are
the host surface for those commands. Formal parameters, activation, input
rebinding, source-region edits, managed copies, CAS transactions and publication
receipts remain in the formal Studio workflow and are never inferred from a
preview visual draft.

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
| `snapshot` | none | `snapshot` with `document`; `document.snapshotRevision` identifies the committed recursive frontier revision |
| `request-source` | none | `source` with `source`, optional `bundle`, and `document` |
| `focus` | `nodeId`, `annotationId`, or `sourcePath` and `line`; optional `additive` | reveals collapsed ancestors and focuses the object; `additive` toggles node membership, then replies `focused` with selection |
| `save` | none | `saved` after IndexedDB completes |
| `svg` | optional visible `nodeId` | `svg` with `svg` and `xml` strings |
| `export-svg`, `export-json` | none | starts existing download flow, then `exported` |
| `visual` | `operations` | `applied`, then `state`; every command carries a request id and the state includes `snapshotRevision`/`sourceIdentity` |
| `set-frontier` | `preset`: `overview` (F0) or `detail` (F1), or legacy `locations`/`sourceLocations` plus `expanded` | `applied`, then `state`; the state document reports `frontierPreset` |
| `show-library`, `show-routing` | none | opens original drawer |
| `show-import`, `show-evidence` | none | opens original dialog |
| `undo`, `redo`, `reset`, `fit`, `apply-layout`, `collapse-all`, `expand-all` | none | invokes original operation; reset restores the initial view and is undoable |
| `zoom` | `factor` | updates camera |
| `select-tool`, `connect-tool`, `bend-tool` | none | selects the tool and publishes the actual tool state |
| `pan-tool` | none | available only on the standalone/non-canvas surface |
| `show-ports`, `show-ghost`, `show-obstacles`, `grid` | optional `visible`/`enabled` | updates preview-only helper overlays; the routing candidate-grid setting remains independent |
| `interaction-mode` | `mode`: `compat` or `realtime` | changes the Summary drag/route interaction mode and publishes a new state |
| `arrange-selection` | `kind`: `left`, `hcenter`, `right`, `top`, `vcenter`, `bottom`, `distribute-x`, or `distribute-y`; optional `scope` | arranges actual selected visible sibling nodes as one validated undo step |
| `pin-selection` | optional boolean `pinned` (otherwise toggles the selected set) | fixes or unlocks direct movement of the actual selected visible nodes |

Replies retain `requestId`. Validation failures return `error` with `command`
and `message`. Cases without model source return `source-unavailable`; the
parent must retain their own identity and never reuse the previous model source.

The child also publishes `selection` and `state` when users operate it directly.
During pointer gestures and pending graph tasks, automatic notifications use
`archcanvas:preview:interaction` with only `caseId`, `busy`, `dragging` and
`canCancel`. They never contain graph geometry, selection evidence or a source
document. The host updates toolbar/cancellation flags on the last committed
snapshot and does not rebuild its panel projection or dirty fingerprint. The
normal full `state` follows a completed/cancelled gesture; explicit `snapshot`,
source, save and export replies keep their complete document contracts.
Autosave completion also uses this lightweight status, since saving does not
change the committed graph. Selection evidence/inspector work waits until
release, while selection outlines and graph movement render locally.

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

The preview-mode hierarchy uses the recursive authority's real display identities
and parent relationships, not formal-parser identities. Selection, alias, pins
and expansion mirror the preview state. Junctions are omitted; mandatory root
frames stay expanded. Search reveals matching paths in the tree; selecting a
hidden result or expanding it also reveals its ancestors on the canvas. These
navigation rows do not replace the managed formal document or grant source facts.

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

### Native Summary source semantics (2026-10-28)

Studio source analysis requests select top-level `semanticMode: "summary"`;
`config` remains the unmodified constructor configuration. The portable bundle
retains the native `archcanvas-source-semantic/2` document at `ir.semantic_ir`.
`ir.canonicalSemanticIR` contains its canonical JSON excluding `ir_digest`, so
the browser verifies the native digest without changing Python float literals
through JavaScript serialization. Every native node and edge must be represented
in the portable projection with the same identity, parent and canonical ports.
Registry-added syntax inspection objects remain explicitly `syntaxOnly` /
`source_structure`; they never become native semantic facts.

The right Studio inspector reads the same native document for contracts,
motifs, iteration, coverage and opaque reasons. It sends ordinary bridge focus
and evidence commands and owns no graph, selection or frontier store. Model
source is read as AST only. Runtime/probe modules are not invoked by analysis.
SCC condensation is used only to place cyclic dependencies: loop edges and
original ports stay in the canonical graph. Control/effect relations use dashed
presentation. Native v2 bundles now choose original certified semantic cuts; legacy bundles and catalog cases retain recursive depth frontiers;
the measured adaptive renderer loop and runtime/merged views remain outstanding. `SummarySourceAdapter.semanticDocument(bundle)`
exports the original canonical Python JSON with its native digest, preserving
float spellings and integers that JavaScript cannot represent exactly.

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

Studio toolbar commands are fire-and-forget at the React call site, but the
bridge queues them behind the iframe handshake and serializes their delivery.
This prevents an early F0/F1, drawer, tool or overlay command from being lost
while the child is still loading, and keeps successive commands in user order.

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

## Studio selection and feedback (2026-10-16)

The selection tool supports both single and multiple selection, with no separate
mode or toolbar toggle. `select-nodes` accepts visible node `ids` and `mode` (`replace`,
`add`, `toggle`), or a `scope` of `siblings`, `all`, or `clear`. All selections
are presentation state: they do not create history, change source facts, or
select hidden nodes. `all` and the marquee exclude expanded scopes and junctions.
Selection, alignment, distribution and pinning share the engine's actual IDs;
source hierarchy rows must map through the host's verified occurrence bindings.

Canvas clicks support Shift, Ctrl and Command. Empty-canvas drags select fully
contained visible modules; additive marquee preserves the initial selection.
Dragging a selected member of a multiple selection previews the group, then
commits one validated visual move; fixed members and invalid placements reject
without changing the graph. Escape cancels an active gesture before clearing a
committed selection. Middle-button panning retains its capture-first behavior.

`notice` events carry `{ message, error }`. The host displays immediate contextual
feedback and clears stale failures after successful operations. They do not
certify source-generation capabilities or authorize model execution.

## Generic visual audit fixes (2026-10-17)

Independent source-dependency wires receive separate display terminals while
canonical bindings and the source IR remain unchanged. Mixed frontiers register
new expanded endpoint interfaces before routing. Default frontier routing applies
bounded, fully validated lane cleanup, respecting fixed ports, shared stems and
manual knots. Syntax-only condition controls reject narrow reverse hairpins.

Camera navigation adds a collapsible minimap, readable tree focus, arrow-key
panning and whole-graph return without graph/history mutations. The added
`view-navigation.js` is an independently written Studio camera helper.

The host publication adapter distinguishes preview identities from SHA256
digests and flattens nested SVG definition wrappers before strict publication
validation. Vendor provenance remains in vendor-manifest.json; current adapted
asset hashes are recorded in integration-manifest.json. Reproduction, UI/export
evidence and remaining historical failures: docs/visual-fixes-20261017.md.


## Native semantic view commands (2026-10-28)

For a verified bundle containing `ir.semantic_ir.schema === "archcanvas-source-semantic/2"`,
`set-frontier` dispatches to the original native `frontier` / `certifiedDetails`
pipeline through `studio-semantic.js`. `graph.generic.ir` is the complete source
authority; `graph.semanticHierarchy` is a read-only navigation projection, not
a second graph. The legacy `recursive` authority remains exclusive to catalog
and compatibility documents.

- `semantic-view({patch})` supports the six original granularities, sequence,
  read binding, frame, role path/detail, focus, expression and relation policies.
  Role requests must name an existing certificate and its exact role key.
  `semantic-view({back:true})` returns through native navigation history.
- `expand-all` selects native source-unit/canonical presentation. Canonical
  node/edge accounting remains complete and exactly once at every cut.
- `continue-routing` retries explicitly pending/failed routes against settled
  lanes; the default native budget is 8 seconds plus any in-flight route search.
  It is not a hard wall-clock deadline or an implemented cancellation protocol.
- `document.semanticView` exposes committed granularity, certified recipe,
  accounting, role options, relations and routing counts. Routing `complete`
  requires zero pending and zero failed routes. Incomplete routes remain marked;
  neither a saved flag nor a visual operation changes canonical bindings.
- Native layouts and up to four cut cameras restore across navigation; live
  camera is included in snapshot/save and native undo/redo. Studio panel
  folding state stays outside this graph.

Only static source evidence is exposed here. `runtime`/`merged`, automatic
CPU probes and the measured adaptive renderer loop are not enabled by these
commands. Formal authoring and source transactions retain their existing APIs.

## Summary 文档导入扩展（2026-10-28）

`load.bundle` 除已验证源码 adapter 与旧递归文档外，也接受
`archcanvas-native-semantic/1`、`semantic-canvas/1`、`archcanvas-architecture-document/1`、
`semantic-authoring/1` 与 `archcanvas-source-semantic/2`。含 `adapter` 的编辑包仍优先走
源码验证，不通过普通文档格式绕过证据检查。原生投影、切面与路由只有一个当前 authority。

普通文档 snapshot 的 `importedDocument` 含原始 schema、`documentSha256`、
`sourceVerified:false`、`modelExecuted:false`；`nativeDocument` 含
`archcanvas-summary-import/1` 记录（id/title/documentSha256/document）。`document` 是原始 JSON，
编辑状态仍在 `graph`。case id 来自原始 stable JSON 摘要；导入记录不是服务器源码认证。
`sourceAvailable` 为 false，`request-source` 返回 `source-unavailable`。

`export-json`、snapshot 和 save 响应携带该记录；重新 `load` 时校验原文、case、IR、authoring
与编辑图，并核对原生 SVG 是 Summary 生成内容。顶部 preview-only 保存使用当前浏览器
IndexedDB，不声称完成正式源码 CAS 保存。原始导入文档和当前 graph 可通过编辑 JSON
一起搬运。完整原生 authoring、CPU 执行与 measured adaptive 尚未由该扩展接入。

## Summary declared authoring (2026-10-28)

The same-origin `authoring` command creates or updates an independent Summary
workspace. `action: begin` forks the current native IR; `blank: true` starts an
empty draft. Supported actions are `title`, `scope`, `interface`, `add`
(preset/library/sourceNode), `duplicate`, `erase`, `group`, `library`, `edit`,
`connect`, `rewire`, and `remove-edge`. Endpoints require exact `node` and `port`;
occupied inputs refuse unless `replace: true`. `source` returns to the original
registered source case, never translating the assembled graph to Python.

Replies use the normal `applied`/`error` protocol. `document.authoring` is a
read-only inspector projection. `nativeDocument` may carry a digest-checked
`archcanvas-summary-authoring/1` record; ordinary immutable imports retain
`archcanvas-summary-import/1`. `generic.authoring` owns declared facts and
`authoringWorkspace` stores record metadata only. All mutations validate a copy
and rebuild/route through the current Worker before one history commit.

Source provenance is retained but no adapter or formal source-transaction
authority is conferred. Browser save and portable editing JSON restore the
current document, not the complete in-memory undo stack. Current budgets remain
480 nodes, 3600 dependencies and 16 MB. Studio panels remain the product shell;
no standalone authoring page or second renderer is embedded.


## Summary source modules and exact reconstruction (2026-10-28)

`POST /api/preview/authoring/module` requires the current session and same-origin
checks. It accepts source text, a single `entry` identifier and optional finite
JSON `constructor`. It returns `semantic-module/1` from the original static
Summary compiler in a bounded formal Python process; user source is never
imported or executed. Capabilities publish `preview.nativeAuthoring`.

New `authoring` actions are `add-source` (`module`), `replace-module` (`id`,
`module`), `recipe-start` (`atomic?`), `recipe-add` (`part`), and `recipe-wires`.
Source result application pins optional `workspaceId` and `baseDocumentSha256`;
stale replies refuse. A compatible replacement preserves exact named boundary
slots and rebinds the root presentation; dropping a connected input refuses
without modifying the document. Recipe parts preserve original identities and
parents; cross-part dependencies restore exact operand slots. The inspector's
`recipe.exact` compares full node/edge facts, not counts alone.

Module evidence and source text remain in the declared document across save and
portable restore. A reloaded module is not implicitly compiled or executed.
These actions confer no source transaction binding. Local structural
recertification is not yet connected. Limits and validation evidence are in
`docs/summary-source-authoring-integration-20261028.md`.


## Declared local assembly results (2026-10-28)

`POST /api/preview/authoring/certify` accepts `{ir}` under the formal session and
same-origin boundary. The original Summary `certify_assembly` re-derives only
local operand contracts in a bounded static process; no saved module source is
executed. Capabilities publish `preview.nativeAuthoring.localAssembly`.

`authoring` action `certify` accepts `result`, `workspaceId` and
`baseDocumentSha256`. The result is `archcanvas-summary-local-assembly/1` with
Python canonical `irText`, `resultSha256` and limited `analysis`. This action does
not modify `generic.authoring` or its digest. `authoringWorkspace.localAnalysis`
stores the derived result; `document.authoring.localAnalysis` is a summary.

Restore recomputes base `sourceIR`, verifies declaration/result digests and
compares all facts except the explicitly derived contract fields/digests. It
also checks local scope and denied execution/source authority. All subsequent
declaration edits clear the layer; visual cuts retain it. Undo/redo restores the
matching declaration and derived layer through the existing history. Imported
results remain unverified document evidence, not signed server receipts, and
are not automatically re-analyzed. Python source transactions stay separate.


### 2026-10-28 原生手势取消

`cancel-gesture` 可在 active gesture busy 时调用；清除手势 owner/rAF，恢复 baseline 图与两侧历史、框选前选区或 pan camera，随后释放 capture。后续 pointerup 不提交旧手势。其他 mutation 仍遵守 busy 拒绝。该指令不保证取消已开始的 Worker 布线任务。React 仅将 child `dragging` 投影到面板，已握手的取消即时发送，不经过一般 toolbar 命令微任务队列。

App 不再构造 preview Scene、宿主 pointer/port/box 或预览相机；布线和端口面板仍在 Studio，分别发送 `apply-layout` 与 `visual(portLayout: null)`，结果来自同一 Summary snapshot/history。

### Summary generic catalog

The Studio inspector reads the formal static `data/semantic/studio-catalog.json`, bounds streamed asset reads and verifies byte SHA-256 before using the existing `load` document command. No new source-transaction or execution command is granted. Forty of 43 catalog models fit current native document limits; three retained large models are explicitly unavailable until transport/storage/history stress validation. Original source paths and runtime observations remain provenance.


### Source / archived CPU / merged evidence views

`semantic-view.patch` accepts `mode: source|runtime|merged` and `runtimeInlineRun` (valid integer object record, merged only). CPU mode requires canonical runtime-observations. Inspector projects availableModes and runtimeEvidence without granting execution or source authority. Exact canonical focus crosses modes when necessary and native back restores the previous cut; history/camera/persistence remain native. Imported records are declared evidence. Empty source_runtime_index.regions stays unbound; no label-based inline mapping. See `docs/summary-evidence-views-integration-20261028.md` for current verification scope.


### Compact native hierarchy and session snapshots

Native `semanticHierarchy.nodes` can carry `semanticRef:true`: the host resolves only that row's exact ID in the same graph.generic.ir.nodes. Unknown IDs or other reference values do not resolve. Derived rows retain necessary matching metadata; presentation-only aggregates do not repeat member arrays because their existing exclusion already forbids formal binding. Complete native IR/receipts remain authoritative. N.snapshot freezes canonical evidence and calls the original cloneGeometry for independent mutable geometry/overlays/drafts/layout caches; save/undo/redo/session/reset use it. This is an in-memory optimization, not serialized trust or a raised document budget.


## 原生测量驱动局部细化（2026-10-28）

Summary 的原版 adaptive-frontier/5 现由 studio-adaptive.js 接到唯一原生画布；候选比较使用实际图元文字、精确操作数绑定和成功的物理路径。Studio 保留右侧折叠面板，增加开关、策略、采用/拒绝回执和手动收起入口。保存有效请求与开启前基线；关闭恢复原请求，重开独立校验已保存布局。详细范围、来源及验证见 `docs/summary-adaptive-view-integration-20261028.md`。新 CPU、大图完整压力与 D1 仍未完成。

## Explicit Apply/layout responsiveness (2026-10-29)

`apply-layout` delegates preflight, `needed` conflict detection, routing and final
validation to the existing Worker (`task: optimize`). Its `applied` reply carries
the single final full state/document and is consumed by the host as a state
update; automatic idle snapshots inside this command are suppressed. Busy and
cancellation status still use `interaction`. Explicit snapshot/export reads
retain their complete reply contract.

Search uses a one-second batch budget and a short per-edge search budget,
excluding source certification, final validation, transport and painting. A
legal path may be retained when search is exhausted. The graph's
`routeOptimization.pendingIds` identifies unvisited scoped edges; clicking Apply
again resumes those edges only when scope, options and all relevant geometry
match the exact scheduling signature. The receipt does not license any source
or geometric fact: each batch validates before commit. Scope/settings/geometry
changes start a fresh pass. Cancelling or refusing the result preserves the
previous graph/history. Node positions, manual waypoint policy and source
bindings continue through the same routing contracts.

### Source workbench and explicit Python export (2026-10-29)

The host's floating Monaco Python editor calls `/api/preview/authoring/inspect`
for advisory AST entry inventory, then the existing isolated module compiler.
`import-source-model` prepares `ArchCanvasSummaryAuthoring.fromSource` and
installs the complete native workspace only after native preflight succeeds.
It carries `document.codeReference` (source text, entry, constructor); this is
an export binding rechecked against a fresh static compilation, not a formal
source transaction, an execution certificate or permission to write Python.
The host pins workspace and document digest during source analysis.

`/api/preview/authoring/python` accepts only the current authoring document.
It exports an exact source-preserving reconstruction or a DAG of unchanged
source modules joined through their explicit interfaces. `modules.codeBinding`
records the ID mapping used by `SemanticAuthoring.add`; the backend recompiles
source and verifies all capsule nodes and internal edges before generating
calls from external edges. Unknown atoms, groups, cycles, missing inputs,
multiple drivers and modified capsule internals are rejected. This export
creates new files, never writes original model source, and never executes user
Python in the server. Archive filenames are generated locally. The UI hides
stale downloads after the document changes. Archived IR-only cases need a
source import before Python export; a reference IR alone is insufficient.

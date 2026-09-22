# Implementation Status

## Current State

The repository has completed fixture-backed implementations for Stages 1 through 4, Stage 5's
Engine lifecycle, and the original Stage 6 desktop canvas MVP. Native Linux Tauri E2E now passes
with the installed `/usr/bin/WebKitWebDriver`: it opens an Engine-approved Transformer fixture,
exercises the full interaction path, persists a visual drag across a native restart, verifies the
Exact/Publication view boundary and confirms source bytes remain unchanged. The same test is
configured in Linux CI, whose first remote run remains external acceptance evidence.
Section 25 of the updated plan supersedes the prior Stage 6 presentation and interaction scope: the
revised Stage 6 remains in progress. Semantic editing, structural editing, MCP transport and release
hardening have not started.

## Completed In Current Worktree

- Stage 1: strict Source Identity, Exact Architecture IR and Patch Protocol schemas; a
  candidate-first, atomic, fixture-scoped `set_parameter` transaction with fail-closed negatives.
- Stage 2: bounded read-only PyTorch AST recovery, project discovery, source anchors, identity
  reconciliation, module containers, common flow patterns, capabilities and fixture goldens.
- Stage 3: explicit opt-in isolated FX/export workers, revision-bound runtime evidence, coverage
  gaps and shape validation. Runtime evidence cannot replace source anchors.
- Stage 4: Publication IR and VisualScene protocols, conservative Transformer repeat and residual
  stage reductions, node/edge omission ledger, deterministic SVG, preflight, and fixture goldens.
  A repeat group has a default collapsed scene and an explicit visual-only expanded scene; neither
  state changes Publication IR, Exact IR or source bytes.
- Stage 5: approved-root project manifests, explicit environment validation, cache-root-only graph
  repository, polling source freshness, revision history, visual patch persistence/orphan replay,
  and typed Engine request/response/event schemas. The Engine opens, analyzes, caches and reloads
  the Transformer fixture without writing its source.
- Stage 6 (revised scope in progress): a strict `CanvasDocument` schema for visual state only;
  Engine persistence, restart replay, stale-revision rejection and typed RPC coverage; an
  independent world/SVG/HTML `CanvasStage` replacing the React Flow interaction surface;
  pointer-anchored zoom, middle-mouse/space pan, fit mode, selection, marquee, multi-drag preview,
  grid/object snapping, gesture-level undo protection, visual lock/collapse controls and LOD.
  The warm-white/near-black/blue token system is now the only desktop UI token source. The Tauri 2
  shell forwards typed JSONL requests to a host-configured Engine sidecar instead of reading
  project source directly. Native E2E covers Engine open, drag/save/restart/replay, Exact view
  selection and byte-identical source. Open Project and source-location queries remain Engine RPC.
  The Engine persists an approved scalar `resolved_config` snapshot and passes it to the
  fail-closed static adapter, so selected task helpers and `ModuleList` repetitions are recovered
  only when their task/count is explicitly supplied. A read-only TFB Transformer/TimesNet
  observation is recorded in `docs/agent-handoffs/stage-6-tfb-observation.json`; it is not D5
  acceptance or a claim of complete paper-style rendering.
  A new read-only TFB census tool accounts for every statically discovered `nn.Module` entrypoint
  and records per-entrypoint capability, source revisions, unresolved facts, publication status
  and hash preservation. It also parses static baseline registry exports, retaining non-PyTorch
  exports as explicit unsupported entries. The current read-only TFB baseline has 460 discovered
  relations: 439 assessed entries, 21 aliases, 102 supported, 265 unresolved, 72 unsupported and
  0 blocked; this is recorded in `docs/agent-handoffs/stage-6-tfb-census-observation.json`.
  D4 scientific miniatures are now modeled as source-mapped `PublicationIR` children and rendered
  by both deterministic SVG and the interactive CanvasStage. The initial fixture path supplies an
  explicitly labelled illustrative input-flow glyph plus source-backed repeat equation/inset
  markers; the protocol supports tensor, signal and distribution previews only with their permitted
  static/runtime evidence, and runtime previews require a trace ID. They remain visual-only and do
  not enter `CanvasDocument`, Exact IR or any source-edit path.
  D5 now has an explicit read-only Publication preflight path. It emits per-entrypoint Publication
  IR, overview/detail scenes, SVG and pending manual checklist only to an external evidence root.
  The current non-Article benchmark TFB run accounts for all 460 relations: 102 fully static and 45
  parameter-provenance-limited entrypoints pass machine Publication/SVG preflight, while 292 remain
  visibly unassessed. Transformer, TimesNet and DUET use the narrow, versioned config ledger in
  `docs/acceptance/tfb-resolved-configs-v1.json`; their configuration-driven source flow is now
  evidenced without relaxing unresolved facts. See
  `docs/agent-handoffs/stage-6-tfb-publication-preflight-observation.json`.
  The registered deep-semantic patterns require complete, source-backed structural signatures:
  `spectral_period_inception_block_v1` requires FFT/Top-K, period loop, 1D/2D reshape, Inception
  path, adaptive aggregation and residual evidence; cross-file attention stacks require constructor
  repetition, `ModuleList` loop/norm behavior, task dispatch/output head, attention order and
  residual/norm order. Multi-branch patterns independently require structural evidence for Top-K
  expert routing, decomposition/linear fusion, frequency/Gumbel masking and masked attention
  stacks. Missing markers fail closed, and previews remain explicitly schematic until runtime
  evidence exists.
  These IDs, templates and source recovery rules describe structures rather than benchmark, class or
  field identities. The adapter derives roles from approved local import bindings and AST structure;
  the config snapshot preserves all safe scalar fields instead of using a model-specific whitelist.
  A deterministic fixture that renames every TFB/DUET-derived class and field proves the same evidence
  chain can be recovered without benchmark symbols. TFB remains a read-only reference corpus: its
  Transformer and multi-branch observations exercise the generic rules, but do not define the public
  protocol or claim full paper rendering, runtime evidence or transitive topology recovery.
  The Publication compiler consumes only complete semantic evidence as source-mapped nodes, repeat
  groups, annotations and disclosed miniatures. It does not invent missing Exact edges; unresolved
  benchmark entries remain explicitly `publication_not_assessed` until their approved configuration
  supplies the required source-backed branch evidence.
  The generic Benchmark Model Reference contract now has a strict L0 catalog parser and a unified
  L0/L1 ledger. All 20 indexed records remain visible: explicit adapter selection maps a
  root-relative project scope to a generic static adapter, while every unselected local-model
  record remains adapter-level `unsupported` and every benchmark-only record remains
  `no_local_model`. A real read-only run selects the TFB project as one PyTorch scope and records
  its 460 relations without turning TFB paths, classes or configuration fields into public protocol
  semantics. The reviewed `tfb-entrypoints-v1.json` is supplementary to discovery: its three
  Transformer/TimesNet/DUET seeds are all rediscovered by the static adapter, and a missing seed
  would make the ledger unresolved rather than creating a phantom model. The D5 validator makes the
  full-census equation, source immutability, artifact set and checklist state machine-readable;
  machine coherence now passes for the current TFB preflight, but the 147 checklists remain pending
  manual approval. They are explicitly eligible for `provisional_visual_iteration`, which supports
  later visual-style changes without manufacturing reviewer approval. The same generic adapter has
  now been exercised read-only on ADE20K, RecBole and
  OGB scopes, discovering 20, 67 and 87 entrypoint relations respectively. Their representative
  registries are supplementary seeds; the remaining unresolved entries stay visible and are not
  promoted to supported or publication claims. MMPretrain and SpeechBrain have also passed the same
  read-only L1 preflight with 101 and 158 discovered relations respectively; their seed registries
  cover representative components only, while dynamic/config-driven and unresolved entries remain
  explicitly visible.

## Scope Boundaries

- Static and runtime validation evidence currently cover repository fixtures. Article projects are
  read-only observations until separately approved A0-A6 evidence exists.
- Publication reduction supports declared Transformer repeat and residual-stage patterns. It does
  not claim a complete paper diagram for arbitrary Python or arbitrary PyTorch code.
- The current CLI remains fixture-scoped and has not yet been routed through Engine.
- Browser fixture mode persists only visual state in browser storage and must never be confused
  with Engine-backed project persistence. Actual CanvasDocument Engine persistence is covered by
  Python integration tests.
- Native E2E requires Tauri's Linux SDK libraries plus a `WebKitWebDriver` binary. The test accepts
  `ARCHCANVAS_WEBKIT_DRIVER` for distributions where the binary is not on `PATH`; CI installs the
  distro driver explicitly.
- The Tauri bridge requires `ARCHCANVAS_ENGINE_PYTHON` and `ARCHCANVAS_ENGINE_CACHE_ROOT`; when
  either is absent it fails closed. It does not offer a direct filesystem fallback.
- The generic benchmark ledger is an L0/L1 accounting mechanism. Only explicitly selected project
  scopes run a delivered adapter; the current baseline selects TFB's PyTorch scope. Java,
  TensorFlow, provider and additional Python/PyTorch scopes remain visible as adapter-level gaps,
  rather than being included in a PyTorch success rate.

## Revised Stage 6 Exit Criteria

The earlier MVP evidence remains valid for Engine persistence and source immutability, but it is not
sufficient for the updated Section 25 contract. The D5 machine gate now passes for the current
read-only TFB preflight (`460 = 439 + 21`, 147 external evidence directories and unchanged source),
  but Stage 6 still cannot exit: every generated checklist needs manual overview/detail,
  evidence-traversal and screenshot approval; applicable entrypoints still need approved immutable
  config snapshots (including DUET `enc_in`); and the first hosted CI acceptance remains outstanding.
  The local Native Tauri E2E and specified desktop visual regression now pass. Stage 7 must not be
  entered until the remaining D5 and hosted CI conditions pass.

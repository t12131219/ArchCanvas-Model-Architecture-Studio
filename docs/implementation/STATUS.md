# Implementation Status

## Current State

The repository has completed fixture-backed implementations for Stages 1 through 4, Stage 5's
Engine lifecycle, and the original Stage 6 desktop canvas MVP. Native Linux Tauri E2E now opens an
Engine-approved Transformer fixture, persists a visual drag across a native restart, verifies the
Exact/Publication view boundary, and confirms source bytes remain unchanged. The same test is
configured in Linux CI; its first remote run remains an external acceptance observation. Section 25
of the updated plan supersedes the prior Stage 6 presentation and interaction scope: the revised
Stage 6 remains in progress. Semantic editing, structural editing, MCP transport and release
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
  exports as explicit unsupported entries. Its initial TFB baseline has 460 discovered relations:
  439 assessed entries, 21 aliases, 79 supported, 288 unresolved, 72 unsupported and 0 blocked;
  this is recorded in `docs/agent-handoffs/stage-6-tfb-census-observation.json`.
  D4 scientific miniatures are now modeled as source-mapped `PublicationIR` children and rendered
  by both deterministic SVG and the interactive CanvasStage. The initial fixture path supplies an
  explicitly labelled illustrative input-flow glyph plus source-backed repeat equation/inset
  markers; the protocol supports tensor, signal and distribution previews only with their permitted
  static/runtime evidence, and runtime previews require a trace ID. They remain visual-only and do
  not enter `CanvasDocument`, Exact IR or any source-edit path.
  D5 now has an explicit read-only Publication preflight path. It emits per-entrypoint Publication
  IR, overview/detail scenes, SVG and pending manual checklist only to an external evidence root.
  The current non-Article benchmark TFB run accounts for all 460 relations: 101 fully static and 42
  parameter-provenance-limited entrypoints pass machine Publication/SVG preflight, while 296 remain
  visibly unassessed. Transformer and TimesNet forecast use the narrow, versioned config ledger in
  `docs/acceptance/tfb-resolved-configs-v1.json`; their configuration-driven source flow is now
  evidenced without relaxing the remaining parameter-provenance facts. See
  `docs/agent-handoffs/stage-6-tfb-publication-preflight-observation.json`.
  The first registered deep-semantic pattern, `timesnet_v1`, now requires a complete static signature
  (FFT/Top-K, period loop, 1D/2D reshape, Inception path, adaptive aggregation and residual) with
  eight source anchors before it emits a `TimesBlock` Publication group. Missing markers fail closed;
  period previews remain explicitly schematic until runtime evidence exists. A fixture and the real TFB
  TimesNet entrypoint are covered by deterministic tests, while the deep-semantic DUET and Transformer
  patterns remain pending for real cross-file benchmark sources. A fixture-backed
  `transformer_encoder_layer_v1` registry signature is now available; the real TFB Transformer is
  intentionally not matched until its imported `EncoderLayer`/`DecoderLayer` attention and residual
  order can be proven from source anchors.

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

## Revised Stage 6 Exit Criteria

The earlier MVP evidence remains valid for Engine persistence and source immutability, but it is not
sufficient for the updated Section 25 contract. The revised implementation still requires visual
regression at the specified desktop viewports, contrast/token-drift checks, native E2E evidence for
the full interaction set, and D5 validation for the complete approved TFB model census. Stage 7
must not be entered until those requirements pass.

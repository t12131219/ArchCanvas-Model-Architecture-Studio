# Scene Studio Cutover Acceptance

Verification date: 2026-10-02

This record closes the migration described by
`studio/prototypes/scene-visual-lab/IMPLEMENTATION_MIGRATION_GUIDE.md`. The
prototype remains an independent visual and interaction oracle; production
code lives in `studio/src/scene-studio` and does not import the prototype or
the retired main-view/visual-kernel implementation.

## Runtime Ownership

- `studio/src/main.tsx` renders only `SceneStudioApp`.
- `studio/src/scene-studio/App.tsx` is the single production SVG canvas.
- The retired `app`, `main-view`, `visual-kernel`, `shell`, and `inspector`
  implementations have no production imports and are absent from the bundle.
- `studio/prototypes/scene-visual-lab` remains independently type-checkable,
  buildable, and browser-testable. It was not modified by the cutover work.
- `src/archcanvas_studio/static` is generated from the scene-studio entry and
  serves the same scene used by SVG, JSON, PNG, and PDF export.

## Migration Inventory

| Guide phase | Production result | Acceptance evidence |
| --- | --- | --- |
| 0-1: prototype copy and state boundary | Prototype-derived canvas, scene-studio store slices, no second production renderer | prototype build; production dependency test; scene visual regression E2E |
| 2: source-to-view slice | project discovery, entry/config/environment selection, asynchronous analysis, Exact IR projection, evidence and source excerpts | Python Studio/source-v2 tests; `scene-studio.spec.ts` |
| 3-4: multi-view and generalization | seven presets over one semantic identity, hierarchy frontier, two Transformer baselines, Tier A and seven no-Pattern-Pack holdouts | projector tests; Tier A tests; `stage-8.md`; expanded/paper E2E |
| 5: visual persistence | position, size, expansion, alignment, distribution, pinning, theme, undo/redo, stable hierarchy targets, four export formats | visual API/projector/layout tests; `scene-studio.spec.ts` |
| 6: semantic writeback | parameter/structural intents, topology draft, named ports, capability decisions, prepare/verify/review/commit/discard, Graph Delta and round-trip receipts | transaction and conformance Python tests; Studio transaction E2E |
| 7: source/codegen capabilities | CodeMirror workspace, generated project lifecycle, registry/codegen rules, source maps, state compatibility, recovery journal, offline bundle, contract maintenance | generated-project/release/protocol tests; contract-maintenance E2E |
| 8: cutover | production entry switched, old frontend removed, static bundle rebuilt, rollback point retained | TypeScript/build/import gates; archived checksum and rollback build verification |
| P2 extensions | incremental editor-local Tree-sitter service, explicit ELK relayout, bounded Keras/JAX/ONNX lowering, viewport detail virtualization, adaptive routing Worker | worker/client tests; cross-framework transaction tests; production bundle split; source-backed and expanded-scene E2E |

## Interaction And Visual Matrix

The release browser matrix contains eleven Chromium cases:

- the source-backed Studio flow, including project state, search, diagnostics,
  source workspace, visual commands, persistence, transaction review, mobile
  layout, and four-format export;
- two module-contract maintenance flows, including breaking migration review;
- full expansion and interaction budgets for classic Transformer,
  Tensor2Tensor Transformer, and the largest non-Transformer catalog case;
- negative coordinates, left/up/down drag, wheel anchoring, middle-button pan,
  atomic/recursive hierarchy A/B, export coherence, and static metrics;
- classic and Tensor2Tensor paper views with encoder-left/decoder-right
  ordering and recursive expansion.

The real-browser oracle comparison additionally covered Classic and
Tensor2Tensor in standard/paper presets, collapsed, one-side-expanded, and
fully-expanded states. Classic paper is 16 nodes/15 edges and Tensor2Tensor
paper is 12 nodes/11 edges in both production and the prototype. After Worker
routing settles, both fully-expanded production views have zero crossings,
zero node overlaps, and zero edge-through-node violations. Classic retains the
prototype's 7 label collisions, 28 bends, and 18570 total route length;
Tensor2Tensor retains 4 label collisions, 29 bends, and 19038 total route
length. These nonzero label counts are part of the current frozen oracle and
are not reported as zero.

The production toolbar exposes only live commands. The prototype case matrix,
read-only semantic add/connect/delete controls, paper-view automatic relayout,
and the ineffective source-backed visual reset are absent. Module contract
maintenance is a project-level command in the right-side Model inspector and
does not require a selected canvas node. At a 1144px-wide real browser viewport,
the 210px navigation panel, bounded variant toolbar, and 260px inspector do not
overlap.

The source-backed geometry regression explicitly asserts that the visual patch
target equals the operated node's `view:hierarchy:*` binding and that the same
scene node restores its position after reload. Exact IR and source digests stay
unchanged by visual operations.

## Release Gates

The final run covers:

- all Python tests, Ruff, and Python bytecode compilation;
- all non-E2E Vitest tests and both production/prototype TypeScript projects;
- production and prototype builds;
- the eleven-case browser matrix;
- the complete generated schema consistency check;
- `git diff --check`, production dependency/import gates, holdout tests, and
  archive checksum verification.

| Gate | Result |
| --- | --- |
| Python | 333 passed, 22 skipped |
| Vitest | 33 files, 184 tests passed |
| Chromium release matrix | 11 passed |
| Ruff and compileall | passed |
| Production/prototype TypeScript | passed |
| Production/prototype builds | passed |
| Generated schemas | complete registry passed |
| Archived main-view checksums | all entries passed |

The workspace extension `VisualTemplateBinding.parameters` is represented in
the source model and included in the binding digest when nonempty. Empty
parameters preserve legacy digests. Both public schema copies are generated
from that model, so the complete schema registry passes `--check` without an
exception or manual overwrite.

## P2 Extension Closure

The guide's four P2 tracks are implemented on the cutover architecture:

- the Python Source Workspace lazily loads a dedicated Tree-sitter Worker and
  grammar WASM, maps every CodeMirror ChangeSet through `tree.edit`, reparses
  against the old tree, and exposes only `editor-local` errors, folds, and
  class/function navigation; LibCST and Exact IR remain the validation authority;
- ELK layered layout runs only after an explicit user command in a cancellable
  Worker, preserves pinned nodes, rejects stale results, and commits one visual
  patch batch for one-step undo;
- bounded advanced lowerings cover Keras subclass/Functional activation edits,
  Keras subclass normalization insertion, Flax and pure-JAX activation edits,
  and ONNX initializer/attribute/standard-node edits; every supported path is
  reanalyzed and checked against a framework-specific Graph Delta oracle;
- large scenes retain all node/edge hit geometry while virtualizing off-viewport
  detail, and adaptive routing moves to a Worker after interaction stabilizes.

These are bounded capabilities rather than blanket framework claims. Unsupported
forms, ambiguous anchors, transformed/stateful JAX, custom ONNX domains, and
unproved edits continue to report `unavailable` or `partial` and produce zero
source writes.

The recursive/stepwise routing mode still carries historical nonzero quality
metrics shared with the prototype, and the Classic v2 analysis can still emit
`OUTPUT_NOT_REACHABLE`. Neither is represented as fixed by this acceptance;
the hard visual result above applies to the atomic-bottom-up golden states.

## Rollback

`docs/archive/main-view-v1/SHA256SUMS` protects the archived main-view source,
and commit `45a887fabebf767965235e8f6996369c2b5555ff` is the retained rollback
revision. The archived checksums and a production build from that revision were
verified during cutover. The historical P0 records under
`docs/acceptance/main-view-p0` remain evidence only and are not runtime inputs.

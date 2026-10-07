# Output movement across saved frontiers: bounded design

Design analysis only, 2026-10-06. No product, old preparation, candidate, browser raw, reports or saved document is modified. No browser is opened and no model is executed. The parent has not released the next product change.

## What actually happened

The preparer uses one valid ordinary `move` for the output: `dx=0`, `dy=-28590`. Current `studio/src/core/document.ts` is byte-identical to its frozen preparation copy (SHA-256 `ceb6a83a00517ed23591938457a76f53beb8ccac75557d6f17fb287dc338b3f1`). Its move branch intentionally adds the same delta to the active layout and every saved frontier containing that ID. This is not an incorrect arithmetic implementation.

| Output position | Before move | After ordinary move |
| --- | ---: | ---: |
| Expanded active local Y | 30254 | 1664 |
| Expanded saved local Y | 30254 | 1664 |
| Collapsed saved local Y | 262 | -28328 |
| Expanded world Y (root Y 92) | 30346 | 1756 |
| Collapsed world Y (root Y 92) | 354 | -28236 |

The two frontiers have distinct neighbor placements because expanding a 300-child network previously pushed output down. Arranging those children into a compact grid shrank the network, but did not automatically pull output back. The subsequent large output move was meaningful for the expanded view and unsuitable for the collapsed cache.

The saved collapsed negative position is real, not a stale screenshot or validator-only error. Restoring it on collapse follows the current cache contract. Expanded geometry and canonical facts can remain exact while the overview becomes unusable. The native diagnostic's old **353/357** and all four failed comparisons stay intact. Its blanket expectation that every unpinned common body stays at the same position during collapse is independently too strong: output is allowed to return to its distinct compact placement. A passing spatial oracle must distinguish legitimate frontier-specific placement from this severe negative displacement.

## Existing contract and classification

`document.ts:258–259` implements global delta propagation. `expand:178–198` captures the departing effective visible frontier and restores the next saved frontier while preserving the operated node, ancestors and pinned subtrees. Effective frontier keys ignore hidden expansion flags and use a sorted JSON identity array. Compatible legacy lookup deliberately refuses ambiguous/conflicting interpretations.

The global move behavior is required by existing `move-preview.test.ts:80`, `move-recovery-independent.test.ts:165`, `core.test.ts:113`, and the hand-authored collapse acceptance tests imported by `collapse-continuity-independent.test.ts`. The latter's manual container/output movement test adds deltas to compact and deep layouts while retaining hidden expansion memory. `expansion-intrusion.test.ts:44` also expects a manual output move made in a compact frontier to survive reopening.

Thus the preparation satisfies typed-operation, revision, identity/source and arithmetic contracts. It **does not satisfy the multiple-frontier spatial/readability precondition** of a collapse/expand workload. The product's limited scope controls make a view-specific compaction awkward, which is a usability/capability gap; these records do not establish that existing default all-frontier movement is itself unintended. Schema validation requires finite position numbers, permits negative manual positions, and does not certify containment or visual quality. An info-only scene diagnostic is also not an all-frontier preflight.

## Minimal compatible product extension

Add an explicit optional move scope, proposed contract:

```ts
{ type: 'move', ids: string[], dx: number, dy: number,
  scope?: 'all-frontiers' | 'current-frontier' }
```

Omission preserves the existing `all-frontiers` behavior exactly. Validate the enum and reject unknown values. Do not silently change ordinary gestures, language moves or recovery proposals, clamp coordinates, clear caches, rewrite old documents, or replace restored compact coordinates with expanded ones.

For explicit `current-frontier`:

1. Resolve the effective visible frontier using the existing frontier contract, not raw `expandedIds`. Require selected IDs to belong to that visible frontier; hidden-node edits remain available only through the existing default contract where established layout permits them.
2. Reuse materialization, finite delta validation, selected-ancestor deduplication, pinned-subtree protection, atomic validation and revision/history behavior. The active layout changes by the exact delta; manual negative coordinates remain permitted.
3. Save the resulting visible active arrangement under the canonical current frontier key, using the existing visible snapshot contract. This also establishes a canonical cache when the current frontier had only a compatible legacy key. Keep all other keys/positions byte-exact, including ambiguous or conflicting legacy caches; canonical direct lookup then supplies the explicitly edited view. Do not add a new document-schema field or separate history mechanism.
4. Subsequent toggles must restore each saved frontier exactly where the existing pin/anchor rules allow it. A later default move still adds its delta to **all** saved views, including the canonical edited view. Preview Scene/SVG should equal a real commit's active scene for either scope; cache policy remains a commit concern.

The bounded implementation would touch `VisualOperation` in `types.ts`, accepted operation fields and the move branch in `document.ts`, plus focused independent tests. The Python document store persists CanvasDocument fields and does not execute visual operations; no Python operation reducer or schema migration is needed for this scope proposal. UI wording and natural-language support are a separate exposure step, not implied by adding the core field.

For the workload, start from the frozen **unbroken grid revision 4**, apply the same output delta with explicit `current-frontier`, and produce a new candidate/receipt/storage directory. Expected expanded local/world Y remains1664/1756; collapsed cache remains262, so collapse restores world354. No old candidate is repaired or relabelled. Applying the new scope to the already malformed revision5 candidate would preserve its bad collapsed cache and is not a repair.

## Preparation and acceptance preflight

Before timing, enumerate and replay every declared workload frontier from a fresh candidate, preserving the original input. Independently check source/IR/canonical identities, actual visible count, moved ID and pin/anchor geometry, declared neighbor placements, outside-parent/body/header conflicts, scene bounds, viewport coverage and nominal text projections. Restore the initial frontier and confirm exact active geometry/cache/history/save/reopen evidence. Inspect actual collapsed and expanded pixels separately; no all-frontier readability, routing beauty or timing follows from arithmetic.

The expected output difference354↔1756 is legitimate view-specific placement. It must not be tested as zero displacement for an unpinned neighbor. The network/ancestor anchors and unrelated pinned input have separate zero-displacement expectations. A finite preflight can reject the −28236 observation without globally outlawing negative manual coordinates or every intentional overlap.

## Independent counterexamples for implementation

Use a literal small source-bound hierarchy with two independently supplied frontiers and fixed expected coordinates. Do not generate expected caches or frontier keys through the implementation under test.

| Case | Required result |
| --- | --- |
| Literal compact output262/deep30254, default dy−28590 | Preserve the historical arithmetic: both caches get the delta. This is not a new passing visual workload. |
| Same literal fixture, explicit current deep move | Active/deep1664, compact262; repeated collapse/reopen restores world354/1756 without cumulative drift. |
| Current move left/right/up/down, duplicate selection | Exact deltas once; unrelated view bytes and other IDs unchanged. |
| Omitted scope versus explicit all-frontiers, ordinary small move | Complete documents identical; previous global-move assertions still pass. |
| Selected ancestor plus child; pinned descendant/selected pin | Existing one-root movement/protection semantics retained; no double translation or modified outside cache. |
| Hidden expanded descendant memory under collapsed ancestor | Scope resolves the literal effective displayed frontier; hidden memory stays exact and cannot select a deep cache by raw flags. |
| Current frontier has no cache or only a compatible legacy cache | Establish correct canonical visible snapshot; other cache bytes remain unchanged; reopen uses edited view. |
| Ambiguous delimiter legacy key and conflicting hidden-state caches | Preserve original bytes; no guessing which unrelated cache to update. |
| Explicit current move of hidden node | Reject atomically; default established-hidden-layout behavior remains unchanged. |
| Manual negative position or user-chosen overlap | Exact coordinates retained with diagnostics; no zero clamp, auto-repair or rejected finite document. |
| Current move followed by ordinary global move | Global delta reaches each saved frontier from its distinct local baseline. |
| History undo/redo, stale revision, JSON save/reload | Whole layout/cache snapshots restore exactly; stale edits fail without mutation; aliases/styles/source/IR unchanged. |
| Already malformed candidate plus new current move | Bad other cache remains bad; no undocumented migration or claimed recovery. |
| Toggle oracle demands all common bodies stay fixed | Negative-control oracle rejected: unpinned output legitimately has different compact/deep positions; protected IDs are tested separately. |

`readback.py` is a separate parser/arithmetic analysis and writes only its new `report.json` with exclusive creation. It does not import the product, generate a corrected candidate, or count as a product test. The report binds finite input bytes and verifies the exact cause; all UI, publication, performance and human gates remain open.

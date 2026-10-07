# Independent corridor acceptance

This work uses only formal public Canvas/Scene/SVG observations. It does not run
model code, a browser, services, the failed prototype, or a historical runtime.
No prototype fragment is reused. Archived formal BG JSON/SVG files are immutable
reference observations, not an expected-output algorithm.

`../ancestor-corridor-oracle.ts` independently implements complete lexical path
validation, orthogonal geometry, strict interior crossings, per-edge-pair lane
interval unions, actual direct-owned SVG cards/backplates, public circles,
canonical memberships, protected metric checks and coherent-corruption checks.
It imports product schema types only, and imports no product geometry/scoring
helpers. Product build/render calls in tests and `verify-current.ts` provide
observed outputs only.

`../freeze_baseline.py` copied 34 exact archived byte bindings into `../baseline`:
9 Canvas inputs, 12 BG Scene outputs, 12 SVG outputs and the archived capture.
Every copied byte is checked against the previous archive manifest. None of the
archived or previous sealed evidence was edited.

The new `studio/tests/ancestor-corridor-independent.test.ts` has 9 focused tests:
strict parser rejects 10 lexical/geometry corruptions; literal metrics protect
split crossings, endpoint contact, pair-local union and same-tensor crossing
pair exchanges; archive bytes remain exact; family identity rejects 17 wrong or
unresolved canonical/style/side/member cases; coherent source/branch/style/circle
and own-body changes fail; a known single-route 17-overlap candidate fails due to
same-tensor crossing; the independent literal two-branch candidate demonstrates
safe improvement with distinct-tensor crossing exchanges; all 12 current views
retain frozen source/card/port/branch facts; actual L3 reaches 17 overlaps while
retaining all canonical branches and removing the two named mask overlaps; work
caps equal the literal approved bounds.

The current Repeat test changes only its three Transformer L1/L2/L3 no-stack SVG
byte-equality assertions, replacing them with this independent invariant check
against copied archived BG observations. The other six frontiers, three details,
all old assertions and the sealed-ChS environment negative-control scope retain
their prior checks. Old sealed tests, archives and evidence remain untouched.

`current-attempt-1/report.json` records independently checked final outputs:

| View | Strict pairs / points | Different-tensor overlap pairs | Changed routes |
| --- | --- | --- | --- |
| Transformer L1 | 20/21 → 19/20 | 7 → 5 | 44,55 |
| Transformer L2 | 22/25 → 22/25 | 19 → 17 | 44,55 |
| Transformer L3 | 20/23 → 20/23 | 19 → 17 | 44,55 |

L3 pair-overlap length is 4314.21 → 4068.81. Disjoint-owner strict pairs/points
are 17/20 → 16/19, overlap pairs remain 13. Same-tensor strict pair counts/points
do not increase; no individual same-tensor pair gains a crossing. Both named
44/45 and 44/46 mask overlap intervals disappear. Both memory branches and their
immutable source/target/canonical memberships survive, with a shared trunk.
Different-tensor crossing pairs are exchanged; this report makes no claim that
each different-tensor pair is individually monotone.

The remaining six frontiers plus three details have exact BG Scene and SVG bytes.
All twelve outputs preserve source digests/facts, Canvas bytes, object/port/card
geometry, style, hidden-edge accounting and export scope. No new public body,
backplate or ancestor-header intrusion appears. The earlier failed root capture
is bound and rejected by the new oracle for 19 → 20 overlap regression and 13 →
16 disjoint-owner overlaps.

Receipts (all retain stdout/stderr and exact source before/after bindings):

- `../root/acceptance-target-attempt-3/receipt.json`: final new9 + Repeat17,
  26/26 pass, source unchanged.
- `../root/acceptance-capture-attempt-1/receipt.json`: twelve current public
  captures and negative captured-attempt check, pass, source unchanged.
- `../root/acceptance-strict-ts-attempt-1/receipt.json`: strict TypeScript pass;
  this preceded the final narrow Repeat assertion/L3 gate changes, so root's
  final strict/build receipt is the authoritative final combined check.
- Earlier target attempts remain as historical observations. Attempt1 used
  Node's default isolation and reported the test file as one test; attempt2
  used the package's `--test-isolation=none` and reported nine individual tests.

This is AI geometry/semantic evidence, not human visual or pixel acceptance.
The caps are deterministic work limits, not measured performance. The product's
new family stage guards same-tensor pairs; its existing generic routing stage
is preserved. Acceptance validates final observed outputs independently of that
implementation distinction.

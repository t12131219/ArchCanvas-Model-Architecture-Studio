# Internal wire-contact regression

This is a small real `SummaryRecursive.route` proof, not a manually substituted
candidate. It executes only the graph runtime in a disposable JavaScript VM;
no model Python is imported or executed.

The original legal candidate route contains a 5 px internal step. The optional
cleanup shortens its 10 recorded points to 8. Before the contact guard, it chooses
a path whose internal corner at `(50, 50)` coincides with the independent peer's
internal corner. Strict segment crossings stay at 1 and collinear overlap stays
at 0, but distinct physical contacts increase from 1 to 2. The source, layout,
edge and registered-junction validators all pass. Thus the strict crossing count
alone does not prove that a shortcut avoids additional touches.

The guard rejects that shortcut while retaining a different legal 8 point
simplification. Physical contacts stay at 1, strict segment crossings stay at 1,
and overlap stays at 0. Existing crossings are not represented as eliminated.
The production guard affects only optional cleanup quality checks; it does not
add visibility searches or relax any source/geometry validator.

| Runtime | Loaded router SHA-256 | Loaded recursive SHA-256 | Contacts before → after |
| --- | --- | --- | --- |
| Before | `c5c9f073f9d83b993f7281a4a8541dc45c9f48a99f0a0d55088367cf5b3e6cf5` | `e68a5b2b12f33f39d2794a19f55de1fd6cc514ebb8bae8a717aadc77f5b05e37` | 1 → 2 |
| Final after | `56be06129595998c3d92f0d8bf0725ca3d5a6f62f674b0e89f9b68f440f3904d` | `5439a0df9cd22f18ffe48cdc27a49f1eb814fad799d6bc08ff616bc0636f02dd` | 1 → 1 |

`before-proof.json` is the actual original run. `before-proof-reproduced.json`
repeats it against preserved bytes. The old router bytes were recovered from
the previous frozen runtime and matched the original run's load-time hash;
the other seven before files matched the live bytes when preserved. The receipt
states this provenance explicitly. `after-proof.json` captures the fixed runtime
with the same input geometry. Both complete runtime sets are preserved here.
The intermediate after run and receipts are retained under
`pre-final-version-key/`. Its recursive hash `32c535...` precedes the final
addition of the cleanup receipt's presentation version key; it is not the final
product receipt. The top-level after proof, runtime, tests and hash manifest all
refer to the final frozen bytes listed above.

`wire-contact-helper.cjs` is an independent diagnostic copy used by the proof
script. The regression tests call the production `R.wireContacts` API. Contacts
are deduplicated by physical point per unordered route pair. They include
nonparallel intersections and collinear single-point internal contacts, including
octilinear segments. Coincident actual terminals of both routes are excluded.
Positive shared runs remain governed by the existing overlap validator. The
cleanup caller excludes equal canonical wire identities and complete licensed
shared presentations; partial coincident paths do not acquire that exemption.

The 8 passing tests cover pair deduplication, segmentation, rotations,
reflections, translation, scale, diagonal contacts, actual terminal boundaries,
the real frontier regression, exact bindings/ports/contracts/manual knots,
repeat stability, registered same-wire fan-out, and complete versus partial
source-recorded shared presentations. See `regression-tests.log` and
`regression-tests-receipt.json` for the exact test and runtime bytes.

From the formal project root:

```bash
node docs/evidence/preview-generalization-20261014/t-contact-regression/proof-before.cjs \
  docs/evidence/preview-generalization-20261014/t-contact-regression/before-runtime \
  /tmp/t-contact-before-reproduced.json
node docs/evidence/preview-generalization-20261014/t-contact-regression/proof-before.cjs \
  docs/evidence/preview-generalization-20261014/t-contact-regression/after-runtime \
  /tmp/t-contact-after-reproduced.json
cd studio
node --experimental-strip-types --test --test-isolation=none tests/previewWireContacts.test.ts
```

This receipt does not claim that every historical graph is free of every type
of wire touch. Broader matrix quality reports retain their strict segment-crossing
field and add a separate physical-contact diagnostic.

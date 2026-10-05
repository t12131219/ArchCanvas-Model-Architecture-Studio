# Independent routing review

`audit.mjs` is a geometry oracle separate from the product routing parser,
intersection functions, grid solver and tests. It runs against a durable copy of
the formal candidate core and the archived core before the routing repair. No
browser automation, model execution, dependency installation, prototype import,
existing evidence rewrite or product edits are involved.

Run from the formal project root:

```bash
node --experimental-strip-types docs/evidence/m4-ai-usability-next/routing-independent/audit.mjs
```

The expected facts come from geometric contracts, deliberately constructed
counterexamples and original source-bound canvas inputs. Candidate outputs are
not used as expected snapshots. The oracle checks orthogonal segments, unrelated
node body and source/target body penetration, expanded headers, port attachment,
scene bounds, input immutability, exact preview versus guarded
commit Scene/SVG and undo/redo. It explicitly detects a deliberately intersecting
segment before testing repair.

For every whole scene, canonical visible plus hidden edge coverage must equal the
architecture edge IDs exactly. Source facts and the projected semantic bindings,
roles, labels and styles must match the archived core; this comparison checks that
the routing-only repair changed presentation rather than inherited model facts.
Every tested router's overlap index is checked against an independent quadratic
rectangle oracle, and retained stress crossings must carry exact structured
object IDs and edge IDs. The stress input's embedded source hashes must match the
current fixture bytes.

`audit.json` separates `baselineMatrix` (archived old core) from `matrix` (candidate
core); `details` contains candidate detail scenes. The 39 historical canvas inputs
are rerendered in CPU code. They are not new browser captures or inherited browser
coverage. There are 32 distinct detail selections across frontiers and edited
snapshots. All candidate body/header/attachment/bounds arrays must be empty for
these inputs or the checker fails.

The eight explicit route examples cover unrelated bodies, source re-entry,
ancestor headers, negative fractional coordinates, a covered endpoint, a maze
requiring multiple bends, a 300-object grid budget counterexample, and a literal
node identity ending with `#header`. There are
120 deterministic integer obstacle fields with the declared seed `0x524f5554`.
Every field must produce a clear route or accurately name each retained intrusion.
An intentional object move into its ancestor's header must preserve its anchor and
produce a warning. The source-analyzed DenseStress300 input is expanded through
guarded operations. Its twelve four-direction move trials check the complete
Scene/SVG, semantic immutability, commit history and undo/redo. Intentional overlap
after the large vertical moves is recorded with the actual diagnostics.

This review establishes bounded geometric correctness for these cases. It does
not certify visual elegance, parallel corridor separation, minimal edge crossings,
human task completion, browser display performance or publication acceptance.
Endpoint and path serialization uses 0.01-unit precision with a 0.01-unit product
collision tolerance. The negative fractional example records a strict 0.001-unit
target penetration from rounding; the 0.02-unit interior oracle excludes that
numerical contact. The 300-object maze reaches the 40000-cell fallback cap even
though a clear multi-bend route is known to exist, and records an honest conflict.
CPU timings are diagnostic and may contain host contention; they are not a
presented frame-rate or latency acceptance result.

`source-snapshots` preserves every candidate core copied by this review. The
current receipt binds one snapshot by file hashes and records whether the live
core still matched at the end. Earlier copied candidate bytes are not promoted
product builds or browser coverage.

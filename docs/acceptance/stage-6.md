# Stage 6 Acceptance: Safe Parameter Round-Trip

## Delivered

- Versioned `SemanticParameterPatch`, `GraphDelta`, `SourceTransaction`, and `TransactionReceipt`
  protocols with exported JSON schemas.
- `archcanvas patch prepare`, `verify`, `commit`, and `discard` commands. Each command emits exactly
  one compact JSON receipt on stdout.
- Exact config-value transforms and exact Python literal transforms through LibCST.
- Isolated transaction project copies, anchor fingerprints, source/config hashes, unified diffs,
  Expected Graph Delta, independently observed Graph Delta, and an explicit `review-ready` gate.
- Persisted state history from `draft` through `planned`, `prepared`, source validation, reanalysis,
  graph-delta validation, tests, review, and the terminal commit/discard/failure state.
- Ordered verification for syntax, static relative imports, Exact IR, semantic closure, exact graph
  delta, shape/type invariants, built-in compile plus requested targeted tests, optional Stage 5
  runtime replay, and arbitrary-depth hierarchy/frontier publication/geometry recompilation.
- Atomic commit with source revision/hash recheck, no fuzzy merge, post-commit reanalysis, and byte
  restoration if the commit path fails.
- Studio Model Inspector for current value/provenance, target value, transform type, affected graph
  count, and risk; the review surface shows source diff, expected/observed delta, receipt gates,
  explicit commit, and discard controls.

## Safety Evidence

All transaction tests operate on temporary copies of the Transformer fixture. The canonical fixture
is never a commit target.

| Scenario | Expected outcome |
| --- | --- |
| Successful config parameter edit | `review-ready`, atomic commit, reanalysis sees the new value |
| Invalid prepared syntax/JSON | `failed`, original bytes unchanged |
| Invalid shape relation | `failed`, original bytes unchanged |
| Requested targeted test failure | `failed`, original bytes unchanged |
| Concurrent source/config modification | commit rejected, concurrent bytes preserved |

The `set_parameter` oracle rejects added/removed topology, port changes, repeat/sharing changes, and
unresolved-fact changes. Expected and observed deltas must be model-equal before review. A skipped
optional runtime gate is not reported as passed; it is absent unless explicitly requested.

## Scope Boundary

Stage 6 does not implement structural transforms, fuzzy merge, arbitrary connection editing, or an
AgentProposal handoff. These remain Stage 7 work. Model-mode dragging continues to create only
`VisualPatch` records and cannot write source.

## Verification Record

- Full suite: 87 passed, 2 skipped because the test sandbox denied local socket creation. The same
  Studio API routes were exercised successfully against the loopback-only final server.
- Ruff, `compileall`, exported-schema freshness, Vite production build, and `git diff --check` pass.
- Browser QA passes at 1440x900 and 390x844 with no console warning/error, no document-width
  overflow, and no Inspector/review-surface overlap.
- The final demo transaction records all eight non-terminal states through `review-ready`, has seven
  passed verification gates, and has model-equal Expected and Observed Graph Delta.
- Canonical Transformer source/config and the copied demo project's original config remained byte
  unchanged after prepare/verify and all failure-path checks.

# Stage 7 Acceptance: Structural Round-Trip

## Delivered

- Versioned `SemanticStructuralPatch`, `ProposedConnection`, `AgentProposal`, expanded `GraphDelta`,
  and union `SourceTransaction` protocols with exported JSON schemas.
- A trusted registry for zero-argument GELU/ReLU/SiLU replacement and single-consumer sequential
  LayerNorm insertion through exact LibCST constructor and forward anchors.
- Transform-specific semantic oracles plus canonical fact digests. Prepare computes the expected
  delta; verify independently reanalyzes and requires model-equal expected and observed deltas.
- `archcanvas propose` and the Studio Proposed Connection flow. Both compatible and incompatible
  arbitrary connections remain handoffs because connection rewriting is not registered.
- Studio controls for both registered transforms, explicit source/target ports, source diff review,
  graph delta review, commit/discard, and visible denied shell/network/source-write permissions.

## Registry Boundary

| Intent | Result |
| --- | --- |
| Replace directly registered zero-argument GELU/ReLU/SiLU | Source transaction |
| Insert LayerNorm after a directly registered single-consumer module | Source transaction |
| Arbitrary connection or new branch | AgentProposal |
| Cross-attention, skip/loss path, rank change, or merge change | AgentProposal |
| Complex control flow or unknown multi-factory refactor | AgentProposal |

An AgentProposal is descriptive handoff context. Its schema rejects any true value for `shell`,
`network`, or `source_write`, so creating a proposal never authorizes execution or mutation.

## Mutation Evidence

- Replacing the prepared ReLU with SiLU fails exact Graph Delta comparison even though the same
  canonical node ID changed.
- Bypassing the inserted LayerNorm in the prepared forward path fails exact Graph Delta comparison.
- Unregistered structural operations fail request validation and cannot enter transaction prepare.
- Unsafe AgentProposal permission values fail protocol validation.
- All prepare/verify and proposal tests preserve the canonical fixture and original temporary
  project source bytes.

## Verification

The final suite contains 95 tests: 92 pass and 3 Studio socket tests skip because the command
sandbox denies local socket creation. The same HTTP transaction and proposal paths pass against the
final loopback Studio server. Ruff, `compileall`, exported-schema freshness, Vite production build,
and `git diff --check` pass.

Browser inspection passes at 1144x931 and in a true 390x844 same-origin viewport. The mobile page
reports `scrollWidth=390`; the top bar, canvas, floating Inspector, and bottom review panel remain
bounded. Desktop interaction produced a review-ready GELU-to-ReLU transaction with matching exact
deltas and seven passed gates. Proposed Connection displayed its compatibility reason and denied
shell, network, and source-write permissions.

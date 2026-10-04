# Semantic edits and reviewed source writeback

Read this reference only when the user changes model parameters, operators, tensor bindings, repetition, or Python symbols. Styling, layout, displayed labels, and legends use the visual workflow.

## Preview the actual intent

Resolve the canonical target, source/config origin, base corpus/IR digests, and all affected instances/calls. Display the effective value and its origin. A derived value or ambiguous source cannot be replaced by a guessed literal.

For an Attention Q edit, prove that the visible Q maps to an authored call argument, rather than a schematic decomposition of fused attention. Resolve the selected repeated layer's invocation/instance and sharing scope. If the producer or target is unresolved, preserve unresolved endpoints in the proposal instead of inventing IDs or expressions.

Inspect the installed transform registry. Only supported intents with satisfied preconditions can prepare a source transaction. Input rebind requires an identifiable call argument, a producer that dominates the consumer in the supported control region, a usable in-scope value, and compatible port/type/shape contracts. A second arrow does not automatically mean residual addition or concatenation.

For unsupported changes, retain an AgentProposal containing intent, relevant source evidence, intended graph delta, blockers, and a suggested code change. A proposal is not a verified transaction. Do not bypass the registry by rewriting the original file directly.

Approval cannot resolve a missing transform or an unverified required gate. Do not ask for confirmation while promising an unsupported change can then be applied; ask only for genuinely missing target/input information, and identify the capability blocker.

## Prepare, verify, review, commit

1. Freeze the relevant source/config version. Prepare the registered change in isolation, preserving surrounding classes, comments, expressions, formatting, and unrelated training code.
2. Compute the intended graph change independently of re-analysis. Re-parse staged source, compare observed structure/parameters/ports/sharing against that expectation, and run the required constraint checks. Report unknown or skipped gates as such.
3. Run an execution profile only if it is necessary for this change and allowed by the task and host. Specify environment, inputs, mode, isolation, timeout, and coverage. A static pass is not a runtime pass; one sampled trace is not full-program proof.
4. Present human-readable changes, affected modules, before/after figure, minimal source diff, validation results, unresolved points, and checkpoint implications. Technical GraphDelta details may be expandable.
5. Bind human approval to the exact transaction/diff/source version. If the user has already explicitly approved this concrete result in the session, use that evidence; a generic request to edit or a `ReviewReady` status alone does not record approval of a newly prepared diff.
6. Commit only after required gates, approval, freshness, and backup/recovery checks. If any relevant source or staged content changes, invalidate the previous approval and re-prepare. Re-analyze after commit and reconcile the existing canvas through unique identity mappings.

Model architecture and optimizer/checkpoint migration are separate changes. Report incompatible state shapes or new parameter keys; do not overwrite old weights as a side effect of editing source. Undo of a committed source change is a new guarded transaction, not ordinary canvas undo.

## Formal runtime capability boundary

Resolve the formal runtime and verify its provenance as described in [runtime-compatibility.md](runtime-compatibility.md). This Skill bundles no runtime. The formal visual Alpha has a verified CLI analysis/document service contract but no semantic transaction or source writeback implementation. The workflow names above remain semantic stages, not executable subcommands. Use only transaction interfaces that have actually been implemented and verified.

Before preparing or committing, inspect the actual intent registry, isolation mechanism, independent change verification, approval record, freshness checks, and backup/recovery path. Keep the concrete review visible to the user. A conversational review does not prove an implementation stores an approval binding or enforces a commit gate.

If the formal runtime is unavailable or required writeback protections cannot be verified, deliver a reviewable proposal or isolated patch/diff with the evidence that can actually be obtained, without replacing the originals. State the missing capability. Do not reuse the failed prototype's runtime to complete these stages, including through an existing configured entry point.

The failed prototype is a read-only reference for pitfalls or limited candidate code. Its receipts and expected outputs are not correctness oracles for source changes. A candidate transform must earn confidence through independent source-mapping, delta, preservation, freshness, and recovery checks in the new implementation before adoption.

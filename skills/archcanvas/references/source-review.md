# Semantic edits and reviewed source writeback

Read this reference only when the user changes model parameters, operators, tensor bindings, repetition, or Python symbols. Styling, layout, displayed labels, and legends use the visual workflow.

## Preview the actual intent

Resolve the canonical target, source/config origin, base corpus/IR digests, and all affected instances/calls. Display the effective value and its origin. A derived value or ambiguous source cannot be replaced by a guessed literal.

For an Attention Q edit, prove that the visible Q maps to an authored call argument, rather than a schematic decomposition of fused attention. Resolve the selected repeated layer's invocation/instance and sharing scope. If the producer or target is unresolved, preserve unresolved endpoints in the proposal instead of inventing IDs or expressions.

Inspect the installed transform registry. Only supported intents with satisfied preconditions can prepare a source transaction. Input rebind requires an identifiable call argument, a producer that dominates the consumer in the supported control region, a usable in-scope value, and compatible port/type/shape contracts. A second arrow does not automatically mean residual addition or concatenation.

The formal local Alpha's first RebindInput fragment is HTTP/Python only: one positional Name in an entry-root straight-line Identity/Dropout/ReLU/GELU chain, unique assignment, no in-place effects or unknown alias/state, and the same base input. Its compatibility receipt is conditional symbolic shape/dtype preservation; G6 is not run. Do not describe it as runtime shape verification or a complete M3 profile. Import-time symbol mutation, keyword inputs, control flow, nested/shared authored scopes, aliases/reassignment and different base inputs are unsupported. Consult actual `rebindScope` and source-bound candidates before preparing; do not invent a CLI rebind subcommand.

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

Resolve the formal runtime and verify its provenance as described in [runtime-compatibility.md](runtime-compatibility.md). This Skill bundles no runtime. The formal M2 Alpha registers only `set_dropout_probability` for an explicit floating-point literal in external PyTorch Dropout `p` or MultiheadAttention `dropout`. It has independent expected/observed static verification, exact review approval, freshness and guarded single-file recovery. Derived/config values, integer source literals, connections and multi-file semantic transactions remain unsupported. The actual CLI uses `patch prepare|review|approve|commit|discard`; every action requires explicit `--root`, `--entry` and private `--store`, and review/approval/commit require the exact transaction/digest/token flags reported by its help. CLI commit writes that explicit source root, while Studio HTTP commit writes a managed copy.

Studio/service edits are confined to a registered managed source copy. Prepare re-analyzes that project instead of trusting caller-provided canvas facts, and rejects stale source/IR bindings. The actual prepared review names all calls affected by the one source origin. Commit requires the unconsumed signed approval for that exact review, checks the complete discovered corpus and staged bytes, preserves a durable backup/journal, and re-analyzes after replacement. A managed-copy commit leaves the imported original directory untouched. Applying it to the original model remains a separate concrete source action and must not be claimed as already done.

The Python `TransactionManager` API may operate on an explicitly selected local source root, so verify the configured root and user authorization before using it. Test approvals exercised on `/tmp` hand-authored fixtures certify guards; they grant no authorization for real model files. Visual undo after a commit cannot restore old source bytes.

Before preparing or committing, inspect the actual intent registry, isolation mechanism, independent change verification, approval record, freshness checks, and backup/recovery path. Keep the concrete review visible to the user. A conversational review does not prove an implementation stores an approval binding or enforces a commit gate.

If the formal runtime is unavailable or required writeback protections cannot be verified, deliver a reviewable proposal or isolated patch/diff with the evidence that can actually be obtained, without replacing the originals. State the missing capability. Do not reuse the failed prototype's runtime to complete these stages, including through an existing configured entry point.

The failed prototype is a read-only reference for pitfalls or limited candidate code. Its receipts and expected outputs are not correctness oracles for source changes. A candidate transform must earn confidence through independent source-mapping, delta, preservation, freshness, and recovery checks in the new implementation before adoption.

# Semantic edits and reviewed source writeback

Read this reference only when the user changes model parameters, operators, tensor bindings, repetition, or Python symbols. Styling, layout, displayed labels, and legends use the visual workflow.

## Preview the actual intent

Resolve the canonical target, source/config origin, base corpus/IR digests, and all affected instances/calls. Display the effective value and its origin. A derived value or ambiguous source cannot be replaced by a guessed literal.

For an Attention Q edit, prove that the visible Q maps to an authored call argument, rather than a schematic decomposition of fused attention. Resolve the selected repeated layer's invocation/instance and sharing scope. If the producer or target is unresolved, preserve unresolved endpoints in the proposal instead of inventing IDs or expressions.

Inspect the installed transform registry. Only supported intents with satisfied preconditions can prepare a source transaction. Input rebind requires an identifiable call argument, a producer that dominates the consumer in the supported control region, a usable in-scope value, and compatible port/type/shape contracts. A second arrow does not automatically mean residual addition or concatenation.

The retained static RebindInput API accepts one positional Name in an entry-root straight-line Identity/Dropout/ReLU/GELU chain, unique assignment and the same base input. Its compatibility is conditional symbolic shape/dtype preservation and G6 remains not_run. The separate `structural-verified` path supports bounded unary/MultiheadAttention positional or keyword Name slots, declared named tensor shapes/dtypes/modes/seed and a dominating source-bound producer. A concrete input contract and independent static oracle are frozen before rewriting; the isolated staged model must match expected calls, ports, producer identities, shapes/dtypes, outputs, gradient/state facts and same-seed replay. Consult actual `structuralRebindScope` and candidates; `patch rebind` now exists and requires the explicit profile files. Do not promote the retained static path into runtime evidence.

Import-time symbol mutation, in-place/unknown effects, dynamic control, aliases/reassignment and unsupported nested/shared authored scopes remain blocked. A visible MHA Q/K/V port is editable only when its exact source argument and role are proved. Intentional rebinds can change numerical output: the runtime gate checks the declared structure/sample contract and does not require old/new outputs to agree.

`update_configuration` is limited to one unique module-top-level float literal whose every read is an analyzed Dropout/MHA probability argument. It changes the source origin once and shows all affected readers; derived values, hidden readers and shadowing/reassignment fail. `replace_activation` is limited to exact no-argument ReLU/GELU constructors with complete affected-instance scope. Studio and CLI use a required structural CPU profile; no generic activation or functional-code rewrite is implied.

For unsupported changes, retain an AgentProposal containing intent, relevant source evidence, intended graph delta, blockers, and a suggested code change. A proposal is not a verified transaction. Do not bypass the registry by rewriting the original file directly.

Approval cannot resolve a missing transform or an unverified required gate. Do not ask for confirmation while promising an unsupported change can then be applied; ask only for genuinely missing target/input information, and identify the capability blocker.

## Prepare, verify, review, commit

1. Freeze the relevant source/config version. Prepare the registered change in isolation, preserving surrounding classes, comments, expressions, formatting, and unrelated training code.
2. Compute the intended graph change independently of re-analysis. Re-parse staged source, compare observed structure/parameters/ports/sharing against that expectation, and run the required constraint checks. Report unknown or skipped gates as such.
3. Run an execution profile only when required/requested and allowed by the task and host. `structural-verified` requires actual Linux isolation, locked environment, named inputs, modes/seed, forward/backward, binding replay and state observations. If isolation is unavailable, a model fails, or the job is cancelled/times out, retain Failed and do not downgrade to static ReviewReady. A static pass is not a runtime pass; one sampled trace is not full-program proof.
4. Present human-readable changes, affected modules, before/after figure, minimal source diff, validation results, unresolved points, and checkpoint implications. Technical GraphDelta details may be expandable.
5. Bind human approval to the exact transaction/diff/source version. If the user has already explicitly approved this concrete result in the session, use that evidence; a generic request to edit or a `ReviewReady` status alone does not record approval of a newly prepared diff.
6. Commit only after required gates, approval, freshness, and backup/recovery checks. Relevant source/staged content, expected/observed deltas, input spec, profile/modes/seed/device, runtime receipt or locked environment bytes changing invalidate approval. Fresh environment binding rehashes actual files and probes trusted infrastructure; version strings alone do not establish freshness. Re-analyze after commit and reconcile the existing canvas through unique identity mappings.

Model architecture and optimizer/checkpoint migration are separate changes. Report incompatible state shapes or new parameter keys; do not overwrite old weights as a side effect of editing source. Undo of a committed source change is a new guarded transaction, not ordinary canvas undo.

## Formal runtime capability boundary

Resolve the formal runtime and verify provenance as described in [runtime-compatibility.md](runtime-compatibility.md). This Skill bundles no runtime. The local Alpha registers literal probability, unique top-level probability configuration, bounded ReLU/GELU replacement and input rebinding; each has a distinct scope/profile. The actual CLI uses `patch prepare|configuration|activation|rebind|review|approve|commit|discard`; every action requires explicit `--root`, `--entry` and private `--store`. Structural actions require input/environment flags, and review/approval/commit the exact transaction/digest/token reported by help. CLI commit writes that explicit source root; Studio HTTP commit writes a managed copy. Derived/ambiguous configuration, arbitrary structure changes and multi-file semantic commits remain unsupported.

Studio/service edits are confined to a registered managed source copy. Prepare re-analyzes that project instead of trusting caller-provided canvas facts, and rejects stale source/IR bindings. The actual prepared review names all calls affected by the one source origin. Commit requires the unconsumed signed approval for that exact review, checks the complete discovered corpus and staged bytes, preserves a durable backup/journal, and re-analyzes after replacement. A managed-copy commit leaves the imported original directory untouched. Applying it to the original model remains a separate concrete source action and must not be claimed as already done.

The Python `TransactionManager` API may operate on an explicitly selected local source root, so verify the configured root and user authorization before using it. Test approvals exercised on `/tmp` hand-authored fixtures certify guards; they grant no authorization for real model files. Visual undo after a commit cannot restore old source bytes.

Before preparing or committing, inspect the actual intent registry, isolation mechanism, independent change verification, approval record, freshness checks, and backup/recovery path. Keep the concrete review visible to the user. A conversational review does not prove an implementation stores an approval binding or enforces a commit gate.

If the formal runtime is unavailable or required writeback protections cannot be verified, deliver a reviewable proposal or isolated patch/diff with the evidence that can actually be obtained, without replacing the originals. State the missing capability. Do not reuse the failed prototype's runtime to complete these stages, including through an existing configured entry point.

The failed prototype is a read-only reference for pitfalls or limited candidate code. Its receipts and expected outputs are not correctness oracles for source changes. A candidate transform must earn confidence through independent source-mapping, delta, preservation, freshness, and recovery checks in the new implementation before adoption.

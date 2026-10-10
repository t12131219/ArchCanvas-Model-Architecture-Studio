# Runtime compatibility

A Skill description does not install a runtime. Identify this copy with its launcher and `doctor`; use its actual version, asset hashes and module counts. Frozen Beta.2 is a historical 17/3 distribution. Current development capabilities are not its release certification. Human/publication/performance gates and actual three-host client E2E remain open.

## Resolve a formal runtime

Start with an explicitly configured formal runtime, a documented installation for this product, or its formal project configuration. Resolve the executable, interpreter, package origin, helper target, working directory, and symlinks before use. A matching executable name or an existing configuration entry is insufficient evidence of identity.

`ArchCanvas_Model Architecture Studio_Temp` is a failed prototype. Do not use it as the development runtime, run its helper, copy its command contract, or fall back to it when the formal runtime is missing. This also applies when a configured executable, package, helper, or symlink resolves into that directory. Report the obsolete configuration and continue work that does not require the runtime.

Use the formal runtime's own documentation and available help/capability interface to establish the supported operations. Invoke only interfaces whose existence and side effects have been checked. The local Alpha has static CLI analysis, a document service, current-scene SVG/PDF/PNG, registered probability/configuration edits, ReLU/GELU replacement and bounded input rebinding. `patch prepare|configuration|activation|rebind|review|approve|commit|discard` exists; `runtime` is an explicit isolated CPU observation command. Inspect `supportedIntents`, `semanticScope`, `activationScope`, `rebindScope`, `structuralRebindScope`, `runtimeObservation`, `runtimeProfiles`, `publicationExport`, exact per-action help and actual provenance. The retained same-input unary static path and the new required-execution structural profile are separate contracts.

Use the project's configured environment when available. Do not install dependencies or modify a global environment merely to compensate for a missing implementation. Checking runtime identity and dependencies must not import or execute a user's model.

## Explicit isolated CPU profile

The formal checkout uses its own `.venv-runtime` and exact `requirements-runtime.lock`; publication uses a separate `.venv`. Runtime setup is documented in the formal README: the CPU PyTorch wheel comes from the official PyTorch CPU index, then the remaining exact pins are installed inside the formal venv. Do not substitute a prototype/user interpreter or silently download weights.

`archcanvas_runtime.runtime_capabilities(config)` probes trusted infrastructure and the locked framework only. `config` explicitly names absolute `interpreter` and `dependencyLock` files; optional limits are `timeoutSeconds`, `memoryMb`, `cpuSeconds`. `verify_structural(root, entry, input_spec, config)` is the executing API. The CLI requires `runtime --root --entry --input-spec --interpreter --dependency-lock`, with optional `--output`; exit 0 means passed, exit 2 means failed/unavailable. Source rendering continues to use nonexecuting `analyze`.

InputSpec v1 declares all named tensor inputs, each with bounded shape, float32/float64/int64/bool dtype and normal/zeros/ones fill, plus seed, unique eval/train modes and an empty constructor object. Only source-default model construction is currently supported. Model execution is explicit; capability checks never import the user's source.

Only Linux x86-64 isolation has actual acceptance evidence. Mandatory Bubblewrap namespaces and kernel seccomp deny network sockets and new processes. Frozen source is read-only; scratch is private. The worker sees the formal venv and narrow private read-only Python executable, standard-library and ELF-dependency copies, not the complete host/Conda directory. Receipts bind actual interpreter, installed environment bytes, lock, adapter, source generation and input spec. They record kernel probes and per-process address-space/CPU/file/open-file limits, wall timeout and task restrictions. These limits do not include cgroup aggregate RSS or a total tmpfs quota.

Isolation or environment validation failure yields `unavailable` and disables that execution profile; never substitute an ordinary subprocess or turn skipped G6 into passed. Model exceptions, timeout or cancellation yield failed receipts. A successful receipt contains per-mode module calls, named ports, actual tensor producers, shape/dtype, forward/backward, same-seed fresh-construction replay and parameter/buffer/shared state facts. These are observed samples, not complete path coverage or old/new numerical equivalence. Arbitrary functional operations can retain unresolved producers; semantic writes also require their independent static contract/oracle. Checkpoints, optimizers and training progress are not loaded or migrated.

## Check capabilities for the requested workflow

Treat the following as capability requirements, not implemented commands or a required manifest schema. Record the runtime identity/version, evidence inspected, supported scope, and any unmet requirements before making capability claims.

| Workflow | Evidence to check in the formal runtime |
| --- | --- |
| Source analysis | Supported frameworks, model entry/config/input contracts, static versus executing paths, source evidence and unresolved facts. |
| Open the Studio | Real document loading and a usable local service or app, service lifecycle, session/document identity, and a returned URL or host opening mechanism. |
| Visual editing | Actual CanvasDocument mutations for layout, aliases, glyphs, styles, legends, groups, hierarchy and routing; undo/redo; save and reopen. |
| Edited export | The same saved document and scene used by the editor, supported formats, font/style treatment, and visual checks of the exported result. |
| Semantic proposal | Canonical targets, supported intent registry, unresolved blockers, and source/graph evidence without original-file mutation. |
| Source transaction | Isolation, independent expected/observed change checks, concrete approval binding, freshness, backup/recovery, commit and post-commit reconciliation. |
| Optional execution | Explicit environment/input/mode contracts, isolation, timeout, and a receipt distinguishing observed coverage from static evidence. |

Inspect implementation and appropriate independent verification; labels in a manifest, fixtures, interface fields, or inherited prototype tests alone do not demonstrate an end-to-end capability. A rendered SVG does not establish an interactive editor, and a successful save does not establish faithful edited export. Check the full path needed by the user rather than advertising every planned feature.

For a supported Studio service, use the harness's available managed/background process mechanism, retain its actual lifecycle receipt/log, and open its returned local address. Do not claim availability after the host terminates the process. Browser opening and browser automation are distinct host capabilities. Model execution is a separate conditional workflow; never make it the implicit prerequisite for a static figure.

## When a capability is unavailable

Report the specific missing runtime or operation and preserve the available source evidence and visual documents. Source-grounded design, visual specifications, reviewable proposals, and development of the new formal implementation can continue within the authorized task. Do not claim a completed interactive bidirectional framework or a successful writeback based on Skill instructions alone. Follow [source-review.md](source-review.md) for semantic changes.

## Failed-prototype reference policy

The failed prototype may be inspected read-only to identify pitfalls or a narrowly scoped candidate implementation. It is not a support matrix, trusted baseline, expected-result oracle, or acceptance evidence for the formal product. Any candidate code requires a stated reason for reuse, dependency/license review, independent verification of its behavior, and validation in the new design before limited incorporation. Default to a fresh implementation when that confidence is absent.


## New authored model drafts

For a request to build a model from zero, the current formal Studio has a separate authored-draft workspace and the actual runtime’s catalog and transparent starting graphs. Check `modelAuthoring` and the actual `/api/authoring/catalog`; create and save a draft rather than inserting fabricated source-bound nodes into a CanvasDocument. Generation statically validates declared tensors, exact operation/port bindings and generated source facts; it never executes the model. Opening “编辑当前模型” imports a source-derived draft that retains the current frontier’s layout, style, hierarchy, selection and camera, and source-frontier rebase refuses changed source or IR digests. Open the generated source as a new managed project only after showing the concrete source. This is distinct from structural writeback into an existing imported model, which retains its reviewed transaction requirements.

The development library exposes transparent starting graphs, including MLP, CNN, residual, convolutional, attention, recurrent, embedding, decoder, U-Net and projection variants. Click or drag one from the left library, then edit its ordinary modules, parameters and tensor connections. These are transparent draft graphs built from registered atomic kinds, not opaque whole-network promises or executed models. A new harness must still establish that its actual Studio provides this UI; representative AI trials do not certify human usability or publication quality. The older three-graph statement above remains historical evidence only.

Authoring validation errors may include structured Chinese diagnostics while preserving English technical text. Resolve node/parameter/port targets against actual unique catalog identities; never infer targets from labels. Invalid raw parameter text blocks draft save/generation. Arrangement fits the updated draft and empty search states explain unsupported modules; consult the configured checkout’s `docs/m4-authoring-feedback.md` for source/build-bound UI evidence and open M4 gates.

## Precise canvas handoff

When `capabilities.canvasSessions` is present, `open --root SOURCE_ROOT --entry module:Class --server http://127.0.0.1:8765` performs static analysis and creates/reopens the exact persisted document. It returns `documentId`, `sessionId`, storage revision, managed project identity and the document URL. The service must already be running. HTTP open accepts frozen analyzed source contents, never filesystem roots. The URL chooses that document before browser recovery; a missing requested document reports an error rather than silently opening a default example.

`session read --document-id ID` returns the saved document and history. `session apply --operations ops.json --expected-revision N --visual-revision V`, `undo`, `redo` and `export` use that same persisted session. Apply accepts only the Studio typed visual operations. Save accepts a CanvasDocument or a saved history envelope and its actual storage revision. Source facts stay immutable. A clean visible Studio polls for saved external visual updates; unsaved edits are retained and a stale save fails with a conflict. Save UI edits before an external operation. History remains bounded by 100 snapshots and the 4 MB stored-envelope budget; the current persistence layer stores immutable architecture facts once and reconstructs exact snapshots on read. Source-derived draft persistence and authoring requests have a separate 16 MB budget.

`serve --data-dir PATH` now treats PATH as the complete state root, with `documents`, `projects`, `drafts`, `exports`, and `transactions` beneath it. The default stays `<formal-runtime>/.archcanvas`. For old explicit document directories, select their original parent only when intentionally reopening that legacy state; there is no automatic migration. Use independent roots and one process per root.

CLI publication stages artifact and receipt together and restores prior files on ordinary commit failure. This does not promise a filesystem-wide transaction during power loss. Read the same saved document before exporting, verify receipt digests and inspect the rendered figure.

## Unfamiliar source models

Use [source-coverage.md](source-coverage.md) to distinguish display/edit support from semantic lowering. The current implementation projects pure source-draft presentation edits into the original canvas through typed `title`, `alias`, `nodeStyle`, `nodeLayout` and `portLayout` operations. Hidden layout and history persist; opaque operators do not require source generation for those edits. A changed generated-model binding falls back to its independently verified generation workflow. Unresolved conditional regions expose authored branch/module source for inspection without a selected configuration; real configuration evidence remains necessary for choosing an execution path and deeper tensor lowering.

For a new release from a changed development checkout, use `python scripts/m5_beta_bundle.py candidate --project-root ROOT --version VERSION --output ARCHIVE`. This stages fresh asset bindings and verifies the candidate without rewriting the historical checked-in Beta.2 receipt. `pack` remains strict against the selected tree's own release manifest.

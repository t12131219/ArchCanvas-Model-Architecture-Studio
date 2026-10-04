# Runtime discovery and capability checks

This Skill is an instruction package. It does not bundle the runtime, Python dependencies, a built Studio, or model adapters. The formal checkout now contains an independently implemented visual Alpha; its verified local entry and limits are described in [formal-alpha.md](formal-alpha.md). Copying the Skill does not install that checkout or establish the runtime's availability in another harness.

## Resolve a formal runtime

Start with an explicitly configured formal runtime, a documented installation for this product, or its formal project configuration. Resolve the executable, interpreter, package origin, helper target, working directory, and symlinks before use. A matching executable name or an existing configuration entry is insufficient evidence of identity.

`ArchCanvas_Model Architecture Studio_Temp` is a failed prototype. Do not use it as the development runtime, run its helper, copy its command contract, or fall back to it when the formal runtime is missing. This also applies when a configured executable, package, helper, or symlink resolves into that directory. Report the obsolete configuration and continue work that does not require the runtime.

Use the formal runtime's own documentation and available help/capability interface to establish the supported operations. Invoke only interfaces whose existence and side effects have been checked. The current Alpha has CLI analysis and a local document service, but no source transaction interface. Do not infer planned commands from workflow stage names or invent success receipts.

Use the project's configured environment when available. Do not install dependencies or modify a global environment merely to compensate for a missing implementation. Checking runtime identity and dependencies must not import or execute a user's model.

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

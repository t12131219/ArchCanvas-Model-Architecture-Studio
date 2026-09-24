---
name: archcanvas
description: Analyze real model source into evidence-backed architecture IR, validate architecture artifacts, and prepare publication or editing workflows. Use for model architecture recovery, source-to-diagram work, architecture explanation, visual-only diagram edits, or reviewed semantic model changes; do not use as a generic flowchart tool.
---

# ArchCanvas

Start read-only. Resolve the repository, entrypoint, task branch, configuration, and execution mode before claiming an exact architecture.

## Workflow

1. Run `archcanvas doctor --json` when environment support is unknown.
2. For analyze, draw, or explain requests, run `archcanvas analyze` before any rendering step.
3. Treat source and replayable runtime evidence as truth. Treat papers, READMEs, comments, names, and reference images as secondary evidence.
4. Preserve uncertainty as `unresolved`; never fill missing execution facts from a familiar model name.
5. Run `archcanvas validate` on generated Exact IR and report the receipt and artifact paths.

Read [references/evidence-contract.md](references/evidence-contract.md) when resolving conflicts, reviewing provenance, or adding an adapter.
Read [references/pattern-pack-contract.md](references/pattern-pack-contract.md) when enabling a
workspace pack, reviewing a generated candidate, or interpreting an ambiguous match.

## Editing boundary

- Visual requests may change only CanvasDocument or VisualSpec state.
- Model changes require a semantic proposal, isolated prepare/verify phases, source diff, expected and observed graph delta, and explicit user commit.
- Only registered structural transforms may enter a source transaction. Route connections, branches, rank/merge changes, complex control flow, and unknown refactors to an AgentProposal with no shell, network, or source-write permission.
- A request to draw or drag does not authorize source writes.
- If a requested capability is unavailable, return the structured capability error and do not improvise a direct source edit.

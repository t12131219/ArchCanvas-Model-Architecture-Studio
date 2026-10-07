---
name: archcanvas
description: Create source-grounded, publication-style deep learning model diagrams and edit their canvas, glyphs, legends, and hierarchy through ArchCanvas Studio. Use for model source-to-figure work, visual refinement, in-place expansion, and reviewed model edits.
---

# ArchCanvas

Turn model source into a readable research figure and a persistent canvas that the user can refine directly or through natural language. Prioritize the first view, spatial continuity, object-level editing, and faithful export. Model facts come from source evidence; presentation comes from the canvas document.

For current M5 packaging and host evidence, read the configured checkout’s [release scope](../../docs/m5-beta-release.md). M4 remains partial; the user explicitly authorized development to continue while human trials and publication review remain open. Do not treat starting M5 or a local bundle as a certified Beta release.

## Implementation baseline

Build the formal product from scratch around its independent contracts. `ArchCanvas_Model Architecture Studio_Temp` is a failed prototype, not the development runtime or a migration baseline. Do not auto-discover, execute, import, or fall back to it. Its code may be consulted as low-confidence historical evidence; any small candidate reused in the formal runtime needs independent correctness evidence, identified dependencies, and a documented reason. Existing prototype tests or demos alone do not establish that confidence.

## Choose the workflow

For every workflow, establish the actual runtime contract using [runtime-compatibility.md](references/runtime-compatibility.md) before calling tools. Inspect [host-adapters.md](references/host-adapters.md) when discovery, permissions, or presentation capabilities are unknown; reuse already confirmed session capabilities.

- **Build a new model from zero:** When the formal runtime exposes `modelAuthoring`, use Studio’s separate authored draft and actual module catalog. Create typed nodes/connections, validate the complete graph, show the generated source, then open a fresh managed model for figure editing. Draft edits do not structurally rewrite an imported CanvasDocument; declared tensors are not runtime observations.
- **Create or open a model figure:** Resolve the repository and model entry from available files, use a verified formal runtime to analyze and render, then open the same document in Studio. Read [runtime-compatibility.md](references/runtime-compatibility.md) for discovery and capability checks.
- **Refine an existing figure:** Read [visual-workflow.md](references/visual-workflow.md). Change the document through supported visual operations; preserve identities, manual arrangement, and history. Reversible styling, labels, legends, routing, and layout changes do not need a source review.

For the supported Studio frontier caches, visual movement uses canvas-world units. An omitted move scope preserves `all-frontiers`; choose `current-frontier` explicitly when only the visible frontier should change. Dragging, alignment, recovery and bounded natural-language movement share the selected scope, and preview/commit use the same scope. Preserve stable source, IR and canonical identities together with pinned and ancestor protections. This bounded stage does not establish presented FPS, global routing quality, publication acceptance or human usability.
- **Change model parameters or connections:** Read [source-review.md](references/source-review.md). Preview a semantic intent, prepare and verify an isolated source change, show the concrete review, and commit only the approved version.
- **Package, install, or change harness:** Read [host-adapters.md](references/host-adapters.md). Use the same Skill and Studio across Codex, Claude Code, and the official DeepSeek Harness, adapting only discovery, tools, presentation, and permissions.

## From request to canvas

1. Reuse the active document/session if one exists. Otherwise inspect source to identify entry, construction/configuration, task, and train/eval mode. Infer what is unambiguous; ask only for information needed to select a real model or operation. Do not require input shapes for a static figure when analysis can proceed without them.
2. Check the available runtime and host capabilities. CLI is the baseline; an installed MCP adapter may expose the same operations. Read local help and receipts before using commands. This distribution contains instructions, not a bundled runtime or a completed editor.
3. Generate a source-backed overview with explicit opaque regions. Start with a paper preset and an appropriate level of abstraction, rather than displaying every low-level operator. Do not fill missing model details from a textbook template.
4. Open Studio in the host's available browser/panel, or return its actual local URL. Show the exported figure when inline artifacts are supported. Keep one CanvasDocument for gestures and language edits. If only static output is available, identify that the interactive goal remains incomplete. When source material is sufficient, a clearly labeled static draft can accompany that explanation; do not claim an interactive session exists.
5. For edits, resolve targets by stable identity and visible selection. “Make Encoder blue” changes presentation; “set dropout to 0.2” changes model semantics. Ask a focused question if the intended target or meaning remains ambiguous.
6. Inspect the rendered result at overview and final export size. Check text, hierarchy, residual/memory routes, legend meaning, and black-and-white readability. Save the document and export from its current scene. Report actual paths, remaining unsupported operations, and source changes only when they occurred.

## Preserve these contracts

- A compatible Studio must allow display aliases and registered glyph styles for source-bound nodes; they do not rename Python symbols or change operator type. Check the installed runtime before claiming this contract is implemented.
- Expand Encoder → layer → Attention in place where hierarchy evidence permits. Restore prior local layout on re-expansion; protect unrelated pinned objects.
- Visual operations cannot change source bytes, model parameters, canonical port bindings, or the semantic IR digest. An explanatory arrow is distinct from a tensor binding.
- Natural-language edits and direct gestures must use the same supported document operations. Do not regenerate an unrelated HTML/SVG after each edit or silently patch generated assets behind Studio's back.
- Expose actual support. A visible node or a passing static check does not imply a supported writeback, execution, or full interactive editor. An unsupported structural edit remains a proposal.
- Loading this Skill does not grant tool permissions. Honor the user's authorized scope and the active harness policy; do not execute a model merely to draw a static figure.

If a requested editor capability is absent, report the concrete gap and retain the current document. A source-backed static draft may accompany a capability gap, but never replaces an existing edited document or proves that Studio persisted the changes. For a standalone figure request, a source-backed SVG is a valid final artifact.

---
name: archcanvas
description: Create source-grounded, publication-style deep learning model diagrams and edit their canvas, glyphs, legends, and hierarchy through ArchCanvas Studio. Use for model source-to-figure work, visual refinement, in-place expansion, and reviewed model edits.
---

# ArchCanvas

Turn model source into a readable research figure and a persistent canvas that the user can refine directly or through natural language. Prioritize the first view, spatial continuity, object-level editing, and faithful export. Model facts come from source evidence; presentation comes from the canvas document.

Resolve this copy's runtime using `python3 -I -B scripts/archcanvas_runtime.py doctor` from the Skill directory. An installed copy has `archcanvas-install.json` and an embedded release; the source-tree launcher uses its containing formal checkout. A separately copied development Skill requires an explicit `archcanvas-runtime.json` containing an absolute `runtimeRoot`. Never guess a runtime or fall back to the failed prototype. A copied instruction file without a bound runtime cannot deliver a canvas. Use the actual doctor's release version, asset hashes and catalog counts; historical Beta.2 and the current checkout are different versions. M4 human, publication and performance gates and three-host E2E remain open.

## Implementation baseline

Build the formal product from scratch around its independent contracts. `ArchCanvas_Model Architecture Studio_Temp` is a failed prototype, not the development runtime or a migration baseline. Do not auto-discover, execute, import, or fall back to it. Its code may be consulted as low-confidence historical evidence; any small candidate reused in the formal runtime needs independent correctness evidence, identified dependencies, and a documented reason. Existing prototype tests or demos alone do not establish that confidence.

## Choose the workflow

For every workflow, establish the actual runtime contract using [runtime-compatibility.md](references/runtime-compatibility.md) before calling tools. Inspect [host-adapters.md](references/host-adapters.md) when discovery, permissions, or presentation capabilities are unknown; reuse already confirmed session capabilities.

- **Build a new model from zero:** When the formal runtime exposes `modelAuthoring`, use Studio’s separate authored draft and actual module catalog. Discover the live `/api/authoring/catalog` and the doctor's preset count; do not assume the development checkout's counts apply to an installed release. Create typed nodes/connections, validate the complete graph, show the generated source, then open a fresh managed model for figure editing. Draft edits do not structurally rewrite an imported CanvasDocument; declared tensors are not runtime observations.
- **Create or open a model figure:** Resolve the repository and model entry from available files, use a verified formal runtime to analyze and render, then open the same document in Studio. Read [runtime-compatibility.md](references/runtime-compatibility.md) for discovery and capability checks.
- **Refine an existing figure:** Read [visual-workflow.md](references/visual-workflow.md). Change the document through supported visual operations; preserve identities, manual arrangement, and history. Reversible styling, labels, legends, routing, and layout changes do not need a source review.

For the supported Studio frontier caches, visual movement uses canvas-world units. An omitted move scope preserves `all-frontiers`; choose `current-frontier` explicitly when only the visible frontier should change. Dragging, alignment, recovery and bounded natural-language movement share the selected scope, and preview/commit use the same scope. Preserve stable source, IR and canonical identities together with pinned and ancestor protections. This bounded stage does not establish presented FPS, global routing quality, publication acceptance or human usability.
- **Continue from a source view:** Use the Studio “编辑当前模型” entry. In runtimes supporting source composition editing, composites with source children recursively expand into a separate editing frontier, including source inspection beneath unresolved conditional regions. Inspection shows authored alternatives and definitions without claiming their execution or tensor bindings. The compact view and editor layout/history are retained separately. Source-frontier rebasing requires unchanged source and IR digests; visual edits remain separate from source bytes. The editor surface is an infinite world-anchored dot canvas, while publication exports omit the editing grid.
- **Change model parameters or connections:** Read [source-review.md](references/source-review.md). Preview a semantic intent, prepare and verify an isolated source change, show the concrete review, and commit only the approved version.
- **Package, install, or change harness:** Read [host-adapters.md](references/host-adapters.md). Use the same Skill and Studio across Codex, Claude Code, and the official DeepSeek Harness, adapting only discovery, tools, presentation, and permissions.

## From request to canvas

1. Reuse the active document/session if one exists. Otherwise inspect source to identify entry, construction/configuration, task, and train/eval mode. Infer what is unambiguous; ask only for information needed to select a real model or operation. Do not require input shapes for a static figure when analysis can proceed without them.
2. Check the available runtime and host capabilities. CLI is the baseline; an installed MCP adapter may expose the same operations. Read local help and receipts before using commands. A source-tree Skill binds to the formal checkout; an installed Skill binds to its embedded verified runtime and Studio. A copied instruction-only file has no runtime until an explicit binding is supplied.
3. Generate a source-backed overview with explicit opaque regions. Start with a paper preset and an appropriate level of abstraction, rather than displaying every low-level operator. Do not fill missing model details from a textbook template.
4. Open Studio in the host's available browser/panel, or return its actual local URL. Show the exported figure when inline artifacts are supported. Keep one CanvasDocument for gestures and language edits. If only static output is available, identify that the interactive goal remains incomplete. When source material is sufficient, a clearly labeled static draft can accompany that explanation; do not claim an interactive session exists.
   Where `canvasSessions` is available, start a loopback service with an independent state root, then call `open --root SOURCE_ROOT --entry module:Class --server URL`. Open the returned exact `?documentId=...` URL. Reuse its session identity for `session read/apply/undo/redo/save/export`; mutations require the actual storage and visual revisions. Send only supported typed visual operations; they use the Studio reducer and persistent history. Read first, preserve unsaved UI changes, and handle revision conflicts. Do not claim an arbitrary natural-language or source rewrite API.
5. For edits, resolve targets by stable identity and visible selection. “Make Encoder blue” changes presentation; “set dropout to 0.2” changes model semantics. Ask a focused question if the intended target or meaning remains ambiguous.
6. Inspect the rendered result at overview and final export size. Check text, hierarchy, residual/memory routes, legend meaning, and black-and-white readability. Save the document and export from its current scene. Report actual paths, remaining unsupported operations, and source changes only when they occurred.

## Unfamiliar models

Read [source-coverage.md](references/source-coverage.md) for a model absent from the preset catalog or a source region that remains opaque. Use source evidence for all names and structures. Preserve visual editing on the original canvas even when semantic generation is unsupported; unresolved configs and dynamic code remain explicit boundaries.

## Preserve these contracts

- A compatible Studio must allow display aliases and registered glyph styles for source-bound nodes; they do not rename Python symbols or change operator type. Check the installed runtime before claiming this contract is implemented.
- Expand Encoder → layer → Attention in place where hierarchy evidence permits. Restore prior local layout on re-expansion; protect unrelated pinned objects.
- Visual operations cannot change source bytes, model parameters, canonical port bindings, or the semantic IR digest. An explanatory arrow is distinct from a tensor binding.
- Natural-language edits and direct gestures must use the same supported document operations. Do not regenerate an unrelated HTML/SVG after each edit or silently patch generated assets behind Studio's back.
- Expose actual support. A visible node or a passing static check does not imply a supported writeback, execution, or full interactive editor. An unsupported structural edit remains a proposal.
- Loading this Skill does not grant tool permissions. Honor the user's authorized scope and the active harness policy; do not execute a model merely to draw a static figure.

If a requested editor capability is absent, report the concrete gap and retain the current document. A source-backed static draft may accompany a capability gap, but never replaces an existing edited document or proves that Studio persisted the changes. For a standalone figure request, a source-backed SVG is a valid final artifact.

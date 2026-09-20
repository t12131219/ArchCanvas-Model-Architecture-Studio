---
name: archcanvas-model-architecture
description: Analyze supported PyTorch model source into a source-aware architecture view, create publication-ready architecture artifacts, or plan a validated model-architecture edit. Use when a user asks to inspect, diagram, export, or safely change a neural-network architecture with ArchCanvas.
---

# ArchCanvas Model Architecture

Architecture semantics come from user source and re-analysis. The canvas is a view; it is
never a substitute for source code or an authorization to modify it.

## Availability

When ArchCanvas MCP is available, call `archcanvas_health` once at the start of the
conversation and use only the capabilities it reports. Do not install, upgrade, provision,
or fabricate unavailable tools. If the required analysis or commit capability is unavailable,
state that clearly and stop before claiming an artifact, validation result, or source change.

## Route By Request

| User intent | Read |
| --- | --- |
| Inspect a supported PyTorch project or create a diagram | `references/architecture-contract.md` |
| Export a publication architecture figure | `references/architecture-contract.md` |
| Change a model parameter or structure | `references/architecture-contract.md` |
| Tool, project-root, or commit failure | `references/architecture-contract.md` |

## Core Constraints

- Treat a project path suggested by the model as a candidate, not authority. Use only an
  approved root reported by the host or engine.
- Keep Exact Architecture IR, Publication IR, and CanvasDocument separate.
- Visual edits persist as visual patches only. They must not enter a source transaction.
- Source edits follow `analyze -> plan -> candidate diff -> validate -> explicit commit ->
  re-analyze`. Never fold commit into analysis, rendering, plan, or validation.
- Report unresolved or unsupported code honestly. Do not infer confirmed architecture facts
  from a visually plausible diagram.

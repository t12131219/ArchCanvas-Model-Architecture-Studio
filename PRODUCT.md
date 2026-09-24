# Product Baseline

ArchCanvas compiles selected model source, configuration, and optional replayable runtime evidence
into an auditable architecture representation. Exact IR drives L1-L4 publication views, SVG/HTML,
the visual-only Studio, reviewed source transactions, and portable offline review bundles.

The non-negotiable product loop is:

```text
source snapshot -> evidence -> Exact IR -> validation -> publication view
```

Visual edits belong to a separate `CanvasDocument`. Semantic edits are prepared in an isolated
transaction and require an explicit commit. A reference image or Pattern Pack may guide visual
language and semantic grouping but cannot add executable facts.

The Stage 9 release surface includes PyTorch, static Keras/JAX, and ONNX adapters; Codex and Claude
Code local installers; and a digest-verified offline bundle. Runtime evidence and source
transactions remain PyTorch-only. Claude API and claude.ai distribution are explicitly unsupported.

# Product Baseline

ArchCanvas compiles selected model source, configuration, and optional replayable runtime evidence into an auditable architecture representation. The same representation will later drive publication views, SVG, HTML, and the Studio.

The non-negotiable product loop is:

```text
source snapshot -> evidence -> Exact IR -> validation -> publication view
```

Visual edits belong to a separate `CanvasDocument`. Semantic edits will be prepared in an isolated transaction and require an explicit commit. A reference image may guide visual language but cannot add executable facts.

The current milestone is the rewrite baseline plus the start of the Transformer vertical slice. It does not claim publication rendering, runtime confirmation, or source round-trip support.

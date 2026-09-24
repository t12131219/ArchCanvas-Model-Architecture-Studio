# Design Direction

The Studio opens directly into a compact Paper x Instrument workspace: project and view controls
above, model navigation on the left, the architecture canvas in the center, evidence and
visual/model inspectors on the right, and validation surfaces below.

Explore, Layout, and Model are distinct modes. Layout changes write visual patches only. Model changes create proposals and never become source writes without a reviewed transaction.

The canonical render surface is SVG derived from `VisualScene`. Interactive state, hover state, and viewport state cannot alter the exported graph semantics.

Framework adapters depend on core protocols, never the reverse. Python adapters are static and do
not import target frameworks. ONNX parsing is isolated behind an optional official parser. Release
bundles contain redacted analysis records, frozen publication artifacts, schemas, a support matrix,
and file digests; they do not contain a second semantic representation.

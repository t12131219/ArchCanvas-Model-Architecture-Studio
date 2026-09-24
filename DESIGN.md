# Design Direction

The Studio opens directly into a compact Paper x Instrument workspace: project and view controls
above, model navigation on the left, the architecture canvas in the center, evidence and
visual/model inspectors on the right, and validation surfaces below.

Explore, Layout, and Model are distinct modes. Layout changes write visual patches only. Model changes create proposals and never become source writes without a reviewed transaction.

The canonical render surface is SVG derived from `VisualScene`. Interactive state, hover state, and viewport state cannot alter the exported graph semantics.

Studio state is separated into project/canonical, draft authoring, visual document, interaction,
and job/validation planes. Draft identities never enter Exact IR, proof overlays never enter
`VisualPatch`, and search/focus never changes either document. Project, analysis, and validation
results carry generation or fingerprint bindings so late responses cannot replace newer state.

Framework adapters depend on core protocols, never the reverse. Python adapters are static and do
not import target frameworks. ONNX parsing is isolated behind an optional official parser. Release
bundles contain redacted analysis records, frozen publication artifacts, schemas, a support matrix,
and file digests; they do not contain a second semantic representation.

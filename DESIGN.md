# Design Direction

The future Studio opens directly into a compact Paper x Instrument workspace: project and view controls above, model navigation on the left, the architecture canvas in the center, evidence and visual/model inspectors on the right, and validation surfaces below.

Explore, Layout, and Model are distinct modes. Layout changes write visual patches only. Model changes create proposals and never become source writes without a reviewed transaction.

The canonical render surface is SVG derived from `VisualScene`. Interactive state, hover state, and viewport state cannot alter the exported graph semantics.


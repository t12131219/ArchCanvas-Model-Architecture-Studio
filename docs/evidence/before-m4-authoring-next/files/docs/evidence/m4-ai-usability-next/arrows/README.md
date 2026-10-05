# AI arrow review evidence

- `matrix-geometry.json`: independent read-only geometry audit of 39 saved actual browser SVGs from old `index-Cr_xKW9U.js`. Historical findings remain failed where routes cross bodies.
- `audit_geometry.py` / `test_geometry.py`: saved-SVG oracle and 7 deliberate counterexample tests; no product router imports.
- `shared-ui-move-geometry.json`, `audit_moves.py`, `saved-ui-svg/`: independent read-only review/extraction of root's 16 actual old-build move captures. No UI operation was performed by these scripts.
- `candidate/`: early CPU rerenders and CPU performance diagnostics. SVGs and original test receipts here predate final structured diagnostics. They are retained as development evidence and do not establish final browser coverage.
- `frozen-final/manifest.json`, `files/`: durable final formal source/build freeze after 102 passing Studio tests, strict TypeScript and build success. The manifest binds `index-DgtJrWU9.js`.
- `frozen-final/generate_cpu.mjs`, `cpu-scenes.json`, `cpu-scenes/`: final frozen core rerender of the 39 historical canvas inputs, with input/archive hashes checked. Interactive SVG mode is used solely to expose grouped saved port dots to the oracle; no browser is involved.
- `frozen-final/audit_cpu.py`, `independent-geometry.json`: same independent saved-SVG oracle applied to the CPU rerenders. No inherited browser or human acceptance is claimed.

The separate `../routing-independent/` review additionally checks own endpoint bodies, expanded headers, exact canonical coverage, source-fact preservation, seeded fields, stress moves, bounded fallback and numerical tolerance. The narrative is [m4-arrow-routing-audit.md](../../../m4-arrow-routing-audit.md).

# Architecture index cache experiment

The experiment caches read-only source-architecture indexes in a WeakMap. `sourceFacts` are rebuilt per scene to keep returned metadata detached. The baseline archive preserves the previous source/test/frozen dist bytes. `core-after-reference.json` was run against the archived scene copy with full document/history/scene/interactive-SVG equivalence assertions. These are CPU measurements only; browser paint, presented FPS, and native Event Timing remain unmeasured.

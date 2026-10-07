# Bounded Output caption repair

The actual sealed authored-model document already explicitly maps the canonical Output to the visual alias `输出`. Its real source dictionary key is `n_192b289eb9894cdf852dee0442427de7`; this repair does not classify that string as machine-generated or change it.

For a graph Output with an output path and an explicit own entry in `displayAliases`, the scene now displays the alias as the main label and `model output` as the small subtitle. Without an alias, it continues to display the real compact return path. Opaque evidence keeps its existing priority. Whole-value, nested, scalar and UUID-looking paths remain source facts.

Only `studio/src/core/scene.ts` changed in the product for this repair. Python/model generation, return keys, imported architecture, source bytes, digests, renderer, document schemas and authoring UI were not edited by this task. The live before/after hashes of the sealed managed source/document are recorded separately. Concurrent work by the root and other agents is outside this bounded receipt.

`contract.json` and `studio/tests/output-caption-independent.test.ts` contain handwritten positive/negative examples. The test reads an exact frozen copy of the actual generated architecture/document and checks its SHA256. Expected aliases, return paths and captions are not derived from the repaired output. Long, different labels on two outputs test distinct titles and complete nested output facts; they do not claim browser typography acceptance.

Before the implementation, the six new tests passed 3 and failed 3, reproducing the aliased output subtitle problem. After the implementation, the same exact test bytes passed all 6, and the 3 existing nested output-path/validation/reconciliation tests also passed: 9/9 total. Logs, commands, before/after source copies and hashes are preserved in this directory. No broader test, build or browser run was performed by this subtask.

Scene projection/export leave the input document and canonical architecture unchanged; generated SVG visible text uses the concise caption while its title and machine-readable `sourceFacts` retain the full actual path. Existing alias undo/redo restores the real unaliased caption and preserves source facts.

This is bounded static presentation and source-metadata evidence. It establishes no human participation, runtime tensor results, final publication-size readability or M4 completion. The root owns the current unified checks/build and native browser verification.

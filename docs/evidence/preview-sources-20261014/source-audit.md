# Preset source availability audit

This audit reads the formal Studio files and runs the two static analyzers. It
does not import, instantiate or execute any model. Run it from the project root:

```bash
PYTHONPATH=src python3 -B studio/scripts/check-preview-sources.py \
  --baseline docs/evidence/preview-sources-20261014/source-availability-before.json
```

`source-availability.json` records the full case results, asset hashes, entry
locations, budgets, parser diagnostics and Notebook checks. All 230 catalog IDs
match their source descriptors. The 223 descriptors with model source reference
306 Python assets, deduplicated into 142 actual files. Every asset matches its
declared SHA256 and retained original, parses as Python, and has an entry that
resolves to a real class, function or recorded module scope. All source corpora
fit the 80-file / 2 MB input budget.

The Notebook ledger accounts for 112 original files, 28 distinct Notebook
contents and 29 canonical Python assets. The extra asset preserves a separate
logical import path for identical code. All 27,674 recorded line mappings match
their Notebook cells, and the deterministic conversion tool's `--check` passes.
Original Notebook files remain as provenance; runtime source entries use Python.

Among 112 current cases with source, 96 pass the formal authoring projection.
The prior audit passed 7; 89 previously failing cases now pass and no prior pass
regressed. The recursive source adapter accepts 103 of these 112 entries. These
counts describe static projection availability and do not certify runtime model
behavior or shapes. Parser diagnostics and opaque regions remain visible in the
machine-readable report.

The remaining 16 authoring entries have valid source and explicit parser limits:

| Reason | Current cases |
| --- | --- |
| Specialized methods without a supported model `forward` | convgan, dcgan, dcwgan |
| Function or module scope instead of a model class | autoregressive mask, channel shuffle, corn decoder, gru cell, manual fused bn, milstm projection |
| Entry inheritance is outside the formal parser's static proof | lstmcell, compact bilinear pooling, flow sequential, layernorm lstm cell, sparse gcn, spectral norm linear, wavenet block |

Three current cases and four historical cases intentionally have no model-source
descriptor: the routing laboratory and residual teaching SVGs. Their SVGs do not
contain verified model-node source positions. Source files are never assigned to
those objects by guessing from labels. `pytorch-original` has its Transformer
source corpus, while its original SVG geometry remains without invented node
bindings.

Unprovided relative imports are recorded for review. They include external
library boundaries and may refer to package symbols rather than missing modules;
the audit does not download dependencies or treat these observations as missing
catalog assets.

The HTTP check is separately reproducible with:

```bash
python3 -B studio/scripts/check-preview-source-http.py
```

It requests the source assets, evidence, licenses, Notebook Python, metadata,
integration files and the built Studio entry over the local HTTP service. Each
response must equal the corresponding built file byte for byte, which rejects
an HTML fallback returned for a missing source URL. Its final result is recorded
in `http-source-assets.json`: 507 of 507 resources match exactly, including
`index-CHFG_21J.js` and `index-edVmbGnq.css`. The source metadata, integration
manifest and every checked public/dist asset also agree.

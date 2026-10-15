`convert-preview-notebooks.py` migrates Notebook code to `public/preview/sources/notebooks/`, then removes the `.ipynb` originals. It never imports or executes model code. Run from the formal project root:

```bash
python3 -B studio/scripts/convert-preview-notebooks.py
python3 -B studio/scripts/convert-preview-notebooks.py --check
python3 -B -m unittest tests.test_preview_notebook_conversion
```

The tool scans all Notebook files below `snapshots/`, including checkpoint copies and case variants of `.ipynb`, extracts code cells and validates the Python AST. When the adjacent `.py` contains equivalent code, it preserves its exact bytes and source-evidence line positions. Notebook magics are static comments; unsupported non-Python cells remain comments with diagnostics. Training examples and side effects are preserved as source text and never run by this tool. Notebook outputs, cell execution counters and non-code cells are not executable source and are not copied into Python assets.

Shared Python paths use the logical path after the last `sources/` directory, normalized to legal Python identifiers. Identical outputs share one asset; different outputs with the same logical path receive a content hash suffix. The deterministic `data/notebook-conversions.json` ledger records every original Notebook and Python source hash, target Python asset, conversion strategy, and shared cell-to-Python line mapping. Catalog consumers should use `canonical_python` as the public asset URL and keep the evidence's original path separately.

Removal is the default; the old `--remove-notebooks` argument remains compatible. All inputs must convert successfully before any originals are removed. Python assets and the conversion ledger are published first, and original content hashes are rechecked before deletion. Repeating the command preserves removed-file provenance and source URLs, while also converting newly added or refreshed Notebook files. `--check` verifies Python hashes and AST validity and rejects any remaining or newly introduced Notebook files without writing.

Notebook provenance paths must point below `snapshots/` and have an `.ipynb` suffix. Files and parent directories containing symlinks are rejected. Conversion also refreshes the ledger's hash and byte count when that resource already appears in `integration-manifest.json`; unrelated integration receipts remain unchanged.

`vendor-summary-preview.py` uses the same migration when refreshing upstream materials, so refreshing cannot publish Notebook originals. After source organization it refreshes the resources listed in an existing integration manifest. Its `files` list describes retained copied resources; `convertedSources` records each removed upstream Notebook's original path, hash and byte count, plus its replacement Python asset and conversion ID. These historical paths are provenance strings, not requests to load missing files. Source origin and cell/line maps remain in the conversion ledger.

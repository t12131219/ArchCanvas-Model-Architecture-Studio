`convert-preview-notebooks.py` publishes Notebook code to `public/preview/sources/notebooks/` without importing or executing model code. Run from the formal project root:

```bash
python3 -B studio/scripts/convert-preview-notebooks.py
python3 -B studio/scripts/convert-preview-notebooks.py --check
python3 -B -m unittest tests.test_preview_notebook_conversion
```

The tool scans every `snapshots/**/*.ipynb`, extracts code cells and validates the Python AST. When the adjacent `.py` contains equivalent code, it preserves its exact bytes and source-evidence line positions. Notebook magics are static comments; unsupported non-Python cells remain comments with diagnostics. Training examples and side effects are preserved as source text and never run by this tool.

Shared Python paths use the logical path after the last `sources/` directory, normalized to legal Python identifiers. Identical outputs share one asset; different outputs with the same logical path receive a content hash suffix. The deterministic `data/notebook-conversions.json` ledger records every original Notebook and Python source hash, target Python asset, conversion strategy, and shared cell-to-Python line mapping. Catalog consumers should use `canonical_python` as the public asset URL and keep the evidence's original path separately.

Notebook originals remain available for historical evidence by default. The optional `--remove-notebooks` flag removes them only after publishing the Python assets and ledger; `--check` also verifies that completed removal state. Repeating the command after removal preserves the existing ledger.

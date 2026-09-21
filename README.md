# ArchCanvas Model Architecture Studio

The current implementation covers the first four fixture-backed stages: strict source and
architecture protocols, a safe `nhead` source round-trip, conservative PyTorch static recovery,
isolated runtime evidence, and a separate deterministic publication SVG pipeline.

The static and publication paths remain intentionally bounded to declared PyTorch patterns and
repository fixtures. Engine/RPC, persisted visual state, desktop canvas, general parameter UI,
structural edits, MCP transport, and release hardening remain future stages.

The current executable path is deliberately fixture-scoped while the general PyTorch adapter
is not yet complete. It never writes by default:

```bash
conda run -n TFB_py311 archcanvas-fixture-transaction \
  --fixture-dir fixtures/transformer_set_parameter_v1 \
  --source-file /absolute/path/to/model.py
```

Add `--commit` only after inspecting the JSON candidate diff and validation result. The command
requires source bytes matching the fixture's analyzed revision and rejects stale input.

## Development

```bash
conda run -n TFB_py311 python -m pip install -e '.[dev]'
conda run -n TFB_py311 python -m pytest -q
conda run -n TFB_py311 python tools/generate_static_goldens.py
conda run -n TFB_py311 python tools/generate_publication_goldens.py
```

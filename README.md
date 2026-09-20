# ArchCanvas Model Architecture Studio

The initial implementation freezes the exact architecture protocols and the first safe
source round-trip: a PyTorch `nhead` literal can be changed through a validated
`set_parameter` patch without rewriting unrelated source formatting.

The current scope intentionally excludes the desktop canvas, publication compiler, and
structural graph edits. Those layers consume the protocols established here.

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
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m pytest
```

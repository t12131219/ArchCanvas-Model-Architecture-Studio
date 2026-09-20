# Stage 2 Static Recovery Checkpoint

## Scope Completed In This Checkpoint

- Extended the conservative PyTorch AST discovery records with constructor-parameter provenance.
  Supported origins are literal, constructor argument, module-level JSON literal constant, and
  `config`/`self.config` attribute. Arbitrary expressions are recorded as computed and emit an
  unresolved fact; no user expression is evaluated.
- Added canonical `num_heads <- nhead` handling for `TransformerEncoderLayer`, positional-name
  maps for the currently supported `nn` modules, and `ModuleList(range(...))` repeat discovery.
- Added parameter-expression anchors to Source Identity and mapped the discoveries to strict
  `ArchitectureParameter` records with evidence.
- Added reconciliation records for initial discoveries, exact source-symbol matches after a
  refresh, and ambiguous prior matches. Ambiguity becomes a blocking unresolved IR fact.
- Added Transformer and ResNet static fixture sources, deterministic golden generation, and
  byte-exact golden tests.
- Added a bounded, read-only `PyTorchProjectScanner` and `scan_pytorch_project.py`. It finds
  candidate `nn.Module` entrypoints without importing user code, excludes common generated or
  environment directories, records unparseable/oversized/out-of-root files, and resolves direct
  `torch.nn` symbol imports.
- Read-only scan of `../Article/PatchTST/PatchTST_supervised` found 64 Python files and no parse
  failures. It discovered the public `models/PatchTST.py:Model` entrypoint plus its backbone and
  layer candidates. The result is discovery evidence only: cross-file custom calls are not yet
  asserted as Exact IR topology.

## Validation

```bash
conda run -n TFB_py311 python -m pytest
conda run -n TFB_py311 python -m compileall -q src tools tests
conda run -n TFB_py311 python tools/generate_static_goldens.py
conda run -n TFB_py311 python tools/export_schemas.py
git diff --check
```

## Known Limitations

- This is a project scanner, not yet a local/cross-file symbol resolver or complete-project IR
  compiler. `Sequential` is discovered as a container but does not yet materialize every inner
  member.
- Functional operations other than residual add, `torch.cat`, and `torch.stack` are not modeled.
- Reconciliation is analysis evidence only. No Stage 2 path performs a source transaction.
- Wheel construction could not be verified locally: `TFB_py311` lacks importable `hatchling`, and
  build isolation cannot download it because network access is restricted. The package list was
  updated to include `archcanvas_pytorch`; run the wheel check in CI or an environment with the
  declared build dependency installed.

## Next Input Contract

Extend only the Stage 2 static adapter. Preserve strict v1 Source Identity and Architecture IR,
the committed goldens, and fail-closed unresolved behavior. The next work should add
local/cross-file import and symbol resolution for a selected entrypoint before claiming Stage 2
complete.

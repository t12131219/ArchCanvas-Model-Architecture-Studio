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
- Added direct local `nn.Module` symbol resolution for selected entrypoints. The PatchTST public
  model now resolves `PatchTST_backbone` to `layers/PatchTST_backbone.py:PatchTST_backbone` and
  `series_decomp` to `layers/PatchTST_layers.py:series_decomp`; no code was imported or executed.
- Constructor scanning now stops at `if`, loop, `try`, `with`, and `match` statements. It emits
  `DYNAMIC_CONSTRUCTOR_CONTROL_FLOW` and does not retain assignments in those bodies as confirmed
  modules. Direct-call and literal `OrderedDict` `nn.Sequential` instances, plus literal
  `nn.ModuleList` instances, materialize every member and their ordered internal edges;
  dynamic/non-literal members stay unresolved. `ModuleList(range(...))` remains a repeat record.
  A selected, branch-free direct local constructor call now creates one anchored
  local-module node: its identity includes both the entrypoint call anchor and the imported class
  declaration anchor, while the source snapshot includes the imported class file revision. Unused
  local imports and conditional local calls do not produce target-class topology anchors.
- Added bounded transitive declaration evidence. From a confirmed root local-call node, the adapter
  can record direct local calls in the target class with their call-site anchor, target-class anchor,
  entrypoint and file revision. These records are metadata only, not recursively flattened IR
  topology; traversal has a configurable depth limit, explicit expanded/depth-limit/duplicate/cycle
  status, and never starts from a conditional root call.

## Validation

```bash
conda run -n TFB_py311 python -m pytest
conda run -n TFB_py311 python -m compileall -q src tools tests
conda run -n TFB_py311 python tools/generate_static_goldens.py
conda run -n TFB_py311 python tools/export_schemas.py
git diff --check
```

The latest local `TFB_py311` run passed 56 tests after the constructor, Sequential, ModuleList,
selected-entrypoint, direct-local-call, and dynamic-container regression cases were added.

## Known Limitations

- This is a project scanner with direct local-symbol resolution, not a complete local/cross-file
  resolver or complete-project IR compiler. It represents only branch-free direct local calls as
  one node; it does not recursively flatten a target class implementation. Dynamically built
  `Sequential` or `ModuleList` forms remain unresolved; literal `OrderedDict` Sequential and
  literal ModuleList members are supported.
- Functional operations other than residual add, `torch.cat`, and `torch.stack` are not modeled.
- Reconciliation is analysis evidence only. No Stage 2 path performs a source transaction.
- Wheel construction could not be verified locally: `TFB_py311` lacks importable `hatchling`, and
  build isolation cannot download it because network access is restricted. The package list was
  updated to include `archcanvas_pytorch`; run the wheel check in CI or an environment with the
  declared build dependency installed.

## Next Input Contract

Extend only the Stage 2 static adapter. Preserve strict v1 Source Identity and Architecture IR,
the committed goldens, and fail-closed unresolved behavior. The next work should add a separately
specified transitive/local-container subset with fixture proof, rather than flattening dynamic or
conditional source paths into confirmed topology.

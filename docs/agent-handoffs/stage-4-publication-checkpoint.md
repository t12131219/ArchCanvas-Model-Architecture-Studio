# Stage 4 Publication Compiler Checkpoint

## Scope

Stage 4 introduces a read-only publication pipeline:

```text
Exact Architecture IR -> Publication IR -> VisualScene -> deterministic SVG
```

Neither the compiler, layout engine, renderer nor preflight code modifies user source bytes,
Source Identity, Exact IR, runtime evidence or a patch candidate. Publication labels and visual
groups are presentation reductions, not additional source-semantic facts and not code-editing
capabilities.

## Delivered Components

- Strict `PublicationIR` and `VisualScene` protocols, exported as committed JSON schemas.
- Cross-document validation requiring every Exact node and edge to be either represented by a
  publication member mapping or explicitly recorded as omitted.
- Conservative Transformer repeat reduction to a collapsed `Transformer encoder` group, preserving
  a symbolic depth annotation when the static analysis cannot prove an integer count.
- Conservative residual-stage reduction for the repository ResNet fixture. Internal data edges are
  explicitly omitted; the residual edge remains represented as a publication self-loop.
- Default omission of implementation-only `reshape`, `transpose`, `permute`, `flatten`, `squeeze`
  and `unsqueeze` function/operator nodes.
- Deterministic stage layout, orthogonal edge routing, SVG-first renderer, and non-mutating SVG
  preflight.
- Visual-only repeat expansion: the layout accepts an explicit repeat-group ID set and produces a
  taller `VisualScene` preview with deterministic layer markers. It rejects unknown or non-repeat
  IDs, and preflight rejects externally constructed expanded non-repeat scene nodes.
- Transformer and CNN publication/scene/SVG golden fixtures with an explicit `--write` generator.
- ADR 0001 records the separation of Exact IR, Publication IR and Scene expansion state; focused
  local rules constrain the compiler and renderer ownership boundaries.

## Verified Fixtures

- `transformer_static_v1`: Input -> token embedding -> collapsed Transformer encoder -> layer
  normalization -> prediction head -> Output. The repeat annotation is `Repeated depth times`,
  because `depth` is source-symbolic rather than a statically confirmed literal.
- `resnet_static_v1`: Input -> collapsed residual stage -> Output, with a residual self-loop and
  `Residual connection` annotation.
- `publication_transformer_v1`: both the collapsed scene and the expanded repeat-preview scene
  have byte-stable JSON/SVG goldens. Expansion retains one publication node and its original Exact
  member mapping; the preview layers are visual grammar, not recovered source modules.
- A constructed `torch.reshape` Exact node is omitted by default and remains visible in the
  Publication IR omission ledger, rather than being silently discarded.

## Validation

```bash
conda run -n TFB_py311 python -m pip install -e '.[dev]'
conda run -n TFB_py311 python -m pytest -q
conda run -n TFB_py311 python -m ruff check src tests tools
conda run -n TFB_py311 python -m compileall -q src tools tests
conda run -n TFB_py311 python tools/export_schemas.py
conda run -n TFB_py311 python tools/generate_static_goldens.py
conda run -n TFB_py311 python tools/generate_publication_goldens.py
git diff --check
```

The editable package install succeeded in `TFB_py311`; the final run passed `82` tests and the full
`src tests tools` Ruff gate. CI runs the same test, compile, schema and static/publication golden
checks. The generators run in verification mode after their reviewed golden documents were written,
so a change in publication output, scene placement, edge routing or SVG serialization is a
regression.

## Boundary And Remaining Work

No Article input was read, executed or modified for this stage. Article models remain a later,
separately approved integration target with their own provenance and capability report.

The supported reductions are intentionally fixture-backed patterns, not a claim that arbitrary
PyTorch programs have a complete paper diagram. Project persistence, engine/RPC access and the
desktop canvas are Stage 5 and Stage 6 responsibilities.

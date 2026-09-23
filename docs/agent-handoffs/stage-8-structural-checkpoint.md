# Stage 8 Structural Checkpoint

Status: restricted-subset implementation evidence, not a Stage 8 exit validation.

## Implemented

- Patch Protocol v2 accepts `insert_layer_norm` and its source-proven inverse,
  `remove_layer_norm`, alongside the v1-compatible `set_parameter` payload.
- `insert_layer_norm` is bounded to a same-file, existing-`nn` import, direct local assignment
  chain with exact constructor and forward anchors. It inserts one `nn.LayerNorm` and requires two
  textual diff hunks plus an exact declared node/edge graph delta.
- `remove_layer_norm` is only the inverse of that linear splice. It requires both adjacent
  source-proven edges, exact anchors/fingerprints, `self.<attribute> = nn.LayerNorm(...)`, and an
  identity local forward call. It removes exactly those two statements.
- Engine routes both operations through candidate-first planning, isolated registered runtime
  profiles, structural coverage/shape validation, one-time confirmation, atomic commit, and
  post-commit re-analysis/rollback.
- The Exact Architecture Inspector consumes Engine-advertised structural capabilities. It can draft
  only a source-proven direct-edge insert or the proven inverse removal; it remains unavailable to
  projects without both an explicit analyzer and runtime profile.
- The default desktop sidecar deliberately registers neither. It therefore keeps structural
  commands hidden until a project-specific approved registration mechanism is provided; benchmark
  discovery and generic static analysis never enable source edits implicitly.

## Corpus Evidence

- `fixtures/structural_embedding_encoder_v1` is a registered static golden corpus for the direct
  `Embedding -> Encoder` acceptance path. Its Engine integration test covers plan, runtime/shape
  validation, confirmation and commit.
- `fixtures/transformer_static_v1` covers the original Transformer `layers -> norm` splice and
  the Engine-level inverse round trip restoring the original source bytes.
- Negative coverage rejects stale anchors, an inverse non-identity local call, missing runtime
  profiles, failed runtime validation, coverage gaps and graph-delta violations before source write.

## Verified

```text
PYTHONPATH=src:. conda run -n TFB_py311 pytest -q
PYTHONPATH=src:. conda run -n TFB_py311 ruff check src tests tools
PYTHONPATH=src:. conda run -n TFB_py311 python -m compileall -q src tools tests
PYTHONPATH=src:. conda run -n TFB_py311 python tools/export_schemas.py
PYTHONPATH=src:. conda run -n TFB_py311 python tools/generate_static_goldens.py
PYTHONPATH=src:. conda run -n TFB_py311 python tools/generate_publication_goldens.py
cd desktop && npm run build && npm run lint
cd desktop && npm run test:tokens && npm run test:visual
ARCHCANVAS_ENGINE_PYTHON=<approved-python> ARCHCANVAS_WEBKIT_DRIVER=/usr/bin/WebKitWebDriver \
  npm --prefix desktop run test:e2e:tauri
git diff --check
```

## Not an Exit Gate

Generic module removal, arbitrary rewire and residual edits remain unsupported by design. Stage 7
also cannot formally pass until its recorded Stage 6 external acceptance blockers are resolved.
Therefore this checkpoint does not authorize Stage 9.

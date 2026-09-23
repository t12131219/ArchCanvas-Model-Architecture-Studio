# Structural Embedding-to-Encoder Corpus

- Owner: ArchCanvas structural transaction maintainers.
- Provenance: a minimal local PyTorch model created for the Stage 8 restricted splice contract; it
  is not a benchmark model and makes no claim about a paper architecture.
- Positive case: insert exactly one registered `nn.LayerNorm` on the source-proven direct
  `embedding -> encoder` edge, then confirm its expected source, static-IR and graph-delta facts.
- Negative case: a non-identity local call such as `x = self.insert_norm(tokens)` is rejected by
  the restricted inverse transform; missing runtime coverage/profile is rejected by Engine tests.
- Regeneration: `PYTHONPATH=src:. conda run -n TFB_py311 python tools/generate_static_goldens.py`.

This corpus exists solely to exercise the direct local-call subset. It does not expand support to
control-flow rewrites, arbitrary imports, cross-file modules, generic removal, rewiring or residual edits.

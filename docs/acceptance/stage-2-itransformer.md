# Stage 2 Checkpoint: iTransformer

Status: iTransformer source recovery implemented. See `stage-2.md` for the completed stage gate.

The fixture preserves the upstream model, inverted embedding, and encoder implementation byte for
byte with archive and member SHA-256 provenance. Analysis parses these files without importing the
project and rejects modified fixture members.

The `B-itransformer` gate proves:

- normalization and denormalization follow the resolved `use_norm` predicate;
- `DataEmbedding_inverted` performs an internal non-learnable `[B,L,N] -> [B,N,L]` permutation;
- the embedding projects temporal axis `L` to model depth `D`;
- optional covariates become extra tokens and are trimmed from the output;
- the architecture is encoder-only and records its layer repeat;
- the forecast head maps `D -> pred_len`, then permutes to `[B,S,N]`.

Mutation tests reject an external learnable permutation and a missing covariate trim. The same
fixture also passes semantic closure through `--no-pattern-packs` generic recovery.

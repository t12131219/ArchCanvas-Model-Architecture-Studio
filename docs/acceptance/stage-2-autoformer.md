# Stage 2 Checkpoint: Autoformer

Status: Autoformer source recovery implemented. See `stage-2.md` for the completed stage gate.

The fixture preserves four upstream THUML Autoformer source files byte-for-byte with archive and member SHA-256 provenance. The adapter parses those files without importing `torch` and refuses analysis when any member digest or required AST pattern changes.

The `B-autoformer` gate proves:

- both embeddings use `DataEmbedding_wo_pos` without an active position term;
- encoder, decoder self, and decoder cross AutoCorrelation paths expose Q/K/V projection roles;
- the source contains RFFT, conjugate spectral product, IRFFT, top-k selection, and inference time-delay aggregation;
- encoder layers contain two progressive decompositions;
- decoder layers contain three decompositions and sum all three trend residuals;
- decoder trend is accumulated separately, then added to projected seasonal output;
- encoder memory feeds decoder cross K and V;
- this source revision does not consume the accepted mask arguments inside `AutoCorrelation.forward`.

The source-correction report records position embedding, generic Add & Norm, mask behavior, and the executable seasonal/trend dual path. Runtime evidence is explicitly `skipped` because this stage is static-first.

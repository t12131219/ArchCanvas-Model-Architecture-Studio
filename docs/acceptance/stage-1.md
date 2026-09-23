# Stage 1 Acceptance: Evidence and Exact IR

Status: implemented for the checked-in Transformer fixture.

The Stage 1 profile is source-first and does not import `torch` or execute the fixture. Analysis freezes the source and config digests, resolves constructor parameter provenance, emits the six ledgers, and validates every referenced evidence identifier against the frozen snapshot.

The Transformer L3 gate requires:

- parallel encoder and decoder Q/K/V projections;
- explicit head split, transposed K, scaled QK score, softmax, weights x V, and head concat;
- target mask connected to decoder scores through a condition edge;
- cross-attention Q from decoder hidden state and K/V from encoder memory;
- explicit residual merge events followed by LayerNorm;
- symbolic head shapes and `[B,T,V]` logits returned directly by `forward`.

The tests include destructive mutations of required memory and mask paths. A gate is accepted only when the intact fixture passes and the mutated fixture fails.

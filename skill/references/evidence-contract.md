# Evidence Contract

Use this reference when analyzing provenance or resolving contradictory sources.

Truth priority is: selected source revision and analysis context; active `forward`/`call` dependencies; replayable runtime evidence; constructor/config/checkpoint metadata; then papers, READMEs, comments, names, and reference images.

Every executable node, key tensor, and edge needs evidence or an unresolved record. Source evidence includes a relative path, symbol, line span, file digest, claim, confidence, and execution predicate.

Confidence values are `exact`, `runtime-confirmed`, `equivalent`, `inferred`, `unresolved`, `reference-only`, and `contradicted`. Reference-only facts do not enter the executable graph.

Containment is not execution. Adjacency is not an edge. A flow edge is producer port to tensor to consumer port. Add, concat, multiply, reduce, gate, select, stack, and sum must be explicit merge events. Q, K, and V are parallel roles unless selected source proves otherwise.


# Stage 2 Checkpoint: PatchTST

Status: PatchTST source recovery implemented. See `stage-2.md` for the completed stage gate.

The fixture preserves four upstream files byte for byte and records archive/member hashes. The
supplied archive lacks a repository-root license file, so provenance is explicitly `NOASSERTION`;
licenses from bundled comparison projects are not misattributed to PatchTST.

The `B-patchtst` gate proves:

- optional RevIN normalization and denormalization follow config;
- end padding is conditional and patch count reflects the selected stride and patch length;
- unfold yields `[B,C,Np,P]`, followed by `P -> D` projection;
- batch and channel fold into `[B*C,Np,D]` before the shared encoder;
- positional encoding and optional residual attention are present;
- the selected normalization is BatchNorm;
- the true head is `Flatten(D*Np) -> Linear(pred_len)`;
- decomposition executes independent residual/trend backbones and adds their forecasts.

Mutation tests reject a simplified `D -> pred_len` head and a disconnected trend merge. Both the
dual-backbone config and a single-backbone config pass, as does generic recovery with packs disabled.

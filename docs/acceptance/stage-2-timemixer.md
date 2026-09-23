# Stage 2 Checkpoint: TimeMixer

Status: TimeMixer source recovery implemented.

The fixture preserves the model, embedding, normalization, and Apache-2.0 license from revision
`e24610583b36fdd8c76cc17a8df4e65759a5f460`, with archive and member SHA-256 provenance.

The `B-timemixer` gate proves:

- source-driven downsampling creates the configured multiscale list;
- every scale has Normalize, optional channel-independent reshape, and `DataEmbedding_wo_pos`;
- moving-average or DFT decomposition follows config;
- seasonal components mix high resolution to low resolution;
- trend components mix low resolution to high resolution;
- every scale has its own temporal predictor and output projection;
- per-scale forecasts are stacked, summed, and denormalized;
- no fictional short/mid/long Conv mixer branches enter the executable graph.

Mutation tests reject a reversed seasonal direction and a missing scale forecast. Moving-average and
DFT configs both pass, as does generic recovery with packs disabled.

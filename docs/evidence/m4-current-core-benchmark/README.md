# Current DenseStress300 core benchmark

This directory is a durable input and receipt for the current formal project build.

The architecture JSON was produced by the independent copy created by
`scripts/check_m4_stress.py` and then copied here. It contains the source bytes and
digest for `fixtures/stress_300/model.py`; no model import or forward execution was
performed. The benchmark uses the current `studio/src/core` files and the existing
`scripts/benchmark_move_preview.mjs` script.

Run from the formal project root:

```bash
./.venv/bin/python scripts/check_m4_stress.py --project .
node scripts/benchmark_move_preview.mjs \
  --architecture docs/evidence/m4-current-core-benchmark/architecture.json \
  --samples 30 --warmup 5 \
  --output docs/evidence/m4-current-core-benchmark/move-preview-final.json
```

The receipt is CPU-only. It checks complete Scene and interactive SVG byte equality
for every trial, input/history immutability, guarded commit, and undo/redo. It does not
claim browser latency, paint, presented FPS, Event Timing, INP, or publication quality.

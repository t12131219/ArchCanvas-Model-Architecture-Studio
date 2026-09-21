# Stage 3 Runtime Evidence Checkpoint

## Scope

Stage 3 adds an explicitly opt-in, short-lived PyTorch runtime worker. The engine process never
imports the requested model. Runtime evidence supplements the Stage 2 Exact IR; it cannot create,
replace or remove source anchors or identities.

## Delivered Components

- Strict `TraceRequest` and `RuntimeTraceResult` schemas with request/trace IDs, source revision,
  entrypoint file revision, configured Python, environment name, dependency lockfile, constructor
  arguments, tensor input specifications, provider, timeout, memory limit and network policy.
- `RuntimeTraceProvider` interface with `torch.fx` and `torch.export` implementations.
- `IsolatedTraceWorker`, which starts the configured interpreter in the selected project root,
  validates the entrypoint revision, applies CPU/memory limits where supported, captures model
  stdout/stderr, returns structured failure taxonomy and exits after every request.
- `RuntimeEvidenceResolver`, which appends runtime edge evidence and output `TensorSpec` only when
  the trace source revision matches the Exact IR. It leaves `source_anchor_ids` unchanged.
- `RuntimeShapeValidator`, which exposes uncovered nodes and makes trace failure or shape mismatch
  blocking for a requested structural change.
- `TraceRequestFactory`, which creates a request only from a current `SourceIdentityDocument` and
  rejects stale, root-external or unregistered entrypoint files before a worker starts.
- `run_pytorch_trace.py`, an explicit command-line execution entrypoint. It returns
  `EXECUTION_NOT_ACKNOWLEDGED` unless the caller supplies `--execute`.

## Fixture Evidence

The repository-owned `resnet_static_v1` fixture is the only runtime target used in this checkpoint.
It was executed by a worker running the `TFB_py311` interpreter:

- FX succeeded and observed `conv1`, `conv2`, residual add and `relu`.
- Export succeeded and returned graph observations.
- A dynamic conditional model returns `TRACE_UNSUPPORTED` with a coverage gap rather than a
  partial confirmed topology.
- A stale entrypoint revision returns `STALE_ENTRYPOINT_REVISION`.
- A deliberately incompatible static output `TensorSpec` yields blocking
  `RUNTIME_SHAPE_MISMATCH` for a structural operation.
- The fixture source bytes, parent working directory and parent module imports remain unchanged.
- The explicit CLI completed the same FX trace with a current source identity document. Worker
  environments limit OpenMP/BLAS thread pools to one thread so parallel trace requests do not
  exhaust host thread quotas.

## Security and Article Boundary

Runtime analysis executes model code and is therefore not part of the Stage 2 static scanner.
The worker applies a best-effort in-process network denial policy and OS resource limits where
available; it is not a security sandbox for hostile code. It must only be launched after an
explicit execution approval through a future engine/UI workflow.

No Article source was imported, executed, installed, modified, or added to `sys.path` by this
checkpoint. Article runtime tracing requires a future approved root, explicit constructor/input
contract and a separately recorded environment/provenance report.

## Validation

```bash
conda run -n TFB_py311 python -m pytest -q
conda run -n TFB_py311 python -m ruff check src/archcanvas_pytorch/runtime src/archcanvas_core/models/runtime.py tests/runtime
conda run -n TFB_py311 python -m compileall -q src tools tests
conda run -n TFB_py311 python tools/export_schemas.py
git diff --check
```

The checkpoint's final validation result is recorded with the worktree. Runtime schemas are
committed alongside the existing protocol schemas and covered by schema-drift tests.

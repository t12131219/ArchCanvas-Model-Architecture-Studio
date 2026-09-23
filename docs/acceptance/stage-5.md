# Stage 5 Acceptance: Runtime Evidence

Status: complete for opt-in PyTorch module-boundary tracing.

Stage 5 adds `archcanvas trace` as a separate command. Static `analyze` remains non-executing and
does not import Torch or the target project. Trace requires an existing ArchitectureIR,
SourceSnapshot, and explicit RuntimeInputSpec. It verifies every frozen source hash before starting
an isolated worker.

## Runtime protocol

The versioned runtime protocols cover generated tensor names, shapes, dtypes and generators;
constructor/forward keyword arguments; random seed; requested device; timeout; CPU limit; and
memory limit. RuntimeTrace records ordered module observations, matched canonical node IDs, output
shape/dtype/device, exact environment fingerprint, isolation policy, blocked boundary attempts,
and the structural replay digest.

The worker runs with Python isolated mode in a temporary working directory. Its environment is
allowlisted, bytecode writes are disabled, CPU/address-space/file-size/file-descriptor limits are
applied, socket and child-process operations are denied, and Python file writes or destructive
operations outside the temporary sandbox are rejected. The receipt states the remaining limitation
clearly: these are process/resource and Python API boundaries, not an OS container or VM security
boundary.

## Publication and failure behavior

Every successful command executes the same seeded spec in two fresh workers. Replay passes only
when observations, output tensor metadata, and blocked boundary attempts have the same digest.
Published artifacts are:

- `runtime-trace.json`
- `runtime-evidence-ledger.json`
- `runtime-evidence-overlay.json`
- `runtime-capability-report.json`
- `runtime-receipt.json`

Static ArchitectureIR and evidence ledgers are never rewritten. The parent hashes all protected
static artifacts and frozen source files before and after execution. Worker failure publishes only
a failure receipt: the isolation gate reports whether static state remained intact, replay is
reported as skipped, and provenance fails rather than being presented as runtime-confirmed.

Studio loads a complete, source-bound runtime bundle when it is stored beside `architecture.json`.
The Evidence Inspector merges runtime-confirmed records through the sidecar overlay without adding
runtime facts to canonical IR. Incomplete or stale runtime bundles are rejected.

## Acceptance evidence

The Transformer fixture input uses seed `20260924` on CPU. With Torch `2.7.1+cu118`, it produces 21
module observations and 21 canonical runtime evidence records; the final output is
`float32[1,3,32000]`. Both independent runs produce the same replay digest. The current host reports
CUDA build `11.8` but `cuda_available=false`, so CUDA execution is not claimed.

Automated tests prove:

- shape/dtype trace, canonical node provenance, and a single JSON CLI receipt;
- two-worker structural replay for the same input spec;
- source and static artifact hashes remain unchanged after success and runtime failure;
- a failed forward publishes no RuntimeTrace and leaves static validation usable;
- inherited non-allowlisted environment values are unavailable;
- attempted network access, child-process creation, and an absolute write outside the sandbox are
  blocked and audited;
- Studio loads valid runtime sidecars and advertises runtime evidence only when present.

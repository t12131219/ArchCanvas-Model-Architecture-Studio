# Acceptance Evidence

Acceptance is layered. A passing unit test does not prove a desktop interaction, a source
transaction, an MCP policy, or a release artifact.

| Evidence class | Location | Introduced by | Required assertion |
| --- | --- | --- | --- |
| Protocol | `tests/schema`, `tests/models` | Stage 1 | schemas, strict models, references, and negative input agree |
| Fixture and golden | `fixtures/`, `tests/transforms`, `tests/graph_delta` | Stages 1-4 | deterministic source/IR/scene output and fail-closed negatives |
| Static compatibility corpus | `fixtures/transformer_static_v1`, `fixtures/resnet_static_v1` | Stage 2 | known source patterns produce supported topology or explicit unresolved facts |
| Runtime | `tests/runtime`, `fixtures/runtime_trace_v1` | Stage 3 | worker isolation, coverage, failure code, and shape evidence |
| Engine integration | `tests/engine` | Stage 5 | typed request/response, persistence, refresh, and stale-state behavior |
| Semantic patch lifecycle | `tests/engine/test_engine_patch.py`, `tests/transactions` | Stage 7 | candidate diff, provenance/risk, validation, atomic commit, stale rejection and post-commit re-analysis |
| Scientific miniature | `tests/publication` | Stage 6 D4 | source-member mapping, evidence/disclosure contract, deterministic SVG and negative provenance cases |
| Desktop E2E | `desktop/tests`, `tests/e2e` | Stages 6-8 | actual interaction, persistence, source hash, and validation display |
| MCP policy | `tests/mcp` | Stage 9 | capability advertisement, root authority, candidate-first commit policy |
| Release | `docs/acceptance/release/`, CI artifacts | Stage 10 | platform matrix, provenance, performance, and regression report |

Every new fixture needs an owner, a source or input provenance note, an expected positive
result, at least one meaningful negative case, and a deterministic regeneration command.
Generated files are committed only when they are reviewed as evidence, not merely because a
test happened to write them.

## Static Recovery Regeneration

Stage 2 static goldens are verified without writing by default:

```bash
conda run -n TFB_py311 python tools/generate_static_goldens.py
```

Use `--write` only after an intentional scanner/adapter change and review the resulting JSON
alongside the source fixture and focused negative tests.

## TFB Model Census

The D5 census analyzes every statically discovered `nn.Module` entrypoint under an approved TFB
root. It never imports, executes, installs dependencies into, or writes to that root. The output
must be stored in an Engine cache or acceptance directory outside the inspected source tree.

```bash
PYTHONPATH=src conda run -n TFB_py311 python tools/generate_pytorch_model_census.py \
  /approved/TFB-master/ts_benchmark \
  --project-id project:tfb-census \
  --output /cache-or-acceptance/tfb-model-census.json \
  --quiet
```

The resulting JSON must account for every discovered entrypoint. `unresolved` and `blocked` are
valid explicit results; omission is not. A `supported` static result is not a claim that a
Publication/SVG scene exists. See `stage-6-tfb-census-observation.json` for the initial local
baseline and the remaining D5 gates.

For D5 machine preflight, request Publication evidence explicitly and place it outside the inspected
TFB root:

```bash
PYTHONPATH=src conda run -n TFB_py311 python tools/generate_pytorch_model_census.py \
  /approved/TFB-master/ts_benchmark \
  --project-id project:tfb-d5-preflight \
  --assess-publication \
  --publication-artifact-root /cache-or-acceptance/tfb-publication-evidence \
  --output /cache-or-acceptance/tfb-model-census.json \
  --quiet
```

`publication_svg_ready` means the source-mapped Publication IR, overview/detail scenes and SVG
preflight passed. It is still below `publication_supported`: each artifact directory carries a
pending manual checklist, and Section 26.8 still requires screenshots, evidence traversal and the
deep-semantic examples before D5 can pass.

During visual styling work, a machine-preflight artifact may carry
`visual_iteration_status: "provisional_visual_iteration"`. This permits repeatable layout and
token iteration without claiming that a reviewer approved the architecture depiction. It must
remain `manual_review: "pending"` until the actual overview/detail, evidence traversal and
reference comparison are performed.

Validate the saved census and its external artifacts separately. This validator checks accounting,
source immutability and machine preflight evidence, but deliberately does not convert a pending
manual checklist into an approval:

```bash
PYTHONPATH=src conda run -n TFB_py311 python tools/validate_d5_census.py \
  /cache-or-acceptance/tfb-model-census.json \
  --publication-artifact-root /cache-or-acceptance/tfb-publication-evidence \
  --output /cache-or-acceptance/d5-validation.json
```

Add `--require-stage6-exit-ready` only in an exit gate: it returns nonzero while any manual
checklist remains pending, even when the machine ledger itself is coherent.

## Benchmark Model Reference Ledger

`Benchmark model reference/BENCHMARK_MODEL_INDEX.md` is a generic regression corpus, not a TFB
product interface. Generate the L0 catalog from a user-approved root and keep the result outside
that root:

```bash
PYTHONPATH=src conda run -n TFB_py311 python tools/generate_benchmark_catalog.py \
  /approved/Benchmark-model-reference \
  --output /cache-or-acceptance/benchmark-catalog.json
```

The unified ledger retains every catalog record. A framework adapter is invoked only for an
explicitly selected, root-relative project scope; all other local-model records remain visible as
adapter-level `unsupported`, while `benchmark_only` remains `no_local_model`.

```bash
PYTHONPATH=src conda run -n TFB_py311 python tools/generate_benchmark_census.py \
  /approved/Benchmark-model-reference \
  --output /cache-or-acceptance/benchmark-census.json \
  --pytorch-project 01:TFB-master/ts_benchmark \
  --pytorch-resolved-config-file 01:docs/acceptance/tfb-resolved-configs-v1.json \
  --pytorch-entrypoint-registry-file 01:docs/acceptance/tfb-entrypoints-v1.json
```

The project selector is an approval boundary, not a model-name convention. It must identify a
directory below the approved benchmark root. The report stores only that relative path and the
adapter's relative census; it does not execute, import, install into, or write to benchmark source.
An entrypoint registry is supplementary: every listed entry must still be discovered by the static
adapter, and missing entries remain an explicit unresolved result. The current TFB registry is a
three-entry deep-semantic seed, not a reduction of the 460-entry census.

The same generic path can be exercised against the first heterogeneous Python/PyTorch slices:

```bash
PYTHONPATH=src conda run -n TFB_py311 python tools/generate_benchmark_census.py \
  /approved/Benchmark-model-reference \
  --output /cache-or-acceptance/python-pytorch-slices.json \
  --pytorch-project 06:06-semantic-segmentation-ADE20K/mit_semseg/models \
  --pytorch-project 12:12-recommendation-RecBole/recbole/model \
  --pytorch-project 13:13-GNN-OGB/examples \
  --pytorch-entrypoint-registry-file 06:docs/acceptance/ade20k-entrypoints-v1.json \
  --pytorch-entrypoint-registry-file 12:docs/acceptance/recbole-entrypoints-v1.json \
  --pytorch-entrypoint-registry-file 13:docs/acceptance/ogb-entrypoints-v1.json
```

MMPretrain and SpeechBrain can be added with the same explicit scope and registry contract:

```bash
--pytorch-project 04:04-image-classification-mmpretrain/mmpretrain/models \
--pytorch-project 11:11-speech-audio-speechbrain/speechbrain/lobes/models \
--pytorch-entrypoint-registry-file 04:docs/acceptance/mmpretrain-entrypoints-v1.json \
--pytorch-entrypoint-registry-file 11:docs/acceptance/speechbrain-entrypoints-v1.json
```

## Stage 7 Patch Boundary

Stage 7 source editing is Engine-owned. Desktop clients submit a typed `PatchSet` through
`plan_patch`, `validate_patch` and `commit_patch`; they never write approved project files. Only
an explicitly registered project analyzer may produce a candidate. Projects without one are
rejected with `PATCH_ANALYZER_UNAVAILABLE`, which keeps benchmark reference code useful for
compatibility evidence without treating any single benchmark or fixture analyzer as universal.
The desktop inspector exposes only source-backed literal parameter controls and must show the
candidate diff and validation/risk metadata before commit. Validation issues an Engine-owned,
one-time confirmation capability; a commit without the matching live candidate and capability is
rejected, including after an Engine restart. A cancelled candidate has no source side effect, and a
successful commit is followed by Engine re-analysis. If post-commit analysis fails, original bytes
are atomically restored only when the candidate revision is still current; a concurrent change is
reported as a rollback conflict and is never overwritten.
Where a project requires runtime evidence, the Engine administrator must explicitly register a
`PatchRuntimeProfile`; it specifies tensor inputs, constructor arguments, trace provider, timeout,
memory limit and network policy. The candidate is written only into a temporary copy of the approved
root and executed by the existing isolated worker. RPC clients cannot provide an arbitrary command,
script, environment or test payload. A failed runtime result rejects validation without confirmation
or an approved-source write. Symlinked candidate trees are rejected before worker execution so an
import cannot escape the approved temporary copy.
The registry currently covers `num_heads`, `dropout`, `activation`, and hidden-size aliases
(`hidden_size`, `hidden_dim`, `d_model`, `dim_feedforward`); names such as `batch_first` remain
unregistered and are rejected even when their source value is literal. Registry value contracts
also reject non-positive dimensions, out-of-range dropout values, unsupported activation values and
head counts that do not divide a visible model dimension. Hidden-size transforms are registered but
not currently commit-capable without a registered `PatchRuntimeProfile`: the Engine rejects them
before candidate creation and the Desktop does not offer a control for them. With such a profile,
they remain candidate-first and must complete the isolated runtime gate before confirmation.

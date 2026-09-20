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
